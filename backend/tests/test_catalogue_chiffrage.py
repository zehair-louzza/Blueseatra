"""Sources fournisseurs du chiffrage (catalogue_chiffrage.py) — tests unitaires.

Sans base de donnees : les sessions SQLAlchemy sont remplacees par des faux
objets, catalogue_navigation par des doubles. On verifie surtout :
- la forme des articles renvoyes au selecteur du devis (meme champs que les
  pricing_items + marqueur de provenance) ;
- la construction de la requete SQL (clauses par source activee, jamais une
  cle client crue telle quelle) ;
- activer/desactiver ne supprime jamais rien (INSERT ... ON CONFLICT pour
  activer, UPDATE actif = false pour desactiver).
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import catalogue_chiffrage
import catalogue_navigation


TENANT = "11111111-1111-4111-8111-111111111111"
CLE_VERSION = "22222222-2222-4222-8222-222222222222"
CLE_HIST = "hist:33333333-3333-4333-8333-333333333333"


class FakeResult:
    """Resultat SQLAlchemy : .all() pour les etats, .mappings() pour les lignes."""

    def __init__(self, rows=None, mappings=None):
        self._rows = rows or []
        self._mappings = mappings or []

    def all(self):
        return self._rows

    def mappings(self):
        return self

    def __iter__(self):
        return iter(self._mappings)


class FakeSession:
    def __init__(self, results=None):
        # results : liste de FakeResult, consommee dans l'ordre ; le dernier
        # est reutilise si la requete depasse.
        self.results = list(results or [])
        self.executed = []

    async def execute(self, sql, params=None):
        self.executed.append((sql, params))
        if self.results:
            r = self.results.pop(0)
        else:
            r = FakeResult()
        return r

    async def commit(self):
        self.committed = True


class _Ctx:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *a):
        return False


def _patch(monkeypatch, session, fournisseurs=None, etats=None, resoudre_ok=True):
    monkeypatch.setattr(catalogue_chiffrage, "get_current_tenant", lambda: TENANT)
    monkeypatch.setattr(catalogue_chiffrage, "tenant_session", lambda: _Ctx(session))

    async def faux_fournisseurs():
        return {"fournisseurs": fournisseurs or [], "total_references": 0}

    async def faux_etats_tenant(tenant):
        return etats or {}

    async def faux_resoudre(session, tenant, cle):
        if not resoudre_ok or not cle:
            raise LookupError("Catalogue introuvable ou masqué pour cette entreprise.")

    monkeypatch.setattr(catalogue_navigation, "fournisseurs", faux_fournisseurs)
    monkeypatch.setattr(catalogue_navigation, "_resoudre", faux_resoudre)
    monkeypatch.setattr(catalogue_chiffrage, "_etats_tenant", faux_etats_tenant)


# --- Forme des articles renvoyes au selecteur du devis ---------------------

def test_en_article_forme_pricing_item():
    offre = {
        "id": "abc", "fournisseur": "Rexel", "designation": "Disjoncteur 16A",
        "marque": "ABB", "reference_fournisseur": "SN201SL", "code_ean": "4016",
        "prix_net_ht": 6.83, "prix_public_ht": 21.34, "unite_vente": "Pièce",
        "conditionnement": 1, "famille": "Modulaire", "url_produit": None,
    }
    a = catalogue_chiffrage._en_article(offre)
    # Champs attendus par le selecteur (QuoteEditor) et addFromCatalog.
    for k in ("item_code", "item_label", "unit", "brand", "supplier_main",
              "unit_price_ht", "vat_rate", "margin", "min_qty", "currency"):
        assert k in a, f"champ manquant : {k}"
    assert a["item_code"] == "SN201SL"
    assert a["item_label"] == "Disjoncteur 16A"
    assert a["unit_price_ht"] == 6.83
    assert a["supplier_main"] == "Rexel"
    # Marqueur de provenance + id prefixe : jamais de collision avec un
    # pricing_item du catalogue actif.
    assert a["source"] == "fournisseur"
    assert a["id"].startswith("frn:")


def test_en_article_sans_reference_ni_conditionnement():
    a = catalogue_chiffrage._en_article({"id": "x", "designation": "Gaine",
                                        "fournisseur": None})
    assert a["item_code"] == "x"
    assert a["unit"] == "u"
    assert a["min_qty"] == 1
    assert a["suppliers"] == []


# --- Recherche ---------------------------------------------------------------

def test_recherche_sans_requete_rend_vide(monkeypatch):
    _patch(monkeypatch, FakeSession())
    assert asyncio.run(catalogue_chiffrage.rechercher("   ")) == []


def test_recherche_sans_source_activee_rend_vide(monkeypatch):
    _patch(monkeypatch, FakeSession(), etats={CLE_VERSION: False})
    assert asyncio.run(catalogue_chiffrage.rechercher("disjoncteur")) == []


def test_recherche_ignore_les_sources_plus_visibles(monkeypatch):
    # Source activee en base mais disparue du parcours (masquee, supprimee)
    # : aucune clause ne doit partir en SQL.
    session = FakeSession()
    _patch(monkeypatch, session, fournisseurs=[], etats={CLE_VERSION: True})
    assert asyncio.run(catalogue_chiffrage.rechercher("disjoncteur")) == []
    assert session.executed == []


def test_recherche_construit_les_clauses_par_source(monkeypatch):
    session = FakeSession(results=[FakeResult(
        mappings=[{"id": "o1", "fournisseur": "Rexel", "designation": "Disjoncteur 16A",
                   "marque": None, "reference_fournisseur": None, "reference_fabricant": None,
                   "code_ean": None, "prix_net_ht": 7.5, "prix_public_ht": None,
                   "unite_vente": None, "conditionnement": None, "famille": None,
                   "sous_famille": None, "url_produit": None, "date_prix": None,
                   "catalogue_commun": False}])])
    _patch(monkeypatch, session,
           fournisseurs=[{"cle": CLE_VERSION, "fournisseur": "Rexel"},
                         {"cle": CLE_HIST, "fournisseur": "Prolians"}],
           etats={CLE_VERSION: True, CLE_HIST: True})
    articles = asyncio.run(catalogue_chiffrage.rechercher("disjoncteur 16a"))
    sql, params = session.executed[0]
    sql_text = str(sql)
    # Une clause par source activee, verrouillee sur sa version ou son
    # fournisseur (l'ordre d'iteration est libre), ET avec les conditions
    # de recherche. Defense en profondeur : le filtre tenant reste
    # explicite meme sur les cles de version.
    assert "o.version_id = :v" in sql_text
    assert "(o.tenant_id = :tenant_id OR o.tenant_id = :commun)" in sql_text
    assert "o.supplier_id = :h" in sql_text
    assert "recherche_norm" in sql_text
    assert set(params.values()) >= {CLE_VERSION, CLE_HIST[5:], TENANT}
    # Resultat marque fournisseur, dans l'ordre prix croissant.
    assert len(articles) == 1 and articles[0]["source"] == "fournisseur"
    assert "ORDER BY o.price_ht ASC" in sql_text


def test_recherche_n_echoue_jamais_sur_une_erreur(monkeypatch):
    async def boom():
        raise RuntimeError("base indisponible")

    monkeypatch.setattr(catalogue_chiffrage, "get_current_tenant", lambda: TENANT)
    monkeypatch.setattr(catalogue_chiffrage, "_etats_tenant", boom)
    assert asyncio.run(catalogue_chiffrage.rechercher("disjoncteur")) == []


# --- Bascule activer / desactiver --------------------------------------------

def test_basculer_refuse_une_cle_invalide(monkeypatch):
    session = FakeSession()
    _patch(monkeypatch, session, resoudre_ok=False)
    try:
        asyncio.run(catalogue_chiffrage.basculer("cle-inconnue", True, "u@x.fr"))
        assert False, "LookupError attendue"
    except LookupError:
        pass
    assert session.executed == []  # aucune ecriture


def test_basculer_activer_insere_sans_rien_supprimer(monkeypatch):
    session = FakeSession()
    _patch(monkeypatch, session)
    asyncio.run(catalogue_chiffrage.basculer(CLE_VERSION, True, "u@x.fr"))
    sql_text = str(session.executed[0][0])
    assert "INSERT INTO blueseatra.chiffrage_sources" in sql_text
    assert "ON CONFLICT (tenant_id, cle) DO UPDATE" in sql_text
    assert "DELETE" not in sql_text
    assert session.committed


def test_basculer_desactiver_ne_supprime_que_l_etat(monkeypatch):
    session = FakeSession()
    _patch(monkeypatch, session)
    asyncio.run(catalogue_chiffrage.basculer(CLE_VERSION, False, "u@x.fr"))
    sql_text = str(session.executed[0][0])
    # Desactiver = actif = false. Jamais DELETE : le contenu du fournisseur
    # et le choix de l'entreprise restent en place.
    assert "UPDATE blueseatra.chiffrage_sources" in sql_text
    assert "actif = false" in sql_text
    assert "DELETE" not in sql_text
    assert session.committed
