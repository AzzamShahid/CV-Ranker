"""Private, session-scoped resume identities for interrupted CV assessments.

Only digests and validated assessment objects should be retained by the UI.
Neither document contents nor provider credentials belong in a cache key.
"""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from .build_info import BUILD_ID
from .config import Settings


_TRANSPORT_FIELDS = {
    "openrouter_api_key", "openrouter_request_interval_seconds",
    "openrouter_retry_delay_seconds", "openrouter_max_retry_after_seconds",
    "openrouter_max_requests_per_run", "openrouter_max_requests_per_assessment",
    "llm_retries",
    "approved_aliases_path", "eligibility_policy_path",
}

# Changes to this *general assessment pipeline*, not CSS or unrelated docs,
# invalidate prior in-session decisions even when local source edits are
# intentionally permitted without a release-manifest failure. No job, skill,
# person or named model is an assessment result baked into this fingerprint.
_ASSESSMENT_LOGIC_FILES = (
    "jd.py", "jd_coverage.py", "fallback.py", "requirement_typing.py", "documents.py", "segments.py",
    "assessment_clock.py", "failure_diagnostics.py", "source_subject_guard.py",
    "condition_review.py", "jd_expression.py", "source_snapshot.py", "operation_ledger.py",
    "retrieval_priorities.py", "assessor.py", "unified.py",
    "experience_validation.py", "qualification_validation.py",
    "compound_validation.py", "scoring.py", "weighted_scoring.py",
    "llm.py", "text_utils.py", "criteria_scope.py", "jd_review.py",
    "constraints.py", "evidence_bridge.py", "semantic/core.py",
    "semantic/integration.py", "semantic/adapters.py",
    "semantic/embedding.py", "pipeline.py", "schemas.py", "eligibility.py",
    "semantic/transferability.py", "semantic/decomposition.py",
    "semantic/relationship_consistency.py", "semantic/cache.py",
)


def assessment_logic_fingerprint(root: Path | None = None) -> str:
    """Hash source *bytes*, so changing local scoring code invalidates reuse.

    Unlike the signed distribution manifest, this is a cache identity, not an
    access control. Reading it afresh permits editing during a local session.
    Missing logic files fail closed instead of accepting stale results.
    """
    root = root or Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for name in _ASSESSMENT_LOGIC_FILES:
        digest.update(name.encode("utf-8") + b"\x00")
        digest.update(hashlib.sha256((root / name).read_bytes()).digest())
    return digest.hexdigest()


def candidate_resume_key(filename: str, content: bytes) -> str:
    """Bind a reused judgment to the exact uploaded filename and bytes."""
    digest = hashlib.sha256()
    digest.update(filename.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(content)
    return digest.hexdigest()


def candidate_resume_keys(items: list[tuple[str, bytes]]) -> list[str]:
    """Stable identities for upload slots, including intentional duplicates.

    Unique uploads retain their original content-bound key, preserving
    compatibility with previously saved checkpoints and existing CLI callers.
    The second occurrence of an identical file gets its own deterministic key.
    """
    seen: dict[str, int] = {}
    keys = []
    for name, content in items:
        base = candidate_resume_key(name, content)
        occurrence = seen.get(base, 0)
        seen[base] = occurrence + 1
        keys.append(base if occurrence == 0 else hashlib.sha256(
            f"{base}:{occurrence}".encode("utf-8")).hexdigest())
    return keys


def assessment_context_key(
    settings: Settings, *, jd_bytes: bytes,
    approved_aliases_bytes: bytes = b"", eligibility_policy_bytes: bytes = b"",
    use_llm: bool = True,
) -> str:
    """Reuse only same-version, same-JD, same-policy, same-model decisions.

    Transport timing and API key rotation may change between resume attempts
    without invalidating the original source-grounded judgment.
    """
    meaningful_settings = {
        name: value for name, value in asdict(settings).items()
        if name not in _TRANSPORT_FIELDS
    }
    payload = {
        "build_id": BUILD_ID,
        "assessment_logic_fingerprint": assessment_logic_fingerprint(),
        "use_llm": bool(use_llm),
        "settings": meaningful_settings,
        "jd": hashlib.sha256(jd_bytes).hexdigest(),
        "approved_aliases": hashlib.sha256(approved_aliases_bytes).hexdigest(),
        "eligibility_policy": hashlib.sha256(eligibility_policy_bytes).hexdigest(),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
