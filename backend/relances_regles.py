"""Règles de relance des devis envoyés (module Clients).

Logique pure, sans base ni réseau : elle calcule QUAND relancer, PAR QUEL
CANAL et POURQUOI, à partir d'un devis et des règles de l'entreprise.
L'API écrit ensuite le résultat dans `blueseatra.relances`.

Règles (docs/specs/module-clients.md, section « Règles de relance »)
---------------------------------------------------------------------
1. Déclencheur : un devis passe au statut « envoyé ». Rien avant.
2. Échéances en jours OUVRÉS (hors samedi, dimanche et jours fériés
   français), à l'heure de relance de l'entreprise (9 h par défaut) :
   J+3 après l'envoi, puis +7, puis +14 (3 relances au maximum).
   Demande urgente : J+1, +2, +4.
3. Rappel d'expiration : si le devis a une date de validité, un rappel
   « expire le … » est prévu N jours ouvrés avant (3 par défaut), et
   aucune relance ordinaire n'est prévue après l'expiration.
4. Canal : appel si le montant HT dépasse le seuil de l'entreprise
   (10 000 € par défaut) ou si le contact n'a pas d'e-mail ; sinon e-mail.
   Contact opposé aux relances : simple tâche interne, jamais d'e-mail.
5. Arrêt : devis accepté, refusé, classé sans suite, remis en brouillon,
   client archivé, ou règles désactivées -> les relances prévues sont
   annulées avec leur motif (jamais supprimées).
6. Une relance n'est JAMAIS envoyée seule : c'est une tâche avec un texte
   proposé ; l'utilisateur envoie, appelle ou marque « faite ».
7. Chaque relance porte une raison lisible, affichée telle quelle.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

RANG_EXPIRATION = 7


@dataclass(frozen=True)
class Regles:
    actif: bool = True
    delais_jours_ouvres: tuple[int, ...] = (3, 7, 14)
    delais_urgent: tuple[int, ...] = (1, 2, 4)
    max_relances: int = 3
    validite_devis_jours: int = 30
    rappel_avant_expiration_j: int = 3
    seuil_appel_ht: float = 10_000.0
    heure_relance: time = time(9, 0)
    fuseau: str = "Europe/Paris"


@dataclass(frozen=True)
class Devis:
    id: str
    numero: str
    envoye_le: datetime                    # horodatage de l'envoi (avec fuseau)
    total_ht: float = 0.0
    urgent: bool = False
    valable_jusqu_au: date | None = None
    contact_email: str | None = None
    contact_accepte_relances: bool = True
    langue: str = "fr"


@dataclass(frozen=True)
class RelancePrevue:
    rang: int
    echeance: datetime
    canal: str
    raison: str
    brouillon: str = field(default="", compare=False)


# --- Calendrier ------------------------------------------------------------

def _paques(annee: int) -> date:
    """Dimanche de Pâques (algorithme de Meeus/Jones/Butcher)."""
    a, b, c = annee % 19, annee // 100, annee % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 22 * l) // 451
    mois = (h + l - 7 * m + 114) // 31
    jour = ((h + l - 7 * m + 114) % 31) + 1
    return date(annee, mois, jour)


def jours_feries(annee: int) -> set[date]:
    """Les 11 jours fériés nationaux (métropole)."""
    p = _paques(annee)
    return {
        date(annee, 1, 1), date(annee, 5, 1), date(annee, 5, 8), date(annee, 7, 14),
        date(annee, 8, 15), date(annee, 11, 1), date(annee, 11, 11), date(annee, 12, 25),
        p + timedelta(days=1),    # lundi de Pâques
        p + timedelta(days=39),   # Ascension
        p + timedelta(days=50),   # lundi de Pentecôte
    }


def est_ouvre(j: date) -> bool:
    return j.weekday() < 5 and j not in jours_feries(j.year)


def ajouter_jours_ouvres(depart: date, n: int) -> date:
    j = depart
    while n > 0:
        j += timedelta(days=1)
        if est_ouvre(j):
            n -= 1
    return j


def retirer_jours_ouvres(depart: date, n: int) -> date:
    j = depart
    while n > 0:
        j -= timedelta(days=1)
        if est_ouvre(j):
            n -= 1
    return j


def _a_l_heure(j: date, r: Regles) -> datetime:
    return datetime.combine(j, r.heure_relance, tzinfo=ZoneInfo(r.fuseau))


def _fr_date(j: date) -> str:
    return j.strftime("%d/%m/%Y")


# --- Planification ----------------------------------------------------------

def canal_pour(d: Devis, r: Regles) -> str:
    if not d.contact_accepte_relances:
        return "tache"
    if d.total_ht >= r.seuil_appel_ht or not d.contact_email:
        return "appel"
    return "email"


def _brouillon(d: Devis, rang: int, expiration: bool) -> str:
    """Texte proposé, jamais envoyé seul. Aucun montant recalculé : le
    total cité est celui du devis."""
    if d.langue == "en":
        if expiration:
            return (f"Hello,\n\nOur quote {d.numero} remains valid until "
                    f"{d.valable_jusqu_au:%d/%m/%Y}. Would you like us to schedule the works?\n\nBest regards,")
        return (f"Hello,\n\nFollowing up on our quote {d.numero} sent on {d.envoye_le:%d/%m/%Y}: "
                f"do you have any questions, or would you like us to adjust it?\n\nBest regards,")
    if expiration:
        return (f"Bonjour,\n\nNotre devis {d.numero} reste valable jusqu'au "
                f"{_fr_date(d.valable_jusqu_au)}. Souhaitez-vous que nous planifiions l'intervention ?"
                "\n\nCordialement,")
    suite = "" if rang == 1 else " Nous restons à votre disposition pour l'adapter si besoin."
    return (f"Bonjour,\n\nJe me permets de revenir vers vous au sujet de notre devis {d.numero}, "
            f"envoyé le {_fr_date(d.envoye_le.date())}. Avez-vous des questions ?{suite}\n\nCordialement,")


def planifier(d: Devis, r: Regles, ajd: date | None = None) -> list[RelancePrevue]:
    """Relances à prévoir au moment de l'envoi d'un devis."""
    if not r.actif or r.max_relances <= 0:
        return []
    tz = ZoneInfo(r.fuseau)
    envoi = d.envoye_le.astimezone(tz).date()
    ajd = ajd or envoi
    delais = list(r.delais_urgent if d.urgent else r.delais_jours_ouvres)[: r.max_relances]
    canal = canal_pour(d, r)
    expire = d.valable_jusqu_au
    rappel_expiration = retirer_jours_ouvres(expire, r.rappel_avant_expiration_j) if expire else None

    prevues: list[RelancePrevue] = []
    j = envoi
    for rang, delai in enumerate(delais, start=1):
        j = ajouter_jours_ouvres(j, delai)
        if expire and j >= rappel_expiration:
            break                             # le rappel d'expiration prend le relais
        if j < ajd:
            continue
        raison = (f"Devis {d.numero} envoyé le {_fr_date(envoi)}, sans réponse : "
                  f"relance {rang} sur {len(delais)}")
        if d.urgent:
            raison += " (demande urgente)"
        if canal == "appel" and d.total_ht >= r.seuil_appel_ht:
            raison += f" ; appel conseillé, montant supérieur à {r.seuil_appel_ht:,.0f} € HT".replace(",", " ")
        if canal == "tache":
            raison += " ; le contact refuse les relances : aucun e-mail, suivi interne seulement"
        prevues.append(RelancePrevue(rang, _a_l_heure(j, r), canal, raison + ".",
                                     _brouillon(d, rang, False) if canal != "tache" else ""))
    if expire and rappel_expiration > envoi and rappel_expiration >= ajd:
        prevues.append(RelancePrevue(
            RANG_EXPIRATION, _a_l_heure(rappel_expiration, r), canal,
            f"Devis {d.numero} valable jusqu'au {_fr_date(expire)} : rappel avant expiration.",
            _brouillon(d, RANG_EXPIRATION, True) if canal != "tache" else ""))
    return prevues


MOTIFS_ARRET = {
    "accepte": "Devis accepté",
    "refuse": "Devis refusé",
    "sans_suite": "Devis classé sans suite",
    "brouillon": "Devis remis en brouillon",
    "client_archive": "Client archivé",
    "regles_desactivees": "Relances désactivées par l'entreprise",
    "contact_oppose": "Le contact refuse les relances",
}


def motif_arret(evenement: str) -> str:
    """Motif enregistré sur chaque relance annulée (jamais supprimée)."""
    if evenement not in MOTIFS_ARRET:
        raise ValueError(f"événement d'arrêt inconnu : {evenement}")
    return MOTIFS_ARRET[evenement]


def apres_resultat(resultat: str, maintenant: datetime, r: Regles) -> datetime | None:
    """Relance « faite » : que faire ensuite ?
    - accepte / refuse : on arrête tout (issue du devis mise à jour) ;
    - a_rappeler : nouvelle tâche le jour ouvré suivant ;
    - en_reflexion : on laisse courir les relances déjà prévues ;
    - sans_reponse : idem, la relance suivante reste à sa date.
    Renvoie l'échéance d'une relance supplémentaire, ou None."""
    if resultat == "a_rappeler":
        j = ajouter_jours_ouvres(maintenant.astimezone(ZoneInfo(r.fuseau)).date(), 1)
        return _a_l_heure(j, r)
    if resultat in ("accepte", "refuse", "en_reflexion", "sans_reponse"):
        return None
    raise ValueError(f"résultat inconnu : {resultat}")
