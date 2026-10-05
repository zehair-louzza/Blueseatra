"""Routage GPT-OSS texte (05/10/2026), sans détourner l'OCR/vision."""
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("REACT_APP_BACKEND_URL", "http://127.0.0.1:1")
import ai_service as ai


def _defaults_in_clean_env(**extra):
    """Valeurs à l'import sans aucune variable HERMES_* (défauts du code)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("HERMES_")}
    env.update(extra)
    code = (
        "import json, ai_service as ai; print(json.dumps({"
        "'extract': ai.HERMES_EXTRACT_MODEL, 's1': ai.HERMES_STRUCTURING_MODEL_1,"
        "'s3': ai.HERMES_STRUCTURING_MODEL_3, 'effort': ai.HERMES_STRUCTURING_EFFORT,"
        "'reason_effort': ai.HERMES_REASONING_EFFORT, 'vision': ai.HERMES_VISION_MODEL,"
        "'fallback': ai.HERMES_FALLBACK_MODELS, 'timeouts': list(ai._STRUCTURING_CASCADE_TIMEOUTS),"
        "'stages': [list(s) for s in ai._structuring_cascade_stages()]}))"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env,
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_code_defaults_text_gpt_oss_low_vision_unchanged():
    d = _defaults_in_clean_env()
    assert d["extract"] == "gpt-oss:20b"
    assert d["s1"] == "gpt-oss:20b"
    assert d["s3"] == "hermes3"
    assert d["effort"] == "low"
    assert d["reason_effort"] == "medium"  # rôle reason inchangé
    assert d["vision"] == "qwen2.5vl:7b"
    assert "qwen2.5:7b" not in d["fallback"]
    assert d["fallback"][-2:] == ["hermes3", "hermes-3"]
    assert d["timeouts"] == [600.0, 420.0, 300.0]
    assert [s[:2] for s in d["stages"]] == [
        ["GPT-OSS-20B", "gpt-oss:20b"],
        ["GPT-OSS-20B (compact)", "gpt-oss:20b"],
        ["Hermes-3", "hermes3"],
    ]


def test_vision_never_inherits_text_reasoning_model():
    d = _defaults_in_clean_env(HERMES_REASONING_MODEL="gpt-oss:20b")
    assert d["vision"] == "qwen2.5vl:7b"


def test_invalid_structuring_effort_falls_back_to_low():
    assert _defaults_in_clean_env(HERMES_STRUCTURING_EFFORT="max")["effort"] == "low"


def test_stage_timeouts_follow_position_not_label(monkeypatch):
    monkeypatch.setattr(ai, "HERMES_STRUCTURING_MODEL_1", "mon-modele:7b")
    monkeypatch.setattr(ai, "HERMES_STRUCTURING_MODEL_3", "hermes-3:latest")
    monkeypatch.setattr(ai, "_STRUCTURING_CASCADE_TIMEOUTS", (611.0, 422.0, 333.0))
    assert ai._structuring_cascade_stages() == [
        ("mon-modele:7b", "mon-modele:7b", 611.0),
        ("mon-modele:7b (compact)", "mon-modele:7b", 422.0),
        ("Hermes-3", "hermes-3:latest", 333.0),
    ]


def test_explicit_gpt_text_preserves_vision_route():
    settings = {"ai_provider": "hermes", "ai_model": "gpt-oss:20b"}
    assert asyncio.run(ai.resolve_ai_config(settings, role="extract"))[1] == "gpt-oss:20b"
    assert asyncio.run(ai.resolve_ai_config(settings, role="file"))[1] == ai.HERMES_VISION_MODEL
    assert asyncio.run(ai.resolve_ai_config(settings, role="vision"))[1] == ai.HERMES_VISION_MODEL


def test_generic_integrated_engine_uses_gpt_for_extraction(monkeypatch):
    monkeypatch.setattr(ai, "HERMES_EXTRACT_MODEL", "gpt-oss:20b")
    result = asyncio.run(ai.resolve_ai_config(
        {"ai_provider": "hermes", "ai_model": "hermes-3:latest"}, role="extract"))
    assert result[1] == "gpt-oss:20b"


def _cascade_setup(monkeypatch, fail_first=0):
    calls = []

    async def fake(model, system_prompt, user_message, **kwargs):
        calls.append(dict(model=model, system_prompt=system_prompt, **kwargs))
        if len(calls) <= fail_first:
            raise RuntimeError("ReadTimeout simulé")
        return '{"ok":true}'

    monkeypatch.setattr(ai, "IA_VIA_HERMES", True)
    monkeypatch.setattr(ai, "HERMES_STRUCTURING_MODEL_1", "gpt-oss:20b")
    monkeypatch.setattr(ai, "HERMES_STRUCTURING_MODEL_3", "hermes3")
    monkeypatch.setattr(ai, "HERMES_STRUCTURING_EFFORT", "low")
    monkeypatch.setattr(ai, "_hermes_chat", fake)
    return calls


def test_cascade_sends_low_effort_without_brevity_hint(monkeypatch):
    calls = _cascade_setup(monkeypatch)
    _, label = asyncio.run(ai._call_structuring_cascade("system", "input"))
    assert label == "GPT-OSS-20B"
    assert calls[0]["model"] == "gpt-oss:20b"
    assert calls[0]["reasoning_effort"] == "low"
    assert calls[0]["system_prompt"] == "system"  # pas de consigne booléenne


def test_cascade_explicit_hermes3_fallback_without_reasoning(monkeypatch):
    calls = _cascade_setup(monkeypatch, fail_first=2)
    _, label = asyncio.run(ai._call_structuring_cascade("system", "full", user_message_compact="compact"))
    assert label == "Hermes-3"
    assert [c["model"] for c in calls] == ["gpt-oss:20b", "gpt-oss:20b", "hermes3"]
    assert [c["reasoning_effort"] for c in calls] == ["low", "low", None]


def test_extract_role_uses_low_and_reason_role_keeps_its_effort(monkeypatch):
    seen = []

    async def fake(model, system_prompt, user_message, **kwargs):
        seen.append((kwargs["role"], model, kwargs["reasoning_effort"]))
        return "ok"

    monkeypatch.setattr(ai, "IA_VIA_HERMES", True)
    monkeypatch.setattr(ai, "HERMES_STRUCTURING_EFFORT", "low")
    monkeypatch.setattr(ai, "HERMES_REASONING_EFFORT", "medium")
    monkeypatch.setattr(ai, "_hermes_chat", fake)
    asyncio.run(ai._call_hermes_ollama("gpt-oss:20b", "s", "u", role="extract"))
    asyncio.run(ai._call_hermes_ollama("gpt-oss:20b", "s", "u", role="reason"))
    assert seen == [("extract", "gpt-oss:20b", "low"), ("reason", "gpt-oss:20b", "medium")]


def test_extract_role_falls_back_to_hermes3_without_effort(monkeypatch):
    seen = []

    async def fake(model, system_prompt, user_message, **kwargs):
        seen.append((model, kwargs["reasoning_effort"]))
        if model.startswith("gpt-oss"):
            raise RuntimeError("échec simulé")
        return "ok"

    monkeypatch.setattr(ai, "IA_VIA_HERMES", True)
    monkeypatch.setattr(ai, "HERMES_FALLBACK_MODELS", ["gpt-oss:20b", "gpt-oss:20b", "hermes3", "hermes-3"])
    monkeypatch.setattr(ai, "_hermes_chat", fake)
    assert asyncio.run(ai._call_hermes_ollama("gpt-oss:20b", "s", "u", role="extract")) == "ok"
    assert seen == [("gpt-oss:20b", "low"), ("hermes3", None)]
