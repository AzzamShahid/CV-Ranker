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


class JDConditionNode(StrictModel):
    """Human-approved Boolean structure with original, position-bound JD leaves.

    A repeated printed phrase at two different positions remains two distinct
    leaves. The node never contributes an additional scoring criterion.
    """
    op: Literal["leaf", "all_of", "any_of"]
    text: str | None = None
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=0)
    children: list["JDConditionNode"] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_structure(self):
        if self.op == "leaf":
            if not self.text or self.start is None or self.end is None or self.end <= self.start or self.children:
                raise ValueError("JD condition leaf requires nonempty original source span and no children")
        elif len(self.children) < 2 or self.text is not None or self.start is not None or self.end is not None:
            raise ValueError("JD AND/OR conditions require two or more children and no invented text")
        return self


RequirementKind = Literal["skill", "experience", "education", "certification", "license", "responsibility", "eligibility", "other"]
LogicalOperator = Literal["single", "any_of", "all_of", "complex"]
TypingOrigin = Literal["source_rules", "llm_suggestion", "manual_review_pending", "unclassified"]


class RequirementConstraint(StrictModel):
    kind: RequirementKind = "other"
    operator: LogicalOperator = "single"
    options: list[str] = Field(default_factory=list)
    minimum_years: float | None = Field(default=None, ge=0, le=100)
    # The JD can ask for performed work without imposing a duration gate.
    # This discriminator is derived from the frozen JD's numeric threshold;
    # its classification does not depend on the section heading.
    experience_mode: Literal["tenure", "qualitative"] | None = None
    # The kind is a description of the JD; evidence modality is an
    # independent, source-derived question. No scoring multiplier.
    evidence_modality: Literal[
        "knowledge_claim", "performed_work", "dated_professional_tenure",
        "completed_qualification", "credential_claim", "eligibility_condition",
        "employer_review_required",
    ] | None = None
    duration_subject: Literal[
        "candidate_tenure", "non_tenure_timeframe_review", "none",
    ] | None = None
    subject: str | None = None
    degree_level: Literal["associate", "diploma", "bachelor", "master", "doctorate"] | None = None
    field_of_study: str | None = None
    source_line_numbers: list[int] = Field(default_factory=list)
    # Optional explicit HR-reviewed JD facets. These are verbatim substrings
    # of jd_evidence, never generated skills, extra scored criteria, or an
    # occupational dictionary. Each mandatory part must be supported; for
    # each alternative group, at least one approved option must be supported.
    approved_mandatory_parts: list[str] = Field(default_factory=list)
    approved_alternative_groups: list[list[str]] = Field(default_factory=list)
    approved_expression: JDConditionNode | None = None
    origin: TypingOrigin = "unclassified"
    requires_review: bool = True

    @model_validator(mode="after")
    def check_consistency(self):
        if self.duration_subject == "candidate_tenure" and self.kind != "experience":
            raise ValueError("candidate_tenure requires an experience requirement")
        if (self.evidence_modality == "dated_professional_tenure"
                and self.kind != "experience"):
            raise ValueError("dated professional tenure evidence requires experience kind")
        if self.minimum_years is not None and self.kind != "experience":
            raise ValueError("minimum_years may appear only on experience criteria")
        if self.kind == "experience":
            expected_mode = "tenure" if self.minimum_years is not None else "qualitative"
            if self.experience_mode not in (None, expected_mode):
                raise ValueError("experience_mode must agree with the explicit JD duration gate")
            self.experience_mode = expected_mode
        elif self.experience_mode is not None:
            raise ValueError("experience_mode may appear only on experience criteria")
        if (self.degree_level is not None or self.field_of_study is not None) and self.kind != "education":
            raise ValueError("degree attributes may appear only on education criteria")
        if self.operator in {"any_of", "all_of"} and len(self.options) < 2:
            raise ValueError("AND/OR requires at least two explicit options")
        if self.operator == "single" and self.options:
            raise ValueError("single requirement must not invent alternatives")
        if len(self.source_line_numbers) != len(set(self.source_line_numbers)):
            raise ValueError("source line numbers must be unique")
        if any(not part.strip() for part in self.approved_mandatory_parts):
            raise ValueError("approved mandatory parts must be nonempty")
        if len(set(self.approved_mandatory_parts)) != len(self.approved_mandatory_parts):
            raise ValueError("approved mandatory parts must be unique")
        if any(len(group) < 2 or len(set(group)) != len(group)
               or any(not option.strip() for option in group)
               for group in self.approved_alternative_groups):
            raise ValueError("approved alternative groups need 2+ unique source options")
        return self


class ValidatedRequirement(StrictModel):
    requirement_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    priority: Priority
    jd_evidence: str = Field(min_length=1)
    # Phase 7A metadata: descriptive only; never used to change an existing score.
    # Import at construction time to avoid circular imports from the typing service.
    constraint: "RequirementConstraint" = Field(default_factory=RequirementConstraint)


class JDReviewDraft(StrictModel):
    """Source-bound extraction awaiting a human's explicit scoring approval."""
    jd_sha256: str
    yake_candidates: list[YakeCandidate]
    requirements: list[ValidatedRequirement]
    jd_validation_mode: str
    warnings: list[str] = Field(default_factory=list)
    diagnostics: list[dict] = Field(default_factory=list)
    approved: bool = False
    edited: bool = False


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
    # Optional v52 source-bound condition provenance. Historical components
    # deserialize with None; old evidence must not be newly certified.
    jd_start: int | None = None
    jd_end: int | None = None
    group_role: Literal["mandatory", "alternative", "unresolved"] | None = None
    group_id: str | None = None
    relation: Literal["satisfied", "missing", "uncertain"] | None = None


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


class DecisionTransition(StrictModel):
    """Sanitized per-criterion decision handoff; never contains CV text.

    Retains the *fact and reason* of a source-checked status change. Earlier
    v43 reports deserialize with an empty trace for backward readability.
    """
    stage: str = Field(min_length=1)
    from_status: str = Field(min_length=1)
    to_status: str = Field(min_length=1)
    reason_code: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)


class RequirementAssessment(StrictModel):
    requirement_id: str = Field(min_length=1)
    status: AssessmentStatus
    evidence: str | None = None
    matched_term: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_segments: list[EvidenceCitation] = Field(default_factory=list)
    # Optional explanation from the assessor. Original source citations remain
    # authoritative; the explanation does not itself establish a match.
    reason: str = ""
    # V4.8: single validated final decision. Transferable never earns direct credit.
    unified_status: Literal["Found", "Transferable", "Not Found", "Unverified"] | None = None
    # Technical LLM/schema/citation failures must never be mistaken for an
    # actual CV nonmatch. Old reports default to verified for compatibility.
    assessment_state: Literal["verified", "unverified"] = "verified"
    # v55 migration field. The legacy fields above remain readable for old
    # reports and intermediate stage adapters, but this record is authoritative
    # when present. It is assigned by application code, NEVER by a model schema.
    current_decision: "DecisionRecord | None" = None
    review_recommended: bool = False
    # Provenance metadata for technical audit, not candidate-facing reasoning.
    review_checkpoint_origin: Literal["model", "retrieval"] | None = None
    # A condition review using identical frozen JD/CV/source/model context
    # cannot be silently repeated on Resume after a failed semantic verdict.
    # Digest only: no candidate source text is serialized into this field.
    condition_review_attempt_signature: str | None = None
    reviewed_alias_by: str | None = None
    # Phase 7B: source-backed numeric experience diagnostic, when applicable.
    experience_check: "ExperienceCheck | None" = None
    qualification_check: "QualificationCheck | None" = None
    compound_check: CompoundCheck | None = None
    decision_trace: list[DecisionTransition] = Field(default_factory=list)

    @model_validator(mode="after")
    def current_decision_consistency(self):
        # Historical rows without current_decision retain their old labels.
        # For new rows, a processing failure cannot also be a candidate
        # negative or an awarded positive. The application owns this state.
        record = self.current_decision
        if record is None:
            return self
        if record.processing_state == "completed":
            if (self.assessment_state != "verified" or
                    self.unified_status != record.verdict or
                    (record.verdict == "Found") != (self.status == "matched")):
                raise ValueError("Current completed verdict contradicts assessment status")
        else:
            if self.assessment_state != "unverified" or self.unified_status is not None:
                raise ValueError("Unfinished current assessment must have no final verdict")
        return self


class CandidateAssessmentResponse(StrictModel):
    # Legacy/internal response retained for deterministic tests and reports.
    assessments: list[RequirementAssessment]


class LLMAssessmentItem(StrictModel):
    requirement_id: str = Field(min_length=1)
    status: AssessmentStatus
    evidence_ids: list[str] = Field(default_factory=list)
    matched_term: str | None = None
    reason: str = ""


class LLMCandidateAssessmentResponse(StrictModel):
    assessments: list[LLMAssessmentItem]


class LLMLiveThreeVerdictItem(StrictModel):
    """Current provider wire contract. Historical LLMAssessmentItem is read-only."""
    requirement_id: str = Field(min_length=1)
    status: Literal["matched", "transferable", "not_matched"]
    evidence_ids: list[str] = Field(default_factory=list)
    matched_term: str | None = None
    reason: str = Field(min_length=8)


class LLMLiveThreeVerdictResponse(StrictModel):
    assessments: list[LLMLiveThreeVerdictItem]


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
    # Exact submitted JD text. Required for a self-contained downloadable audit.
    # Older reports without this field remain readable, but cannot reconstruct it.
    original_jd_text: str | None = None
    # Frozen calendar reference for Present/Current tenure and LLM judgments.
    # An older report without this field remains readable as historical only.
    assessment_as_of_date: str | None = None
    jd_validation_mode: str
    yake_candidates: list[YakeCandidate]
    requirements: list[ValidatedRequirement]
    jd_review_approved: bool = False
    jd_review_edited: bool = False
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
from .decision_contract import DecisionRecord  # noqa: E402
RequirementAssessment.model_rebuild()
