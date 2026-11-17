# v52 runtime prompt and builder contract inventory

**Scope:** 13 runtime system-prompt assignments and 16 dynamic builder/caller functions. The prior 15-builder list omitted the existing condition-review entry point; the v51 baseline contained its prompt. This is a source-level inventory, not proof that all 13 prompts have been A/B-rewritten, that models follow them, or that every optional path is UI-reachable. Exact expression hashes are in `V4966_PROMPT_INVENTORY.json` and `V4966_PROMPT_DIFF.json`.

## System prompt assignments

| Prompt source | Symbol | v52 line | v51→v52 | Contract and trust boundary |
|---|---|---:|---|---|
| `cv_ranker/jd.py` | `SYSTEM_PROMPT` | 23 | unchanged | Input employer JD text is untrusted; output must use source-grounded criteria and preserve frozen review, not score candidates |
| `cv_ranker/jd.py` | `CORRECTION_PROMPT` | 74 | unchanged | Input employer JD text is untrusted; output must use source-grounded criteria and preserve frozen review, not score candidates |
| `cv_ranker/requirement_typing.py` | `TYPE_SYSTEM_PROMPT` | 291 | unchanged | Output suggested type only, bounded to current R IDs; no candidate verdict |
| `cv_ranker/unified.py` | `UNIFIED_PROMPT` | 292 | unchanged | Candidate original S IDs plus frozen R IDs; structured proposals subject to source and specialist validators |
| `cv_ranker/unified.py` | `FINAL_ADJUDICATION_PROMPT` | 108 | unchanged | Candidate original S IDs plus frozen R IDs; structured proposals subject to source and specialist validators |
| `cv_ranker/assessor.py` | `SYSTEM_PROMPT` | 31 | unchanged | Source-cited candidate decisions; no unvalidated citation can grant direct credit |
| `cv_ranker/assessor.py` | `CORRECTION_PROMPT` | 72 | unchanged | Source-cited candidate decisions; no unvalidated citation can grant direct credit |
| `cv_ranker/semantic/decomposition.py` | `SYSTEM_PROMPT` | 19 | unchanged | JD retrieval hints only; similarity is not qualification proof |
| `cv_ranker/semantic/transferability.py` | `SYSTEM_PROMPT` | 386 | unchanged | Adjacent-capability proposals only; unverified relevance cannot grant direct points |
| `cv_ranker/semantic/transferability.py` | `COMPACT_SYSTEM_PROMPT` | 140 | unchanged | Adjacent-capability proposals only; unverified relevance cannot grant direct points |
| `cv_ranker/semantic/transferability.py` | `BATCH_SYSTEM_PROMPT` | 158 | unchanged | Adjacent-capability proposals only; unverified relevance cannot grant direct points |
| `cv_ranker/ui/final_decisions.py` | `_JUDGE_PROMPT` | 42 | unchanged | Optional focused explanation/review is advisory and must not override official source-backed finalization |
| `cv_ranker/condition_review.py` | `REVIEW_PROMPT` | 58 | changed | Independent source-bound per-facet review. Exact approved offsets, mandatory/OR structure and source proof quotes are machine-validated; still not human truth verification |

## Dynamic builders/callers

| Source | Callable | v52 line | Required validation |
|---|---|---:|---|
| `cv_ranker/jd.py` | `_user_prompt` | 399 | Frozen R IDs and candidate S IDs must retain original scope; JSON-safe source data, bounded provider request, explicit output schema and no result policy from source text. |
| `cv_ranker/jd.py` | `validate_jd_requirements` | 423 | Frozen R IDs and candidate S IDs must retain original scope; JSON-safe source data, bounded provider request, explicit output schema and no result policy from source text. |
| `cv_ranker/requirement_typing.py` | `enrich_ambiguous_types` | 301 | Frozen R IDs and candidate S IDs must retain original scope; JSON-safe source data, bounded provider request, explicit output schema and no result policy from source text. |
| `cv_ranker/assessor.py` | `_build_user_prompt` | 114 | Frozen R IDs and candidate S IDs must retain original scope; JSON-safe source data, bounded provider request, explicit output schema and no result policy from source text. |
| `cv_ranker/assessor.py` | `_correct_invalid_rows` | 974 | Frozen R IDs and candidate S IDs must retain original scope; JSON-safe source data, bounded provider request, explicit output schema and no result policy from source text. |
| `cv_ranker/assessor.py` | `_focused_abbreviation_recheck` | 1103 | Frozen R IDs and candidate S IDs must retain original scope; JSON-safe source data, bounded provider request, explicit output schema and no result policy from source text. |
| `cv_ranker/unified.py` | `_payload` | 663 | Frozen R IDs and candidate S IDs must retain original scope; JSON-safe source data, bounded provider request, explicit output schema and no result policy from source text. |
| `cv_ranker/unified.py` | `_correction_payload` | 853 | Frozen R IDs and candidate S IDs must retain original scope; JSON-safe source data, bounded provider request, explicit output schema and no result policy from source text. |
| `cv_ranker/unified.py` | `plan_evidence_batches` | 709 | Frozen R IDs and candidate S IDs must retain original scope; JSON-safe source data, bounded provider request, explicit output schema and no result policy from source text. |
| `cv_ranker/unified.py` | `_independently_adjudicate` | 1417 | Frozen R IDs and candidate S IDs must retain original scope; JSON-safe source data, bounded provider request, explicit output schema and no result policy from source text. |
| `cv_ranker/semantic/decomposition.py` | `create_shadow_search_plan` | 146 | Frozen R IDs and candidate S IDs must retain original scope; JSON-safe source data, bounded provider request, explicit output schema and no result policy from source text. |
| `cv_ranker/semantic/transferability.py` | `assess_transferability_shadow` | 636 | Frozen R IDs and candidate S IDs must retain original scope; JSON-safe source data, bounded provider request, explicit output schema and no result policy from source text. |
| `cv_ranker/semantic/transferability.py` | `_assess_single_compact` | 531 | Frozen R IDs and candidate S IDs must retain original scope; JSON-safe source data, bounded provider request, explicit output schema and no result policy from source text. |
| `cv_ranker/semantic/transferability.py` | `_assess_compact_jobs` | 556 | Frozen R IDs and candidate S IDs must retain original scope; JSON-safe source data, bounded provider request, explicit output schema and no result policy from source text. |
| `cv_ranker/ui/final_decisions.py` | `_judge_requirement` | 277 | Frozen R IDs and candidate S IDs must retain original scope; JSON-safe source data, bounded provider request, explicit output schema and no result policy from source text. |
| `cv_ranker/condition_review.py` | `review_compound_uncertainty` | 139 | Frozen R IDs and candidate S IDs must retain original scope; JSON-safe source data, bounded provider request, explicit output schema and no result policy from source text. |

## Model and quality acceptance

The v52 code adds a mandatory proof quote requirement **for explicit reviewed nested JD expressions**. It does not prove the quoted text semantically entails the criterion. The older twelve prompts were not rewritten in this release; only the thirteenth `REVIEW_PROMPT` and its builder changed. Controlled 7+15 model-stub scenarios and the v52 source tests are not actual provider A/B performance. Live/model-scoped token budgets, schema success, false-Found rates and human-labelled semantic accuracy remain **NOT QUALIFIED**. Do not invent usage statistics.
