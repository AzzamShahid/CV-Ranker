# V4.9.32 · Unverified ranking explanation and step-numbering repair

Build: `phase7g-v4-9-32-unverified-reasoning-ui-fix-2026-11-10`

## Confirmed failure

When one or more frozen JD criteria were unverified, `weighted_candidate()` correctly withheld the candidate's score and all per-criterion point contributions. The new V4.9.31 overall/individual Why panels nonetheless formatted `earned_points` or `possible_points` with `:.2f`, causing `TypeError: unsupported format string passed to NoneType.__format__` and preventing the results page from rendering. The issue affected both mixed complete/incomplete groups and entirely withheld rankings.

## Repair

- The results UI now formats all optional point values through a shared helper. Missing point values are labeled `points withheld · assessment incomplete`, not fabricated as zero.
- A CV with verified Found evidence but at least one unverified criterion retains its source-backed partial findings, marked as **unscored**. It still receives no weighted score or rank until assessment is complete.
- Both the overall leaderboard explanation and individual candidate explanation handle withheld points consistently; the completed candidate comparison remains unchanged.
- Step numbering is now explicit and sequential: (1) Upload documents, (2) Extract JD requirements, (3) Review and approve, (4) Category weightage, (5) Individual requirement allocations, (6) Assess candidates. Nested upload headings no longer reuse step numbers.

## Tests

- Streamlit result rendering is exercised with two completed candidates, one unverified + one completed candidate, and two unverified candidates.
- Regression coverage checks the exact step sequence and guards the absence of missing-point formatting failures.
- All existing scoring, recovery, cumulative HTTP budget, exports, citations, and assessment semantics remain unchanged. No paid provider requests are needed for the offline checks.
