# TextileHR AI three-verdict implementation — preview qualification report

**Date:** 2026-11-15  
**Build:** `phase7g-v4-9-69-three-verdict-preview-2026-11-15`  
**Protocol version:** 55 (development preview only)

## Baseline identity and limitation

The supplied master execution prompt mandates the Windows-compatible `TextileHR_AI_CV_Ranker_v4.9.68_Windows_Test_Compatibility_2026-11-14.zip` (SHA-256 `813f1deb8456d78ea16d52ec1398bdd2f1c9981654a848249f686c560bd24587`). That exact archive was **not** present. Available `TextileHR_AI_CV_Ranker_v4.9.68_Prompt_First_Repair_2026-11-14(1).zip` hashed to `e7b342bc20ec2045ff7c15912059cd2e632cc698c3eb685601858c9cd96388a5`. Work was performed against that distinct archive; no Windows compatibility carry-forward may be asserted.

## Implemented source changes

1. Application-owned typed `DecisionRecord`, `ProcessingFailure`, and finite failure-code enum.
2. Live **unified**, **independent**, **compound semantic**, and **focused judge** model schemas restrict final responses to three choices; key prompts revised accordingly.
3. Source-identity failures and unfinished final reconciliations have empty final verdicts; scoring revalidates canonical records and withholds full scores.
4. Legacy model-request failures and persistently invalid citations are no longer automatically reported as candidate negatives on the modified routes.
5. The weighted leaderboard suppresses official score/rank for incomplete candidates while retaining explicitly separate provisional bounds.
6. Unified UI and ranking-reasoning projections prioritize the current decision; historical labels remain readable.
7. Semantic compound response-validation failure is distinguished from unknown provider delivery, preventing a misleading retry classification.

## Qualification status — **incomplete, not production ready**

- **Full three-verdict adoption is NOT complete.** The legacy assessor still has final `uncertain` model output; several compound, specialist, UI, semantic transferability, cache/recovery and report paths retain the old internal `Unverified` contract. The prompt/caller and route ledgers identify these.
- No live-provider, offline model quality benchmark, unbiased held-out evaluation, real Windows launch, full native UI or restart qualification has been run.
- The exact mandatory Windows-compatible baseline is unavailable, so a patch against it cannot be certified.
- Historical reports deserialize but a full version-aware historical UI/reassessment migration is not implemented.
- Older regression tests requiring the *old* `Unverified` label are expected to fail. They have **not** been silently altered to improve pass rates.
- An early broad run reached **963 passing tests** before `--maxfail=15` stopped. Those failures include expected old-contract assertions and missing `streamlit`, `langchain_core`, and `langchain_ollama` dependencies. This is **not** a complete suite pass or a certified test count.
- Paired provider model accuracy, token count, latency and cost experiments were **not** performed. No improvement in judgment accuracy is claimed.

## Local focused tests and expected contract

`python -m pytest -q tests/test_three_verdict_transition.py tests/test_v4968_prompt_first_contracts.py tests/test_v4967_operation_subset.py tests/test_v4966_current_defects.py`

Expected result on this working preview: **53 passed**. The newly added tests cover source-citation mismatch, 429 preservation, typed contract invariants, official-rank withholding, historical parsing, and an invalid `model_copy` score-boundary guard.

## Do not deploy yet

This preview is a partially implemented vertical slice. Production completion still requires applying the patch to the mandated Windows-compatible source, migrating all assessor/transferability/validator/recovery paths, full UI and exports testing, full protected suite with dependencies, protocol-aware historical migration, Windows handoff and independent semantic accuracy gates.
