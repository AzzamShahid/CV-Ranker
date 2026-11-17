# TextileHR AI CV Ranker Supervisor Edition — v4.9.58

**Date:** 12 November 2026. **Assessment protocol:** `segment_ids_semantic_llm` v44. **Scope:** first implementation milestone **M0/M1/M2** of the Unified Master Remediation Plan. **Not a full M0–M8 release.**

## Fixes actually implemented

1. **Confirmed production defect:** for compound `needs_review` clauses, the grammar checker could overwrite a correctly source-grounded Found or Transferable. A conservative source-preserving path now protects: (a) an affirmative, full-text original-CV skills claim for a knowledge criterion after original source-ID/text checks and existing positive-evidence validation; and (b) already model-proposed Transferable accompanied by cited, completed affirmative work. All other ambiguous clauses continue to trigger review/negative safeguards.
2. **Reconciliation integrity:** a non-null `compound_check` no longer serves as a blanket veto of previously validated Transferable. Related completed work must have original citations and cannot be instruction-only, unrelated citation-only, or negated work. Education/experience specialist restrictions are unchanged.
3. **Auditability:** `RequirementAssessment.decision_trace` stores source-ID-only records of compound syntax review and material status changes. No raw applicant text is added to trace entries. Old reports without the optional field remain parseable.
4. **Cache identity:** assessment logic fingerprint now includes decision-bearing `pipeline.py`, `schemas.py`, `eligibility.py` and relevant semantic modules. Editing these modules invalidates reuse of their old assessments. CSS-only editing does not cause assessment reuse invalidation.
5. **Regression tests:** synthetic, domain-neutral reproductions first failed in unmodified v4.9.57 (2 failures, 5 passes); after repairs, the expanded 12-test regression file and 86-test directly related group passed. Negative cases cover partial named AND, unsupported Found, forged source ID/text, negative status preservation, technical Unverified, trace and cache fingerprints.

## Behavioral safeguards retained

- No name-, company-, tool- or `R###`-specific production verdicts.
- `Found` alone earns direct weighted points; Transferable displays but earns zero.
- Strict source provenance, no unapproved paid calls, no change to retry caps or cloud integrations.
- Already supported direct AND/OR literal options still checked; mandatory-work negative cases continue failing closed.
- Historical protocol v43 assessments are **not** presented as re-evaluated under v44. Restart the application and run a **fresh** JD assessment for new behavior.

## Verification and limits

The local build completed 86 directly targeted regressions and a broader locally available dependency-independent suite (**1,170 passed**, with 20 test modules intentionally excluded due to missing Streamlit/LangChain dependencies). The full native Windows suite, interactive Streamlit UI, real OpenRouter/Ollama performance, real CV 4/CV 5 incidents and held-out result-quality benchmarks are **not verified** in this environment. The system remains supervised local decision support, **not certified production screening**.

**Incomplete milestones:** M1 full canonical JD meaning contract; M2 full source-validated semantic entailment and immutable decision authority; M3 JD semantic typing/source coverage; M4 retrieval/provider budgets; M5 productive recovery; M6 export/UI parity; M7 cross-domain/live benchmark; M8 optional secure remote production. No claim is made that the v4.9.57 no-progress warning is fully resolved.

## Windows setup / rollback

Extract this release to a **new folder**. Do not copy `.cv_ranker_cache` or old recovery signing keys into the source ZIP. Copy only your privately held configuration (e.g., `.env`) locally as appropriate. Activate your existing compatible environment or install pinned requirements, then run `run_runtime_check.cmd`, `run_tests.cmd`, `run_ui.cmd`. Start a new v44 assessment; use v4.9.57 separately to view/rollback historical v43 reports. Old reports should not be labeled fresh v44 judgments.

## Test-only Windows packaging correction (same build and protocol)

Updated `tests/test_v4940_visual_refresh.py` to avoid asserting the stale
4.9.57 build identity after this v4.9.58 release. The test now verifies the
UI-to-build identity consistency and requires assessment protocol v44 or later.
This is a **test and manifest change only**: production assessment logic,
model prompts, scoring, API calls, and cache identity are unchanged.

A Windows run of the original ZIP reported 1,380 passed, 1 failed at this
stale assertion. The corrected full-suite outcome must be verified again on
the Windows installation; that previous run is not claimed as a new pass.
