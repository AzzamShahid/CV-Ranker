# TextileHR AI three-verdict migration — v4.9.70 release candidate 1

**Date:** 2026-11-15

**Build:** `phase7g-v4-9-70-three-verdict-rc1-2026-11-15`

**Assessment protocol:** `segment_ids_semantic_llm`, version **56**
**Qualification:** **NOT feature-complete; do not replace the production installation.**

## Source identity and migration limit

- Requested canonical baseline: `TextileHR_AI_CV_Ranker_v4.9.68_Windows_Test_Compatibility_2026-11-14.zip`, required SHA-256 `813f1deb8456d78ea16d52ec1398bdd2f1c9981654a848249f686c560bd24587`. **Not supplied in the container.** No claim is made that Windows compatibility repairs in that archive were merged.
- Available predecessor: `TextileHR_AI_CV_Ranker_v4.9.69_Three_Verdict_PREVIEW_2026-11-15.zip`, SHA-256 `3f14ec14511b5247e661ad2b2c1d9869ae11ef9ae911fb69a6b96edd2d9279f2`.
- Known preview ancestor: `TextileHR_AI_CV_Ranker_v4.9.68_Prompt_First_Repair_2026-11-14(1).zip`, SHA-256 `e7b342bc20ec2045ff7c15912059cd2e632cc698c3eb685601858c9cd96388a5`.
- The accompanying patch is against **the available v4.9.69 preview**, not the missing canonical Windows archive. These are different baselines.

## Implemented in this candidate

1. Approved compound JD interpretation is pending work until source-grounded review executes, rather than a fabricated `semantic_review_incomplete` operation failure.
2. Compound semantic provider replies enforce `found/transferable/not_found` through a constrained response schema, support one bounded targeted response correction, and preserve technical errors as application-owned `DecisionRecord` failures without a candidate verdict.
3. A source-bound supervisor test enters through `CVRanker.run` and verifies **Found**, **Transferable**, **Not Found**, full JD denominator, exact-source evidence, primary/weighted points, JSON round-trip, candidate Why and ZIP export.
4. Real 429 errors produce `paused/provider_rate_limit` with null verdict and no official rank. Invalid fourth-choice responses are rejected and corrected on a bounded operation.
5. Legacy LLM calls now use `LLMLiveThreeVerdictResponse` (`matched/transferable/not_matched`); affirmative related completed work can be marked `Transferable` without receiving direct points.
6. Initial invalid professional-depth objection triggers semantic review, and a repeated structurally invalid correction is recorded as an actual `response_schema_invalid` failure, not as an invented negative.
7. `reconcile_final_assessments` is executed for unified, legacy and fallback supervisor modes. Current UI, weighted scoring, recovery, ranking reasoning and ZIP outputs prioritize the typed decision record.
8. Missing candidate assessment rows are processing-incomplete, not newly generated `Unverified` or `Not Found`; current unfinished rows have no official score/rank. Historical saved Unverified strings remain intact for audit.
9. A compatible saved report is reused after a new ranker instance starts, with zero model redispatch. Weight-only projections issue zero model calls.
10. Dashboard status chips, icons, filters and saved-session reconstruction recognize `Assessment incomplete`; current modes use the canonical display projection rather than the optional historical focused judge.

## Verification performed in this environment

| Gate | Observed state |
|---|---|
| G0 — correct Windows-compatible baseline | **BLOCKED**: exact required archive absent. Available predecessor identities verified. |
| G1 — real supervisor vertical slice | **PARTIAL PASS**: deterministic three-choice source review, provider 429, bounded schema correction, export, resume, reweight, and missing-row UI tests. Native UI and actual provider not run. |
| G2 — every active assessment route | **INCOMPLETE**: older specialist/legacy/semantic-shadow edge cases, provider failure handling and migration review remain. |
| G3 — UI, score, exports and history | **PARTIAL**: canonical score/export JSON tested and source-level UI corrected. Actual Streamlit interaction, protected Windows restart, all CSV/UI permutations and historical migration not fully qualified. |
| G4 — entire protected suite, live quality | **FAIL/OPEN**: broad suite still contains failures; Python environment lacks Streamlit/LangChain/Yake for UI and some integration tests. No paired live-model benchmark. |
| G5 — patch, manifest and package | Independent clean-patch/re-extraction result is recorded in the accompanying final handoff (not claimed by this source-only document). |

The prior preview ran offline with **1,488 passed / 55 failed** using the same ignored collection modules. A development checkpoint of this successor ran **1,499 passed / 52 failed**. **Neither result is a fully passing suite.** A successful offline model stub is not evidence of production semantic accuracy. Installation of missing dependencies was attempted but the package index could not be reached from this environment.

## Remaining code and release work

- Obtain and merge the **exact Windows Test Compatibility** archive, then rerun strict manifest, source identity and all Windows UI/export tests from the integrated tree.
- Reconcile remaining old-contract tests and reachable code paths without weakening original citation checks, competency evidence, condition-tree semantics, degree level or years-of-experience arithmetic.
- Prove all supported provider and fallback edge cases (authentication, unavailable provider, 429, invalid response, interrupted dispatch, partial recovery, actual resume state) via production entry points.
- Finish deterministic qualification of numeric experience, same-subject higher degree, negative and transferable field constraints, semantic-shadow full/compact/batch variants, old report version migration, focused judge redraw, and cross-output completeness.
- Independently reviewed, blinded live-provider holdout tests must compare wrong Found, missed Found, lost Transferable, technical error rate, token usage, request count and wall-clock latency; unavailable model access prevents honest accuracy certification.
- Full protected suite must pass in dependency-complete Python and native Windows environments before this release is named production ready.

## Safety and rollback

Keep the current installation, CV sources, saved reports, `.env`, credentials and signing keys untouched. Extract this candidate under a **new directory**. Never overwrite a working installation with a development RC. The new protocol/build rejects incompatible cached final decisions; historical saved records retain their original historical state. If acceptance fails, continue using the original installation rather than rewriting archived Unverified decisions into negatives.
