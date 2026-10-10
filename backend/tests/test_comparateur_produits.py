"""Comparateur : prix comparables et regroupement par produit (format unique).

Tests sans base. Les donnees reprennent des cas reels de production
(02/10/2026) : conduit ICA YESSS vendu par 100 m, onduleur Schneider
rattache chez Prolians par marque + reference.
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import catalogue_commun  # noqa: E402
import comparateur_produits as cp  # noqa: E402
import fournisseur_recherche as fr  # noqa: E402

TENANT = "11111111-1111-4111-8111-111111111111"
COMMUN = catalogue_commun.TENANT_COMMUN


def _o(i, f, prix, cle=None, pub=None, unite="U", qte=1.0, niveau="GTIN", desig=None):
    return {"id": i, "fournisseur": f, "prix_net_ht": prix, "prix_unite_base_ht": pub,
            "cle_produit": cle, "unite_base": unite, "qte_par_conditionnement": qte,
            "niveau_identification": niveau, "designation": desig or i}


# --- prix comparable ----------------------------------------------------------

def test_prix_comparable_prefere_l_unite_de_base():
    assert cp.prix_comparable({"prix_net_ht": 146.61, "prix_unite_base_ht": 1.4661}) == 1.4661
    assert cp.prix_comparable({"prix_net_ht": 6.83}) == 6.83          # non normalisee
    assert cp.prix_comparable({"prix_net_ht": 0, "prix_unite_base_ht": None}) is None
    assert cp.prix_comparable({"prix_net_ht": "abc"}) is None


def test_tri_lot_de_100_m_passe_devant():
    lignes = [_o("rexel", "Rexel", 2.0, pub=2.0, unite="M"),
              _o("yesss", "YESSS", 146.61, pub=1.4661, unite="M", qte=100),
              _o("sans", "SFIC", None)]
    assert [l["id"] for l in sorted(lignes, key=cp.cle_tri)] == ["yesss", "rexel", "sans"]


def test_meilleurs_par_fournisseur_au_prix_comparable():
    m = cp.meilleurs_par_fournisseur([
        _o("y1", "YESSS", 146.61, pub=1.4661, unite="M", qte=100),
        _o("y2", "YESSS", 1.9, pub=1.9, unite="M"),
        _o("r1", "Rexel", 1.08, pub=1.08, unite="M"),
        _o("x", "Prolians", None)])
    assert [(x["fournisseur"], x["id"]) for x in m] == [("Rexel", "r1"), ("YESSS", "y1")]
    assert m[1]["prix_net_ht"] == 146.61 and m[1]["prix_unite_base_ht"] == 1.4661
    assert m[1]["qte_par_conditionnement"] == 100


def test_enrichir_ne_touche_pas_aux_valeurs_source():
    ligne = {"id": "a", "designation": "Libelle source", "marque": "LEGRAND S.N.C.",
             "prix_net_ht": 9.16, "prix_public_ht": None}
    cp.enrichir(ligne, {"cle_produit": "GTIN:03245064067744", "marque_canonique": "Legrand",
                        "prix_unite_base_ht": "9.16", "prix_public_ht": "28.5",
                        "anomalies": ["GTIN_CLE", "PRIX_EXTREME"], "qte_par_conditionnement": "1"})
    assert ligne["designation"] == "Libelle source" and ligne["marque"] == "LEGRAND S.N.C."
    assert ligne["marque_canonique"] == "Legrand" and ligne["prix_unite_base_ht"] == 9.16
    assert ligne["prix_public_ht"] == 28.5                # complete seulement s'il manque
    assert ligne["anomalies"] == ["PRIX_EXTREME"]         # GTIN_CLE : controle interne
    assert cp.enrichir({"id": "b"}, None) == {"id": "b"}


# --- regroupement -------------------------------------------------------------

def test_regroupe_par_cle_et_garde_le_moins_cher_par_fournisseur():
    g = cp.regrouper_par_produit([
        _o("r", "Rexel", 89.75, "GTIN:00731304338444", 89.75, niveau="MARQUE_REF",
           desig="Easy UPS BVS - onduleur 1 ph line-interactive - 230V - 500VA"),
        _o("p", "Prolians", 106.11, "GTIN:00731304338444", 106.11, niveau="MARQUE_REF",
           desig="Onduleur EASY UPS 500 VA"),
        _o("y", "YESSS", 165.10, "GTIN:00731304338444", 165.10),
        _o("y2", "YESSS", 170.0, "GTIN:00731304338444", 170.0),
        _o("seul", "Rexel", 5.0, "GTIN:03245064067744", 5.0),     # 1 fournisseur
        _o("sans_cle", "SFIC", 3.0)],
        ids_trouves={"r", "y"})
    assert len(g) == 1
    p = g[0]
    assert p["nb_fournisseurs"] == 3 and p["gtin"] == "00731304338444"
    assert [o["fournisseur"] for o in p["offres"]] == ["Rexel", "Prolians", "YESSS"]
    assert p["prix_min"] == 89.75 and p["prix_max"] == 165.10 and p["ecart_pct"] == 84
    assert [o["ecart_pct"] for o in p["offres"]] == [0, 18, 84]
    assert p["offres"][1]["designation_differente"] is True       # trouvee par la cle
    assert p["offres"][0]["designation_differente"] is False
    assert p["offres"][1]["par_reference"] is True
    assert p["offres"][2]["autres_offres"] == 1
    assert p["designation"].startswith("Easy UPS BVS")            # la plus complete


def test_unites_differentes_pas_d_ecart():
    g = cp.regrouper_par_produit([
        _o("a", "Rexel", 1.08, "GTIN:1", 1.08, unite="M"),
        _o("b", "YESSS", 50.0, "GTIN:1", 50.0, unite="U")])
    assert g[0]["unites_differentes"] is True
    assert g[0]["ecart_pct"] is None and g[0]["unite_base"] is None
    assert all(o["ecart_pct"] is None for o in g[0]["offres"])


def test_lot_compare_au_metre():
    g = cp.regrouper_par_produit([
        _o("r", "Rexel", 1.08, "GTIN:2", 1.08, unite="M"),
        _o("y", "YESSS", 146.61, "GTIN:2", 1.4661, unite="M", qte=100)])
    assert g[0]["unite_base"] == "M" and g[0]["ecart_pct"] == 36  # et non 13 475 %
    assert g[0]["offres"][1]["prix_net_ht"] == 146.61


def test_ordre_des_resultats_et_plafond():
    offres = []
    for k in range(30):
        offres += [_o(f"a{k}", "Rexel", 10, f"GTIN:{k}", 10), _o(f"b{k}", "YESSS", 12, f"GTIN:{k}", 12)]
    ordre = [f"GTIN:{k}" for k in reversed(range(30))]
    g = cp.regrouper_par_produit(offres, ordre=ordre)
    assert len(g) == cp.MAX_GROUPES
    assert g[0]["cle_produit"] == "GTIN:29"


# --- recherche complete sur session simulee ------------------------------------

class _Res:
    def __init__(self, lignes):
        self.lignes = lignes

    def mappings(self):
        return self

    def all(self):
        return self.lignes

    def __iter__(self):
        return iter(self.lignes)


class _Nested:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _Session:
    """Repond selon la requete ; enregistre SQL et parametres."""

    def __init__(self, panne_norm=False, unite_y="M"):
        self.executed, self.panne_norm, self.unite_y = [], panne_norm, unite_y

    def begin_nested(self):
        return _Nested()

    async def execute(self, sql, params=None):
        q = str(sql)
        self.executed.append((q, params))
        if "offres_candidates(" in q:
            return _Res([
                {"id": "r1", "tenant_id": COMMUN, "supplier_id": "s1", "price_ht": 1.08,
                 "recherche_norm": "conduit ica 20"},
                {"id": "y1", "tenant_id": COMMUN, "supplier_id": "s2", "price_ht": 146.61,
                 "recherche_norm": "conduit ica 20"}])
        if "FROM blueseatra.suppliers f" in q and "WHERE f.tenant_id" in q:
            return _Res([{"tenant_id": COMMUN, "id": "s1", "name": "Rexel"},
                         {"tenant_id": COMMUN, "id": "s2", "name": "YESSS"}])
        if "n.offre_id = ANY(:ids)" in q:
            if self.panne_norm:
                raise RuntimeError("relation offres_normalisees inexistante")
            return _Res([
                {"id": "r1", "cle_produit": "GTIN:2", "unite_base": "M", "qte_par_conditionnement": 1,
                 "prix_unite_base_ht": 1.08, "niveau_identification": "GTIN", "anomalies": []},
                {"id": "y1", "cle_produit": "GTIN:3", "unite_base": self.unite_y, "qte_par_conditionnement": 100,
                 "prix_unite_base_ht": 1.4661, "niveau_identification": "GTIN", "anomalies": []}])
        if "n.cle_produit = ANY(:cles)" in q:
            return _Res([
                {"id": "y1", "fournisseur": "YESSS", "designation": "Conduit ICA 20 - 100 m",
                 "prix_net_ht": 146.61, "cle_produit": "GTIN:3", "unite_base": "M",
                 "qte_par_conditionnement": 100, "prix_unite_base_ht": 1.4661,
                 "niveau_identification": "GTIN", "anomalies": [], "prix_public_norm": None},
                {"id": "p9", "fournisseur": "Point.P", "designation": "Gaine annelée 20 mm",
                 "prix_net_ht": 1.95, "cle_produit": "GTIN:3", "unite_base": "M",
                 "qte_par_conditionnement": 1, "prix_unite_base_ht": 1.95,
                 "niveau_identification": "GTIN", "anomalies": ["UNITE_SUPPOSEE", "GTIN_CLE"],
                 "prix_public_norm": 3.1}])
        if "o.id = ANY(:ids)" in q:
            return _Res([
                {"id": "r1", "fournisseur": "Rexel", "designation": "Conduit ICA 20", "prix_net_ht": 1.08},
                {"id": "y1", "fournisseur": "YESSS", "designation": "Conduit ICA 20 - 100 m",
                 "prix_net_ht": 146.61}])
        return _Res([])


class _Ctx:
    def __init__(self, s):
        self.s = s

    async def __aenter__(self):
        return self.s

    async def __aexit__(self, *a):
        return False


def _lancer(monkeypatch, session):
    monkeypatch.setattr(fr, "get_current_tenant", lambda: TENANT)
    monkeypatch.setattr(fr, "tenant_session", lambda: _Ctx(session))

    async def est_masque(_s, _t):
        return False
    monkeypatch.setattr(catalogue_commun, "est_masque", est_masque)
    return asyncio.run(fr.recherche("conduit ica 20"))


def test_recherche_compare_au_prix_par_unite_et_regroupe(monkeypatch):
    session = _Session()
    res = _lancer(monkeypatch, session)
    m = res["moins_cher_par_fournisseur"]
    assert [x["fournisseur"] for x in m] == ["Rexel", "YESSS"]
    assert m[1]["prix_unite_base_ht"] == 1.4661 and m[1]["prix_net_ht"] == 146.61
    assert res["prix"]["max"] == 1.47                      # et non 146,61
    p = res["produits_identiques"]
    assert len(p) == 1 and p[0]["cle_produit"] == "GTIN:3"
    assert [o["fournisseur"] for o in p[0]["offres"]] == ["YESSS", "Point.P"]
    assert p[0]["offres"][1]["designation_differente"] is True
    assert p[0]["offres"][1]["anomalies"] == ["UNITE_SUPPOSEE"]
    lignes = {l["id"]: l for l in res["resultats"]}
    assert lignes["y1"]["nb_fournisseurs_produit"] == 2
    assert lignes["r1"]["nb_fournisseurs_produit"] == 1
    # Filtre tenant explicite (forme exigee par test_tenant_isolation_static)
    # sur les deux lectures du format unique, en plus de RLS.
    lus = [(q, params) for q, params in session.executed if "offres_normalisees" in q]
    assert len(lus) == 2
    for q, params in lus:
        assert "n.tenant_id = :tenant_id" in q and "n.tenant_id = :commun" in q
        assert params["tenant_id"] == TENANT and params["commun"] == COMMUN
        assert params["avec_commun"] is True
    q, params = lus[1]
    assert "o.tenant_id = :tenant_id" in q                 # FILTRE_PERIMETRE
    assert "o.is_active" in q and "active_version_id" in q
    assert params["cles"] == ["GTIN:2", "GTIN:3"]


def test_catalogue_commun_masque_exclu_des_produits_identiques(monkeypatch):
    session = _Session()
    monkeypatch.setattr(fr, "get_current_tenant", lambda: TENANT)
    monkeypatch.setattr(fr, "tenant_session", lambda: _Ctx(session))

    async def est_masque(_s, _t):
        return True
    monkeypatch.setattr(catalogue_commun, "est_masque", est_masque)
    asyncio.run(fr.recherche("conduit ica 20"))
    lus = [p for q, p in session.executed if "offres_normalisees" in q]
    assert lus and all(p["avec_commun"] is False for p in lus)


def test_recherche_sans_table_normalisee_retombe_sur_les_prix_bruts(monkeypatch):
    res = _lancer(monkeypatch, _Session(panne_norm=True))
    assert [x["fournisseur"] for x in res["moins_cher_par_fournisseur"]] == ["Rexel", "YESSS"]
    assert res["moins_cher_par_fournisseur"][1]["prix_unite_base_ht"] == 146.61
    assert res["produits_identiques"] == []
    assert res["prix"]["max"] == 146.61


def test_unites_differentes_pas_d_ecart_dans_le_bloc_prix(monkeypatch):
    """« conduit icta 20 » le 02/10/2026 : 0,44 €/m contre 1,55 €/pièce, écart 253 %."""
    res = _lancer(monkeypatch, _Session(unite_y="U"))
    assert res["prix"]["unites_differentes"] is True
    assert res["prix"]["ecart_pct"] is None
    res = _lancer(monkeypatch, _Session())
    assert res["prix"]["unites_differentes"] is False
    assert res["prix"]["ecart_pct"] == 36


# --- panneau « meilleure correspondance » : garde de pertinence -------------
# Cas réel du 04/10/2026 (« porte coupe feu ») : pertinences mesurées en
# production — le panneau PVC Rexel et le déclencheur YESSS sont des
# accessoires qui mentionnent la demande (34-43 % du leader).
def _m(f, d, p):
    return {"fournisseur": f, "designation": d, "pertinence": p,
            "prix_unite_base_ht": 1.0, "id": f}


def test_panneau_garde_les_portes_reelles():
    meilleurs = [
        _m("LPB", "porte coupe feu 1/2 h reversible", 1.833),
        _m("Prolians", "porte metallique coupe feu 1 heure split ce", 1.583),
        _m("Point.P", "porte simple essential coupe feu ei30", 1.45),
        _m("Chausson", "bloc porte coupe feu 1 2h premafeu", 1.083),
        _m("Rexel", "panneau pvc porte coupe feu", 0.783),
        _m("AFDB", "ensemble western coupe feu pour porte 36 a 44 mm", 0.75),
        _m("YESSS", "declencheur electromagnetique pour porte coupe feu", 0.617),
    ]
    gardes, ecartes = cp.garder_meilleures_correspondances(meilleurs)
    assert {m["fournisseur"] for m in gardes} == {"LPB", "Prolians", "Point.P", "Chausson"}
    assert {m["fournisseur"] for m in ecartes} == {"Rexel", "AFDB", "YESSS"}
    assert ecartes[0]["designation"]  # désignation conservée pour l'affichage


def test_panneau_sans_pertinences_tout_garde():
    gardes, ecartes = cp.garder_meilleures_correspondances([_m("Rexel", "x", 0.0)])
    assert len(gardes) == 1 and ecartes == []


def test_panneau_vide():
    assert cp.garder_meilleures_correspondances([]) == ([], [])


def test_panneau_resultat_unique_toujours_garde():
    gardes, ecartes = cp.garder_meilleures_correspondances([_m("Rexel", "panneau pvc", 0.783)])
    assert len(gardes) == 1 and ecartes == []


def test_panneau_seuil_personnalise():
    meilleurs = [_m("A", "porte coupe feu", 1.0), _m("B", "porte coupe feu blinde", 0.7)]
    gardes, ecartes = cp.garder_meilleures_correspondances(meilleurs, rapport=0.8)
    assert [m["fournisseur"] for m in gardes] == ["A"]
    assert [m["fournisseur"] for m in ecartes] == ["B"]
