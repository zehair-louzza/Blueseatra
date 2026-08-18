"""Découpe une demande en options exclusives (soit A soit B). Aucun prix."""
from __future__ import annotations

import copy
import re

_SOIT = re.compile(
    r"soit\s+(?P<a>.+?)\s+ou\s+soit\s+(?P<b>.+?)(?=(?:\n\n|!!|Merci|Cordialement|$))",
    re.I | re.S,
)
_OU_PIECES = re.compile(
    r"(?:soit\s+)?(?P<a>le\s+remplacement\s+total\s+de\s+[^.\n]+?)\s+"
    r"ou\s+(?:soit\s+)?les\s+pi[eè]ces\s+suivantes[^\n]*:?\s*(?P<b>.*)",
    re.I | re.S,
)
_OPTION_N = re.compile(r"option\s*(\d+)\s*[:\-–]\s*(.+)", re.I)
_PART_LINE = re.compile(r"^[A-Z0-9][A-Z0-9 /_.-]{3,80}$")


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip(" \t-.,;:"))


_ACTION_VERB_RE = re.compile(
    r"^(?:le |la |les |l['’])?"
    r"(?:remplacement(?: total| partiel)?|pose|d[ée]pose|installation|"
    r"r[ée]paration|changement|fourniture(?: et pose)?|mise en place|"
    r"entretien|nettoyage|v[ée]rification|contr[ôo]le|maintenance|"
    r"intervention sur|d[ée]montage|montage)\s+"
    r"(?:de |du |de la |des |d['’])?",
    re.I,
)
_LEADING_ARTICLE_RE = re.compile(r"^(?:le |la |les |l['’]|du |de la |des |de )", re.I)


def _strip_action_verb(text: str) -> str:
    """Nom d'article seul pour le matching catalogue (pas le verbe d'action).
    Ex. "le remplacement total de la pompe de relevage" -> "pompe de relevage".
    Voir matching.article_only — même règle, dupliquée ici pour éviter un
    import croisé quote_scenarios <-> matching."""
    s = _clean(text or "")
    prev = None
    while prev != s:
        prev = s
        s = _ACTION_VERB_RE.sub("", s).strip()
    s = _LEADING_ARTICLE_RE.sub("", s).strip()
    return s or _clean(text or "")


def _part_lines(block: str) -> list[str]:
    out = []
    for raw in (block or "").splitlines():
        line = raw.strip().strip("-•*")
        if not line or line.startswith("!!") or line.lower().startswith("merci"):
            continue
        if _PART_LINE.match(line) or (
            line.isupper() and len(line) > 4 and not line.lower().startswith("soit")
        ):
            out.append(line)
    return out


def _from_extracted_options(extracted: dict) -> list[dict] | None:
    opts = extracted.get("quote_options")
    if not isinstance(opts, list) or len(opts) < 2:
        return None
    rows = []
    for i, o in enumerate(opts, 1):
        if not isinstance(o, dict):
            continue
        label = _clean(o.get("label") or o.get("description") or f"Option {i}")
        items = o.get("line_items") or [{"description": label, "quantity": 1, "unit": "ens"}]
        rows.append({
            "label": label,
            "description": _clean(o.get("description") or label),
            "line_items": items,
            "labor_hours": o.get("labor_hours"),
            "travel_days": o.get("travel_days"),
            "crew_size": o.get("crew_size"),
            "excludes": o.get("excludes") or "",
        })
    return rows if len(rows) >= 2 else None


def detect_exclusive_options(text: str) -> list[dict]:
    """Parse raw request text into exclusive options (0 if none)."""
    blob = text or ""
    m = _OU_PIECES.search(blob)
    if m:
        a = _clean(m.group("a"))
        parts = _part_lines(m.group("b") or "")
        b_label = "Pièces à remplacer sur la pompe existante" if "pompe" in a.lower() else "Pièces listées"
        b_items = [{"description": p, "quantity": 1, "unit": "u"} for p in parts] or [
            {"description": b_label, "quantity": 1, "unit": "ens"}
        ]
        # Matching catalogue = nom de l'article seul, jamais la phrase d'action
        # (voir skill devis-options-master / rapprochement-catalogue-sans-prix).
        a_article = _strip_action_verb(a)
        return [
            {
                "label": a[0].upper() + a[1:] if a else "Remplacement total",
                "description": a,
                "line_items": [{"description": a_article, "quantity": 1, "unit": "ens"}],
                "labor_hours": 4.5,
                "travel_days": 1,
                "crew_size": None,  # laisse estimate_chantier appliquer la regle 2 pers. par defaut
                "excludes": b_label,
            },
            {
                "label": b_label,
                "description": "Remplacement des pièces suivantes sans échange du corps de pompe : "
                + ", ".join(parts),
                "line_items": b_items,
                "labor_hours": 2.5,
                "travel_days": 1,
                "crew_size": None,  # laisse estimate_chantier decider (petit travail <= 3h -> 1 pers.)
                "excludes": a,
            },
        ]

    m = _SOIT.search(blob)
    if m:
        a, b = _clean(m.group("a")), _clean(m.group("b"))
        if a and b and a.lower() != b.lower():
            return [
                {
                    "label": a[:80],
                    "description": a,
                    "line_items": [{"description": a, "quantity": 1, "unit": "ens"}],
                    "labor_hours": None,
                    "travel_days": 1,
                    "crew_size": None,
                    "excludes": b,
                },
                {
                    "label": b[:80],
                    "description": b,
                    "line_items": [{"description": b, "quantity": 1, "unit": "ens"}],
                    "labor_hours": None,
                    "travel_days": 1,
                    "crew_size": None,
                    "excludes": a,
                },
            ]

    numbered = []
    for line in blob.splitlines():
        om = _OPTION_N.search(line)
        if om:
            numbered.append((_clean(om.group(2)), int(om.group(1))))
    if len(numbered) >= 2:
        numbered.sort(key=lambda x: x[1])
        return [
            {
                "label": lab[:80],
                "description": lab,
                "line_items": [{"description": lab, "quantity": 1, "unit": "ens"}],
                "labor_hours": None,
                "travel_days": 1,
                "crew_size": None,
                "excludes": "",
            }
            for lab, _ in numbered
        ]
    return []


def split_quote_scenarios(extracted: dict, raw_text: str = "") -> list[dict]:
    """Clone extracted once per exclusive option. Single item if no split."""
    base = copy.deepcopy(extracted or {})
    opts = _from_extracted_options(base) or detect_exclusive_options(
        "\n".join([raw_text or "", base.get("description") or ""])
    )
    if not opts:
        return [base]
    out = []
    n = len(opts)
    others = [o["label"] for o in opts]
    for i, opt in enumerate(opts, 1):
        row = copy.deepcopy(base)
        excl = opt.get("excludes") or ", ".join(x for x in others if x != opt["label"])
        row["quote_option_index"] = i
        row["quote_option_count"] = n
        row["option_label"] = opt["label"]
        row["description"] = opt["description"] or opt["label"]
        row["line_items"] = opt["line_items"]
        if opt.get("labor_hours") is not None:
            row["labor_hours"] = opt["labor_hours"]
        if opt.get("travel_days") is not None:
            row["travel_days"] = opt["travel_days"]
        if opt.get("crew_size") is not None:
            row["crew_size"] = opt["crew_size"]
        row["option_excludes"] = excl
        out.append(row)
    return out
