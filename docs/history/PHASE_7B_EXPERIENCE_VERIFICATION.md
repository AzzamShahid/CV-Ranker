# Phase 7B — Source-backed experience verification

**Build:** `typed-experience-verification-2026-10-12`  
**Baseline:** Phase 7A `typed-jd-requirements-2026-10-12` (267 passing baseline tests).  
**Status:** Deterministic offline validation only. Live Qwen results must be measured on the Windows/Ollama machine.

## Problem and scope

Previously, the same Qwen semantic match status could earn credit for a requirement of **5 years of Python** when the CV claimed **2 years Python**, or **6 years Java**, or **6 years general experience** next to a Python skill listing. Phase 6A provided a very narrow rejection of some explicitly insufficient cited evidence; Phase 7A introduced typed JD metadata but did not enforce it.

Phase 7B enforces a numeric experience gate **after** the existing LLM/fallback assessment and reviewed-alias stage, but **before** `score_candidate()`. It uses the same frozen JD requirements, candidate evidence and deterministic scoring. It does not use embeddings, a skill synonym dictionary, a second model, inferred career timelines, or inferred seniority.

## Files and responsibilities

- `cv_ranker/experience_validation.py` **new**: `check_experience` gathers source-backed literal duration claims and evaluates minimums; `apply_experience_checks` reconciles each typed experience assessment with the evidence, preserving separate diagnostics. `DurationClaim` and `ExperienceCheck` are strict Pydantic objects.
- `cv_ranker/requirement_typing.py`: recognizes additional plainly sourced JD subject forms, e.g. `5 years in Python`, `5 years Python`, `3 yrs using SAP`.
- `cv_ranker/schemas.py`: adds `RequirementAssessment.experience_check` for numeric provenance. Non-experience rows have `null`.
- `cv_ranker/pipeline.py`: invokes the experience gate after the LLM/fallback assessor and optional human-approved equivalents, before the scorer.
- `cv_ranker/report.py`, `app.py`: show the numeric outcome, explanation, source IDs and year bounds.
- `tests/test_phase7b_experience_verification.py`: new deterministic cross-domain, threshold, negative, uncertainty, adversarial and integration tests.
- `sample_data/experience_jd.txt`, `sample_data/experience_resumes/`: a four-candidate, no-LLM supervisor demonstration.

## Outcomes and score behavior

| Typed experience evidence | Numeric finding | Final assessment |
|---|---|---|
| `6 years of Python experience` vs required 5 | `sufficient` | `matched` with source citation |
| `2 years of Python experience` vs required 5 | `insufficient` | `not_matched` |
| `2–4 years of Python experience` vs required 5 | `insufficient` | `not_matched` |
| `2+ years of Python experience` vs required 5 | `ambiguous` | `uncertain` (0 credit) |
| `4–6 years of Python experience` vs required 5 | `ambiguous` | `uncertain` |
| `6 years of Java experience` vs required Python 5 | `not_evidenced` | `not_matched` unless separately supported |
| Python in skills, 6 years general experience separately | `ambiguous` | `uncertain` (0 credit) |
| `No Python experience` | `insufficient` | `not_matched` |
| `6 years Python` and `No Python experience` | `ambiguous` | `uncertain` |
| `2019–2026 Python developer` | no counted year-unit claim | does not get automatic credit |
| `Python developer with 5 years of total/professional experience` | `ambiguous` | no automatic skill-specific years |

A **sufficient** direct, unambiguous, positive statement may correct a Qwen false negative; this change is labelled `mixed` when the status changes. Inadequate source-backed evidence may downgrade a false positive. Source-citation IDs are attached from the resume segmenter. Ambiguous evidence is reported for human review; `uncertain` earns zero credit.

Numeric parsing supports `years`, `year`, `yrs`, decimals, fixed numbers, plus signs, ranges and explicit minimum wording. An open-ended lower bound like `2+ years` does **not** establish it is below 5 years, so it cannot justify the specific claim of insufficient total experience; it stays ambiguous.

## Deliberate non-goals / safety boundaries

1. **No inferred duration from dates** (`2019–2026`, overlapping employment or current date); future interval parsing requires explicit product policy.
2. No invented equivalence between technologies/professions. Subject matching is literal; semantic relevance elsewhere remains an LLM/human question.
3. No verification of employment history authenticity. It verifies what the **resume claims**, not what an employer or educational institution would confirm.
4. Not all HR experience is skill-specific; a total career tenure does not prove tenure in Python. Relevant profession roles are only accepted where the source explicitly ties the duration to that role.
5. Semantically complex JDs, degree/certificate/license requirements and compound constraints remain Phase 7C/7D work.
6. The baseline 21-case benchmark contains a `Python developer with 5 years of professional experience` row labelled positive for **3+ years Python**. Phase 7B intentionally treats this as *ambiguous*, rather than assuming all career years are Python years. If the live benchmark score decreases, inspect this policy difference before assuming regression. Do **not** rewrite existing labels just to achieve a higher score without independent human adjudication.
7. The parser is deliberately conservative, not a full natural-language entailment system. False positives and false negatives remain possible. Never use scores as the sole automated hiring decision.

## Exact commands (Windows PowerShell)

```powershell
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe doctor.py --live
.\scripts\run_benchmark.cmd
.\scripts\run_benchmark_pipeline.cmd
```

**New offline supervisor demo:**

```powershell
.\.venv\Scripts\python.exe main.py --no-llm --details --jd sample_data\experience_jd.txt --resumes sample_data\experience_resumes --output outputs\experience_ranking.json
```

**Expected offline demo (structural fallback mode):** 6-year Python candidate `100%`; 2-year Python candidate `50%`; 6-year Java/unclear general tenure candidates `50%` each (both have Python listed as a skill, but do not earn the required experience credit). The last two receive numeric `uncertain` in their experience checks, not `matched`.

## Supervisor architecture

```text
JD -> YAKE/Qwen JD validation -> frozen requirements -> Phase 7A typed constraints
CV -> document extractor -> source segments -> Qwen assessment / safe fallback
           -> optional reviewed aliases
           -> Phase 7B numeric experience check and provenance
           -> existing coverage scorer (unchanged formula)
           -> existing ranker / UI / JSON / CLI
```

**Acceptance:** run the 267 pre-existing tests plus new Phase 7B tests, validate manifest, compare existing Backend and HR demo ranks against Phase 7A, and separately measure local live Ollama benchmarks. Offline tests do not prove model accuracy or general hiring accuracy.
