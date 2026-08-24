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


class TestOcrCascadePreferenceReordering:
    def test_default_order_is_unchanged_without_preference(self):
        assert _labels(ai_service._ocr_cascade_stages()) == [
            "PaddleOCR-VL-1.6", "GLM-OCR", "LightOnOCR-2-1B", "Qwen2.5-VL-7B", "olmOCR-2-7B",
        ]

    def test_preferred_glm_ocr_moves_to_front_others_unchanged(self):
        labels = _labels(ai_service._ocr_cascade_stages(preferred="glm-ocr"))
        assert labels[0] == "GLM-OCR"
        # every stage is still present -- reordering, not replacement.
        assert set(labels) == {"PaddleOCR-VL-1.6", "GLM-OCR", "LightOnOCR-2-1B", "Qwen2.5-VL-7B", "olmOCR-2-7B"}
        assert labels[1:] == ["PaddleOCR-VL-1.6", "LightOnOCR-2-1B", "Qwen2.5-VL-7B"]

    def test_preferred_olmocr2_moves_to_front(self):
        labels = _labels(ai_service._ocr_cascade_stages(preferred="olmocr2"))
        assert labels[0] == "olmOCR-2-7B"
        assert len(labels) == 5

    def test_auto_is_a_no_op(self):
        assert _labels(ai_service._ocr_cascade_stages(preferred="auto")) == \
            _labels(ai_service._ocr_cascade_stages())

    def test_unknown_or_empty_preference_is_a_no_op(self):
        default = _labels(ai_service._ocr_cascade_stages())
        assert _labels(ai_service._ocr_cascade_stages(preferred="")) == default
        assert _labels(ai_service._ocr_cascade_stages(preferred=None)) == default
        assert _labels(ai_service._ocr_cascade_stages(preferred="not-a-real-model")) == default

    def test_every_public_choice_key_maps_to_a_real_stage_label(self):
        # server.OCR_MODEL_CHOICES (frontend-facing) and
        # ai_service.OCR_MODEL_PREFERENCE_LABELS (backend routing) must stay
        # in sync -- every non-"auto" tenant-facing key must resolve to an
        # actual cascade stage, otherwise a saved preference would silently
        # do nothing.
        stage_labels = set(_labels(ai_service._ocr_cascade_stages()))
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
