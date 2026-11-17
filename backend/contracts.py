"""Stable external API DTOs. Core ranking meaning remains owned by cv_ranker."""
from __future__ import annotations

from typing import Literal, Any
from pydantic import BaseModel, Field, ConfigDict

class PublicDTO(BaseModel):
    model_config=ConfigDict(extra='ignore')

class WorkspaceDTO(PublicDTO):
    id: str
    title: str
    revision: int
    created: str
    updated: str

class WorkspacesDTO(PublicDTO):
    items: list[WorkspaceDTO]

class DocumentDTO(PublicDTO):
    id: str
    workspace_id: str
    kind: Literal['jd','cv']
    filename: str
    sha256: str
    byte_size: int
    extraction_state: str
    extraction_error: str|None = None
    created: str

class DocumentsDTO(PublicDTO):
    items: list[DocumentDTO]
    formats: list[str]
    max_upload_bytes: int

class JDRowDTO(PublicDTO):
    model_config=ConfigDict(extra='forbid',populate_by_name=True)
    ID: str = ''
    Requirement: str
    Priority: Literal['required','preferred','unknown']
    Type: Literal['skill','experience','education','certification','license','responsibility','eligibility','other']
    jd_source: str = Field(alias='JD source')
    minimum_years: float | None = Field(default=None,ge=0,alias='Minimum years',allow_inf_nan=False)
    degree_level: str = Field(default='',alias='Degree level')
    field_of_study: str = Field(default='',alias='Field of study')
    evidence_standard: str = Field(default='',alias='Evidence standard')
    duration_subject: str = Field(default='',alias='Duration subject')
    mandatory_parts: str = Field(default='',alias='Mandatory JD parts')
    alternative_groups_json: str = Field(default='',alias='Alternative groups JSON')
    complete_expression_json: str = Field(default='',alias='Complete JD expression JSON')

class JDDraftDTO(PublicDTO):
    id: str
    workspace_id: str
    document_id: str
    revision: int
    body: dict[str,Any]
    rows: list[JDRowDTO]

class JobSnapshotDTO(PublicDTO):
    id: str
    workspace_id: str
    kind: Literal['jd_extract','assess']
    state: Literal['queued','running','paused','completed','completed_with_errors','failed','cancelling','cancelled']
    request: dict[str,Any]
    progress: int
    total: int
    sequence: int
    result_revision: int
    cancel_requested: bool
    error_code: str | None = None
    error_message: str | None = None
    eligible_at: float | None = None
    created: str
    updated: str

class JobsDTO(PublicDTO):
    items: list[JobSnapshotDTO]

class JobEventDTO(PublicDTO):
    job_id: str
    seq: int
    kind: str
    payload: dict[str,Any]
    created: str

class JobEventsDTO(PublicDTO):
    items: list[JobEventDTO]
    snapshot: JobSnapshotDTO

class WeightPolicyDTO(PublicDTO):
    experience: int
    education: int
    jd: int
    split_jd: bool
    jd_view: str
    jd_allocation: Literal['pooled','weighted_split']
    jd_required_share: int|None
    jd_preferred_share: int|None
    requirement_shares_percent_of_category: dict[str,float]
    default_requirement_allocation: Literal['equal','custom']

class WeightsDTO(PublicDTO):
    revision: int
    body: WeightPolicyDTO

class RankingDTO(PublicDTO):
    candidate_index: int
    candidate_id: str
    candidate: str
    weighted_score: float | None
    verified_floor: float | None
    provisional: bool
    score_status: str
    unverified_count: int
    jd_overall: str
    required: str
    preferred: str
    experience: str
    education: str
    review: str
    rank: int | None
    breakdown: dict[str,Any]
    placement_reason: str | None = None
    score_gap: float | None = None

class RankingsDTO(PublicDTO):
    items: list[RankingDTO]
    total: int
    ready: bool
    offset: int = 0
    limit: int = 50
    search: str = ''
    weight_revision: int | None = None
    result_revision: int | None = None
    official_count: int = 0
    unfinished_count: int = 0
    comparative_summary: str | None = None

class CandidateWeightedDTO(PublicDTO):
    candidate_id: str
    result_revision: int
    weight_revision: int
    result: RankingDTO

class SourceSegmentDTO(PublicDTO):
    segment_id: str
    section: str
    text: str

class CheckpointDTO(PublicDTO):
    Segment: str
    Section: str
    Text: str
    Sources: list[str] = Field(default_factory=list)
    Why: list[str] = Field(default_factory=list)
    highlight_terms: list[str] = Field(default_factory=list,alias='Highlight terms')
    validated_against_cv: bool = Field(alias='Validated against CV')

class CriterionDTO(PublicDTO):
    ID: str
    Requirement: str
    Priority: str
    # Unverified is a READ-ONLY historical label, not a current verdict.
    Result: Literal['Found','Transferable','Not Found','Assessment incomplete','Unverified']
    Why: str
    jd_source: str = Field(alias='JD source')
    Kind: str
    evidence_level: str = Field(alias='Evidence level')
    Checkpoints: list[CheckpointDTO]
    display_checkpoints: list[CheckpointDTO] = Field(alias='Display checkpoints')
    review_recommended: bool = Field(alias='Review recommended')
    processing_state: str = Field(alias='Processing state')
    failure_code: str | None = Field(alias='Failure code')

class FinalCandidateDTO(PublicDTO):
    Candidate: str
    Criteria: list[CriterionDTO]
    Notices: list[str]
    run_warnings: list[str] = Field(alias='Run warnings')
    Provisional: bool
    required_matched: int = Field(alias='Required matched')
    required_total: int = Field(alias='Required total')
    preferred_matched: int = Field(alias='Preferred matched')
    preferred_total: int = Field(alias='Preferred total')
    Transferable: int
    processing_incomplete: int = Field(alias='Processing incomplete')

class CandidateSummaryDTO(PublicDTO):
    candidate_name: str
    candidate_source: str
    primary_score: float | None
    matched_required: int
    total_required: int
    matched_preferred: int
    total_preferred: int
    evaluation_mode: str
    errors: list[str] = Field(default_factory=list)
    rank: int | None = None

class FrozenRequirementDTO(PublicDTO):
    requirement_id: str
    name: str
    priority: str
    jd_evidence: str
    constraint: dict[str,Any]

class ReasoningItemDTO(PublicDTO):
    requirement_id: str = ''
    requirement: str = ''
    priority: str = ''
    category: str | None = None
    decision: str = ''
    points: float | None = None
    why: str = ''

class HeadToHeadComparisonDTO(PublicDTO):
    against_candidate_index: int
    against: str
    rank: int | None = None
    score_gap: float | None = None
    top_candidate_advantages: list[ReasoningItemDTO] = Field(default_factory=list)
    other_candidate_advantages: list[ReasoningItemDTO] = Field(default_factory=list)
    is_tie: bool = False

class CandidateRankingReasoningDTO(PublicDTO):
    summary: str = ''
    placement_reason: str = ''
    rank: int | None = None
    score: float | None = None
    strengths: list[ReasoningItemDTO] = Field(default_factory=list)
    gaps: list[ReasoningItemDTO] = Field(default_factory=list)
    transferable: list[ReasoningItemDTO] = Field(default_factory=list)
    head_to_head_summary: str = ''
    top_candidate_advantages: list[ReasoningItemDTO] = Field(default_factory=list)
    other_candidate_advantages: list[ReasoningItemDTO] = Field(default_factory=list)
    score_gap: float | None = None
    all_comparisons: list[HeadToHeadComparisonDTO] = Field(default_factory=list)

class CandidateDetailDTO(PublicDTO):
    result_revision: int
    candidate: CandidateSummaryDTO
    final: FinalCandidateDTO
    original_segments: list[SourceSegmentDTO]
    requirements: list[FrozenRequirementDTO]
    ranking_reasoning: CandidateRankingReasoningDTO | None = None

class ExportDTO(PublicDTO):
    id: str
    job_id: str
    workspace_id: str
    weight_revision: int
    result_revision: int
    size: int
    created: str

class ExportsDTO(PublicDTO):
    items: list[ExportDTO]

class HistoricalDTO(PublicDTO):
    id: str
    workspace_id: str
    source_name: str
    source_build: str
    created: str

class HistoricalListDTO(PublicDTO):
    items: list[HistoricalDTO]

class ErrorDTO(PublicDTO):
    code: str
    message: str

class DeleteResultDTO(PublicDTO):
    deleted: str

class UnknownResolutionDTO(PublicDTO):
    job_id: str | None = None
    state: str
    committed_candidates: int|None = None
    total: int|None = None
    may_have_incurred_provider_cost: bool|None = None
    next_actions: list[str] = Field(default_factory=list)
    id: str|None = None

class UnknownRecoveryRequest(BaseModel):
    resolution: Literal['inspect','accept_duplicate_risk']
    acknowledgement: str|None = None

class ConfirmDeletion(BaseModel):
    confirmation: Literal['DELETE']

class WorkspaceDelete(BaseModel):
    confirmation: Literal['DELETE WORKSPACE']

class FocusedReviewRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    requirement_id: str = Field(min_length=1)
    provider: str | None = None
    use_llm: bool | None = None
    expected_result_revision: int | None = None
    idempotency_key: str | None = None

class FocusedReviewDTO(PublicDTO):
    candidate_id: str
    requirement_id: str
    prior_verdict: str
    new_verdict: str
    explanation: str
    result_revision: int
    citations: list[dict[str, Any]] = Field(default_factory=list)

class ReviewHistoryItemDTO(PublicDTO):
    id: str
    job_id: str
    candidate_id: str
    requirement_id: str
    prior_verdict: str
    new_verdict: str
    explanation: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    created: str

class ReviewHistoryDTO(PublicDTO):
    items: list[ReviewHistoryItemDTO]

class SemanticShadowRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    top_k: int = Field(default=5, ge=1, le=20)
    embedding_model: str | None = None

class SemanticShadowItemDTO(PublicDTO):
    requirement_id: str
    candidate_id: str
    similarity: float
    finding: str
    source_segments: list[str] = Field(default_factory=list)

class SemanticShadowDTO(PublicDTO):
    ready: bool
    scoring_unchanged: bool = True
    notice: str
    items: list[SemanticShadowItemDTO] = Field(default_factory=list)

class TokenUsageDTO(PublicDTO):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

class JobUsageDTO(PublicDTO):
    job_id: str
    provider: str
    model: str
    logical_model_calls: int = 0
    actual_model_request_attempts: int = 0
    token_usage: TokenUsageDTO
    estimated_cost_usd: float | None = None
    cost_label: str
    reused_prompt_calls: int = 0
    preserved_unknown: bool = False

class RetentionSummaryDTO(PublicDTO):
    workspace_id: str
    eligible_jobs: int
    eligible_exports: int
    eligible_documents: int
    protected_active_jobs: int
    protected_unknown_delivery_jobs: int
    default_retention_days: int

class RetentionPurgeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    retention_days: int = Field(default=30, ge=1, le=3650)

class RetentionPurgeResultDTO(PublicDTO):
    purged_jobs: int
    purged_exports: int
    purged_documents: int
    retention_days: int

