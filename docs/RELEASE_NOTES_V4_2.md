# Phase 7G V4.2 — leaderboard restoration and presentation

**Date:** 22 October 2026

## Fixed

1. `render_app()` once again calls the existing leaderboard renderer **above** the selected candidate's final decision table. V4.1 retained `_ranking()` but the results tab omitted the call, so users saw only the selected candidate.
2. Leaderboard construction now lives in the tested presentation helper `cv_ranker/ui_support.py:final_leaderboard_rows`. It reads the same final reconciled Found counts as the detail table and orders by exact required fraction, then preferred Found fraction. Percentage display is rounded only after sorting.
3. It shows `Required X/Y`, `Preferred X/Y`, `Transferable`, assessment mode, and a `Review` state for every candidate. Unfinished candidates are not silently labelled 0%; old unreconciled sessions are clearly labelled for rerun rather than pretending that transferability was checked.
4. Downloaded leaderboard CSV contains the same rows as the on-screen table.
5. Added targeted regressions in `tests/test_supervisor_final_leaderboard.py` to lock down ordering, displayed counts, no transferable score inflation, failed-run status, and rendering order.

## Unchanged from V4.1

- The user-facing decisions remain **Found / Transferable / Not Found** in one final table per candidate.
- Affirmative, non-negated ordinary skills-list claims can be counted as Found; source and level of evidence are retained.
- Explicit named-tool denials remain important; a functional alternative can be Transferable, not a fake direct match.
- Every original cited source checkpoint, explanation, and unfiltered source ledger is preserved.
- Reconciled final Found required counts are the only source for the **displayed** final ranking score. No extra preferred weighting or transferable points are introduced.
- The original V4 assessment remains downloadable under Technical details for audit.

## Project arrangement

The root README is shorter and now leads directly to Windows setup, scoring rules, supervisor walkthrough, and folder layout. Earlier phase/release notes are retained in `docs/history/`; core modules, evaluation tools, synthetic datasets, scripts and regression tests stay in their existing functional folders. Source functionality is preserved, not reimplemented as a separate demo app.

## Checks

On Windows after installing `requirements.txt`, run `run_runtime_check.cmd`, `python -m pytest -q`, then `doctor.py --live` if external models are configured. The last command tests your local environment and is not a prerequisite for offline UI startup.
