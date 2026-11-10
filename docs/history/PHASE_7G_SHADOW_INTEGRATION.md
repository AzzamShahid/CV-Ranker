# Phase 7G Checkpoint 1 — EmbeddingGemma shadow retrieval integrated with real Phase 7F.2

**Integrated source:** `CV_Ranker_Phase7F2_Forensic_Source_Scope_Organized(1).zip` (build `evidence-scope-forensic-fix-2026-10-13`, 513 offline tests). **This is an older provided build**, not an overwrite of any newer 678-test/Phase 7G6x code on the user's Windows computer.

**Change boundaries:** The existing `CVRanker.run()` pipeline, YAKE, JD freezing, source/citation checks, Qwen prompts, statuses, scoring, sorting, fallback, UI and report serialization are unchanged. New `CVRanker.run_semantic_shadow(report, cache_path=...)` executes *after* a complete normal ranking run. There is no invocation from the default UI or CLI. The stored ranking report is unmodified and is produced before semantic retrieval.

## What was implemented

- `cv_ranker/semantic/embedding.py`: local Ollama `embeddinggemma-2:latest` native-dimension embedding using asymmetric search query/document prompts, `truncate=False`, strict vector validation and L2 normalization. An explicit dimension override is optional only for later experiments. Ollama model digest must be read from `/api/tags` and becomes part of every persistent cache key.
- `cv_ranker/semantic/cache.py`: SQLite vector-only cache keyed by model fingerprint, original text and query/document role. Does not write raw resume text to the cache (numeric embeddings can still disclose personal information).
- `cv_ranker/semantic/core.py`: candidate-scoped NumPy exact-cosine top-k retrieval, deterministic sorting, exact-term hit preservation, source-ID deduplication, no semantic scores or verdicts.
- `cv_ranker/semantic/integration.py`: consumes the **existing report's frozen JD requirements**, reuses `documents.extract_text()` and `segments.segment_resume()` with same source IDs, filters `non_candidate`, `metadata` and obvious instruction-like segments, then retrieves diagnostic candidates. Negated or learning-only segments remain eligible to retrieve as *negative context*, not proof of ability. The filter is **retrieval-only**, not a full unified positive-evidence adjudicator.
- `cv_ranker/pipeline.py`: optional `run_semantic_shadow()` method. Default `run()` unchanged.
- `scripts/phase7g_shadow.py`: optional standalone CLI, writing the original ranking report unchanged and a separate **sensitive** evidence-retrieval JSON sidecar.
- `tests/test_phase7g_shadow_core.py` and `tests/test_phase7g_shadow_integration.py`: offline fake-encoder regressions for formatting, vector shapes, candidate isolation, caching, context restrictions and invariance of existing scores/requirements/ranks.

## Setup on Windows (PowerShell)

From the extracted root folder (the one containing `run_runtime_check.cmd`):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
ollama pull embeddinggemma-2:latest
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe doctor.py --live
```

The first two commands install the additional NumPy dependency and model; both models must be available to run the full LLM + embedding example.

### Optional shadow retrieval (model-dependent)

```powershell
.\.venv\Scripts\python.exe -m scripts.phase7g_shadow --jd sample_data\backend_jd.txt --resumes sample_data\backend_resumes
```

Use `--no-llm` to run existing deterministic fallback assessment before embedding retrieval, or `--top-k 3` for a retrieval experiment. **Neither flag changes the old score formula.** Outputs:

- `outputs/phase7g_shadow/ranking.json`: normal unchanged ranking output.
- `outputs/phase7g_shadow/retrieval.json`: candidate-scoped source IDs, original text, cosine relevance and literal flag — **not candidate competency scores**.
- `outputs/phase7g_shadow/embeddings.db`: SQLite embeddings; handle as sensitive candidate data.

The new command is optional; `run_ui.cmd`, `main.py` and original benchmarks continue to run exactly as before.

## Validation and limitations

- Offline fake-model tests verify algorithms and interfaces; the actual `embeddinggemma-2:latest` model was **not runnable in this hosted environment**. Live Ollama performance and task-prefix behavior must be checked on Windows.
- Parent JD requirements are used as search queries in Checkpoint 1; **dynamic capability decomposition is not implemented yet**.
- Neither Qwen functional transferability verification nor transferability credit is implemented in this checkpoint.
- The original Phase 7F.2 requirement limit can still truncate a large JD while warning and ranking; it must be resolved separately before production use.
- `retrieval_eligible_ids` excludes known non-candidate sections, but is not yet a unified authoritative source-admissibility layer across all verifiers. It may still surface irrelevant, negated, unverified, or title-only statements. Semantic results must never be used to grant positive credit at this stage.
- Avoid publishing sidecar JSON or persisted embeddings without consent/access control; do not use the report for automated hiring decisions.
- The project is not validated for real-world recruitment accuracy or fairness. The previous 197/200 synthetic fallback score is a regression baseline only.

## Next checkpoint

Benchmark `Recall@1/3/5` on labelled evidence pairs and unseen professional domains, fix evidence admission and JD truncation, add dynamic JD-grounded capability decomposition, then introduce batched Qwen transferability verification with strict original source links. Keep partial transferability **report-only** until the supervisor approves a scoring contract.
