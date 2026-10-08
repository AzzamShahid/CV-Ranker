from typing import TypeVar

from pydantic import BaseModel

from .config import Settings


T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


def estimate_tokens(text: str) -> int:
    """Conservative local-model context estimate; avoids silent Ollama truncation."""
    return int(len(text or "") / 3.5) + 1


class StructuredLLM:
    def __init__(self, settings: Settings):
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:
            raise LLMError(
                "langchain-ollama is not installed. Run: pip install -r requirements.txt"
            ) from exc

        self.settings = settings
        self.disabled_reason: str | None = None
        self.model = ChatOllama(
            model=settings.model_name,
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
