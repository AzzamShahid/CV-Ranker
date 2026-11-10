# Phase 7G V4.4 — JD completeness and academic transfer

22 October 2026 · Build: `phase7g-v4-4-jd-coverage-education-transfer-2026-10-22`

## Problem reproduced

The user's previous exported final evidence reported **9 Required / 7 Preferred** and did not include a separate numeric professional-years criterion or a degree criterion. The CV's `BS Computer Science` and employment dates appeared under **CV background**, not the frozen JD assessment. Consequently, a `9/9` result was only complete against the *incomplete frozen list*; it was not proof of three years' experience.

The bundled example Applied AI/ML job description explicitly requires at least **three years of relevant professional experience** but **does not explicitly require a Computer Science degree**. The actual user-uploaded JD was not present in the exported evidence JSON; criteria cannot be fabricated from the CV or guessed from the role title.

## Repairs

1. **JD denominator recovery.** Explicit required years, qualifications and degrees are preserved even if they follow a section heading across blank lines or the extraction model omitted them. Additional standard qualification section headings are recognized, without a profession-specific skill dictionary.
2. **PDF layout repair.** A wrapped three-line tenure statement becomes one JD requirement rather than two fragments. Embedded PDF bullet glyphs are removed from frozen criterion labels. Original source line numbers cover exact text that spans consecutive physical JD lines.
3. **Education identity and relationship.** Completed same-level, same-field claimed degree is Found. A completed same-level but *different* degree cannot be promoted to Found by the model; with a real cited degree claim and a reasoned domain-appropriate LLM review, it may be reported as Transferable for supervisor review, **with zero scoring points**. Unrelated degrees are Not Found. A model failure cannot turn a different degree into a direct academic match.
4. **CV section labelling.** Combined `EDUCATION AND NOTES` headings label reported degrees as education, not experience; `SELECTED PROJECT OUTCOMES` is recognized as projects.
5. **User-facing check.** If the uploaded JD yields no numeric-years criterion or no degree criterion, the final-assessment screen says so explicitly. The leaderboard and evidence table still derive from the same one set of Found / Transferable / Not Found decisions.

## Reproducible checks

- **Bundled role JD:** `sample_data/applied_ai_documents/jd/Applied_AI_ML_Engineer_Updated_JD.{txt,docx,pdf}` must all freeze **10 required + 7 preferred** criteria and identify **one 3-year required tenure** row. None of those three JD formats specifies a degree.
- **Bundled applicant CV:** `sample_data/applied_ai_documents/pdf/10_farhan_under_3_years.pdf` reports **2 years 4 months** of relevant professional experience; the numeric requirement validator returns **insufficient** against 3 years.
- **Academic cross-field regression:** For a separate *synthetic JD* explicitly requiring `Bachelor's degree in Computer Science`, `BS Computer Science` can be Found; `BS Software Engineering` can be Transferable with a grounded focused judgment; `BS Fine Arts` is Not Found. Transferable earns zero Required points. Regression tests mock the cloud adjudicator, so they do not prove live-provider quality or guarantee any particular semantic judgment.
- Run `python -m pytest -q` and `python -m cv_ranker.runtime_check`. They do not require an OpenRouter key. `python doctor.py --live` requires configured provider/network access.

## Important limitations

- A document that **does not actually state** a required level, field, tenure or qualification cannot legitimately produce such a scored row. If a particular uploaded JD still reports 9 Required, inspect its extracted text and provide that exact JD for a targeted diagnosis.
- The project verifies **claims from CV source passages**, not real academic attainment, professional competence or employment verification. Academic *transferability* must be reviewed by a supervisor.
- The OpenRouter API key, user documents and any sensitive results must stay outside release packages. Live OpenRouter reliability depends on model availability, API permissions, credits and rate limits. Previous V4.3 cloud error recovery remains; V4.4 adds no guarantee of successful external calls.
- No fixed computer-science/arts skill list, guessed hiring credentials, or additional preferred weighting is introduced.

## Installation

Extract V4.4 into a **fresh directory**, verify the build ID in the sidebar, and rerun the JD and CV analysis. Do not mix with a running V4.3 Streamlit server or expect its old final evidence export to acquire newly recovered criteria automatically.
