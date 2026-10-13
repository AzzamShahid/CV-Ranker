# Phase 6C — Diagnose Focused Acronym Failures Before Changing Matching Rules

**Build ID:** `focused-acronym-diagnostics-2026-10-12`  
**Scope:** Benchmark instrumentation and A/B controls ONLY. No changes to production assessor decisions, model prompts, scores or ranking policy.

## Confirmed Phase 6B Windows results

- Runtime manifest: 29 files, valid. Automated tests: 214 passed. Live `doctor.py --live`: READY.
- Assessment-only 19/21 (90.48%). Full JD→CV pipeline 19/21 (90.48%).
- Both scopes have **100% matched precision and 83.33% matched recall** on the tiny 21-label suite; **zero correct semantic abbreviation decisions out of two**.
- Errors: Natural Language Processing / NLP and Google Cloud / GCP. The system did not grant unsupported positives.
- The previous terminal trace conflated grouped and focused Qwen calls under `llm_second_look...`, making it impossible to distinguish their outcomes.
- These numbers are **combined final outcomes with some Python intervention**, not pure Qwen accuracy.

## Diagnostic changes

1. `evaluation/trace.py` differentiates `initial`, `correction`, `second_look`, `focused_abbreviation` for each structured model response. It records raw structured `status`, `evidence_ids`, `matched_term` and attempt call index. It does not record complete prompts or entire resume text. Treat any quoted matched term as resume-derived data when sharing logs.
2. `evaluation/evaluate_benchmark.py` includes `model_attempt_history` for every benchmark row in JSON and prints attempt history for failed rows. New `llm_focused_abbreviation_rows` instrumentation makes it clear whether a focused attempt happened; it does **not** grant credit itself.
3. `--no-focused-abbreviation` disables only the focused call (grouped second look remains on). `--no-second-look` disables both. `--scenario semantic_positive` runs just the 7-label scenario with both missing abbreviations, reducing the local-model load of diagnosis.
4. New offline tests confirm phase labels, attempt order, no whole-prompt capture, and independent A/B flag propagation.

## Commands on Windows

After replacing the project source with this ZIP, keep the working `.venv` and run:

```powershell
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe doctor.py --live
```

**Targeted A/B comparison (same code, same 7-label scenario):**

```powershell
.\.venv\Scripts\python.exe -m evaluation.evaluate_benchmark --scope assessment --scenario semantic_positive --no-focused-abbreviation --output outputs\acronym_without_focused.json
.\.venv\Scripts\python.exe -m evaluation.evaluate_benchmark --scope assessment --scenario semantic_positive --output outputs\acronym_with_focused.json
```

Then run the normal full benchmarks if needed:

```powershell
.\scripts\run_benchmark.cmd
.\scripts\run_benchmark_pipeline.cmd
```

The benchmark intentionally returns exit code `3` when the result contains mixed or fallback evaluation modes, even after saving JSON. This is a *measurement provenance flag*, not automatically a crash; inspect `Saved:` and the output file. Exit `2` indicates an actual benchmark execution failure.

For each of the two acronym requirements, inspect the JSON's `rows[].model_attempt_history`:

```json
[
  {"phase":"initial", "status":"not_matched", "evidence_ids":[], "matched_term":null, "call_index":0},
  {"phase":"second_look", "status":"matched", "evidence_ids":["S003"], "matched_term":null, "call_index":1},
  {"phase":"focused_abbreviation", "status":"not_matched", "evidence_ids":[], "matched_term":null, "call_index":2}
]
```

The block above is **only an illustrative trace shape**, NOT measured data from the user's Qwen. A `matched` model proposal can be invalidated by source validation when `matched_term` is missing; conversely a focused `not_matched` confirms the model rejected the acronym even with isolated context.

## Next engineering decision

If Qwen still returns `not_matched` in a focused request, **do not add ungrounded Python synonyms or remove source checks** just to boost this tiny dataset. Further solutions would need a broader independently labelled abbreviation set across professions, side-by-side testing of a better local model or a different constrained output schema, and latency measurement. A complete experience/qualification constraint system and scalable applicant workflow remain separate priorities for industrial readiness.
