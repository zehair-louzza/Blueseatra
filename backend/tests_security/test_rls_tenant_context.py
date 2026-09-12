"""Contexte de tenant pour RLS -- etape 2/3 du durcissement.

Ces tests verrouillent la plomberie qui rendra RLS effective a l'etape 3.
Ils sont ecrits MAINTENANT, avant l'activation de FORCE ROW LEVEL SECURITY,
parce qu'une erreur ici ne serait visible qu'au moment ou l'on ouvre l'eau
-- c'est-a-dire en production.

Le piege principal n'est pas l'absence de cloisonnement, c'est le
cloisonnement qui FUIT : un `SET` global au lieu d'un `SET LOCAL` laisse la
valeur sur la connexion, et comme le pool en recycle 8 a 10, le tenant
passe d'une requete a la suivante. Bug intermittent, quasi impossible a
reproduire, et strictement pire que pas de cloisonnement du tout. Plusieurs
tests ci-dessous ne servent qu'a interdire ce scenario.

Aucune base de donnees, aucun reseau : la session est simulee.
"""
import asyncio

import pytest

import database as db_mod
from database import (
    get_current_tenant,
    reset_current_tenant,
    set_current_tenant,
    tenant_context,
    tenant_session,
    with_tenant,
)


class SessionFactice:
    """Session SQLAlchemy simulee : enregistre les requetes recues."""

    def __init__(self):
        self.executions = []

    async def execute(self, statement, params=None):
        self.executions.append((str(statement), params))
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def close(self):
        return None

    async def rollback(self):
        return None


@pytest.fixture
def session_factice(monkeypatch):
    """Remplace AsyncSessionLocal par la fabrique factice."""
    creees = []

    def fabrique():
        s = SessionFactice()
        creees.append(s)
        return s

    monkeypatch.setattr(db_mod, "AsyncSessionLocal", fabrique)
    return creees


@pytest.fixture(autouse=True)
def contexte_propre():
    """Isole chaque test : aucun tenant ne doit deborder sur le suivant."""
    jeton = set_current_tenant(None)
    yield
    reset_current_tenant(jeton)


# ---------------------------------------------------------------------------
# Le contexte lui-meme
# ---------------------------------------------------------------------------

def test_aucun_tenant_par_defaut():
    assert get_current_tenant() is None


def test_tenant_context_restaure_l_etat_precedent():
    async def scenario():
        assert get_current_tenant() is None
        async with tenant_context("tenant-a"):
            assert get_current_tenant() == "tenant-a"
            async with tenant_context("tenant-b"):
                assert get_current_tenant() == "tenant-b"
            # Sortie du bloc imbrique : retour a A, jamais a None.
            assert get_current_tenant() == "tenant-a"
        assert get_current_tenant() is None

    asyncio.run(scenario())


def test_tenant_context_restaure_meme_en_cas_d_exception():
    """Une exception ne doit pas laisser un tenant colle au contexte."""
    async def scenario():
        with pytest.raises(RuntimeError):
            async with tenant_context("tenant-a"):
                raise RuntimeError("boom")
        assert get_current_tenant() is None

    asyncio.run(scenario())


def test_isolation_entre_taches_concurrentes():
    """LE test qui justifie l'emploi d'un ContextVar.

    Avec une variable globale, deux requetes concurrentes de deux tenants
    differents s'ecraseraient mutuellement -- precisement la fuite que ce
    mecanisme doit empecher. Ce test echouerait alors de facon aleatoire.
    """
    observes = {}

    async def travail(nom, tenant, delai):
        async with tenant_context(tenant):
            await asyncio.sleep(delai)          # entrelacement force
            observes[nom] = get_current_tenant()

    async def scenario():
        await asyncio.gather(
            travail("a", "tenant-a", 0.03),
            travail("b", "tenant-b", 0.01),
            travail("c", "tenant-c", 0.02),
        )

    asyncio.run(scenario())
    assert observes == {"a": "tenant-a", "b": "tenant-b", "c": "tenant-c"}


# ---------------------------------------------------------------------------
# tenant_session : ce qui est reellement emis a la base
# ---------------------------------------------------------------------------

def test_la_session_emet_le_tenant(session_factice):
    async def scenario():
        async with tenant_context("tenant-a"):
            async with tenant_session() as s:
                pass
        return s

    s = asyncio.run(scenario())
    assert len(s.executions) == 1, "exactement une instruction de contexte attendue"
    sql, params = s.executions[0]
    assert "set_config" in sql
    assert params == {"tenant_id": "tenant-a"}


def test_la_session_n_emet_rien_sans_tenant(session_factice):
    """Operations SYSTEME : demarrage, authentification avant resolution.

    Ne rien emettre est le comportement voulu, pas un oubli.
    """
    async def scenario():
        async with tenant_session() as s:
            pass
        return s

    s = asyncio.run(scenario())
    assert s.executions == []


def test_le_reglage_est_local_a_la_transaction(session_factice):
    """LE test le plus important du fichier.

    `is_local => true` est le troisieme argument de set_config. S'il passait
    a false, la valeur survivrait sur la connexion, et le pool (8 a 10
    connexions recyclees) ferait fuiter le tenant d'une requete vers la
    suivante. Ce test interdit cette regression.
    """
    async def scenario():
        async with tenant_context("tenant-a"):
            async with tenant_session() as s:
                pass
        return s

    s = asyncio.run(scenario())
    sql = s.executions[0][0].lower()
    assert "true" in sql, (
        "set_config doit etre appele avec is_local => true. Sans cela le "
        "tenant fuit d'une requete a la suivante via le pool de connexions."
    )
    assert "set local" not in sql, (
        "`SET LOCAL` n'accepte aucun parametre lie : l'utiliser imposerait "
        "une concatenation de chaine, donc une injection SQL sur la valeur "
        "meme qui porte le cloisonnement. Utiliser set_config."
    )


def test_la_valeur_du_tenant_est_un_parametre_lie(session_factice):
    """Pas de concatenation : la valeur ne doit jamais entrer dans le SQL."""
    malveillant = "x'; DROP TABLE blueseatra.quotes; --"

    async def scenario():
        async with tenant_context(malveillant):
            async with tenant_session() as s:
                pass
        return s

    s = asyncio.run(scenario())
    sql, params = s.executions[0]
    assert "DROP TABLE" not in sql, "la valeur a ete concatenee dans le SQL"
    assert params == {"tenant_id": malveillant}


def test_deux_sessions_successives_emettent_chacune_leur_tenant(session_factice):
    """Chaque transaction doit reaffirmer son tenant.

    Avec un reglage local a la transaction, rien ne persiste : ne pas le
    reemettre laisserait la seconde requete sans contexte.
    """
    async def scenario():
        async with tenant_context("tenant-a"):
            async with tenant_session():
                pass
        async with tenant_context("tenant-b"):
            async with tenant_session():
                pass

    asyncio.run(scenario())
    assert len(session_factice) == 2
    assert session_factice[0].executions[0][1] == {"tenant_id": "tenant-a"}
    assert session_factice[1].executions[0][1] == {"tenant_id": "tenant-b"}


# ---------------------------------------------------------------------------
# Le decorateur des taches de fond
# ---------------------------------------------------------------------------

def test_with_tenant_lit_l_argument_positionnel():
    @with_tenant
    async def tache(request_id, tenant_id):
        return get_current_tenant()

    assert asyncio.run(tache("req-1", "tenant-a")) == "tenant-a"


def test_with_tenant_lit_l_argument_nomme():
    @with_tenant
    async def tache(request_id, tenant_id=None):
        return get_current_tenant()

    assert asyncio.run(tache("req-1", tenant_id="tenant-b")) == "tenant-b"


def test_with_tenant_tolere_l_absence_de_tenant_id():
    """Une fonction sans parametre tenant_id ne doit pas exploser."""
    @with_tenant
    async def tache(autre):
        return get_current_tenant()

    assert asyncio.run(tache("x")) is None


def test_with_tenant_nettoie_apres_exception():
    @with_tenant
    async def tache(tenant_id):
        raise ValueError("boom")

    async def scenario():
        with pytest.raises(ValueError):
            await tache("tenant-a")
        return get_current_tenant()

    assert asyncio.run(scenario()) is None


def test_with_tenant_preserve_les_metadonnees():
    """functools.wraps : sinon FastAPI et les logs perdent le nom reel."""
    @with_tenant
    async def process_request(request_id, tenant_id):
        """Docstring d'origine."""
        return None

    assert process_request.__name__ == "process_request"
    assert "Docstring d'origine" in (process_request.__doc__ or "")


# ---------------------------------------------------------------------------
# Cablage effectif dans server.py (statique, sans importer FastAPI)
# ---------------------------------------------------------------------------

def test_les_taches_de_fond_sont_decorees():
    """Une tache de fond non decoree ouvrirait des sessions sans contexte.

    Elle serait la premiere a casser a l'etape 3, et le diagnostic serait
    indirect. Verification par lecture du source, pour ne pas dependre de
    l'import de server.py (qui exige FastAPI, jwt, etc.).
    """
    import re
    from pathlib import Path

    source = (Path(__file__).resolve().parent.parent / "server.py").read_text(encoding="utf-8")

    attendues = ["process_request", "_watchdog_reprocess_if_stuck", "_run_deep_vision"]
    for nom in attendues:
        motif = re.compile(
            r"@with_tenant\s*\n\s*async def " + re.escape(nom) + r"\s*\(",
            re.M,
        )
        assert motif.search(source), (
            f"{nom}() n'est pas decoree par @with_tenant. Cette tache recoit "
            f"un tenant_id en parametre et doit le publier au contexte, "
            f"sinon ses sessions n'emettront aucun tenant."
        )


def test_get_current_publie_le_tenant():
    """Le tenant doit etre publie APRES la verification d'appartenance.

    Le publier avant reviendrait a declarer a la base un tenant que
    l'appelant n'a pas encore prouve.
    """
    from pathlib import Path

    source = (Path(__file__).resolve().parent.parent / "server.py").read_text(encoding="utf-8")

    assert "set_current_tenant(payload[\"tenant_id\"])" in source, (
        "get_current() ne publie pas le tenant : tenant_session() n'aurait "
        "alors jamais rien a emettre sur le chemin HTTP."
    )

    position_controle = source.find('raise HTTPException(403, "No access to tenant")')
    position_publication = source.find('set_current_tenant(payload["tenant_id"])')
    assert position_controle != -1 and position_publication != -1
    assert position_publication > position_controle, (
        "set_current_tenant() est appele AVANT le controle d'appartenance au "
        "tenant. L'ordre doit etre inverse : ne jamais declarer un tenant "
        "non prouve."
    )
