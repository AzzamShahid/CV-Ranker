# TextileHR React/FastAPI source architecture — development checkpoint

**Baseline:** supplied preview SHA-256 `b6b839178e7b9c5af8c7d71096dbf4e8f61b174222871bb70f583f975d634d60`; assessment engine `cv_ranker/` remains P1/protocol 58. No new JavaScript scoring/verdict authority. The original Streamlit entry point is retained for rollback.

## Ownership

- `frontend/` now contains React 19/TypeScript source, React Router 7, Vite 7 and Tailwind 4 integration, reusable semantic components, the original RWML SVGs, the generated API types and a Zod-validated API client. **Dependency installation, a lockfile and the compiled UI are not available in this checkpoint** because npm returned `ENOTCACHED`; FastAPI explicitly serves a `frontend_build_missing` 503 until `frontend/dist` is generated.
- `backend/api.py` declares typed FastAPI routes and Pydantic response models (`backend/contracts.py`). It owns local signed session/CSRF, origin/host/scope checks, API versioning, snapshots and safe file transport, not hiring decisions. `backend/openapi.generated.json` and `frontend/src/api.generated.d.ts` are generated together using `scripts/generate_web_contract.py`.
- `backend/engine_service.py` delegates JD extraction, review validation, assessment, scoring projections, Why and exports to the existing `cv_ranker` source. GET routes do not dispatch generation requests.
- `worker/runner.py` is a separate OS process. It claims queued jobs, invokes only the existing Python engine, and persists independently committed candidates and progress; crashes do not remove persisted completed siblings.
- `backend/storage.py` owns SQLite schema **version 4**, transactions, workspaces/documents, JD draft and approval revisions, weights, idempotency keys, job lease/fence/heartbeat, candidate commits, events, historical imports, exports, deletion protections, provider retry eligibility and recovery decision history. User data stays in the configured private data directory, separate from source.

## Processing and recovery

Each job binds the original approved JD revision, source IDs and submitted provider/model and safety ceilings. Only the Python engine can return the three completed verdicts **Found / Transferable / Not Found**; processing failures are not scored as candidate negatives. A null score is never a completed zero.

A worker that loses its lease pauses an unknown-delivery request rather than blindly reissuing a potentially paid call. The operator can inspect persisted checkpoints and explicitly acknowledge duplicate-charge risk before scheduling unresolved work again. This is an explicit, auditable risk choice, **not** guaranteed provider-side reconciliation or exactly-once delivery. Known provider 429 retries are blocked before the persisted eligible time. Cooperative cancellation cannot undo an already sent provider call.

SSE progress is durable. Snapshot and event watermark are obtained in one read transaction, per-job sequence values are monotonic, `Last-Event-ID` replay is supported, and client deduplication/polling never starts work. The browser is a read-only assessment consumer except for explicit POST/PUT/DELETE operations with CSRF protection.

Completed jobs/exports/unreferenced documents and entire inactive workspaces can be deleted by confirmed actions. Active and unknown-delivery work protects its inputs. External backups are outside automated deletion scope. Historical JSON and supported ZIP exports are imported read-only; prior results are **not** silently reassessed under protocol 58.

## Deployment boundaries

Local loopback, single operator only. No multi-user identity provider, LAN, public hosting, TLS termination or enterprise authorization is qualified. Linux/Python 3.13 worker/process smoke and fictional tests pass; native Windows/Python 3.11 acceptance and live-model accuracy are unverified. **A working web UI cannot be claimed without an actual npm install, typecheck, lint, production Vite build and browser tests.** See `COMPLETION_CHECKPOINT.md`, `RELEASE_QUALIFICATION.md` and the 41-row `PARITY_REGISTER.csv`.


## 0.2.1 continuation
Submission-key lookups and post-deletion tombstones reside in `backend/storage.py`. Incomplete source failures are persisted as candidate input states, not negative verdicts. Event observation policies live in `frontend/src/api/observation.ts`. See `COMPLETION_V3.md`.
