"""Crée (ou retrouve) le catalogue Stripe de Blueseatra — ticket #90.

Idempotent : chaque prix porte une `lookup_key` stable ; un prix déjà présent
n'est jamais recréé. Refuse une clé live sans --live explicite.

    STRIPE_SECRET_KEY=sk_test_... python scripts/stripe/creer_catalogue.py
Grille validée le 24/09/2026 (docs/tarification-2026-09.md). Montants HT, EUR.
"""
import os, ssl, sys
import httpx

API = "https://api.stripe.com/v1"
PRODUITS = [
    # code produit, nom, [(lookup_key, montant en centimes, intervalle ou None)]
    ("initial", "Blueseatra Initial", [("initial_mensuel", 5900, "month"), ("initial_annuel", 59000, "year")]),
    ("pilotage", "Blueseatra Pilotage", [("pilotage_mensuel", 14900, "month"), ("pilotage_annuel", 149000, "year")]),
    ("performance", "Blueseatra Performance", [("performance_mensuel", 39900, "month"), ("performance_annuel", 399000, "year")]),
    ("siege", "Siège supplémentaire", [("siege_mensuel", 1500, "month"), ("siege_annuel", 15000, "year")]),
    ("recharge_devis_25", "Recharge 25 devis assistés", [("recharge_devis_25", 1900, None)]),
    ("recharge_devis_100", "Recharge 100 devis assistés", [("recharge_devis_100", 5900, None)]),
    ("recharge_pages_500", "Recharge 500 pages lues", [("recharge_pages_500", 3900, None)]),
]


def main(live: bool = False) -> int:
    cle = os.environ.get("STRIPE_SECRET_KEY", "")
    if cle.startswith(("sk_live_", "rk_live_")) and not live:
        print("Clé live refusée : relancer avec --live après validation (Epic 7).")
        return 2
    h = {"Stripe-Version": "2024-06-20"}
    if cle:
        h["Authorization"] = f"Bearer {cle}"      # sinon : authentification injectée par le proxy
    # Vérification TLS conservée ; seul le contrôle X.509 « strict » de Python 3.13+
    # est relâché, car certains proxys d'entreprise signent sans « key usage ».
    ctx = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE"))
    ctx.verify_flags &= ~getattr(ssl, "VERIFY_X509_STRICT", 0)
    c = httpx.Client(base_url=API, headers=h, timeout=30, verify=ctx)
    cles = [lk for _, _, prix in PRODUITS for lk, _, _ in prix]
    existants = {}
    for i in range(0, len(cles), 10):            # Stripe : 10 lookup_keys au plus par requête
        r = c.get("/prices", params=[("lookup_keys[]", k) for k in cles[i:i + 10]] + [("limit", 100)]).json()
        if "error" in r:
            print("Erreur Stripe :", r["error"].get("message"))
            return 1
        existants.update({p["lookup_key"]: p for p in r.get("data", [])})
    produits = {p["metadata"].get("blueseatra_code"): p for p in c.get("/products", params={"limit": 100}).json().get("data", [])
                if p.get("metadata", {}).get("blueseatra_code")}
    for code, nom, prix in PRODUITS:
        prod = produits.get(code)
        if not prod:
            prod = c.post("/products", data={"name": nom, "metadata[blueseatra_code]": code, "tax_code": "txcd_10103001"},
                          headers={"Idempotency-Key": f"produit-{code}"}).json()
            print(f"produit créé : {nom} ({prod.get('id')})")
        for lk, montant, intervalle in prix:
            if lk in existants:
                p = existants[lk]
                ok = p["unit_amount"] == montant and p["active"]
                print(f"  prix existant : {lk} {p['unit_amount'] / 100:.2f} € {'' if ok else '— ÉCART avec la grille, à corriger dans Stripe'}")
                continue
            d = {"product": prod["id"], "currency": "eur", "unit_amount": montant, "lookup_key": lk,
                 "tax_behavior": "exclusive", "metadata[blueseatra_code]": lk}
            if intervalle:
                d["recurring[interval]"] = intervalle
            p = c.post("/prices", data=d, headers={"Idempotency-Key": f"prix-{lk}-{montant}"}).json()
            print(f"  prix créé : {lk} {montant / 100:.2f} € HT {('/ ' + intervalle) if intervalle else '(paiement unique)'} ({p.get('id') or p})")
    return 0


if __name__ == "__main__":
    sys.exit(main(live="--live" in sys.argv))
