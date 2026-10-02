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
import json
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
    # Cache des sources (20 s) : chaque test part d'un cache vide.
    catalogue_chiffrage.invalider_sources()
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
    # Une branche par source activee, chacune verrouillee sur son tenant
    # EXACT et sa version ou son fournisseur (ordre d'iteration libre), via
    # blueseatra.offres_candidates : sous RLS, une requete directe ne pouvait
    # pas utiliser l'index trigramme (TimeoutError en production, 01/10/2026).
    assert sql_text.count("blueseatra.offres_candidates(") == 2
    assert "UNION ALL" in sql_text
    assert "CAST(:termes AS jsonb), 200" in sql_text
    branches = {(tuple(params[f"t{i}"]), params[f"v{i}"], params[f"h{i}"]) for i in range(2)}
    assert branches == {((TENANT,), CLE_VERSION, None), ((TENANT,), None, CLE_HIST[5:])}
    termes = json.loads(params["termes"])
    assert termes == [[{"op": "like", "v": "%disjoncteur%"}], [{"op": "like", "v": "%16a%"}]]
    # Second temps : relecture des fiches par id, filtre tenant explicite
    # (mode repli sous postgres) et RLS ; tri par prix sur le petit resultat.
    assert "JOIN blueseatra.supplier_offers o ON o.id = sel.id" in sql_text
    assert "(o.tenant_id = :tenant_id OR o.tenant_id = :commun)" in sql_text
    assert "ORDER BY o.price_ht ASC NULLS LAST, o.id" in sql_text
    assert params["tenant_id"] == TENANT
    # Resultat marque fournisseur, dans l'ordre prix croissant.
    assert len(articles) == 1 and articles[0]["source"] == "fournisseur"


def test_recherche_n_echoue_jamais_sur_une_erreur(monkeypatch):
    async def boom():
        raise RuntimeError("base indisponible")

    monkeypatch.setattr(catalogue_chiffrage, "get_current_tenant", lambda: TENANT)
    monkeypatch.setattr(catalogue_chiffrage, "_etats_tenant", boom)
    assert asyncio.run(catalogue_chiffrage.rechercher("disjoncteur")) == []


# --- Candidats fournisseurs pour le rapprochement d'un devis ----------------

def test_libelles_extraits_depuis_lignes():
    e = {"line_items": [{"label": "Trou d'évacuation"},
                        {"description": "Barre anti-rongeurs"},
                        {"label": "trou d'évacuation"},   # doublon insensible a la casse
                        {"label": "  "}]}
    assert catalogue_chiffrage._libelles_extraits(e) == ["Trou d'évacuation", "Barre anti-rongeurs"]


def test_libelles_extraits_repli_sur_description():
    assert catalogue_chiffrage._libelles_extraits({"description": "Réfection complète"}) == ["Réfection complète"]
    assert catalogue_chiffrage._libelles_extraits({}) == []
    assert catalogue_chiffrage._libelles_extraits({"line_items": [{"label": None}]}) == []


def test_libelles_extraits_bornes():
    e = {"line_items": [{"label": f"article {i}"} for i in range(40)]}
    assert len(catalogue_chiffrage._libelles_extraits(e)) == 15


def test_candidats_rapprochement_agrege_et_deduplique(monkeypatch):
    contexts = []

    class _CtxT:
        def __init__(self, tenant):
            self.tenant = tenant

        async def __aenter__(self):
            contexts.append(self.tenant)
            return None

        async def __aexit__(self, *a):
            return False

    recherches = []

    async def faux_rechercher(q, limite):
        recherches.append((q, limite))
        # deux libelles, un article commun (id 'frn:x' dedouble)
        if "évacuation" in q:
            return [{"id": "frn:x", "item_label": "Grille", "source": "fournisseur"},
                    {"id": "frn:y", "item_label": "Evacuation", "source": "fournisseur"}]
        return [{"id": "frn:x", "item_label": "Grille", "source": "fournisseur"}]

    monkeypatch.setattr(catalogue_chiffrage, "tenant_context", _CtxT)
    monkeypatch.setattr(catalogue_chiffrage, "rechercher", faux_rechercher)
    resultat = asyncio.run(catalogue_chiffrage.candidats_rapprochement(
        TENANT, {"line_items": [{"label": "Trou d'évacuation"}, {"label": "Grille"}]}))
    # Le contexte tenant est bien pose avec le tenant EXPLICITE passe par le
    # serveur (generation en tache de fond, hors requete HTTP).
    assert contexts == [TENANT]
    assert [r[1] for r in recherches] == [8, 8]
    assert [a["id"] for a in resultat] == ["frn:x", "frn:y"]


def test_candidats_rapprochement_sans_libelle_rend_vide(monkeypatch):
    async def boom(q, limite):
        raise AssertionError("ne doit pas chercher")

    monkeypatch.setattr(catalogue_chiffrage, "rechercher", boom)
    assert asyncio.run(catalogue_chiffrage.candidats_rapprochement(TENANT, {})) == []


def test_candidats_rapprochement_n_echoue_jamais(monkeypatch):
    class _CtxKO:
        def __init__(self, tenant):
            pass

        async def __aenter__(self):
            raise RuntimeError("contexte indisponible")

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(catalogue_chiffrage, "tenant_context", _CtxKO)
    resultat = asyncio.run(catalogue_chiffrage.candidats_rapprochement(
        TENANT, {"line_items": [{"label": "Grille"}]}))
    assert resultat == []  # repli silencieux : la generation ne doit pas echouer


# --- Sources actives : generation refusee seulement si AUCUNE -----------------

def test_a_sources_actives_vrai_si_active_et_visible(monkeypatch):
    class _CtxT:
        def __init__(self, tenant):
            pass

        async def __aenter__(self):
            return None

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(catalogue_chiffrage, "tenant_context", _CtxT)

    async def etats(t):
        return {CLE_VERSION: True, "cle_morte": True}

    async def fournisseurs():
        return {"fournisseurs": [{"cle": CLE_VERSION, "fournisseur": "Rexel"}]}

    monkeypatch.setattr(catalogue_chiffrage, "_etats_tenant", etats)
    monkeypatch.setattr(catalogue_navigation, "fournisseurs", fournisseurs)
    assert asyncio.run(catalogue_chiffrage.a_sources_actives(TENANT)) is True


def test_a_sources_actives_faux_si_aucune_active_ou_plus_visible(monkeypatch):
    class _CtxT:
        def __init__(self, tenant):
            pass

        async def __aenter__(self):
            return None

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(catalogue_chiffrage, "tenant_context", _CtxT)

    async def toutes_deactivees(t):
        return {CLE_VERSION: False}

    async def fournisseurs():
        return {"fournisseurs": [{"cle": CLE_VERSION}]}

    monkeypatch.setattr(catalogue_chiffrage, "_etats_tenant", toutes_deactivees)
    monkeypatch.setattr(catalogue_navigation, "fournisseurs", fournisseurs)
    assert asyncio.run(catalogue_chiffrage.a_sources_actives(TENANT)) is False

    async def activee(t):
        return {CLE_VERSION: True}

    async def aucune_visible():
        return {"fournisseurs": []}

    monkeypatch.setattr(catalogue_chiffrage, "_etats_tenant", activee)
    monkeypatch.setattr(catalogue_navigation, "fournisseurs", aucune_visible)
    assert asyncio.run(catalogue_chiffrage.a_sources_actives(TENANT)) is False


def test_a_sources_actives_nechoue_jamais(monkeypatch):
    class _CtxKO:
        def __init__(self, tenant):
            pass

        async def __aenter__(self):
            raise RuntimeError("indisponible")

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(catalogue_chiffrage, "tenant_context", _CtxKO)
    assert asyncio.run(catalogue_chiffrage.a_sources_actives(TENANT)) is False


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


# --- Recherche parallele par groupes de sources (02/10/2026) -----------------

def _ligne(i, prix):
    return {"id": f"o{i}", "fournisseur": "F", "designation": f"Article {i}", "marque": None,
            "reference_fournisseur": None, "reference_fabricant": None, "code_ean": None,
            "prix_net_ht": prix, "prix_public_ht": None, "unite_vente": None,
            "conditionnement": None, "famille": None, "sous_famille": None,
            "url_produit": None, "date_prix": None, "catalogue_commun": True}


def test_repartir_sources_equilibre_et_conserve_tout():
    cles = [f"v{i}" for i in range(9)]
    visibles = {c: {"references": 50000} for c in cles}
    visibles["v7"]["references"] = visibles["v8"]["references"] = 100   # petites sources
    groupes = catalogue_chiffrage.repartir_sources(cles, visibles)
    assert len(groupes) == 3
    assert sorted(c for g in groupes for c in g) == sorted(cles)        # rien perdu, rien double
    lourdes = [sum(1 for c in g if visibles[c]["references"] > 2000) for g in groupes]
    assert max(lourdes) - min(lourdes) <= 1                              # 7 lourdes : 3/2/2


def test_repartir_sources_peu_de_sources_un_seul_groupe():
    assert catalogue_chiffrage.repartir_sources(["a", "b", "c"], {}) == [["a", "b", "c"]]
    assert len(catalogue_chiffrage.repartir_sources([f"v{i}" for i in range(4)], {})) == 2


def test_recherche_parallele_fusionne_trie_et_limite(monkeypatch):
    cles = [f"{i:08d}-0000-4000-8000-000000000000" for i in range(9)]
    # Chaque session renvoie ses lignes ; prix volontairement entrelaces.
    sessions = []

    def nouvelle_session():
        k = len(sessions)
        s = FakeSession(results=[FakeResult(mappings=[_ligne(10 * k + j, float(k + 3 * j) if j < 2 else None)
                                                      for j in range(3)])])
        sessions.append(s)
        return _Ctx(s)

    _patch(monkeypatch, FakeSession(),
           fournisseurs=[{"cle": c, "fournisseur": "F", "references": 50000, "catalogue_commun": True}
                         for c in cles],
           etats={c: True for c in cles})
    monkeypatch.setattr(catalogue_chiffrage, "tenant_session", nouvelle_session)
    articles = asyncio.run(catalogue_chiffrage.rechercher("disjoncteur", 5))
    assert len(sessions) == 3                                   # 3 groupes, 3 sessions
    toutes = [(sql, p) for s in sessions for sql, p in s.executed]
    assert sum(str(sql).count("blueseatra.offres_candidates(") for sql, _ in toutes) == 9
    for _, p in toutes:                                         # chaque groupe : son propre top
        assert p["limite"] == 5 and p["tenant_id"] == TENANT
    prix = [a["unit_price_ht"] for a in articles]
    assert len(articles) == 5
    assert prix == sorted(prix)                                 # tri global par prix
    assert prix == [0.0, 1.0, 2.0, 3.0, 4.0]                    # les 5 moins chers de l'ensemble


def test_recherche_parallele_prix_absents_en_dernier(monkeypatch):
    cles = [f"{i:08d}-0000-4000-8000-000000000000" for i in range(6)]
    sessions = []

    def nouvelle_session():
        k = len(sessions)
        s = FakeSession(results=[FakeResult(mappings=[_ligne(k, None if k % 2 else float(k))])])
        sessions.append(s)
        return _Ctx(s)

    _patch(monkeypatch, FakeSession(),
           fournisseurs=[{"cle": c, "fournisseur": "F", "references": 50000, "catalogue_commun": True}
                         for c in cles],
           etats={c: True for c in cles})
    monkeypatch.setattr(catalogue_chiffrage, "tenant_session", nouvelle_session)
    articles = asyncio.run(catalogue_chiffrage.rechercher("prise", 10))
    prix = [a["unit_price_ht"] for a in articles]
    connus = [p for p in prix if p is not None]
    assert prix == connus + [None] * (len(prix) - len(connus))   # prix absents en dernier
    assert len(sessions) == 2 and len(articles) == 2              # 6 sources -> 2 groupes
    assert connus == [0.0]


def test_recherche_parallele_erreur_d_un_groupe_rend_liste_vide(monkeypatch):
    cles = [f"{i:08d}-0000-4000-8000-000000000000" for i in range(9)]
    appels = []

    class Boom(FakeSession):
        async def execute(self, sql, params=None):
            raise RuntimeError("base indisponible")

    def nouvelle_session():
        appels.append(1)
        return _Ctx(Boom() if len(appels) == 2 else FakeSession())

    _patch(monkeypatch, FakeSession(),
           fournisseurs=[{"cle": c, "fournisseur": "F", "references": 50000, "catalogue_commun": True}
                         for c in cles],
           etats={c: True for c in cles})
    monkeypatch.setattr(catalogue_chiffrage, "tenant_session", nouvelle_session)
    assert asyncio.run(catalogue_chiffrage.rechercher("prise", 10)) == []
