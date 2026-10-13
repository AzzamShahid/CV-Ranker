from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    model_name: str = "qwen2.5:3b"
    yake_top_k: int = 40
    yake_max_ngram: int = 3
    yake_dedup_threshold: float = 0.90
    max_requirements: int = 30
    assessment_batch_size: int = 20
    second_look_unmatched: bool = True
    focused_abbreviation_retry: bool = True
    exact_initialism_guard: bool = False
    approved_aliases_path: str | None = None
    llm_type_review: bool = False
    eligibility_policy_path: str | None = None
    llm_retries: int = 1
    ollama_num_ctx: int = 8192
    ollama_num_predict: int = 2048
    ollama_keep_alive: str = "15m"
    ollama_timeout_seconds: float = 180.0
    seed: int = 42

    def __post_init__(self) -> None:
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
