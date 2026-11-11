# Phase 7G V4.9.39 — Restore each requirement's independent Why

## Reported regression

The user exported the individual candidate's final requirements dataframe and
found columns for ID, requirement, priority, category, decision, cited segments
and review, **but no Why**. The separate leaderboard already displayed
`Why this rank`. The user needs the former *per-requirement* explanation as a
distinct section, e.g. why a candidate's explicitly reported 4 years 5 months
of scoped experience satisfies a 3-year job requirement.

## Root cause

The individual evidence expander retained a model `reason` string but omitted a
visible **Why** heading. More importantly, the primary `st.dataframe` selected
only seven columns, dropping the per-criterion `Why` field. Users exporting
that visible table through Streamlit's built-in CSV button received exactly
those seven fields. The separately implemented `Download final decisions (CSV)`
already carried a `Why` field; the two exports had inconsistent contracts.

The numeric experience validator also retained stale initial model reasoning
after converting a model `not_matched` to source-supported `matched`. In some
cases that produced a contradictory, generic explanation under a Found verdict.

## Fix

- Show `Why this decision` in the individual requirements dataframe as a
  readable column, included in the table's built-in CSV export.
- Label the existing evidence expander's explanation **Why this decision**, before
  showing JD wording and original source passages.
- Preserve the distinct leaderboard field `Why this rank`: individual evidence
  decisions and comparative position remain conceptually separate.
- For a sufficient **source-grounded numeric** experience check, derive one
  concise explanation from the accepted literal duration clause, typed JD
  threshold and original segment section. It states where the experience is
  claimed and that the claim is not independent employment verification.
- Keep the dedicated full-decisions CSV and audit JSON. The change does not
  affect model calls, category weights, Found logic, source IDs or rank scoring.

## Tests

- Reproduce the reported absence in the old visible CSV column list.
- Use the real bundled Bilal PDF to confirm a negative first-model judgment is
  corrected to Found with a reason containing the original `4 years 5 months
  of professional AI/ML delivery` and the JD's `3 years` threshold.
- Run a Streamlit component test asserting the requirement table contains
  `Why this decision` with the full explanation and the separate individual
  ranking explanation remains available.
- Re-run prior validation and ranking tests; no candidate or profession is
  special-cased.

## Operation

The new build ID invalidates stale in-memory assessment checkpoints. A fresh
analysis and export under this build is needed; old saved CSV files do not
gain missing columns. Live cloud-provider behavior is not represented by the
offline regression tests.
