"""Verrouille les listes de modèles des réglages (Réglages > Intégrations >
Moteur IA) sur le contenu EXACT du VPS OVH -- relevé `ollama list` du
02/10/2026, fourni par l'utilisateur (« chaque modèle dans sa position ») :

    glm-4.7-flash:Q3_K_M        (LLM)
    gpt-oss:20b                  (LLM)
    glm-ocr:latest              (OCR/vision)
    qwen2.5vl:7b                (OCR/vision)
    qwen2.5:7b                  (LLM)
    maternion/LightOnOCR-2:1b   (OCR/vision)
    richardyoung/olmocr2:7b-q8  (OCR/vision)
    AuditAid/PaddleOCR-VL-1.6-0.9B:latest (OCR/vision)
    hermes-3:latest             (LLM)
    hermes3:latest              (LLM)

No network, no DB needed -- pure constant tests.
"""
import sys

sys.path.insert(0, "/app/backend")
import server  # noqa: E402


# `ollama list` du VPS, ordre exact (le même ID Ollama 4f6b83f30b62 apparaît
# sous deux tags distincts, affichés tous les deux à la demande de l'utilisateur).
VPS_LLM_MODELS = [
    "glm-4.7-flash:Q3_K_M",
    "gpt-oss:20b",
    "qwen2.5:7b",
    "hermes-3:latest",
    "hermes3:latest",
]

VPS_OCR_MODELS = [
    "glm-ocr:latest",
    "qwen2.5vl:7b",
    "maternion/LightOnOCR-2:1b",
    "richardyoung/olmocr2:7b-q8",
    "AuditAid/PaddleOCR-VL-1.6-0.9B:latest",
]


class TestProviderModelsMatchVps:
    def test_hermes_llm_models_in_exact_ollama_list_order(self):
        hermes = server.PROVIDER_MODELS["hermes"]
        locaux = [m for m in hermes if not m.startswith("mistral:")]
        assert locaux == VPS_LLM_MODELS

    def test_mistral_entries_kept_after_local_models(self):
        # « À part ceux de Mistral » : conservés à la suite des modèles du VPS.
        hermes = server.PROVIDER_MODELS["hermes"]
        assert hermes[len(VPS_LLM_MODELS):] == [
            "mistral:mistral-medium-latest",
            "mistral:mistral-large-latest",
            "mistral:mistral-small-latest",
        ]

    def test_cloud_providers_absent_from_settings(self):
        # 02/10/2026 : OpenAI / Gemini / Anthropic retirés des réglages --
        # leurs modèles n'existent pas sur le VPS (demande utilisateur).
        for absent in ("openai", "gemini", "anthropic"):
            assert absent not in server.PROVIDER_MODELS
            assert absent not in server.PROVIDER_LABELS

    def test_no_model_left_in_settings_that_is_not_on_the_vps(self):
        autorises = set(VPS_LLM_MODELS) | set(VPS_OCR_MODELS) | {"hermes-3"}  # hermes-3 = alias historique
        for provider, modeles in server.PROVIDER_MODELS.items():
            for m in modeles:
                # « mistral:<id> » (fournisseur hermes) et le fournisseur
                # mistral : API Mistral via Hermès, conservée à la demande.
                if m.startswith("mistral:") or provider in ("mistral", "opencode"):
                    continue   # opencode : 13 modèles OpenCode Free via Hermès (09/10/2026, demande utilisateur)
                assert m in autorises, f"{m} absent du VPS"

    def test_opencode_free_13_modeles_exacts(self):
        # https://opencode.ai/zen/v1/models, modèles gratuits, relevé du 09/10/2026.
        assert server.PROVIDER_MODELS["opencode"] == [
            "big-pickle", "jev-1.13-free", "exo-free", "muse-spark-1.3-contributor-free",
            "muse-spark-1.2-contributor-free", "mimo-v2.6-flash-free", "space-bunny-free",
            "longcat-2.5-preview-free", "step-5-preview-free", "ling-3.0-flash-fin-free",
            "nemotron-3-ultra-free", "nemotron-3.5-lightning-free", "ling-3.1-flash-free"]
        assert "opencode" in server.PROVIDER_LABELS

    def test_ocr_choices_follow_ollama_list_order(self):
        # Ordre du sélecteur « Modèle OCR préféré » = ordre `ollama list`
        # (l'entrée « auto », un mode et non un modèle, reste en 2e position).
        cles_sans_auto = [k for k in server.OCR_MODEL_CHOICES if k != "auto"]
        assert cles_sans_auto == ["glm-ocr", "qwen25vl", "lightonocr", "olmocr2", "paddleocr-vl"]


class TestModeleAliasesVersPasserelle:
    def test_noms_hermes_exacts_mappes_vers_nom_declare(self):
        # Les deux tags ollama de l'image 4f6b83f30b62 s'affichent tels quels
        # dans les réglages, mais la passerelle Hermès du VPS déclare
        # « hermes3 » (hermes/passerelle/config.yaml) : le nom envoyé sur le
        # réseau doit toujours être « hermes3 ».
        import ai_service
        for nom in ("hermes-3", "hermes3", "hermes-3:latest", "hermes3:latest"):
            assert ai_service.MODEL_ALIASES[nom] == "hermes3", nom
