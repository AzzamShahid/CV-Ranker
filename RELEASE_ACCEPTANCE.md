# TextileHR AI — Release Acceptance Gates (A through H)

This document certifies release acceptance compliance in accordance with Section 4 and Sections 5–18 of the Master Implementation, Regression Repair and Release Acceptance Specification.

## Release Metadata
- **Release Version**: `v0.2.1-DA021-P1-RC1`
- **Build ID**: `phase7g-v4-9-72-p1-prompt-integration-rc1-2026-11-16`
- **Protocol**: `segment_ids_semantic_llm` (Version 58)
- **Target Architecture**: Local single-operator supervised operation (React 19 + FastAPI + Python 3.11)
- **Execution Date**: 2026-11-17
- **Verification Environment**: Windows 10/11, Python 3.11.9, Node v23.11.0, npm 11.10.0

---

## Acceptance Gates Summary

| Gate | Category | Description | Applicable Requirements | Gate Decision |
|---|---|---|---|---|
| **GATE A** | Decision Correctness | Substantive 3-verdict model; operational separation; domain neutrality; negation & duration handling | 12 atomic requirements | **PASS** |
| **GATE B** | Identity & Diagnostics | Stable candidate & document ID mappings; vector vs lexical separation; truthful failure modes | 8 atomic requirements | **PASS** |
| **GATE C** | Durable Execution | Operations table persistence; idempotency keys; CAS concurrency protection; crash recovery | 7 atomic requirements | **PASS** |
| **GATE D** | Accounting | Replay-safe usage events; deduplicated attempts; honest unknown token reporting; model provenance | 6 atomic requirements | **PASS** |
| **GATE E** | Data Lifecycle | Retention purge preview parity; protected active records; recoverable physical unlinks with startup retry | 5 atomic requirements | **PASS** |
| **GATE F** | Application Integration | React 19 production build; 0 lint warnings; 31 frontend tests; 70 web tests; B01–B14 browser scenarios | 8 atomic requirements | **PASS** |
| **GATE G** | Release | 100% strict source manifest hashes; clean-room packaging; secret exclusion; extraction verification | 6 atomic requirements | **PASS** |
| **GATE H** | Historical Program | 32-requirement 15-column reconciliation; experience/education hierarchies; frozen assessment dates | 8 atomic requirements | **PASS (Local)** / **BLOCKED (External Cloud Evals)** |

---

## Detailed Gate Evidence & Verification Records

### GATE A — Decision Correctness

#### 1. Atomic Requirements
1. **Substantive 3-Verdict Model**: Completed decisions are strictly `Found`, `Transferable`, or `Not Found`. No 4th semantic status (such as `Unverified`) is used as an easy out for difficult text.
2. **Operational Error Separation**: System faults, missing input, incomplete extractions, network/provider failures, and schema violations remain distinct operational errors; they never masquerade as substantive `Not Found` verdicts.
3. **Missing Source Input Guard**: Missing document or empty source segments abort as operational errors; they are never marked as verified `Not Found`.
4. **Preservation of Prior Assessment**: Failed or inconclusive optional focused reviews preserve the candidate's last valid official assessment.
5. **Score vs Status Distinction**: Null or unavailable scores are never coerced into verified zero scores.
6. **Criterion Standards**: Bare skill requirements accept affirmative skill claims; performed duties require duty evidence; tenure requirements require duration evidence; qualifications require suitable credential evidence.
7. **Compound Logic**: `AND` criteria enforce all mandatory facets; `OR` criteria allow alternatives without dropping sibling requirements.
8. **Negation & Context Protection**: Supported paraphrases accepted; explicit negations, future/hypothetical aspirations ("planning to learn", "currently learning"), and unrelated acronyms receive no direct credit.
9. **Domain Neutrality**: Zero candidate-specific, filename-specific, requirement-ID-specific, or employer-specific hardcoded answers.
10. **Canonical Decision Finalization**: Unified assessment, ordinary evaluation, focused review, and fallback routes adhere to one shared finalizer and scoring engine.
11. **Zero Model Calls on Weight Revisions**: Adjusting JD requirement weights executes purely arithmetic recalculation without model re-inference.
12. **Evidence Traceability**: Every decision includes an evidence passage citation or an honest explanation of CV absence.

#### 2. Passed Checks
- `tests/web/test_audit_reproductions.py::test_reproduce_da_a16_missing_source_input_not_evidenced`: Verified missing source raises operational error, preserving prior status.
- `tests/web/test_audit_reproductions.py::test_reproduce_da_a02_focused_review_outcome_schema`: Verified ambiguous review outcomes conform strictly to allowed schemas without mutating substantive verdicts.
- `tests/test_v484_domain_neutral_prompts.py`: Verified zero hardcoded domain bias in evaluation prompts.
- `tests/test_surgical_fixes.py`: Verified bare skills vs performed duty separation across test suites.
- `tests/test_audit_regressions.py`: Verified zero model calls on weight change.

#### 3. Failed Checks
- None (0 failed).

#### 4. Blocked Checks
- None.

#### 5. Evidence References
- `cv_ranker/decision_contract.py`
- `cv_ranker/scoring.py`
- `backend/engine_service.py`
- `tests/web/test_audit_reproductions.py`

#### 6. Residual Limits
- Human supervisor verification remains authoritative for borderline domain-specific qualifications.

#### 7. Gate Decision
- **PASS**

---

### GATE B — Identity & Diagnostics

#### 1. Atomic Requirements
1. **Stable Document & Candidate ID**: Candidate records and documents are tracked by unique IDs, never by display names or filenames.
2. **Duplicate Disambiguation**: Two candidates with identical names or identical filenames are assigned separate document and candidate entities without collision.
3. **No Synthetic Substitute CVs**: System never manufactures dummy or synthetic substitute CV text when files are missing.
4. **Vector vs Lexical Distinction**: Lexical inclusion and vector cosine similarity remain strictly separated.
5. **Finite & Nullable Similarity**: Vector similarity preserves finite numeric values `[0.0, 1.0]` or explicit `null`; malformed numeric representations (NaN, infinity) are rejected.
6. **Diagnostic Independence**: Semantic diagnostics and similarity shadows provide operator inspection only; they can never alter official decisions, scores, or rankings.
7. **Diagnostic Failure Classification**: Extraction, configuration, embedding service, and model response errors are classified into truthful diagnostic states.
8. **Clean Production Separation**: Production runtime does not import test encoders or mock evaluation classes.

#### 2. Passed Checks
- `tests/web/test_audit_reproductions.py::test_reproduce_da_a05_candidate_identity_in_semantic_diagnostics`: Verified candidate ID and document ID mappings prevent identity cross-contamination.
- `tests/web/test_audit_reproductions.py::test_reproduce_da_a06_substitute_input_and_nullable_similarity`: Verified absence of synthetic text and verified nullable float validation.
- `tests/web/test_audit_reproductions.py::test_reproduce_da_a07_semantic_diagnostic_error_handling`: Verified honest diagnostic failure reporting without fallback masking.
- `tests/web/test_submission_identity.py`: Verified document ID uniqueness and submission deduplication.

#### 3. Failed Checks
- None (0 failed).

#### 4. Blocked Checks
- None.

#### 5. Evidence References
- `backend/storage.py` (Documents & Candidate mapping)
- `backend/api.py` (Diagnostics endpoint)
- `tests/web/test_submission_identity.py`

#### 6. Residual Limits
- Vector similarity calculations depend on available local sentence-transformers models or embedding providers when configured.

#### 7. Gate Decision
- **PASS**

---

### GATE C — Durable Execution

#### 1. Atomic Requirements
1. **Durable Operations Ledger**: Operation intent persisted in `operations` table prior to dispatching external review tasks.
2. **Idempotency Contract**: Same `idempotency_key` + identical request payload returns existing operation; same key with different payload returns `409 Conflict`.
3. **Legal State Transitions**: Discrete state machine transitions: `queued` → `running` → `response_saved` → `completed` (or `failed` / `conflict`).
4. **Crash Recovery**: Survives mid-execution crashes; if crashed in `response_saved`, server re-evaluates the saved response upon restart without triggering duplicate model calls.
5. **Optimistic Concurrency (CAS)**: Publication verifies `base_result_revision`; stale worker writes or conflicting concurrent updates trigger `409 Conflict`.
6. **Atomic Publication Commit**: Candidate checkpoint, assessment verdict, decision history, result revision, and operation status commit atomically in one database transaction.
7. **Bounded Retries**: Review retries are capped, bounded, and obey `Retry-After`.

#### 2. Passed Checks
- `tests/web/test_audit_reproductions.py::test_reproduce_da_a08_durable_review_operations_and_recovery`: Verified operation intent persistence, crash recovery from `response_saved`, and CAS concurrency rejection.
- `tests/web/test_audit_reproductions.py::test_reproduce_da_a09_concurrency_and_crash_scenarios`: Verified optimistic concurrency conflict handling.

#### 3. Failed Checks
- None (0 failed).

#### 4. Blocked Checks
- None.

#### 5. Evidence References
- `backend/storage.py` (`create_operation`, `get_operation_by_key`, `update_operation_state`)
- `backend/api.py` (`focused_review` endpoint)
- `tests/web/test_audit_reproductions.py`

#### 6. Residual Limits
- Single-database SQLite locking semantics; bounded for single-operator supervised workloads.

#### 7. Gate Decision
- **PASS**

---

### GATE D — Accounting

#### 1. Atomic Requirements
1. **Stable Usage Events**: Model consumption tracked in `usage_events` table deduplicated by `event_id` (`{job_id}:{doc_id}:{stage}`).
2. **Replay Safety**: Persisting the same usage event multiple times has zero cumulative effect (`INSERT OR IGNORE`).
3. **Genuine Retry Accounting**: Each genuine distinct review attempt records an additional discrete event.
4. **Honest Incomplete Accounting**: Unknown token counts remain explicitly unknown; they are never coerced to zero. Totals with unknown components are marked incomplete.
5. **Model Label Immutability**: Historical usage records freeze the provider and model resolved at call time; changes to `.env` never retroactively rename historical usage records.
6. **Traceable Cost Tariffs**: Model rates and token costs maintain date, version, and currency provenance.

#### 2. Passed Checks
- `tests/web/test_audit_reproductions.py::test_reproduce_da_a10_replay_safe_usage_accounting`: Verified `usage_events` deduplication, event replaying idempotency, and unknown token preservation.
- `backend/storage.py`: `get_job_metrics` verified summing discrete events.

#### 3. Failed Checks
- None (0 failed).

#### 4. Blocked Checks
- None.

#### 5. Evidence References
- `backend/storage.py` (`usage_events` table and queries)
- `tests/web/test_audit_reproductions.py`

#### 6. Residual Limits
- External provider billing reconciliations depend on provider token reporting accuracy.

#### 7. Gate Decision
- **PASS**

---

### GATE E — Data Lifecycle

#### 1. Atomic Requirements
1. **Retention Preview Parity**: Retention purge preview exact-matches the candidate and document records purged during execution.
2. **Active Record Protection**: Active jobs, incomplete evaluations, running operations, and needed inputs are strictly protected from purge deletion.
3. **Foreign Key Integrity**: Database cascades and deletions maintain complete relational integrity without disabling foreign key checks.
4. **Recoverable Physical Cleanup**: Physical document unlinks are logged to `pending_cleanups` table on OS file-lock failures (Windows `OSError`), ensuring zero unreferenced ghost files.
5. **Startup Cleanup Processing**: Server startup and storage initialization automatically process and retry `pending_cleanups`.

#### 2. Passed Checks
- `tests/web/test_audit_reproductions.py::test_reproduce_da_a12_recoverable_physical_cleanup`: Verified simulated Windows file-lock failure registers in `pending_cleanups` and succeeds on restart.
- `tests/web/test_retention.py`: Verified retention policy preview and purge execution parity.

#### 3. Failed Checks
- None (0 failed).

#### 4. Blocked Checks
- None.

#### 5. Evidence References
- `backend/storage.py` (`_safe_unlink`, `pending_cleanups`, `process_pending_cleanups`)
- `tests/web/test_retention.py`
- `tests/web/test_audit_reproductions.py`

#### 6. Residual Limits
- Files actively locked by external antivirus or file indexers remain queued in `pending_cleanups` until released.

#### 7. Gate Decision
- **PASS**

---

### GATE F — Application Integration

#### 1. Atomic Requirements
1. **Production Bundle Compilation**: Frontend compiles cleanly into `frontend/dist/` with asset hashing and zero build warnings.
2. **Strict TypeScript Compliance**: `npm run typecheck` passes with exit code 0.
3. **Zero Lint Tolerances**: `npm run lint` passes with 0 errors and 0 warnings (`--max-warnings 0`).
4. **Contract Synchronization**: OpenAPI specification and TypeScript client DTOs strictly in sync (`scripts/generate_web_contract.py --check`).
5. **Mounted Component Tests**: 31 frontend unit and mounted component tests pass cleanly.
6. **Comprehensive Web & Engine Tests**: 70 web API and worker tests pass cleanly.
7. **Master Browser Scenarios (B01–B14)**: All 14 master user journeys executed and verified with visual evidence.
8. **UI Layout Polish**: Stat card equal sizing, collapsed dock collision prevention, and spacious candidate detail drawer verified.

#### 2. Passed Checks
- `npm --prefix frontend run build`: Compiled in 1.27s (dist assets hashed).
- `npm --prefix frontend run typecheck`: Exit code 0.
- `npm --prefix frontend run lint`: 0 errors, 0 warnings.
- `npm --prefix frontend test`: 31/31 passed.
- `python scripts/generate_web_contract.py --check`: Exit code 0.
- `pytest tests/web/`: 70/70 passed.
- `BROWSER_VERIFICATION.md`: Scenarios B01 through B14 verified.

#### 3. Failed Checks
- None (0 failed).

#### 4. Blocked Checks
- None.

#### 5. Evidence References
- `frontend/dist/`
- `BROWSER_VERIFICATION.md`
- `TEST_RESULTS.md`

#### 6. Residual Limits
- Browser execution targeted for modern Chromium, Firefox, and WebKit desktop viewports (min width 1024px).

#### 7. Gate Decision
- **PASS**

---

### GATE G — Release

#### 1. Atomic Requirements
1. **Strict Source Integrity**: All 61 `cv_ranker/*.py` engine authority files byte-identical to approved baseline (`CVR_STRICT_SOURCE_HASHES=1`).
2. **Build Manifest Integrity**: All source files hashed in `cv_ranker/build_manifest.json` with zero unauthorized modifications.
3. **Package Hygiene**: Zero `.env`, credentials, local caches, applicant CVs, or temporary databases packaged.
4. **Production Asset Packaging**: Production frontend bundle (`frontend/dist/`) and lockfiles included.
5. **Fresh-Extraction Verification**: Extracted release archive verified in isolated directory with runtime preflights passing.
6. **External Release Identity**: SHA-256 and byte sizes emitted to external `RELEASE_IDENTITY.json` avoiding circular checksum claims.

#### 2. Passed Checks
- `CVR_STRICT_SOURCE_HASHES=1 python -m cv_ranker.runtime_check`: `SOURCE_INTEGRITY=strict_verified`.
- Packaging via `scripts/package_source_release.py`: Verified files + manifest.
- SHA-256 computation and clean-room extraction test.

#### 3. Failed Checks
- None (0 failed).

#### 4. Blocked Checks
- None.

#### 5. Evidence References
- `cv_ranker/build_manifest.json`
- `RELEASE_IDENTITY.json`
- `TextileHR_AI_Migration_Qualified_2026-11-17.zip`

#### 6. Residual Limits
- Release ZIP is intended for local supervised operator execution.

#### 7. Gate Decision
- **PASS**

---

### GATE H — Historical Program

#### 1. Atomic Requirements
1. **Consolidated Requirement Matrix**: Complete 15-column `REQUIREMENT_MATRIX.csv` covering all 32 historical requirements.
2. **JD Interpretation**: Required vs. preferred classification, bare skills vs. duties, duration constraints, and stable row identity during edit/deletion.
3. **Document Extraction**: Support for DOCX, multi-column PDF, image/OCR boundary honesty (no false negatives for unread image pages).
4. **Experience & Education Hierarchy**: Overlapping roles, frozen assessment dates, higher degree hierarchy.
5. **Prompt Budget & Protocol 58**: P1 prompt integration within protocol 58 budget limits.
6. **Engine Source Protection**: Core Python engine unchanged.
7. **Single-Operator Boundary**: Documented local supervised boundaries; no false claims of universal semantic accuracy.
8. **Independent Gold Evaluation**: Ground-truth dataset evaluation separated into local offline fixtures and cloud evaluations.

#### 2. Passed Checks
- `REQUIREMENT_MATRIX.csv`: All 32 requirements fully mapped across 15 columns.
- `tests/test_phase7a_typed_requirements.py`: Verified requirement typing and duration parsing.
- `tests/test_v4961_experience_education_hierarchy.py`: Verified degree hierarchy and experience calculations.
- `tests/test_surgical_fixes.py`: Verified JD row identity preservation.

#### 3. Failed Checks
- None (0 failed).

#### 4. Blocked Checks
- External live cloud evaluation against paid API keys remains explicitly BLOCKED due to intentional zero-spend local test policy; local offline evaluations certified.

#### 5. Evidence References
- `REQUIREMENT_MATRIX.csv`
- `docs/P1_CONTEXT_BUDGET_AND_QUALIFICATION.md`

#### 6. Residual Limits
- Universal semantic accuracy is not claimed; human operator retains supervised oversight.

#### 7. Gate Decision
- **PASS (Local Scope)** / **BLOCKED (External Cloud Evaluations)**

---

## Final Release Determination

All applicable gates for local supervised single-operator execution (**Gates A through G, and Gate H Local Scope**) have achieved **PASS**.

**Current repair scope completed; external cloud qualification gates remain explicitly documented as blocked.**
