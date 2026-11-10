import json
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from typing import TypeVar

from pydantic import BaseModel

from .config import Settings


T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class ModelOutputTruncatedError(LLMError):
    """The same completion budget cannot finish the current response batch."""


class ModelStructuredResponseError(LLMError):
    """The provider responded, but repeated JSON/schema validation failed.

    Callers can try smaller assessment groups. A transport, quota or access
    problem must not be mistaken for a reason to create more cloud requests.
    """


class OpenRouterHTTPError(LLMError):
    """An HTTP status without the response body (which may contain CV data)."""

    def __init__(self, status_code: int, retry_after_seconds: float | None = None):
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        advice = {
            400: "request or schema rejected",
            401: "API key unauthorized",
            402: "insufficient API credits",
            403: "provider access forbidden",
            404: "model or endpoint unavailable",
            422: "request or schema rejected",
            429: "rate limit reached; retry later or change provider/model",
            503: "provider temporarily unavailable",
            529: "provider overloaded",
        }.get(status_code, "provider request failed")
        super().__init__(f"OpenRouter HTTP {status_code}: {advice}")


def _retry_after_seconds(headers) -> float | None:
    """Read only the public delay hint; never retain provider error bodies."""
    raw = headers.get("Retry-After") if headers is not None else None
    if not raw:
        return None
    try:
        if str(raw).strip().isdigit():
            return max(0.0, float(raw))
        when = parsedate_to_datetime(str(raw))
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())
    except (ValueError, TypeError, OverflowError):
        return None


def estimate_tokens(text: str) -> int:
    """Conservative context estimate; avoids silent model truncation."""
    return int(len(text or "") / 3.5) + 1


def _unique_json_object_pairs(pairs: list[tuple[str, object]]) -> dict:
    """Do not silently keep the last value for a repeated JSON field.

    In ID-keyed model output, two copies of R018 must never be accepted as
    one source-grounded decision simply because JSON parsing overwrote one.
    This applies to all structured-output schemas, not a particular JD.
    """
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("structured response contains a duplicate JSON property")
        result[key] = value
    return result


class StructuredLLM:
    # A small flat schema is more reliable for local 3B-scale model calls.
    supports_compact_transferability = True
    def __new__(cls, settings: Settings | None = None):
        if cls is StructuredLLM and settings is not None and settings.llm_provider == "openrouter":
            return super().__new__(OpenRouterStructuredLLM)
        return super().__new__(cls)

    def __init__(self, settings: Settings):
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:
            raise LLMError(
                "langchain-ollama is not installed. Run: pip install -r requirements.txt"
            ) from exc

        self.settings = settings
        self.disabled_reason: str | None = None
        self.logical_calls = 0
        self.http_attempts = 0
        self.token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.model = ChatOllama(
            model=settings.model_name,
            base_url=settings.ollama_base_url,
            temperature=0,
            seed=settings.seed,
            num_ctx=settings.ollama_num_ctx,
            num_predict=settings.ollama_num_predict,
            keep_alive=settings.ollama_keep_alive,
            client_kwargs={"timeout": settings.ollama_timeout_seconds},
        )

    def prompt_fits(self, system_prompt: str, user_prompt: str) -> bool:
        prompt_tokens = estimate_tokens(system_prompt) + estimate_tokens(user_prompt) + 300
        return prompt_tokens + self.settings.ollama_num_predict <= self.settings.ollama_num_ctx

    def invoke_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
    ) -> T:
        if self.disabled_reason:
            raise LLMError(f"LLM circuit is disabled for this run: {self.disabled_reason}")

        if not self.prompt_fits(system_prompt, user_prompt):
            prompt_tokens = estimate_tokens(system_prompt) + estimate_tokens(user_prompt) + 300
            raise LLMError(
                f"Context budget exceeded: ~{prompt_tokens} prompt tokens + "
                f"{self.settings.ollama_num_predict} output tokens > num_ctx={self.settings.ollama_num_ctx}. "
                "Prompt was not sent, so no silent truncation occurred."
            )
        # Count only requests that pass the preflight budget check. Some
        # diagnostics/tests construct a lightweight client with __new__ and
        # intentionally skip __init__, so counters must initialize lazily.
        self.logical_calls = getattr(self, "logical_calls", 0) + 1

        try:
            from langchain_core.prompts import ChatPromptTemplate
        except ImportError as exc:
            raise LLMError("langchain-core is not installed.") from exc

        structured_model = self.model.with_structured_output(
            schema,
            method="json_schema",
            include_raw=True,
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{task}"),
            ]
        )
        chain = prompt | structured_model

        last_error: Exception | str | None = None
        attempts = self.settings.llm_retries + 1
        correction = ""
        for attempt in range(attempts):
            task = user_prompt + correction
            if not self.prompt_fits(system_prompt, task):
                prompt_tokens = estimate_tokens(system_prompt) + estimate_tokens(task) + 300
                raise LLMError(
                    f"Context budget exceeded after structured-output correction: ~{prompt_tokens} prompt tokens + "
                    f"{self.settings.ollama_num_predict} output tokens > num_ctx={self.settings.ollama_num_ctx}. "
                    "Prompt was not sent, so no silent truncation occurred."
                )
            try:
                self.http_attempts = getattr(self, "http_attempts", 0) + 1
                result = chain.invoke({"task": task})
                parsed = result.get("parsed") if isinstance(result, dict) else result
                parsing_error = result.get("parsing_error") if isinstance(result, dict) else None
                if parsed is not None and parsing_error is None:
                    if isinstance(parsed, schema):
                        return parsed
                    return schema.model_validate(parsed)
                last_error = parsing_error or "Structured output was empty."
            except Exception as exc:  # network/model/runtime/parsing
                last_error = exc

            if attempt < attempts - 1:
                error_text = str(last_error)
                if len(error_text) > 1000:
                    error_text = error_text[:1000] + "..."
                correction = (
                    "\n\nCORRECTION: The previous structured response failed validation/parsing. "
                    "Return data conforming exactly to the supplied schema. "
                    f"Validation/runtime detail: {error_text}"
                )

        error_text = str(last_error)
        lower = error_text.casefold()
        if any(token in lower for token in (
            "connection", "connect", "timeout", "timed out", "refused",
            "ollama", "httpx", "socket",
        )):
            self.disabled_reason = error_text[:500]
        raise LLMError(f"Structured LLM call failed after {attempts} attempt(s): {last_error}")


class OpenRouterStructuredLLM(StructuredLLM):
    """Provider-compatible structured JSON calls, preserving all Pydantic validators.

    All CV/JD passages are sent to the configured remote provider. No automatic
    fallback to another provider, and no exposure of credentials in error output.
    """

    supports_compact_transferability = True
    prefer_flat_focused_judgment = True

    def __init__(self, settings: Settings):
        self.settings = settings
        self.disabled_reason: str | None = None
        self.logical_calls = 0
        self.http_attempts = 0
        self.token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.model = None  # No local ChatOllama instance for OpenRouter requests.
        self._last_request_started: float | None = None
        self.http_429_count = 0
        self.last_retry_after_seconds: float | None = None
        self._schema_mode_rejected = False

    def _post_chat(self, payload: dict) -> dict:
        ceiling = self.settings.openrouter_max_requests_per_run
        if ceiling > 0 and self.http_attempts >= ceiling:
            self.disabled_reason = (
                f"OpenRouter run-wide HTTP request budget reached ({ceiling}). "
                "No additional remote CV data was sent; adjust the explicit "
                "OPENROUTER_MAX_REQUESTS_PER_RUN setting or rerun the remaining CVs.")
            raise LLMError(self.disabled_reason)
        # Many assessment phases share one client. Pace *all* calls, not just
        # retries, so a large CV batch does not instantly exhaust cloud RPM.
        now = time.monotonic()
        if self._last_request_started is not None:
            remaining = (self.settings.openrouter_request_interval_seconds -
                         (now - self._last_request_started))
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_started = time.monotonic()
        endpoint = self.settings.openrouter_base_url + "/chat/completions"
        request = Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + self.settings.openrouter_api_key,
                "Content-Type": "application/json",
                "X-OpenRouter-Title": "CV Ranker Phase 7G",
            },
            method="POST",
        )
        self.http_attempts = getattr(self, "http_attempts", 0) + 1
        progress = getattr(self, "progress_callback", None)
        if callable(progress):
            progress(f"Cloud API request {self.http_attempts}: awaiting the model response "
                     f"(timeout {self.settings.ollama_timeout_seconds:g}s)")
        try:
            with urlopen(request, timeout=self.settings.ollama_timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
                usage = data.get("usage", {}) if isinstance(data, dict) else {}
                if isinstance(usage, dict):
                    for field in self.token_usage:
                        count = usage.get(field)
                        if type(count) is int and count >= 0:
                            self.token_usage[field] += count
                if callable(progress):
                    progress(f"Cloud API request {self.http_attempts}: response received; "
                             "checking structured evidence")
                return data
        except HTTPError as exc:
            # Never print request headers or body; these contain secrets/CV text.
            retry_after = _retry_after_seconds(exc.headers)
            if exc.code == 429:
                self.http_429_count += 1
                if retry_after is not None:
                    self.last_retry_after_seconds = max(
                        self.last_retry_after_seconds or 0.0, retry_after)
            if callable(progress):
                progress(f"Cloud API request {self.http_attempts}: HTTP {exc.code}; "
                         "applying the bounded provider retry policy")
            raise OpenRouterHTTPError(exc.code, retry_after) from None
        except (URLError, TimeoutError, OSError) as exc:
            if callable(progress):
                progress(f"Cloud API request {self.http_attempts}: network/timeout error; "
                         "preserving completed decisions")
            raise LLMError(f"OpenRouter network/timeout error ({type(exc).__name__})") from None
        except (ValueError, UnicodeError) as exc:
            raise LLMError("OpenRouter returned an invalid JSON API envelope") from None

    def invoke_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
    ) -> T:
        if self.disabled_reason:
            raise LLMError(f"LLM circuit is disabled for this run: {self.disabled_reason}")

        attempts = self.settings.llm_retries + 1
        correction = ""
        last_error = "No valid response"
        response_mode = ("json_object" if getattr(self, "_schema_mode_rejected", False)
                         else self.settings.openrouter_response_format)
        structured_failure = False
        for attempt in range(attempts):
            task = user_prompt + correction
            if not self.prompt_fits(system_prompt, task):
                prompt_tokens = estimate_tokens(system_prompt) + estimate_tokens(task) + 300
                raise LLMError(
                    f"Context budget exceeded: ~{prompt_tokens} prompt tokens + "
                    f"{self.settings.ollama_num_predict} output tokens > "
                    f"configured budget={self.settings.ollama_num_ctx}. No data was sent."
                )
            if attempt == 0:
                self.logical_calls = getattr(self, "logical_calls", 0) + 1
            payload = {
                "model": self.settings.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": task},
                ],
                "temperature": 0,
                "max_tokens": self.settings.ollama_num_predict,
                "stream": False,
            }
            if response_mode == "json_schema":
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema.__name__,
                        "strict": True,
                        "schema": schema.model_json_schema(),
                    },
                }
                payload["provider"] = {"require_parameters": True}
            else:
                payload["response_format"] = {"type": "json_object"}
                payload["provider"] = {"require_parameters": True}
            try:
                result = self._post_chat(payload)
                # OpenRouter may return a provider error *inside* an HTTP 200
                # envelope when generation already began. Treat its canonical
                # typed rate-limit/credit error exactly like a real HTTP error,
                # never as a malformed JSON model answer requiring a prompt
                # correction. Do not copy provider body text into logs.
                envelope_error = (result.get("error") if isinstance(result, dict)
                                  else None)
                choices = result.get("choices") if isinstance(result, dict) else None
                if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                    if choices[0].get("finish_reason") == "error":
                        envelope_error = choices[0].get("error") or envelope_error
                if isinstance(envelope_error, dict):
                    metadata = envelope_error.get("metadata")
                    error_type = (metadata.get("error_type") if isinstance(metadata, dict)
                                  else None)
                    try:
                        error_code = int(envelope_error.get("code"))
                    except (ValueError, TypeError):
                        error_code = None
                    if error_type == "rate_limit_exceeded" or error_code == 429:
                        self.http_429_count += 1
                        raise OpenRouterHTTPError(429)
                    if error_type == "payment_required" or error_code == 402:
                        raise OpenRouterHTTPError(402)
                    if error_type == "authentication" or error_code == 401:
                        raise OpenRouterHTTPError(401)
                    if error_type == "permission_denied" or error_code == 403:
                        raise OpenRouterHTTPError(403)
                    raise LLMError("OpenRouter provider returned a non-retryable model error")
                choice = result["choices"][0]
                if choice.get("finish_reason") == "length":
                    raise ModelOutputTruncatedError(
                        f"OpenRouter model output truncated at max_tokens={self.settings.ollama_num_predict}; "
                        "split the requirement batch")
                message = choice["message"]
                content = message.get("content")
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("missing structured response content")
                parsed = schema.model_validate(json.loads(
                    content, object_pairs_hook=_unique_json_object_pairs))
                return parsed
            except OpenRouterHTTPError as exc:
                last_error = str(exc)
                if exc.status_code in {400, 422} and response_mode == "json_schema" and attempt < attempts - 1:
                    # Some routes reject strict schemas. JSON-object mode
                    # still requires local Pydantic validation before credit.
                    self._schema_mode_rejected = True
                    response_mode = "json_object"
                    correction = "\n\nReturn one valid JSON object matching every required field."
                    continue
                if exc.status_code in {408, 429, 500, 502, 503, 524, 529} and attempt < attempts - 1:
                    # Honor HTTP Retry-After (with a safe cap), otherwise use
                    # slower exponential backoff. A 429 is not fixed by a 1.5s
                    # immediate burst from the next assessment row.
                    backoff = self.settings.openrouter_retry_delay_seconds * (2 ** attempt)
                    delay = max(backoff, exc.retry_after_seconds or 0.0)
                    if delay > min(self.settings.openrouter_max_retry_after_seconds, 60.0):
                        # Never shorten a provider-specified Retry-After. Defer
                        # the full wait to the session recovery scheduler.
                        self.disabled_reason = (
                            f"OpenRouter HTTP {exc.status_code}: waiting for provider retry window")
                        break
                    time.sleep(delay)
                    continue
                if exc.status_code in {400, 401, 402, 403, 404, 408, 422, 429,
                                       500, 502, 503, 524, 529}:
                    # A recurring provider failure must not be multiplied by
                    # the remaining CV count within this assessment attempt.
                    self.disabled_reason = last_error
                break
            except ModelOutputTruncatedError:
                # Retrying the same oversized response cannot increase the
                # output budget. The caller must reduce batch size.
                raise
            except LLMError as exc:
                last_error = str(exc)
                # A temporary connection failure may clear on the next call;
                # it must not permanently poison all downstream checks.
                if attempt < attempts - 1:
                    time.sleep(min(1.5 * (2 ** attempt), 3.0))
                    continue
                self.disabled_reason = last_error
                break
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                # Never repeat model-completion text or sensitive source fragments
                # in terminal logs or remote repair prompts.
                last_error = (f"model output was truncated at max_tokens={self.settings.ollama_num_predict}; "
                              "increase the output token budget"
                              if str(exc) == "truncated response (max_tokens reached)"
                              else f"{type(exc).__name__}: structured JSON did not validate")
                structured_failure = True
                if attempt < attempts - 1:
                    # Sending an identical schema request after a malformed
                    # provider completion often yields the same invalid JSON.
                    # Change the retry to JSON-object mode while keeping local
                    # Pydantic/source validation mandatory. This changes the
                    # *strategy*, not the number of permitted HTTP attempts.
                    if response_mode == "json_schema":
                        response_mode = "json_object"
                    correction = (
                        "\n\nCORRECTION: Return exactly one JSON object matching "
                        "the required response schema; no markdown or additional prose."
                    )
        error = (f"OpenRouter structured call failed after at most {attempts} "
                 f"attempt(s): {last_error}")
        if structured_failure and not self.disabled_reason:
            raise ModelStructuredResponseError(error)
        raise LLMError(error)
