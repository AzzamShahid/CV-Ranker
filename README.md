# CV Ranker — Supervisor Edition

Evidence-first, configurable JD-to-CV screening with original source citations, transparent scoring and reviewer-facing explanations.

**Current interface:** 4.9.54 (11 November 2026)  
**Assessment build:** `phase7g-v4-9-54-unbulleted-requirements-completeness-2026-11-11`  
**Protocol:** `segment_ids_semantic_llm` v39  
**Status:** local supervisor-review application; not an autonomous hiring decision system.

## What it does

1. Read one job description from text, Markdown, PDF or DOCX.
2. Extract JD criteria with YAKE-assisted structured interpretation, and let the reviewer **edit and approve** the frozen requirement list.
3. Compare multiple CVs to the **same approved requirements**, retaining original source segment IDs and an independent **Why this decision** for every criterion.
4. Distinguish **Found**, **Transferable**, **Not Found** and **Unverified**. Only source-verified **Found** earns direct points; unverified technical results withhold the candidate's rank rather than pretending to be a nonmatch.
5. Configure category weights (default **10% Experience / 10% Education / 80% JD**) and individual requirement shares **after JD extraction**, without making more model calls. Required and Preferred items share one JD scoring pool; the split toggle changes display only.
6. Review a ranked leaderboard with a separate **Why this CV received its ranking**, individual evidence, review notices and optional technical diagnostics. Download CSV, JSON or a complete reviewer ZIP.
7. Download a **signed recovery checkpoint ZIP** to reopen saved results after a browser refresh/server restart; incomplete runs can resume only after their identical JD/CVs and approved criteria are supplied again.

The current AI-assisted pipeline uses **local Ollama EmbeddingGemma retrieval** with a selectable **Ollama or OpenRouter assessment model**. The optional diagnostic/research scripts are separate from the authoritative final score. There are no hardcoded profession-specific matching answers. The employer's explicit alternative academic majors are accepted at their stated degree level, while relevant work from a different discipline can be displayed as **Transferable** only when supported by cited original CV duties; it never earns direct points.

The Streamlit UI uses native **Light / Dark / System** themes with high-contrast custom evidence cards and readable buttons, inspired by Reliance Weaving Mills' green corporate palette. In the Streamlit app menu, select **Settings → Theme**. The “RW” initials are a text-based placeholder, **not an official company logo**. Brand customization makes no assessment/API requests and keeps private-file static serving disabled. See [4.9.54 release notes](docs/RELEASE_NOTES_V4_9_54.md).

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

### Run the supervisor UI

```powershell
.\run_runtime_check.cmd
.\run_ui.cmd
```

Open **http://localhost:8501**. Work through **Analyze → Review/approve extracted JD → Adjust weights → Run assessment → Rankings & evidence**. Other tabs display original CV segments and technical details. `run_ui.cmd` fails safely if port 8501 is already in use or release hashes do not match.

**Access safeguard (retained in 4.9.54):** The app starts in loopback-only `CVR_ACCESS_MODE=local` and refuses a non-loopback bind in that mode. For a future managed deployment, optional OIDC authentication requires an explicit verified-email allowlist and configured Streamlit identity-provider secrets; see [production security and deployment acceptance](docs/PRODUCTION_SECURITY.md). A public deployment is **not approved** by enabling OIDC alone.

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
