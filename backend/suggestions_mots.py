"""Suggestions de mots pendant la frappe (02/10/2026).

Le chiffreur tape « disj » : on propose les mots qui EXISTENT dans ses
catalogues, du plus frequent au plus rare (disjoncteur, 27 637 offres), avec
leurs synonymes du metier (vocabulaire_btp). La recherche lourde ne part que
sur un mot complet choisi.

Sources :
- fournisseurs : table blueseatra.vocabulaire_recherche, lue par la fonction
  vocabulaire_suggestions() (cloisonnee : entreprise courante + catalogue
  commun), filtree sur les sources actives (devis) ou visibles (comparateur) ;
- catalogue interne : designations deja en memoire (cache du catalogue actif) ;
- synonymes : vocabulaire_btp.LIBELLES.

Ne leve jamais : une suggestion indisponible ne doit pas gener la saisie.
"""
from __future__ import annotations

import logging
import re
from collections import Counter

from sqlalchemy import text

import catalogue_chiffrage
import catalogue_commun
import vocabulaire_btp
from database import get_current_tenant, tenant_session
from fournisseur_recherche import normalise

log = logging.getLogger(__name__)

LIMITE = 8
PORTEES = ("devis", "comparateur")
_MOT_VALIDE = re.compile(r"^[a-z0-9.+]{2,40}$")

SQL_SUGGESTIONS = text("""
    SELECT mot, nb_offres
      FROM blueseatra.vocabulaire_suggestions(
               CAST(:tenants AS text[]), CAST(:sources AS text[]), :prefixe, :limite)
""")


def decoupe(q: str) -> tuple[str, str]:
    """(debut deja saisi, prefixe du dernier mot). Prefixe vide si la saisie
    se termine par un espace : le mot est complet, rien a proposer."""
    brut = q or ""
    if not brut.strip() or brut[-1].isspace():
        return normalise(brut), ""
    mots = normalise(brut).split()
    if not mots:
        return "", ""
    return " ".join(mots[:-1]), mots[-1]


def _synonymes(mot: str) -> list[str] | None:
    try:
        lib = vocabulaire_btp.libelles(mot)
    except Exception:  # pragma: no cover - vocabulaire statique
        return None
    if not lib:
        return None
    autres = [l for l in lib if normalise(l) != mot]
    return autres or None


def mots_internes(designations: list[str], prefixe: str) -> Counter:
    """Mots du catalogue interne commencant par `prefixe` (une fois par article)."""
    c: Counter = Counter()
    for d in designations:
        vus = {m for m in normalise(d).split()
               if m.startswith(prefixe) and len(m) >= 2 and re.search(r"[a-z]", m)}
        c.update(vus)
    return c


async def _mots_fournisseurs(prefixe: str, portee: str, limite: int) -> list[tuple[str, int]]:
    tenant = get_current_tenant()
    if not tenant:
        return []
    if portee == "comparateur":
        sources = await catalogue_chiffrage.sources_visibles(tenant)
    else:
        sources, _ = await catalogue_chiffrage._sources_recherche(tenant)
    if not sources:
        return []
    tenants = [tenant] if tenant == catalogue_commun.TENANT_COMMUN else [tenant, catalogue_commun.TENANT_COMMUN]
    async with tenant_session() as session:
        lignes = (await session.execute(SQL_SUGGESTIONS, {
            "tenants": tenants, "sources": list(sources)[:200],
            "prefixe": prefixe, "limite": limite})).all()
    return [(r[0], int(r[1])) for r in lignes]


async def suggerer(q: str, portee: str = "devis", designations_internes: list[str] | None = None,
                   limite: int = LIMITE) -> dict:
    """Suggestions pour ce qui est tape.

    Composition de mots (02/10/2026) : on propose d'abord les GROUPES de
    mots qui continuent la frappe — « porte c » -> « porte coupe feu », ou
    « porte » + espace -> les groupes commencant par porte — puis les mots
    simples pour le dernier mot partiel. Chaque suggestion porte
    `remplace` : le nombre de mots tapes qu'elle remplace (1 pour un mot
    isole, 2 ou 3 pour un groupe).
    """
    brut = q or ""
    mots = normalise(brut).split()
    complet = bool(brut) and brut[-1].isspace()
    reponse = {"debut": " ".join(mots[:-1]) if not complet else " ".join(mots),
               "prefixe": "" if complet else (mots[-1] if mots else ""),
               "suggestions": []}
    portee = portee if portee in PORTEES else "devis"

    async def groupe(groupes: list, prefixe_sql: str, seul_isole: bool) -> None:
        try:
            for mot, n in await _mots_fournisseurs(prefixe_sql, portee, limite):
                if seul_isole and " " in mot:
                    continue            # l'appel mots isoles ne garde que les mots isoles
                groupes.append((mot, n))
        except Exception:
            # Migration absente ou base lente : on garde le catalogue interne
            # et les synonymes, sans bloquer la saisie.
            log.warning("suggestions fournisseurs indisponibles", exc_info=True)

    trouves: list[tuple[str, int]] = []
    phrase = " ".join(mots[-3:]) if mots else ""
    if complet and phrase:
        # Mot complet : GROUPES qui le continuent (« porte » + espace).
        await groupe(trouves, phrase + " ", False)
    elif not complet and len(mots) >= 2:
        # Dernier mot partiel : GROUPES commencant par les mots tapes.
        await groupe(trouves, phrase, False)

    isoles: list[tuple[str, int]] = []
    if not complet and reponse["prefixe"] and _MOT_VALIDE.match(reponse["prefixe"]):
        await groupe(isoles, reponse["prefixe"], True)

    compte: Counter = Counter()
    if designations_internes and reponse["prefixe"] and not complet:
        compte.update(mots_internes(designations_internes, reponse["prefixe"]))
        for mot, n in isoles:
            compte[mot] += n
        couples = sorted(compte.items(), key=lambda kv: (-kv[1], kv[0]))
    else:
        couples = sorted(isoles, key=lambda kv: (-kv[1], kv[0]))

    suggestions = [{"mot": m, "nb_offres": n, "synonymes": _synonymes(m),
                    "remplace": len(m.split())}
                   for m, n in ([*sorted(trouves, key=lambda kv: (-kv[1], kv[0])), *couples])[:limite]]

    # Termes du metier connus (« ph+n », « tetrapolaire ») absents des mots
    # trouves : proposes en fin de liste, sans compte.
    deja = {s["mot"] for s in suggestions}
    for cle in sorted(vocabulaire_btp.LIBELLES):
        if len(suggestions) >= limite:
            break
        # Uniquement pour un dernier mot PARTIEL d'au moins 2 lettres : mot
        # complet ou prefixe d'une lettre ne declenche pas de bruit.
        if (len(reponse["prefixe"]) >= 2 and cle.startswith(reponse["prefixe"])
                and " " not in cle and cle not in deja):
            suggestions.append({"mot": cle, "nb_offres": None, "synonymes": _synonymes(cle),
                                "remplace": 1})
    reponse["suggestions"] = suggestions
    return reponse
