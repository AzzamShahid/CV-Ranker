# CV Ranker 4.9.43 — grouped correction consistency and safe document archive

**Date:** 10 November 2026  
**Assessment build:** `phase7g-v4-9-43-mixed-batch-recovery-2026-11-10`  
**Assessment protocol:** `segment_ids_semantic_llm` v32

## Behavioral repair

- Corrected the ID accounting in grouped model-response retries. A batch can contain a requirement with invalid optional highlight metadata, queued directly for independent original-source verification, **and** another requirement that needs one corrective request. The old correction bookkeeping incorrectly treated both as repaired because it compared invalid IDs against a response containing only the requested subset. That could cause an exception, hide a pending ID or lose a valid correction.
- The retry now updates only IDs that were included in the correction request and carries untouched invalid IDs forward to independent verification.
- For short explicitly listed skills, a domain-neutral ordered-word check now recognizes an original positive skills-list entry when one or two modifier words separate the JD label (for example, the JD's `LLM integrations` and a CV's `hosted LLM API integrations`). This discards **only an inaccurate optional model-written highlight**; the source citation and all remaining source/tone checks still apply. Negated, learning-only, punctuation-separated, work-history and non-skills examples do not get the shortcut.
- Added two no-network regression cases: (1) corrected peer and independently verified deferred criterion both complete; (2) corrected peer stays complete while an independently rejected deferred criterion stays **Unverified**, with its candidate ranking withheld.
- No semantic synonym dictionary, candidate-specific adjustment, scoring multiplier or extra model retry was introduced. A clearly cited skill can now avoid one otherwise redundant independent-model call.

## Documentation cleanup

- Moved 47 previous release-note files to `docs/history/releases/` without deleting their content.
- Moved five redundant, superseded overview/status/validation documents to `docs/history/legacy_reference/`, preserving them for audit.
- Added `docs/INDEX.md` as the navigation entry point; kept `README.md`, `docs/ARCHITECTURE.md` and `docs/REPOSITORY_AUDIT.md` authoritative.
- Preserved all tests, synthetic CV fixtures, older benchmark evidence, scripts and compatibility modules. Generated environment/data and cached applicant records are excluded from the source release rather than removed from the developer checkout.

## Upgrade and verification

This is a **behavioral** assessment change, so build and protocol identity changed intentionally. Previously saved verified results under the older identity must not be silently mixed into this revised run; this can require a fresh assessment under the updated release. Unlike the earlier presentation-only releases, this change cannot guarantee zero additional model requests after an upgrade.

Run `run_tests.cmd` and `run_runtime_check.cmd`. A local/cloud provider smoke test should be performed with synthetic data, an explicitly approved request budget and no real applicant CVs during release acceptance.

Offline tests verify deterministic source and control-flow rules, not the factual accuracy of model conclusions. The tool remains **human-supervised screening support**, not production-certified hiring automation.
