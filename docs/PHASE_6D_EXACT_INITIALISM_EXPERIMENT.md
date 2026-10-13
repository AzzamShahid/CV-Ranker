# Phase 6D — Exact Initialism Recovery (Opt-in Experiment)

**Build:** `literal-initialism-experiment-2026-10-12`  
**Model:** unchanged local `qwen2.5:3b` (Ollama/LangChain).  
**Status:** Regression-tested **offline only**. New Phase 6D live Qwen benchmark scores are **not yet measured**.

## Evidence from the user's Phase 6C live log

The prior `focused-acronym-diagnostics-2026-10-12` build passed **218 tests**, reported `doctor.py --live` **READY**, and scored **19/21 (90.48%)** in both assessment-only and end-to-end pipeline tests. On that 21-row sample, matched precision was **100%** and recall **83.33%**, but execution was mixed Qwen/Python, not clean Qwen-only accuracy.

The missed requirements remained:

- `Natural Language Processing` vs literal CV text `NLP`. In assessment, Qwen first returned `not_matched`, its grouped second look proposed `matched` with `S003` but **no `matched_term`**, so Python correctly rejected that proposal. Focused Qwen then returned `not_matched`.
- `Google Cloud` vs literal CV text `GCP`. In the full pipeline, initial Qwen sometimes proposed `matched` with `S004`, but no `matched_term`; correction and focused retry produced `not_matched`.

Extra Qwen retries did not improve this small benchmark. The correct diagnosis is inconsistent model semantics **and** an enforced citation contract, **not** that the program lost the source lines.

## What changed

1. `cv_ranker/assessor.py` now includes `_literal_initialism()` and `_literal_initialism_guard()`. They are isolated, deterministic **orthographic** checks. A JD with exactly **3–5 Title-Case words** can produce the first-letter acronym: `Natural Language Processing` => `NLP`. The guard only accepts the exact acronym when it really appears in `skills`, `experience`, `projects` or `summary`, and the source passes instruction/tone/capability checks. It preserves `S00x` IDs, the full evidence line and `matched_term` and marks the batch **mixed** if Python changed a Qwen negative.
2. `Settings.exact_initialism_guard` defaults to **False** for safety and backward compatibility. No user experience changes without deliberately enabling the experiment. The feature is offered via `--exact-initialism` on the CLI and benchmark and an unchecked Streamlit sidebar checkbox.
3. Benchmark JSON now records whether the experiment was enabled. This supports A/B comparisons of the *same build* and test data.
4. Added tests for opt-in recovery, default-off behavior, source citations, learning/negation/contradiction, title/degree-only evidence, prompt-injection-like text, token boundaries, and non-inferable acronyms.

### What it intentionally does not do

- `Google Cloud` has only two initials (`GC`). `GCP` includes another letter. The source text `GCP` cannot be justified solely by extracting the initials of `Google Cloud`. The program **does not** automatically grant it credit. Supporting this safely requires Qwen to produce a valid evidence-anchored judgment, an explicit matching expansion within the submitted materials, or a human-reviewed JD-specific alias confirmation.
- No predefined skill dictionary, manually hardcoded `NLP` or `GCP` rules, embeddings, vector search, new verifier, score bonuses, or changes to ranking formula.
- The spelling-only heuristic can be ambiguous for short initialisms across industries. Treat the experiment as **human-review-required for consequential hiring decisions**, even when it identifies a source line.
- The check does not repair the larger need for typed degree, certification, experience and eligibility constraints.

## Windows: Phase 6D same-build A/B

Keep your existing `.venv` when replacing source files, then run:

```powershell
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe doctor.py --live

# Baseline: exact-initialism recovery disabled (default)
.\.venv\Scripts\python.exe -m evaluation.evaluate_benchmark --scope assessment --scenario semantic_positive --output outputs\phase6d_baseline.json

# Experimental: literal-initialism recovery enabled
.\.venv\Scripts\python.exe -m evaluation.evaluate_benchmark --scope assessment --scenario semantic_positive --exact-initialism --output outputs\phase6d_initialism.json

# Optional full JD->CV experiment
.\.venv\Scripts\python.exe -m evaluation.evaluate_benchmark --scope pipeline --scenario semantic_positive --exact-initialism --output outputs\phase6d_pipeline_initialism.json
```

Inspect final statuses, `model_attempt_history`, `decision_path`, matched term and source IDs. The benchmark's normal **exit code 3** means mixed Qwen/Python execution was detected, even if results were saved; it is not automatically a process crash.

The feature can also be enabled in the Streamlit sidebar with **Experimental exact-initialism matching**, or via `main.py --exact-initialism`.

## Next milestone

Avoid training the design around a 21-row benchmark. Expand the benchmark with an independent multi-industry abbreviation set, require review of any non-exact alias before scoring, and prioritize **typed JD constraints, numeric experience and qualification validation, and a recruiter approval workflow**.
