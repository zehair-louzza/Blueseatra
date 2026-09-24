"""Règles de relance : calendrier, échéances, canal, arrêt."""
from __future__ import annotations

import sys
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import relances_regles as rr  # noqa: E402

PARIS = ZoneInfo("Europe/Paris")
R = rr.Regles()


def envoye(j, h=15):
    return datetime.combine(j, time(h, 0), tzinfo=PARIS)


def test_jours_feries_2026_et_2027():
    f26 = rr.jours_feries(2026)
    assert date(2026, 4, 6) in f26      # lundi de Pâques 2026
    assert date(2026, 5, 14) in f26     # Ascension 2026
    assert date(2026, 5, 25) in f26     # lundi de Pentecôte 2026
    assert len(f26) == 11
    assert date(2027, 3, 29) in rr.jours_feries(2027)


def test_jours_ouvres_sautent_week_end_et_feries():
    assert rr.ajouter_jours_ouvres(date(2026, 10, 30), 1) == date(2026, 11, 2)   # vendredi -> lundi
    assert rr.ajouter_jours_ouvres(date(2026, 11, 10), 1) == date(2026, 11, 12)  # 11 novembre sauté
    assert rr.ajouter_jours_ouvres(date(2026, 12, 24), 1) == date(2026, 12, 28)  # Noël + week-end


def test_trois_relances_standard_a_9h():
    d = rr.Devis("q1", "D-2026-041", envoye(date(2026, 9, 24)), total_ht=2400, contact_email="a@b.fr")
    p = rr.planifier(d, R)
    assert [x.rang for x in p] == [1, 2, 3]
    assert [x.echeance.date() for x in p] == [date(2026, 9, 29), date(2026, 10, 8), date(2026, 10, 28)]
    assert all(x.echeance.time() == time(9, 0) and x.canal == "email" for x in p)
    assert p[0].raison == "Devis D-2026-041 envoyé le 24/09/2026, sans réponse : relance 1 sur 3."
    assert "D-2026-041" in p[0].brouillon and "€" not in p[0].brouillon


def test_demande_urgente_raccourcit_les_delais():
    d = rr.Devis("q1", "D-1", envoye(date(2026, 9, 24)), urgent=True, contact_email="a@b.fr")
    assert [x.echeance.date() for x in rr.planifier(d, R)] == \
        [date(2026, 9, 25), date(2026, 9, 29), date(2026, 10, 5)]


def test_gros_montant_ou_sans_email_donne_un_appel():
    gros = rr.Devis("q1", "D-1", envoye(date(2026, 9, 24)), total_ht=18_500, contact_email="a@b.fr")
    p = rr.planifier(gros, R)
    assert {x.canal for x in p} == {"appel"} and "10 000 € HT" in p[0].raison
    sans_mail = rr.Devis("q2", "D-2", envoye(date(2026, 9, 24)), total_ht=500)
    assert {x.canal for x in rr.planifier(sans_mail, R)} == {"appel"}


def test_contact_oppose_aucun_email_ni_brouillon():
    d = rr.Devis("q1", "D-1", envoye(date(2026, 9, 24)), contact_email="a@b.fr",
                 contact_accepte_relances=False)
    p = rr.planifier(d, R)
    assert {x.canal for x in p} == {"tache"} and all(x.brouillon == "" for x in p)
    assert "refuse les relances" in p[0].raison


def test_rappel_d_expiration_remplace_les_relances_tardives():
    d = rr.Devis("q1", "D-1", envoye(date(2026, 9, 24)), contact_email="a@b.fr",
                 valable_jusqu_au=date(2026, 10, 15))
    p = rr.planifier(d, R)
    assert [x.rang for x in p] == [1, 2, rr.RANG_EXPIRATION]
    assert p[-1].echeance.date() == date(2026, 10, 12)      # 3 jours ouvrés avant le 15
    assert "valable jusqu'au 15/10/2026" in p[-1].raison


def test_relances_desactivees_ou_zero():
    d = rr.Devis("q1", "D-1", envoye(date(2026, 9, 24)), contact_email="a@b.fr")
    assert rr.planifier(d, rr.Regles(actif=False)) == []
    assert rr.planifier(d, rr.Regles(max_relances=0)) == []
    assert len(rr.planifier(d, rr.Regles(max_relances=1))) == 1


def test_replanification_ne_recree_pas_le_passe():
    d = rr.Devis("q1", "D-1", envoye(date(2026, 9, 24)), contact_email="a@b.fr")
    p = rr.planifier(d, R, ajd=date(2026, 10, 1))
    assert [x.rang for x in p] == [2, 3]


def test_brouillon_en_anglais():
    d = rr.Devis("q1", "Q-7", envoye(date(2026, 9, 24)), contact_email="a@b.com", langue="en")
    assert rr.planifier(d, R)[0].brouillon.startswith("Hello")


def test_arret_et_suite_apres_resultat():
    assert rr.motif_arret("accepte") == "Devis accepté"
    with pytest.raises(ValueError):
        rr.motif_arret("inconnu")
    lundi = rr.apres_resultat("a_rappeler", datetime(2026, 10, 30, 16, tzinfo=PARIS), R)
    assert lundi == datetime(2026, 11, 2, 9, tzinfo=PARIS)
    assert rr.apres_resultat("sans_reponse", datetime(2026, 10, 30, 16, tzinfo=PARIS), R) is None
