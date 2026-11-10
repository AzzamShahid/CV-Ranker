# V4.9.23 — First-page weightage configuration and simplified navigation

## First-page scoring configuration

- The **01 Analyze** page contains Experience, Education and JD requirements
  weighting with synchronized percentage sliders and numeric (+/-) inputs.
- Default is **10 / 10 / 80**. The five built-in presets are folded away until
  needed; the **Fill remainder** action uses whatever remains to reach 100.
- The three weights must total **exactly 100 marks**, matching the supervisor's
  uploaded scoring prototype; incomplete or excess allocation blocks a new run.
- The **Split JD into Required / Preferred** toggle exposes Required's portion
  of the JD weight. The unsplit default retains required-first treatment.
- Adjusting weights reprojects verified decisions on the results page without
  another model call, re-extraction, or modification of the source evidence.
- If the approved JD has no criteria in an allocation category, that category
  is excluded and the remaining applicable weight is renormalized visibly.

## Focused UI

- The visible synthetic sample/demo selectors are removed. Existing synthetic
  test fixtures remain in the package for automated verification only.
- The sidebar houses model/provider selection, advanced controls and a
  collapsed **Session controls** section for clearing the active result.
- The first page keeps upload, allocation, JD approval, assessment and resume
  controls in a single workflow without additional demo actions.
- After an assessment exists, **Continue to Results →** opens the
  **02 Rankings & evidence** tab. Navigation uses stateful tabs so uploaded
  files and reviewer edits remain mounted.
- The results page retains the weighted 0–100 leaderboard, verified evidence,
  original required/preferred match counts and one-click complete ZIP export.

## Compatibility and scope

The evidence assessor, JD review gate, optional semantic evidence retrieval,
source citations, and experience/education evaluation remain unchanged. The
prototype's fictional candidate scores are not imported and no fake candidate
data is displayed. An existing completed run can be reweighted in the same
session, but the uploaded document data stays in memory only until the session
ends. Download the complete results ZIP to keep a copy.
