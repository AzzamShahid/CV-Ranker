"""The UI chooses a provider; the .env owns both model IDs and Ollama URL."""

from pathlib import Path

from pydantic import BaseModel

from cv_ranker.config import Settings, default_ui_provider
from cv_ranker.llm import OpenRouterStructuredLLM, StructuredLLM


class Reply(BaseModel):
    ok: bool


def _configure_models(monkeypatch):
    monkeypatch.setenv("CVR_LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_MODEL", "test/cloud-from-env")
    monkeypatch.setenv("OLLAMA_MODEL", "test-local-from-env:3b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:22555")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-placeholder")


def test_switching_provider_resolves_the_correct_env_model_without_leakage(monkeypatch):
    _configure_models(monkeypatch)
    assert default_ui_provider() == "openrouter"
    cloud = Settings(llm_provider="openrouter")
    local = Settings(llm_provider="ollama")
    assert cloud.model_name == "test/cloud-from-env"
    assert local.model_name == "test-local-from-env:3b"
    assert cloud.openrouter_model == local.openrouter_model == "test/cloud-from-env"
    assert cloud.ollama_model == local.ollama_model == "test-local-from-env:3b"
    assert local.ollama_base_url == "http://127.0.0.1:22555"


def test_local_provider_does_not_require_a_cloud_key(monkeypatch):
    _configure_models(monkeypatch)
    monkeypatch.delenv("OPENROUTER_API_KEY")
    assert Settings(llm_provider="ollama").model_name == "test-local-from-env:3b"


def test_local_dispatch_uses_ollama_model_and_url_from_env(monkeypatch):
    _configure_models(monkeypatch)
    captured = {}
    from langchain_core.runnables import RunnableLambda

    class FakeChatOllama:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def with_structured_output(self, schema, method, include_raw):
            captured["schema"] = schema
            captured["method"] = method
            captured["include_raw"] = include_raw
            return RunnableLambda(lambda messages: {"parsed": Reply(ok=True), "parsing_error": None})

    monkeypatch.setattr("langchain_ollama.ChatOllama", FakeChatOllama)
    settings = Settings(llm_provider="ollama")
    llm = StructuredLLM(settings)
    assert type(llm) is StructuredLLM
    assert captured["model"] == "test-local-from-env:3b"
    assert captured["base_url"] == "http://127.0.0.1:22555"
    assert captured["temperature"] == 0
    assert llm.settings.llm_provider == "ollama"
    response = llm.invoke_structured(system_prompt="Return JSON", user_prompt="Synthetic local check", schema=Reply)
    assert response.ok is True
    assert captured["schema"] is Reply
    assert captured["method"] == "json_schema"
    assert captured["include_raw"] is True


def test_cloud_dispatch_uses_openrouter_model_and_does_not_initialize_ollama(monkeypatch):
    _configure_models(monkeypatch)

    def forbid_local_model(**kwargs):
        raise AssertionError("Cloud selection must not initialize a local assessment LLM")

    monkeypatch.setattr("langchain_ollama.ChatOllama", forbid_local_model)
    llm = StructuredLLM(Settings(llm_provider="openrouter"))
    assert isinstance(llm, OpenRouterStructuredLLM)
    recorded = []

    def fake_post(payload):
        recorded.append(payload)
        return {"choices": [{"finish_reason": "stop", "message": {"content": '{"ok": true}'}}]}

    monkeypatch.setattr(llm, "_post_chat", fake_post)
    response = llm.invoke_structured(system_prompt="Return JSON", user_prompt="Synthetic check", schema=Reply)
    assert response.ok is True
    assert recorded[0]["model"] == "test/cloud-from-env"
    assert recorded[0]["messages"][1]["content"] == "Synthetic check"
    assert recorded[0]["temperature"] == 0


def test_streamlit_exposes_only_provider_selection_not_model_entry():
    source = (Path(__file__).resolve().parents[1] / "cv_ranker/ui/dashboard.py").read_text(encoding="utf-8")
    assert 'st.radio(\n            "AI provider"' in source
    assert '"Cloud (OpenRouter)": "openrouter"' in source
    assert '"Local (Ollama)": "ollama"' in source
    assert "model_name=configured.model_name" not in source
    assert "from `.env`" in source
    assert "switching does not silently rescore an existing report" in source


def test_both_model_names_are_documented_in_env_example():
    content = (Path(__file__).resolve().parents[1] / ".env.example").read_text(encoding="utf-8")
    assert "OPENROUTER_MODEL=" in content
    assert "OLLAMA_MODEL=" in content
    assert "OLLAMA_BASE_URL=" in content
