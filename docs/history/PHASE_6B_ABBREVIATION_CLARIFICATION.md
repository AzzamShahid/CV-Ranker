# Phase 6B — Bounded Acronym Citation Clarification

**Build:** `focused-acronym-clarification-2026-10-12`  
**Model:** the same local `qwen2.5:3b` through LangChain/Ollama.  
**Status:** Offline validation only until run on the user's local Ollama instance.

## Why this change exists

The user's Phase 6A Windows run passed 205 unit tests and `doctor.py --live`, and both 21-item benchmarks scored 19/21 (90.48%) using mixed model/Python logic. The only incorrect labels remained:

- `Natural Language Processing` with `NLP` cited in the resume.
- `Google Cloud` with `GCP` cited in the resume.

The grouped second look sometimes proposed `matched` for a named requirement without giving the **actual source `matched_term`**. Correctly, the validator rejected the unsupported citation and retained `not_matched`. Other grouped second-look attempts returned `not_matched` despite an acronym candidate. A real source ID alone does not establish semantic equivalence.

## Implementation

Files changed:

- `cv_ranker/assessor.py`: Added `_has_orthographic_acronym_lead` and `_focused_abbreviation_recheck`. After the existing grouped second look, unresolved requirements with a possible spelled initialism can receive an **individual, one-requirement Qwen clarification**. This code does not assert that an initialism equals the JD name; it only asks the same model. A `matched` outcome is accepted only after the existing source/citation rules and a verbatim `matched_term` check. All unresolved negatives remain uncredited. At most **two** extra focused requests are allowed per assessment batch.
- `cv_ranker/config.py`: Added `focused_abbreviation_retry=True` for a controlled experiment; `second_look_unmatched=False` disables the complete second-look mechanism.
- `evaluation/trace.py`: Labels focused requests as second-look calls in the existing benchmark provenance tracker.
- `tests/test_phase6b_focused_abbreviations.py`: New regression tests for invalid grouped citations, negative second-look outcomes, source-term rejection, no automatic acronym credit, the two-call limit and trace provenance.

### Deliberate boundaries

- **No skill synonym table, embedding model, vector database, or independent verifier.**
- Model interpretation is fallible: even a cited name can be semantically misjudged. This adjustment is a *bounded experiment*, not verified accuracy improvement.
- Default assessment batch size remains 20; scoring, frozen JD requirements, eligibility, and experience logic are unchanged.
- Additional Qwen requests cost latency. The upper bound is 2 new calls per requirement batch, only when a plausible acronym remains unresolved.
- The general writing-pattern heuristic `GC` -> `GCP` is **not** an equivalence rule. It is only used to select candidates for a question to Qwen.

## On Windows, run

```powershell
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe doctor.py --live
.\scripts\run_benchmark.cmd
.\scripts\run_benchmark_pipeline.cmd
```

Compare these against the **Phase 6A baseline** of assessment 19/21 and full pipeline 19/21. Review individual rows, status changes, `matched_term`, and `evidence_ids`, not the aggregate alone.

Run a same-build A/B by disabling the entire optional second-look feature with the evaluation command-line flag `--no-second-look`; this comparison turns off both the grouped and focused rechecks, so it does **not** isolate just the focused retry. For isolated testing, instantiate `Settings(focused_abbreviation_retry=False)` in the assessment harness while keeping `second_look_unmatched=True`.

## Interpretation guardrails

The 21-item benchmark is insufficient evidence of general hiring accuracy, production suitability, fairness, or statistical significance. The latest user-reported 19/21 is **from Phase 6A**, not from this build. A health-check `READY` means the miniature live pipeline is functional, not that the entire ranker is accurate.
