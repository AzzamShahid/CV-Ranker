# TextileHR AI v4.9.68 — Evidence-based prompt-first implementation dossier

**Prepared:** 14 November 2026 · **Build:** `phase7g-v4-9-68-prompt-first-contract-evaluation-2026-11-14`  
**Protocol:** `segment_ids_semantic_llm` **v54**  
**Baseline:** authenticated v4.9.67/v53 ZIP SHA-256 `edecb96c8193d31dd84a01b7b2f99f05e3ec5a51ad7053c4fea03b5f85142d84`.  
**Status:** Implemented experimental system-prompt clarifications, safe input builders, paired packet verifier, offline tests, and a clean source ZIP. **No real model, blinded accuracy, native Windows or remote-production qualification was performed.**

## A. First-divergence analysis

The previous prompt inventory located 13 system definitions and 16 builder/caller sites. The original request boundary showed five important controllable risks:

1. **Primary source completeness:** retrieved `priority_segments` and real `sources` were legitimate candidate passages, but the model instructions could be interpreted as treating those selected excerpts as all available evidence. The new instruction marks the retrieved universe as a subset; it does not allow a missing passage to become a verified negative merely through prompt wording.
2. **Second adjudication anchoring:** earlier model decisions are not new original evidence. New independent wording requires explicit consideration of reversing both a missed equivalent and an unsupported positive; source and specialist validators remain authoritative.
3. **Compound schema and local system-template hazard:** the v53 `REVIEW_PROMPT` contained a literal JSON `{"source_id":...}` in a system message. That is a potential LangChain template field, not just a harmless example. v54 describes `proof_quotes` and `jd_start`/`jd_end` without literal braces, and explicitly reports all mandatory/optional expression leaves using real schema field names.
4. **JD source meaning:** employers may put obligations under inherited headings or as narrative duties. Source-first instructions now preserve headings, priorities, narrative obligations and accepted sibling rows during corrective extraction.
5. **Untrusted source wrappers:** optional JD typing and retrieval decomposition placed employer text inside ad hoc wrappers or `requirement_id:` line headers. The v54 builders pass the full original text as JSON strings with stable ID fields. Both changes have deterministic malicious-string controls.

These are **source/prompt-contract** findings. A good system prompt cannot prove semantic entailment: real-model errors and false Found still require downstream evidence validation and held-out testing.

## B. Prompt-by-prompt disposition (all 13)

| Stage/source | Disposition | Specific reason |
|---|---|---|
| `unified.UNIFIED_PROMPT` | **Experimental clarification** | packet-source subset, actor, complete duty/outcome, absence cannot be inferred from unsent material |
| `unified.FINAL_ADJUDICATION_PROMPT` | **Experimental clarification** | independent reversibility, unlike-worded equivalence versus misleading authentic source ID |
| `condition_review.REVIEW_PROMPT` | **Schema/wording fix** | escaped-safe description of real proof fields and exact-offset AND/OR leaves |
| `jd.SYSTEM_PROMPT` | **Experimental clarification** | inherited heading priority and narrative obligations |
| `jd.CORRECTION_PROMPT` | **Experimental clarification** | failed-row-only repair, no alteration of accepted siblings |
| `requirement_typing.TYPE_SYSTEM_PROMPT` | **Experimental clarification** | knowledge/work, tenure/retention, qualification/skill boundaries |
| `assessor.SYSTEM_PROMPT` | **Retained** | existing legacy source and negation guards; no isolated quality gain proved |
| `assessor.CORRECTION_PROMPT` | **Retained** | bounded affected-ID correction contract retained |
| `semantic/decomposition.SYSTEM_PROMPT` | **Retained** | source retrieval change must be tested separately; builder serialization improved |
| `semantic/transferability.SYSTEM_PROMPT` | **Retained** | preserve original evidence/candidate ownership schema |
| `semantic/transferability.COMPACT_SYSTEM_PROMPT` | **Retained** | compact capabilities wire schema and policy unchanged |
| `semantic/transferability.BATCH_SYSTEM_PROMPT` | **Retained** | multi-requirement wrapper and per-requirement evidence scope unchanged |
| `ui/final_decisions._JUDGE_PROMPT` | **Retained** | optional UI adjudicator cannot be live-UI qualified here |

The complete source-assignment hashes, source locations and change labels are in `V4968_PROMPT_AND_BUILDER_LEDGER.json`; the inventory is re-extractable using `python scripts/prompt_inventory.py`.

## C. Builder/caller coverage (all 16)

Every source-defined builder is mapped to its consuming prompt/schema in `V4968_PROMPT_AND_BUILDER_LEDGER.json`. **Eight complete fictional pre-provider packet examples** were generated for primary, independent, condition review, JD extraction, JD typing, retrieval decomposition, legacy assessment and the optional focused judge. The remaining builder sites were inspected statically and protected by their prior tests; do not misrepresent this as all 16 exercising a real provider.

The two changed builder formats (`enrich_ambiguous_types`, `create_shadow_search_plan`) are intentionally **not** part of the isolated wording-only paired packets. Their source text and ID containment were tested separately. Comparing a new builder and new system prompt together without a second arm cannot attribute model-quality changes to prompt wording alone.

## D. Measured A/B packet experiment (no model inference)

The paired runner loaded identical frozen fictional JD/CV requests from separate v53 and v54 source trees with manifest checks. There were **15 cases**: nine primary, three second-adjudication, two compound and one JD extraction. Each pair had **equal user-packet and schema hashes** and distinct changed prompt hashes where applicable. No live model calls, new model labels or provider costs were observed.

| Stage | Baseline estimated prompt tokens | Candidate estimated prompt tokens | Difference |
|---|---:|---:|---:|
| Primary | 4,100 | 4,274 | +174 |
| Independent | 3,302 | 3,452 | +150 |
| Compound | 1,176 | 1,379 | +203 |
| JD extraction | 1,351 | 1,417 | +66 |

Estimates use `cv_ranker.llm.estimate_tokens` and include a fixed allowance; they are **not actual OpenRouter/Ollama billed tokens**. Increases in context may require smaller batches. No prompt was declared more accurate or cost-effective based on the offline comparison.

**Offline Level A controls:** strict keyed response schemas, missing/foreign IDs, JSON-data boundary, original source separation, duplicated local segment IDs across candidates, untrusted role-marker strings, cloud JSON schema and output-budget wire fields, explicit opt-in before any model request, safe system-template brace parsing, run-local manifest integrity and two builder source-format checks.

## E. Supervisor and source regressions

The seven-case and fifteen-case deterministic supervisor pipelines remain **7/7 and 15/15**; they measure select engineering invariants under scripted model responses, not AI generalization. The existing v53 operation-ledger and differential-oracle repairs are retained. No new scoring weights, statuses, degrees, experience thresholds, source ranking, authorized aliases, or candidate-specific rules were introduced by this release. A previously hardcoded old test version was updated to verify current build identity while keeping the oracle values and source path validation unchanged.

The v54 scoring semantics were not promoted as a benchmark victory. Prompt edits change how an LLM may interpret a request, so the assessment protocol is deliberately bumped; old checkpoints must not be relabeled v54 without a fresh assessment. A branding or weight-only change must remain a zero-provider-call projection.

## F. Exact observed verification and open work

**Linux Python 3.13.5 full available suite:** **1,510 passed, 22 failed, 10 collection errors**. Of the 22 failures, 20 are absent Streamlit/LangChain imports and two are tests requiring a configured LLM; the 10 collection errors are missing UI dependencies. The full suite is **NOT GREEN**. The exact release-specific focused pass total and clean-extraction integrity result are recorded in the packaged `V4968_VERIFICATION_REPORT.md` after final packaging.

**Unfinished work:** complete semantic R2 JD coverage, R3 canonical decision finalizer, R4 degree/experience edge qualification, R6 crash/response exactly-once uncertainty, R7 real provider and privacy hardening, R8 independently labeled model benchmark, R9 native Windows UI, and R10 remote security/tenant controls. The live local/cloud A/B harness is a **handoff**, not an executed result; provider usage/cost/accuracy are unknown.

## G. Reproduction and rollback

- `docs/V4968_PAIRED_PACKET_RESULTS.json`: raw, source-hash-linked packet-only comparison output.
- `docs/V4968_FICTIONAL_PRE_PROVIDER_PACKETS.json`: eight fully synthetic pre-provider message/schema examples.
- `docs/V4968_PROMPT_AND_BUILDER_LEDGER.json`: 13-row prompt disposition and 16-row builder map.
- `verification/PROMPT_FIRST_WINDOWS_HANDOFF.md`: exact independent Windows and optional local/cloud commands.
- `docs/V4968_VERIFICATION_REPORT.md`: actual test and qualification ledger.

Keep the original v4.9.67 ZIP as immutable rollback. Newly verified v54 reports must not be loaded under the earlier v53 decision semantics. No secret-bearing `.env`, private applicant uploads, recovery-signing keys or operational candidate exports are packaged.
