from typing import cast

from .schemas import CandidateResult, EvaluationMode, RequirementAssessment, ValidatedRequirement


def _validate_coverage_contract(
    requirements: list[ValidatedRequirement],
    assessments: list[RequirementAssessment],
) -> None:
    """Enforce exactly one status per frozen JD requirement at the score boundary.

    This is intentionally independent of assessor validation. A duplicate,
    missing or invented assessment must never distort the ranking percentage.
    """
    frozen_ids = [item.requirement_id for item in requirements]
    assessed_ids = [item.requirement_id for item in assessments]
    if len(frozen_ids) != len(set(frozen_ids)):
        raise ValueError("Duplicate frozen requirement ID: ranking is unsafe")
    if len(assessed_ids) != len(set(assessed_ids)):
        raise ValueError("Duplicate assessment requirement ID: ranking is unsafe")
    missing = sorted(set(frozen_ids) - set(assessed_ids))
    unknown = sorted(set(assessed_ids) - set(frozen_ids))
    if missing or unknown:
        raise ValueError(f"Incomplete assessment contract: missing={missing}, unexpected={unknown}")


def _coverage_for_ids(
    ids: set[str],
    assessments: list[RequirementAssessment],
) -> tuple[float | None, int, int]:
    total = len(ids)
    if total == 0:
        return None, 0, 0
    matched = sum(
        1
        for item in assessments
        if item.requirement_id in ids and item.status == "matched"
    )
    return round((matched / total) * 100, 2), matched, total


def score_candidate(
    *,
    candidate_name: str,
    requirements: list[ValidatedRequirement],
    assessments: list[RequirementAssessment],
    evaluation_mode: str,
    errors: list[str],
    candidate_source: str = "",
) -> CandidateResult:
    _validate_coverage_contract(requirements, assessments)
    unverified = sorted(a.requirement_id for a in assessments
                        if a.assessment_state == "unverified")
    required_ids = {r.requirement_id for r in requirements if r.priority == "required"}
    preferred_ids = {r.requirement_id for r in requirements if r.priority == "preferred"}
    unknown_ids = {r.requirement_id for r in requirements if r.priority == "unknown"}

    required_score, matched_required, total_required = _coverage_for_ids(
        required_ids, assessments
    )
    preferred_score, matched_preferred, total_preferred = _coverage_for_ids(
        preferred_ids, assessments
    )
    unknown_score, matched_unknown, total_unknown = _coverage_for_ids(
        unknown_ids, assessments
    )

    if required_ids:
        primary_ids = required_ids
        score_basis = "explicit required requirements"
    elif unknown_ids:
        primary_ids = unknown_ids
        score_basis = "unknown-priority requirements (no explicit required requirements detected)"
    elif preferred_ids:
        primary_ids = preferred_ids
        score_basis = "preferred-only requirements (no required/unknown requirements detected)"
    else:
        primary_ids = set()
        score_basis = "no scoreable requirements"

    primary_score, matched_primary, total_primary = _coverage_for_ids(
        primary_ids, assessments
    )

    if unverified:
        # Keep known successes and every frozen denominator for diagnosis, but
        # publish NO percentage/rank while any assessment is technically
        # unverified. A provider/schema failure is not a CV skill failure.
        primary_score = required_score = preferred_score = unknown_score = None
        score_basis += " · incomplete source/model assessment"
        errors = list(errors) + [
            "Ranking withheld: technical assessment incomplete for " + ", ".join(unverified)
        ]

    allowed_modes = {"llm_assessed", "mixed", "fallback_exact", "failed"}
    mode = cast(
        EvaluationMode,
        evaluation_mode if evaluation_mode in allowed_modes else "mixed",
    )

    return CandidateResult(
        candidate_name=candidate_name,
        candidate_source=candidate_source,
        primary_score=primary_score,
        matched_primary=matched_primary,
        total_primary=total_primary,
        required_score=required_score,
        matched_required=matched_required,
        total_required=total_required,
        preferred_score=preferred_score,
        matched_preferred=matched_preferred,
        total_preferred=total_preferred,
        unknown_score=unknown_score,
        matched_unknown=matched_unknown,
        total_unknown=total_unknown,
        score_basis=score_basis,
        evaluation_mode="failed" if unverified else mode,
        assessments=assessments,
        errors=errors,
    )


def _ranking_key(item: CandidateResult) -> tuple:
    """The sole source of candidate ordering for backend and UI/export."""
    if item.primary_score is None:
        return (1, 0.0, 0.0, item.candidate_name.casefold(), item.candidate_source.casefold())
    return (0, -(item.primary_score or 0.0),
            -(item.preferred_score or 0.0),
            item.candidate_name.casefold(), item.candidate_source.casefold())


def assign_ranks(candidates: list[CandidateResult]) -> list[CandidateResult]:
    successful = [c for c in candidates if c.primary_score is not None]
    failed = [c for c in candidates if c.primary_score is None]

    successful.sort(key=_ranking_key)
    previous_score: tuple[float, float] | None = None
    previous_rank = 0
    for position, candidate in enumerate(successful, start=1):
        score = (candidate.primary_score or 0.0, candidate.preferred_score or 0.0)
        if previous_score is None or score != previous_score:
            previous_rank = position
            previous_score = score
        candidate.rank = previous_rank

    failed.sort(key=_ranking_key)
    return successful + failed
