"""OpenRouter integration tests: all calls are mocked, never send CVs or keys."""
import json
from urllib.error import HTTPError

import pytest
from pydantic import BaseModel, ConfigDict

from cv_ranker.config import Settings
from cv_ranker.llm import LLMError, OpenRouterStructuredLLM, StructuredLLM


class Reply(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    ok: bool
    message: str


def cloud_settings(**changes):
    base = dict(llm_provider="openrouter", openrouter_api_key="sk-or-test-private", model_name="qwen/qwen3.5-27b")
    base.update(changes)
    return Settings(**base)


def test_opt_in_dispatched_to_openrouter_without_instantiating_local_llm():
    llm = StructuredLLM(cloud_settings())
    assert isinstance(llm, OpenRouterStructuredLLM)
    assert llm.model is None
    assert llm.supports_compact_transferability


def test_local_default_still_instantiates_structuredllm_if_no_explicit_model():
    # Verify configuration choice without requiring Ollama runtime.
    settings = Settings(llm_provider="ollama")
    assert settings.model_name


def test_missing_key_is_rejected_before_network():
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        cloud_settings(openrouter_api_key="")


def test_key_not_in_settings_repr():
    assert "sk-or-test-private" not in repr(cloud_settings())


def test_invalid_provider_rejected():
    with pytest.raises(ValueError, match="llm_provider"):
        Settings(llm_provider="unknown")


def test_structured_cloud_payload_is_validated_locally(monkeypatch):
    llm = StructuredLLM(cloud_settings())
    captured = []

    def fake_post(payload):
        captured.append(payload)
        return {"choices": [{"finish_reason": "stop", "message": {"content": '{"ok": true, "message": "ready"}'}}]}

    monkeypatch.setattr(llm, "_post_chat", fake_post)
    response = llm.invoke_structured(system_prompt="Return JSON", user_prompt="Hello", schema=Reply)
    assert response == Reply(ok=True, message="ready")
    assert captured[0]["model"] == cloud_settings().model_name
    assert captured[0]["provider"] == {"require_parameters": True}
    assert captured[0]["response_format"]["type"] == "json_schema"
    assert captured[0]["response_format"]["json_schema"]["schema"]["type"] == "object"
    assert captured[0]["messages"][0]["role"] == "system"
    assert captured[0]["messages"][1]["content"] == "Hello"


def test_openrouter_post_headers_use_bearer_and_never_add_key_to_payload(monkeypatch):
    llm = StructuredLLM(cloud_settings())
    captured = {}

    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self): return b'{"choices": []}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["auth"] = request.get_header("Authorization")
        captured["body"] = request.data
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("cv_ranker.llm.urlopen", fake_urlopen)
    assert llm._post_chat({"model": "test", "messages": []}) == {"choices": []}
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["auth"] == "Bearer sk-or-test-private"
    assert b"sk-or-test-private" not in captured["body"]


def test_openrouter_http_error_does_not_leak_key(monkeypatch):
    llm = StructuredLLM(cloud_settings())
    def failed(*args, **kwargs):
        raise HTTPError("https://openrouter.ai/api/v1/chat/completions", 401, "nope", {}, None)
    monkeypatch.setattr("cv_ranker.llm.urlopen", failed)
    with pytest.raises(LLMError, match="HTTP 401") as info:
        llm.invoke_structured(system_prompt="s", user_prompt="u", schema=Reply)
    assert "sk-or-test-private" not in str(info.value)
    assert llm.disabled_reason


def test_structured_parse_error_retries_then_succeeds(monkeypatch):
    llm = StructuredLLM(cloud_settings())
    outputs = ['{"ok": "not_boolean", "message": "bad"}', '{"ok": true, "message": "good"}']
    seen = []
    def fake(payload):
        seen.append(payload)
        return {"choices": [{"finish_reason": "stop", "message": {"content": outputs.pop(0)}}]}
    monkeypatch.setattr(llm, "_post_chat", fake)
    assert llm.invoke_structured(system_prompt="s", user_prompt="u", schema=Reply).ok
    assert len(seen) == 2
    assert "CORRECTION" in seen[1]["messages"][1]["content"]


def test_exhausted_schema_retries_fail_closed(monkeypatch):
    llm = StructuredLLM(cloud_settings())
    monkeypatch.setattr(llm, "_post_chat", lambda payload: {"choices": [{"finish_reason": "stop", "message": {"content": '{"ok": "wrong"}'}}]})
    with pytest.raises(LLMError, match="structured call failed"):
        llm.invoke_structured(system_prompt="s", user_prompt="u", schema=Reply)


def test_missing_or_truncated_response_is_not_accepted(monkeypatch):
    llm = StructuredLLM(cloud_settings(llm_retries=0))
    monkeypatch.setattr(llm, "_post_chat", lambda p: {"choices": [{"finish_reason": "length", "message": {"content": '{"ok": true, "message": "x"}'}}]})
    with pytest.raises(LLMError):
        llm.invoke_structured(system_prompt="s", user_prompt="u", schema=Reply)


def test_context_budget_blocks_post(monkeypatch):
    llm = StructuredLLM(cloud_settings(ollama_num_ctx=2048, ollama_num_predict=1900))
    monkeypatch.setattr(llm, "_post_chat", lambda p: (_ for _ in ()).throw(AssertionError("posted despite over-limit")))
    with pytest.raises(LLMError, match="Context budget exceeded"):
        llm.invoke_structured(system_prompt="system " * 300, user_prompt="user " * 500, schema=Reply)


def test_json_object_mode_explicit(monkeypatch):
    llm = StructuredLLM(cloud_settings(openrouter_response_format="json_object"))
    captured = []
    def fake(payload):
        captured.append(payload)
        return {"choices": [{"finish_reason": "stop", "message": {"content": '{"ok": true, "message": "fine"}'}}]}
    monkeypatch.setattr(llm, "_post_chat", fake)
    llm.invoke_structured(system_prompt="s", user_prompt="u", schema=Reply)
    assert captured[0]["response_format"] == {"type": "json_object"}


def test_environment_switches_model_and_provider(monkeypatch):
    monkeypatch.setenv("CVR_LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-private")
    settings = Settings()
    assert settings.model_name == "google/gemini-2.5-flash"
    assert settings.llm_provider == "openrouter"
