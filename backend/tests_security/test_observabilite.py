"""Ticket #93 : journaux sans données personnelles, identifiant de requête, gabarits de mesures."""
import json, logging, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
pytest.importorskip("fastapi")
import observabilite as o  # noqa: E402


def test_emails_masques_et_pseudonyme_stable():
    t = o.masquer("Devis envoyé à Paul.Martin@foncia.fr et copie à x@y.com")
    assert "@" not in t.replace("<email:", "")
    assert o.pseudo("a@b.fr") == o.pseudo("a@b.fr") != o.pseudo("c@d.fr")


def test_format_json_contient_request_id_sans_email():
    rec = logging.LogRecord("blueseatra", logging.WARNING, __file__, 1, "échec pour %s", ("jean@exemple.fr",), None)
    jeton = o.request_id_var.set("abc123def456")
    try:
        doc = json.loads(o.FormatJSON().format(rec))
    finally:
        o.request_id_var.reset(jeton)
    assert doc["request_id"] == "abc123def456" and doc["niveau"] == "WARNING"
    assert "jean@exemple.fr" not in json.dumps(doc)


class _Req:
    def __init__(self, chemin):
        self.scope = {}
        self.url = type("U", (), {"path": chemin})()


def test_gabarit_remplace_les_identifiants():
    assert o._gabarit(_Req("/api/quotes/619199f2-ff95-45be-99d9-ef957a47d7ba/versions")) == "/api/quotes/{id}/versions"
    assert o._gabarit(_Req("/api/clients")) == "/api/clients"


def test_centiles_et_slo():
    o._mesures.clear()
    for ms in range(1, 101):
        o._mesures["/api/x"].append((0, 200, float(ms)))
    o._mesures["/api/x"].append((0, 503, 5.0))
    m = o.instantane_mesures()
    assert m["global"]["erreurs_5xx"] == 1 and m["routes"]["/api/x"]["p95_ms"] >= 94
    assert m["respect_slo"]["taux_5xx"] is True
    o._mesures.clear()


def test_export_rgpd_exclut_les_secrets():
    assert "ai_key" in o.TABLES_EXPORT["settings_integrations"]
    assert "file_b64" in o.TABLES_EXPORT["requests"]
    assert "users" not in o.TABLES_EXPORT   # jamais les empreintes de mots de passe


def test_filtre_garde_les_arguments_positionnels_d_uvicorn():
    rec = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d',
                            ("127.0.0.1:1", "GET", "/api/x?mail=a@b.fr", "1.1", 200), None)
    assert o.FiltreMasquage().filter(rec)
    assert len(rec.args) == 5 and rec.args[4] == 200 and "a@b.fr" not in rec.getMessage()
