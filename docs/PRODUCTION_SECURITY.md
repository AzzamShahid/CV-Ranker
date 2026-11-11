# TextileHR AI — deployment security and operational acceptance

**Current implementation:** Supervisor Edition 4.9.54 (Phase 2E foundation)  
**Risk classification:** Applicant CVs, identity data, hiring assessments and source quotations are confidential HR records.  
**Deployment status:** **Local supervised use only by default. Public or multi-user production is not approved by this release.**

## 1. Threat boundaries and data lifecycle

| Boundary | Data handled | Safeguard now | Remaining production work |
|---|---|---|---|
| Browser / Streamlit UI | Original uploads, frozen JD, personal CV evidence and ranking tables | Local-only listener by default; XSRF and CORS enabled; uploads limited | Review browser policies, shared-device access, external ingress and security headers |
| Authentication / authorization | OIDC identity information | Optional Streamlit OIDC login plus **verified-email exact allowlist** before any dashboard access | Choose real identity provider, verify callback/TLS, session expiry/MFA and role management |
| Inference | JD text and retrieved CV passages | Local Ollama option; OpenRouter requires explicit configured key, bounded attempts | Privacy assessment and vendor-processing agreement; live retries, cost and rate testing |
| Temporary files | Upload bytes in per-run temporary folders | Temporary-directory cleanup on normal exit; no extra server-side raw-file repository | Crash cleanup verification and data-handling policy on each operating system |
| Embedding cache | SHA-derived keys and applicant-derived float vectors (not plaintext CV text) | Restrictive local file permissions where supported; SQLite busy timeout, WAL and secure delete | Per-user/per-tenant isolation, encryption at rest, retention and backup policy |
| Streamlit session | Candidate decisions, source excerpts, resume counters, selected model | Session-scoped state with explicit signed recovery export | Encrypted durable transactional jobs, role-based access and crash-consistent accounting |
| Reviewer downloads | Plaintext ZIP/CSV/JSON and signed recovery archives | Manual, clear-sensitive labeling; signed recovery tamper check | Secure download distribution, retention, access logging and key handling |

**No authentication mode solves data isolation by itself.** Shared local vector caches, a process-wide worker pool and administrator-accessible disk state remain. Until a tenant-scoped design and load test are approved, do **not** run this as a public multi-customer SaaS.

## 2. Safe local installation (current recommended mode)

The bundled `.streamlit/config.toml` pins `server.address = "127.0.0.1"`, enables CORS/XSRF protections, disables static serving, limits per-message/upload sizes and disables browser usage statistics. The UI adds document-specific limits: **10 MiB each for JD/CVs**, **48 MiB for a signed recovery ZIP**. The existing `run_ui.cmd` also specifies localhost explicitly.

In `.env`:

```dotenv
CVR_ACCESS_MODE=local
```

Run:

```powershell
.\.venv\Scripts\python.exe -m scripts.production_preflight
.\run_ui.cmd
```

**Local mode is not a password.** It only refuses operation when Streamlit is configured to bind to a non-loopback address. A reverse proxy, SSH tunnel, port forward or container mapping could still expose a loopback service. Ensure your network and OS access policies prevent that. Do not publish the Streamlit port directly.

## 3. Organization sign-in for a future private deployment

To prepare for a remotely reachable, organization-controlled installation:

1. Choose an OpenID Connect identity provider (for example, Entra ID, Google, Okta or Auth0) and register the exact HTTPS redirect URI. Enable MFA at the provider.
2. Configure Streamlit's official OIDC settings in a locally protected `.streamlit/secrets.toml` (or the platform's encrypted secret store). This file is excluded from the release manifest and `.gitignore`.
3. Set the access mode and an **explicit list of individual approved reviewer email addresses**. The app rejects wildcard domains, missing `email_verified: true`, missing email claims and identities outside the list.
4. Validate that a nonmember, an unverified account, a new browser session and expired sessions cannot access JD or CV results. Verify sign-in, sign-out and reauthentication manually.
5. Restrict network ingress to the managed HTTPS proxy. Configure the cookie secret, TLS certificates, WebSocket support, correct redirect host, allowed origins and sticky sessions if needed. Do not disable XSRF/CORS to make a proxy appear to work.

Example of the **shape only** of a private Streamlit secret configuration (replace every placeholder in a file that is **never committed**):

```toml
[auth]
redirect_uri = "https://internal-hr.example.com/oauth2callback"
cookie_secret = "REPLACE_WITH_LONG_RANDOM_SECRET"
client_id = "REPLACE_WITH_IDP_CLIENT_ID"
client_secret = "REPLACE_WITH_IDP_CLIENT_SECRET"
server_metadata_url = "https://YOUR-IDP/.well-known/openid-configuration"
```

Example environment settings:

```dotenv
CVR_ACCESS_MODE=oidc
CVR_ALLOWED_EMAILS=reviewer1@example.com,reviewer2@example.com
```

The UI requires `st.user.is_logged_in`, an **exact** allowlisted email and the OIDC claim `email_verified` equal to Boolean `true` before rendering any application tabs. If an identity provider does not supply this claim, integrate and verify the provider's identity contract before enabling access; the app will intentionally deny it.

**Never expose a remote listener merely by changing `server.address`.** Mode `oidc` is necessary for the implemented gate, but not sufficient evidence of secure external deployment.

Official references: [Streamlit authentication](https://docs.streamlit.io/develop/concepts/connections/authentication), [Streamlit configuration](https://docs.streamlit.io/develop/api-reference/configuration/config.toml).

## 4. Offline production preflight

```powershell
.\.venv\Scripts\python.exe -m scripts.production_preflight
.\.venv\Scripts\python.exe -m scripts.production_preflight --remote
.\.venv\Scripts\python.exe -m scripts.production_preflight --remote --json
```

- The first command verifies the local configuration and release hashes; it does not upload CVs, touch provider APIs, print secrets or change data.
- `--remote` deliberately returns a **nonzero exit code** until externally verifiable security, privacy and reliability requirements are complete. A source-only check cannot verify a real login provider, HTTP edge policy or organizational approvals.
- `--json` produces a minimal, privacy-safe summary suitable for CI; it does not include candidate names, model prompts or configured reviewer email addresses.

Do not treat an automated PASS as approval to process live applicant data.

## 5. Operations, retention and incident response

1. Before a real run, record the responsible supervisor, authorized hiring purpose, approved source of CVs, consent/legal basis, local/cloud provider choice and spending cap. Restrict file access to the project and OS account.
2. Restrict and protect `.env`, `.streamlit/secrets.toml`, `.cv_ranker_cache/recovery_signing.key`, `outputs/` and any generated report, recovery ZIP or temporary files. On POSIX, local SQLite DB permissions are tightened to the owner where supported; Windows requires appropriate NTFS ACLs.
3. Maintain a written retention schedule covering applicant exports, browser downloads, SQLite `*.db`, SQLite `-wal`/`-shm` companions, uploaded originals, model-provider logs and signing-key backup. **This release does not implement a scheduled eraser or encrypted database.** Do not rely on reinstallation to purge data.
4. Monitor provider health/429/503 counts, request-budget utilization, incomplete/withheld rankings, elapsed batch time, memory and SQLite busy/locked errors. Central logs and alerts must be configured by the deployment operator and must not contain CV passages, raw JD/CV uploads, API keys or session tokens.
5. For an incident, stop ingress and model calls, preserve minimum necessary audit evidence under authorized access, rotate exposed credentials, notify the responsible security/HR team and follow the organization's breach-response procedure.
6. Verify backups and restoration using **synthetic** data before any live cutover. The signed recovery ZIP remains plaintext and manual; its local signing key is not a substitute for encryption or a proper secret manager.

## 6. Production release gates still open

- [ ] Named HR data owner, lawful processing basis, retention/deletion schedule and provider agreements approved.
- [ ] Identity provider, MFA, allowed reviewers, TLS edge, session expiration and independent access tests completed.
- [ ] Encrypted, per-tenant durable storage and transactional progress recovery implemented and tested across crashes.
- [ ] Cross-user cache and job isolation, concurrency limits, background worker supervision and lock/contention load tests approved.
- [ ] Representative, consented or synthetic real-model E2E evaluation across professions; no R001/R008-style evidence failures, no unbounded retries.
- [ ] Monitoring, alerting, security logging, backups, recovery drills and incident ownership assigned.
- [ ] Penetration testing, deployment change-control and supervisor acceptance completed.

**Until the open gates are closed, keep use supervised and local. No automated hiring decisions.**
