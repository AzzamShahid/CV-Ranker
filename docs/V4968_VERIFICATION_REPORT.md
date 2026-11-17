# v4.9.68 verification and remaining qualification gates

**Input:** exact v4.9.67/v53 archive SHA-256 `edecb96c8193d31dd84a01b7b2f99f05e3ec5a51ad7053c4fea03b5f85142d84`.  
**Candidate:** v4.9.68/v54.  
**Host:** Linux, Python 3.13.5; Streamlit and LangChain dependencies unavailable; no authorized external cloud inference or blinded independent human label set.

## Levels and what they mean

| Level/gate | Evidence in this release | Disposition |
|---|---|---|
| **Level A — strict prompt/schema source contract** | 13 prompt definitions, 16 builder/caller references inventoried. Seven targeted wording corrections within six definitions; two JSON builder safety repairs. Scripted original source/foreign-ID/negative tests. | **VERIFIED_OFFLINE for listed tests** |
| **Level A — paired packet experiment** | Separate v53/v54 processes, exact same user-packet and schema hashes for 15 fictional cases; packet mode makes no provider calls. | **PASS — packet parity only** |
| **Level A — actual provider wire shape** | Intercepted OpenRouter `_post_chat` validates two message roles, temperature, schema and explicit cloud output budget without networking. | **VERIFIED_OFFLINE for captured request** |
| **Level B — local Ollama model A/B** | Runnable harness provided with explicit `--authorize-local`, model name/config inherited from each source's settings. | **NOT RUN / no model configured** |
| **Level B — OpenRouter cloud model A/B** | Runnable opt-in harness, fictional data only, source/model request ceiling required. | **NOT RUN / no user authorization or credits used** |
| **Level C — independently labeled whole-document accuracy** | Development counterfactuals exist, but no blinded, independently adjudicated holdout supplied. | **NOT QUALIFIED** |
| **Windows/Streamlit runtime** | Commands included; no native Windows computer available in this execution environment. | **NOT QUALIFIED** |
| **R2/R3 canonical meaning and finalizer** | Prompt contract improvements do not consolidate every old decision path. | **PARTIAL / separate workstream** |
| **R6 exactly-once remote billing** | v53 operation-claim protection retained; external crash/receipt boundary not solvable without provider idempotency/reconciliation. | **NOT QUALIFIED** |
| **R10 remote production privacy/security** | No remote deployment, tenant isolation, IdP or user-data processing conducted. | **BLOCKED / separate authorization** |

## Reproducible measurements

- `scripts/prompt_first_pair.py --mode packet` produced 15 packet/schema-parity rows; zero baseline and candidate model calls. This is **not** 15/15 live accuracy.
- The original v53 seven-case and fifteen-case controlled supervisor suites must continue to pass. They are deterministic probes, not held-out model labels.
- Full available-suite totals (pass/fail/collection error) must be recorded after the final manifest and package are regenerated. A nonzero broader-suite result is **not a green release**.
- A simplified estimator in `cv_ranker.llm.estimate_tokens` produces **estimated**, not provider-reported, token counts. Any savings or increases in token counts are *not* monetary cost claims.
- There is no measured first/second model error improvement, refusal rate, timing/cost quality gain, or developer blind holdout preference. **Real-model winner: insufficient evidence**.

## Development benchmark holdout policy

Fictional development cases in `evaluation/prompt_first/development_cases.json` must not be used as independent hidden gold. Collect separate fictional or explicitly authorized source documents; have two people label JD clauses, evidence spans and status before seeing model outputs; adjudicate disagreements, freeze thresholds and provider spend, then execute A/B from the same source packet and a separate full-pipeline run. Split by document, candidate and template/wording family. Report wrong→right and right→wrong as well as absence/unverified coverage, source-citation precision, requests, provider tokens, latency and unknown cost.

## Privacy and repeatability

`docs/V4968_FICTIONAL_PRE_PROVIDER_PACKETS.json` contains **only fictional demonstration text**, raw synthetic messages and response schemas. Operational logs in the harness record hashes, IDs and typed errors by default; there is no authenticated candidate text or provider bearer token. A human must explicitly authorize cloud use; the opt-in flag by itself does not constitute an approval to send real CVs. Sensitive `.env`, keys, recovery files, caches and applicant reports are excluded from the source ZIP.

## Actual final candidate-tree execution (14 November 2026)

- `python -m pytest -q tests/test_runtime_identity.py tests/test_v4968_prompt_first_contracts.py tests/test_v4967* tests/test_v4966* tests/test_v4965_supervisor_end_to_end.py tests/test_v4965_independent_compound_review.py tests/test_v484_domain_neutral_prompts.py tests/test_v483_live_calibration.py tests/test_v498_semantic_prompt_contracts.py tests/test_phase7a_typed_requirements.py tests/test_phase7g_dynamic_decomposition.py` → **133 passed**.
- `python -m pytest -q --continue-on-collection-errors` → **1,510 passed, 22 failed, 10 collection errors**. This is **NOT** a full green suite. Twenty failed tests are missing Streamlit/LangChain imports, and two older tests require the configured LLM. Collection errors likewise concern unavailable UI dependencies.
- `python -m evaluation.evaluate_supervisor --output ...` → **7/7 controlled scripted cases**; `python -m evaluation.evaluate_supervisor --cross-domain --output ...` → **15/15 controlled scripted cases**.
- The independent packet comparison was **15/15 exact same user-payload/schema hashes**, **zero actual LLM calls**, with separate baseline/candidate source imports. System-prompt changes were observed through different system-message hashes.
- `CVR_STRICT_SOURCE_HASHES=1 python -m cv_ranker.runtime_check` → verified v4.9.68/v54 candidate source identity.
- No real Ollama output, OpenRouter billing/usage, independent human adjudication or native Windows Streamlit session was collected. Model-quality and end-to-end UI gates remain **OPEN**.

The final ZIP extraction and clean-apply source patch are checked after this document is finalized and are recorded in the standalone release integrity receipt.
