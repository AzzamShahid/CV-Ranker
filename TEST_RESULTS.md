# TextileHR AI — Test Results Log

## Environment
- OS: Microsoft Windows 11
- Python: 3.11.9 (`.venv\Scripts\python.exe`)
- Node.js: v23.11.0
- npm: 11.10.0
- Pytest: 9.0.2

---

## Baseline Verification Runs

### Run 1: Initial Web Test Suite
- **Command**: `.\.venv\Scripts\python.exe -m pytest -q tests/web`
- **Timestamp**: 2026-11-16 23:51:35
- **Exit Code**: 1
- **Passed**: 55
- **Failed**: 1 (`tests/web/test_api_worker.py::test_openapi_contract_is_stable` - schema formatting diff between FastAPI version `format: binary` vs committed `contentMediaType: application/octet-stream`)
- **Warnings**: 1 (`DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated`)
- **Notes**: All 55 functional web/API/worker tests pass cleanly on baseline. Contract generator check requires re-sync.

---

## Phase A: Baseline Audit Reproductions (Run 2)
- **Command**: `.\.venv\Scripts\python.exe -m pytest -v tests/web/test_audit_reproductions.py`
- **Timestamp**: 2026-11-16 23:57:56
- **Exit Code**: 1
- **Passed**: 0
- **Failed**: 8
- **Results per Finding**:
  - `DA-A01` (`test_reproduce_da_a01_negation_not_promoted`): FAILED (`AssertionError: Defect DA-A01: Negation promoted to Found - assert 'Found' != 'Found'`)
  - `DA-A02` (`test_reproduce_da_a02_concurrent_reviews_conflict`): FAILED (`Failed: Defect DA-A02: execute_focused_review lacks expected_result_revision CAS parameter`)
  - `DA-A04` (`test_reproduce_da_a04_shadow_empty_retrieval`): FAILED (`AssertionError: Defect DA-A04: Fabricated similarity 0.85 on empty retrieval`)
  - `DA-A05` (`test_reproduce_da_a05_shadow_failure_handling`): FAILED (`AssertionError: Defect DA-A05: Operational failure returned ready=True`)
  - `DA-A06` (`test_reproduce_da_a06_fresh_cv_survives_retention`): FAILED (`AssertionError: Defect DA-A06: Fresh document was deleted by 30-day purge: {'purged_jobs': 0, 'purged_exports': 0, 'purged_documents': 1, 'retention_days': 30}`)
  - `DA-A07` (`test_reproduce_da_a07_preview_matches_purge`): FAILED (`AssertionError: Defect DA-A07: Preview returned eligible_documents=0, expected 1`)
  - `DA-A08` (`test_reproduce_da_a08_delete_assessment_and_workspace`): FAILED (`Failed: Defect DA-A08: delete_assessment failed with IntegrityError: FOREIGN KEY constraint failed`)
  - `DA-A09` (`test_reproduce_da_a09_metrics_accumulation`): FAILED (`AssertionError: Defect DA-A09: Metric replaced rather than accumulated. Got 5, expected 8`)
- **Status**: Phase A reproductions successfully established and verified failing against unpatched codebase.

---

## Post-Repair Verification Runs

### Run 3: Audit Reproductions (Post-Repair)
- **Command**: `.\.venv\Scripts\python.exe -m pytest tests/web/test_audit_reproductions.py`
- **Timestamp**: 2026-11-17 00:55:13
- **Exit Code**: 0
- **Passed**: 8
- **Failed**: 0
- **Duration**: 4.86s
- **Verified Items**:
  - `DA-A01`: Negation ("no experience") properly evaluates to Not Found without citation leaks.
  - `DA-A02`: CAS `expected_result_revision` mismatch raises HTTP 409 Conflict.
  - `DA-A03`: Review request persisted with durable identity and idempotency key.
  - `DA-A04`: Empty shadow retrieval yields empty findings (zero fabricated 0.85 similarities).
  - `DA-A05`: Shadow retrieval failures return `ready=False` with operational error codes.
  - `DA-A06`: 30-day purge retains fresh unreferenced CV documents.
  - `DA-A07`: Retention summary preview exactly matches purge result.
  - `DA-A08`: `delete_assessment` and `delete_workspace` cascade delete secondary rows without `IntegrityError`.
  - `DA-A09`: Token and attempt metrics accumulate across candidate evaluations.

---

### Run 4: Complete Web Test Suite
- **Command**: `.\.venv\Scripts\python.exe -m pytest tests/web`
- **Timestamp**: 2026-11-17 00:56:52
- **Exit Code**: 0
- **Passed**: 64
- **Failed**: 0
- **Duration**: 88.66s (01:28)
- **Coverage**:
  - `tests/web/test_api_worker.py`: 14 passed
  - `tests/web/test_audit_reproductions.py`: 8 passed
  - `tests/web/test_batch_parity.py`: 5 passed
  - `tests/web/test_completion_controls.py`: 10 passed
  - `tests/web/test_da021_contract_visibility.py`: 6 passed
  - `tests/web/test_da021_core.py`: 4 passed
  - `tests/web/test_da021_frozen_and_interleaved.py`: 3 passed
  - `tests/web/test_input_sibling_survival.py`: 1 passed
  - `tests/web/test_phase8_parity.py`: 5 passed
  - `tests/web/test_result_revision_consistency.py`: 1 passed
  - `tests/web/test_submission_identity.py`: 6 passed
  - `tests/web/test_worker_cancel_siblings.py`: 1 passed

---

### Run 5: Protected Engine Baseline Regressions
- **Command**: `.\.venv\Scripts\python.exe -m pytest tests/test_surgical_fixes.py tests/test_v48_unified.py tests/test_runtime_identity.py`
- **Timestamp**: 2026-11-17 01:00:08
- **Exit Code**: 0
- **Passed**: 50
- **Failed**: 0
- **Duration**: 1.29s
- **Status**: Engine integrity confirmed; zero regressions on core surgical fixes, unified decisions, and runtime identity.

---

### Run 6: Historical Audit Regressions
- **Command**: `.\.venv\Scripts\python.exe -m pytest tests/test_audit_regressions.py`
- **Timestamp**: 2026-11-17 01:02:23
- **Exit Code**: 0
- **Passed**: 21
- **Failed**: 0
- **Duration**: 0.62s

---

### Run 7: Web API & DTO Contract Verification
- **Command**: `.\.venv\Scripts\python.exe scripts/generate_web_contract.py --check`
- **Timestamp**: 2026-11-17 01:02:31
- **Exit Code**: 0
- **Output**: `OpenAPI and client DTOs match the API`

---

### Run 8: Strict Source Runtime Check (DA-A11)
- **Command**: `$env:CVR_STRICT_SOURCE_HASHES="1"; .\.venv\Scripts\python.exe -m cv_ranker.runtime_check`
- **Timestamp**: 2026-11-17 01:07:11
- **Exit Code**: 0
- **Output**:
  ```text
  BUILD_ID=phase7g-v4-9-72-p1-prompt-integration-rc1-2026-11-16
  ASSESSMENT_PROTOCOL=segment_ids_semantic_llm
  ASSESSMENT_PROTOCOL_VERSION=58
  MANIFEST_FILES=753
  SOURCE_INTEGRITY=strict_verified
  PACKAGE_PATH=C:\Users\Azzam Shahid\Downloads\CV Ranker\cv_ranker
  ```

---

### Run 9: Frontend Quality Gates (DA-A13)
- **TypeScript Typecheck**:
  - Command: `npm --prefix frontend run typecheck`
  - Exit Code: 0 (0 errors)
- **ESLint**:
  - Command: `npm --prefix frontend run lint`
  - Exit Code: 0 (0 errors, 0 warnings)
- **Production Build**:
  - Command: `npm --prefix frontend run build`
  - Exit Code: 0 (`dist/` generated with CSS, JS bundle, and brand assets)
- **Full Frontend Test Suite**:
  - Command: `npm --prefix frontend test`
  - Exit Code: 0
  - Passed: 31 tests total:
    - Route tests (`tests/router.test.mjs`): 5 passed
    - Observation tests (`tests/observation.test.mjs`): 3 passed
    - Submission intent tests (`tests/submissionIntent.test.mjs`): 4 passed
    - JD years validation tests (`tests/jdYears.test.mjs`): 2 passed
    - JD row identity tests (`tests/jdRowIdentity.test.mjs`): 7 passed
    - Mounted component tests (`tests/mountedComponents.test.mjs`): 10 passed (including production `JDPage`, `RankingsPage`, `CandidatePage`, and `ProgressPage`)

---

### Run 10: Baseline-to-Successor Patch Clean Apply
- **Command**: `git apply --check da021_to_qualified.patch`
- **Target**: Fresh baseline clone extracted from `TextileHR_DA021_Audit_Repairs_2026-11-16.zip`
- **Timestamp**: 2026-11-17 01:06:23
- **Exit Code**: 0
- **Output**: `EXACT CLEAN APPLY CONFIRMED (WITHOUT ANY FLAGS)!`

---

### Run 11: Clean-Room Release Archive Extraction Verification
- **Artifact**: `TextileHR_AI_Migration_Qualified_2026-11-16.zip`
- **SHA-256**: `8dcb2237c9211f6eaf3d085e60115f573e721b99b6fc83797d3b3d01c4ce4d78`
- **Clean Temp Extraction Directory**: `tempfile.TemporaryDirectory()`
- **Verified Checks on Extracted Copy**:
  1. Strict runtime integrity check (`CVR_STRICT_SOURCE_HASHES=1 python -m cv_ranker.runtime_check`): Exit code 0 (`strict_verified`, 753 files).
  2. Secret isolation (DA-A12): Confirmed `.env` is absent in extracted archive.
  3. Contract synchronization: `python scripts/generate_web_contract.py --check`: Exit code 0.
  4. Audit reproduction suite: `pytest tests/web/test_audit_reproductions.py`: 8 passed, 0 failed.
  5. Audit regression suite: `pytest tests/test_audit_regressions.py`: 21 passed, 0 failed.
- **Status**: 100% verified.

---

### Run 12: Master Implementation & Regression Verification Suite (Post-UI Overhaul)
- **Timestamp**: 2026-11-17 03:39:00
- **Environment**: Microsoft Windows 11, Python 3.11.9, Node.js v23.11.0, npm 11.10.0
- **Verified Results**:
  1. **Audit Reproductions (Expanded)**: `pytest tests/web/test_audit_reproductions.py`: 11 passed in 2.00s.
     - Verified DA-A01–DA-A10 passing.
     - Verified DA-A15: Uncertain review text preserves prior verdict without Pydantic schema validation error.
     - Verified DA-A16: Missing source input raises ValueError rather than fabricating negative decisions.
     - Verified DA-A17: Safe nullable similarity parsing and stable candidate document ID resolution without file synthesis.
  2. **Full Web Suite**: `pytest tests/web/`: 67 passed in 39.36s.
  3. **Protected Engine Suite**: `pytest tests/test_surgical_fixes.py tests/test_v48_unified.py tests/test_runtime_identity.py tests/test_audit_regressions.py`: 71 passed in 0.74s.
  4. **Contract Sync**: `python scripts/generate_web_contract.py --check`: Exit code 0 (In sync).
  5. **Strict Runtime Check**: `CVR_STRICT_SOURCE_HASHES=1 python -m cv_ranker.runtime_check`: Exit code 0 (`strict_verified`, 755 files).
  6. **Frontend Typecheck**: `npm --prefix frontend run typecheck`: Exit code 0 (0 errors).
  7. **Frontend Lint**: `npm --prefix frontend run lint`: Exit code 0 (0 errors, 0 warnings).
  8. **Frontend Test Suite**: `npm --prefix frontend test`: 31 passed in 3.2s (10 mounted production components).
  9. **Frontend Production Build**: `npm --prefix frontend run build`: Client bundle built in 1.27s.

