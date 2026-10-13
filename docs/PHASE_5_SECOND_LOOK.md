# Phase 5 — Selective false-negative second look

**Build:** `selective-second-look-2026-10-12`  
**Status:** Tested offline with controlled structured Qwen responses. **No live Qwen accuracy result has been measured for this build.**

## Why this is needed

The user's latest Windows results on **Phase 4** (`source-anchor-audit-2026-10-12`) reported:

| Phase 4 measurement | Correct | Accuracy | Precision (matched) | Recall (matched) |
|---|---:|---:|---:|---:|
| Assessment only | 18 / 21 | 85.71% | 100.00% | 75.00% |
| Full JD → CV pipeline | 17 / 21 | 80.95% | 100.00% | 66.67% |

Both are combined-system measurements, with mixed model/Python intervention. **Neither is a clean Qwen-only accuracy result.** The program passed its user's live `doctor.py --live` check with `READY` and scored 100% on the deliberately small health fixture, but that does not establish general accuracy.

Phase 4 improved false-positive safety: Django and Redis were correctly rejected in the uploaded Windows run, and the job-title-only safety case passed. The main remaining failures are *false negatives*: Qwen misses `NLP` for Natural Language Processing, `GCP` for Google Cloud, and sometimes rejects genuine task paraphrases like developing a source-first AI intake application.

## What changed

### 1. Selective second look in `cv_ranker/assessor.py`

After the ordinary batch assessment, source validation, direct literal guard, and any invalid-row correction, Python considers only final `not_matched` requirements. It identifies **orthographic leads** in suitable resume evidence, such as:

- A matching acronym initialism found as an uppercase resume token. For two-word names, a three-letter token with the same starting initials may be a *lead*, not proof.
- Two directly shared informative words or an existing uppercase requirement word.
- A word shared with a years-of-experience requirement and an explicit duration expression.

The cues are general string formatting and literal-overlap checks, *not a hardcoded list of skill equivalents*. They **do not award points**. A JD requirement may still have no eligible leads, in which case there is **no additional model call**.

One **grouped call to the same local Qwen model** rechecks eligible `not_matched` rows. It uses the **existing CV correction system prompt**, a dynamic user message that labels the leads as unverified, and the complete resume segments for context. A new `matched` response is adopted *only if* it passes all existing source-ID, matched-term, section, instruction, and tone validators. Invalid or still-negative corrections retain `not_matched`.

The feature is enabled by default through `Settings(second_look_unmatched=True)`. Set it to `False` in `cv_ranker/config.py` if the extra optional Qwen call is not worth its latency. The production batch size remains **20**, and scoring, JD extraction, and evidence schemas have not changed.

### 2. Auditable benchmark attribution

`evaluation/trace.py` now identifies calls made for a second look separately from the original assessment and the invalid-source correction. `evaluation/evaluate_benchmark.py` reports `llm_second_look_agreed_with_final` and `llm_second_look_rows`, and saves `second_look_unmatched` in the JSON result. Python interventions and legacy mixed-mode warnings remain visible.

### 3. A/B measurement option

The evaluation command has a `--no-second-look` flag. It disables only the optional new second look, preserving the same model, data, scoring, and initial assessment behavior. Use distinct JSON output filenames to compare the two policies. Run both **assessment-only** and **full-pipeline** scopes with identical model/batch settings.

```powershell
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe doctor.py --live

.\.venv\Scripts\python.exe -m evaluation.evaluate_benchmark --scope assessment --batch-size 20 --no-second-look --output outputs\phase5_assessment_without_second_look.json
.\.venv\Scripts\python.exe -m evaluation.evaluate_benchmark --scope assessment --batch-size 20 --output outputs\phase5_assessment_with_second_look.json

.\.venv\Scripts\python.exe -m evaluation.evaluate_benchmark --scope pipeline --batch-size 20 --no-second-look --output outputs\phase5_pipeline_without_second_look.json
.\.venv\Scripts\python.exe -m evaluation.evaluate_benchmark --scope pipeline --batch-size 20 --output outputs\phase5_pipeline_with_second_look.json
```

**Expected exit-code caveat:** The benchmark prints and saves its results but returns a nonzero status if even one row is mixed or fallback, by design. This does not necessarily mean the test process crashed; read the saved JSON and printed metrics.

## Safety and trade-offs

1. **No independent semantic verifier was introduced.** Qwen still owns abbreviation and paraphrase semantics; it can still be wrong.
2. Python identifies *candidates for rechecking*, not actual synonyms or semantic facts. A superficially similar acronym can be unrelated. The model must reject such cases.
3. All source IDs, full evidence text, and optional `matched_term` must still pass the validator. The existing source-anchoring correction is unaffected.
4. A second Qwen call can increase latency/token consumption and may fail due to context or Ollama availability. If so, previous negative decisions are retained.
5. Rechecking only proposed false negatives does not solve every possible unsupported positive match. An erroneous semantic equivalence with a valid source term can still pass.
6. Test coverage includes positive abbreviation/paraphrase/duration simulations, missing/forged terms, unrelated tools, negation, title-only evidence and opt-out behavior. These use controlled model outputs, **not live accuracy measurements**.

## Interpretation for the supervisor

> The system first assesses all frozen requirements through Qwen and Python source validation. For a *small subset of uncredited requirements* that have possible source clues, it asks Qwen to reconsider with focused citations. The clues cannot produce a match by themselves; every positive result still needs a new, source-grounded Qwen answer. This is an optional accuracy experiment, not a new ranking formula or separate verifier. We will compare its live behavior on the same labelled dataset before declaring it an improvement.
