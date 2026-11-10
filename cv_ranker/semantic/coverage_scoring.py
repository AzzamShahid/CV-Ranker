"""Phase 7G verified-capability coverage; reporting only, not candidate ranking.

THIS MODULE DOES NOT judge the semantic truth of a claim. Only feed it capability
relationships that an independent verifier has checked against original source
text and the preserved JD constraints. It rejects unknown citations and prevents
unreviewed LLM proposals from earning positive functional coverage.

Cosine similarity, cross-encoder logits, lexical rank and embedding model outputs
are deliberately absent from this scoring contract.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Literal

from pydantic import Field, model_validator

from ..schemas import CandidateResult, StrictModel, ValidatedRequirement


Relationship = Literal["direct", "transferable", "related_only", "not_evidenced", "uncertain"]
Verification = Literal["verified", "rejected", "unreviewed"]
ConstraintStatus = Literal["satisfied", "unresolved", "not_satisfied"]
CapabilityOrigin = Literal["explicit", "search_hint"]
ParentStatus = Literal[
    "direct_supported", "functionally_supported", "partially_supported",
    "related_only", "not_evidenced", "needs_review", "not_evaluated",
]


class CapabilityPlan(StrictModel):
    """One JD-derived capability, under an EXISTING frozen requirement."""
    requirement_id: str = Field(min_length=1)
    capability_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    origin: CapabilityOrigin = "explicit"


class AdjudicatedCapability(StrictModel):
    """Evidence relationship determined by Qwen, subsequently audited.

    verification='verified' MUST be assigned by a trusted, independent verifier,
    not simply copied from the model's own response.
    """
    capability_id: str = Field(min_length=1)
    relationship: Relationship
    evidence_ids: list[str] = Field(default_factory=list)
    verification: Verification = "unreviewed"
    constraint_status: ConstraintStatus = "unresolved"

    @model_validator(mode="after")
    def check_local_structure(self):
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("Duplicate evidence ID in capability decision")
        if self.relationship in {"direct", "transferable"} and not self.evidence_ids:
            raise ValueError("Positive relationship requires original evidence IDs")
        return self


class RequirementCoverage(StrictModel):
    requirement_id: str
    priority: Literal["required", "preferred", "unknown"]
    state: ParentStatus
    explicit_capabilities: int
    direct_capabilities: int
    transferable_capabilities: int
    unresolved_capabilities: int
    missing_capabilities: int


class VerifiedCoverageReport(StrictModel):
    mode: Literal["verified_functional_coverage_report_only"] = "verified_functional_coverage_report_only"
    candidate_name: str
    original_primary_score: float | None
    frozen_required_count: int
    evaluated_required_count: int
    complete_direct_required: int
    complete_functional_required: int
    partial_required: int
    review_required: int
    # A requirement's decomposition must be complete to be in a valid aggregate.
    # These percentages are *requirement counts*, NOT candidate competence probabilities.
    verified_direct_requirement_coverage_pct: float | None
    verified_functional_requirement_coverage_pct: float | None
    requirements: list[RequirementCoverage]
    search_hints_excluded: int
    ranking_unchanged: Literal[True] = True


def score_verified_capability_coverage(
    *,
    candidate: CandidateResult,
    requirements: list[ValidatedRequirement],
    plan: list[CapabilityPlan],
    decisions: list[AdjudicatedCapability],
    admissible_source_ids: set[str],
) -> VerifiedCoverageReport:
    """Audit *verified* capability relationships into a separate coverage report.

    Does not mutate CandidateResult, override primary scores or rank candidates.
    Requires source allowlist for exactly the candidate being assessed.
    Missing capability outcomes are a hard error, not a zero or invented negative.
    Search-only hints never count in numerator or denominator.
    """
    if candidate.primary_score is None or candidate.evaluation_mode == "failed":
        raise ValueError("Cannot report verified coverage for an incomplete or failed candidate assessment")
    if not isinstance(admissible_source_ids, set):
        raise TypeError("Caller must supply the candidate-scoped admissible source ID set")
    frozen = {r.requirement_id: r for r in requirements}
    if len(frozen) != len(requirements):
        raise ValueError("Duplicate frozen JD requirement ID")
    if len({p.capability_id for p in plan}) != len(plan):
        raise ValueError("Duplicate capability plan ID")
    if any(p.requirement_id not in frozen for p in plan):
        raise ValueError("Capability linked to a nonexistent frozen JD requirement")
    decision_map = {d.capability_id: d for d in decisions}
    if len(decision_map) != len(decisions):
        raise ValueError("Duplicate capability verdict ID")
    plan_ids = {p.capability_id for p in plan}
    unknown = set(decision_map) - plan_ids
    if unknown:
        raise ValueError(f"Unexpected capability verdicts: {sorted(unknown)}")
    missing = plan_ids - set(decision_map)
    if missing:
        raise ValueError(f"Incomplete capability assessment: missing={sorted(missing)}")
    for outcome in decisions:
        foreign = set(outcome.evidence_ids) - admissible_source_ids
        if foreign:
            raise ValueError(f"Unknown or inadmissible source IDs for {outcome.capability_id}: {sorted(foreign)}")

    grouped: dict[str, list[CapabilityPlan]] = defaultdict(list)
    for item in plan:
        if item.origin == "explicit":
            grouped[item.requirement_id].append(item)

    requirement_rows: list[RequirementCoverage] = []
    for req in requirements:
        children = grouped[req.requirement_id]
        if not children:
            requirement_rows.append(RequirementCoverage(
                requirement_id=req.requirement_id, priority=req.priority,
                state="not_evaluated", explicit_capabilities=0, direct_capabilities=0,
                transferable_capabilities=0, unresolved_capabilities=0,
                missing_capabilities=0,
            ))
            continue
        direct = transfer = unresolved = related = absent = 0
        for child in children:
            outcome = decision_map[child.capability_id]
            positive = outcome.relationship in {"direct", "transferable"}
            credited = (positive and outcome.verification == "verified"
                        and outcome.constraint_status == "satisfied")
            if credited:
                if outcome.relationship == "direct":
                    direct += 1
                else:
                    transfer += 1
            elif (outcome.verification == "unreviewed" or
                  (positive and outcome.constraint_status == "unresolved") or
                  outcome.relationship == "uncertain"):
                unresolved += 1
            elif outcome.relationship == "related_only" and outcome.verification == "verified":
                related += 1
            else:
                absent += 1
        n = len(children)
        if direct == n:
            state: ParentStatus = "direct_supported"
        elif direct + transfer == n:
            state = "functionally_supported"
        elif direct + transfer:
            state = "partially_supported"
        elif unresolved:
            state = "needs_review"
        elif related:
            state = "related_only"
        else:
            state = "not_evidenced"
        requirement_rows.append(RequirementCoverage(
            requirement_id=req.requirement_id, priority=req.priority, state=state,
            explicit_capabilities=n, direct_capabilities=direct,
            transferable_capabilities=transfer, unresolved_capabilities=unresolved,
            missing_capabilities=absent + related,
        ))

    required = [r for r in requirement_rows if r.priority == "required"]
    ready = bool(required) and all(
        r.state != "not_evaluated" and r.unresolved_capabilities == 0
        for r in required
    )
    direct_count = sum(r.state == "direct_supported" for r in required)
    functional_count = sum(r.state in {"direct_supported", "functionally_supported"} for r in required)
    return VerifiedCoverageReport(
        candidate_name=candidate.candidate_name,
        original_primary_score=candidate.primary_score,
        frozen_required_count=len(required),
        evaluated_required_count=sum(r.state != "not_evaluated" for r in required),
        complete_direct_required=direct_count,
        complete_functional_required=functional_count,
        partial_required=sum(r.state == "partially_supported" for r in required),
        review_required=sum(r.state == "needs_review" or r.unresolved_capabilities > 0 for r in required),
        verified_direct_requirement_coverage_pct=(round(direct_count / len(required) * 100, 2) if ready else None),
        verified_functional_requirement_coverage_pct=(round(functional_count / len(required) * 100, 2) if ready else None),
        requirements=requirement_rows,
        search_hints_excluded=sum(p.origin == "search_hint" for p in plan),
    )
