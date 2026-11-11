# CV Ranker Phase 7G · Interface V4.9.42

**Released:** 10 November 2026  
**Scope:** Completion and review-status presentation; no change to assessment decisions.

## Problem

The old `Provisional` flag means either an incomplete assessment **or** a
completed assessment containing a criterion marked for human judgment. For
example, a fully scored candidate with one Transferable requirement could be
shown the broad and alarming banner even though every requirement was processed.

## Resolution

- Removed the generic provisional banner for completed candidate assessments.
- Kept prominent blocking warnings when the ranking is genuinely withheld.
- Added a plain-language error if an otherwise scored candidate unexpectedly
  contains an unverified final criterion. This does not silently repair scores.
- Showed a quiet, criterion-specific `Human review suggested` note in affected
  requirement evidence panels instead of a candidate-wide warning.
- Replaced the leaderboard's `Provisional · review` label with three accurate
  states: **Complete**, **Review suggested (N)**, and unverified/unranked status.
- Standardized the one-click ZIP `weighted_leaderboard.csv` and candidate
  `weighted_result.review` status with the same labeling rules. Older partial
  export payloads remain accepted.

## Compatibility and safety

`Provisional` stays in raw `final_decisions` JSON for existing downstream
consumers, but is no longer interpreted as equivalent to assessment failure.
Its original semantics remain intact; only supervisor-facing status wording
and placement changed. None of the LLM prompts, source validation, YAKE,
embedding retrieval, scoring, threshold checks, retry budgets or cloud requests
were changed. Incomplete candidates still cannot receive a fabricated rank.

UI release: **4.9.42**. Assessment build ID remains
`phase7g-v4-9-39-individual-criterion-why-restored-2026-11-10` and protocol 31,
so a cosmetic release should not invalidate previous completed assessments.

## Validation

Regression tests cover a scored candidate with a legacy provisional flag,
completed candidates with and without criterion-specific review flags,
consistent supervisor exports, unavailable/incomplete candidates, and the
existing assessment pipelines. A new source manifest and signed-inventory ZIP
are built after the full test suite passes.
