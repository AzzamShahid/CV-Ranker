"""User-authorized continuous recovery must obey provider wait hints."""

import pytest
from pydantic import BaseModel

from cv_ranker.config import Settings
from cv_ranker.llm import (LLMError, OpenRouterHTTPError,
                           OpenRouterStructuredLLM)


def test_zero_request_cap_is_valid_and_disables_local_run_ceiling(monkeypatch):
    settings = Settings(llm_provider="openrouter", openrouter_api_key="offline-test",
                        openrouter_max_requests_per_run=0)
    client = OpenRouterStructuredLLM(settings)
    client.http_attempts = 999
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
        def read(self):
            return b'{"choices": [{"message": {"content": "{}"}}]}'
    monkeypatch.setattr("cv_ranker.llm.urlopen", lambda *a, **kw: Response())
    assert client._post_chat({"model": "test"})["choices"]
    assert client.http_attempts == 1000


def test_positive_env_cap_remains_an_explicit_override(monkeypatch):
    settings = Settings(llm_provider="openrouter", openrouter_api_key="offline-test",
                        openrouter_max_requests_per_run=5)
    client = OpenRouterStructuredLLM(settings)
    client.http_attempts = 5
    with pytest.raises(LLMError, match="budget reached"):
        client._post_chat({"model": "test"})


def test_long_retry_after_is_delegated_to_nonblocking_resume(monkeypatch):
    settings = Settings(llm_provider="openrouter", openrouter_api_key="offline-test",
                        openrouter_max_requests_per_run=0, llm_retries=2)
    client = OpenRouterStructuredLLM(settings)
    class Answer(BaseModel):
        answer: str

    calls = []
    def reject(*args):
        calls.append(1)
        client.http_429_count += 1
        client.last_retry_after_seconds = 3600.0
        raise OpenRouterHTTPError(429, 3600.0)

    monkeypatch.setattr(client, "_post_chat", reject)
    monkeypatch.setattr("cv_ranker.llm.time.sleep", lambda *_:
                        pytest.fail("A long Retry-After must not block the UI thread"))
    with pytest.raises(LLMError, match="429"):
        client.invoke_structured(system_prompt="Answer briefly.",
                                 user_prompt="Return answer.", schema=Answer)
    assert len(calls) == 1
    assert client.last_retry_after_seconds == 3600.0
    assert "429" in client.disabled_reason


def test_typed_rate_limit_inside_http_200_envelope_enters_429_recovery(monkeypatch):
    settings = Settings(llm_provider="openrouter", openrouter_api_key="offline-test",
                        openrouter_max_requests_per_run=0, llm_retries=0)
    client = OpenRouterStructuredLLM(settings)
    class Answer(BaseModel):
        answer: str

    monkeypatch.setattr(client, "_post_chat", lambda *_: {
        "choices": [{"finish_reason": "error", "error": {
            "code": 429, "message": "do not echo private provider payload",
            "metadata": {"error_type": "rate_limit_exceeded"}}}]})
    with pytest.raises(LLMError, match="429") as observed:
        client.invoke_structured(system_prompt="Answer briefly.",
                                 user_prompt="Return answer.", schema=Answer)
    assert "private provider payload" not in str(observed.value)
    assert client.http_429_count == 1
    assert "429" in client.disabled_reason
