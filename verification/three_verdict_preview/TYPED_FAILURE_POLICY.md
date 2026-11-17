# TextileHR Three-Verdict v4.9.69-preview — typed processing policy

This is a source-backed development preview, **not a qualified production release**.

A completed current decision has exactly Found, Transferable, or Not Found. `DecisionRecord` validates this and rejects `completed/null`, `completed/Unverified` and failure with a candidate verdict. Execution states are `pending`, `running`, `completed`, `paused`, `failed`, or `input_required`. `ProcessingFailure` stores an error code, stage, sanitized detail, retry eligibility and optional operation reference. Candidate evidence is never placed into failure details by this adapter.

The new app-owned `RequirementAssessment.current_decision` is authoritative when present. The older `assessment_state` and `unified_status` fields still exist to support internal review scheduling and historical records. These legacy fields are NOT fully migrated; the preview does not claim that every final consumer is converted.

Known codes: `provider_rate_limit`, `provider_timeout`, `provider_authentication`, `provider_unavailable`, `response_schema_invalid`, `response_row_missing`, `citation_identity_invalid`, `document_unreadable`, `source_coverage_incomplete`, `semantic_review_incomplete`, `source_identity_invalid`, `processing_error`.

Evidence-only negative is a completed `Not Found` with score zero; an unreadable file, absent model output or a nonexistent source ID is an unfinished operation. No automatic mapping from a null result or exception to a candidate negative is permitted. Existing legacy fallback-exact mode is NOT fully reconciled with this new policy and requires further work.
