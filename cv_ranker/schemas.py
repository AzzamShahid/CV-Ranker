from typing import Literal
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .build_info import BUILD_ID


Priority = Literal["required", "preferred", "unknown"]
AssessmentStatus = Literal["matched", "not_matched", "uncertain"]
EvaluationMode = Literal["llm_assessed", "mixed", "fallback_exact", "failed"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class YakeCandidate(StrictModel):
    keyword: str = Field(min_length=1)
    score: float


class JDRequirement(StrictModel):
    name: str = Field(min_length=1)
    priority: Priority
    evidence: str = Field(min_length=1)


class JDValidationResponse(StrictModel):
    requirements: list[JDRequirement]


RequirementKind = Literal["skill", "experience", "education", "certification", "license", "responsibility", "eligibility", "other"]
LogicalOperator = Literal["single", "any_of", "all_of", "complex"]
TypingOrigin = Literal["source_rules", "llm_suggestion", "manual_review_pending", "unclassified"]


class RequirementConstraint(StrictModel):
    kind: RequirementKind = "other"
    operator: LogicalOperator = "single"
    options: list[str] = Field(default_factory=list)
    minimum_years: float | None = Field(default=None, ge=0, le=100)
    subject: str | None = None
    degree_level: Literal["associate", "diploma", "bachelor", "master", "doctorate"] | None = None
    field_of_study: str | None = None
    source_line_numbers: list[int] = Field(default_factory=list)
    origin: TypingOrigin = "unclassified"
    requires_review: bool = True

    @model_validator(mode="after")
    def check_consistency(self):
        if self.minimum_years is not None and self.kind != "experience":
            raise ValueError("minimum_years may appear only on experience criteria")
        if (self.degree_level is not None or self.field_of_study is not None) and self.kind != "education":
            raise ValueError("degree attributes may appear only on education criteria")
        if self.operator in {"any_of", "all_of"} and len(self.options) < 2:
            raise ValueError("AND/OR requires at least two explicit options")
        if self.operator == "single" and self.options:
            raise ValueError("single requirement must not invent alternatives")
        if len(self.source_line_numbers) != len(set(self.source_line_numbers)):
            raise ValueError("source line numbers must be unique")
        return self


class ValidatedRequirement(StrictModel):
    requirement_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    priority: Priority
    jd_evidence: str = Field(min_length=1)
    # Phase 7A metadata: descriptive only; never used to change an existing score.
    # Import at construction time to avoid circular imports from the typing service.
    constraint: "RequirementConstraint" = Field(default_factory=RequirementConstraint)


class LLMTypeProposal(StrictModel):
    requirement_id: str = Field(min_length=1)
    kind: RequirementKind


class LLMTypeResponse(StrictModel):
    requirements: list[LLMTypeProposal]


class EvidenceCitation(StrictModel):
    segment_id: str = Field(min_length=1)
    section: str = Field(min_length=1)
    text: str = Field(min_length=1)


class CompoundComponent(StrictModel):
    name: str = Field(min_length=1)
    status: AssessmentStatus
    evidence: list[EvidenceCitation] = Field(default_factory=list)
    reason: str = ""


class CompoundCheck(StrictModel):
    operator: LogicalOperator
    outcome: Literal["matched", "not_matched", "uncertain", "needs_review"]
    components: list[CompoundComponent] = Field(default_factory=list)
    explanation: str = ""


class EligibilityCheck(StrictModel):
    status: Literal["not_configured", "criteria_satisfied", "criteria_unmet", "needs_review", "evaluation_failed"] = "not_configured"
    gated_requirement_ids: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    reviewed_by: str | None = None


class RequirementAssessment(StrictModel):
    requirement_id: str = Field(min_length=1)
    status: AssessmentStatus
    evidence: str | None = None
    matched_term: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_segments: list[EvidenceCitation] = Field(default_factory=list)
    reviewed_alias_by: str | None = None
    # Phase 7B: source-backed numeric experience diagnostic, when applicable.
    experience_check: "ExperienceCheck | None" = None
    qualification_check: "QualificationCheck | None" = None
    compound_check: CompoundCheck | None = None


class CandidateAssessmentResponse(StrictModel):
    # Legacy/internal response retained for deterministic tests and reports.
    assessments: list[RequirementAssessment]


class LLMAssessmentItem(StrictModel):
    requirement_id: str = Field(min_length=1)
    status: AssessmentStatus
    evidence_ids: list[str] = Field(default_factory=list)
    matched_term: str | None = None


class LLMCandidateAssessmentResponse(StrictModel):
    assessments: list[LLMAssessmentItem]


class CandidateResult(StrictModel):
    candidate_name: str
    candidate_source: str = ""
    rank: int | None = None

    primary_score: float | None = None
    matched_primary: int = 0
    total_primary: int = 0

    required_score: float | None = None
    matched_required: int = 0
    total_required: int = 0
    preferred_score: float | None = None
    matched_preferred: int = 0
    total_preferred: int = 0
    unknown_score: float | None = None
    matched_unknown: int = 0
    total_unknown: int = 0

    score_basis: str = ""
    evaluation_mode: EvaluationMode = "failed"
    assessments: list[RequirementAssessment] = Field(default_factory=list)
    eligibility: EligibilityCheck = Field(default_factory=EligibilityCheck)
    errors: list[str] = Field(default_factory=list)


class RankingReport(StrictModel):
    build_id: str = BUILD_ID
    job_description_source: str
    jd_validation_mode: str
    yake_candidates: list[YakeCandidate]
    requirements: list[ValidatedRequirement]
    candidates: list[CandidateResult]
    warnings: list[str] = Field(default_factory=list)
    # JD-only trace: raw model proposals, grounding decisions, explicit-source
    # preservation, and the final frozen denominator. No resume text is logged.
    jd_diagnostics: list[dict] = Field(default_factory=list)
    approved_aliases: list[dict[str, str]] = Field(default_factory=list)
    approved_aliases_sha256: str | None = None
    jd_sha256: str | None = None
    eligibility_policy_sha256: str | None = None
    eligibility_policy_reviewed_by: str | None = None
    eligibility_gate_names: list[str] = Field(default_factory=list)
    eligibility_gates: list[dict[str, str]] = Field(default_factory=list)


# Phase 7B type imported after model declarations to avoid import cycles.
from .experience_validation import ExperienceCheck
from .qualification_validation import QualificationCheck
RequirementAssessment.model_rebuild()
