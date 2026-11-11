# CV Ranker 4.9.45 — Phase 2E security and operations foundation

**Date:** 10 November 2026  
**Assessment build:** `phase7g-v4-9-43-mixed-batch-recovery-2026-11-10` (unchanged)  
**Protocol:** `segment_ids_semantic_llm` v32 (unchanged)  
**Interface:** `4.9.45`

## Changes in this release

### Access control and safe defaults

- Defaults to **local-only** Streamlit binding on `127.0.0.1`. `CVR_ACCESS_MODE=local` refuses an unspecified, wildcard or non-loopback server listener. This is a binding safety check, not user authentication.
- Added optional `CVR_ACCESS_MODE=oidc` integration with Streamlit `st.login()` and `st.user`. Requires explicit individual `CVR_ALLOWED_EMAILS` membership and a Boolean `email_verified` claim before dashboard access. Missing/unknown mode, absent allowlist, unverified identity and nonmember accounts fail closed.
- Streamlit config enables XSRF/CORS, disables static file serving, limits default upload payloads to 48 MiB and messages to 64 MiB. JD/CV widgets use their 10 MiB per-file cap; signed recovery import has a 48 MiB widget cap.
- OIDC secrets and alternative `secrets.*.toml` files are excluded from Git and generated source manifests, along with `.env.*` private variants, local recovery caches and common private-key extensions.

### Local embedding-cache concurrency and confidentiality

- SQLite vector caches refuse symlink paths and use owner-only database permissions on POSIX where supported; existing cache content is retained.
- The cache enables WAL, secure deletion and a bounded 15-second busy timeout for better concurrent connection behavior.
- Added multi-connection tests writing unique keys concurrently and verifying completed reads and rows. These **do not** certify large-scale multi-user loads or cross-tenant isolation.

### Production readiness diagnostics and documentation

- Added `python -m scripts.production_preflight` for no-network integrity, local bind, Streamlit protection and package-secret exclusion checks.
- Added `--remote` and `--json` for deployment checklists and CI. Remote mode intentionally flags missing external OIDC/TLS verification, encrypted durable storage and operational acceptance instead of claiming the deployment is safe.
- Added `docs/PRODUCTION_SECURITY.md` with data-flow sensitivity, identity-provider setup, local/cloud privacy limits, manual retention procedures and a remaining production release-gate checklist.

## Compatibility

No changes to the assessment prompt, source-grounded validation, frozen JD identity, R001/R008 cases, Found-only scoring, weighted ranking or cloud request budgets. The assessment build and protocol identifiers stay unchanged so already validated compatible v32 decisions do not need reevaluation due to UI-only security additions.

## Deliberate limitations

- Local loopback restrictions cannot detect a reverse proxy or tunnel that exposes the app externally; administrators must enforce network isolation.
- Optional OIDC is a starting access gate. Identity-provider integration, TLS termination, group/role policies, tenant-scoped data isolation and live login sessions require deployment-specific acceptance. Do not publish this to an untrusted network as-is.
- Signed recovery is still **manual and plaintext**, not an encrypted durable job store. Filesystem caches and downloads require a separately approved retention policy and secure storage.
- Real model/provider accuracy and behavior under production load have not been certified by offline tests. Human review remains mandatory.

**Release classification:** Hardened supervised local testing build, **not production-certified hiring automation**.
