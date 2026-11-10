# CV Ranker Phase 7G · Interface V4.9.41

**Date:** 10 November 2026  
**Scope:** Supervisor-facing presentation only; no assessment protocol changes.

## Supervisor reading order

1. **Candidate leaderboard** — a sortable table retaining current scores,
   required/preferred counts where enabled, and `Why this rank`.
2. **Why candidates ranked this way** — one full-width row per candidate, with
   rank, verified score and one source-derived placement explanation. No
   alternating card columns or duplicate candidate narratives.
3. **Optional head-to-head comparison** — closed by default, select one
   candidate to compare against the leader, including actual differences,
   additional Found requirements and their complete reasons.
4. **Individual CV explanation** — a prominent summary plus clearly separated
   match strengths and missing requirement evidence. The individual criterion
   `Why this decision` remains separate from leaderboard placement reasoning.
5. **Requirement evidence** — each criterion is titled in ordinary language;
   technical source IDs remain visible inside the expanded citation audit and
   downloadable records, not in crowded row headings.

## Audit separation and warnings

- `Reasoning reliability check · structurally_valid` is no longer displayed in
  the normal candidate results. It is an internal structural consistency
  result, not proof that a person possesses a skill or that a model judgment is
  correct.
- The full status, warnings, repaired explanations and scope of verification
  remain inspectable in **Technical details → Reasoning verification · internal
  audit**. When a completed explanation needs attention, the normal result
  includes a short warning linking readers to that audit.
- A technically incomplete assessment remains visibly unranked, with its
  missing requirements available for review. The overview avoids long raw
  validator messages, while the detailed records and diagnostics remain.
- If the approved JD does not specify a degree or numeric experience minimum,
  the interface notes this neutrally. It does not imply an unrequested
  qualification was failed.

## Data and compatibility guarantees

The UI uses the unchanged `comparative_reasoning` and `candidate_reasoning`
outputs. It retains complete `placement_reason`, `summary`, per-requirement
`why`, weighted comparisons, source IDs and exports. It never infers a score
for an incomplete CV, adds an AI request, changes a frozen JD, or adjusts
weightage. Newly rendered strings remain HTML-escaped.

The interface release is **V4.9.41**, but the assessment identity stays on
**V4.9.39 / protocol 31** because no scoring or assessment behavior changed.
Existing completed checkpoints should therefore remain compatible.

## Quality checks

The tests exercise Streamlit render paths for completed and withheld
assessments; distinct ranking explanations and criterion decisions; safe
rendering of untrusted candidate text; placement audit diagnostics exclusively
in Technical details; and regression scoring and pipeline behavior. The source
manifest and ZIP package are independently verified.

An automated pixel screenshot was unavailable because both the local Chromium
sandbox and the separate browser surface could not access the local Streamlit
server. Final display should be checked in the supervisor's browser before
live deployment.
