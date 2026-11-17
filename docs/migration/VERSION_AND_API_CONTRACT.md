# Version and contract boundary

- Assessment engine: preserved v4.9.72 P1, protocol **58**; no prompt, scoring or semantic revision.
- API: `backend/api.py` development v0.2.0 under `/api/v1`.
- SQLite schema: `backend/storage.py` **version 3** with additive retry eligibility and recovery acknowledgement fields.
- FastAPI DTOs: `backend/contracts.py` defines outward response models for jobs, source documents, workspaces, scoring projections, exports and events.
- Type generation: `python scripts/generate_web_contract.py` emits `backend/openapi.generated.json` and `frontend/src/api.generated.d.ts`. `--check` compares full deterministic content. The frontend typed client consumes those DTO interfaces and uses Zod parsers on server responses.
- Frontend versions declared exactly in `frontend/package.json` but **not installed in this environment**. No valid lockfile or Vite build is claimed.
- The assessment result identity is independent of UI version. Weight-only projections must not invalidate semantic evidence or call the model.
- Unknown-delivery resolution requires operator acknowledgement; never automatically reset a provider operation ledger just to progress.


**0.2.1:** schema 4 adds `submission_tombstones`; read-only `GET /submissions/{intent_key}` supports stable UI submission recovery. No semantic protocol version change.
