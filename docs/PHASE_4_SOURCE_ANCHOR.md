# Phase 4 — Named-requirement evidence anchoring and granular benchmark provenance

**Build:** `source-anchor-audit-2026-10-12`  
**Scope:** Focused correction-path improvement on the supervisor-ready local CV Ranker. No new semantic engine, independent verifier, embeddings, vector search, or skills/alias dictionary.

## Why this phase was needed

In the last actual Windows repeatability run (three trials for each batch size, 21 labelled requirements), the complete assessment system achieved **16/21 (76.19%)** at batch 20 and **17/21 (80.95%)** at batch 3. The reported Qwen-only raw status agreement was **12/21 (57.14%)** in both configurations. **Zero runs used a completely unmodified LLM path**. Repetition on one small set alone cannot establish general validity.

A recurring error: Qwen claimed a short named technology requirement such as `Django` was matched while citing a valid CV source line referring to another technology such as PostgreSQL. The source ID was real; the *meaning* was not justified. The current project must not hardcode semantic equivalences or add a separate verifier, so it cannot automatically prove that two named terms are (or aren't) equivalent.

## Code changes

### 1. Source-term anchoring for short named requirements

`cv_ranker/assessor.py` detects an **atomic name by generic text formatting**, not by a domain-specific list: 1–3 capitalized words, with ordinary letters/digits/punctuation. Examples of formatting: `Django`, `Google Cloud`, `Natural Language Processing`.

If Qwen labels an atomic name **matched/uncertain** but cites only an otherwise-positive segment that has neither the requirement's exact wording nor a specific `matched_term` copied from the segment, the assessment row is invalid and goes through the **existing CV correction prompt**. The model must identify the actual source term (even one word) or return `not_matched`. Python verifies any supplied `matched_term` exists in the cited text. **Qwen still owns semantic equivalence.**

This is *not* a blanket requirement to quote source terms: a properly cited generic task, experience or degree paraphrase can still omit `matched_term`. Literal named requirements, real learning-only cues, and exact supported source terms are not changed. Existing title-only and negative/contradictory evidence safeguards remain.

**Examples:**

| JD requirement | Cited CV source | First model claim | New behavior |
|---|---|---|---|
| Django | Maintained PostgreSQL databases. | `matched`, null source term | Invalid; existing correction prompt runs |
| Google Cloud | Skills: GCP | `matched`, `matched_term=GCP` | Accept, display full line |
| Natural Language Processing | Skills: NLP | `matched`, null source term | Request source-term correction |
| REST API development | Built REST endpoints using FastAPI | `matched`, null source term | Accept cited semantic action paraphrase |
| PostgreSQL | Maintained PostgreSQL databases | `matched`, null source term | Accept exact wording |

**Limit:** If Qwen falsely states that a quoted real phrase is an equivalent named item, this stage cannot detect all such semantic errors. That is a model-quality limitation. We do not claim it is a semantic verifier.

### 2. Per-requirement model-vs-Python diagnostics

`evaluation/evaluate_benchmark.py` now adds the following to `measurement_quality`:

- `decision_path_counts`
- `qwen_initial_status_unchanged_rows`
- `llm_correction_rows`
- `post_model_status_changed_rows`

This supplements, rather than replaces, existing batch-level `mode_counts`, raw status diagnostics, and the strict `valid_live_llm_measurement` flag. A group flagged `mixed` can contain an initial Qwen decision that Python did not change; the new fields let us describe those rows accurately. **An unchanged Qwen decision is not necessarily correct.**

### 3. Configuration policy

Production `assessment_batch_size` remains **20** for compatibility with the last supervisor demonstration. The evaluation runners still support batches 3 and 20. Selecting 3 globally based on only 21 labels would risk overfitting without showing better safety on novel JDs/CVs. Benchmark data is never imported into production decisions.

## Technical validation

- Test suite: **184 tests passed** (original 176 + 8 focused regressions).
- Runtime hash manifest regenerated and checked from the final ZIP.
- Source files compiled with Python.
- Tested offline with mock structured LLM replies; **no Ollama service is available in this container**. The live health check and before/after accuracy need to be measured again on your PC.
- Source-anchoring logic is generic and does not import the benchmark dataset.

## Windows commands

```powershell
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe doctor.py --live
.\scripts\run_benchmark.cmd
.\scripts\run_benchmark_pipeline.cmd
.\scripts\run_repeatability_probe.cmd
```

Preserve your working `.venv` when updating the project. **Do not compare newly generated accuracy to old build outputs as if they came from the same build.** Run the unchanged 21-case benchmark using the new build, then inspect the source-anchor warnings and individual `decision_path_counts`.

## Next unresolved engineering issue

Qwen still has to improve identification of genuine abbreviations (`NLP`, `GCP`), experience thresholds (3+ years), and cross-tool distinctions without a skill-specific dictionary. If this source-anchor change causes false negatives on real semantic equivalents, use the per-row trace to identify them; do not silently grant unsupported named-tool matches.
