# TextileHR AI migration — 0.2.1 completion checkpoint

**16 November 2026 · Baseline hash:** `08f2a56aea001c6d1574d1a2e4a96f19263be2d2241e85ab47bfa632e1c6ef56`.

**Release verdict:** substantive additional implementation, **NOT completed, browser-ready or production-qualified**. Assessment engine remains **v4.9.72 P1 / protocol 58**, with all 61 Python files under `cv_ranker/` byte-identical to the starting checkpoint. The old Streamlit application is preserved and should remain in use for production.

## Changes implemented against this checkpoint

1. **Submission-intent recovery** (`frontend/src/api/submissionIntent.ts`, `backend.storage.submission`, `GET /api/v1/workspaces/{workspace_id}/submissions/{key}`): one stable, opaque SHA-256 request identity, persisted before POST, shared across tabs, recovered after a lost HTTP response or browser restart. Only a definite HTTP 404 permits a new POST; ambiguous response failures remain pending. An explicit **new independent run** action rotates the intent generation for identical inputs. No CV text, applicant names, settings secrets or raw request payload enter browser persistence.
2. **Deletion tombstones** (`backend/storage.py`, SQLite v4): completed/cancelled job deletion keeps an immutable, workspace-scoped idempotency tombstone. A stale browser using its old key gets HTTP 409 instead of starting another job. Whole-workspace deletion removes the tombstones after checking for active/unknown-delivery requests. Incremental migration v3→v4 tested.
3. **SSE observation** (`frontend/src/api/observation.ts`, `frontend/src/pages/Results.tsx`): monotonic event deduplication, explicit reconnect backoff, fallback polling only when SSE unhealthy, terminal-state cleanup, and coalesced single-flight job/ranking refreshes. These source changes pass offline pure-logic tests, **not real browser or network-interruption acceptance**.
4. **Candidate results** (`backend/contracts.py`, `frontend/src/api/client.ts`, `frontend/src/pages/Results.tsx`): explicit Pydantic/Zod structures for candidate summary, frozen requirements, criteria, original-source checkpoints and failure states. The UI now reads the engine's actual `Checkpoints` field rather than the nonexistent `Evidence checkpoints`; shows JD quotation, source text and processing warnings. Primary engine score is distinguished from canonical weighted score and weight revision.
5. **Complete batch handling**: real HTTP→SQLite→Python engine integration tested with **1, 6, 7, 12 and 13 fictional candidate CVs**. Every document has a distinct committed result and its own source identity. This checks candidate batch sizes, not a live provider's outstanding compound-review batching.
6. **Unreadable candidate isolation** (`worker/runner.py`): on an actual `DocumentError` or missing original candidate source, record an incomplete/no-verdict candidate with a null score and a sanitized input message. Other CVs continue through the existing Python engine. No missing evidence is converted to Not Found.
7. **Cancellation after a provider reply**: once a candidate engine result has returned, an in-flight Cancel no longer discards that result before persistence. It commits under the worker fence, then prevents scheduling the next candidate. Resume skips the committed siblings. Tests verify the successful operations are not reissued.
8. **Result/export revision consistency**: regression verifies weighted revision, saved assessment revision, source UUIDs, original evidence and export behavior; stale export revision requests return conflict, while weight-only changes leave source assessment revision untouched.
9. **Completed parity register**: `PARITY_REGISTER.csv` includes 56 individually identified entries, specific implementation, evidence, status and remaining gates. The original 41-row parity source is retained as `PARITY_REGISTER_SOURCE.csv`; use `generate_completion_register.py` to reproduce the current register.

## Actual local verification

- Python 3.13.5, Node 22.16.0; FastAPI and other actual package versions are in `verification/completion_v3/runtime_versions.txt`.
- Protected engine/P1/three-verdict regression subset: **92 passed**.
- Node route, SSE observation and submission-intent tests: **12 passed** (5+3+4). These are real Node tests of route/intent/observation modules, *not* React component or browser tests.
- Additional API/worker checks include lost response, concurrent idempotent requests, restart, batch boundaries, zero-model weight revisions, missing input, canceled in-flight replies, source evidence, and export revisions.
- OpenAPI and generated TypeScript DTOs are derived from the same current FastAPI source and verified by `python scripts/generate_web_contract.py --check`.
- Full regression (post-repair, before final packaging): **1,638 passed, 21 failed, 10 collection errors**. 20 failures and all ten collection errors are unavailable Streamlit/LangChain modules; one failure is a required served-frontend test returning **503 instead of 200** because the real Vite bundle cannot be built here. This test remains enabled. See `verification/completion_v3/broad_pytest.log`. The focused new completion-control suite passes **24**, existing protected engine suite passes **92**, and offline Node route/observation/submission tests pass **12**. Strict integrity showed **720** hashed entries before final evidence/log updates.

## Not implemented or not verified

**Open implementation:** the React/Vite production bundle does not exist, an authentic npm lockfile and full package-based accessible shadcn UI are not present, the explicit bounded focused-judge job / canonical successor publication is not wired, the semantic-shadow job/UI is not wired, and automatic retention scheduling is absent. The bundle/build failure is not reclassified as successful implementation.

**External qualification:** npm registry lookup is blocked by DNS/cache (`ENOTCACHED` for `@eslint/js`), producing downstream missing `vite/client` TypeScript definition and failed `npm run build`. Native Windows 10/Python 3.11 and real browsers cannot be qualified in this Linux environment; authorized live-model/token-cost quality measurements also remain absent. No screenshots are claimed.

**Security boundary:** this is a loopback-only, single-operator application. No public hosting, multi-tenant permissions, external-billing exactly-once guarantee, automatic backup deletion or provider reconciliation assertion is made.

## Required next acceptance commands on a machine with package access

```powershell
cd frontend
npm install --package-lock
npm ci
npm run typecheck
npm run lint
npm test
npm run build
cd ..
python scripts/generate_web_contract.py --check
python -m pytest -q tests/web
python -m pytest -q
```

Then inspect the **actual running** FastAPI-served React application at desktop/mobile viewports, direct candidate deep-link refresh, light/dark logos, accessibility, and native Windows worker installation. Complete the remaining explicit implementation rows in the parity register before claiming migration acceptance.

## Rollback

Do not overwrite your stable Streamlit directory or data. Deploy into a separate extraction directory and use `TEXTILEHR_DATA_DIR` for a new local store. Stop only this installation's worker/API with `stop_web.cmd`. Restore backups into an empty directory after hash verification; backup ZIPs are plaintext and must be protected. Continue using the original stable Streamlit installation until this package passes all remaining acceptance gates.
