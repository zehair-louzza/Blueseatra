"""Temps passé par requête HTTP : total, SQL, connexions (en-tête Server-Timing).

Pourquoi (02/10/2026, ticket #86) : mesuré depuis le navigateur, /api/health
répond en 28 ms mais /api/auth/me en 916 ms et /api/catalog/active en 384 ms,
soit environ 180 ms par requête du pg_adapter. Sans mesure côté serveur,
impossible de savoir si le temps part dans le SQL, dans l'ouverture de
connexions (TLS vers Supavisor) ou dans le code.

Chaque réponse /api porte désormais :

    Server-Timing: app;dur=916.2, sql;dur=120.4;desc="5 requetes",
                   cnx;dur=0;desc="0 nouvelles / 5 emprunts"

- app : durée totale côté serveur ;
- sql : somme des durées d'exécution des requêtes (aller-retour réseau compris) ;
- cnx : connexions physiques ouvertes pendant la requête (une ouverture coûte
  une poignée de main TLS) et connexions empruntées au pool (chacune paie un
  ping de vérification, pool_pre_ping).

Aucune donnée métier ni SQL n'est exposé : seulement des nombres.
"""
from __future__ import annotations

import contextvars
import time
import weakref

from sqlalchemy import event


class Mesure:
    __slots__ = ("n_sql", "ms_sql", "n_connexions", "ms_connexions", "n_emprunts")

    def __init__(self):
        self.n_sql = 0
        self.ms_sql = 0.0
        self.n_connexions = 0
        self.ms_connexions = 0.0
        self.n_emprunts = 0


# Objet MUTABLE dans la variable de contexte : SQLAlchemy async exécute les
# événements dans un greenlet qui peut travailler sur une copie du contexte ;
# la copie référence le même objet, les compteurs restent partagés.
_mesure: contextvars.ContextVar[Mesure | None] = contextvars.ContextVar("mesure_temps", default=None)


def demarrer() -> tuple[Mesure, contextvars.Token]:
    m = Mesure()
    return m, _mesure.set(m)


def terminer(jeton: contextvars.Token) -> None:
    _mesure.reset(jeton)


def courante() -> Mesure | None:
    return _mesure.get()


def entete(m: Mesure, total_ms: float) -> str:
    return (f"app;dur={total_ms:.1f}, "
            f"sql;dur={m.ms_sql:.1f};desc=\"{m.n_sql} requetes\", "
            f"cnx;dur={m.ms_connexions:.1f};desc=\"{m.n_connexions} nouvelles / {m.n_emprunts} emprunts\"")


# Un id numérique peut être réutilisé après collecte d'un moteur. Le registre
# faible suit les objets vivants sans les retenir ni oublier un nouveau moteur.
_branches = weakref.WeakSet()


def brancher(moteur) -> None:
    """Attache les compteurs à un moteur (async ou sync). Idempotent."""
    sync = getattr(moteur, "sync_engine", moteur)
    if sync is None or sync in _branches:
        return
    _branches.add(sync)

    @event.listens_for(sync, "before_cursor_execute")
    def _avant(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        conn.info.setdefault("_mesure_t0", []).append(time.perf_counter())

    @event.listens_for(sync, "after_cursor_execute")
    def _apres(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        pile = conn.info.get("_mesure_t0") or []
        t0 = pile.pop() if pile else None
        m = _mesure.get()
        if m is not None and t0 is not None:
            m.n_sql += 1
            m.ms_sql += (time.perf_counter() - t0) * 1000

    @event.listens_for(sync, "do_connect")
    def _ouverture(dialect, conn_rec, cargs, cparams):  # noqa: ANN001
        conn_rec.info["_mesure_cnx_t0"] = time.perf_counter()

    @event.listens_for(sync.pool, "connect")
    def _ouverte(dbapi_conn, conn_rec):  # noqa: ANN001
        t0 = conn_rec.info.pop("_mesure_cnx_t0", None)
        m = _mesure.get()
        if m is not None:
            m.n_connexions += 1
            if t0 is not None:
                m.ms_connexions += (time.perf_counter() - t0) * 1000

    @event.listens_for(sync.pool, "checkout")
    def _emprunt(dbapi_conn, conn_rec, conn_proxy):  # noqa: ANN001
        m = _mesure.get()
        if m is not None:
            m.n_emprunts += 1
