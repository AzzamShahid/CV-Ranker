# TextileHR AI — Master Repair and Qualification Execution Plan

## 1. Baseline Identity and Environment
- **Baseline Package**: `TextileHR_DA021_Audit_Repairs_2026-11-16.zip`
  - **SHA-256**: `aa2eddacf7bbb7a9611d65f9ada9dd802909bc9f7ab20af23e6e66b03d7d31d3`
- **Qualified Release Package**: `TextileHR_AI_Migration_Qualified_2026-11-16.zip`
  - **SHA-256**: `8dcb2237c9211f6eaf3d085e60115f573e721b99b6fc83797d3b3d01c4ce4d78`
- **Environment**: Windows 10/11, Python 3.11.9, Node v23.11.0, npm 11.10.0, pytest 9.0.2
- **Audit Basis**: `TextileHR_Antigravity_Deep_Audit.md` (14 findings: DA-A01 to DA-A14)
- **Directives**: `TextileHR_Antigravity_Master_Repair_Prompt.md`

## 2. Invariants
1. **Generality and source grounding**: No candidate names, filenames, requirement IDs, departments, or benchmark answers hardcoded in matching logic. No constant match scores or fabricated similarities.
2. **Three-way substantive decisions**: Found, Transferable, and Not Found. Operational failures (missing input, embedding failure, network 429) remain explicit operational states, never disguised as candidate capability decisions.
3. **Engine preservation**: All 61 `cv_ranker/` Python files remain byte-identical to the repair baseline.
4. **Scoring integrity**: Zero model calls for weight-only changes. Result and weight revisions must derive from compatible snapshots.
5. **Data safety**: Temporary test stores only. Destructive tests never run against production data. Secrets excluded from release packages and logs.

---

## 3. Ordered Execution Phases

### Phase A: Establish Reproductions and Protect Data
- **Objective**: Implement deterministic failing tests for audit defects before applying fixes.
- **Scope**:
  - Create `tests/web/test_audit_reproductions.py` covering:
    - DA-A01: Negated experience ("I have no experience in Python development") promoted to Found.
    - DA-A02: Concurrent calls to `execute_focused_review` resulting in lost updates.
    - DA-A04: Empty retrieval returning hardcoded `similarity=0.85` in `run_semantic_shadow_diagnostic`.
    - DA-A05: Embedding exception returning `ready=True` with error string disguised as completed finding.
    - DA-A06: Fresh CV document deleted by 30-day retention purge.
    - DA-A07: Retention preview returning `eligible_documents=0` when purge deletes them.
    - DA-A08: `delete_assessment` and `delete_workspace` raising `IntegrityError` due to foreign keys.
    - DA-A09: Metric overwrite when committing 3 then 5 attempts, reporting 5 instead of 8.
  - Verify baseline reproductions fail cleanly.
  - Inspect `.env` privately; ensure `.env` is omitted from distribution and `.env.example` is sanitized.

### Phase B: Repair Retention and Deletion Lifecycle (DA-A06, DA-A07, DA-A08)
- **Objective**: Unified retention planning, age-aware document pruning, and clean cascaded deletion.
- **Affected Paths**: `backend/storage.py`, `backend/api.py`.
- **Implementation**:
  - Implement a single `_retention_plan(workspace_id, retention_days)` function shared by `get_retention_summary` and `purge_retention`.
  - Enforce age threshold on documents: fresh unreferenced CVs (< N days old) survive purge.
  - Revalidate eligibility at purge time under transaction / revision snapshot.
  - Fix `delete_assessment()`: explicitly delete child rows in `focused_reviews`, `semantic_shadows`, `job_metrics`, `job_events`, `exports` before deleting `jobs` row.
  - Fix `delete_workspace()`: delete all child assessment data, documents, drafts, approvals, and reviews before deleting workspace.
- **Acceptance Tests**: Fresh CV survives; expired unreferenced CV pruned; preview matches execution; assessment and workspace delete without foreign key errors.

### Phase C: Repair Focused-Review Semantics and Provider Selection (DA-A01, DA-A03)
- **Objective**: Eliminate substring matching in focused review; wire canonical assessment path with negation handling.
- **Affected Paths**: `backend/engine_service.py`, `frontend/src/api/client.ts`, `frontend/src/pages/Results.tsx`.
- **Implementation**:
  - Remove substring matching (`name.casefold() in segment`).
  - Route focused review through the canonical single-decision engine/evaluator with full source validation, negation handling, and mandatory criteria.
  - Remove client overrides forcing `useLlm: false` and `provider: 'ollama'`. Inherit resolved workspace/job provider and model settings.
- **Acceptance Tests**: Negated experience returns Not Found; supported positives return Found with true citations; client defaults align with job configuration.

### Phase D: Durable Review Requests, Concurrency, and Recovery (DA-A02, DA-A03)
- **Objective**: Durable review request records, compare-and-swap commit on base report revision, and idempotent recovery.
- **Affected Paths**: `backend/storage.py`, `backend/api.py`, `backend/contracts.py`.
- **Implementation**:
  - Enforce compare-and-swap on `expected_result_revision` in `execute_focused_review` to prevent concurrent overwrite.
  - Track review requests with idempotency key, status, and attempt counts.
  - Handle revision conflicts with explicit 409 responses, allowing client-driven retry/refresh.
- **Acceptance Tests**: Overlapping concurrent reviews on different requirements either serialize safely or return a conflict; no silent lost updates.

### Phase E: Truthful Semantic-Shadow Diagnostics (DA-A04, DA-A05)
- **Objective**: Ground semantic diagnostics in actual retrieval results; separate operational failures from completed results.
- **Affected Paths**: `backend/engine_service.py`.
- **Implementation**:
  - Replace constant `0.85` similarity. Project actual retrieval similarity scores and real source spans.
  - When retrieval returns empty, return an empty findings list `[]`.
  - When retrieval or embedding fails, set `ready=False` with safe operational `error_code` (e.g., `EMBEDDING_UNAVAILABLE`), preserving any prior diagnostic revision.
- **Acceptance Tests**: Empty retrieval produces zero findings; embedding error returns `ready=False` and operational error code.

### Phase F: Accurate Usage, Model Identity, and Costs (DA-A09, DA-A10)
- **Objective**: Accumulate attempts across candidates and reviews; capture resolved model identity and explicit pricing.
- **Affected Paths**: `backend/storage.py`, `backend/contracts.py`.
- **Implementation**:
  - In `commit_candidate()`: accumulate request metrics (`total_tokens`, `actual_model_request_attempts`) instead of overwriting on conflict.
  - Capture resolved provider and model in request records; do not fall back to a hardcoded local model string.
  - Distinguish local models ($0.00) from cloud models; if pricing rate is unknown, report cost as unknown rather than a hardcoded generic rate.
- **Acceptance Tests**: Committing 3 then 5 attempts results in 8 accumulated attempts; resolved model name appears accurately.

### Phase G: Real Frontend Component Tests & Browser Integration (DA-A13)
- **Objective**: Mount actual production components (`Workflow.tsx`, `Results.tsx`) in Vitest; verify browser workflow.
- **Affected Paths**: `frontend/tests/mountedComponents.test.mjs`, `frontend/src/pages/Results.tsx`.
- **Implementation**:
  - Update `mountedComponents.test.mjs` to mount real exported components (`Results`, `Workflow`) with proper memory routers and providers.
  - Test JD editing row identity, revision recovery, and review UI controls.
  - Verify complete browser flow using FastAPI + worker with temporary test store.
- **Acceptance Tests**: Frontend test suite passes mounting production components; browser test confirms end-to-end operation.

### Phase H: Historical Regression Protection
- **Objective**: Retain historical regressions AUD-001..AUD-013 and DA021 migration guards (cancellation, stale lease, pagination, export revision consistency).
- **Verification**: Run complete test suite (`tests/web`, `tests/test_*.py`).

### Phase I: Contract Synchronization & Prompt Verification
- **Objective**: Regenerate OpenAPI schema and TypeScript DTOs using `scripts/generate_web_contract.py`.
- **Verification**: `scripts/generate_web_contract.py --check` passes cleanly.

### Phase J: Packaging, Manifest, and Release Qualification (DA-A11, DA-A12, DA-A14)
- **Objective**: Build clean release ZIP, regenerate manifest, verify SHA-256, extract to clean directory, run full checks.
- **Checklist**:
  - [x] Exclude `.env`, secrets, test databases, node_modules.
  - [x] Provide sanitized `.env.example`.
  - [x] Generate whole-package manifest (753 source files).
  - [x] Run runtime check under Windows PowerShell with `CVR_STRICT_SOURCE_HASHES=1` (passed with exit code 0).
  - [x] Package clean ZIP (`TextileHR_AI_Migration_Qualified_2026-11-16.zip`) and compute SHA-256 (`8dcb2237c9211f6eaf3d085e60115f573e721b99b6fc83797d3b3d01c4ce4d78`).
  - [x] Verify clean-room extraction in temporary directory with all test gates passing.
  - [x] Baseline-to-successor patch applied cleanly with `git apply --check` (exit code 0).
