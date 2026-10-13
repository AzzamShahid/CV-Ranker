# Phase 7E — Expanded ranking and requirement benchmark

**Build:** `industrial-benchmark-v1-2026-10-13`  
**Baseline:** Phase 7D `compound-eligibility-verification-2026-10-13`: 404 automated tests passed, Windows `doctor.py --live` READY, 21-case assessment 19/21 and end-to-end pipeline 18/21 (both mixed-model/Python measurements; not clean Qwen scores).

## Why Phase 7E exists

The same 21 labels had been reused through multiple releases. A general HR CV Ranker cannot establish reliability from those small, partly mixed-mode cases. This phase adds **strictly evaluation-only** files, not production scoring modifications. It is a measurement release, not a candidate-matching fix.

## Implemented, and exact boundaries

- **Frozen synthetic dataset v1:** 8 separate role JDs, each with 5 resumes. Exactly 40 candidate files, 5 requirements per JD (4 required + 1 preferred), and 200 hand-authored per-candidate/per-requirement status labels. Areas: backend, AI/ML, HR, finance, manufacturing, procurement, customer support, healthcare. All text only; no external applicant details. Labels include exact resume source excerpts for expected `matched` and `uncertain` claims.
- **Independent from ranker output:** Labels are in `evaluation/industrial_dataset/labels.json`. Neither the ranking pipeline nor Qwen generates the reference statuses. Synthetic labels were **manually authored for evaluation**, but have **NOT been independently adjudicated by multiple HR experts**. See [labeling protocol](../evaluation/industrial_dataset/LABELING_PROTOCOL.md).
- **Strict preflight validation:** Requires unique JDs, requirement IDs/names and candidate IDs; a label for every JD requirement for every candidate; exact source excerpts for positive/uncertain labels; JD requirement text present in source; blocked relative-path escape. Dataset SHA-256 includes `labels.json` and every JD/resume file to prevent silent comparison drift. Invalid fixtures fail without a score.
- **Two comparable modes:** `fallback` runs the **same production CVRanker** with `use_llm=False`; `live` runs **the same production CVRanker** with the local Qwen model. The latter reports combined validated outcomes and can include Python fallback; it must **not** be called Qwen-only accuracy. The production `main.py`, `cv_ranker/` assessment/scoring modules, prompt set and dependency pins are unchanged (except build identity).
- **Full JD coverage:** Match frozen output requirements to each label by the exact JD wording (whitespace/case normalized, **no semantic aliases**). Track JD extraction precision/recall, wrong priorities, invented output criteria, duplicates and missing criteria. Missing frozen requirements produce `missing` predicted status on each affected candidate, **not** an ignored row.
- **Three-class confusion:** Compute exact status accuracy, matched precision/recall/F1, false-positive credited matches, missed true matches, uncertain recall and per-category/department results. Zero denominators return `null`/N/A rather than a deceptive 100%.
- **Ranking evaluation:** Gold matched-required/total-required score is calculated **from manually assigned statuses**, independently of the model's scoring output. Pairwise order agreement compares all candidate pairs **including score ties**, with missing candidates counted as disagreement. Also reports top-ranked group overlap and nDCG@3 (using the number of correctly matched required criteria as the gain). High nDCG can coexist with many exact-status errors.
- **Comparison utility:** Checks identical dataset SHA-256, selected scenario list, and full row identity before classifying improvements, regressions and changed-but-still-wrong statuses. Refuses comparison across different labels.
- **Supervisor artifacts:** JSON with case-level predictions and gold source excerpts, Markdown summary and detailed failures, built-in fallback baseline under `evaluation/results/industrial/`.

## Observed offline baseline — the actual result, not a target

The Phase 7E fallback run against synthetic v1 on this machine reported:

| Metric | Baseline value |
|---|---:|
| Job descriptions | 8 |
| Candidates | 40 |
| Labelled decisions | 200 |
| Exact 3-status accuracy | 148/200 = 74.00% |
| Matched precision | 96.20% |
| Matched recall | 63.87% |
| Matched F1 | 76.77% |
| False-positive credited matches | **3** |
| Missed matches | **43** |
| JD extraction precision/recall | 100% / 100% on these structured TXT examples only |
| Macro pairwise rank agreement including ties | 76.25% |
| Macro nDCG@3 | 98.91% |
| Modes | 11 `fallback_exact`, 29 `mixed` |

**Safety-relevant finding:** Three resumes with Python, production, or customer support stated as separate skills/activities plus *general career duration* were awarded a `matched` on a **skill-specific numerical experience minimum**, despite manually labelled `uncertain` evidence. The three cases are `ai_ml/unscoped_years/R004`, `manufacturing/unscoped/R004`, and `customer_support/unscoped/R004`. These are real false-positive findings of this synthetic fallback test. Preserve these failing cases; do not relax the ground truth just to raise accuracy. A subsequent targeted correction should inspect source segmentation, subject-duration scoping, and whether a Python post-validator is actually enforcing the context it assumes. Any fix needs before/after benchmark and tests.

Finance, healthcare, and other domain-specific phrase mismatches also generated false negatives. Treat those as measured limitations, not justification for a hardcoded general skill dictionary.

**This baseline does NOT measure the live Qwen model**: that must run on the user's Windows Ollama installation. It is also not externally adjudicated, not PDF/DOCX/OCR coverage, not fairness validation, and not an industrial production accuracy result.

## Windows validation and commands

Keep Phase 7D as a backup and install this ZIP in a clean folder, preserving `.venv`.

```powershell
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe doctor.py --live
```

Run **evaluation-only**, no local model required:

```powershell
.\scripts\run_phase7e_fallback.cmd
```

Run against local Ollama using the identical dataset:

```powershell
.\scripts\run_phase7e_live.cmd
```

Compare different runs with the same dataset:

```powershell
.\.venv\Scripts\python.exe -m evaluation.compare_industrial --baseline outputs\phase7e_fallback.json --current outputs\phase7e_live.json --output outputs\phase7e_comparison.json
```

Run a single area to investigate a failure (e.g. finance):

```powershell
.\.venv\Scripts\python.exe -m evaluation.evaluate_industrial --mode live --scenario finance --output outputs\phase7e_finance.json --markdown outputs\phase7e_finance_report.md
```

The evaluator prints metrics and writes JSON/Markdown, but does **not** fail the process merely because a prediction is wrong: measurement is the purpose. Exit code `3` indicates a pipeline/candidate **execution failure**; code `2` indicates invalid dataset or invocation.

## Files added or modified

- `evaluation/industrial_dataset/` — gold labels, 8 JD files, 40 resumes, human-labeling protocol (evaluation-only).
- `evaluation/evaluate_industrial.py` — dataset integrity checks, same-engine multi-JD evaluation, metrics, JSON/Markdown outputs.
- `evaluation/compare_industrial.py` — checked before/after row comparison.
- `evaluation/results/industrial/phase7e_fallback_baseline.json` and `phase7e_fallback_report.md` — observed offline baseline included as reference; local file paths in historical outputs are not replay inputs.
- `scripts/run_phase7e_fallback.cmd`, `scripts/run_phase7e_live.cmd` — Windows entry points.
- `tests/test_phase7e_industrial.py` — source tampering, missing/duplicated labels, confusion, ranking tie safety, comparison, and actual pipeline tests.
- `docs/PHASE_7E_INDUSTRIAL_BENCHMARK.md`, `docs/VALIDATION.md`, `README.md` — guidance and explicit limitations.
- `cv_ranker/build_info.py` and `cv_ranker/build_manifest.json` — new build identification and SHA-256 hashes only.

## Next decision — measure first, then fix

Phase 7E creates a repeatable baseline. Do **not** immediately continue adding new features; the first corrective milestone should be **experience false-positive containment** (source-scope validity and segment bridging), followed by an independently adjudicated and realistic PDF/DOCX document benchmark, and a separate ranking fairness/privacy review. Keep current scoring, do not introduce embeddings, invented synonyms or automated adverse hiring decisions.
