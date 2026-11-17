"""Safe per-criterion technical failure classification and operator next action.

These descriptions are *not* candidate verdicts and never affect score. They
only summarize available execution facts without publishing CV text or model
responses. Avoid guessing transport/citation failure from absence of an S ID.
"""
from __future__ import annotations


def classify_failure(*, interruption: str | None,
                     rejected_model_ids: list[str],
                     selected_ids: list[str],
                     cited_review_ids: list[str]) -> dict:
    detail = (interruption or "").casefold()
    if "429" in detail or "rate limit" in detail:
        code = "PROVIDER_RATE_LIMIT"
        action = "Wait for provider cooldown or request budget before authorized retry."
    elif "503" in detail or "502" in detail:
        code = "PROVIDER_UNAVAILABLE"
        action = "Retry only after provider recovery within the existing attempt limit."
    elif "timeout" in detail or "network" in detail:
        code = "PROVIDER_TRANSPORT"
        action = "Inspect provider connectivity and remaining request budget."
    elif "outputtruncated" in detail or "token limit" in detail:
        code = "OUTPUT_TRUNCATED"
        action = "Reduce criteria per batch or reserve more output tokens within approved limits."
    elif "structuredresponse" in detail or "structured json" in detail:
        code = "MODEL_SCHEMA_INVALID"
        action = "Use a bounded schema correction on the failed requirement only."
    elif "context budget" in detail:
        code = "CONTEXT_OVERFLOW"
        action = "Repack requirements with original linked evidence; disclose omitted S IDs."
    elif "budget" in detail:
        code = "REQUEST_BUDGET_EXHAUSTED"
        action = "Keep verified siblings; obtain authorization before further provider calls."
    elif rejected_model_ids:
        code = "REJECTED_MODEL_CITATION"
        action = "Inspect rejected original S IDs and search for materially different relevant passages."
    elif interruption:
        code = "PROVIDER_REQUEST_FAILED"
        action = "Inspect sanitized provider error and run configuration before retry."
    else:
        code = "SOURCE_VALIDATION_INCOMPLETE"
        action = "Review source relevance and correction history; do not repeat identical evidence blindly."
    return {
        "failure_code": code,
        "next_useful_action": action,
        "rejected_model_ids": list(dict.fromkeys(rejected_model_ids)),
        "selected_source_ids": list(dict.fromkeys(selected_ids)),
        "review_source_ids_not_verified": list(dict.fromkeys(cited_review_ids)),
        "technical_not_candidate_failure": True,
    }
