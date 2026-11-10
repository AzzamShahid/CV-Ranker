"""Optional one-click Phase 7G semantic review for the supervisor dashboard.

All model calls happen while uploaded temporary CVs still exist, because the
citation auditor must reopen their original source files. Results are read-only.
This module intentionally does not import Streamlit or change ranking policy.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from cv_ranker.schemas import RankingReport
from cv_ranker.semantic.embedding import EmbeddingError
from cv_ranker.llm import LLMError
from cv_ranker.semantic.transferability import TransferabilityShadowReport


def semantic_failure_message(exc: Exception) -> str:
    """Safe, actionable errors without CV excerpts or API secrets."""
    if isinstance(exc, EmbeddingError):
        detail = str(exc)
        if "not found in Ollama" in detail:
            return "Embedding model not installed. Check EMBEDDING_MODEL in .env and pull that Ollama model."
        if "dimension" in detail.casefold():
            return "Embedding dimensions disagree. Check EMBEDDING_MODEL and the local Ollama model digest."
        if "Cannot reach Ollama" in detail:
            return "Local Ollama is unreachable. Check that Ollama is running and OLLAMA_BASE_URL in .env. Cloud assessment still needs local embeddings when cross-check is enabled."
        if "HTTP" in detail:
            return "Local Ollama embedding endpoint returned HTTP failure. Verify the configured embedding model and service health."
        return "Local embedding failed. Inspect model/timeout/batch settings in .env and Ollama health."
    if isinstance(exc, LLMError):
        if "429" in str(exc):
            return "Cloud LLM HTTP 429 rate limit. Retry budget exhausted: wait for quota reset or select Local (Ollama); baseline scores remain available."
        return "Assessment LLM call failed. Check provider availability, quota/credits, and model selection in .env."
    return f"Semantic review unavailable ({type(exc).__name__}); original candidate results remain available."


def run_semantic_review(
    ranker: Any,
    report: RankingReport,
    *,
    cache_path: str | Path,
    top_k: int = 8,
    embedding_model: str | None = None,
    retrieval_callback: Callable[[dict[str, Any]], None] | None = None,
) -> TransferabilityShadowReport:
    """Propose source-audited relationships, never modify ``report``.

    Raises for missing Ollama, network errors, invalid identities, or malformed
    outputs. The Streamlit caller keeps the original result on these failures.
    """
    if not report.requirements or not report.candidates:
        raise ValueError("A completed ranking with JD requirements and candidates is required")
    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    # Duplicate display names make a visual comparison ambiguous even if the
    # internal candidate IDs are unique. Do not accidentally attach results
    # for one uploaded CV to another candidate's evidence panel.
    names = [c.candidate_name for c in report.candidates]
    if len(set(names)) != len(names):
        raise ValueError("Duplicate candidate display names; rename the CV files before semantic review")

    before = report.model_dump()
    plan = ranker.plan_jd_capabilities(report)
    model = (embedding_model or
             getattr(getattr(ranker, 'settings', None), 'embedding_model', 'embeddinggemma-2:latest'))
    retrieval = ranker.run_semantic_shadow(
        report, cache_path=cache_path, top_k=top_k,
        model=model, capability_plan=plan,
    )
    # Persist independently successful LOCAL search before the LLM makes any
    # further calls. A later OpenRouter 429 must not erase working retrieval.
    if retrieval_callback is not None:
        retrieval_callback(retrieval)
    proposals = ranker.assess_transferability_shadow(report, retrieval)
    if not isinstance(proposals, TransferabilityShadowReport):
        proposals = TransferabilityShadowReport.model_validate(proposals)
    if not proposals.scoring_unchanged:
        raise ValueError("Semantic result attempted to change original ranking")
    if report.model_dump() != before:
        raise ValueError("Semantic stage mutated the baseline ranking")
    if proposals.candidate_count != len(report.candidates):
        raise ValueError("Incomplete semantic candidate count")
    actual = {c.candidate_name: c for c in report.candidates}
    if len(proposals.candidates) != len(actual):
        raise ValueError("Semantic output candidate list mismatch")
    used: set[str] = set()
    valid_req_ids = {r.requirement_id for r in report.requirements}
    for candidate in proposals.candidates:
        if candidate.candidate_name in used or candidate.candidate_name not in actual:
            raise ValueError("Semantic output contains foreign/duplicate candidate")
        used.add(candidate.candidate_name)
        baseline = actual[candidate.candidate_name]
        if candidate.original_rank != baseline.rank or candidate.original_primary_score != baseline.primary_score:
            raise ValueError("Semantic result mismatches original candidate rank or score")
        if any(a.requirement_id not in valid_req_ids for a in candidate.assessments):
            raise ValueError("Semantic result references a foreign requirement")
    return proposals


def semantic_candidate_rows(
    report: RankingReport,
    semantic: TransferabilityShadowReport | dict[str, Any] | None,
    candidate_name: str,
) -> list[dict[str, Any]]:
    """Candidate-scoped, presentation-only proposals with explicit provenance.

    A missing/incomplete semantic report creates no guessed skill results.
    All percentages, ranks, and required-score fields are deliberately absent.
    """
    if semantic is None:
        return []
    if not isinstance(semantic, TransferabilityShadowReport):
        semantic = TransferabilityShadowReport.model_validate(semantic)
    if not semantic.scoring_unchanged:
        return []
    originals = {r.requirement_id: r for r in report.requirements}
    candidates = [c for c in semantic.candidates if c.candidate_name == candidate_name]
    if len(candidates) != 1:
        return []
    candidate = candidates[0]
    rows: list[dict[str, Any]] = []
    for item in candidate.assessments:
        requirement = originals.get(item.requirement_id)
        if requirement is None:
            continue
        rows.append({
            "Requirement ID": item.requirement_id,
            "Requirement": requirement.name,
            "Capability ID": item.capability_id,
            "Priority": requirement.priority.title(),
            "Relationship": item.relationship,
            "Source IDs": ", ".join(c.segment_id for c in item.citations),
            "Evidence": " | ".join(c.exact_quote for c in item.citations),
            "Citations": [{"segment_id": c.segment_id, "text": c.exact_quote}
                          for c in item.citations],
            "Explanation": item.explanation,
            "Review flags": ", ".join(item.relationship_consistency_flags),
            "Citation audit": item.citation_audit,
            "Needs review": True,
            "Functional overlap review": item.functional_review_candidate,
            "Functional review note": item.functional_review_note,
        })
    return rows


def semantic_summary(semantic: TransferabilityShadowReport | dict[str, Any] | None) -> dict[str, int]:
    """Counts of *proposals*, not competencies or awarded requirements."""
    if semantic is None:
        return {}
    if not isinstance(semantic, TransferabilityShadowReport):
        semantic = TransferabilityShadowReport.model_validate(semantic)
    counts = {k: 0 for k in ("direct", "transferable", "related_only", "uncertain", "not_evidenced")}
    for candidate in semantic.candidates:
        for item in candidate.assessments:
            counts[item.relationship] += 1
    return counts
