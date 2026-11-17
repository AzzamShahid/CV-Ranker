# CV Ranker v4.9.60 — universal named-alternative source validation and citation recovery

**Date:** 12 November 2026. **Build:** `phase7g-v4-9-60-named-or-citation-repair-2026-11-12`. **Assessment protocol:** 46 (previous v45/v44 results remain historical, not newly reassessed).

## Incident driving this repair

Three user assessments were technical Unverified for the same employer requirement, **“Use of ERP or manufacturing execution systems (MES) for weaving production reporting.”** The validator reported that the cited source did not establish `MES`, including when equivalent direct citations of ERP were possible. The source code actually demanded **both ERP and MES** because each uppercase term was treated as a separately mandatory condition. This was reproduced independently with `Used ERP...`, `Used MES...`, and spelled-out `manufacturing execution systems...` citations. The user's exact S011 source and CV 6–8 originals were not supplied, so the individual candidate decisions are **not claimed verified**.

## Confirmed fixes (universal, not keyed to R015 or specific technology)

1. **Named-condition groups:** `cv_ranker/assessor.py` interprets clear OR/and-or between named entities as **one acceptable alternative group**; an explicit AND remains distinct mandatory named conditions. Parenthesized alternatives and longer descriptive requirements are supported; ambiguous mixed unparenthesized AND/OR is not guessed into a punitive source check. Any prior unconditional mandate to cite *every* acronym in an OR was wrong.
2. **Positive source scope:** `cv_ranker/text_utils.py` recognizes `without A or B` as coordinated negation; merely naming an alternative in a denial cannot establish it. Original source IDs, non-candidate-text exclusions and actual affirmative claim checks remain enforced.
3. **Reporting duty versus tool mention:** a skills inventory naming a tool alone does not prove its application to a performed responsibility. A narrative performed-work claim under a misparsed heading remains eligible for semantic review; the original model still decides actual relevance.
4. **Named-condition citation recovery:** `cv_ranker/unified.py` treats a *missing named alternative in a cited passage* as a source-repair class. It searches the original CV ledger for positive mentions, prioritizes completed-use passages over inventories and places a newly targeted alternative first even when that source was available among earlier, unselected retrieval leads. A correction citing an irrelevant old passage should not be repeated unchanged. This rearrangement is a retrieval opportunity, not scoring credit.
5. **Independent final verification:** prioritized named alternative leads are also exposed to the existing one-shot final source-grounded adjudicator. If proof is lacking, the model can produce a verified Not Found or unscored Transferable with genuine original citations. An irreparably malformed response remains Unverified, without being disguised as a candidate deficiency.

## Test strategy and observed evidence

- Added `tests/test_v4960_named_alternatives_and_recovery.py`: compact OR and explicit AND, acronyms and spelled-out alternatives, negation and unrelated tools, bare skills inventory, modified-source recovery, controlled unified-pipeline runs, and full compound-check/score agreement.
- Baseline v45: `Used ERP` and `Used MES` each failed with *the other alternative missing*. New tests fail against the old source and pass after this patch.
- The controlled fake-model whole-pipeline scenarios are **not a live model benchmark**. They demonstrate that the pipeline accepts a correctly cited ERP/MES response, repairs a wrong first citation with another available original passage, returns justified Not Found or Transferable without duplicate semantic retries, and preserves score policies.
- Validation continues to reject invented/foreign source IDs, unsupported jobs, missing mandatory AND, unrelated work and explicit negation. All model results remain subject to evidence provenance and specialist validation.

## Known limitations

- Actual CV 6 R015, CV 7 R015 and CV 8 R015 **must** be reassessed with protocol 46. Their personal S011 and other original source texts were not available for individual source comparison; S015 displayed as a *retrieval lead* is **not accepted proof**.
- An original CV may mention ERP in its skills inventory yet not demonstrate its **use for weaving production reporting**. The model must distinguish that from source-supported Transferable or Not Found; no automatic Found grant is provided.
- Live OpenRouter/Ollama model output and complete Windows/Streamlit test suite were unavailable in this container. The offline full-suite result, exclusions and exact commands must be stated separately from those future checks.
- Semantic JD approval, mixed Boolean intent, advanced evidence retrieval, full no-progress recovery diagnostics and held-out cross-department accuracy work remain open in the master plan.
- The source release is for private local supervised review, not unapproved remote deployment or unattended hiring decisions.

## Windows installation / regression

Extract into a **new directory**, use your own private `.env`, and install pinned project requirements. Run `run_runtime_check.cmd`, `run_tests.cmd`, `run_ui.cmd`; use a **fresh** JD/CV assessment under protocol 46 (not a resumed v45 report). Keep v45 as a rollback and review accepted/cited/rejected S IDs after re-running the problematic case.

## Verified release-level checks

After edits and updated build identity, the offline suite completed **1,324 passed, 22 deselected** with 10 collection modules intentionally excluded because this environment lacked Streamlit. The 22 individually deselected tests required Streamlit/LangChain/Ollama or UI integration, so they must be rerun with the full Windows dependencies. No live model accuracy or actual CV 6–8 assessment has been claimed. The strict source manifest and packaged file integrity were checked after release packaging.
