"""Unit tests for the tenant OCR model preference (Reglages > Modele OCR
prefere). Covers ai_service._ocr_cascade_stages(preferred=...) reordering
and the server.OCR_MODEL_CHOICES validation used by PUT /settings/integrations.

No network, no DB needed -- pure function tests.
"""
import sys

sys.path.insert(0, "/app/backend")
import ai_service  # noqa: E402
import server  # noqa: E402


def _labels(stages):
    return [label for label, _model, _timeout in stages]


def _stages(preferred=None):
    return ai_service._ocr_cascade_stages(preferred=preferred)


class TestOcrCascadePreferenceReordering:
    def test_default_order_is_unchanged_without_preference(self):
        # 2026-09-29 : GLM-OCR remplace PaddleOCR-VL-1.6 en tête de cascade.
        # 2026-10-02 : PaddleOCR-VL-1.6 réinstallé sur le VPS -> dernier étage.
        assert _labels(_stages()) == [
            "GLM-OCR", "LightOnOCR-2-1B", "Qwen2.5-VL-7B", "olmOCR-2-7B",
            "PaddleOCR-VL-1.6",
        ]

    def test_preferred_lightonocr_moves_to_front_others_unchanged(self):
        labels = _labels(_stages(preferred="lightonocr"))
        assert labels[0] == "LightOnOCR-2-1B"
        # every stage is still present -- reordering, not replacement.
        assert set(labels) == {"GLM-OCR", "LightOnOCR-2-1B", "Qwen2.5-VL-7B",
                               "olmOCR-2-7B", "PaddleOCR-VL-1.6"}
        assert labels[1:] == ["GLM-OCR", "Qwen2.5-VL-7B", "olmOCR-2-7B", "PaddleOCR-VL-1.6"]

    def test_ancienne_preference_paddleocr_vaut_glm_ocr(self):
        # Clé historique « paddleocr » (avant le 29/09/2026) : routée vers
        # GLM-OCR et absente des choix proposés au tenant. La NOUVELLE clé
        # est « paddleocr-vl » (modèle réinstallé sur le VPS le 02/10/2026).
        assert _labels(_stages(preferred="paddleocr"))[0] == "GLM-OCR"
        assert "paddleocr" not in server.OCR_MODEL_CHOICES
        assert _labels(_stages())[0] == "GLM-OCR"  # PaddleOCR jamais en tête par défaut

    def test_preferred_paddleocr_vl_moves_to_front(self):
        # 02/10/2026 : PaddleOCR-VL-1.6-0.9B réinstallé sur le VPS et
        # sélectionnable dans les réglages (clé « paddleocr-vl »).
        labels = _labels(_stages(preferred="paddleocr-vl"))
        assert labels[0] == "PaddleOCR-VL-1.6"
        assert labels[1:] == ["GLM-OCR", "LightOnOCR-2-1B", "Qwen2.5-VL-7B", "olmOCR-2-7B"]

    def test_preferred_olmocr2_moves_to_front(self):
        labels = _labels(_stages(preferred="olmocr2"))
        assert labels[0] == "olmOCR-2-7B"
        assert len(labels) == 5

    def test_auto_is_a_no_op(self):
        assert _labels(_stages(preferred="auto")) == _labels(_stages())

    def test_unknown_or_empty_preference_is_a_no_op(self):
        default = _labels(_stages())
        assert _labels(_stages(preferred="")) == default
        assert _labels(_stages(preferred=None)) == default
        assert _labels(_stages(preferred="not-a-real-model")) == default

    def test_every_stage_timeout_exceeds_its_own_measured_duration(self):
        # 02/10/2026 : un étage ne doit jamais être coupé avant SA propre
        # durée mesurée (règle max(propre, suivante) x 1.2) -- vrai aussi
        # pour la cascade réordonnée par préférence (olmocr2 ~587s en tête).
        for preferred in (None, "olmocr2", "paddleocr-vl"):
            for label, _model, timeout in _stages(preferred=preferred):
                own = ai_service._OCR_STAGE_MEASURED_SECONDS.get(label, 300)
                assert timeout >= round(ai_service._OCR_STAGE_TIMEOUT_MULTIPLIER * own), \
                    f"{label} (preferred={preferred}) : timeout {timeout}s < 1.2x {own}s"

    def test_every_public_choice_key_maps_to_a_real_stage_label(self):
        # server.OCR_MODEL_CHOICES (frontend-facing) and
        # ai_service.OCR_MODEL_PREFERENCE_LABELS (backend routing) must stay
        # in sync -- every non-"auto" tenant-facing key must resolve to an
        # actual cascade stage, otherwise a saved preference would silently
        # do nothing.
        stage_labels = set(_labels(_stages()))
        for key in server.OCR_MODEL_CHOICES:
            if key == "auto":
                continue
            assert key in ai_service.OCR_MODEL_PREFERENCE_LABELS, f"{key} missing from OCR_MODEL_PREFERENCE_LABELS"
            assert ai_service.OCR_MODEL_PREFERENCE_LABELS[key] in stage_labels


class TestOcrModelPreferenceValidation:
    def test_all_choices_are_valid_pydantic_input(self):
        for key in server.OCR_MODEL_CHOICES:
            body = server.IntegrationSettings(ocr_model_preference=key)
            assert body.ocr_model_preference == key

    def test_none_defaults_to_auto_semantics(self):
        body = server.IntegrationSettings()
        assert body.ocr_model_preference is None  # update_settings() normalizes None -> "auto"
