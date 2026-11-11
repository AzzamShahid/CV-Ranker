# V4.9.25 — JD counts exclude separately weighted categories

## Disjoint criteria groups

The same four categories are used consistently for weighted scoring and
human-visible counts:

1. **Experience:** JD requirements with an explicit numeric professional
   duration threshold, evaluated by the established tenure evidence rules.
2. **Education:** explicit degree or study requirements.
3. **Required JD:** remaining required qualifications, skills, duties,
   certifications and qualitative experience without a numeric threshold.
4. **Preferred JD:** remaining preferred qualifications, skills, duties and
   qualitative experience without a numeric threshold.

A JD phrase is assigned to exactly one bucket. A qualitative experience
requirement such as building production-oriented APIs is a JD competency,
not an implicit multi-year experience gate. No role-specific hardcoding is
introduced.

## UI and exports

- The approval banner identifies four distinct totals.
- The results summary reports only JD Required and JD Preferred totals in
  the JD counters; a caption identifies separately assessed categories.
- The leaderboard reports JD-only Required/Preferred match counts and shows
  Experience/Education coverage separately when those buckets exist.
- Candidate details display JD-only Required/Preferred counts, separate
  Experience/Education counts, and one final weighted score. The requirement
  table and CSV identify each scoring category, and the category filter uses
  the same four disjoint groups.
- Both the page 02 CSV and the ZIP's weighted leaderboard export use the same
  categories. Original backend criterion decisions, counts, and citation
  evidence remain available in full raw audit JSON.

## Non-goals

This change does not revise LLM verdicts, retrieve different CV passages,
change classification of the approved JD, or grant credit for Transferable
results. The only scoring adjustment is the domain-neutral placement of
qualitative experience in the JD bucket rather than the numeric tenure
bucket, consistent with its verified schema type.
