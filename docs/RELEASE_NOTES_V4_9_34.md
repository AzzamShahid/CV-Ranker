# Phase 7G V4.9.34 — focused unresolved review and supervisor presentation

Date: 10 November 2026

## Symptom

At least one CV remained Unverified (example: `02_bilal_direct_fullstack.pdf`,
R008) even when other candidates had finished. The UI displayed a generic
ranking-withheld message after automatic retries paused. Streamlit's top-right
script activity icon did not spin during background execution. Ranking
reasoning was inside a collapsed section and printed internal source IDs.
The first setup page visually skipped numbered steps because some labels were
inside controls instead of at the same heading level.

## Source-level findings

- The auto-recovery code was designed to stop identical source-validation
  failures, but previously surfaced mostly a generic no-progress notice.
- The final adjudication selected unresolved requirements **and** optional
  overlap reviews together. This could increase the prompt and schema size
  for the only requirement preventing a complete candidate result.
- The bundled example Bilal PDF includes held-out evaluation sets, retrieval
  recall metrics, response-faithfulness measurements and baseline comparisons.
  An offline source-grounded synthetic LLM verdict for R008 passes the actual
  validator. The exact OpenRouter failure is still unknown because no
  provider run log/structured response was supplied.
- Background workers run on independent threads; Streamlit's global script
  spinner therefore need not indicate their activity. This was a UX problem,
  not proof that no API request occurred.

## Corrections

1. An unfinished requirement takes priority over optional overlap reviews in
   the final bounded verification. Actual source-validation notices are sent
   to its corrective context, without requesting a whole fresh CV assessment.
2. Incomplete candidate summaries now show unverified requirement names,
   sanitized validation reasons and relevant original passage excerpts.
3. The automatic and manual background fragments render a persistent
   `st.status(..., state="running")` widget with progress and elapsed time.
4. Steps 1–6 are consistently visible as section headings in order, including
   extraction after upload and separate category/requirement allocations.
5. Each leaderboard row includes an evidence-weighted "Why this rank"
   explanation. All candidates' position summaries are visible immediately;
   the more detailed comparisons remain available below.
6. Internal CV segment identifiers are omitted from supervisor-facing
   explanatory prose. Their original IDs remain in evidence, checkpoint
   diagnostics and exported audit files for traceability.

## Safeguards and limits

- No named-skill aliases, employer names or candidate-specific scoring rules
  were added. Verified Found, Not Found and Transferable decisions remain
  source-grounded and use the same dynamic weighting formulas.
- An R008 judgment still remains Unverified if the chosen model cannot
  produce a valid semantic determination; this release will **not** silently
  convert a failed model response into a Found or Not Found score.
- A live OpenRouter run, or the affected run's sanitized per-criterion
  validation diagnostics, is necessary to attribute the exact repeated
  failure to provider JSON, citation selection, or semantic validation.
