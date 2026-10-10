"""Module Clients de bout en bout : API FastAPI réelle, database.py réel,
rôle membre de blueseatra_app, base PostgreSQL JETABLE.

À lancer seul (le serveur doit être importé avec la base de test) :
    TEST_PG_URL='postgresql://postgres@localhost:55432/qc' \
    TEST_PG_URL_APP='postgresql://qt_app@localhost:55432/qc' \
    pytest backend/tests_clients/test_module_clients_api.py -q
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

URL, URL_APP = os.environ.get("TEST_PG_URL"), os.environ.get("TEST_PG_URL_APP")
pytestmark = pytest.mark.skipif(not (URL and URL_APP), reason="TEST_PG_URL(_APP) non définis")

T1, T2 = str(uuid.uuid4()), str(uuid.uuid4())


@pytest.fixture(scope="module")
def ctx():
    assert "supabase" not in URL and "supabase" not in URL_APP, "base jetable uniquement"
    os.environ.update(DATABASE_URL=URL, DATABASE_URL_APP=URL_APP, JWT_SECRET="x" * 64)
    from cryptography.fernet import Fernet
    os.environ.setdefault("APP_ENCRYPTION_KEY", Fernet.generate_key().decode())
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    for m in ("database", "pg_adapter", "quotas", "clients_module", "server"):
        sys.modules.pop(m, None)
    import server
    from database import set_current_tenant
    from fastapi.testclient import TestClient

    etat = {"tenant": T1, "role": "owner"}

    async def faux_utilisateur():
        set_current_tenant(etat["tenant"])
        return server.CurrentUser(user_id="u1", email="chef@anelec.fr", name="Chef",
                                  tenant_id=etat["tenant"], role=etat["role"])

    server.app.dependency_overrides[server.get_current] = faux_utilisateur
    with TestClient(server.app) as c:
        yield c, etat, server
    server.app.dependency_overrides.clear()


def _ligne_chiffree(total_ht):
    """Une ligne complète, sinon le contrôle TCE v4 refuse l'envoi (409)."""
    return json.dumps([{"line_type": "generic", "description": "Prestation", "qty": 1, "unit": "u",
                        "unit_price_ht": total_ht, "line_ht": total_ht, "vat_rate": 20}])


def _valider(c, qid):
    """Parcours réel : revue (empreinte lue sur le devis) puis validation."""
    empreinte = c.get(f"/api/quotes/{qid}").json()["review_digest"]
    r = c.post(f"/api/quotes/{qid}/validate", json={"expected_digest": empreinte, "review_tce": True})
    assert r.status_code == 200, r.text


def _sql(sql, params=()):
    import psycopg2
    c = psycopg2.connect(URL.replace("localhost", "localhost"), client_encoding="utf8")
    c.autocommit = True
    with c.cursor() as cur:
        cur.execute(sql, params)
        r = cur.fetchall() if cur.description else None
    c.close()
    return r


def test_fiches_clients_recherche_doublon_archivage(ctx):
    c, etat, _ = ctx
    r = c.post("/api/clients", json={"raison_sociale": "Foncia Versailles", "type": "syndic",
                                     "siret": "123 456 789 00011", "email": "gestion@foncia-versailles.fr",
                                     "adresse": {"ville": "Versailles"}})
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    assert r.json()["siret"] == "12345678900011"
    assert c.post("/api/clients", json={"raison_sociale": "Doublon", "siret": "12345678900011"}).status_code == 409
    assert c.post("/api/clients", json={"raison_sociale": "X", "siret": "12"}).status_code == 400
    assert c.get("/api/clients", params={"q": "fonciA versaillés"}).json()["total"] == 1
    assert c.get("/api/clients", params={"q": "versailles"}).json()["clients"][0]["ville"] == "Versailles"
    etat["role"] = "viewer"
    assert c.post("/api/clients", json={"raison_sociale": "Interdit"}).status_code == 403
    assert c.post(f"/api/clients/{cid}/archiver").status_code == 403
    etat["role"] = "owner"
    assert c.post(f"/api/clients/{cid}/archiver").json()["ok"]
    assert c.get("/api/clients").json()["total"] == 0
    assert c.get("/api/clients", params={"archives": True}).json()["total"] == 1
    c.post(f"/api/clients/{cid}/restaurer")
    assert c.get("/api/clients").json()["total"] == 1
    routes_delete = [r.path for r in ctx[2].app.routes if "DELETE" in getattr(r, "methods", set())
                     and any(k in r.path for k in ("client", "contact", "chantier", "relance", "echange"))]
    assert routes_delete == []


def test_contacts_chantiers_anonymisation(ctx):
    c, etat, _ = ctx
    cid = c.get("/api/clients", params={"q": "foncia"}).json()["clients"][0]["id"]
    a = c.post(f"/api/clients/{cid}/contacts", json={"prenom": "Paul", "nom": "Martin", "email": "p.martin@foncia.fr",
                                                     "principal": True}).json()
    b = c.post(f"/api/clients/{cid}/contacts", json={"prenom": "Léa", "nom": "Durand", "principal": True}).json()
    liste = c.get(f"/api/clients/{cid}/contacts").json()
    assert [x["nom"] for x in liste if x["principal"]] == ["Durand"]
    assert c.post(f"/api/contacts/{a['id']}/anonymiser").json()["ok"]
    anon = _sql("SELECT nom, email, accepte_relances FROM blueseatra.contacts WHERE id=%s", (a["id"],))[0]
    assert anon == ("Contact anonymisé", None, False)
    assert c.patch(f"/api/contacts/{a['id']}", json={"nom": "Retour"}).status_code == 400
    ch = c.post(f"/api/clients/{cid}/chantiers", json={"nom": "Résidence Les Tilleuls", "code_site": "RT-12"}).json()
    assert c.get(f"/api/clients/{cid}/chantiers").json()[0]["id"] == ch["id"]
    assert b["id"]


def test_suggestions_depuis_une_demande(ctx):
    c, etat, server = ctx
    import asyncio
    from database import tenant_context
    import clients_module as cm
    rid = str(uuid.uuid4())
    texte = ("Ordre de mission. Devis à adresser exclusivement à FONCIA VERSAILLES (gestion@foncia-versailles.fr). "
             "Client : Picard Surgelés, magasin de Rueil.")
    _sql("INSERT INTO blueseatra.requests (id, tenant_id, title, raw_text, status) VALUES (%s,%s,'OM',%s,'done')",
         (rid, T1, texte))
    ex = {"donneur_d_ordre": "FONCIA VERSAILLES", "donneur_email": "gestion@foncia-versailles.fr",
          "client_final": "Picard Surgelés", "client_email": "rueil@picard.fr"}

    async def go():
        async with tenant_context(T1):
            return await cm.suggerer_depuis_extraction(rid, ex, texte), await cm.suggerer_depuis_extraction(rid, ex, texte)
    n1, n2 = c.portal.call(go)                                   # même boucle que l'API
    assert (n1, n2) == (2, 0)                                   # retraitement : pas de doublon
    r = c.get("/api/suggestions-clients", params={"demande_id": rid}).json()
    assert len(r["rattachements_auto"]) == 1 and r["rattachements_auto"][0]["force"] == "exacte"
    assert "exclusivement à FONCIA VERSAILLES" in r["rattachements_auto"][0]["preuve"]
    lie = _sql("SELECT client_id FROM blueseatra.requests WHERE id=%s", (rid,))[0][0]
    assert lie is not None
    nouveau = [s for s in r["a_valider"] if s["type"] == "nouveau_client"][0]
    assert nouveau["role"] == "client_final" and "Picard" in nouveau["preuve"]
    acc = c.post(f"/api/suggestions-clients/{nouveau['id']}/accepter").json()
    assert _sql("SELECT client_final_id FROM blueseatra.requests WHERE id=%s", (rid,))[0][0] == acc["client_id"]
    assert _sql("SELECT type, source FROM blueseatra.clients WHERE id=%s", (acc["client_id"],))[0] == ("enseigne", "suggestion_ia")
    auto = r["rattachements_auto"][0]
    assert c.post(f"/api/suggestions-clients/{auto['id']}/annuler-rattachement").json()["ok"]
    assert _sql("SELECT client_id FROM blueseatra.requests WHERE id=%s", (rid,))[0][0] is None


def test_relances_du_devis_envoye_a_l_issue(ctx):
    c, etat, server = ctx
    cid = c.get("/api/clients", params={"q": "foncia"}).json()["clients"][0]["id"]
    qid = str(uuid.uuid4())
    _sql("""INSERT INTO blueseatra.quotes (id, tenant_id, number, status, total_ht, total_vat, total_ttc,
                                           lines, created_at, client)
            VALUES (%s,%s,'D-2026-041','draft',2400,480,2880,%s::jsonb,'2026-09-24T10:00:00Z','Foncia')""",
         (qid, T1, _ligne_chiffree(2400)))
    assert c.post(f"/api/quotes/{qid}/client", json={"client_id": cid}).json()["client_nom"] == "Foncia Versailles"
    _valider(c, qid)
    assert c.post(f"/api/quotes/{qid}/issue", json={"issue": "accepte"}).status_code == 400   # pas encore envoyé
    assert c.post(f"/api/quotes/{qid}/send").status_code == 200
    suivi = c.get(f"/api/quotes/{qid}/suivi").json()
    assert suivi["issue"] == "en_attente" and suivi["valable_jusqu_au"]
    prevues = [x for x in suivi["relances"] if x["statut"] == "prevue"]
    assert [x["rang"] for x in prevues][:2] == [1, 2] and prevues[0]["canal"] == "email"
    assert "D-2026-041" in prevues[0]["raison"]
    # renvoi : aucune relance en double
    c.post(f"/api/quotes/{qid}/send")
    assert len([x for x in c.get(f"/api/quotes/{qid}/suivi").json()["relances"] if x["statut"] == "prevue"]) == len(prevues)
    # a_rappeler : nouvelle tâche
    r1 = prevues[0]["id"]
    assert c.post(f"/api/relances/{r1}/faite", json={"resultat": "a_rappeler", "note": "Absent"}).json()["ok"]
    apres = c.get(f"/api/quotes/{qid}/suivi").json()["relances"]
    assert any("Rappel demandé" in x["raison"] for x in apres)
    assert c.post(f"/api/relances/{r1}/faite", json={"resultat": "sans_reponse"}).status_code == 400
    # reporter
    r2 = [x for x in apres if x["statut"] == "prevue"][0]["id"]
    assert c.post(f"/api/relances/{r2}/reporter", json={"jours_ouvres": 2}).json()["ok"]
    # issue accepté : tout s'arrête, journal alimenté
    assert c.post(f"/api/quotes/{qid}/issue", json={"issue": "accepte"}).json()["issue"] == "accepte"
    fin = c.get(f"/api/quotes/{qid}/suivi").json()["relances"]
    assert not [x for x in fin if x["statut"] in ("prevue", "reportee")]
    assert {x["motif_annulation"] for x in fin if x["statut"] == "annulee"} == {"Devis accepté"}
    types = [e["type"] for e in c.get(f"/api/clients/{cid}/echanges").json()]
    assert "devis_envoye" in types and "devis_accepte" in types and "relance" in types
    k = c.get(f"/api/clients/{cid}/resume").json()
    assert k["signe_ht"] == 2400 and k["taux_transformation"] == 1.0


def test_reouverture_annule_et_regles_desactivees(ctx):
    c, etat, _ = ctx
    qid = str(uuid.uuid4())
    _sql("""INSERT INTO blueseatra.quotes (id, tenant_id, number, status, total_ht, total_vat, total_ttc,
                                           lines, created_at)
            VALUES (%s,%s,'D-2026-050','draft',25000,5000,30000,%s::jsonb,'2026-09-24T10:00:00Z')""",
         (qid, T1, _ligne_chiffree(25000)))
    _valider(c, qid)
    assert c.post(f"/api/quotes/{qid}/send").status_code == 200
    s = c.get(f"/api/quotes/{qid}/suivi").json()["relances"]
    assert s and {x["canal"] for x in s} == {"appel"}          # gros montant, pas de contact
    c.post(f"/api/quotes/{qid}/reopen")
    assert {x["motif_annulation"] for x in c.get(f"/api/quotes/{qid}/suivi").json()["relances"]} == {"Devis remis en brouillon"}
    g = c.get("/api/regles-relance").json()
    assert g["delais_jours_ouvres"] == [3, 7, 14] and g["apercu"]
    g2 = c.put("/api/regles-relance", json={**{k: g[k] for k in ("delais_jours_ouvres", "delais_urgent", "max_relances",
               "validite_devis_jours", "rappel_avant_expiration_j", "seuil_appel_ht", "heure_relance")}, "actif": False}).json()
    assert g2["actif"] is False and g2["apercu"] == []
    etat["role"] = "operator"
    assert c.put("/api/regles-relance", json={"actif": True}).status_code == 403
    etat["role"] = "owner"
    c.put("/api/regles-relance", json={"actif": True})


def test_isolation_entre_entreprises(ctx):
    c, etat, _ = ctx
    cid = c.get("/api/clients", params={"q": "foncia"}).json()["clients"][0]["id"]
    etat["tenant"] = T2
    try:
        assert c.get("/api/clients").json()["total"] == 0
        assert c.get(f"/api/clients/{cid}").status_code == 404
        assert c.get(f"/api/clients/{cid}/contacts").json() == []
        assert c.get("/api/relances").json()["relances"] == []
        assert c.post(f"/api/clients/{cid}/contacts", json={"nom": "Pirate"}).status_code == 404
        assert c.post(f"/api/clients/{cid}/archiver").status_code == 404
    finally:
        etat["tenant"] = T1


def test_import_et_export_csv(ctx):
    c, etat, _ = ctx
    csv_txt = ("Raison sociale;SIRET;E-mail;Ville;Type\n"
               "Nexity Le Chesnay;98765432100017;contact@nexity.fr;Le Chesnay;bailleur\n"
               "Doublon Foncia;12345678900011;;Versailles;syndic\n"
               ";;;;\n").encode("utf-8")
    ap = c.post("/api/clients/import/preview", files={"file": ("c.csv", csv_txt, "text/csv")}).json()
    assert ap["mapping"]["raison_sociale"] == "Raison sociale" and ap["mapping"]["ville"] == "Ville"
    r = c.post("/api/clients/import", files={"file": ("c.csv", csv_txt, "text/csv")}).json()
    assert r["crees"] == 1 and len(r["doublons"]) == 1
    exp = c.get("/api/clients-export.csv")
    assert exp.status_code == 200 and "Nexity Le Chesnay" in exp.text and exp.text.startswith("\ufeff")
