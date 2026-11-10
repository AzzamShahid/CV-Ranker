# V4.8.3 — Live evidence calibration and stricter grouped prompts

27 October 2026. This release builds **only** on the independent V4.8.2
retrieval-first branch; the approved V4.7 ZIP remains unchanged.

## Why

The fictional Sara CV in the first successful V4.8.2 live assessment showed:

- R004 Machine Learning and R005 Deep Learning correctly recovered with
  source-backed PyTorch training examples.
- R018 *production-oriented AI work, including deployable AI applications,
  APIs, containerized services, or cloud-ready solutions* was reset from a
  sourced performed-work assessment to uncertain. The generic Boolean checker
  treated its illustrative list as an unevaluable complex AND/OR statement,
  discarded all citations, and withheld credit.
- R014 Time-series forecasting was marked Found based on documented seasonal
  anomaly screening. The CV does demonstrate time-series work, but screening
  for anomalies does **not by itself** demonstrate making forecasts.
- R009 LangChain was Not Found while comparable performed work justified a
  Transferable classification for R012 LangGraph. Direct platform use remains
  negated for both, but completed comparable work can count as transferable.
- Four candidate assessment notices shown in the UI were absent from the
  exported `Notices` array; run-wide warnings were omitted entirely.

## Changes

1. **General, not department-specific Python compound fix.** For a
   non-numeric `experience` criterion with complex Boolean metadata and
   illustrative wording (`including`, `such as`, `for example`) followed by
   OR examples without a separate mandatory AND clause, preserve a
   source-validated Found if it cites genuinely completed work in employment
   or projects. Label it *human review recommended*. A bare skills list,
   denied work, unrelated claim, or missing performed-work citation cannot
   gain a match from this exception. Exact numeric years, degrees, licenses,
   and actual compound skills stay under their earlier conservative guards.
   Preserve unresolved citations instead of clearing review context.
2. **Firmer yet grouped LLM prompt.** Mandatory entailment test for Found;
   positive listed skills remain accepted for ordinary skill JDs; related
   completed tasks become Transferable (zero direct points). Distinguishes
   anomaly detection/time-series features from forecasting, tool denials from
   completed analogous workflows, reported GCP from undocumented GCP, and
   operational AI delivery from a toy demonstration. Reconciles explanation
   with status and requires valid original segment IDs. JD extractor prompts
   retain descriptive `including` examples with the broad original criterion.
3. **Export provenance.** `Notices` now preserves the candidate's validation
   notices shown in UI, with duplicates removed. `Run warnings` includes
   pipeline-level notices separately. No model call is added for display.
4. **Regression coverage.** New isolated tests cover the three decisions,
   positive and negative experience evidence, genuine complex Boolean gates,
   and export consistency. Tests are synthetic and require no cloud calls.

## Unchanged

- YAKE and source-grounded LLM JD extraction, frozen required/preferred IDs.
- Approved EmbeddingGemma-2-only local semantic retrieval and segment mapping.
  **No BM25, lexical search engine, new reranker, or extra search stage.**
- Grouped LLM assessment with one grouped correction where needed; no
  per-requirement model request loop. The prompt is longer, but no new call
  stage was introduced; actual batching and tokens depend on context limits.
- Source-ID validation, independently verified experience/degree constraints,
  and full Found/Transferable/Not Found explanations.
- Required Found / Required total determines ranking percentage; Preferred
  Found only breaks ties; Transferable adds no direct points.
- The proposed 10/10/80 customizable weights and employment-gap annotations
  remain **out of scope** for this build.

## Verification on Windows

Use the **extracted V4.8.3 folder** rather than mixing files into V4.8.2.

```powershell
.\run_tests.cmd
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe doctor.py --live
.\run_ui.cmd
```

Analyze `03_sara_functional_transfer.pdf` and inspect original S008/S012
evidence for R018, R014 anomaly-screening as Transferable instead of direct
forecasting, and R009/R012 independent completed work. Model outputs are
probabilistic: prompt changes are not proof of future classification accuracy.
Also inspect `04 Technical details` for the *actual* requests and tokens from
the selected provider. The assessment was not re-run live in this environment.
