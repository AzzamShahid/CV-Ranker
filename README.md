# CV Ranker — Supervisor Edition

Evidence-first, configurable JD-to-CV screening with original source citations, transparent scoring and reviewer-facing explanations.

**Current interface:** 4.9.68 (14 November 2026)  
**Assessment build:** `phase7g-v4-9-68-prompt-first-contract-evaluation-2026-11-14`  
**Protocol:** `segment_ids_semantic_llm` v54  
**Status:** local supervisor-review application; not an autonomous hiring decision system.

## What it does

1. Read one job description from text, Markdown, PDF or DOCX.
2. Extract JD criteria with YAKE-assisted structured interpretation, and let the reviewer **edit and approve** the frozen requirement list.
3. Compare multiple CVs to the **same approved requirements**, retaining original source segment IDs and an independent **Why this decision** for every criterion.
4. Distinguish **Found**, **Transferable**, **Not Found** and **Unverified**. Only source-verified **Found** earns direct points; technically unverified criteria earn zero pending review, while a clearly labeled provisional lower-bound score and position remain visible. A provisional position is **not a fully verified hiring rank**.
5. Configure category weights (default **10% Experience / 10% Education / 80% JD**) and individual requirement shares **after JD extraction**, without making more model calls. Required and Preferred items share one JD scoring pool by default; the legacy split toggle changes display only. New optional **weighted split** mode assigns explicit Required/Preferred group shares before per-criterion shares (see release notes).
6. Review a ranked leaderboard with a separate **Why this CV received its ranking**, individual evidence, review notices and optional technical diagnostics. Download CSV, JSON or a complete reviewer ZIP.
7. Download a **signed recovery checkpoint ZIP** to reopen saved results after a browser refresh/server restart; incomplete runs can resume only after their identical JD/CVs and approved criteria are supplied again.

The current AI-assisted pipeline uses **local Ollama EmbeddingGemma retrieval** with a selectable **Ollama or OpenRouter assessment model**. The optional diagnostic/research scripts are separate from the authoritative final score. There are no hardcoded profession-specific matching answers. The employer's explicitly accepted academic options and a completed higher qualification in the same exact subject can meet a lower academic minimum, while relevant work from a different discipline can be displayed as **Transferable** only when supported by cited original CV duties; it never earns direct points.

**v4.9.68 prompt-first contracts and paired evaluation (experimental wording, not live-qualified):** Six of the thirteen system-prompt definitions now give clearer instructions about original-source completeness, independent semantic reversals, original compound proof/AND-OR leaves, JD inherited priority and typing. Two optional JD request builders now JSON-bind untrusted source text rather than using breakable tags/headers. The shipped packet A/B runner verifies identical fictional user packets and schemas in isolated v53/v54 trees; actual model-accuracy improvement is **not claimed**, and no provider requests were made. See [release notes](docs/V4968_RELEASE_NOTES.md), [13-prompt/16-builder ledger](docs/V4968_PROMPT_AND_BUILDER_LEDGER.json), [verification report](docs/V4968_VERIFICATION_REPORT.md), and [Windows A/B handoff](verification/PROMPT_FIRST_WINDOWS_HANDOFF.md). Protocol v54 requires a fresh assessment of prior v53 decisions.

**v4.9.67 per-operation recovery and oracle-verified differential (partial engineering release):** Fixes a mixed semantic batch in which a completed/unknown A prevented fresh B from running, while the old caller falsely stamped both as attempted. New per-operation SQLite claims, result SHA references, batch packet identity, partial-row validation and concurrency/legacy-table migration tests preserve independent progress without automatically retrying unknown provider delivery. Replaces the unsafe same-tree differential success path with a source-hash authenticated, version-specific fixed oracle. Adds a Found original-ledger backstop, unreviewed compound scope completeness checks, and a blinded independent-gold labeling preflight. **This release is NOT Windows-, live-model-, or human-accuracy-qualified**. See [v4.9.67 dossier](docs/V4967_RELEASE_DOSSIER.md), [58-entry register](docs/V4967_TRACEABILITY_REGISTER.md), and [native Windows handoff](verification/VERIFY_ON_WINDOWS_V4967.md).

**v4.9.66 differential integrity repair (not full model/release qualification):** Repairs the eight currently reproduced failure classes: provisional bounds now use the same points as the leaderboard, unknown JD priority no longer causes a weighted-split `KeyError`, corrupt vector-cache entries yield one-key typed errors, raw share edits validate before rounding, explicit approved compound obligations cannot be bypassed by syntactic preservation, unused approved OR alternatives no longer defeat a complete conjunction, source-bound condition review preserves structured facet citations on save, and per-CV snapshots isolate missing/unreadable sources across resumes and reports. Adds offset-anchored nested reviewer expressions and an atomic local SQLite semantic-request-claim ledger. The ledger blocks automatic duplicate uncertain deliveries; it cannot prove exactly-once remote billing or recover a lost response. Full tests remain environment-incomplete; source-level correctness is **not** independently adjudicated LLM accuracy. See [v4.9.66 release dossier](docs/V4966_RELEASE_DOSSIER.md) and [traceability register](docs/V4966_TRACEABILITY_REGISTER.md).

**v4.9.65 source-grounded compound review (partial engineering qualification):** Compound parser uncertainty no longer becomes a verified negative; one bounded independent condition review can resolve cited complete work or confirmed related work while enforcing original source IDs and mandatory JD facets. A failed review signature is retained across compatible resume to avoid identical new model calls; valid zero-stem semantic paraphrases can receive an independently source-reviewed decision. Advanced supervisor-approved JD facets and neutral configurable organization branding are available. This does not establish independent live-model accuracy, durable cross-process provider dispatch safety, or Windows qualification. See [release notes](docs/RELEASE_NOTES_V4_9_65.md) and [implementation ledger](docs/V4965_IMPLEMENTATION_LEDGER.md).

**v4.9.64 source-coverage and decision-safety update (not full R0–R9 completion):** Every structurally explicit original JD clause receives a source-to-R coverage disposition visible during review; supervisor edits trigger a fresh coverage check. Frozen requirement metadata distinguishes evidence modality and whose duration is described. JD correction prompts now specify exact rejection errors even without optional tracing. Technical Unverified output includes sanitized typed failure codes and next actions; unrelated completed work with no substantive employer-duty anchor cannot automatically earn direct points under the new typed evidence contract, while a genuine inflected multi-action duty stays eligible. The 7 original + 15 cross-domain fictional cases pass the **actual unified supervisor path under stubbed replies**, not an independently labeled live-model benchmark. See [v4.9.64 release notes](docs/RELEASE_NOTES_V4_9_64.md) and [verification ledger](docs/V4964_IMPLEMENTATION_LEDGER.md). Updated assessment semantics require a fresh v50 run; older reports are historical.

**v4.9.63 targeted engineering release (not full R0–R9 completion):** The JD and legacy-assessor prompt builders now serialize untrusted source text as JSON values; a frozen per-run date is recorded in ranking reports and used for scoped tenure checks and relevant model packets. Batch transferability now has its own schema wrapper, sharing explicit policy rather than brittle string replacements. The optional focused reviewer no longer receives earlier verdicts as evidence, records sources omitted by context fit, and refuses citations to those omitted IDs; previously accepted uncommon completed work remains supported. These are offline-tested engineering changes, **not proof of cross-domain accuracy or Windows/cloud production readiness**. Read [v4.9.63 implementation ledger](docs/V4963_IMPLEMENTATION_LEDGER.md) for the R0–R9 status and remaining gates.

**v4.9.62 forensic decision/security repair:** Reproduced and addressed erroneous acronym-initials matches, three-/four-way named alternatives, non-tenure business durations, cross-origin cloud redirects, silent DOCX-header and mixed-PDF page omissions, unavailable-score export labels, stale parser-dependent assessment reuse, first-use checkpoint-key races and narrative-JD fallback contamination. New opt-in weighted split scoring is separate from the old display toggle. A deterministic seven-case benchmark exercises the actual `CVRanker(unified=True)` engine; **it does not measure live provider quality**. PDF scans are detected/flagged, **not OCRed**; real Windows and cloud-model testing remain pending. See [v4.9.62 release notes](docs/RELEASE_NOTES_V4_9_62.md) and the [13-finding forensic status ledger](docs/FORENSIC_AUD_001_013_IMPLEMENTATION_STATUS_V4962.md).

**v4.9.61 experience and education repair:** A source-linked full-time professional summary, sufficiently long dated employer role and its original affirmative duties can jointly establish a professional experience minimum without insisting that the model individually cite each duty. Full-time work is never inferred from dates alone. Completed higher academic degrees in the same exact JD-named subject can satisfy lower academic minimums (e.g. completed MSc CS for BS CS), while unrelated/in-progress credentials and explicit independent degrees remain guarded. See [v4.9.61 release notes](docs/RELEASE_NOTES_V4_9_61.md).

**v4.9.60 targeted R015-class repair:** Source validation now respects actual **OR** alternatives among named conditions (ERP **or** MES), accepts source-spelled acronym expansions only as supporting lexical leads, and prevents negated alternative lists from being mistaken for positive mentions. For a rejected named-condition citation, correction can prioritize a different original CV source even when that source was in the earlier broad shortlist; it remains a **bounded, evidence-based request**. Full assessment-path tests include direct ERP, direct MES, related-only reporting, and a false first citation followed by successful original-source recovery. **A bare ERP skills list does not automatically establish ERP use for reporting.** Live-model responses remain unverified; technical Unverified remains necessary for irreducible failures. See [v4.9.60 release notes](docs/RELEASE_NOTES_V4_9_60.md).

**v4.9.59 partial reliability work:** reviewable noun-form JD duty typing, completed-work recall for `other`, cloud-specific context/output limits, and source-expanding correction when the first citation has no qualifying evidence. This does **not** eliminate every technical Unverified or complete the JD semantic/AND-OR redesign. See [v4.9.59 release notes](docs/RELEASE_NOTES_V4_9_59.md).

**v4.9.57 assessment refinement:** Retrieval now prioritizes source passages that directly share informative language with the approved JD while retaining semantic-only leads. It recognizes more general CV heading patterns, improves dated-role corroboration for qualifying experience, and records source IDs rejected by validation separately from retrieval leads. Within the unified assessment run, exact repeated *successful* model prompts can reuse a validated structured response without a new API request; failed calls are not cached. Source edits invalidate in-session assessment reuse via an assessment-logic fingerprint, without restoring the local release-hash startup block. These improvements do **not** automatically convert lexical similarity into Found or assign extra Transferable points.

The Streamlit UI uses native **Light / Dark / System** themes with high-contrast custom evidence cards and readable buttons, inspired by Reliance Weaving Mills' green corporate palette. In the Streamlit app menu, select **Settings → Theme**. A configurable organization label (`CVR_ORGANIZATION_NAME`, default TextileHR AI) replaces the previous hardcoded example employer; its initials are a text placeholder, **not an official logo**. Brand customization makes no assessment/API requests and keeps private-file static serving disabled. See [4.9.57 release notes](docs/RELEASE_NOTES_V4_9_57.md).

> **Decision support, not verification:** CVs are self-reported. Source citations, structural checks and model judgments do not establish real-world qualifications, employment authenticity or fitness to hire. A person must review significant decisions.

## Requirements

- **Python 3.11+** (project dependencies are pinned in `requirements.txt`).
- **Windows 10/11 with PowerShell or Command Prompt** for the provided `.cmd` launchers; Linux/macOS can run the Python modules directly.
- **Ollama**, accessible locally for AI-assisted runs, with the model specified by `EMBEDDING_MODEL`. Local assessment also requires `OLLAMA_MODEL`.
- **Optional OpenRouter API key and supported structured-output model** for cloud inference (third-party cost and CV-excerpt transfer).
- Available CPU/RAM appropriate for the installed local models. No external database is required for the normal local UI.

### Install (Windows PowerShell)

From the extracted project directory:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Choose the initial provider by setting `CVR_LLM_PROVIDER=ollama` or `openrouter` in `.env`. Set **both** model identifiers there, not in the UI. For AI assessment, start Ollama and install the embedding model:

```powershell
ollama pull embeddinggemma-2:latest
ollama pull qwen2.5:3b
```

You may omit the Qwen pull if using cloud-only assessment, but **keep Ollama and EmbeddingGemma running** for the current unified retrieval. Replace the model names if your `.env` uses different installed models. When selecting cloud mode, set your own `OPENROUTER_API_KEY`; do not commit `.env`.

For a future remotely authenticated installation, the optional Streamlit OIDC dependency is provided separately via `requirements-remote.txt`. **Do not expose this local supervisor application to the public internet solely by installing that extra.** Remote identity, TLS, isolation, secure retention and operational gates remain unqualified.

### Run the supervisor UI

```powershell
.\run_runtime_check.cmd
.\run_ui.cmd
```

Open **http://localhost:8501**. Work through **Analyze → Review/approve extracted JD → Adjust weights → Run assessment → Rankings & evidence**. Other tabs display original CV segments and technical details. `run_ui.cmd` fails safely if port 8501 is already in use. Local-only mode permits legitimate edits to project source without a build-manifest hash mismatch; use `CVR_STRICT_SOURCE_HASHES=1` to opt back into source-hash verification. Remotely accessible modes always enforce the release manifest and cannot opt out.

**Access safeguard (retained in 4.9.55):** The app starts in loopback-only `CVR_ACCESS_MODE=local` and refuses a non-loopback bind in that mode. For a future managed deployment, optional OIDC authentication requires an explicit verified-email allowlist and configured Streamlit identity-provider secrets; see [production security and deployment acceptance](docs/PRODUCTION_SECURITY.md). A public deployment is **not approved** by enabling OIDC alone.

For a no-network local configuration check:

```powershell
.\.venv\Scripts\python.exe -m scripts.production_preflight
```

### Save or restore a supervisor run

1. From **Rankings & evidence**, expand **Save a restart-safe recovery checkpoint** and download the signed ZIP. Do this after every meaningful progress milestone; it is not an automatic background checkpoint.
2. After a browser refresh or server restart, reopen the app, expand **Restore a downloaded recovery checkpoint** on **Analyze**, upload that ZIP and select **Restore saved results**. Previous decisions, source evidence, request counters and editable weights return without additional AI calls.
3. If any assessment was unfinished, supply the **same original JD and CV files**, extract and approve the **same frozen JD**, then select **Resume unfinished assessments**. Changes to input bytes, requirement identities, policy settings or provider/model reject checkpoint reuse. Already-finished reports can simply be reviewed or exported.

**Privacy and portability:** Recovery ZIPs include applicant-derived excerpts and decisions in plaintext. Store them in an access-controlled location and delete according to your retention policy. A random local HMAC signing key is created in `.cv_ranker_cache/recovery_signing.key` (excluded from source releases); retain a secure backup of this key if you need recovery after reinstalling or migrating servers. Signing detects alterations but **does not encrypt** the ZIP. Never share the signing key, commit it, or send a recovery ZIP to a public repository. No server-side background checkpoint database is configured.

For a supervised local model smoke test (may take time):

```powershell
.\.venv\Scripts\python.exe doctor.py --provider ollama --live
```

Cloud smoke test (issues provider requests, potentially billable):

```powershell
.\.venv\Scripts\python.exe doctor.py --provider openrouter --live
```

### Linux/macOS equivalent

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
# Edit .env; ensure the selected Ollama models/service are available.
.venv/bin/python -m cv_ranker.runtime_check
.venv/bin/python -m streamlit run app.py --server.address localhost --server.port 8501
```

Windows batch scripts are optional on non-Windows systems; **do not copy a Windows `.venv`** to another OS.

## Command-line use

The CLI generates the **base** candidate coverage report (JSON). For editable supervisor weightages, per-requirement allocation and the interactive leaderboard, use the Streamlit interface.

```powershell
.\.venv\Scripts\python.exe main.py --jd sample_data\backend_jd.txt --resumes sample_data\backend_resumes --output outputs\ranking.json --details
```

To inspect arguments, run `python main.py --help`. To run a conservative offline fixture without model requests, choose `CVR_LLM_PROVIDER=ollama` in `.env` and append `--no-llm`; fallback evidence is not a substitute for a full human review.

## Project structure

| Path | Purpose |
|---|---|
| `app.py`, `cv_ranker/ui/` | Streamlit dashboard, results and evidence inspection. |
| `main.py`, `doctor.py` | CLI report and diagnostics. |
| `cv_ranker/config.py`, `schemas.py`, `pipeline.py`, `unified.py` | Configuration, strict contracts and assessment orchestration. |
| `cv_ranker/documents.py`, `jd.py`, `segments.py` | Text ingestion, frozen JD criteria and source segmentation. |
| `cv_ranker/semantic/` | Local embedding retrieval, caches and diagnostic compatibility paths. |
| `cv_ranker/*validation.py`, `scoring.py`, `weighted_scoring.py` | Evidence/credential/tenure checks and ranking calculations. |
| `cv_ranker/ranking_reasoning.py`, `report_bundle.py`, `recovery_bundle.py`, `ui_support.py` | Distinct ranking explanations, reviewer exports and signed portable recovery. |
| `cv_ranker/access_control.py`, `scripts/production_preflight.py` | Fail-closed local/OIDC access policy and offline deployment diagnostics. |
| `tests/` | Automated regression suite. |
| `sample_data/`, `evaluation/` | Synthetic examples, benchmark tooling and preserved historical results. |
| `scripts/` | Manifest packaging, demonstrations and older diagnostic launchers. |
| `docs/` | Canonical architecture, cleanup register, focused guides and release history. |

## Tests and contribution workflow

```powershell
.\run_tests.cmd
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe doctor.py
```

For cross-platform Python:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m cv_ranker.runtime_check
```

Before submitting changes:

1. Add a regression test for changes to JD extraction, evidence validation, category allocation, ranking, recovery or exports. Do not customize model decisions to one sample candidate or profession.
2. Keep source IDs, frozen JD coverage, original citations, **Found-only credit** and zero-credit Transferable behavior intact unless a separately reviewed product requirement changes them.
3. Run offline tests and a hash check. Real cloud evaluations need explicit budget/privacy approval; passing offline tests does **not** prove live model accuracy.
4. Update [architecture and contracts](docs/ARCHITECTURE.md) and any relevant operating guide. Rebuild the source manifest after reviewed changes:

   ```powershell
   .\.venv\Scripts\python.exe scripts\rebuild_manifest.py
   .\run_runtime_check.cmd
   ```

5. Package a distributable source ZIP **outside this directory**:

   ```powershell
   .\.venv\Scripts\python.exe scripts\package_source_release.py C:\path\outside\CV_Ranker_release.zip
   ```

The manifest detects mixed source versions and is not a digital signature. Do not commit `.env`, `.venv`, `outputs/`, applicant files or embedding caches.

## Documentation

- **[Documentation index](docs/INDEX.md)** — start here for current instructions versus archived history.
- **[Unified architecture, system design, data contracts and environment variables](docs/ARCHITECTURE.md)** — authoritative current engineering specification.
- **[Repository audit and staged cleanup actions](docs/REPOSITORY_AUDIT.md)** — duplicate findings, safe deletion candidates, consolidation plan and target tree.
- [Supervisor walkthrough](docs/SUPERVISOR_WALKTHROUGH.md), [demo guide](docs/DEMO_GUIDE.md), [benchmark guide](docs/BENCHMARK_GUIDE.md) — focused operational references; check their dated context.
- **[Production access, privacy, operations and deployment gates](docs/PRODUCTION_SECURITY.md)** — security setup, data-retention and release acceptance.
- [Latest release notes](docs/RELEASE_NOTES_V4_9_45.md), [4.9.44 recovery](docs/RELEASE_NOTES_V4_9_44.md), [4.9.43 repairs](docs/RELEASE_NOTES_V4_9_43.md) and [historical releases](docs/history/releases/) — release provenance, not a substitute for the current specification.

## Deployment cautions

This release is designed for a supervised local review workflow. A formal production rollout still needs organizational approval for cloud CV processing, privacy and retention controls, model accuracy evaluation on representative JDs, multi-user session/cache stress testing, **authenticated encrypted automatic persistence**, and access management. The current signed ZIP is manual recovery, not unattended crash-proof processing. **No automatic hiring decisions.**

## Three-verdict protocol 56 (v4.9.70-rc1, development candidate)

This source is a **development release candidate, not a certified Windows production
release**. Every *completed* JD-to-CV assessment now uses Found, Transferable,
or Not Found; genuine input/provider/response failures have no final verdict and
no official candidate score/rank. Historical saved Unverified records remain
historical and must not be silently converted to candidate negatives.

Read `docs/V4970_THREE_VERDICT_RC1_QUALIFICATION.md` and
`verification/V4970_THREE_VERDICT_ROUTE_AND_PROMPT_LEDGER.md` before adoption.
Run `bash verification/V4970_THREE_VERDICT_VERIFY.sh` in a supported offline
Python environment. The exact v4.9.68 Windows Test Compatibility baseline was
not included in this source work, and this candidate is not a replacement for
it without the documented integration and acceptance gates.


## React + FastAPI migration development checkpoint (16 November 2026)

A separate React/TypeScript + FastAPI migration tree is included for ongoing
engineering work. **This source checkpoint is not a production-ready web app:**
the modern frontend packages could not be installed in the build environment,
so there is no Vite production bundle. The working Python engine and original
Streamlit UI remain available. See `docs/migration/COMPLETION_CHECKPOINT.md`,
`docs/migration/INSTALL_AND_RUN.md` and `docs/migration/PARITY_REGISTER.csv`
before trying the new web workflow.


## DA021 repair continuation — 16 November 2026

The local React/FastAPI migration has additional storage, worker, API contract and supervisor UI-source repairs. The current DA021 work **has not met release completion**: npm was not available in the engineering environment, so there is no authentic lockfile or compiled Vite frontend, and missing focused-review / semantic-shadow / retention integrations still require work. Keep the existing Streamlit application. See `docs/migration/DA021_IMPLEMENTATION_AND_RELEASE_STATUS.md` and `docs/migration/DA021_REPAIR_REGISTER.csv`.
