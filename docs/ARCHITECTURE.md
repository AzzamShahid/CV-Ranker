# System architecture | CV Ranker

## Objective

Rank multiple CVs against a single JD, with a transparent and deterministic scoring basis and visible, source-grounded supporting evidence. This prototype is intended for a supervisor demo and further validation, not automated hiring decisions.

## End-to-end workflow

```text
               JOB DESCRIPTION                    RESUMES
                      |                              |
          Extract text (documents.py)       Extract text (documents.py)
                      |                              |
                YAKE hints                  Segment resume (segments.py)
                      |                              |
       Qwen JD interpretation (jd.py)                  |
                      |                              |
     Python-source-grounded frozen requirements -------+
                      |                              |
                      +--------------> Qwen CV assessment (assessor.py)
                                              |
                              Pydantic output / source validation
                                              |
                               deterministic scores (scoring.py)
                                              |
                               sorted ranked candidates (pipeline.py)
                                              |
                               Streamlit / CLI with evidence
```

## Folder responsibilities

| Source | Responsibility |
|---|---|
| `cv_ranker/documents.py` | Read PDF/DOCX/TXT/MD; enforce minimum readable text |
| `cv_ranker/yake_extractor.py` | Unsupervised JD phrase candidates only |
| `cv_ranker/jd.py` | Qwen JD parsing, priority identification, source-grounded frozen list |
| `cv_ranker/segments.py` | Deterministic original CV source sections and segment IDs |
| `cv_ranker/assessor.py` | Qwen CV decisions, cited evidence, generic context/safety checks |
| `cv_ranker/llm.py` | Ollama/LangChain structured model adapter |
| `cv_ranker/schemas.py` | Pydantic schemas and typed pipeline objects |
| `cv_ranker/fallback.py` | Visible deterministic conservative recovery/fallback |
| `cv_ranker/scoring.py` | Score computation and candidate rank keys |
| `cv_ranker/pipeline.py` | Orchestrates the above for one JD and many resumes |
| `cv_ranker/ui_support.py`, `cv_ranker/report.py` | Output and safe evidence presentation |
| `cv_ranker/runtime_check.py` | SHA-256 checks to prevent mixing code releases |
| `app.py`, `main.py` | Streamlit UI and CLI applications |

## Frozen requirements vs variable candidate answers

A JD is processed once and produces stable requirements `R001`, `R002`, etc. The same requirement denominator is reused for every resume in that ranking run. Qwen does not assign scores or decide sorting.

A CV is segmented into IDs such as `S001`. Qwen reports `requirement_id`, `status`, `evidence_ids`, and optional `matched_term`. Python verifies the cited source exists; one exact word can be identified as supporting evidence, but the UI displays the original complete line or segment. An evidence citation is not a guarantee of semantic correctness: Qwen may still make a wrong inference.

## Decision statuses and score

`matched` counts toward coverage. `uncertain` and `not_matched` get zero credit. Primary rank score for JDs with required items: `100 * matched_required / total_required`; preferred coverage is separate. Equal primary scores are ties subject to the documented deterministic sort key.

## Scope exclusions

- No embedding-based similarity or vector retrieval
- No hardcoded skill synonyms or cross-skill/transferable-skill bonus
- No active second-model verifier
- No LLM-controlled score or applicant rank
- No external/cloud AI or database requirement

## Critical accuracy caveat

The source validator is intentionally not a semantic verifier. A valid cited line can still be **irrelevant** (a known benchmark issue). This is the main limitation requiring further model/calibration research. The software must not be represented as independently verifying every semantic conclusion.

## Phase 7A — Typed JD metadata (additive)

After the final JD denominator has been frozen, `cv_ranker/requirement_typing.py` enriches each requirement with source-grounded `RequirementConstraint` metadata. The scorer and resume assessor continue to operate on the same frozen requirement IDs, names, and priorities; typed attributes are descriptive and not yet enforced. Ambiguous cases are flagged for HR review, and optional Qwen category suggestions remain unverified and separate from scoring. See [Phase 7A](PHASE_7A_TYPED_REQUIREMENTS.md).


## Phase 7C addendum (2026-10-12)

The candidate pipeline is now `Qwen/fallback -> reviewed aliases -> Phase 7B numeric experience -> Phase 7C credential claim check -> existing deterministic scoring`. `qualification_check` records source text and segment IDs for typed education, certification and license requirements. A `satisfied` claim is **not third-party credential authentication**, and uncertain/invalid cases never receive automatic credential credit. Phase 7D will handle compound qualification requirements and eligibility policy separately.


## Phase 7D — Compound source checks and optional HR gates (2026-10-13)

The candidate pipeline is `Qwen/fallback -> reviewed short-name aliases -> numeric experience claims -> qualification claims -> JD-explicit short AND/OR literal options -> unchanged deterministic scoring -> optional employer-selected gate report`. See [Phase 7D](PHASE_7D_COMPOUND_ELIGIBILITY.md). AND/OR checks can change only the status of a frozen compound requirement, never expand the denominator. Complex Boolean syntax and mixed qualification/experience alternatives receive review status rather than invented precedence. HR gates do not influence rank, are tied to SHA256 of JD text, and are accepted as input declarations (not authenticated). Their screening status is **not** actual hiring/license eligibility.
