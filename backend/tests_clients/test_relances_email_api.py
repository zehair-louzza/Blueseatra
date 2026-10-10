"""Relances par e-mail de bout en bout : API FastAPI réelle, base PostgreSQL JETABLE
sous RLS (rôle membre de blueseatra_app), serveur SMTP remplacé par un faux.

À lancer seul (le serveur doit être importé avec la base de test) :
    TEST_PG_URL='postgresql://postgres@localhost:55432/qc' \\
    TEST_PG_URL_APP='postgresql://qt_app@localhost:55432/qc' \\
    pytest backend/tests_clients/test_relances_email_api.py -q
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest

URL, URL_APP = os.environ.get("TEST_PG_URL"), os.environ.get("TEST_PG_URL_APP")
pytestmark = pytest.mark.skipif(not (URL and URL_APP), reason="TEST_PG_URL(_APP) non définis")

T1, T2 = str(uuid.uuid4()), str(uuid.uuid4())
BOITE = {"hote": "smtp.zoho.eu", "port": 465, "identifiant": "devis@anelec-fictif.fr",
         "expediteur_email": "devis@anelec-fictif.fr", "expediteur_nom": "ANELEC",
         "signature": "Jean Martin\nANELEC", "copie_cachee": True, "actif": True}


@pytest.fixture(scope="module")
def ctx():
    assert "supabase" not in URL and "supabase" not in URL_APP, "base jetable uniquement"
    os.environ.update(DATABASE_URL=URL, DATABASE_URL_APP=URL_APP, JWT_SECRET="x" * 64, BLUESEATRA_ENVOI_AUTO="0")
    from cryptography.fernet import Fernet
    os.environ.setdefault("APP_ENCRYPTION_KEY", Fernet.generate_key().decode())
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    for m in ("database", "pg_adapter", "quotas", "clients_module", "relances_email", "envoi_relances", "server"):
        sys.modules.pop(m, None)
    import server
    import envoi_relances
    import relances_email
    from database import set_current_tenant
    from fastapi.testclient import TestClient

    etat = {"tenant": T1, "role": "owner"}
    envois = {"messages": [], "erreur": None}

    async def faux_utilisateur():
        set_current_tenant(etat["tenant"])
        return server.CurrentUser(user_id="u1", email="chef@anelec-fictif.fr", name="Chef",
                                  tenant_id=etat["tenant"], role=etat["role"])

    def faux_envoi(m, msg, **k):
        if envois["erreur"]:
            raise envois["erreur"]
        envois["messages"].append((m, msg))
        return str(msg["Message-ID"])

    envoi_relances.verifier_hote = lambda hote, port, **k: hote
    envoi_relances.envoyer = faux_envoi
    server.app.dependency_overrides[server.get_current] = faux_utilisateur
    with TestClient(server.app) as c:
        yield c, etat, envois, relances_email, envoi_relances
    server.app.dependency_overrides.clear()


def _sql(sql, params=()):
    import psycopg2
    c = psycopg2.connect(URL, client_encoding="utf8")
    c.autocommit = True
    with c.cursor() as cur:
        cur.execute(sql, params)
        r = cur.fetchall() if cur.description else None
    c.close()
    return r


@pytest.fixture(scope="module")
def relances(ctx):
    """Un devis de 2 400 € HT envoyé à un contact joignable par e-mail : relances prévues par e-mail."""
    c, *_ = ctx
    for t, nom in ((T1, "Entreprise fictive 1"), (T2, "Entreprise fictive 2")):
        _sql("INSERT INTO blueseatra.tenants (id, name) VALUES (%s, %s) ON CONFLICT DO NOTHING", (t, nom))
    cid = c.post("/api/clients", json={"raison_sociale": "Syndic Fictif", "type": "syndic",
                                       "email": "accueil@syndic-fictif.fr"}).json()["id"]
    kid = c.post(f"/api/clients/{cid}/contacts", json={"nom": "Durand", "prenom": "Alice",
                                                       "email": "alice.durand@syndic-fictif.fr"}).json()["id"]
    qid = str(uuid.uuid4())
    _sql("""INSERT INTO blueseatra.quotes (id, tenant_id, number, status, total_ht, created_at, client, lines,
                                           client_id, contact_id)
            VALUES (%s,%s,'D-2026-090','sent',2400,'2026-10-01T10:00:00Z','Syndic Fictif','[]'::jsonb,%s,%s)""",
         (qid, T1, cid, kid))
    # Relances telles que planifier_relances_devis les écrit (calcul testé dans test_relances_regles.py).
    ids = [str(uuid.uuid4()) for _ in range(4)]
    for rang, rid in enumerate(ids, 1):
        _sql("""INSERT INTO blueseatra.relances (id, tenant_id, devis_id, client_id, contact_id, rang, echeance, canal,
                                                 raison, brouillon)
                VALUES (%s,%s,%s,%s,%s,%s, now() + make_interval(days => %s), 'email', %s, %s)""",
             (rid, T1, qid, cid, kid, rang, 3 * rang, f"Relance {rang} sur 3 du devis D-2026-090",
              "Bonjour,\n\nJe me permets de revenir vers vous au sujet de notre devis D-2026-090.\n\nCordialement,"))
    return {"client": cid, "contact": kid, "devis": qid, "ids": ids}


def test_sans_messagerie_l_envoi_est_refuse(ctx, relances):
    c, _, envois, *_ = ctx
    assert c.get("/api/relances").json()["messagerie_active"] is False
    r = c.post(f"/api/relances/{relances['ids'][0]}/envoyer", json={})
    assert r.status_code == 400 and "messagerie" in r.json()["detail"]
    assert envois["messages"] == []


def test_messagerie_mot_de_passe_chiffre_jamais_renvoye(ctx):
    c, etat, *_ = ctx
    assert c.put("/api/messagerie", json=BOITE).status_code == 400            # mot de passe obligatoire
    v = c.put("/api/messagerie", json={**BOITE, "mot_de_passe": "mdp-fictif-123"}).json()
    assert v["configuree"] and v["mot_de_passe_defini"] and "mot_de_passe" not in v and v["verifie_le"] is None
    assert _sql("SELECT mot_de_passe FROM blueseatra.messagerie_smtp WHERE tenant_id=%s", (T1,))[0][0].startswith("enc::")
    assert "mdp-fictif-123" not in str(c.get("/api/messagerie").json())
    assert c.put("/api/messagerie", json={**BOITE, "port": 25, "mot_de_passe": "x"}).status_code == 400
    etat["role"] = "operator"
    try:
        assert c.put("/api/messagerie", json={**BOITE, "mot_de_passe": "x"}).status_code == 403
        assert c.get("/api/messagerie").status_code == 403
    finally:
        etat["role"] = "owner"


def test_envoi_auto_exige_un_test_reussi(ctx):
    c, _, envois, *_ = ctx
    g = c.get("/api/regles-relance").json()
    regles = {k: g[k] for k in ("actif", "delais_jours_ouvres", "delais_urgent", "max_relances", "validite_devis_jours",
                                "rappel_avant_expiration_j", "seuil_appel_ht", "heure_relance")}
    assert c.put("/api/regles-relance", json={**regles, "envoi_auto": True}).status_code == 400
    v = c.post("/api/messagerie/test").json()
    assert v["verifie_le"] and v["derniere_erreur"] is None
    m, msg = envois["messages"].pop()
    assert msg["To"] == "devis@anelec-fictif.fr" and m.mot_de_passe == "mdp-fictif-123"
    # Changer le mot de passe annule la vérification.
    assert c.put("/api/messagerie", json={**BOITE, "mot_de_passe": "autre"}).json()["verifie_le"] is None
    c.put("/api/messagerie", json={**BOITE, "mot_de_passe": "mdp-fictif-123"})
    assert c.post("/api/messagerie/test").json()["verifie_le"]
    envois["messages"].clear()
    # Modifier seulement la signature garde la vérification.
    assert c.put("/api/messagerie", json={**BOITE, "signature": "L'équipe ANELEC"}).json()["verifie_le"]
    c.put("/api/messagerie", json=BOITE)


def test_texte_modifiable_puis_envoi_par_clic(ctx, relances):
    c, _, envois, *_ = ctx
    rid = relances["ids"][0]
    x = c.patch(f"/api/relances/{rid}/texte", json={"objet": "Votre devis D-2026-090",
                                                    "brouillon": "Bonjour Madame Durand,\n\nTexte relu.\n\nCordialement,"}).json()
    assert x["objet"] == "Votre devis D-2026-090"
    r = c.post(f"/api/relances/{rid}/envoyer", json={"brouillon": "Bonjour Madame Durand,\n\nTexte final.\n\nCordialement,"})
    assert r.status_code == 200, r.text
    assert r.json()["envoye_a"] == "alice.durand@syndic-fictif.fr"
    m, msg = envois["messages"].pop()
    assert msg["To"] == "alice.durand@syndic-fictif.fr" and msg["Subject"] == "Votre devis D-2026-090"
    assert msg["From"] == "ANELEC <devis@anelec-fictif.fr>" and msg["Bcc"] == "devis@anelec-fictif.fr"
    assert "Texte final." in msg.get_content() and msg.get_content().rstrip().endswith("Jean Martin\nANELEC")
    st, envoi, par, dest = _sql("SELECT statut, envoi_statut, envoye_par, envoi_destinataire FROM blueseatra.relances "
                                "WHERE id=%s", (rid,))[0]
    assert (st, envoi, par, dest) == ("faite", "envoye", "chef@anelec-fictif.fr", "alice.durand@syndic-fictif.fr")
    journal = [e["resume"] for e in c.get(f"/api/clients/{relances['client']}/echanges").json()]
    assert any("envoyée par e-mail à alice.durand@syndic-fictif.fr" in j for j in journal)
    # Jamais deux fois ; texte figé après l'envoi.
    assert c.post(f"/api/relances/{rid}/envoyer", json={}).status_code == 409
    assert c.patch(f"/api/relances/{rid}/texte", json={"objet": "x"}).status_code == 409
    assert envois["messages"] == []


def test_echec_trace_puis_nouvel_essai(ctx, relances):
    c, _, envois, _, er = ctx
    rid = relances["ids"][1]
    envois["erreur"] = er.ErreurBoite("Identifiant ou mot de passe SMTP refusé par le serveur.")
    r = c.post(f"/api/relances/{rid}/envoyer", json={})
    assert r.status_code == 400 and "mot de passe" in r.json()["detail"]
    assert _sql("SELECT statut, envoi_statut, envoi_erreur FROM blueseatra.relances WHERE id=%s", (rid,))[0] == \
        ("prevue", "echec", "Identifiant ou mot de passe SMTP refusé par le serveur.")
    envois["erreur"] = None
    assert c.post(f"/api/relances/{rid}/envoyer", json={}).status_code == 200
    assert len(envois["messages"]) == 1
    envois["messages"].clear()


def test_contact_oppose_aucun_e_mail(ctx, relances):
    c, _, envois, *_ = ctx
    rid = relances["ids"][2]
    _sql("UPDATE blueseatra.contacts SET accepte_relances = false WHERE id=%s", (relances["contact"],))
    try:
        r = c.post(f"/api/relances/{rid}/envoyer", json={})
        assert r.status_code == 400 and "opposé" in r.json()["detail"]
        assert envois["messages"] == []
    finally:
        _sql("UPDATE blueseatra.contacts SET accepte_relances = true WHERE id=%s", (relances["contact"],))
        _sql("UPDATE blueseatra.relances SET envoi_statut = NULL, envoi_erreur = NULL WHERE id=%s", (rid,))


def test_envoi_automatique_a_l_echeance_seulement_apres_activation(ctx, relances):
    c, _, envois, relances_email, _ = ctx
    g = c.get("/api/regles-relance").json()
    regles = {k: g[k] for k in ("actif", "delais_jours_ouvres", "delais_urgent", "max_relances", "validite_devis_jours",
                                "rappel_avant_expiration_j", "seuil_appel_ht", "heure_relance")}
    g2 = c.put("/api/regles-relance", json={**regles, "envoi_auto": True}).json()
    assert g2["envoi_auto"] is True and g2["envoi_auto_depuis"]
    restantes = [i for i in relances["ids"][2:]]
    a_temps, en_retard = restantes[0], (restantes[1] if len(restantes) > 1 else None)
    _sql("UPDATE blueseatra.regles_relance SET envoi_auto_depuis = now() - interval '10 minutes' WHERE tenant_id=%s", (T1,))
    _sql("UPDATE blueseatra.relances SET echeance = now() - interval '1 minute' WHERE id=%s", (a_temps,))
    if en_retard:
        _sql("UPDATE blueseatra.relances SET echeance = now() - interval '2 days' WHERE id=%s", (en_retard,))
    # Une autre entreprise sans messagerie, relance échue : jamais touchée.
    autre = str(uuid.uuid4())
    _sql("""INSERT INTO blueseatra.regles_relance (tenant_id, envoi_auto, envoi_auto_depuis)
            VALUES (%s, true, now() - interval '1 day')""", (T2,))
    _sql("""INSERT INTO blueseatra.relances (id, tenant_id, devis_id, rang, echeance, canal, raison, brouillon)
            VALUES (%s, %s, %s, 1, now() - interval '1 minute', 'email', 'test', 'Bonjour')""",
         (autre, T2, str(uuid.uuid4())))
    # Réglages enregistrés sans changement : la date d'activation ne bouge pas.
    depuis = _sql("SELECT envoi_auto_depuis FROM blueseatra.regles_relance WHERE tenant_id=%s", (T1,))[0][0]
    c.put("/api/regles-relance", json={**regles, "envoi_auto": True})
    assert _sql("SELECT envoi_auto_depuis FROM blueseatra.regles_relance WHERE tenant_id=%s", (T1,))[0][0] == depuis

    assert c.portal.call(relances_email.envoyer_echeances) == 1
    (m, msg), = envois["messages"]
    assert msg["To"] == "alice.durand@syndic-fictif.fr"
    assert _sql("SELECT statut, envoye_par FROM blueseatra.relances WHERE id=%s", (a_temps,))[0] == \
        ("faite", relances_email.AUTEUR_AUTO)
    if en_retard:
        assert _sql("SELECT statut, envoi_statut FROM blueseatra.relances WHERE id=%s", (en_retard,))[0] == ("prevue", None)
    assert _sql("SELECT statut, envoi_statut FROM blueseatra.relances WHERE id=%s", (autre,))[0] == ("prevue", None)
    # Second balayage : rien de plus.
    assert c.portal.call(relances_email.envoyer_echeances) == 0
    envois["messages"].clear()


def test_boite_desactivee_coupe_l_envoi_auto(ctx):
    c, etat, *_ = ctx
    c.put("/api/messagerie", json={**BOITE, "actif": False})
    g = c.get("/api/regles-relance").json()
    assert g["envoi_auto"] is False and g["messagerie_active"] is False
    etat["tenant"] = T2
    try:
        assert c.get("/api/messagerie").json()["configuree"] is False
    finally:
        etat["tenant"] = T1
