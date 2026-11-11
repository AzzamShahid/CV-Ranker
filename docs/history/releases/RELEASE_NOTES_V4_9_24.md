# V4.9.24 — Compact weightage, sidebar controls and YAKE review

## UI organization

- First page: one collapsed **Step 2 · Weightage configuration** section with
  live Experience / Education / JD percentages, sliders, numeric controls,
  100-mark allocation feedback and an optional fill-remainder button.
- Removed all weightage presets; the default remains **10 / 10 / 80**.
- Moved **Split JD into Required / Preferred** / **Combine JD groups** into
  the sidebar. Splitting reveals the Required percentage control inside the
  collapsed weightage section on page 01.
- Removed the duplicate **Required score** percentage from the leaderboard,
  summary CSV and complete-bundle leaderboard CSV. Required and Preferred
  matched/total counts remain available; the full raw assessment still
  contains original source-model fields for audit compatibility.

## Less-used controls

- Kept the JD processing limit in **Limits & cloud recovery** as a safety
  guardrail. Cloud auto-resume remains available because provider limits can
  interrupt a batch.
- YAKE phrase count uses the configured engine default (40); literal JD
  initialism checks remain enabled, and ambiguous-type model suggestions keep
  their configured default. These controls are no longer exposed on every run.
- HR equivalence and eligibility JSON files are **not required for ordinary
  screenings**. Their optional upload controls are preserved in a collapsed
  sidebar **Employer policies** section so existing authorized policies can
  still be used without cluttering the analysis page.

## Page 04: YAKE phrase discovery

- Displays the extracted phrase count and first-ranked phrase.
- Shows all original YAKE phrases sorted by ascending YAKE score with rank,
  search, exact numeric scores and a CSV download.
- Explains that a smaller YAKE score means stronger *JD phrase extraction*
  priority; it is **not** direct candidate evidence, a match percentage, or
  scoring credit. JD extraction diagnostics remain available separately.

## Scope

No JD extraction, AI assessment, source-citation, semantic-retrieval, or
score-credit logic is changed. The final weighted score is still computed
over the frozen, reviewer-approved JD using the user-configured weights.
