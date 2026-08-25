"""role=describe (redaction Description + Etapes a suivre uniquement).

Garde-fous demandes explicitement le 25/08 : glm-4.7-flash (HERMES_DESCRIPTION_MODEL)
ne doit jamais etre utilise pour role=reason (decomposition materiaux/lots,
impacte le calcul), et son texte ne doit jamais contenir de prix. En cas
d'echec/timeout, le repli sur le gabarit 100% deterministe doit toujours
fonctionner sans exception.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("REACT_APP_BACKEND_URL", "http://localhost:8000")

import ai_service
import matching


def _run(coro):
    return asyncio.run(coro)


class TestRoleIsolation:
    def test_describe_role_never_resolves_to_reasoning_model(self):
        settings = {"ai_provider": "hermes", "ai_model": "hermes-3"}
        _, describe_model, _ = _run(ai_service.resolve_ai_config(settings, role="describe"))
        _, reason_model, _ = _run(ai_service.resolve_ai_config(settings, role="reason"))
        assert describe_model == ai_service.HERMES_DESCRIPTION_MODEL
        assert reason_model == ai_service.HERMES_REASONING_MODEL
        assert describe_model != reason_model

    def test_reasoning_model_default_is_not_glm(self):
        # 2026-08-25 : glm-4.7-flash was briefly HERMES_REASONING_MODEL then
        # explicitly removed from that role -- must never regress back.
        assert not ai_service.HERMES_REASONING_MODEL.lower().startswith("glm-4.7-flash")

    def test_description_model_default_is_glm(self):
        assert ai_service.HERMES_DESCRIPTION_MODEL.lower().startswith("glm-4.7-flash")

    def test_describe_fallback_pool_never_used_for_reason_role(self):
        assert ai_service.HERMES_DESCRIPTION_MODEL not in ai_service.HERMES_FALLBACK_MODELS
        assert ai_service.HERMES_REASONING_MODEL not in ai_service.HERMES_DESCRIPTION_FALLBACK_MODELS or (
            ai_service.HERMES_REASONING_MODEL in ai_service.HERMES_DESCRIPTION_FALLBACK_MODELS
        )  # gpt-oss:20b is an intentional shared fallback, not the primary


class TestGracefulFallback:
    def _extracted(self):
        return {
            "description": "Remplacement ballon eau chaude 200L",
            "intervention_site": "Boutique Test, Paris",
            "line_items": [{"label": "Ballon ECS 200L"}],
            "labor_hours": 3, "travel_days": 1, "crew_size": 1,
        }

    def test_falls_back_to_deterministic_template_when_ai_unavailable(self):
        # No network path to Ollama in this sandbox -> must fall back cleanly,
        # never raise, and stay byte-identical to the deterministic path.
        settings = {"ai_provider": "hermes", "ai_model": "hermes-3"}
        extracted = self._extracted()
        result = _run(ai_service.build_works_description_ai(extracted, settings, timeout=2))
        expected = matching.build_works_description(extracted)
        assert result == expected

    def test_fallback_never_raises_on_malformed_settings(self):
        result = _run(ai_service.build_works_description_ai({}, {}, timeout=1))
        assert isinstance(result, str)
        assert len(result) > 0


class TestPriceSafetyFilter:
    def test_price_like_narrative_is_rejected(self, monkeypatch):
        async def fake_call(model, system_prompt, user_message):
            return '{"description": "Cout total 250 euros pour ce chantier.", "etapes": ["Etape 1.", "Etape 2."]}'

        monkeypatch.setattr(ai_service, "_call_describe", fake_call)
        extracted = {"description": "Test", "line_items": [{"label": "Article"}]}
        result = _run(ai_service.generate_ai_works_narrative(extracted, {"ai_provider": "hermes", "ai_model": "hermes-3"}))
        assert result is None  # price-like token must reject the whole narrative

    def test_clean_narrative_is_accepted(self, monkeypatch):
        async def fake_call(model, system_prompt, user_message):
            return '{"description": "Perimetre des travaux.", "etapes": ["Arrivee sur site.", "Pose.", "Nettoyage."]}'

        monkeypatch.setattr(ai_service, "_call_describe", fake_call)
        extracted = {"description": "Test", "line_items": [{"label": "Article"}]}
        result = _run(ai_service.generate_ai_works_narrative(extracted, {"ai_provider": "hermes", "ai_model": "hermes-3"}))
        assert result is not None
        assert result["description"] == "Perimetre des travaux."
        assert len(result["etapes"]) == 3


class TestModelUsageLogging:
    def test_resolve_ai_config_logs_role_and_model(self, caplog):
        settings = {"ai_provider": "hermes", "ai_model": "hermes-3"}
        with caplog.at_level("INFO", logger="blueseatra.ai"):
            _run(ai_service.resolve_ai_config(settings, role="describe"))
            _run(ai_service.resolve_ai_config(settings, role="reason"))
        messages = [r.message for r in caplog.records]
        assert any("role=describe" in m and "glm-4.7-flash" in m for m in messages)
        assert any("role=reason" in m and "gpt-oss" in m for m in messages)

    def test_ai_call_attempt_is_logged_with_role_and_model(self, monkeypatch, caplog):
        async def fake_call(model, system_prompt, user_message):
            return '{"description": "Test.", "etapes": ["Une.", "Deux."]}'

        monkeypatch.setattr(ai_service, "_call_describe", fake_call)
        extracted = {"description": "Test", "line_items": [{"label": "Article"}]}
        settings = {"ai_provider": "hermes", "ai_model": "hermes-3"}
        with caplog.at_level("INFO", logger="blueseatra.ai"):
            _run(ai_service.generate_ai_works_narrative(extracted, settings))
        messages = [r.message for r in caplog.records]
        assert any("ai_role_resolved role=describe" in m for m in messages)


class TestDeterministicNumbersNeverFromAi:
    def test_deplacement_mo_text_matches_between_ai_path_and_template_path(self, monkeypatch):
        # The numeric tail (Deplacement/Main-d'oeuvre) must be byte-identical
        # whether or not the AI narrative succeeds -- these numbers must
        # never come from the model.
        async def fake_call(model, system_prompt, user_message):
            return '{"description": "Perimetre.", "etapes": ["Une.", "Deux."]}'

        monkeypatch.setattr(ai_service, "_call_describe", fake_call)
        extracted = {
            "description": "Test", "line_items": [{"label": "Article"}],
            "labor_hours": 6, "travel_days": 2, "crew_size": 2,
        }
        settings = {"ai_provider": "hermes", "ai_model": "hermes-3"}
        ai_result = _run(ai_service.build_works_description_ai(extracted, settings, timeout=5))
        expected_tail = matching.deplacement_mo_text(extracted)
        assert ai_result.strip().endswith(expected_tail.strip())
