# TextileHR AI — DA021 audit repair execution and remaining acceptance

**Date:** 16 November 2026. **Release state: engineering repair checkpoint, NOT a complete or runnable React/FastAPI migration.** This is an implementation report against the uploaded 0.2.1 archive, not a promise that unavailable frontend build/dependencies have passed.

## Exact input and preserved assessment authority

- Baseline: `TextileHR_AI_React_FastAPI_Migration_0.2.1_Engineering_Checkpoint_2026-11-16(2).zip`, SHA-256 `917ec0a6af698056298fe757e64a4c363bb930736a32f948e6921c56a2d79e37`.
- Reference: supplied `TextileHR_0.2.1_Deep_Audit.md` and uploaded `Pasted text(20261116-151349).txt`, DA021 repair specification.
- All **61** Python files under `cv_ranker/` remain byte-identical. Protocol **58**, P1 prompts, Found/Transferable/Not Found, source provenance and Python scoring remain authoritative. All original RWML SVG assets are byte-identical. Streamlit remains supported for rollback.

## Reproduced or corrected defects

The authoritative item-by-item status lives in `DA021_REPAIR_REGISTER.csv`. The actual changes include:

- **DA021-01:** missing `Message` import repaired; Tailwind configuration converted from CommonJS to ESM; TypeScript strictness retained, no React 16 fallback. **Clean npm install, lint, full typecheck, Vite build and browser testing are still blocked by unavailable package registry and package cache.**
- **DA021-02:** source-bound editable JD rows use explicit Pydantic types, with nullable/nonnegative numeric minimum years; frontend Zod and form parsing support null and decimal years without coercing bad text into zero. Backend & standalone pure TS tests passed; actual React client-validation test requires npm.
- **DA021-03:** JD page refreshes persisted workspace state on entry/focus; draft identity, dirty edits, conflict and reload controls added. No actual mounted React/browser verification was possible.
- **DA021-04:** repeated Cancel cannot prematurely release a live owner's lease or enable a second worker to claim it. Fenced worker acknowledges cancellation; DB/worker regression passed.
- **DA021-05:** stale-worker reconciliation runs periodically during worker operation, not once at startup. Lease loss remains conservative unknown-delivery; controlled worker-loop test passed.
- **DA021-06:** each new assessment saves a frozen UTC assessment date, source IDs, JD revision, engine build and settings fingerprint; worker passes the same date to every candidate, resumes with it, checks alias/eligibility identity and retains response metadata in aggregate reports. Three-candidate cancellation/multi-day fake-clock resume test passed. Legacy jobs missing trustworthy context must start a new assessment.
- **DA021-07:** server-wide filtered paging and totals; candidate direct-weighted endpoint independent of first 50 rows; source-ID identity; UI paging and stale-page revision pinning. API 1/50/51/200-candidate tests passed, browser navigation not verified.
- **DA021-08/09:** one transactional result/weight/evidence snapshot per operation; rankings return that snapshot's revisions, exports only publish after a second transactional version check. The application deletes orphan temporary exports on conflict. Controlled revision-interleaving tests passed.
- **DA021-10/11:** new event-observation epoch on Resume/unknown recovery; terminal or paused states stop event and fallback polling; single-flight requests, reconnect backoff and monotonic event acceptance. Pure Node policy tests pass; mounted-component/network tests are still required.
- **DA021-12:** duplicate identical JD approval is idempotent; changed already-approved content returns HTTP 409 requiring a new revision, never falsely confirming old frozen content. API & persistence tests passed.
- **DA021-13:** repaired the generated register so MIG-040, MIG-041 and MIG-053 are **Open**, not falsely 'verified'. A separate 13-row DA021 register distinguishes **implementation status from verification status**.

## Actual executed checks in this environment

| Gate | Result |
|---|---|
| API/worker focused tests except known missing-frontend check | **50 passed**, 1 explicitly excluded in that focused command; exclusion is recorded and does not waive the release gate |
| P1/three-verdict protected regressions | **92 passed** |
| Offline router/observation/submission/JD-years Node tests | **14 passed** (5+3+4+2) |
| DA021 frozen assessment date, export interleaving, rankings interleaving | **3 passed** |
| Deterministic OpenAPI/TypeScript contract generation | **Passed**, 32 paths and 40 DTOs in this environment |
| Full Python regression collection | **Attempted but did not finish within execution timeout**; partial log is evidence only, no invented final count |
| Real npm install | **Failed ENOTCACHED**: `@eslint/js` not cached, and configured npm DNS lookup unavailable |
| Real frontend `npm run typecheck` / `npm run build` | **Failed TS2688**: missing `vite/client` from uninstalled package dependencies; no Vite output created |
| Full frontend lint, React component/browser tests, native Windows tests | **Not executed**; lack of dependency-complete runnable frontend and native Windows environment |
| Live Ollama/OpenRouter, measured token/cost, heldout quality | **Not executed**; no authorized live model test in this run |

The focused test suite and protected engine regressions verify specific properties of the available backend. They **do not** prove the complete supervisor browser workflow or all feature parity.

## Outstanding implementations and gates that cannot be reclassified as fixed

1. **Production frontend:** authentic package lockfile, clean `npm ci`, full TypeScript check, ESLint with zero warnings, Tailwind/Vite production build, SPA/asset test, responsive/mounted browser and accessibility tests. A package registry capable of resolving the declared dependencies is required; no fake lockfile or React 16 fallback was created.
2. **Focused review and explicit optional semantic-shadow integration:** still require full bounded operator action → durable job → shared engine review → validated canonical successor result → audit history, with UI and tests. Merely importing the existing engine functions would not satisfy this requirement.
3. **Durable aggregate provider usage / token cost and automatic configurable retention policy** require implementation, including privacy and operator controls.
4. **Windows 10 / Python 3.11 deployment and actual supervisor workflow qualification**, including cross-tab navigation, SSE disconnections, theme and keyboard tests; live-model quality and billing acceptance remain distinct.

A missing build/feature is a genuine incomplete source/acceptance gate, not an external-benchmark qualification success. **Do not replace the working Streamlit installation with this checkpoint.** No candidate-specific or department-specific verdict shortcuts were introduced.

## Instructions to finish on a supported development machine

With Node 22.12+, a working npm registry, Python 3.11 and the supported Windows host, use a **separate extraction and new data directory**:

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

Review the authentic package lockfile before committing it. Fix any typecheck, lint, or runtime issues rather than skipping. Run the browser on the real FastAPI-served bundle with fictional JD and CVs, then complete the remaining focused-review/semantic/retention implementation rows. `install_web.cmd` and `run_web.cmd` must also pass on Windows. Keep Streamlit as rollback until all listed gates pass.

## Reproducibility

`verification/da021/` contains actual logs for npm failure, typecheck/build failure, available unit and API tests, OpenAPI check and the timed-out broad suite. `scripts/rebuild_manifest.py` verifies the delivered source. Only source code and fictional deterministic tests are packaged; private CV databases, credentials and real user files are not included.
