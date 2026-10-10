"""Envoi des relances par e-mail depuis la boîte de l'entreprise (SMTP).

Logique sans base : construction du message, contrôle du serveur SMTP et
envoi. L'API (clients_module) décide QUI reçoit QUOI et QUAND, et trace le
résultat dans `blueseatra.relances`.

Règles
------
1. Expéditeur : la boîte de l'entreprise, renseignée dans « Messagerie
   d'envoi ». Les réponses du client arrivent dans cette boîte (Reply-To).
2. Ports 465 (SSL) et 587 (STARTTLS) uniquement, certificat vérifié. Le
   port 25 est bloqué par Render et n'est pas chiffré.
3. Serveur SMTP : nom d'hôte public uniquement. Une adresse privée, locale
   ou réservée est refusée (pas de connexion vers le réseau interne).
4. Texte brut, sans pièce jointe ni lien de suivi. Copie cachée à
   l'expéditeur si l'entreprise l'a demandée, pour garder une trace dans
   sa boîte « Envoyés ».
5. Le mot de passe n'apparaît jamais dans un message d'erreur.
"""
from __future__ import annotations

import ipaddress
import re
import smtplib
import socket
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

PORTS = {465: "ssl", 587: "starttls"}
DELAI_SMTP_S = 20
OBJET_MAX = 200
TEXTE_MAX = 20_000

_HOTE = re.compile(r"^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$", re.I)
_EMAIL = re.compile(r"^[^@\s<>\"',;]+@[a-z0-9.-]+\.[a-z]{2,63}$", re.I)


class ErreurEnvoi(Exception):
    """Erreur lisible par l'utilisateur, sans secret."""


class ErreurBoite(ErreurEnvoi):
    """La boîte d'envoi elle-même est en cause (serveur, identifiants, chiffrement) :
    les relances suivantes échoueraient de la même façon."""


@dataclass(frozen=True)
class Messagerie:
    hote: str
    port: int
    identifiant: str
    mot_de_passe: str
    expediteur_email: str
    expediteur_nom: str = ""
    signature: str = ""
    copie_cachee: bool = True


def email_valide(v: str | None) -> bool:
    return bool(v) and bool(_EMAIL.match(v.strip()))


def verifier_hote(hote: str, port: int, *, resoudre=socket.getaddrinfo) -> str:
    """Nom d'hôte public et port autorisé, sinon ErreurEnvoi."""
    hote = (hote or "").strip().lower().rstrip(".")
    if port not in PORTS:
        raise ErreurBoite("Port SMTP non pris en charge : utilisez 465 (SSL) ou 587 (STARTTLS).")
    if not _HOTE.match(hote):
        raise ErreurBoite("Serveur SMTP invalide : indiquez un nom d'hôte, par exemple smtp.zoho.eu.")
    try:
        adresses = {a[4][0] for a in resoudre(hote, port, type=socket.SOCK_STREAM)}
    except (socket.gaierror, UnicodeError):
        raise ErreurBoite(f"Serveur SMTP introuvable : {hote}.") from None
    if not adresses:
        raise ErreurBoite(f"Serveur SMTP introuvable : {hote}.")
    for a in adresses:
        if not ipaddress.ip_address(a.split("%")[0]).is_global:
            raise ErreurBoite("Serveur SMTP refusé : il pointe vers une adresse privée ou réservée.")
    return hote


def _ligne(v: str, limite: int) -> str:
    """Valeur d'en-tête sur une seule ligne (aucune injection d'en-tête)."""
    return re.sub(r"[\r\n\t]+", " ", v or "").strip()[:limite]


def construire_message(m: Messagerie, destinataire: str, objet: str, texte: str) -> EmailMessage:
    if not email_valide(destinataire):
        raise ErreurEnvoi("Adresse e-mail du contact invalide.")
    if not email_valide(m.expediteur_email):
        raise ErreurEnvoi("Adresse d'expédition invalide dans la messagerie d'envoi.")
    objet = _ligne(objet, OBJET_MAX)
    corps = (texte or "").strip()
    if not objet or not corps:
        raise ErreurEnvoi("L'objet et le texte de la relance sont obligatoires.")
    if m.signature.strip():
        corps = f"{corps}\n{m.signature.strip()}"
    msg = EmailMessage()
    msg["From"] = formataddr((_ligne(m.expediteur_nom, 120), m.expediteur_email.strip()))
    msg["To"] = destinataire.strip()
    msg["Reply-To"] = m.expediteur_email.strip()
    if m.copie_cachee:
        msg["Bcc"] = m.expediteur_email.strip()
    msg["Subject"] = objet
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = make_msgid(domain=m.expediteur_email.split("@")[-1].strip())
    msg.set_content(corps[:TEXTE_MAX])
    return msg


def envoyer(m: Messagerie, msg: EmailMessage, *, smtp_ssl=smtplib.SMTP_SSL, smtp=smtplib.SMTP,
            resoudre=socket.getaddrinfo) -> str:
    """Envoie le message (bloquant : à appeler dans un thread). Rend le Message-ID."""
    hote = verifier_hote(m.hote, m.port, resoudre=resoudre)
    ctx = ssl.create_default_context()
    try:
        if PORTS[m.port] == "ssl":
            serveur = smtp_ssl(hote, m.port, timeout=DELAI_SMTP_S, context=ctx)
        else:
            serveur = smtp(hote, m.port, timeout=DELAI_SMTP_S)
        with serveur as s:
            if PORTS[m.port] == "starttls":
                s.starttls(context=ctx)
            s.login(m.identifiant, m.mot_de_passe)
            refuses = s.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        raise ErreurBoite("Identifiant ou mot de passe SMTP refusé par le serveur.") from None
    except smtplib.SMTPRecipientsRefused:
        raise ErreurEnvoi("Adresse du destinataire refusée par le serveur SMTP.") from None
    except smtplib.SMTPSenderRefused:
        raise ErreurBoite("Adresse d'expédition refusée par le serveur SMTP.") from None
    except ssl.SSLError:
        raise ErreurBoite("Connexion chiffrée impossible avec le serveur SMTP (certificat ou port).") from None
    except (socket.timeout, TimeoutError):
        raise ErreurBoite("Le serveur SMTP ne répond pas (délai dépassé).") from None
    except (smtplib.SMTPException, OSError) as e:
        raise ErreurBoite(f"Envoi refusé par le serveur SMTP ({type(e).__name__}).") from None
    if refuses:
        raise ErreurEnvoi("Adresse du destinataire refusée par le serveur SMTP.")
    return str(msg["Message-ID"])
