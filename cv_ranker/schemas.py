from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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


class ValidatedRequirement(StrictModel):
    requirement_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    priority: Priority
    jd_evidence: str = Field(min_length=1)


class RequirementAssessment(StrictModel):
    requirement_id: str = Field(min_length=1)
    status: AssessmentStatus
    evidence: str | None = None
    matched_term: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


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
    errors: list[str] = Field(default_factory=list)


class RankingReport(StrictModel):
    job_description_source: str
    jd_validation_mode: str
    yake_candidates: list[YakeCandidate]
    requirements: list[ValidatedRequirement]
    candidates: list[CandidateResult]
    warnings: list[str] = Field(default_factory=list)
