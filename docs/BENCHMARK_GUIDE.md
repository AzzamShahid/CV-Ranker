# CV Ranker Labelled Benchmark

## Purpose

This benchmark measures the behavior of the current local model against human-readable labels. It is deliberately separate from runtime ranking code.

Production modules under `cv_ranker/` never import `evaluation/benchmark_cases.json`.
The skill and requirement names inside the benchmark are test fixtures, not a hardcoded production skill catalogue.

## Dataset

The bundled benchmark contains 5 scenarios and 21 labelled requirement decisions. It includes:

- exact evidence
- semantic abbreviations
- semantic paraphrases
- explicit OR alternatives
- years-of-experience constraints
- explicit negation
- learning-only evidence
- related-but-different technologies
- job-title / degree false-positive protection
- contradictions
- prompt-injection-like resume text
- standalone uppercase skills
- education and certification requirements

Each row includes a short rationale so that a human can review whether the expected label is sensible.

## Assessment-only benchmark

```powershell
.\.venv\Scripts\python.exe -m evaluation.evaluate_benchmark --scope assessment --output outputs\benchmark_assessment.json
```

This freezes the labelled requirements directly and tests the CV assessment contract. It is the best mode for evaluating Qwen's semantic resume decisions without mixing in JD extraction variability.

## Full pipeline benchmark

```powershell
.\.venv\Scripts\python.exe -m evaluation.evaluate_benchmark --scope pipeline --output outputs\benchmark_pipeline.json
```

This creates temporary explicit Required/Preferred JDs and exercises:

```text
JD -> YAKE -> Qwen JD validation -> frozen requirements
   -> Qwen CV assessment -> Python safety/source checks
   -> deterministic score/report
```

A missing or semantically renamed frozen requirement is counted as a failure rather than silently ignored.

## Metrics

The runner reports:

- requirement-level accuracy
- matched precision
- matched recall
- matched F1
- per-category accuracy
- expected/predicted status confusion counts

These results describe only this small benchmark. They are not evidence of general 99% accuracy.

## Evidence-quality gate (added)

A benchmark that secretly fell back to deterministic logic is **not** a valid measurement of the live Qwen-assisted path. The runner now records `measurement_quality` for every run:

- `valid_live_llm_measurement=true` means every requirement row used `llm_assessed` (and, for `pipeline`, the JD used `llm_validated`). This measures **Qwen plus Python validation**, not an isolated raw Qwen response.
- `false` means one or more rows used `mixed`, `fallback_exact`, an unvalidated JD mode, or an incomplete result. Accuracy is shown only diagnostically and **must not** be presented as clean live-model accuracy.

Benchmark JSON includes `build_id`, `assessment_protocol`, and `benchmark_data_sha256`. A complete, clean run exits successfully **even when some predictions are wrong**. A contaminated measurement uses exit code `3`, and writes diagnostics rather than concealing fallback.

## Comparing both runs

First generate both outputs on the computer where Ollama is running:

```powershell
.\scripts/run_benchmark.cmd
.\scripts/run_benchmark_pipeline.cmd
.\scripts/run_compare_benchmarks.cmd
```

The final command saves `outputs/benchmark_comparison.json`, showing whether the runs used the same model, build and dataset, and splitting differences into cases including:

- `jd_requirement_lost_or_renamed`: the JD stage failed to retain a labelled requirement
- `assessment_correct_pipeline_wrong`: possible pipeline/JD/interaction failure
- `assessment_wrong_pipeline_correct`: prompt variability or cross-stage difference to investigate
- `both_wrong`: a shared semantic/validation weakness to inspect

**Do not equate these classifications with proven root causes**: both modes make separate live model calls, so they may differ due to nondeterministic model behavior. The dataset is small (21 decisions) and must not be treated as a general accuracy guarantee. The comparison refuses to call mismatched datasets/builds or fallback-contaminated results a clean matched comparison.


## Raw Qwen vs validated decision trace (October 2026 checkpoint)

Each benchmark row now records three distinct stages **without changing production scores**:

1. `raw_initial_status`: Qwen's initial structured response.
2. `raw_final_status`: the latest Qwen structured response after any corrective call.
3. `predicted`: the final status after Python source/safety validation and possible deterministic recovery.

Additional fields: `raw_evidence_ids`, `raw_matched_term`, `llm_attempts`, and
`decision_path`. JSON includes `raw_model_diagnostics` with the number of
model-observed rows and post-model status changes. The comparison JSON also
includes raw statuses for disagreement rows. This captures *where* a status
changed; it does not prove that a model answer was semantically correct.

A sample diagnostic:

```text
Requirement: Python
Raw Qwen: not_matched
Final Python-validated result: matched
Decision path: python_or_fallback_changed_status
```

This case must not be described as a correct standalone Qwen decision. The
benchmark's `measurement_quality` flags fallback/mixed decisions. By contrast,
`llm_assessed` describes the complete Qwen + Python validator pipeline, and is
still not a pure raw-model accuracy guarantee. Raw-model status accuracy is
reported only over rows actually observed from structured Qwen outputs.

The 21 scenarios are synthetic, author-labelled and *human-reviewable*, **not**
independently human-validated or representative of all applicant populations.
Do not claim 99% real-world accuracy from these fixtures.

## JD source completeness checkpoint

The full-pipeline benchmark now records `jd_source_resolution` for each row:
`kept_model_source_match`, `restored_from_explicit_source`, or a diagnostic
rejection/cap state. Source restorations make the JD stage
`fallback_structural_after_llm`, so the benchmark is **not** a clean all-LLM
measurement even if the exact requirement set is complete. This separates the
quality of the Qwen JD extraction from source-recovered denominator correctness.
The regular ranking JSON additionally records the full `jd_diagnostics` array.

In the five benchmark JDs, explicit source items can be recovered without
inventing requirements or a fixed profession-specific catalogue. A restored
item can still be scored incorrectly by Qwen's CV assessment: these are
separate errors and should be debugged separately. The 21 benchmark labels
remain unchanged.

## Evidence context checkpoint (2026-10-08)

After JD-completeness protection, Phase 2 accepts short matched phrases and
source-grounded semantic citations even when Qwen omits `matched_term`. It
requires actual segment IDs; semantic meaning remains Qwen's responsibility.
Deterministic safety checks still handle instruction text, negative/learning
language, and job-title-only/degree-only skill claims. Reports include
`evidence_segments` with section and full text for display.

Existing 21 labelled benchmark rows/expected statuses are unchanged. Re-run
assessment and full-pipeline benchmark on the local Ollama machine; passing
synthetic tests here is not a measured Qwen accuracy percentage.

## Repeated paired batch-size reliability experiment (October 8 checkpoint)

**Reason:** the live single-trial comparison returned 76.19% (batch 20) and
80.95% (batch 3), but both configurations missed the explicit NLP abbreviation
and made related-technology errors. Batch 3 changed four decisions: two became
correct, two became incorrect. The small difference does not justify changing
production batch size.

Use the new evaluation-only, three-pair command:

```powershell
.\scripts/run_repeatability_probe.cmd
```

Or choose fewer/more **paired** trials (example: two) and a separate output path:

```powershell
.\.venv\Scripts\python.exe -m evaluation.repeatability_probe --repeats 2 --batch-sizes 20 3 --output-dir outputs\my_repeat_probe
```

The command alternates run order: trial 1 uses 20 then 3, trial 2 uses 3 then
20, and so forth. This reduces, but does not eliminate, order effects.
Outputs are in `outputs/repeatability_probe/`:

- `trial_01_batch_20.json`, `trial_01_batch_3.json`, etc. — original benchmark decisions, including Qwen/Python traces;
- `trial_01_batch_20.log`, etc. — complete benchmark console diagnostics;
- `repeatability_summary.json` — means, ranges, trial-level false positives,
  missed matches, per-requirement flip counts and paired differences.

Interrupted run files can be analyzed without more Ollama calls using:

```powershell
.\.venv\Scripts\python.exe -m evaluation.repeatability_probe --analyze-only --output-dir outputs\repeatability_probe
```

Keep runs on the **same build, model, scope and benchmark SHA-256**. The tool
rejects changed labels, missing requirement results, duplicate trials or mixed
identities. A fallback-assisted run can be included *diagnostically*, but is
never reclassified as Qwen-only accuracy. Each output's `decision_path` and
`raw_model_diagnostics` remain authoritative for understanding interventions.

Do **not** use the majority prediction as a production ranking algorithm. It
would silently multiply Qwen calls and change the supervisor-approved MVP.
A three-pair probe is still a small, nonrepresentative diagnostic and cannot
prove general accuracy or optimal batching.

The hard cases requiring further model-level evaluation remain semantic
abbreviations (`NLP` and `GCP`), contextual AI-application evidence, title-only
proficiency, and a cited *different* technology (`Django` vs `FastAPI`, `Redis`
vs `PostgreSQL`). Since those semantic distinctions are not verifiable by
generic Python string rules, the system must not conceal the limitations with
hardcoded skill mappings or a hidden verifier.
