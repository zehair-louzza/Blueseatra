"""Unit tests for the material/petit-materiel presentation fields added to
matching.build_quote_lines (line_type_hint, included_items, notes).

These fields come from the AI proposal (role=reason, EXPAND_SYSTEM / skill
detail-materiaux-petit-materiel) and must NEVER influence pricing -- only
the catalog match does. No network, no DB needed.
"""
import sys

sys.path.insert(0, "/app/backend")
import matching  # noqa: E402


def _catalog_item(item_code="MAT-001", item_label="Prise 16A encastree",
                   unit_price_ht=12.5, unit="u", category="electricite"):
    return {
        "item_code": item_code,
        "item_label": item_label,
        "label_norm": matching.normalize(item_label),
        "unit_price_ht": unit_price_ht,
        "unit": unit,
        "category": category,
        "margin": 0,
        "is_active": True,
    }


class TestLineTypeHintWhitelist:
    def test_allowed_hint_is_kept(self):
        li = {"line_type_hint": "installation_supplies"}
        assert matching._line_type_hint(li) == "installation_supplies"

    def test_unknown_hint_falls_back_to_material(self):
        li = {"line_type_hint": "prix_calcule_par_ia"}
        assert matching._line_type_hint(li) == "material"

    def test_missing_hint_falls_back_to_material(self):
        assert matching._line_type_hint({}) == "material"

    def test_all_documented_hints_are_allowed(self):
        for hint in ("main_work", "installation_supplies", "consumable",
                     "finish", "protection", "waste_removal", "testing"):
            assert matching._line_type_hint({"line_type_hint": hint}) == hint


class TestPresentationExtras:
    def test_included_items_and_notes_pass_through(self):
        li = {"included_items": ["visserie", "chevilles", "colle"], "notes": "Section a confirmer"}
        extras = matching._presentation_extras(li)
        assert extras["included_items"] == ["visserie", "chevilles", "colle"]
        assert extras["notes"] == "Section a confirmer"

    def test_missing_fields_default_to_empty(self):
        extras = matching._presentation_extras({})
        assert extras["included_items"] == []
        assert extras["notes"] is None

    def test_non_list_included_items_is_ignored_not_crashed(self):
        extras = matching._presentation_extras({"included_items": "pas une liste"})
        assert extras["included_items"] == []

    def test_extras_never_contain_a_price_key(self):
        # A malicious/buggy AI payload trying to smuggle a price must have
        # zero effect: only whitelisted keys are ever returned.
        li = {"included_items": ["x"], "notes": "y", "unit_price_ht": 999, "line_ht": 999}
        extras = matching._presentation_extras(li)
        assert set(extras.keys()) == {"included_items", "notes"}


class TestBuildQuoteLinesNeverPricedByAI:
    def test_matched_line_uses_only_catalog_price_despite_ai_hint(self):
        catalog = [_catalog_item(unit_price_ht=12.5)]
        extracted = {
            "line_items": [{
                "label": "Prise 16A encastree",
                "quantity": 3,
                "unit": "u",
                "category": "electricite",
                "line_type_hint": "main_work",
                "included_items": ["boite d'encastrement", "gaine", "connecteurs"],
                "notes": "Cheminement reel a confirmer",
                # An AI payload could try to inject a price -- it must be ignored.
                "unit_price_ht": 99999,
            }],
        }
        lines, total_ht, _ = matching.build_quote_lines(extracted, catalog)
        material_lines = [l for l in lines if l.get("matched_item_code") == "MAT-001"]
        assert len(material_lines) == 1
        line = material_lines[0]
        # Price comes exclusively from the catalog item, never from the AI payload.
        assert line["unit_price_ht"] == 12.5
        assert line["line_type"] == "main_work"
        assert line["included_items"] == ["boite d'encastrement", "gaine", "connecteurs"]
        assert line["notes"] == "Cheminement reel a confirmer"

    def test_unmatched_line_keeps_price_empty_and_carries_extras(self):
        extracted = {
            "line_items": [{
                "label": "Article totalement hors catalogue xyz",
                "quantity": 1,
                "unit": "u",
                "line_type_hint": "consumable",
                "included_items": ["mastic", "silicone"],
            }],
        }
        lines, total_ht, _ = matching.build_quote_lines(extracted, [])
        line = next(l for l in lines if l.get("request_label") == "Article totalement hors catalogue xyz")
        assert line["unit_price_ht"] is None
        assert line["status"] == "to_confirm"
        assert line["line_type"] == "consumable"
        assert line["included_items"] == ["mastic", "silicone"]

    def test_grouped_petit_materiel_line_without_catalog_match_stays_priceless(self):
        # The "fournitures de pose et consommables" forfait line must go
        # through the same catalog-or-empty rule as any other line.
        extracted = {
            "line_items": [{
                "label": "Fournitures de pose et consommables",
                "quantity": 1,
                "unit": "forfait",
                "line_type_hint": "installation_supplies",
                "included_items": ["visserie", "chevilles", "colles", "bandes", "protections"],
            }],
        }
        lines, total_ht, _ = matching.build_quote_lines(extracted, [])
        line = next(l for l in lines if l.get("request_label") == "Fournitures de pose et consommables")
        assert line["unit_price_ht"] is None
        assert line["line_type"] == "installation_supplies"
        assert total_ht == 0
