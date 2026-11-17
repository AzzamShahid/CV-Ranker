# TextileHR v4.9.72 P1 — prompt / builder integration ledger

## Baseline and revision

- Baseline: `v4.9.71 RC1`, SHA-256 `251b2db3b794cff27d24ec29f2d3baa3be3e11358b107b0220c347ab34fa8631`.
- Candidate: `v4.9.72-p1-rc1`, protocol 58, prompt revision `P1-2026-11-16`.
- Exact approved P1 source: `docs/P1_APPROVED_PROMPTS_AND_FRAGMENTS.json`, preserved verbatim.

## The 13 application prompt assignments

| Approved key | Runtime symbol file | Status | Verification |
|---|---|---|---|
| `jd.SYSTEM_PROMPT` | `cv_ranker/jd.py` | Exact P1 content installed | `test_v4972_p1_prompt_integration.py` source-equality check |
| `jd.CORRECTION_PROMPT` | `cv_ranker/jd.py` | Exact P1 content installed | `test_v4972_p1_prompt_integration.py` source-equality check |
| `requirement_typing.TYPE_SYSTEM_PROMPT` | `cv_ranker/requirement_typing.py` | Exact P1 content installed | `test_v4972_p1_prompt_integration.py` source-equality check |
| `unified.UNIFIED_PROMPT` | `cv_ranker/unified.py` | Exact P1 content installed | `test_v4972_p1_prompt_integration.py` source-equality check |
| `unified.FINAL_ADJUDICATION_PROMPT` | `cv_ranker/unified.py` | Exact P1 content installed | `test_v4972_p1_prompt_integration.py` source-equality check |
| `assessor.SYSTEM_PROMPT` | `cv_ranker/assessor.py` | Exact P1 content installed | `test_v4972_p1_prompt_integration.py` source-equality check |
| `assessor.CORRECTION_PROMPT` | `cv_ranker/assessor.py` | Exact P1 content installed | `test_v4972_p1_prompt_integration.py` source-equality check |
| `condition_review.REVIEW_PROMPT` | `cv_ranker/condition_review.py` | Exact P1 content installed | `test_v4972_p1_prompt_integration.py` source-equality check |
| `semantic.decomposition.SYSTEM_PROMPT` | `cv_ranker/semantic/decomposition.py` | Exact P1 content installed | `test_v4972_p1_prompt_integration.py` source-equality check |
| `semantic.transferability.SYSTEM_PROMPT` | `cv_ranker/semantic/transferability.py` | Exact P1 content installed | `test_v4972_p1_prompt_integration.py` source-equality check |
| `semantic.transferability.COMPACT_SYSTEM_PROMPT` | `cv_ranker/semantic/transferability.py` | Exact P1 content installed | `test_v4972_p1_prompt_integration.py` source-equality check |
| `semantic.transferability.BATCH_SYSTEM_PROMPT` | `cv_ranker/semantic/transferability.py` | Exact P1 content installed | `test_v4972_p1_prompt_integration.py` source-equality check |
| `ui.final_decisions._JUDGE_PROMPT` | `cv_ranker/ui/final_decisions.py` | Exact P1 content installed | `test_v4972_p1_prompt_integration.py` source-equality check |

## The 19 supporting instruction fragments

| Fragment | Caller | Status | Verification |
|---|---|---|---|
| JD user-message prefix | `cv_ranker/jd.py` | Exact P1 constant used by caller | Source AST reference test; selected real dispatch tests |
| JD targeted correction objective | `cv_ranker/jd.py` | Exact P1 constant used by caller | Source AST reference test; selected real dispatch tests |
| JD full-replacement correction objective | `cv_ranker/jd.py` | Exact P1 constant used by caller | Source AST reference test; selected real dispatch tests |
| Typing user-message prefix | `cv_ranker/requirement_typing.py` | Exact P1 constant used by caller | Source AST reference test; selected real dispatch tests |
| Legacy initial user-message instruction | `cv_ranker/assessor.py` | Exact P1 constant used by caller | Source AST reference test; selected real dispatch tests |
| Legacy invalid-row correction | `cv_ranker/assessor.py` | Exact P1 constant used by caller | Source AST reference test; selected real dispatch tests |
| Legacy abbreviation recheck | `cv_ranker/assessor.py` | Exact P1 constant used by caller | Source AST reference test; selected real dispatch tests |
| Legacy unmatched second look | `cv_ranker/assessor.py` | Exact P1 constant used by caller | Source AST reference test; selected real dispatch tests |
| Unified correction payload instruction | `cv_ranker/unified.py` | Exact P1 constant used by caller | Source AST reference test; selected real dispatch tests |
| Independent review payload instruction | `cv_ranker/unified.py` | Exact P1 constant used by caller | Source AST reference test; selected real dispatch tests |
| Compound malformed-response correction | `cv_ranker/condition_review.py` | Exact P1 constant used by caller | Source AST reference test; selected real dispatch tests |
| Compound evidence/condition correction | `cv_ranker/condition_review.py` | Exact P1 constant used by caller | Source AST reference test; selected real dispatch tests |
| Decomposition user-message prefix | `cv_ranker/semantic/decomposition.py` | Exact P1 constant used by caller | Source AST reference test; selected real dispatch tests |
| Shadow second-look instruction | `cv_ranker/semantic/transferability.py` | Exact P1 constant used by caller | Source AST reference test; selected real dispatch tests |
| UI compact suffix | `cv_ranker/ui/final_decisions.py` | Exact P1 constant used by caller | Source AST reference test; selected real dispatch tests |
| Ollama structural-correction suffix | `cv_ranker/llm.py` | Exact P1 constant used by caller | Source AST reference test; selected real dispatch tests |
| OpenRouter structural-correction suffix | `cv_ranker/llm.py` | Exact P1 constant used by caller | Source AST reference test; selected real dispatch tests |
| Doctor system prompt | `doctor.py` | Exact P1 constant used by caller | Source AST reference test; selected real dispatch tests |
| Doctor user prompt | `doctor.py` | Exact P1 constant used by caller | Source AST reference test; selected real dispatch tests |

## Wire-contract preservation and scope

- Unified primary and independent review use separate ID-keyed response schemas; no `assessments` wrapper.
- Legacy uses its three-choice `assessments` list and existing negative citation convention.
- Compound has `facets` and exact JD/source span validation; contextual negative citations do not imply satisfaction.
- Shadow full, compact-single and compact-batch use distinct schemas. Shadow `uncertain` is provisional and does not add a final verdict.
- Focused judge full asks `supporting_sources`, compact asks `source_ids`; the compact suffix is caller-specific.
- Local P1 JSON examples are delivered as a literal system message rather than LangChain-format placeholders.
- Structural correction suffixes are only added for malformed outputs, not HTTP 429 or transport failure; structural diagnostics expose only safe error paths/categories.
- JD targeted correction preserves accepted rows, whereas full replacement is reserved for the initial empty-extraction repair path.
- `evaluation/trace.py` recognizes the revised P1 stage markers without changing adjudicated fixture verdicts.

## Coverage limitations

- Exact P1 source, static caller reachability and selected real request boundaries are tested offline. Not every conditional provider branch is captured end-to-end.
- Source identity and existing canonical three-verdict/recovery rules were not relaxed to accommodate prompt text.
- No actual Ollama/OpenRouter model generation or native Windows runtime was evaluated here.
