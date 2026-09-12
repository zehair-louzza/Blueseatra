"""Routage AUTH / METIER -- etape 3/3 du durcissement RLS.

Ces tests verrouillent la partie la plus dangereuse de l'etape 3 : le
routage par table. Une erreur ici n'est pas un bug qui plante -- c'est un
bug qui REND SILENCIEUX un contournement du cloisonnement (une table
metier basculee par erreur sur le moteur privilegie), ou qui CASSE LE
LOGIN (une table d'authentification basculee par erreur sur le role
restreint). Les deux sont graves et les deux sont silencieux au demarrage.

Aucune base de donnees, aucun reseau : les deux moteurs sont simules par
des fabriques distinctes, pour pouvoir affirmer QUEL moteur a servi
chaque appel.
"""
import asyncio

import pytest

import database as db_mod
import pg_adapter as pg
from database import (
    is_system_context,
    reset_current_tenant,
    set_current_tenant,
    system_context,
    with_system_context,
)
from pg_adapter import MODELS, TABLES_AUTH, _session_pour


class SessionFactice:
    def __init__(self, etiquette):
        self.etiquette = etiquette
        self.executions = []

    async def execute(self, statement, params=None):
        self.executions.append((str(statement), params))
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def deux_moteurs(monkeypatch):
    """Deux fabriques DISTINCTES : sert a prouver quel moteur a ete choisi."""
    metier_crees, auth_crees = [], []

    def fabrique_metier():
        s = SessionFactice("METIER")
        metier_crees.append(s)
        return s

    def fabrique_auth():
        s = SessionFactice("AUTH")
        auth_crees.append(s)
        return s

    monkeypatch.setattr(db_mod, "AsyncSessionLocal", fabrique_metier)
    monkeypatch.setattr(db_mod, "AuthSessionLocal", fabrique_auth)
    return metier_crees, auth_crees


@pytest.fixture(autouse=True)
def contexte_propre():
    jeton_tenant = set_current_tenant(None)
    jeton_systeme = db_mod._system_ctx.set(False)
    yield
    reset_current_tenant(jeton_tenant)
    db_mod._system_ctx.reset(jeton_systeme)


# ---------------------------------------------------------------------------
# La liste TABLES_AUTH elle-meme
# ---------------------------------------------------------------------------

def test_tables_auth_est_exactement_users_tenants_tenant_users():
    """Toute table AJOUTEE ou RETIREE ici doit etre un choix explicite.

    Si ce test echoue apres une modification de MODELS, la question a se
    poser est : cette nouvelle table lit-elle des donnees AVANT de
    connaitre le tenant ? Si non, elle ne doit PAS entrer dans TABLES_AUTH
    -- l'y mettre par erreur la sortirait de la protection FORCE RLS a
    venir.
    """
    assert TABLES_AUTH == frozenset({"users", "tenants", "tenant_users"})


def test_toutes_les_tables_auth_existent_dans_models():
    """Une entree fantome dans TABLES_AUTH serait un signe de derive."""
    assert TABLES_AUTH <= set(MODELS.keys())


# ---------------------------------------------------------------------------
# Le routage lui-meme
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("table", sorted(TABLES_AUTH))
def test_tables_auth_routent_vers_auth_session(deux_moteurs, table):
    metier_crees, auth_crees = deux_moteurs

    async def scenario():
        async with _session_pour(table):
            pass

    asyncio.run(scenario())
    assert len(auth_crees) == 1, f"{table} devrait creer une session AUTH"
    assert len(metier_crees) == 0, f"{table} a cree une session METIER par erreur"


@pytest.mark.parametrize("table", sorted(set(MODELS.keys()) - TABLES_AUTH))
def test_tables_metier_routent_vers_tenant_session_hors_contexte_systeme(deux_moteurs, table):
    metier_crees, auth_crees = deux_moteurs

    async def scenario():
        set_current_tenant("tenant-a")
        async with _session_pour(table):
            pass

    asyncio.run(scenario())
    assert len(metier_crees) == 1, f"{table} devrait creer une session METIER"
    assert len(auth_crees) == 0, f"{table} a cree une session AUTH par erreur"


def test_le_contexte_systeme_devie_une_table_metier_vers_auth(deux_moteurs):
    """Le scenario de _requeue_stuck_on_startup : requests, sans tenant, au demarrage."""
    metier_crees, auth_crees = deux_moteurs
    assert "requests" not in TABLES_AUTH, "requests doit rester une table metier"

    async def scenario():
        async with system_context():
            async with _session_pour("requests"):
                pass

    asyncio.run(scenario())
    assert len(auth_crees) == 1, (
        "une operation systeme sur une table metier doit passer par le "
        "moteur AUTH, pas par le moteur restreint qui sera sous FORCE RLS"
    )
    assert len(metier_crees) == 0


def test_hors_contexte_systeme_la_meme_table_repasse_par_metier(deux_moteurs):
    """Le contexte systeme ne doit PAS fuir sur l'appel suivant."""
    metier_crees, auth_crees = deux_moteurs

    async def scenario():
        async with system_context():
            async with _session_pour("requests"):
                pass
        # Sorti du bloc : retour au comportement normal. Un tenant est
        # desormais OBLIGATOIRE sur le chemin metier (tenant_session()
        # echoue sans lui), donc on en fournit un -- ce qui rend au
        # passage le test plus proche du chemin reel.
        async with db_mod.tenant_context("tenant-temoin"):
            async with _session_pour("requests"):
                pass

    asyncio.run(scenario())
    assert len(auth_crees) == 1, (
        "Dans le bloc system_context(), la table metier doit passer par le "
        f"moteur AUTH. Moteurs AUTH crees : {len(auth_crees)}"
    )
    assert len(metier_crees) == 1, (
        "Hors du bloc, la meme table doit repasser par le moteur METIER : "
        "le contexte systeme ne doit pas fuir sur l'appel suivant. "
        f"Moteurs METIER crees : {len(metier_crees)}"
    )


def test_table_auth_reste_sur_auth_meme_en_contexte_systeme(deux_moteurs):
    """Les deux conditions de routage sont un OU, pas un XOR : verifie l'ordre."""
    metier_crees, auth_crees = deux_moteurs

    async def scenario():
        async with system_context():
            async with _session_pour("users"):
                pass

    asyncio.run(scenario())
    assert len(auth_crees) == 1
    assert len(metier_crees) == 0


# ---------------------------------------------------------------------------
# with_system_context : le decorateur reellement cable sur la tache de fond
# ---------------------------------------------------------------------------

def test_with_system_context_active_puis_desactive():
    async def scenario():
        avant = is_system_context()

        @with_system_context
        async def tache():
            return is_system_context()

        pendant = await tache()
        apres = is_system_context()
        return avant, pendant, apres

    avant, pendant, apres = asyncio.run(scenario())
    assert (avant, pendant, apres) == (False, True, False)


def test_with_system_context_nettoie_apres_exception():
    @with_system_context
    async def tache():
        raise ValueError("boom")

    async def scenario():
        with pytest.raises(ValueError):
            await tache()
        return is_system_context()

    assert asyncio.run(scenario()) is False


def test_requeue_stuck_on_startup_est_decoree():
    """Verification statique : sans @with_system_context, cette tache
    ouvrirait des sessions METIER sans tenant -- et sous FORCE RLS future,
    elle lirait silencieusement zero ligne au lieu de proteger."""
    import re
    from pathlib import Path

    source = (Path(__file__).resolve().parent.parent / "server.py").read_text(encoding="utf-8")
    motif = re.compile(r"@with_system_context\s*\n\s*async def _requeue_stuck_on_startup\s*\(", re.M)
    assert motif.search(source), (
        "_requeue_stuck_on_startup() n'est pas decoree par @with_system_context."
    )


# ---------------------------------------------------------------------------
# Repli et sens des moteurs -- regression de l'incident du 12/09/2026
# ---------------------------------------------------------------------------

def test_repli_sans_database_url_app():
    """Le coeur de la reversibilite.

    Sans configuration supplementaire dans Render, le moteur METIER DOIT
    etre exactement le moteur AUTH (meme objet, pas seulement equivalent)
    -- donc aucune connexion additionnelle et comportement identique a
    avant l'etape 3.
    """
    assert db_mod.DATABASE_URL_APP == "" or db_mod.AsyncSessionLocal is db_mod.AuthSessionLocal, (
        "DATABASE_URL_APP est definie dans CET environnement de test, ce "
        "qui invalide l'hypothese de repli. Verifier les variables d'env."
    )


def test_le_chemin_auth_n_est_pas_configurable():
    """REGRESSION -- incident du 12/09/2026 : login casse en production.

    La premiere version lisait DATABASE_URL_AUTH et en faisait le moteur
    d'AUTHENTIFICATION. L'operateur y a naturellement mis le role
    RESTREINT (blueseatra_app), qui n'a AUCUN droit sur `users`. Plus
    aucun login n'etait possible.

    Le sens correct : le chemin METIER recoit le role restreint, le
    chemin d'AUTHENTIFICATION conserve TOUJOURS DATABASE_URL.

    Ce test verifie par lecture du source que le moteur AUTH est bien
    construit depuis DATABASE_URL et jamais depuis une variable
    configurable.
    """
    import re
    from pathlib import Path

    source = (Path(__file__).resolve().parent.parent / "database.py").read_text(encoding="utf-8")

    motif_auth = re.compile(
        r"auth_engine\s*=\s*_fabrique_moteur\(\s*DATABASE_URL\s*,", re.M
    )
    assert motif_auth.search(source), (
        "Le moteur AUTH n'est plus construit depuis DATABASE_URL. "
        "Le chemin d'authentification doit TOUJOURS utiliser le role "
        "privilegie : il lit users/tenants/tenant_users avant qu'un "
        "tenant soit connu. Le rendre configurable a casse la production "
        "le 12/09/2026."
    )

    motif_interdit = re.compile(
        r"auth_engine\s*=\s*_fabrique_moteur\(\s*DATABASE_URL_APP", re.M
    )
    assert not motif_interdit.search(source), (
        "INVERSION DETECTEE : le moteur AUTH est construit depuis "
        "DATABASE_URL_APP (role restreint). C'est exactement le bug du "
        "12/09/2026 -- le login devient impossible."
    )


def test_le_chemin_metier_utilise_bien_la_variable_app():
    """Symetrique du precedent : le role restreint doit aller au METIER."""
    import re
    from pathlib import Path

    source = (Path(__file__).resolve().parent.parent / "database.py").read_text(encoding="utf-8")
    motif = re.compile(r"engine\s*=\s*_fabrique_moteur\(\s*DATABASE_URL_APP\s*,", re.M)
    assert motif.search(source), (
        "Le moteur METIER n'est pas construit depuis DATABASE_URL_APP. "
        "C'est lui qui doit porter le role restreint destine a FORCE RLS."
    )


def test_ancien_nom_detecte_et_signale():
    """DATABASE_URL_AUTH ne doit pas etre silencieusement ignoree.

    Un operateur qui a suivi l'ancien runbook aurait une variable definie
    et sans effet : le pire des cas, puisque rien ne l'alerterait. Le code
    doit emettre un avertissement explicite.
    """
    from pathlib import Path

    source = (Path(__file__).resolve().parent.parent / "database.py").read_text(encoding="utf-8")
    assert "_DATABASE_URL_AUTH_OBSOLETE" in source, (
        "La detection de l'ancienne variable DATABASE_URL_AUTH a disparu. "
        "Sans elle, une configuration heritee serait ignoree en silence."
    )
    assert "IGNOREE" in source or "ignoree" in source.lower(), (
        "L'avertissement sur DATABASE_URL_AUTH doit dire explicitement "
        "que la variable est ignoree."
    )


# ---------------------------------------------------------------------------
# get_db() : dependance sans contexte tenant, doit rester inutilisee
# ---------------------------------------------------------------------------

def test_get_db_echoue_bruyamment():
    """get_db() ne doit jamais rendre une session sans app.tenant_id.

    Sous RLS, une requete sans contexte tenant renvoie zero ligne SANS
    erreur -- le pire mode de defaillance. Mesure le 12/09/2026 : les 11
    tables metier renvoyaient 0 ligne au lieu de 639.
    """
    import asyncio

    async def consomme():
        async for _ in db_mod.get_db():
            return "une session a ete rendue"
        return "generateur vide"

    try:
        resultat = asyncio.run(consomme())
    except RuntimeError as e:
        msg = str(e)
        assert "app.tenant_id" in msg, (
            "Le message d'erreur doit expliquer la cause (app.tenant_id "
            f"absent), or il dit : {msg}"
        )
        assert "tenant_session" in msg, (
            "Le message doit indiquer l'alternative a utiliser."
        )
        return
    raise AssertionError(
        f"get_db() n'a pas leve RuntimeError : {resultat}. Elle rendrait "
        "une session sans contexte tenant, donc des resultats vides "
        "silencieux sous RLS."
    )


def test_get_db_n_est_utilisee_nulle_part():
    """Aucun endpoint ne doit dependre de get_db().

    Si ce test echoue, c'est qu'un endpoint vient d'etre branche sur une
    session sans contexte tenant -- il renverra des listes vides en
    production sans lever d'erreur.
    """
    import re
    from pathlib import Path

    backend = Path(__file__).resolve().parent.parent
    coupables = []
    for fichier in backend.rglob("*.py"):
        if "tests_security" in str(fichier) or fichier.name == "database.py":
            continue
        txt = fichier.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"Depends\(\s*get_db\s*\)|=\s*get_db\b|\bget_db\(\)", txt):
            coupables.append(fichier.name)

    assert not coupables, (
        f"get_db() est referencee dans : {', '.join(coupables)}. "
        "Cette dependance ne positionne pas app.tenant_id : sous RLS elle "
        "renvoie zero ligne sans erreur. Utiliser tenant_session(), "
        "auth_session() ou system_context()."
    )
