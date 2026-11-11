# Phase 7G V4.9.38 — Compound professional tenure parser correction

## Reproduced failure

On the bundled `02_bilal_direct_fullstack.pdf`, the exact frozen employer
requirement for a minimum of three years delivering or developing AI/ML-powered
software was classified as `experience / complex / minimum_years=3 / subject=None`.
The CV includes this explicit statement in its source-ledger summary:

> Applied ML and full-stack product engineer with 4 years 5 months of
> professional AI/ML delivery.

V4.9.37 extracted **zero usable duration claims**, returning `role_semantic`.
Because the model's selected citations were dated role headings instead of
the duties in every role, the status became Not Found/uncertain, although the
CV directly asserted more than the required three years in the relevant work.

## Root cause and correction

The V4.9.36 safety fix tightened duration attribution to prevent archive/data
coverage such as `four years of sales data` from becoming professional tenure.
Unfortunately, the grammar used `[\w-]+` for descriptors *between* the words
`professional` and `delivery`. It silently rejected `AI/ML` and a standalone
`&` connector. A correct source-grounded numeric statement was therefore
treated as if no professional-duration claim existed.

V4.9.38 expands the existing field-token grammar to accept `[/&+-]` within
compound professional descriptors. The duration must still be connected
grammatically to employment, professional work or an explicit work activity,
and, for an employer-scoped experience requirement, source terms must match
the actual frozen JD scope. The patch does **not** grant credit from a role
title, dates alone, work-domain similarity, a dataset duration or a prompt.

No rule mentions candidate names, source IDs, technologies, departments, or
the minimum threshold as a special case.

## Verification

- Reproduces original failure using the actual extracted Bilal PDF, the
  requirement's actual source-rule classification and original source segments.
- Confirms `4 years 5 months` is accepted as approximately 4.417 years and
  retained as an authentic citation after experience validation and final
  reconciliation, restoring a source-grounded Found decision.
- Uses other job scopes including professional quality/operations delivery,
  manufacturing & quality management and finance-compliance analysis.
- Preserves negatives for years of quality/production datasets, archive
  records and retail/sales data, including inside an Experience section.
- Re-runs existing Aisha-PDF, dated-role, negation, professional-duration and
  other validator tests to prevent undoing previous fixes.

## Operational behavior and limitations

The BUILD_ID and assessment protocol version advance to invalidate stale
in-memory checkpoints from the previous validator. Restart the Streamlit app
and start a new assessment (rather than resume an old result) when using this
release; a fresh provider assessment can incur the configured cloud cost.
This was verified with bundled PDF files and deterministic tests. No live
OpenRouter execution or actual external provider response has been claimed.
The program evaluates claims *made in the CV*, not independent employment
verification, which remains an HR responsibility.
