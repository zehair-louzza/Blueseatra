"""DD-2026-041 regressions: isolated TCE validation, no network or database."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tce_v4 as tce


class TestDD2026041(unittest.TestCase):
    def protect(self, label, source, proof, qty, action="fournir_et_poser", lot="11", quote=None):
        row = {"label": label, "preuve": source if quote is None else quote,
               "quantite_preuve": proof, "qty": qty, "unit": "u",
               "action": action, "lot_tce": lot}
        return tce.protect_extraction({"line_items": [row]}, source)["line_items"][0]

    def test_explicit_quantities(self):
        cases = [
            ("Porte blindée", "Fourniture et pose d'une porte blindée", "d'une porte blindée", None, 1),
            ("Réglage et graissage paumelles fenêtres", "Réglage et graissage de 4 paumelles", "4 paumelles", 4, 4),
            ("Crémones défaillantes", "remplacement de 2 crémones", "2 crémones", None, 2),
            ("Prises de courant 16 A", "Pose de 12 prises de courant 16 A", "12 prises de courant", None, 12),
            ("Lave-mains avec meuble", "pose d'un lave-mains avec meuble", "d'un lave-mains", None, 1),
        ]
        for label, source, proof, qty, expected in cases:
            with self.subTest(label=label):
                self.assertEqual(self.protect(label, source, proof, qty)["qty"], expected)

    def test_typography_and_duplicate_source(self):
        for source in ["Fourniture et pose d’une porte blindée", "Fourniture et pose d'une porte\nblindée", "Fourniture et pose d'une porte blindée\nFourniture et pose d'une porte blindée"]:
            with self.subTest(source=source):
                row = self.protect("Porte blindée", source, "d'une porte blindée", 1,
                                   quote="Fourniture et pose d'une porte blindée")
                self.assertEqual(row["qty"], 1)

    def test_characteristics_and_wrong_object_rejected(self):
        cases = [
            ("Ballon thermodynamique", "Ballon thermodynamique 200 L", "200 L", 200),
            ("Prise de courant", "Prise de courant 16 A", "16 A", 16),
            ("Évier", "raccorder deux éviers dans une pièce", "une pièce", 1),
            ("Évier", "Fourniture de 3 siphons et raccordement de 2 éviers", "3 siphons", 3),
        ]
        for label, source, proof, qty in cases:
            with self.subTest(label=label, proof=proof):
                self.assertIsNone(self.protect(label, source, proof, qty)["qty"])

    def test_invalid_numeric_values_rejected(self):
        for value in [True, float("nan"), float("inf"), 0, -1, 2]:
            with self.subTest(value=value):
                self.assertIsNone(self.protect("Chauffe-eau", "Fourniture d'un chauffe-eau", "un chauffe-eau", value)["qty"])

    def test_unknown_quantity_stays_unknown(self):
        row = self.protect("Tableau électrique", "Remplacement du tableau électrique", "", None)
        self.assertIsNone(row["qty"])

    def test_lots_corrected(self):
        for label, code, expected in [
            ("Porte blindée", "07", "16"), ("Cylindre haute sécurité", "07", "16"),
            ("Verrous de sûreté", "07", "16"), ("Crémones", "07", "05"),
            ("Réglage paumelles fenêtres", "07", "05"), ("Tableau électrique", "10", "14"),
            ("Prises de courant 16 A", "10", "14"), ("Points d'éclairage", "10", "14"),
            ("Détecteurs de fumée", "10", "16"), ("Ballon thermodynamique", None, "11"),
            ("Isolation des combles", "07", "07"), ("Peinture murale", "10", "10"),
        ]:
            with self.subTest(label=label):
                self.assertEqual(tce.detect_lot({"label": label, "lot_tce": code}), expected)

    def test_explicit_replacement_supply(self):
        source = "Remplacement du chauffe-eau électrique par un ballon thermodynamique 200 L"
        row = self.protect("Ballon thermodynamique", source, "un ballon thermodynamique 200 L", 1)
        self.assertTrue(row["tce_fourniture_autorisee"])

    def test_source_context_for_supply_fragments(self):
        source = "Fourniture et pose d'un mitigeur thermostatique de douche et d'une colonne de douche"
        for label, proof in [("Mitigeur thermostatique de douche", "d'un mitigeur thermostatique de douche"),
                             ("Colonne de douche", "d'une colonne de douche")]:
            with self.subTest(label=label):
                row = self.protect(label, source, proof, 1, quote=proof)
                self.assertTrue(row["tce_fourniture_autorisee"])
                self.assertEqual(row["qty"], 1)
                self.assertEqual(row["preuve"], source)

    def test_service_actions_never_authorize_purchase(self):
        for action in [None, "poser", "raccorder", "reparer", "mettre_en_service", "modifier"]:
            with self.subTest(action=action):
                row = self.protect("Évier", "Fourniture d'un évier", "un évier", 1, action=action)
                self.assertFalse(row["tce_fourniture_autorisee"])

    def test_client_existing_negation_and_mixed_actions_blocked(self):
        for source in ["Pose d'un évier, fourniture assurée par le client", "Fourniture d'un évier existant",
                       "Fourniture d'un évier sans fourniture", "Fourniture d'un évier et raccordement",
                       "Fourniture d'un évier et mise en service"]:
            with self.subTest(source=source):
                row = self.protect("Évier", source, "un évier", 1)
                self.assertFalse(row["tce_fourniture_autorisee"])

    def test_forged_source_and_approvals_rejected(self):
        row = self.protect("Évier", "Raccordement d'un évier existant", "un évier", 1,
                           quote="Fourniture d'un évier")
        self.assertIsNone(row["qty"])
        self.assertFalse(row["tce_fourniture_autorisee"])

    def test_protection_does_not_mutate_input(self):
        data = {"line_items": [{"label": "Prises de courant", "qty": 12, "unit": "u", "action": "poser",
                               "lot_tce": "10", "preuve": "Pose de 12 prises de courant", "quantite_preuve": "12 prises de courant"}]}
        before = copy.deepcopy(data)
        result = tce.protect_extraction(data, "Pose de 12 prises de courant")
        self.assertEqual(data, before)
        self.assertEqual(result["line_items"][0]["lot_tce"], "14")

    def test_incomplete_publication_still_blocked(self):
        self.assertTrue(tce.blockers({"lines": [{"qty": 1, "unit_price_ht": None, "line_ht": None, "status": "to_confirm"}]}))
        self.assertEqual(tce.blockers({"lines": None}), ["Aucune prestation chiffrable."])


if __name__ == "__main__":
    unittest.main()
