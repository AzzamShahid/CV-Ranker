# CV Ranker Phase 7G · Interface V4.9.40

**Released:** 10 November 2026  
**Scope:** Streamlit visual presentation, no assessment or scoring changes

## What's more usable

- A prominent supervisor-edition header and consistent, readable page structure.
- Clear step-by-step headings for JD upload, extraction, review, category
  weighting, individual requirement allocation and candidate assessment.
- Responsive explanation cards on the leaderboard, highlighting why each CV
  received its position, rather than burying the rationale inside a wide table.
- A distinct **Why this CV received its ranking** summary for the selected
  candidate, followed by strongest credited requirements and weighted gaps.
- A separate **Why this decision** explanation inside each requirement's
  expandable original-CV evidence view. The full explanation remains in the
  requirements table and its CSV export.
- Cohesive metric tiles, group separators, evidence excerpts, expanders,
  buttons and table containers across analysis, rankings, source segments
  and technical audit.
- Untrusted candidate/CV/JD strings are HTML-escaped in the new visual cards.

## Assessment compatibility

The package's **UI version is 4.9.40**, while `BUILD_ID` remains
`phase7g-v4-9-39-individual-criterion-why-restored-2026-11-10` and assessment
protocol remains 31. This separation is intentional: interface-only changes
must not invalidate verified assessment data, replay previously completed cloud
requests or subtly change numerical ranking results. Existing scoring and
source audit functions are reused unchanged.

## Verification

- Targeted scoring, dynamic allocation, individual-Why and visual safety tests.
- Full bundled Python test suite.
- Source manifest rebuild and runtime integrity check.
- Streamlit `AppTest` renders the headline, candidate summary, and individual
  explanation components without exceptions.

The local Chromium sandbox in the packaging environment denied starting a
headless browser, so an external pixel-level screenshot comparison was not
possible here. Browser appearance should be checked on the supervisor's
preferred Windows/Streamlit display; this is a presentation-only limitation,
not a change in assessment accuracy.
