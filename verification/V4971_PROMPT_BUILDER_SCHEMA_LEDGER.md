# Current prompt / response / caller inventory — v4.9.71 RC1

The source inventory identifies **13 top-level prompt definitions**. There are additional conditional user-message builders and prompt-fitting branches; a count of exactly N callers should not be inferred from the 13 definitions. Each runtime caller and schema must still be exercised in the native configured-provider environment.

| File and symbol | Function / caller | Contract and effect | Offline status |
|---|---|---|---|
| `unified.py` `UNIFIED_PROMPT` | `_invoke_required_id_group`, `UnifiedEvidenceEngine.assess`; batch/context packet | `found/transferable/not_found`, `relation` and source IDs; current finalizer checks source | Tested in supervisor and schema fixtures |
| `unified.py` `FINAL_ADJUDICATION_PROMPT` | `_independently_adjudicate`, bounded last review | Same three verdicts, strict proof_excerpt/source identity | Tested including fake quotes and wrong IDs |
| `condition_review.py` `REVIEW_PROMPT` | `_review_compound_batch` and bounded scheduler | Three final choices; facet-level `uncertain` allowed for intermediate facts, never as final | Seven DA regressions, 1/6/7/12/13 batches, 429, restore |
| `assessor.py` `SYSTEM_PROMPT` | `assess_resume` legacy | `matched/transferable/not_matched`; mapping to canonical result; operational failures null | Tested legacy compound route |
| `assessor.py` `CORRECTION_PROMPT` | `assess_resume` correction / retry builder | Same 3 model choices, no candidate fallback from errors | Tested deterministic corrections |
| `ui/final_decisions.py` `_JUDGE_PROMPT` | optional focused UI judge | `matched/transferable/not_evidenced`; canonical projection before score | Offline source checks; Streamlit rendering blocked |
| `semantic/transferability.py` `SYSTEM_PROMPT` | full shadow semantics | Provisional relations; not a current final candidate-verdict authority | Existing unit tests; live quality blocked |
| `semantic/transferability.py` `COMPACT_SYSTEM_PROMPT` | `assess_compact_*` invocations | Shadow relation; no independent final score | Existing unit tests; live quality blocked |
| `semantic/transferability.py` `BATCH_SYSTEM_PROMPT` | batch shadow invocations | Same provisional semantics and candidate scoped sources | Existing unit tests; live quality blocked |
| `jd.py` `SYSTEM_PROMPT` | JD extraction/validation | JD criteria only; no CV verdict | Existing JD suites, no live accuracy |
| `jd.py` `CORRECTION_PROMPT` | JD extraction correction | JD syntax/denominator repair | Existing JD suites, no live accuracy |
| `requirement_typing.py` `TYPE_SYSTEM_PROMPT` | JD type classifier | Intermediate type/constraint, no final CV verdict | Existing type tests |
| `semantic/decomposition.py` `SYSTEM_PROMPT` | semantic query decomposition | Retrieval only; no final CV verdict | Existing retrieval tests |

**Cross-cutting builders/validators:** frozen JD `requirements`, original candidate `sources`, source ID validation, rendered prompt-length safeguards, compact/batch schema validation, `pipeline.reconcile_final_assessments`, specialist experience/qualification checks, persisted operation fingerprint and report projection. Source text is untrusted data. The LLM cannot set `processing_state`, grant itself score/rank or skip provenance validation.

**Important scope:** This is a static code + deterministic offline regression inventory, **not** proof that every provider received each prompt in a live call or that model accuracy improved.
