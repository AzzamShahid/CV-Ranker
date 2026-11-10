"""The CLI/UI use the environment-owned embedding model by default."""
from inspect import signature
from pathlib import Path
from cv_ranker.semantic.embedding import OllamaEmbeddingGemma
from cv_ranker.semantic.integration import run_shadow_retrieval


def test_embedding_client_uses_installed_latest_tag():
    client = OllamaEmbeddingGemma(model_digest="sha-test")
    assert client.model == "embeddinggemma-2:latest"
    assert "embeddinggemma-2:latest" in client.fingerprint


def test_default_integrated_model_matches_client():
    assert signature(run_shadow_retrieval).parameters["model"].default == "embeddinggemma-2:latest"


def test_shadow_cli_and_preflight_defaults_match():
    project_root = Path(__file__).resolve().parents[1]
    shadow = (project_root / 'scripts/phase7g_shadow.py').read_text(encoding='utf-8')
    preflight = (project_root / 'scripts/phase7g_embedding_preflight.py').read_text(encoding='utf-8')
    assert '"--embedding-model", default=None' in shadow
    assert '"--model", default=settings.embedding_model' in preflight
    assert '"--url", default=settings.ollama_base_url' in preflight
    assert 'EMBEDDING_MODEL=embeddinggemma-2:latest' in (project_root / '.env.example').read_text()
