"""Envoi SMTP des relances : message, contrôle du serveur, connexion (sans réseau)."""
import smtplib
import socket
import ssl

import pytest

import envoi_relances as er

PUBLIC = lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("185.230.63.171", 465))]  # noqa: E731
M = er.Messagerie(hote="smtp.zoho.eu", port=465, identifiant="devis@anelec.fr", mot_de_passe="secret-123",
                  expediteur_email="devis@anelec.fr", expediteur_nom="ANELEC", signature="Jean Martin\nANELEC")


def test_message_expediteur_reponse_copie_et_signature():
    msg = er.construire_message(M, "contact@client-fictif.fr", "Devis D-2026-041", "Bonjour,\n\nCordialement,")
    assert msg["From"] == "ANELEC <devis@anelec.fr>"
    assert msg["To"] == "contact@client-fictif.fr" and msg["Reply-To"] == "devis@anelec.fr"
    assert msg["Bcc"] == "devis@anelec.fr"
    assert msg["Message-ID"].endswith("@anelec.fr>")
    assert msg.get_content().rstrip().endswith("Cordialement,\nJean Martin\nANELEC")


def test_sans_copie_cachee():
    m = er.Messagerie(**{**M.__dict__, "copie_cachee": False})
    assert er.construire_message(m, "a@b-fictif.fr", "Objet", "Texte")["Bcc"] is None


def test_objet_sur_une_seule_ligne_aucune_injection_d_en_tete():
    msg = er.construire_message(M, "a@b-fictif.fr", "Devis\r\nBcc: pirate@exemple.com", "Texte")
    assert msg["Subject"] == "Devis Bcc: pirate@exemple.com"
    assert msg.get_all("Bcc") == ["devis@anelec.fr"]


@pytest.mark.parametrize("dest", ["", "pas-une-adresse", "a@b", "x@y.fr, pirate@z.com", "x@y.fr\nBcc: z@z.com"])
def test_destinataire_invalide_refuse(dest):
    with pytest.raises(er.ErreurEnvoi):
        er.construire_message(M, dest, "Objet", "Texte")


def test_objet_ou_texte_vide_refuse():
    with pytest.raises(er.ErreurEnvoi):
        er.construire_message(M, "a@b-fictif.fr", "  ", "Texte")
    with pytest.raises(er.ErreurEnvoi):
        er.construire_message(M, "a@b-fictif.fr", "Objet", "\n ")


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.5", "192.168.1.10", "169.254.169.254", "::1", "fd00::1"])
def test_serveur_vers_adresse_privee_refuse(ip):
    fam = socket.AF_INET6 if ":" in ip else socket.AF_INET
    with pytest.raises(er.ErreurEnvoi, match="privée"):
        er.verifier_hote("smtp.exemple.fr", 587, resoudre=lambda *a, **k: [(fam, 1, 6, "", (ip, 587))])


@pytest.mark.parametrize("hote,port", [("smtp.exemple.fr", 25), ("localhost", 587), ("10.0.0.5", 587),
                                       ("smtp exemple.fr", 587), ("", 465)])
def test_port_ou_nom_invalide_refuse(hote, port):
    with pytest.raises(er.ErreurEnvoi):
        er.verifier_hote(hote, port, resoudre=PUBLIC)


def test_serveur_introuvable():
    def absent(*a, **k):
        raise socket.gaierror("inconnu")
    with pytest.raises(er.ErreurEnvoi, match="introuvable"):
        er.verifier_hote("smtp.inexistant-fictif.fr", 465, resoudre=absent)


class FauxSMTP:
    journal: list = []
    erreur = None

    def __init__(self, hote, port, timeout=None, context=None):
        self.journal.append(("connexion", hote, port, isinstance(context, ssl.SSLContext)))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.journal.append(("fin",))

    def starttls(self, context=None):
        self.journal.append(("starttls", context.verify_mode == ssl.CERT_REQUIRED))

    def login(self, u, p):
        if self.erreur:
            raise self.erreur
        self.journal.append(("login", u))

    def send_message(self, msg):
        self.journal.append(("envoi", msg["To"]))
        return {}


@pytest.fixture
def faux():
    FauxSMTP.journal, FauxSMTP.erreur = [], None
    return FauxSMTP


def test_envoi_ssl_465(faux):
    msg = er.construire_message(M, "a@b-fictif.fr", "Objet", "Texte")
    mid = er.envoyer(M, msg, smtp_ssl=faux, smtp=None, resoudre=PUBLIC)
    assert mid == msg["Message-ID"]
    assert faux.journal == [("connexion", "smtp.zoho.eu", 465, True), ("login", "devis@anelec.fr"),
                            ("envoi", "a@b-fictif.fr"), ("fin",)]


def test_envoi_starttls_587_certificat_verifie(faux):
    m = er.Messagerie(**{**M.__dict__, "port": 587})
    er.envoyer(m, er.construire_message(m, "a@b-fictif.fr", "Objet", "Texte"), smtp_ssl=None, smtp=faux, resoudre=PUBLIC)
    assert faux.journal[1] == ("starttls", True)


def test_mot_de_passe_refuse_message_lisible_sans_secret(faux):
    faux.erreur = smtplib.SMTPAuthenticationError(535, b"5.7.8 bad credentials secret-123")
    with pytest.raises(er.ErreurEnvoi) as e:
        er.envoyer(M, er.construire_message(M, "a@b-fictif.fr", "Objet", "Texte"), smtp_ssl=faux, resoudre=PUBLIC)
    assert "mot de passe" in str(e.value) and "secret-123" not in str(e.value)


def test_delai_depasse(faux):
    faux.erreur = socket.timeout("timed out")
    with pytest.raises(er.ErreurEnvoi, match="délai"):
        er.envoyer(M, er.construire_message(M, "a@b-fictif.fr", "Objet", "Texte"), smtp_ssl=faux, resoudre=PUBLIC)


def test_erreur_de_boite_distincte_d_un_destinataire_refuse(faux):
    faux.erreur = smtplib.SMTPAuthenticationError(535, b"refus")
    with pytest.raises(er.ErreurBoite):
        er.envoyer(M, er.construire_message(M, "a@b-fictif.fr", "Objet", "Texte"), smtp_ssl=faux, resoudre=PUBLIC)
    faux.erreur = smtplib.SMTPRecipientsRefused({"a@b-fictif.fr": (550, b"inconnu")})
    with pytest.raises(er.ErreurEnvoi) as e:
        er.envoyer(M, er.construire_message(M, "a@b-fictif.fr", "Objet", "Texte"), smtp_ssl=faux, resoudre=PUBLIC)
    assert not isinstance(e.value, er.ErreurBoite)
