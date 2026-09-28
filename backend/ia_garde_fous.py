"""Garde-fous de l'IA en production (ticket #88).

1. Schéma strict de la sortie d'extraction : types vérifiés, champs inconnus
   conservés mais signalés, et SURTOUT aucun prix, montant ou taux de TVA
   produit par l'IA ne passe (l'IA ne décide jamais d'un prix : FastAPI et
   le catalogue seuls le font).
2. Coupure d'urgence en une variable d'environnement :
   BLUESEATRA_IA_COUPURE = ""        fonctionnement normal
                         = "repli"   bascule vers BLUESEATRA_IA_REPLI_PROVIDER/MODEL
                         = "arret"   refus explicite ; l'extraction échoue proprement
                                     et le devis assisté est remboursé.
3. Journal par appel : rôle, fournisseur, modèle, durée, succès ou échec,
   taille des échanges et coût estimé, au format structuré (sans contenu).
"""
from __future__ import annotations

import functools
import inspect
import logging
import os
import time
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

log = logging.getLogger("blueseatra.ia")

CHAMPS_INTERDITS = {
    "price", "prix", "unit_price", "unit_price_ht", "prix_unitaire", "total", "total_ht", "total_ttc",
    "montant", "amount", "line_ht", "vat_rate", "tva", "taux_tva", "margin", "marge", "remise", "discount",
}


class IACoupee(RuntimeError):
    """Coupure d'urgence active : aucune requête n'est envoyée au modèle."""


def _texte(v):
    if v is None:
        return ""
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        return v.strip()
    return str(v)


def _nombre(v):
    if v in (None, "", "null"):
        return None
    try:
        n = float(str(v).replace(",", ".").replace("\u00a0", "").strip())
    except (TypeError, ValueError):
        return None
    return n if n >= 0 else None


class LigneExtraite(BaseModel):
    model_config = ConfigDict(extra="allow")
    label: str = ""
    qty: Optional[float] = None
    unit: str = ""
    line_type_hint: str = ""
    included_items: list[str] = Field(default_factory=list)

    _t = field_validator("label", "unit", "line_type_hint", mode="before")(lambda v: _texte(v))
    _n = field_validator("qty", mode="before")(lambda v: _nombre(v))

    @field_validator("included_items", mode="before")
    @classmethod
    def _liste(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return [_texte(x) for x in (v or []) if _texte(x)]


class SortieExtraction(BaseModel):
    model_config = ConfigDict(extra="allow")
    donneur_d_ordre: str = ""
    client_name: str = ""
    client_final: str = ""
    client_email: str = ""
    location: str = ""
    description: str = ""
    urgency: Literal["urgent", "normal", "planifie"] = "normal"
    language: str = "fr"
    confidence: Optional[float] = None
    labor_hours: Optional[float] = None
    travel_days: Optional[float] = None
    crew_size: Optional[float] = None
    line_items: list[LigneExtraite] = Field(default_factory=list)
    quote_options: list[Any] = Field(default_factory=list)

    _t = field_validator("donneur_d_ordre", "client_name", "client_final", "client_email",
                         "location", "description", "language", mode="before")(lambda v: _texte(v))
    _n = field_validator("labor_hours", "travel_days", "crew_size", mode="before")(lambda v: _nombre(v))

    @field_validator("urgency", mode="before")
    @classmethod
    def _urgence(cls, v):
        t = _texte(v).lower()
        if t.startswith("urg") or t in ("haute", "high", "critique"):
            return "urgent"
        if t.startswith("planif") or t in ("programme", "programmé", "scheduled"):
            return "planifie"
        return "normal"

    @field_validator("confidence", mode="before")
    @classmethod
    def _confiance(cls, v):
        n = _nombre(v)
        if n is None:
            return None
        n = n / 100 if n > 1 else n
        return max(0.0, min(1.0, n))

    @field_validator("line_items", "quote_options", mode="before")
    @classmethod
    def _liste(cls, v):
        return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def _retirer_prix(obj, chemin="", retires=None):
    retires = [] if retires is None else retires
    if isinstance(obj, dict):
        for k in list(obj):
            if str(k).lower() in CHAMPS_INTERDITS:
                if obj[k] not in (None, "", 0):
                    retires.append(f"{chemin}{k}")
                obj.pop(k)
            else:
                _retirer_prix(obj[k], f"{chemin}{k}.", retires)
    elif isinstance(obj, list):
        for i, x in enumerate(obj):
            _retirer_prix(x, f"{chemin}{i}.", retires)
    return retires


def valider_extraction(data: dict) -> dict:
    """Renvoie la sortie validée. Les écarts sont listés dans `_anomalies_schema`
    et journalisés ; une sortie irrécupérable lève ValueError."""
    if not isinstance(data, dict):
        raise ValueError("Sortie IA non structurée (objet JSON attendu)")
    internes = {k: v for k, v in data.items() if str(k).startswith("_")}
    brut = {k: v for k, v in data.items() if not str(k).startswith("_")}
    retires = _retirer_prix(brut)
    anomalies = [f"prix ignoré : {c}" for c in retires]
    try:
        propre = SortieExtraction.model_validate(brut).model_dump()
    except ValidationError as e:   # ne devrait pas arriver : les validateurs convertissent
        raise ValueError(f"Sortie IA hors schéma : {e.errors()[:3]}") from e
    for champ in ("urgency", "confidence"):
        if champ in brut and brut[champ] not in (None, "") and propre[champ] != brut[champ]:
            anomalies.append(f"{champ} normalisé : {brut[champ]!r} → {propre[champ]!r}")
    if anomalies:
        log.warning("ia_sortie_corrigee anomalies=%s", "; ".join(anomalies[:10]))
        propre["_anomalies_schema"] = anomalies
    propre.update(internes)
    return propre


# --- Coupure d'urgence -----------------------------------------------------------

def mode_coupure() -> str:
    m = (os.environ.get("BLUESEATRA_IA_COUPURE") or "").strip().lower()
    return m if m in ("repli", "arret") else ""


def appliquer_coupure(provider: str, model: str, api_key: str) -> tuple[str, str, str]:
    m = mode_coupure()
    if m == "arret":
        raise IACoupee("Lecture IA suspendue temporairement par l'exploitation (coupure d'urgence). "
                       "Réessayez plus tard ; votre devis assisté n'est pas décompté.")
    if m == "repli":
        p = os.environ.get("BLUESEATRA_IA_REPLI_PROVIDER", "").strip().lower()
        mo = os.environ.get("BLUESEATRA_IA_REPLI_MODEL", "").strip()
        if not (p and mo):
            raise IACoupee("Coupure d'urgence en mode repli, mais aucun fournisseur de repli n'est configuré.")
        log.warning("ia_coupure_repli de=%s/%s vers=%s/%s", provider, model, p, mo)
        return p, mo, os.environ.get("BLUESEATRA_IA_REPLI_KEY", "") or api_key
    return provider, model, api_key


# --- Journal par appel -----------------------------------------------------------

# Coût indicatif en euros pour 1 000 caractères échangés (entrée + sortie).
# Le VPS OVH est un coût fixe : 0 par appel. Mistral : estimation prudente
# (≈ 4 caractères par jeton, tarif mistral-medium), à ajuster sur facture réelle.
COUT_PAR_1000_CAR = {"hermes": 0.0, "ollama": 0.0, "openai": 0.002, "mistral": 0.0008}


def journaliser(fournisseur: str):
    def deco(fn):
        @functools.wraps(fn)
        async def enveloppe(*args, **kwargs):
            # Le modèle est lu par son nom de paramètre : une clé API passée en
            # premier argument ne doit jamais finir dans les journaux.
            try:
                lies = inspect.signature(fn).bind_partial(*args, **kwargs).arguments
            except TypeError:
                lies = dict(kwargs)
            modele = lies.get("model") or "?"
            args_texte = [v for k, v in lies.items() if k not in ("api_key",) and isinstance(v, str)]
            role = kwargs.get("role") or ("vision" if kwargs.get("image_b64") else "-")
            taille_in = sum(len(x) for x in args_texte)
            t0 = time.perf_counter()
            ok, taille_out = False, 0
            try:
                sortie = await fn(*args, **kwargs)
                ok = True
                taille_out = len(sortie) if isinstance(sortie, str) else 0
                return sortie
            finally:
                ms = round((time.perf_counter() - t0) * 1000)
                cout = round(COUT_PAR_1000_CAR.get(fournisseur, 0.0) * (taille_in + taille_out) / 1000, 5)
                log.info("ia_appel fournisseur=%s modele=%s role=%s succes=%s duree_ms=%s car_in=%s car_out=%s cout_estime_eur=%s",
                         fournisseur, modele, role, ok, ms, taille_in, taille_out, cout)
        return enveloppe
    return deco
