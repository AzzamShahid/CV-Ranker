> **V4.1 favorable evidence repair (2026-10-22):** Start with [PHASE_7G_V4_1_FAVORABLE_EVIDENCE_REPAIR.md](PHASE_7G_V4_1_FAVORABLE_EVIDENCE_REPAIR.md). This is a focused correction of the V4 unified workflow, **not the rejected alternative V5 design**. It fixes lost GCP/implicit capability review, preserves sourced matches across incomplete AI passes, restores transferable decisions and highlighted terms, and makes the final ranking use the same Found counts as the evidence table.

> Earlier V4 changes: [single-CV accuracy](PHASE_7G_V4_SINGLE_CV_ACCURACY_REPAIR.md), [evidence integrity and UI](PHASE_7G_V4_EVIDENCE_INTEGRITY_AND_UI.md), and [unified evidence](PHASE_7G_V4_UNIFIED_FINAL_EVIDENCE.md).

# CV Ranker — Supervisor Edition

A clean, source-grounded Python prototype for ranking candidate CVs against a job description. **Phase 7G: Streamlit supervisor UI + optional OpenRouter LLM; one-click read-only semantic and transferable-capability review.**

**Start here:** `run_supervisor_demo.cmd` runs the health check and opens the interface; `run_ui.cmd` opens the interface without the live health test. The ranking engine, YAKE extraction, original source citations and deterministic matching scores are preserved.

## Windows quick start

Use **Python 3.11**, from the extracted project folder in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe doctor.py --live
.\run_ui.cmd
```

Existing working `.venv`: skip the first command and reinstall only if dependencies have changed. Keep `.env` **private** and never paste an API key into the app or chat. The project package intentionally excludes `.env` and CV outputs.

### OpenRouter (optional)

Configure `.env` locally:

```ini
CVR_LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=REPLACE_WITH_PRIVATE_KEY
OPENROUTER_MODEL=google/gemini-2.5-flash-lite
```

The example model identifier follows the user's previously successful OpenRouter setup; it is not a guarantee of current pricing or availability. A model must support the structured schema required by the program. If using **local Qwen** instead, set `CVR_LLM_PROVIDER=ollama` (default `qwen2.5:3b`). See [OpenRouter setup](docs/OPENROUTER_SETUP.md).

**Privacy:** OpenRouter sends JD/CV content off device to your chosen provider. Only use documents you are authorized to send. Local Ollama is still needed for optional EmbeddingGemma semantic search.

## Demonstrate to a supervisor

1. Launch the UI. Keep **Show potential transferable skills** enabled (default) if local Ollama has `embeddinggemma-2:latest` available. This adds API calls and can take longer.
2. Select **Analyze → Run Backend developer demo** or **HR specialist demo**, **Transferability demo**, or upload a JD and CVs. One click now runs ranking and optional transferability review for the same inputs.
3. Under **Rankings & evidence**, show primary scores, **Transferable (review)** counts, exact original CV sentences, and the **Potential transferable skills** section for the selected candidate. No JSON import or extra terminal scripts are required.
4. Show that the score is **matched required criteria / frozen required criteria**. Plain named skills explicitly claimed under `Skills` can satisfy ordinary skill requirements; this is CV self-reporting, not external credential verification.
5. Show that **AI-proposed transferable** relationships are read-only and remain unverified; the original ranking does not change even if the semantic stage is offline.

Additional commands:

```powershell
.\scripts\run_phase7g_shadow.cmd --decompose
.\scripts\run_phase7g_transferability.cmd
.\.venv\Scripts\python.exe -m scripts.phase7g_relationship_audit
```

For an exact one-click explanation, see [One-click transferable review](docs/ONE_CLICK_TRANSFERABILITY.md).

The built-in backend/HR demos require a model when AI-assisted assessment is on. For an offline demonstration, toggle off AI-assisted assessment and use the conservative deterministic fallback; check the evaluation-mode label because fallback and LLM outputs are not equivalent.

## Project map

| Path | Purpose |
| --- | --- |
| `app.py` | Minimal Streamlit entry point |
| `cv_ranker/ui/dashboard.py` | Supervisor presentation and integrated semantic review |
| `cv_ranker/ui/semantic_workflow.py` | Safe same-run semantic orchestration and report summaries |
| `cv_ranker/ui_support.py` | File-handling and export helpers |
| `cv_ranker/` | JD extraction, CV evidence, Qwen/OpenRouter calls, deterministic matching |
| `cv_ranker/semantic/` | Experimental EmbeddingGemma index and transferability proposals |
| `sample_data/` | Synthetic HR/backend test resumes and JDs |
| `scripts/` | Launchers and analysis scripts |
| `tests/` | Regression tests |
| `evaluation/` | Independent synthetic benchmark tooling |
| `docs/` | Architecture, project explanation, OpenRouter setup, historical checkpoints |

Read [UI guide](docs/SUPERVISOR_UI_GUIDE.md), [architecture](docs/ARCHITECTURE.md), [project organization](docs/PROJECT_MAP.md) and [supervisor walkthrough](docs/PRESENTATION_CHECKLIST.md).

## Scope and limits

- Only source-supported claims are shown as CV matches; ordinary skills-list claims are still *self-reported*.
- Primary scores **do not** use cosine similarity or provisional transferable-skill labels.
- Relevant contextual work experience can support an ordinary requirement; mandatory experience durations, licenses and eligibility require their appropriate checks/review.
- The Phase 7G semantic subsystem remains an experiment, not a validated production hiring tool. Optional semantic review is now executed in the same UI workflow; it never awards scoring credit. Local EmbeddingGemma/Ollama is still required and additional OpenRouter calls may cost money.
- No BM25, vector database server, arbitrary score calibration or hard-coded skill substitution database was introduced for this UI release.

**Build integrity:** `run_runtime_check.cmd` checks hashes of tracked source files. Do not mix single files from different released ZIPs. Extract into a separate folder. No personal applicant documents or API keys should be included in the ZIP.


## Applied AI / ML Engineer benchmark (October 2026)

An expanded, fictional resume set for a JD specifying **3+ years of relevant professional AI/ML or LLM application development experience**, required skill alternatives (**TensorFlow OR PyTorch**), and preferred tooling.

- Click **Run Applied AI / ML (5 CVs) demo** for a shorter, cost-aware one-click comparison.
- Use `sample_data/applied_ai_jd.txt` with any of the 12 `sample_data/applied_ai_resumes/*.txt` files for the full batch.
- Matching DOCX and PDF examples are under `sample_data/applied_ai_documents/{docx,pdf}`.
- The detailed benchmark handout is under `sample_data/applied_ai_documents/README.md`.
- The top three candidates are full two-page PDFs/DOCX; all resumes are synthetic and no score is pre-assigned.
- Dense embeddings, LLM inference and semantic review can make a large demo slow and consume remote API credits.
- No ranking algorithm, transferability policy or existing sample is modified by this dataset addition.


## Phase 7G Applied AI demo repair (2026-10-20)

The Windows `scripts\run_phase7g_shadow.cmd --decompose` command now uses
`sample_data\applied_ai_jd.txt` and all 12 synthetic Applied AI resumes. It
previously hardcoded the *backend* JD and four backend resumes. The old demo
is available via `scripts\run_phase7g_backend.cmd --decompose`.

For an end-to-end CLI semantic demonstration, run:

```powershell
.\scripts\run_phase7g_applied_ai.cmd
```

This runs ranking and retrieval first, then model-proposed transferability
against **the same saved run**. The configured OpenRouter/Ollama model and
local EmbeddingGemma must be available. It may require many model calls.

For the Streamlit demo, use `Run Applied AI / ML (5 CVs) demo` and enable
`Show potential transferable skills`. The UI now shows **All** proposals by
default (with transferables first), rather than showing an empty filtered table.

The AI/ML JD parser now preserves the explicit 3+ year experience requirement
and excludes explanatory sections from the source requirements. The
`TensorFlow or PyTorch (at least one)` OR wording now has precisely two
options. Skill-to-skill equivalences and cosine-to-competence mappings are
**not hardcoded**.

Model relationships remain **provisional**, never primary-score credits.
Completeness of source parsing and model semantic accuracy are distinct: a
model may still propose zero transfers. Independent reviewers must validate
examples, model calls, sensitive outputs, and candidate outcomes before using
any rankings for hiring decisions.

## Reliability repair: adaptive semantic LLM batching

Phase 7G now uses up to **3 JD parent requirements per candidate** in one structured remote/local model call (`CompactBatchResponse`). Batch IDs and source citations remain isolated by requirement. Over-context or malformed batches are recursively split; missing or invalid requirement-level decisions are individually retried. A final failure remains `uncertain`, never a manufactured transferable positive.

```powershell
# Full 12-resume workflow, default 3 requirements per batch
.\scripts\run_phase7g_applied_ai.cmd

# Avoid rerunning baseline / embeddings if outputs\phase7g_shadow exist:
.\scripts\run_phase7g_transferability.cmd --batch-size 3

# Provider compatibility fallback (original one-requirement calls):
.\scripts\run_phase7g_transferability.cmd --batch-size 1

# Change full-demo batch size without changing retrieval flags:
.\scripts\run_phase7g_applied_ai.cmd --batch-size 2
```

The transferability output includes `batching.batch_calls`, `single_calls`, `split_batches`, `retried_requirements`, and `completed_batches`. Counts exclude optional focused second looks and provider-internal retries, so total API requests may be higher. No direct ranking credit is awarded for provisional functional relationships. Review flags and upstream incomplete assessments still need review.
