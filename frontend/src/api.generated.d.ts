/* AUTO-GENERATED: python scripts/generate_web_contract.py
 * Source of truth: backend.api.create_app().openapi(). Do not hand-edit.
 * This ambient namespace also supports the offline React TypeScript build.
 */
declare namespace TextileHRApi {
  interface Body_import_historical_report_api_v1_workspaces__workspace_id__historical_reports_post {
    "file": string;
  }
  interface Body_upload_api_v1_workspaces__workspace_id__documents_post {
    "file": string;
  }
  interface CandidateDetailDTO {
    "result_revision": number;
    "candidate": TextileHRApi.CandidateSummaryDTO;
    "final": TextileHRApi.FinalCandidateDTO;
    "original_segments": (TextileHRApi.SourceSegmentDTO)[];
    "requirements": (TextileHRApi.FrozenRequirementDTO)[];
    "ranking_reasoning"?: TextileHRApi.CandidateRankingReasoningDTO | null;
  }
  interface CandidateRankingReasoningDTO {
    "summary"?: string;
    "placement_reason"?: string;
    "rank"?: number | null;
    "score"?: number | null;
    "strengths"?: (TextileHRApi.ReasoningItemDTO)[];
    "gaps"?: (TextileHRApi.ReasoningItemDTO)[];
    "transferable"?: (TextileHRApi.ReasoningItemDTO)[];
    "head_to_head_summary"?: string;
    "top_candidate_advantages"?: (TextileHRApi.ReasoningItemDTO)[];
    "other_candidate_advantages"?: (TextileHRApi.ReasoningItemDTO)[];
    "score_gap"?: number | null;
    "all_comparisons"?: (TextileHRApi.HeadToHeadComparisonDTO)[];
  }
  interface CandidateSummaryDTO {
    "candidate_name": string;
    "candidate_source": string;
    "primary_score": number | null;
    "matched_required": number;
    "total_required": number;
    "matched_preferred": number;
    "total_preferred": number;
    "evaluation_mode": string;
    "errors"?: (string)[];
    "rank"?: number | null;
  }
  interface CandidateWeightedDTO {
    "candidate_id": string;
    "result_revision": number;
    "weight_revision": number;
    "result": TextileHRApi.RankingDTO;
  }
  interface CheckpointDTO {
    "Segment": string;
    "Section": string;
    "Text": string;
    "Sources"?: (string)[];
    "Why"?: (string)[];
    "Highlight terms"?: (string)[];
    "Validated against CV": boolean;
  }
  interface ConfirmDeletion {
    "confirmation": "DELETE";
  }
  interface CriterionDTO {
    "ID": string;
    "Requirement": string;
    "Priority": string;
    "Result": "Found" | "Transferable" | "Not Found" | "Assessment incomplete" | "Unverified";
    "Why": string;
    "JD source": string;
    "Kind": string;
    "Evidence level": string;
    "Checkpoints": (TextileHRApi.CheckpointDTO)[];
    "Display checkpoints": (TextileHRApi.CheckpointDTO)[];
    "Review recommended": boolean;
    "Processing state": string;
    "Failure code": string | null;
  }
  interface DeleteResultDTO {
    "deleted": string;
  }
  interface DocumentDTO {
    "id": string;
    "workspace_id": string;
    "kind": "jd" | "cv";
    "filename": string;
    "sha256": string;
    "byte_size": number;
    "extraction_state": string;
    "extraction_error"?: string | null;
    "created": string;
  }
  interface DocumentsDTO {
    "items": (TextileHRApi.DocumentDTO)[];
    "formats": (string)[];
    "max_upload_bytes": number;
  }
  interface ExportDTO {
    "id": string;
    "job_id": string;
    "workspace_id": string;
    "weight_revision": number;
    "result_revision": number;
    "size": number;
    "created": string;
  }
  interface ExportRequest {
    "revision": number;
    "weight_revision": number;
  }
  interface ExportsDTO {
    "items": (TextileHRApi.ExportDTO)[];
  }
  interface ExtractionRequest {
    "document_id": string;
    "provider"?: string;
    "use_llm"?: boolean;
    "yake_top_k"?: number;
    "openrouter_context_tokens"?: number | null;
    "openrouter_output_tokens"?: number | null;
    "openrouter_max_requests_per_assessment"?: number | null;
  }
  interface FinalCandidateDTO {
    "Candidate": string;
    "Criteria": (TextileHRApi.CriterionDTO)[];
    "Notices": (string)[];
    "Run warnings": (string)[];
    "Provisional": boolean;
    "Required matched": number;
    "Required total": number;
    "Preferred matched": number;
    "Preferred total": number;
    "Transferable": number;
    "Processing incomplete": number;
  }
  interface FocusedReviewDTO {
    "candidate_id": string;
    "requirement_id": string;
    "prior_verdict": string;
    "new_verdict": string;
    "explanation": string;
    "result_revision": number;
    "citations"?: (Record<string,unknown>)[];
  }
  interface FocusedReviewRequest {
    "requirement_id": string;
    "provider"?: string | null;
    "use_llm"?: boolean | null;
    "expected_result_revision"?: number | null;
    "idempotency_key"?: string | null;
  }
  interface FrozenRequirementDTO {
    "requirement_id": string;
    "name": string;
    "priority": string;
    "jd_evidence": string;
    "constraint": Record<string,unknown>;
  }
  interface HTTPValidationError {
    "detail"?: (TextileHRApi.ValidationError)[];
  }
  interface HeadToHeadComparisonDTO {
    "against_candidate_index": number;
    "against": string;
    "rank"?: number | null;
    "score_gap"?: number | null;
    "top_candidate_advantages"?: (TextileHRApi.ReasoningItemDTO)[];
    "other_candidate_advantages"?: (TextileHRApi.ReasoningItemDTO)[];
    "is_tie"?: boolean;
  }
  interface HistoricalDTO {
    "id": string;
    "workspace_id": string;
    "source_name": string;
    "source_build": string;
    "created": string;
  }
  interface HistoricalListDTO {
    "items": (TextileHRApi.HistoricalDTO)[];
  }
  interface JDDraftDTO {
    "id": string;
    "workspace_id": string;
    "document_id": string;
    "revision": number;
    "body": Record<string,unknown>;
    "rows": (TextileHRApi.JDRowDTO)[];
  }
  interface JDReviewEdit {
    "draft_id": string;
    "revision": number;
    "rows": (TextileHRApi.JDRowDTO)[];
  }
  interface JDRowDTO {
    "ID"?: string;
    "Requirement": string;
    "Priority": "required" | "preferred" | "unknown";
    "Type": "skill" | "experience" | "education" | "certification" | "license" | "responsibility" | "eligibility" | "other";
    "JD source": string;
    "Minimum years"?: number | null;
    "Degree level"?: string;
    "Field of study"?: string;
    "Evidence standard"?: string;
    "Duration subject"?: string;
    "Mandatory JD parts"?: string;
    "Alternative groups JSON"?: string;
    "Complete JD expression JSON"?: string;
  }
  interface JobEventDTO {
    "job_id": string;
    "seq": number;
    "kind": string;
    "payload": Record<string,unknown>;
    "created": string;
  }
  interface JobEventsDTO {
    "items": (TextileHRApi.JobEventDTO)[];
    "snapshot": TextileHRApi.JobSnapshotDTO;
  }
  interface JobSnapshotDTO {
    "id": string;
    "workspace_id": string;
    "kind": "jd_extract" | "assess";
    "state": "queued" | "running" | "paused" | "completed" | "completed_with_errors" | "failed" | "cancelling" | "cancelled";
    "request": Record<string,unknown>;
    "progress": number;
    "total": number;
    "sequence": number;
    "result_revision": number;
    "cancel_requested": boolean;
    "error_code"?: string | null;
    "error_message"?: string | null;
    "eligible_at"?: number | null;
    "created": string;
    "updated": string;
  }
  interface JobUsageDTO {
    "job_id": string;
    "provider": string;
    "model": string;
    "logical_model_calls"?: number;
    "actual_model_request_attempts"?: number;
    "token_usage": TextileHRApi.TokenUsageDTO;
    "estimated_cost_usd"?: number | null;
    "cost_label": string;
    "reused_prompt_calls"?: number;
    "preserved_unknown"?: boolean;
  }
  interface JobsDTO {
    "items": (TextileHRApi.JobSnapshotDTO)[];
  }
  interface RankingDTO {
    "candidate_index": number;
    "candidate_id": string;
    "candidate": string;
    "weighted_score": number | null;
    "verified_floor": number | null;
    "provisional": boolean;
    "score_status": string;
    "unverified_count": number;
    "jd_overall": string;
    "required": string;
    "preferred": string;
    "experience": string;
    "education": string;
    "review": string;
    "rank": number | null;
    "breakdown": Record<string,unknown>;
    "placement_reason"?: string | null;
    "score_gap"?: number | null;
  }
  interface RankingsDTO {
    "items": (TextileHRApi.RankingDTO)[];
    "total": number;
    "ready": boolean;
    "offset"?: number;
    "limit"?: number;
    "search"?: string;
    "weight_revision"?: number | null;
    "result_revision"?: number | null;
    "official_count"?: number;
    "unfinished_count"?: number;
    "comparative_summary"?: string | null;
  }
  interface ReasoningItemDTO {
    "requirement_id"?: string;
    "requirement"?: string;
    "priority"?: string;
    "category"?: string | null;
    "decision"?: string;
    "points"?: number | null;
    "why"?: string;
  }
  interface RetentionPurgeRequest {
    "retention_days"?: number;
  }
  interface RetentionPurgeResultDTO {
    "purged_jobs": number;
    "purged_exports": number;
    "purged_documents": number;
    "retention_days": number;
  }
  interface RetentionSummaryDTO {
    "workspace_id": string;
    "eligible_jobs": number;
    "eligible_exports": number;
    "eligible_documents": number;
    "protected_active_jobs": number;
    "protected_unknown_delivery_jobs": number;
    "default_retention_days": number;
  }
  interface ReviewHistoryDTO {
    "items": (TextileHRApi.ReviewHistoryItemDTO)[];
  }
  interface ReviewHistoryItemDTO {
    "id": string;
    "job_id": string;
    "candidate_id": string;
    "requirement_id": string;
    "prior_verdict": string;
    "new_verdict": string;
    "explanation": string;
    "sources"?: (Record<string,unknown>)[];
    "created": string;
  }
  interface SemanticShadowDTO {
    "ready": boolean;
    "scoring_unchanged"?: boolean;
    "notice": string;
    "items"?: (TextileHRApi.SemanticShadowItemDTO)[];
  }
  interface SemanticShadowItemDTO {
    "requirement_id": string;
    "candidate_id": string;
    "similarity": number;
    "finding": string;
    "source_segments"?: (string)[];
  }
  interface SemanticShadowRequest {
    "top_k"?: number;
    "embedding_model"?: string | null;
  }
  interface SourceSegmentDTO {
    "segment_id": string;
    "section": string;
    "text": string;
  }
  interface SubmitJob {
    "candidate_ids": (string)[];
    "approved_revision_id": string;
    "provider"?: string;
    "use_llm"?: boolean;
    "unified"?: boolean;
    "yake_top_k"?: number;
    "openrouter_context_tokens"?: number | null;
    "openrouter_output_tokens"?: number | null;
    "openrouter_max_requests_per_assessment"?: number | null;
  }
  interface TokenUsageDTO {
    "prompt_tokens"?: number | null;
    "completion_tokens"?: number | null;
    "total_tokens"?: number | null;
  }
  interface UnknownRecoveryRequest {
    "resolution": "inspect" | "accept_duplicate_risk";
    "acknowledgement"?: string | null;
  }
  interface ValidationError {
    "loc": (string | number)[];
    "msg": string;
    "type": string;
    "input"?: unknown;
    "ctx"?: Record<string,unknown>;
  }
  interface WeightPolicyDTO {
    "experience": number;
    "education": number;
    "jd": number;
    "split_jd": boolean;
    "jd_view": string;
    "jd_allocation": "pooled" | "weighted_split";
    "jd_required_share": number | null;
    "jd_preferred_share": number | null;
    "requirement_shares_percent_of_category": Record<string,number>;
    "default_requirement_allocation": "equal" | "custom";
  }
  interface WeightsDTO {
    "revision": number;
    "body": TextileHRApi.WeightPolicyDTO;
  }
  interface WeightsUpdate {
    "revision": number;
    "weights": Record<string,unknown>;
  }
  interface WorkspaceCreate {
    "title": string;
  }
  interface WorkspaceDTO {
    "id": string;
    "title": string;
    "revision": number;
    "created": string;
    "updated": string;
  }
  interface WorkspaceDelete {
    "confirmation": "DELETE WORKSPACE";
  }
  interface WorkspacesDTO {
    "items": (TextileHRApi.WorkspaceDTO)[];
  }
  type HttpMethod = "get" | "post" | "put" | "patch" | "delete";
  type ApiPath = "/api/v1/health" | "/api/v1/session" | "/api/v1/settings" | "/api/v1/workspaces" | "/api/v1/workspaces/{workspace_id}" | "/api/v1/workspaces/{workspace_id}/assessment-jobs" | "/api/v1/workspaces/{workspace_id}/documents" | "/api/v1/workspaces/{workspace_id}/documents/{document_id}" | "/api/v1/workspaces/{workspace_id}/documents/{document_id}/download" | "/api/v1/workspaces/{workspace_id}/exports" | "/api/v1/workspaces/{workspace_id}/exports/{export_id}" | "/api/v1/workspaces/{workspace_id}/exports/{export_id}/download" | "/api/v1/workspaces/{workspace_id}/historical-reports" | "/api/v1/workspaces/{workspace_id}/historical-reports/{report_id}" | "/api/v1/workspaces/{workspace_id}/jd" | "/api/v1/workspaces/{workspace_id}/jd/approve" | "/api/v1/workspaces/{workspace_id}/jd/drafts/{draft_id}" | "/api/v1/workspaces/{workspace_id}/jd/extraction-jobs" | "/api/v1/workspaces/{workspace_id}/jobs" | "/api/v1/workspaces/{workspace_id}/jobs/{job_id}" | "/api/v1/workspaces/{workspace_id}/jobs/{job_id}/cancel" | "/api/v1/workspaces/{workspace_id}/jobs/{job_id}/candidates/{doc_id}" | "/api/v1/workspaces/{workspace_id}/jobs/{job_id}/candidates/{doc_id}/focused-review" | "/api/v1/workspaces/{workspace_id}/jobs/{job_id}/candidates/{doc_id}/review-history" | "/api/v1/workspaces/{workspace_id}/jobs/{job_id}/candidates/{doc_id}/weighted" | "/api/v1/workspaces/{workspace_id}/jobs/{job_id}/event-history" | "/api/v1/workspaces/{workspace_id}/jobs/{job_id}/events" | "/api/v1/workspaces/{workspace_id}/jobs/{job_id}/exports" | "/api/v1/workspaces/{workspace_id}/jobs/{job_id}/rankings" | "/api/v1/workspaces/{workspace_id}/jobs/{job_id}/resolve-unknown" | "/api/v1/workspaces/{workspace_id}/jobs/{job_id}/resume" | "/api/v1/workspaces/{workspace_id}/jobs/{job_id}/semantic-shadow" | "/api/v1/workspaces/{workspace_id}/jobs/{job_id}/usage" | "/api/v1/workspaces/{workspace_id}/retention" | "/api/v1/workspaces/{workspace_id}/retention/purge" | "/api/v1/workspaces/{workspace_id}/submissions/{intent_key}" | "/api/v1/workspaces/{workspace_id}/weights" | "/api/v1/workspaces/{workspace_id}/weights/rebalance";
  interface Operations {
    "health_api_v1_health_get": { method:"get"; path:"/api/v1/health"; response:unknown };
    "bootstrap_api_v1_session_get": { method:"get"; path:"/api/v1/session"; response:unknown };
    "settings_api_v1_settings_get": { method:"get"; path:"/api/v1/settings"; response:unknown };
    "workspaces_api_v1_workspaces_get": { method:"get"; path:"/api/v1/workspaces"; response:TextileHRApi.WorkspacesDTO };
    "create_workspace_api_v1_workspaces_post": { method:"post"; path:"/api/v1/workspaces"; response:TextileHRApi.WorkspaceDTO };
    "delete_workspace_api_v1_workspaces__workspace_id__delete": { method:"delete"; path:"/api/v1/workspaces/{workspace_id}"; response:TextileHRApi.DeleteResultDTO };
    "workspace_api_v1_workspaces__workspace_id__get": { method:"get"; path:"/api/v1/workspaces/{workspace_id}"; response:TextileHRApi.WorkspaceDTO };
    "start_assessment_api_v1_workspaces__workspace_id__assessment_jobs_post": { method:"post"; path:"/api/v1/workspaces/{workspace_id}/assessment-jobs"; response:TextileHRApi.JobSnapshotDTO };
    "documents_api_v1_workspaces__workspace_id__documents_get": { method:"get"; path:"/api/v1/workspaces/{workspace_id}/documents"; response:TextileHRApi.DocumentsDTO };
    "upload_api_v1_workspaces__workspace_id__documents_post": { method:"post"; path:"/api/v1/workspaces/{workspace_id}/documents"; response:TextileHRApi.DocumentDTO };
    "delete_document_api_v1_workspaces__workspace_id__documents__document_id__delete": { method:"delete"; path:"/api/v1/workspaces/{workspace_id}/documents/{document_id}"; response:TextileHRApi.DeleteResultDTO };
    "download_document_api_v1_workspaces__workspace_id__documents__document_id__download_get": { method:"get"; path:"/api/v1/workspaces/{workspace_id}/documents/{document_id}/download"; response:unknown };
    "exports_api_v1_workspaces__workspace_id__exports_get": { method:"get"; path:"/api/v1/workspaces/{workspace_id}/exports"; response:TextileHRApi.ExportsDTO };
    "delete_export_api_v1_workspaces__workspace_id__exports__export_id__delete": { method:"delete"; path:"/api/v1/workspaces/{workspace_id}/exports/{export_id}"; response:TextileHRApi.DeleteResultDTO };
    "download_api_v1_workspaces__workspace_id__exports__export_id__download_get": { method:"get"; path:"/api/v1/workspaces/{workspace_id}/exports/{export_id}/download"; response:unknown };
    "historical_reports_api_v1_workspaces__workspace_id__historical_reports_get": { method:"get"; path:"/api/v1/workspaces/{workspace_id}/historical-reports"; response:TextileHRApi.HistoricalListDTO };
    "import_historical_report_api_v1_workspaces__workspace_id__historical_reports_post": { method:"post"; path:"/api/v1/workspaces/{workspace_id}/historical-reports"; response:unknown };
    "historical_report_api_v1_workspaces__workspace_id__historical_reports__report_id__get": { method:"get"; path:"/api/v1/workspaces/{workspace_id}/historical-reports/{report_id}"; response:unknown };
    "jd_api_v1_workspaces__workspace_id__jd_get": { method:"get"; path:"/api/v1/workspaces/{workspace_id}/jd"; response:unknown };
    "approve_api_v1_workspaces__workspace_id__jd_approve_post": { method:"post"; path:"/api/v1/workspaces/{workspace_id}/jd/approve"; response:unknown };
    "jd_draft_api_v1_workspaces__workspace_id__jd_drafts__draft_id__get": { method:"get"; path:"/api/v1/workspaces/{workspace_id}/jd/drafts/{draft_id}"; response:TextileHRApi.JDDraftDTO };
    "revise_api_v1_workspaces__workspace_id__jd_drafts__draft_id__put": { method:"put"; path:"/api/v1/workspaces/{workspace_id}/jd/drafts/{draft_id}"; response:unknown };
    "start_extract_api_v1_workspaces__workspace_id__jd_extraction_jobs_post": { method:"post"; path:"/api/v1/workspaces/{workspace_id}/jd/extraction-jobs"; response:TextileHRApi.JobSnapshotDTO };
    "jobs_api_v1_workspaces__workspace_id__jobs_get": { method:"get"; path:"/api/v1/workspaces/{workspace_id}/jobs"; response:TextileHRApi.JobsDTO };
    "delete_assessment_api_v1_workspaces__workspace_id__jobs__job_id__delete": { method:"delete"; path:"/api/v1/workspaces/{workspace_id}/jobs/{job_id}"; response:TextileHRApi.DeleteResultDTO };
    "job_api_v1_workspaces__workspace_id__jobs__job_id__get": { method:"get"; path:"/api/v1/workspaces/{workspace_id}/jobs/{job_id}"; response:TextileHRApi.JobSnapshotDTO };
    "cancel_job_api_v1_workspaces__workspace_id__jobs__job_id__cancel_post": { method:"post"; path:"/api/v1/workspaces/{workspace_id}/jobs/{job_id}/cancel"; response:TextileHRApi.JobSnapshotDTO };
    "candidate_detail_api_v1_workspaces__workspace_id__jobs__job_id__candidates__doc_id__get": { method:"get"; path:"/api/v1/workspaces/{workspace_id}/jobs/{job_id}/candidates/{doc_id}"; response:TextileHRApi.CandidateDetailDTO };
    "run_focused_review_api_v1_workspaces__workspace_id__jobs__job_id__candidates__doc_id__focused_review_post": { method:"post"; path:"/api/v1/workspaces/{workspace_id}/jobs/{job_id}/candidates/{doc_id}/focused-review"; response:TextileHRApi.FocusedReviewDTO };
    "review_history_api_v1_workspaces__workspace_id__jobs__job_id__candidates__doc_id__review_history_get": { method:"get"; path:"/api/v1/workspaces/{workspace_id}/jobs/{job_id}/candidates/{doc_id}/review-history"; response:TextileHRApi.ReviewHistoryDTO };
    "weighted_candidate_api_v1_workspaces__workspace_id__jobs__job_id__candidates__doc_id__weighted_get": { method:"get"; path:"/api/v1/workspaces/{workspace_id}/jobs/{job_id}/candidates/{doc_id}/weighted"; response:TextileHRApi.CandidateWeightedDTO };
    "event_history_api_v1_workspaces__workspace_id__jobs__job_id__event_history_get": { method:"get"; path:"/api/v1/workspaces/{workspace_id}/jobs/{job_id}/event-history"; response:TextileHRApi.JobEventsDTO };
    "events_api_v1_workspaces__workspace_id__jobs__job_id__events_get": { method:"get"; path:"/api/v1/workspaces/{workspace_id}/jobs/{job_id}/events"; response:unknown };
    "make_export_api_v1_workspaces__workspace_id__jobs__job_id__exports_post": { method:"post"; path:"/api/v1/workspaces/{workspace_id}/jobs/{job_id}/exports"; response:TextileHRApi.ExportDTO };
    "rankings_api_v1_workspaces__workspace_id__jobs__job_id__rankings_get": { method:"get"; path:"/api/v1/workspaces/{workspace_id}/jobs/{job_id}/rankings"; response:TextileHRApi.RankingsDTO };
    "resolve_unknown_api_v1_workspaces__workspace_id__jobs__job_id__resolve_unknown_post": { method:"post"; path:"/api/v1/workspaces/{workspace_id}/jobs/{job_id}/resolve-unknown"; response:unknown };
    "resume_job_api_v1_workspaces__workspace_id__jobs__job_id__resume_post": { method:"post"; path:"/api/v1/workspaces/{workspace_id}/jobs/{job_id}/resume"; response:TextileHRApi.JobSnapshotDTO };
    "get_semantic_shadow_endpoint_api_v1_workspaces__workspace_id__jobs__job_id__semantic_shadow_get": { method:"get"; path:"/api/v1/workspaces/{workspace_id}/jobs/{job_id}/semantic-shadow"; response:TextileHRApi.SemanticShadowDTO };
    "run_semantic_shadow_endpoint_api_v1_workspaces__workspace_id__jobs__job_id__semantic_shadow_post": { method:"post"; path:"/api/v1/workspaces/{workspace_id}/jobs/{job_id}/semantic-shadow"; response:TextileHRApi.SemanticShadowDTO };
    "job_usage_api_v1_workspaces__workspace_id__jobs__job_id__usage_get": { method:"get"; path:"/api/v1/workspaces/{workspace_id}/jobs/{job_id}/usage"; response:TextileHRApi.JobUsageDTO };
    "retention_summary_api_v1_workspaces__workspace_id__retention_get": { method:"get"; path:"/api/v1/workspaces/{workspace_id}/retention"; response:TextileHRApi.RetentionSummaryDTO };
    "retention_purge_api_v1_workspaces__workspace_id__retention_purge_post": { method:"post"; path:"/api/v1/workspaces/{workspace_id}/retention/purge"; response:TextileHRApi.RetentionPurgeResultDTO };
    "submission_recovery_api_v1_workspaces__workspace_id__submissions__intent_key__get": { method:"get"; path:"/api/v1/workspaces/{workspace_id}/submissions/{intent_key}"; response:TextileHRApi.JobSnapshotDTO };
    "weights_api_v1_workspaces__workspace_id__weights_get": { method:"get"; path:"/api/v1/workspaces/{workspace_id}/weights"; response:TextileHRApi.WeightsDTO };
    "update_weights_api_v1_workspaces__workspace_id__weights_put": { method:"put"; path:"/api/v1/workspaces/{workspace_id}/weights"; response:TextileHRApi.WeightsDTO };
    "rebalance_api_v1_workspaces__workspace_id__weights_rebalance_post": { method:"post"; path:"/api/v1/workspaces/{workspace_id}/weights/rebalance"; response:unknown };
  }
}
