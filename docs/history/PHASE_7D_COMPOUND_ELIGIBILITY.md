# Phase 7D — Explicit compound criteria and reviewer-selected eligibility gates

**Build ID:** `compound-eligibility-verification-2026-10-13`  
**Baseline:** Phase 7C `typed-qualification-verification-2026-10-12` — **361 tests**, live Windows health **READY**, assessment **19/21** and full pipeline **18/21** in mixed Qwen/Python mode.  
**Phase 7D status:** Regression- and end-to-end tested **offline**. Live Ollama accuracy is **NOT measured** for Phase 7D until Windows logs are supplied.

## Why

The frozen JD requirement metadata already labels simple `any_of`/`all_of` clauses but, before 7D, the assessor could grant the entire clause without checking each component. In addition, required-criterion coverage was conflated with employer-selected essential/eligibility criteria. This phase separates these concepts without allowing the LLM to invent a gate or change the scoring formula.

## Exactly what is implemented

1. **Simple AND**: A short JD-explicit phrase such as `Python and Django` must have affirmative resume evidence for **both** literal components. One skill is insufficient. A learning-only or conflicting claim becomes `uncertain` when the other component is supported. Missing one component yields `not_matched`.
2. **Simple OR**: A phrase like `TensorFlow or PyTorch` requires at least one affirmatively sourced alternative. Missing both gets `not_matched`; a learning-only alternative with no confirmed one yields `uncertain`.
3. **No transferable bonus**: `FastAPI` is not silently equivalent to `Django`. This stage does not use a synonym catalogue, embedding search, or invented options. A CV must mention the component literally in capability-supporting source text, in an allowed section. A negative/learning-only/contradictory source, unrelated team mention or injected instruction cannot silently earn credit.
4. **Complex/non-atomic cases**: Mixed AND/OR, education-plus-licensing alternatives, quantitative compound thresholds, multi-clause syntax, and other ambiguous expressions are not automatically decided by this module. A previously matched ambiguous compound is conservatively set to `uncertain` until reviewed. Do **not** represent this as a complete general Boolean parser.
5. **Frozen scoring contract**: Each compound requirement remains **one** frozen criterion (`R001` etc.), irrespective of 2–3 inner components. Python uses the unchanged `matched_primary / total_primary * 100` formula. An unmet or uncertain compound earns zero credit. The report exposes per-component `status`, source segment IDs and explanations.
6. **Optional HR-selected gates**: No policy supplied => `eligibility.status=not_configured`. If HR supplies a validated JSON policy, selected **required** frozen criteria are designated as document-screening gates. The policy includes an exact JD content SHA-256, reviewer declaration and rationale per criterion. Unknown, changed, preferred, duplicate, oversized or wrong-JD gates fail closed. This is an **unauthenticated reviewer declaration** until a future access-control workflow exists.
7. **Separate statuses**: `criteria_satisfied`, `criteria_unmet`, `needs_review`, `not_configured`, `evaluation_failed`. These concern evidence in the CV, **not** legal employment eligibility, license authenticity or automatic applicant rejection. A claimed active license can be a `matched` qualification but **still** triggers `needs_review` when gated, since authorities have not checked validity. Do not treat `criteria_satisfied` as a final hire/reject decision.
8. **Scoring and ranking independence**: Optional gates cannot change the score, the matched denominator, or rank. Equal percentages remain tied. Review outcomes are displayed separately in CLI, Streamlit and JSON reports.

## Data flow

```text
JD document -> frozen JD requirement set -> Phase 7A typed attributes
CV document -> Qwen/fallback evidence -> aliases -> numeric experience
            -> degree/certification/license claim validation
            -> Phase 7D simple source-literal AND/OR components
            -> original Python percentage scorer -> ranked candidates
                                       |
Optional HR policy (JD SHA-256 + exact required names + reviewer/rationale)
                                       |
                    separate criteria/review status (does not rerank)
```

## Optional policy file format

Create the blank policy from the Streamlit **JD requirements** tab **after running the exact JD once**. It will prefill `jd_sha256` and one eligible requirement name. Replace the reviewer and rationale placeholders, choose the desired existing required names, and rerun the same JD with the file. For a CLI demo, a pre-filled **EXAMPLE, not a valid authenticated HR authorization** lives at `sample_data/compound_eligibility_policy.EXAMPLE.json`.

```json
{
  "schema_version": 1,
  "jd_sha256": "<64 lowercase hexadecimal digits for this exact JD text>",
  "reviewed_by": "Authorized reviewer declaration",
  "gates": [
    {"requirement": "Python and Django", "reason": "Employer considers both required"}
  ]
}
```

The fingerprint binds to extracted JD **text**, not a path or file name. If extracted text changes, update and reapprove the file. The exported report retains policy SHA-256 and per-gate rationales. Review identity is **recorded, not authenticated**. No RBAC, cryptographic signature, real government/licensing verification or automatic reject action exists.

## Windows commands

In a **new folder** containing the Phase 7D ZIP files, with your functioning `.venv` retained:

```powershell
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe doctor.py --live
.\scripts\run_benchmark.cmd
.\scripts\run_benchmark_pipeline.cmd
.\run_ui.cmd
```

**Deterministic demonstration without HR gates:**

```powershell
.\.venv\Scripts\python.exe main.py --no-llm --details --jd sample_data\compound_jd.txt --resumes sample_data\compound_resumes --output outputs\compound_no_gates.json
```

**Same JD and CVs with explicit HR demo policy:**

```powershell
.\.venv\Scripts\python.exe main.py --no-llm --details --jd sample_data\compound_jd.txt --resumes sample_data\compound_resumes --eligibility-policy sample_data\compound_eligibility_policy.EXAMPLE.json --output outputs\compound_with_gates.json
```

Both runs should show the **same primary percentages/ranks**. Only the `eligibility` section differs. The positive resume scores 100%, four others 66.67%, with clear compound details. The positive case has `criteria_satisfied` only if the demo HR policy was supplied; missing components produce `criteria_unmet`; learning and contradictions produce `needs_review`.

## Modified files

- `cv_ranker/compound_validation.py` — new standalone AND/OR verifier with source evidence and tone checks.
- `cv_ranker/eligibility.py` — new optional, JD-bound review gate loader and separate document-evidence outcome.
- `cv_ranker/schemas.py` — adds component/compound and eligibility result structures without removing old fields.
- `cv_ranker/pipeline.py` — calls the compound verifier before scoring and sets eligibility separately after scoring.
- `cv_ranker/config.py`, `main.py` — new optional `--eligibility-policy` setting.
- `cv_ranker/report.py`, `cv_ranker/ui_support.py`, `app.py` — per-component citations and candidate gate status, UI template/download.
- `tests/test_phase7d_compound_and_eligibility.py` — decision truth tables, prompt injection, cross-skills, policy binding, score independence, end-to-end.
- `sample_data/compound_jd.txt`, `sample_data/compound_resumes/`, `sample_data/compound_eligibility_policy.EXAMPLE.json` — supervisor demonstration files.

## Checked for backwards compatibility

The Phase 7C and Phase 7D deterministic fallback reports were compared on **Backend (4), HR (3), Experience (4), Qualification (3), License (4)**: 18 candidate primary percentages, per-requirement statuses and rank assignments were identical. This does not establish live model stability or production-grade accuracy.

## Known scope limitations

- Only simple explicit 2–3 term all-of/any-of **atomic skill** alternatives are evaluated. Other compound types are review-needed; there is no parse-tree/precedence solver.
- No cross-language/source-neutral semantic synonyms, job-specific skills catalogue, or arbitrary similarity scoring.
- `not_matched` reflects *lack of sufficiently supported CV evidence*, not proof the person lacks a competency. Human follow-up is essential before adverse employment action.
- Employment authorization, actual professional licensing, and credential validity cannot be determined from a resume alone.
- JD parsing and source extraction remain imperfect; PDF tables and scanned sources can require manual correction.
- No authenticated HR accounts, durable approval workflow, candidate appeals, fairness audit, employer-policy rules engine, or industry-size benchmark. Those belong to future stages.
- The historical 21-case benchmark is too small and mixed-mode to measure production accuracy. Do not claim 99% accuracy or a clean Qwen-only result.
