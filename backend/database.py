"""Async SQLAlchemy engine/session for Supabase PostgreSQL.

2026-09-12 : la migration Supabase est TERMINEE. La production tourne sur
PostgreSQL (schema `blueseatra`). L'ancien avertissement "The app currently
runs on MongoDB" etait perime et a deja induit un diagnostic errone.

Ce module est aussi le point d'injection du contexte de tenant pour RLS :
voir set_current_tenant() / tenant_session() plus bas.

FIXES applied:
  - pool_pre_ping=True  (was False — dead connections were never tested)
  - asyncpg connect_args key is `prepared_statement_cache_size` (not `statement_cache_size`)
  - Handle both 'postgres://' and 'postgresql://' URI schemes (Supabase issues either)
  - Added ssl='require' to connect_args (Supabase mandates TLS)
  - Reduced pool_size to 8 + max_overflow=2 to stay under the free-tier
    Supavisor limit of 15 client connections per service.
  - pool_timeout lowered to 20 s (30 s was too long for a web request cycle)
"""
import os
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

load_dotenv(Path(__file__).parent / '.env')

DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()

# Schema that holds the Blueseatra tables. Tables were created in a dedicated
# 'blueseatra' schema (not 'public'). asyncpg is told to use it via search_path
# so the existing SQLAlchemy models (which reference unqualified table names)
# resolve correctly. Override with DB_SCHEMA if you ever move the tables.
DB_SCHEMA = os.environ.get('DB_SCHEMA', 'blueseatra').strip() or 'blueseatra'

Base = declarative_base()

engine = None
AsyncSessionLocal = None

# --- Moteur AUTH -- etape 3/3 du durcissement RLS ---------------------------
# Second moteur, dedie au chemin d'AUTHENTIFICATION et aux operations SYSTEME.
#
# Pourquoi deux moteurs : a l'etape finale, les tables metier passeront sous
# FORCE ROW LEVEL SECURITY avec un role NON proprietaire et NOBYPASSRLS. Or
# trois lectures ont lieu AVANT qu'un tenant existe -- ce sont celles de
# l'authentification elle-meme (users, tenant_users, tenants). Sous FORCE
# elles renverraient zero ligne et le login deviendrait impossible.
#
# Le chemin d'authentification garde donc un role privilegie, sur un moteur
# distinct et a portee reduite, tandis que le chemin METIER passera sur le
# role restreint.
#
# INCIDENT DU 12/09/2026 -- POURQUOI CETTE VARIABLE S'APPELLE _APP
# ------------------------------------------------------------------
# La premiere version de ce code lisait DATABASE_URL_AUTH et en faisait le
# moteur d'AUTHENTIFICATION. C'etait une INVERSION : l'operateur y a
# naturellement mis les identifiants du role RESTREINT (blueseatra_app),
# alors que le chemin d'authentification a besoin du role PRIVILEGIE pour
# lire users / tenants / tenant_users. Resultat immediat en production :
# plus aucun login possible ("Connexion au serveur impossible").
#
# Le nom de la variable etait le piege. "URL pour le chemin AUTH" designe
# le role privilegie, mais se lit comme "URL du nouveau role". Le sens
# correct est l'inverse : c'est le chemin METIER qui recoit le role
# restreint, tandis que l'authentification CONSERVE DATABASE_URL.
#
# D'ou DATABASE_URL_APP : "URL du role applicatif restreint". Le mot APP
# fait echo au nom du role lui-meme (blueseatra_app), ce qui rend
# l'association evidente et l'inversion difficile a reproduire.
#
# REPLI SUR : si DATABASE_URL_APP n'est pas definie, le moteur METIER EST
# le moteur principal (DATABASE_URL, privilegie). Deployer ce code sans
# rien configurer est donc un non-evenement strict -- aucune connexion
# supplementaire, aucun changement de comportement.
#
# INVARIANT A NE JAMAIS ROMPRE : le chemin d'AUTHENTIFICATION utilise
# TOUJOURS DATABASE_URL. Il ne doit jamais devenir configurable, sinon
# l'incident du 12/09 redevient possible.
DATABASE_URL_APP = os.environ.get('DATABASE_URL_APP', '').strip()

# Compatibilite : ancien nom, desormais IGNORE. Detecte au demarrage pour
# avertir plutot que d'echouer en silence (voir l'avertissement plus bas).
_DATABASE_URL_AUTH_OBSOLETE = os.environ.get('DATABASE_URL_AUTH', '').strip()

auth_engine = None
AuthSessionLocal = None


def _build_connect_args(url: str) -> dict:
    args = {
        "prepared_statement_cache_size": 0,
        "statement_cache_size": 0,
        "command_timeout": 30,
        "server_settings": {"search_path": f"{DB_SCHEMA},public"},
    }
    # Supabase impose TLS, mais un PostgreSQL LOCAL (tests) n'a pas de SSL.
    if not any(h in url for h in ("localhost", "127.0.0.1")):
        args["ssl"] = "require"
    return args


def _normalise(url: str) -> str:
    """Normalise le schema d'URI et force le pilote asyncpg."""
    # FIX: support both 'postgres://' (Supabase default) and 'postgresql://'.
    if url.startswith('postgres://'):
        url = 'postgresql' + url[len('postgres'):]
    # asyncpg driver for runtime; psycopg2 (sync) is used by Alembic separately.
    return url.replace('postgresql://', 'postgresql+asyncpg://', 1)


def _fabrique_moteur(url: str, pool_size: int, max_overflow: int):
    """Cree un moteur async avec la configuration durement acquise de ce projet.

    Extrait en fonction pour que le moteur AUTH herite EXACTEMENT des memes
    correctifs que le principal. Dupliquer ce bloc aurait garanti qu'un des
    deux derive au premier ajustement -- le meme mecanisme qui a produit
    l'incident DB_SCHEMA du 12/09/2026.
    """
    return create_async_engine(
        _normalise(url),
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=20,
        pool_recycle=600,        # Supavisor ferme les connexions idle vers 5 min
        pool_pre_ping=True,      # sinon une connexion morte plante au 1er usage
        echo=False,
        connect_args=_build_connect_args(url),
    )


def _fabrique_sessions(moteur):
    return async_sessionmaker(
        bind=moteur,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


# Budget de connexions : le palier gratuit Supavisor plafonne a 15 clients par
# service. Avec DEUX moteurs a 8+2 on monterait a 20, donc saturation. Les
# pools sont reduits des qu'un second moteur existe reellement : 5+2 pour le
# metier, 2+1 pour l'authentification, soit 10 -- la meme enveloppe qu'avant,
# repartie. Le chemin AUTH est peu sollicite (login, resolution du tenant),
# 3 connexions suffisent largement.
if DATABASE_URL_APP and DATABASE_URL_APP != DATABASE_URL:
    # Le chemin METIER porte l'essentiel du trafic, le chemin AUTH est
    # sollicite au login et a la resolution du tenant : 3 connexions y
    # suffisent largement.
    _POOL_METIER, _OVERFLOW_METIER = 5, 2
    _POOL_AUTH, _OVERFLOW_AUTH = 2, 1
else:
    _POOL_METIER, _OVERFLOW_METIER = 8, 2
    _POOL_AUTH, _OVERFLOW_AUTH = 0, 0


if DATABASE_URL:
    # Conserve pour compatibilite : referencee ailleurs dans le projet.
    ASYNC_DATABASE_URL = _normalise(DATABASE_URL)

    # Moteur AUTH : TOUJOURS DATABASE_URL, le role privilegie. Non
    # configurable, par conception -- voir l'incident du 12/09/2026.
    # Il doit pouvoir lire users / tenants / tenant_users AVANT qu'un
    # tenant soit connu.
    auth_engine = _fabrique_moteur(DATABASE_URL, _POOL_AUTH or 8, _OVERFLOW_AUTH or 2)
    AuthSessionLocal = _fabrique_sessions(auth_engine)

    if DATABASE_URL_APP and DATABASE_URL_APP != DATABASE_URL:
        # Moteur METIER : role restreint (blueseatra_app), NOBYPASSRLS et
        # non proprietaire. C'est lui qui passera sous FORCE RLS.
        engine = _fabrique_moteur(DATABASE_URL_APP, _POOL_METIER, _OVERFLOW_METIER)
        AsyncSessionLocal = _fabrique_sessions(engine)
    else:
        # REPLI : un seul moteur, privilegie. Comportement identique a
        # avant l'etape 3.
        engine = auth_engine
        AsyncSessionLocal = AuthSessionLocal

    if _DATABASE_URL_AUTH_OBSOLETE:
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "DATABASE_URL_AUTH est definie mais IGNOREE : cette variable a "
            "ete renommee DATABASE_URL_APP le 12/09/2026, car son ancien "
            "sens etait inverse (elle recevait le role restreint alors "
            "qu'elle alimentait le chemin d'authentification, ce qui "
            "cassait le login). Deplacer la valeur vers DATABASE_URL_APP "
            "puis supprimer DATABASE_URL_AUTH."
        )


async def get_db():
    """DESACTIVEE VOLONTAIREMENT -- ne pas reactiver telle quelle.

    Cette dependance FastAPI rendait une session du moteur METIER SANS
    positionner app.tenant_id. Elle n'est utilisee nulle part (verifie
    par test), et elle doit le rester.

    POURQUOI ELLE EST DANGEREUSE
    ----------------------------
    Depuis que le moteur metier tourne sous blueseatra_app (NOBYPASSRLS,
    non proprietaire), RLS s'applique reellement. Or une requete sans
    app.tenant_id ne leve AUCUNE erreur : elle renvoie simplement zero
    ligne. Mesure le 12/09/2026 lors du pre-vol -- les 11 tables metier
    renvoyaient 0 ligne, alors qu'elles contiennent 639 lignes pour le
    tenant teste.

    Un endpoint qui utiliserait get_db() verrait donc des listes vides,
    des "introuvable" sur des objets existants, et des INSERT rejetes
    par la politique WITH CHECK -- sans trace d'erreur exploitable. Le
    pire mode de defaillance possible.

    QUOI UTILISER A LA PLACE
    ------------------------
      - tenant_session()  : chemin metier, emet app.tenant_id ;
      - auth_session()    : users / tenants / tenant_users ;
      - system_context()  : balayage transverse assume, tous tenants.

    En pratique, passer par PGDatabase (pg_adapter) qui route seul.
    """
    raise RuntimeError(
        "get_db() est desactivee : elle ne positionne pas app.tenant_id, "
        "donc sous RLS elle renvoie silencieusement zero ligne. Utiliser "
        "tenant_session() pour le metier, auth_session() pour "
        "users/tenants/tenant_users, ou system_context() pour un "
        "balayage transverse assume. Voir la docstring."
    )
    yield  # pragma: no cover -- conserve la signature de generateur


# ===========================================================================
# Contexte de tenant pour Row Level Security -- ETAPE 2/3 du durcissement
# ===========================================================================
# Constat de l'audit du 12/09/2026 : RLS est activee sur les 14 tables avec
# des politiques correctes, mais elle est INERTE sur le chemin applicatif.
# blueseatra.current_tenant() lit `request.jwt.claims`, renseigne par
# PostgREST et non par la connexion asyncpg directe, ou il vaut NULL.
#
# Ce module publie donc le tenant courant a la base, pour que les politiques
# puissent enfin s'appliquer.
#
#   ETAPE 1 (migration SQL) : current_tenant() accepte app.tenant_id en repli
#   ETAPE 2 (ce code)       : chaque session emet la valeur
#   ETAPE 3 (a venir)       : role non-proprietaire + FORCE ROW LEVEL SECURITY
#
# Tant que l'etape 3 n'est pas faite, ce code n'a AUCUN effet observable : le
# role du backend contourne RLS. C'est voulu -- on installe la plomberie
# avant d'ouvrir l'eau, pour que l'etape 3 ne soit qu'un interrupteur.
# ===========================================================================

# ContextVar et non variable globale : chaque requete asyncio a son propre
# contexte. Avec une globale, deux requetes concurrentes de deux tenants
# differents s'ecraseraient mutuellement -- exactement la fuite que ce
# mecanisme est censee empecher.
_tenant_ctx: ContextVar = ContextVar("blueseatra_tenant_id", default=None)


def set_current_tenant(tenant_id):
    """Declare le tenant de l'unite de travail courante. Rend un jeton de reset."""
    return _tenant_ctx.set(tenant_id)


def reset_current_tenant(token) -> None:
    _tenant_ctx.reset(token)


def get_current_tenant():
    return _tenant_ctx.get()


@asynccontextmanager
async def tenant_context(tenant_id):
    """Fixe le tenant pour la duree du bloc, puis restaure l'etat precedent.

    A utiliser dans toute tache de fond ou boucle de worker, qui recoivent
    leur tenant en parametre et non via une requete HTTP.
    """
    token = _tenant_ctx.set(tenant_id)
    try:
        yield
    finally:
        _tenant_ctx.reset(token)


# set_config(..., is_local => true) est l'equivalent PARAMETRABLE de
# `SET LOCAL`. On ne peut pas ecrire `SET LOCAL app.tenant_id = :t` : la
# syntaxe SET n'accepte aucun parametre lie, ce qui imposerait une
# concatenation de chaine -- donc une injection SQL sur la valeur meme qui
# porte le cloisonnement. set_config evite entierement ce piege.
_SET_TENANT = text("SELECT set_config('app.tenant_id', :tenant_id, true)")


@asynccontextmanager
async def tenant_session():
    """Session applicative, portant le tenant courant s'il est connu.

    `is_local => true` (equivalent SET LOCAL) est OBLIGATOIRE : la portee est
    la TRANSACTION. Avec un `SET` global, la valeur survivrait sur la
    connexion, et comme le pool en recycle 8 a 10, le tenant fuirait d'une
    requete vers la suivante -- un bug strictement pire que l'absence de
    cloisonnement, car intermittent et quasi impossible a reproduire. Le
    pooler de transactions Supabase (port 6543) rend ce point encore plus
    critique.

    Absence de tenant : aucune valeur n'est emise. Ce n'est pas un oubli mais
    le cas des operations SYSTEME -- _requeue_stuck_on_startup au demarrage,
    ou l'authentification qui doit lire `users` AVANT de connaitre le tenant.
    Voir le plan de l'etape 3 pour le traitement de ces chemins.
    """
    if AsyncSessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured (Supabase not connected yet).")
    async with AsyncSessionLocal() as session:
        tenant_id = _tenant_ctx.get()
        if tenant_id:
            # Emis AVANT toute requete : set_config ouvre la transaction et la
            # valeur reste valide jusqu'au commit ou rollback, donc pour
            # toutes les requetes de cette session.
            await session.execute(_SET_TENANT, {"tenant_id": tenant_id})
        yield session


def with_tenant(fn):
    """Decorateur : fixe le contexte de tenant depuis l'argument `tenant_id`.

    Destine aux taches de fond et boucles de worker, qui recoivent leur
    tenant en parametre au lieu de le tirer d'une requete HTTP. Sans lui,
    ces chemins ouvriraient des sessions sans contexte et seraient les
    premiers a casser a l'etape 3.

    Prefere a un `async with tenant_context(...)` manuel dans chaque corps
    de fonction : impossible de l'oublier au milieu d'un refactoring, et
    aucune reindentation du code existant.
    """
    import functools
    import inspect

    signature = inspect.signature(fn)

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            lies = signature.bind_partial(*args, **kwargs)
            tenant_id = lies.arguments.get("tenant_id")
        except TypeError:
            tenant_id = None
        async with tenant_context(tenant_id):
            return await fn(*args, **kwargs)

    return wrapper


# ===========================================================================
# Session AUTH et contexte SYSTEME -- etape 3/3
# ===========================================================================
# Deux chemins echappent au cloisonnement par tenant, et ce n'est pas un
# defaut de conception :
#
#   1. L'AUTHENTIFICATION lit users / tenant_users / tenants AVANT qu'un
#      tenant soit connu. C'est meme l'objet de ces lectures : determiner
#      quel est le tenant.
#
#   2. Les operations SYSTEME balaient volontairement tous les tenants.
#      Exemple reel : _requeue_stuck_on_startup() remet en file les demandes
#      restees bloquees apres un redeploy, toutes entreprises confondues, et
#      propage le tenant_id de chaque ligne. Sous FORCE RLS sans contexte,
#      elle lirait zero ligne : elle ne planterait pas, elle CESSERAIT DE
#      PROTEGER en silence. La pire categorie de regression.
#
# Ces deux chemins passent donc par le moteur AUTH, qui conservera un role
# privilegie. Tout le reste passera par le role restreint sous FORCE RLS.
#
# Ce n'est pas un affaiblissement : aujourd'hui la totalite du cloisonnement
# repose sur le code. Apres l'etape 3, les tables METIER sont garanties par
# la base, et seules les tables d'authentification restent protegees par le
# code -- couvert par le test statique sur l'AST de server.py. C'est une
# amelioration stricte, pas un compromis.
# ===========================================================================

_system_ctx: ContextVar = ContextVar("blueseatra_system_op", default=False)


def is_system_context() -> bool:
    return _system_ctx.get()


@asynccontextmanager
async def system_context():
    """Marque le bloc comme operation SYSTEME : sessions sur le moteur AUTH.

    A n'employer que pour du travail sans tenant appelant : demarrage,
    maintenance, taches transverses. JAMAIS sur un chemin declenche par une
    requete utilisateur -- ce serait un contournement volontaire du
    cloisonnement, et le seul moyen de le rendre inoffensif serait de ne
    jamais l'ecrire.
    """
    token = _system_ctx.set(True)
    try:
        yield
    finally:
        _system_ctx.reset(token)


def with_system_context(fn):
    """Variante decorateur de system_context()."""
    import functools

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        async with system_context():
            return await fn(*args, **kwargs)

    return wrapper


@asynccontextmanager
async def auth_session():
    """Session privilegiee : authentification et operations systeme.

    N'emet AUCUN app.tenant_id, volontairement : il n'y a pas de tenant a
    declarer sur ces chemins.
    """
    if AuthSessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured (Supabase not connected yet).")
    async with AuthSessionLocal() as session:
        yield session
