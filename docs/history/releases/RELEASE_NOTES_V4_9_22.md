# V4.9.22 — Configurable weighted scores and complete one-click export

## Supervisor score configuration

- Experience / Education / JD defaults are 10% / 10% / 80%.
- Sliders and manual integer numeric entry (+/- controls) update results
  without invoking the LLM, altering the frozen JD, or changing citations.
- All entered weights normalize to 100%. Categories absent from the JD are
  excluded; no CV-only qualification is manufactured or silently penalized.
- A **Split JD into Required / Preferred** button enables an adjustable
  80/20 subweight; by default all JD weight goes to Required and Preferred
  is a tie-breaker, preserving the previous preference rule unless chosen.
- Numeric and qualitative experience JD criteria share the experience bucket;
  education criteria occupy education; every other frozen JD item falls into
  Required or Preferred JD exactly once. The three main weights are distinct.
- Only verified Found earns direct credit. Transferable and Not Found earn
  zero; incomplete/unverified candidates are not ranked. The old required
  coverage is retained as a separate auditing number.

## One-click complete results archive

The ZIP includes the exact uploaded/extracted JD text (for new assessments),
approved frozen JD criteria, scoring configuration, weighted leaderboard CSV,
the full original assessment JSON, every candidate's final decision and
explanation, individual original CV source ledgers, and technical diagnostics.
It uses currently published session results; it never reruns model assessment.
Old reports without a retained JD source cannot reconstruct it and identify
that omission rather than claiming an inexact reconstruction is the original.

## Compatibility

The evidence engine, original required/preferred counts, skill negation and
experience validation, and all V4.9.21 evidence retrieval repairs remain.
This build adds a separately labeled weighted ranking projection for the
supervisor; the historical required-only score remains available for review.
