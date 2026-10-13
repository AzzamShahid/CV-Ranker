# Phase 6A — Scoring and Evidence Contract Integrity

**Build:** `scoring-contract-experience-2026-10-12`  
**Status:** Offline checks only; new logic has NOT yet been tested against the user's live local Qwen.  
**Goal:** Repair reproducible correctness defects found in the industrial-readiness audit without changing the architecture or primary scoring policy.

## Real user results that motivated the work

The Phase 5 user-provided Windows log showed `READY`, 195/195 local Python tests and **19/21** correct requirements for *each* of assessment and full-pipeline evaluation. This is combined-system diagnostic accuracy only; both `NLP` and `GCP` were still missed. A Qwen `matched` proposal sometimes becomes `not_matched` after evidence validation, correctly separating raw model judgment from the accepted final decision.

## Phase 6A changes

1. **Defensive scoring boundary** (`cv_ranker/scoring.py`): `score_candidate()` now independently requires exactly one assessment for every frozen JD requirement. It rejects duplicate requirement IDs, duplicate assessment IDs, missing assessment IDs and unexpected assessment IDs with `ValueError`. This prevents the demonstrated 200% score from double-counting two identical matches. The pipeline already catches candidate-level exceptions and records failures rather than issuing invalid ranks.
2. **All-or-nothing citation contract** (`cv_ranker/segments.py`): `resolve_segment_ids()` validates the *entire* ID list, rejects duplicates and rejects more than three IDs. Previously it truncated at three, potentially concealing a fabricated fourth citation. Malformed matched/uncertain rows remain eligible for the existing Qwen corrective attempt.
3. **Narrow numeric contradiction check** (`cv_ranker/constraints.py`, `cv_ranker/assessor.py`): When a JD explicitly requires an `N years` minimum for a named subject (e.g. Python) and **all clearly scoped cited durations** state fewer than N years, a Qwen `matched` cannot be accepted; the row is sent to the existing correction mechanism. Unrelated subjects and ambiguous clauses are not automatically decided. This check does **not** compute actual employment history, parse career dates, handle overlap, or verify professional credentials.
4. **Regression tests** (`tests/test_phase6_integrity.py`): boundary checks for invalid scoring input, fourth/fabricated evidence citations, duplicates, and under-threshold numeric claims.

No new LLM, no embeddings, no vector retrieval, no hardcoded skill synonym list, no preferred-skill bonus, and no change to `assessment_batch_size=20`.

## Why two abbreviations remain unresolved

The cited user run correctly retained negatives for `NLP` and `GCP` because the model failed to produce a valid, accepted source-anchored match. Do **not** bypass citation validation or add secret Python alias mappings just to raise the score on two benchmark labels. The next evaluation should include multiple natural-language and acronym variants across departments and explicitly record invalid source terms and correction outcomes.

## Known industrial limitations after this patch

- Named semantic equivalence is still decided by a small model; valid segment provenance does not prove semantic entailment.
- Skills, degree fields, certifications, licenses and experience thresholds are not yet represented as fully typed criteria approved by HR.
- Date-based total relevant experience, overlap, eligibility gates, OCR, robust document-location spans, multi-user security and audit history are not implemented.
- Automatic filtering on this score alone is not appropriate for consequential hiring decisions.

## Validate on the Windows development machine

```powershell
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe doctor.py --live
.\scripts\run_benchmark.cmd
.\scripts\run_benchmark_pipeline.cmd
```

**Deployment note:** Keep the existing `.venv` when updating project files. If benchmark measurements change, inspect both *final* and *raw model* statuses, the evaluation mode, and source citations before drawing conclusions.
