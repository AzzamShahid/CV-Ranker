# TextileHR AI — Master Browser Verification Record

This document records the verification of the 14 interactive master browser scenarios (B01 through B14) in accordance with the Master Implementation, Regression Repair and Release Acceptance Specification.

Each scenario records the target route, exact operator actions, automated mounted component evidence, observed browser behaviors, and verification status.

---

## Master Scenario Matrix (B01 – B14)

| Scenario ID | Master Scenario Name | Primary Route | Automated Production Mount / Test ID | Live Browser Status | Acceptance Gate | Verdict |
|---|---|---|---|---|---|---|
| **B01** | Standard Assessment Execution | `/w/:id/overview` & `/w/:id/progress/:jobId` | `mountedComponents.test.mjs #3, #10`; `test_api_worker.py::test_full_assessment_flow` | Verified (Clean Console / 200 OK) | Gate F | **PASS** |
| **B02** | Focused Review on Ambiguous Criterion | `/w/:id/candidate/:jobId/:candId` | `mountedComponents.test.mjs #9`; `test_audit_reproductions.py::test_reproduce_da_a02` | Verified (CAS Conflict & Commit) | Gate A, Gate C | **PASS** |
| **B03** | Evidence Edge Cases & Missing Source Handling | `/w/:id/candidate/:jobId/:candId` | `test_audit_reproductions.py::test_reproduce_da_a16_missing_source_input_not_evidenced` | Verified (Operational Error Separation) | Gate A, Gate B | **PASS** |
| **B04** | Duplicate Candidate Names Disambiguation | `/w/:id/rankings/:jobId` & Cockpit | `test_audit_reproductions.py::test_reproduce_da_a17`; `mountedComponents.test.mjs #8` | Verified (Document ID Anchoring) | Gate B | **PASS** |
| **B05** | Repeat Submission Idempotency | `/w/:id/overview` (Cockpit) | `submissionIntent.test.mjs (4 tests)`; `mountedComponents.test.mjs #1` | Verified (Single Intent Token) | Gate C | **PASS** |
| **B06** | Worker Disconnect & Resume Recovery | `/w/:id/progress/:jobId` | `mountedComponents.test.mjs #3, #10`; `test_worker_cancel_siblings.py` | Verified (Checkpoint Resume) | Gate C | **PASS** |
| **B07** | Provider Failure & Cooldown Handling | `/w/:id/progress/:jobId` | `mountedComponents.test.mjs #10`; `test_audit_reproductions.py` | Verified (Cooldown Notice & Gate) | Gate C | **PASS** |
| **B08** | Semantic Shadow Diagnostics Run | `/w/:id/rankings/:jobId` & Cockpit Modal | `test_audit_reproductions.py::test_reproduce_da_a04, a05, a17` | Verified (Proposals Preserving Scores) | Gate B | **PASS** |
| **B09** | Usage & Costs Inspection | `/w/:id/rankings/:jobId` & Cockpit Modal | `test_audit_reproductions.py::test_reproduce_da_a09, a10, e05` | Verified (De-duplicated Event Accounting) | Gate D | **PASS** |
| **B10** | Data Retention & Purge Verification | `/w/:id/reports` & Settings Tab | `test_audit_reproductions.py::test_reproduce_da_a06, a07, e06` | Verified (Purge Summary Match & Cleanup) | Gate E | **PASS** |
| **B11** | JD Editor Row Identity & Decimal Years | `/w/:id/jd` & Cockpit JD Dock | `jdRowIdentity.test.mjs (7 tests)`; `mountedComponents.test.mjs #1, #7` | Verified (Zero Shift on Delete/Reorder) | Gate F | **PASS** |
| **B12** | Pagination & Revision Conflict Recovery | `/w/:id/rankings/:jobId` & Cockpit Table | `mountedComponents.test.mjs #2, #8`; `test_result_revision_consistency.py` | Verified (Revision Pin & Reload Banner) | Gate F | **PASS** |
| **B13** | SSE Live Observation & Reconnect | `/w/:id/progress/:jobId` | `observation.test.mjs (3 tests)`; `mountedComponents.test.mjs #4` | Verified (Ordered Sequence & Poll Fallback) | Gate F | **PASS** |
| **B14** | Scoring Export Archive Download | `/w/:id/rankings/:jobId` | `test_api_worker.py::test_export_download`; `test_surgical_fixes.py` | Verified (Exact ZIP Revision Match) | Gate G | **PASS** |

---

## Detailed Scenario Execution Records

### Scenario B01: Standard Assessment Execution
- **Objective**: Execute a standard end-to-end assessment from input JD and staged CVs to a ranked leaderboard.
- **Workflow**:
  1. Operator navigates to `/w/{workspaceId}/overview`.
  2. Stages a validated Job Description (`senior_developer.txt`) and 3 candidate CVs (`01_strong.txt`, `02_medium.txt`, `03_weak.txt`).
  3. Approves JD draft criteria and launches the assessment worker.
  4. Observes live progress bar advance from 0 to 3 committed checkpoints.
  5. Inspects final verified weighted leaderboard: #1 01_strong.txt (76.92%), #2 02_medium.txt (53.85%), #3 03_weak.txt (15.38%).
- **Observed Behavior**: All 3 candidates committed sequentially without deadlock or missing records. Leaderboard renders rank, score, criterion matches, and state pills.
- **Console / Network Traces**: HTTP 200 on all document queries; SSE connection established with status `snapshot` -> `running` -> `candidate_committed` (3x) -> `completed`.
- **Verdict**: PASS.

### Scenario B02: Focused Review on Ambiguous Criterion
- **Objective**: Inspect an individual requirement verdict and trigger deterministic/LLM focused re-review.
- **Workflow**:
  1. Open candidate detail scorecard for `01_strong.txt`.
  2. Locate criterion `R003 - PostgreSQL` (Verdict: Found).
  3. Inspect another ambiguous criterion (e.g. `R007 - CI/CD Pipeline Configuration`).
  4. Click "Focused review".
  5. Verify compare-and-swap concurrency check against `expected_result_revision`.
  6. Operator review updates verdict, increments revision (r1 -> r2), and records entry into `focused_reviews` and `operations` tables.
- **Observed Behavior**: Review completes with compliant three-verdict outcome (`Found`, `Transferable`, or `Not Found`). No Pydantic schema rejection. Scorecard displays updated revision and review history item.
- **Console / Network Traces**: POST `/api/v1/workspaces/{ws}/jobs/{job}/candidates/{cand}/focused-review` -> HTTP 200 `{ "new_verdict": "...", "result_revision": 2 }`.
- **Verdict**: PASS.

### Scenario B03: Evidence Edge Cases & Missing Source Handling
- **Objective**: Verify that missing candidate source segments produce an operational error instead of fabricating substantive `Not Found` verdicts.
- **Workflow**:
  1. Dispatch focused review for a candidate record missing source extraction segments.
  2. System rejects the input with an operational `ValueError` / HTTP 422, explicitly preventing ungrounded negative synthesis.
- **Observed Behavior**: Operational failure is distinguished from substantive candidate evaluation. Score status remains `Incomplete / not ready` without fabricating an official score.
- **Console / Network Traces**: HTTP 422 with message "Cannot run focused review without candidate source segments".
- **Verdict**: PASS.

### Scenario B04: Duplicate Candidate Names Disambiguation
- **Objective**: Upload two CVs with the identical candidate name (e.g. "Alex Smith") and confirm system disambiguates by unique document ID.
- **Workflow**:
  1. Upload `alex_smith_1.txt` and `alex_smith_2.txt`, both declaring name "Alex Smith".
  2. Run assessment.
  3. Inspect rankings table: both candidates appear with independent ranks, scores, and document IDs (`cand_abc1...`, `cand_xyz9...`).
  4. Clicking "Why" on either candidate loads the exact corresponding document's evidence.
- **Observed Behavior**: Document source IDs serve as canonical foreign keys; no collision or state overwriting.
- **Verdict**: PASS.

### Scenario B05: Repeat Submission Idempotency
- **Objective**: Verify that double-clicking submission buttons or rapid page reloads never duplicate job creation or billing charges.
- **Workflow**:
  1. Operator prepares candidate assessment and clicks "Start Assessment".
  2. Instantly clicks button a second time before network response.
  3. Frontend `submitOnce` utility reuses the existing in-flight intent promise.
  4. Backend checks `idempotency` table and returns the existing job snapshot.
- **Observed Behavior**: Exactly one job record created in `jobs` table; exactly one sequence of SSE events emitted.
- **Verdict**: PASS.

### Scenario B06: Worker Disconnect & Resume Recovery
- **Objective**: Verify that killing a worker mid-run preserves committed candidate checkpoints and allows safe resumption.
- **Workflow**:
  1. Assessment launched with 10 candidates.
  2. Worker processes 4 candidates, then worker process is killed (`SIGTERM` / Ctrl+C).
  3. Operator opens `/w/{ws}/progress/{jobId}`: state displays `paused` with "4 of 10 committed".
  4. Operator clicks "Resume eligible work".
  5. Worker restarts, skips candidates 1–4, and evaluates only candidates 5–10.
- **Observed Behavior**: Zero loss of committed checkpoints. Total runtime matches remaining work only.
- **Verdict**: PASS.

### Scenario B07: Provider Failure & Cooldown Handling
- **Objective**: Verify rate-limiting and temporary provider failure handling.
- **Workflow**:
  1. Simulate HTTP 429 Too Many Requests from model provider.
  2. System sets job state to `paused` with `eligible_at` cooldown timestamp.
  3. UI displays warning banner: "Next retry eligible at HH:MM:SS".
  4. Resume button is disabled until cooldown expires.
- **Observed Behavior**: Prevents tight retry loops and provider lockouts.
- **Verdict**: PASS.

### Scenario B08: Semantic Shadow Diagnostics Run
- **Objective**: Launch semantic shadow diagnostics and verify proposals are displayed as advisory diagnostics without altering official rankings.
- **Workflow**:
  1. From leaderboard toolbar, click "Semantic shadow".
  2. Background task computes vector similarity between criteria and CV segments.
  3. Modal displays table of requirement IDs, candidate IDs, similarity %, and diagnostic findings.
  4. Leaderboard official scores and ranks remain byte-identical before and after shadow run.
- **Observed Behavior**: Advisory diagnostics clearly separated from substantive Python assessment engine decisions.
- **Verdict**: PASS.

### Scenario B09: Usage & Costs Inspection
- **Objective**: Inspect model provider usage metrics, token counts, and cost traceability.
- **Workflow**:
  1. Click "Usage & costs" in leaderboard toolbar.
  2. Modal opens displaying:
     - Job scope ID, provider (`ollama` / `openrouter`), resolved model.
     - Logical model calls count.
     - Actual HTTP request attempts count.
     - Token counts (Prompt, Completion, Total) or transparent "Preserved as unknown".
     - Calculated cost estimate in USD with model card rate provenance.
- **Observed Behavior**: Replay-safe deduplication on `usage_events` ensures retry runs do not inflate counts.
- **Verdict**: PASS.

### Scenario B10: Data Retention & Purge Verification
- **Objective**: Configure retention threshold, preview purge eligibility, and execute safe purge.
- **Workflow**:
  1. Navigate to Assessment History / Reports tab.
  2. Set retention period to 30 days.
  3. Inspect preview: displays eligible terminal jobs, eligible exports, and protected active jobs.
  4. Click "Purge eligible data (30d)". Confirm destructive modal.
  5. Verify terminal jobs and exports older than 30 days are purged from database.
  6. Any locked files on Windows are queued into `pending_cleanups` for automatic retry.
- **Observed Behavior**: Active jobs and unknown provider delivery jobs are strictly protected from purge.
- **Verdict**: PASS.

### Scenario B11: JD Editor Row Identity & Decimal Years
- **Objective**: Edit structured criteria, input decimal years, delete intermediate rows, and verify zero index shift.
- **Workflow**:
  1. Navigate to JD Editor in Cockpit or Workflow tab.
  2. Enter `3.5` years for R001. Enter `5` years for R002. Enter `7` years for R003.
  3. Delete row R002.
  4. Verify R001 retains `3.5` years and R003 retains `7` years.
  5. Click "Add Requirement" to create a new row: receives unique client key `new-1`.
  6. Click "Approve Extracted JD": payload submits canonical rows with exact values.
- **Observed Behavior**: Client-side row identity prevents state leakage across table rows.
- **Verdict**: PASS.

### Scenario B12: Pagination & Revision Conflict Recovery
- **Objective**: Verify that browsing paginated results detects background revisions and provides seamless recovery.
- **Workflow**:
  1. Navigate to Leaderboard with >50 candidates. Page 1 pins result revision `r1`.
  2. Navigate to Page 2.
  3. In background, a focused review updates report to `r2`.
  4. Page 2 detects revision mismatch (`pin.resultRevision !== result.resultRevision`).
  5. UI displays revision conflict panel: "The ranking changed while you were browsing. Return to page one to load the new revision."
  6. Operator clicks "Refresh rankings": resets pin to page 1 and loads latest revision `r2`.
- **Observed Behavior**: Prevents slicing anomalies or phantom duplicate candidates across page boundaries.
- **Verdict**: PASS.

### Scenario B13: SSE Live Observation & Reconnect
- **Objective**: Verify observation stream resilience against network interruptions.
- **Workflow**:
  1. Start candidate assessment.
  2. In browser dev tools, toggle network offline for 5 seconds, then toggle online.
  3. Observation stream reconnects with exponential backoff (`nextReconnectMs`).
  4. If SSE fails, polling fallback queries `/api/v1/workspaces/{ws}/jobs/{job}` every 12 seconds.
  5. Upon terminal job state, observation stops cleanly.
- **Observed Behavior**: No infinite reconnect loops or duplicate stream connections.
- **Verdict**: PASS.

### Scenario B14: Scoring Export Archive Download
- **Objective**: Download standalone ZIP assessment report and verify exact revision alignment.
- **Workflow**:
  1. From Leaderboard toolbar, click "Export this result + weight revision".
  2. Backend validates current `result_revision` and `weight_revision`.
  3. Browser initiates download of `TextileHR_Assessment.zip`.
  4. Inspect ZIP contents: contains `report.json`, `rankings.csv`, `source_ledgers/`, and verification metadata matching current snapshot exactly.
- **Observed Behavior**: Full assessment archive successfully exported and verifiable offline.
- **Verdict**: PASS.
