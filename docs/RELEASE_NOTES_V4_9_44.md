# CV Ranker 4.9.44 — signed recovery and supervisor workflow regression

**Date:** 10 November 2026  
**Assessment build:** `phase7g-v4-9-43-mixed-batch-recovery-2026-11-10` (unchanged)  
**Assessment protocol:** `segment_ids_semantic_llm` v32 (unchanged)  
**UI / recovery format:** `4.9.44` / `1`

## Phase 2C — portable recovery without persistent applicant storage

- Added an explicit **Download signed recovery ZIP** action on the supervisor's ranking page and **Restore a downloaded recovery checkpoint** on Analyze.
- A checkpoint contains the saved source-validated report, final per-criterion judgments, source ledgers, request/evidence metrics, category and individual-JD weights, and resumable candidate entries and cumulative assessment HTTP-attempt budget when available.
- Authentication uses a per-installation 32-byte random secret with HMAC-SHA256. Import checks archive structure, size, signature, build, protocol, frozen JD identity and parsed typed report before it restores state; a mismatched or edited checkpoint is rejected.
- The signing key is stored in ignored `.cv_ranker_cache/recovery_signing.key` with restrictive permissions, **never inside the ZIP**. Keep a secure, separate key backup if migrating installations.
- Restoring displays saved results **without a cloud model call**. Continuing unfinished assessments still requires reuploading exact source files and approving the same frozen JD; existing identity validation and OpenRouter attempt limits remain in force.
- The ZIP includes plaintext applicant excerpts. It is **authenticated, not encrypted**. Users must store/delete it according to their HR privacy and retention rules. No new applicant records are automatically written to a server database.

**Deliberate scope limitation:** This is *manual* restart recovery. It does not survive a crash that happens **before** the reviewer downloads the checkpoint, does not restart running model calls and does not provide an authenticated multi-user job store. Streamlit's active background state is still in memory.

## Phase 2D — offline end-to-end regression

Added `tests/test_v4944_portable_recovery_and_e2e.py`, covering:

1. JD extraction, literal-source reviewer approval, approved JD freeze and two-CV assessment using a realistic **accounting** scenario (profession-neutral behavior).
2. Editable non-default category weights, rank calculation and exact leaderboard CSV agreement.
3. Recovery ZIP export/import preserving candidate report, source ledgers, weights and cumulative provider budget.
4. Historical-session archiving, widget restoration and stale approval/background state removal on import.
5. Rejection of altered ZIPs, wrong signing keys, incompatible builds, inconsistent cloud counters, unexpected ZIP members, oversized data and symlinked local signing-key paths.

Tests use **no paid model calls** and do not establish live OpenRouter/Ollama correctness, external-provider reliability, race-free real browser refreshes, or deployment privacy compliance.

## Compatibility and rollout

The **assessment build and protocol remain unchanged** because this release only adds a recovery transport and offline tests; it does not change model prompting, source validation, per-requirement scoring or candidate ranking rules. Existing compatible v32 assessments do not require paid re-evaluation solely because the UI version changed.

Run `run_tests.cmd`, `run_runtime_check.cmd` and a synthetic full supervisor walkthrough. Do not distribute `.env`, `.cv_ranker_cache/`, uploaded applicant files, local embedding caches or generated reports in the source release.

## Known remaining work before production

- **Automatic restart recovery:** Securely encrypted, access-controlled transactional checkpoints with safe cleanup/retention and bound cloud-request accounting across concurrent workers.
- **Real-model QA:** Repeat JD/CV extraction and citation-validation scenarios with representative consented/synthetic datasets, bounded cloud cost and provider-rate-limit testing; verify R001/R008-style failures remain fixed in practice.
- **Concurrency / security:** Multi-user isolation, authentication, backup-key procedure, deployment monitoring, load tests, authorization review and documentation of provider processing agreements.
- **No-model extraction:** A conservative structural fallback may omit action-only job responsibilities. Reviewers can add such a requirement when it is literally present in the JD. This version deliberately makes no changes to extraction or scoring heuristics.

**Status:** supervisor-assisted local testing release. **Not an autonomous hiring or production-certified deployment.**
