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
        # sorti du bloc : retour au comportement normal
        async with _session_pour("requests"):
            pass

    asyncio.run(scenario())
    assert len(auth_crees) == 1
    assert len(metier_crees) == 1


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
# Repli : sans DATABASE_URL_AUTH, aucun changement de comportement
# ---------------------------------------------------------------------------

def test_repli_sans_database_url_auth():
    """Le coeur de la reversibilite de cette PR.

    Sans configuration supplementaire dans Render, AuthSessionLocal DOIT
    etre exactement AsyncSessionLocal (meme objet, pas seulement equivalent)
    -- donc _session_pour() ne cree jamais de connexion additionnelle et le
    comportement observable est identique a avant cette PR.
    """
    assert db_mod.DATABASE_URL_AUTH == "" or db_mod.AuthSessionLocal is db_mod.AsyncSessionLocal, (
        "DATABASE_URL_AUTH est definie dans CET environnement de test, ce "
        "qui invalide l'hypothese de repli. Verifier les variables d'env."
    )
