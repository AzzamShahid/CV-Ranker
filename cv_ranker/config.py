import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Local configuration only. Never override environment values already provided
# by a process, CI secret manager, or hosting environment.
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=False)


def _provider_default() -> str:
    return os.getenv("CVR_LLM_PROVIDER", "ollama").strip().lower()


def default_ui_provider() -> str:
    """The .env preference for the initial UI selection, not a model choice."""
    return _provider_default()



@dataclass(frozen=True)
class Settings:
    # Resolved from the *selected* provider after initialization. The UI never
    # supplies this argument; both actual model IDs live only in .env.
    # Retain explicit Python/CLI overrides for existing automation scripts.
    model_name: str | None = None
    llm_provider: str = field(default_factory=_provider_default)
    openrouter_model: str = field(default_factory=lambda: os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite").strip())
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "qwen2.5:3b").strip())
    ollama_base_url: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip())
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "embeddinggemma-2:latest").strip())
    embedding_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "180")))
    embedding_batch_size: int = field(default_factory=lambda: int(os.getenv("EMBEDDING_BATCH_SIZE", "16")))
    # Conservative defaults for multi-CV runs; .env may override for known
    # provider capacity. This interval is NOT an OpenRouter quota guarantee.
    openrouter_request_interval_seconds: float = field(default_factory=lambda: float(os.getenv("OPENROUTER_REQUEST_INTERVAL_SECONDS", "6")))
    openrouter_retry_delay_seconds: float = field(default_factory=lambda: float(os.getenv("OPENROUTER_RETRY_DELAY_SECONDS", "15")))
    openrouter_max_retry_after_seconds: float = field(default_factory=lambda: float(os.getenv("OPENROUTER_MAX_RETRY_AFTER_SECONDS", "120")))
    # Zero disables the application-level transport ceiling (the provider's
    # own request and credit limits still apply). An explicit positive .env
    # value remains a per-run safety override; resume can continue batches.
    openrouter_max_requests_per_run: int = field(default_factory=lambda: int(os.getenv("OPENROUTER_MAX_REQUESTS_PER_RUN", "0")))
    # Hard ceiling across the initial CV assessment and every Resume of the
    # same frozen JD/CV checkpoint. JD extraction has its own separate calls.
    openrouter_max_requests_per_assessment: int = field(default_factory=lambda: int(
        os.getenv("OPENROUTER_MAX_REQUESTS_PER_ASSESSMENT", "128")))
    openrouter_api_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""), repr=False)
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_response_format: str = "json_schema"
    yake_top_k: int = 40
    yake_max_ngram: int = 3
    yake_dedup_threshold: float = 0.90
    # Sufficient headroom for multi-discipline JDs; never silently discard
    # explicit source criteria to fit a small model's preferred batch size.
    # Candidate assessment still uses bounded batches and cloud request caps.
    max_requirements: int = 100
    assessment_batch_size: int = 20
    second_look_unmatched: bool = True
    focused_abbreviation_retry: bool = True
    # The V4 API keeps its explicit opt-in for backward compatibility. The UI
    # enables this tightly scoped source check by default for interactive runs.
    exact_initialism_guard: bool = False
    approved_aliases_path: str | None = None
    llm_type_review: bool = False
    eligibility_policy_path: str | None = None
    llm_retries: int = 2
    ollama_num_ctx: int = 8192
    ollama_num_predict: int = 2048
    ollama_keep_alive: str = "15m"
    ollama_timeout_seconds: float = 180.0
    seed: int = 42

    def __post_init__(self) -> None:
        if self.llm_provider not in ("ollama", "openrouter"):
            raise ValueError("llm_provider must be 'ollama' or 'openrouter'")
        if not self.openrouter_model:
            raise ValueError("OPENROUTER_MODEL must not be empty in .env")
        if not self.ollama_model:
            raise ValueError("OLLAMA_MODEL must not be empty in .env")
        if not self.ollama_base_url:
            raise ValueError("OLLAMA_BASE_URL must not be empty in .env")
        if not self.embedding_model:
            raise ValueError("EMBEDDING_MODEL must not be empty in .env")
        if self.embedding_timeout_seconds <= 0 or self.embedding_batch_size < 1:
            raise ValueError("Embedding timeout/batch settings must be positive")
        if (self.openrouter_request_interval_seconds < 0 or
                self.openrouter_retry_delay_seconds < 0 or
                self.openrouter_max_retry_after_seconds <= 0 or
                self.openrouter_max_requests_per_run < 0 or
                self.openrouter_max_requests_per_assessment < 1):
            raise ValueError("OpenRouter pacing/retry settings are invalid")
        if self.model_name is None:
            object.__setattr__(self, "model_name", (
                self.openrouter_model if self.llm_provider == "openrouter" else self.ollama_model
            ))
        if self.openrouter_response_format not in ("json_schema", "json_object"):
            raise ValueError("openrouter_response_format must be 'json_schema' or 'json_object'")
        if self.llm_provider == "openrouter" and not self.openrouter_api_key.strip():
            raise ValueError("OPENROUTER_API_KEY is missing. Set it in your local .env file or environment.")
        if self.openrouter_base_url != "https://openrouter.ai/api/v1":
            raise ValueError("Unrecognized OpenRouter endpoint; use the official HTTPS API URL")
        if not self.model_name.strip():
            raise ValueError("model_name must not be empty")
        if self.yake_top_k < 1:
            raise ValueError("yake_top_k must be >= 1")
        if self.yake_max_ngram < 1:
            raise ValueError("yake_max_ngram must be >= 1")
        if not 0.0 <= self.yake_dedup_threshold <= 1.0:
            raise ValueError("yake_dedup_threshold must be between 0 and 1")
        if self.max_requirements < 1:
            raise ValueError("max_requirements must be >= 1")
        if self.assessment_batch_size < 1:
            raise ValueError("assessment_batch_size must be >= 1")
        if self.llm_retries < 0:
            raise ValueError("llm_retries must be >= 0")
        if self.ollama_num_ctx < 2048:
            raise ValueError("ollama_num_ctx must be >= 2048")
        if self.ollama_num_predict < 1 or self.ollama_num_predict >= self.ollama_num_ctx:
            raise ValueError("ollama_num_predict must be >= 1 and smaller than ollama_num_ctx")
        if self.ollama_timeout_seconds <= 0:
            raise ValueError("ollama_timeout_seconds must be > 0")
