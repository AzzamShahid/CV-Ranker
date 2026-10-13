"""Optional HR-selected JD eligibility gates; screening claims, NOT employment decisions.

No policy supplied => no gates. An approval file records identity/rationale but
cannot authenticate that identity; integrate real RBAC in a later phase.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import Field, field_validator

from .schemas import CandidateResult, EligibilityCheck, StrictModel, ValidatedRequirement
from .text_utils import normalize_whitespace


class EligibilityGate(StrictModel):
    requirement: str = Field(min_length=1, max_length=300)
    reason: str = Field(min_length=8, max_length=500)

    @field_validator("requirement", "reason")
    @classmethod
    def strip_and_check(cls, value: str) -> str:
        clean = normalize_whitespace(value)
        if not clean or any(ord(c) < 32 for c in value):
            raise ValueError("Gate text must not contain blank/control fields")
        return clean


class EligibilityPolicy(StrictModel):
    schema_version: int = 1
    jd_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    reviewed_by: str = Field(min_length=2, max_length=120)
    gates: list[EligibilityGate] = Field(min_length=1, max_length=30)

    @field_validator("reviewed_by")
    @classmethod
    def reviewer(cls, value: str) -> str:
        value = normalize_whitespace(value)
        if len(value) < 2 or any(ord(ch) < 32 for ch in value):
            raise ValueError("Reviewer name is required")
        return value


def jd_source_sha256(jd_text: str) -> str:
    return hashlib.sha256(jd_text.encode("utf-8")).hexdigest()


def load_eligibility_policy(path: str | Path | None, *, jd_text: str,
                            requirements: list[ValidatedRequirement]
                            ) -> tuple[EligibilityPolicy | None, str | None]:
    if not path:
        return None, None
    raw = Path(path).read_bytes()
    if len(raw) > 64 * 1024:
        raise ValueError("Eligibility policy exceeds 64 KB")
    try:
        policy = EligibilityPolicy.model_validate_json(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid eligibility policy JSON: {exc}") from exc
    if policy.schema_version != 1:
        raise ValueError("Unsupported eligibility policy version")
    if policy.jd_sha256 != jd_source_sha256(jd_text):
        raise ValueError("Eligibility policy does not match the current JD content")
    frozen = {r.name.casefold(): r for r in requirements}
    if len(frozen) != len(requirements):
        raise ValueError("Duplicate frozen requirement names make eligibility gates ambiguous")
    seen = set()
    for gate in policy.gates:
        k = gate.requirement.casefold()
        if k in seen:
            raise ValueError(f"Duplicate eligibility gate: {gate.requirement!r}")
        seen.add(k)
        if k not in frozen:
            raise ValueError(f"Eligibility gate references an absent JD criterion: {gate.requirement!r}")
        if frozen[k].priority != "required":
            raise ValueError(f"Eligibility gate requires an employer-stated required criterion: {gate.requirement!r}")
    return policy, hashlib.sha256(raw).hexdigest()


def check_eligibility(*, candidate: CandidateResult,
                      requirements: list[ValidatedRequirement],
                      policy: EligibilityPolicy | None) -> EligibilityCheck:
    if candidate.primary_score is None:
        return EligibilityCheck(status="evaluation_failed", issues=["Candidate evaluation failed; no screening conclusion"])
    if policy is None:
        return EligibilityCheck(status="not_configured", issues=["No employer-reviewed eligibility gates supplied"])
    by_name = {r.name.casefold(): r for r in requirements}
    by_id = {a.requirement_id: a for a in candidate.assessments}
    issues = []
    gated_ids = []
    failures = []
    ambiguous = []
    for gate in policy.gates:
        requirement = by_name[gate.requirement.casefold()]
        gated_ids.append(requirement.requirement_id)
        assessment = by_id[requirement.requirement_id]
        if assessment.status == "not_matched":
            failures.append(requirement.name)
            issues.append(f"{requirement.name}: no matching CV evidence established for mandatory criterion")
        elif assessment.status == "uncertain":
            ambiguous.append(requirement.name)
            issues.append(f"{requirement.name}: claim needs human review")
        elif (requirement.constraint.kind in {"license", "eligibility"} or
              assessment.reviewed_alias_by is not None or
              (requirement.constraint.requires_review and
               not (assessment.compound_check is not None and
                    assessment.compound_check.outcome == "matched"))):
            ambiguous.append(requirement.name)
            issues.append(f"{requirement.name}: matched CV claim still needs employer/authority review")
    # Never declare somebody ineligible to work or eligible to practice;
    # distinguish unsatisfied *CV evidence* from actual legal eligibility.
    if failures:
        status = "criteria_unmet"
    elif ambiguous:
        status = "needs_review"
    else:
        status = "criteria_satisfied"
    return EligibilityCheck(status=status, gated_requirement_ids=gated_ids,
                            issues=issues, reviewed_by=policy.reviewed_by)
