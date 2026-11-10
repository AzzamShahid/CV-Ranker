# Phase 7G V4.3 — JD tenure, studies and cloud focused checks

22 October 2026 · Build: `phase7g-v4-3-duration-qualifications-cloud-repair-2026-10-22`

## What changed

1. **Experience and qualifications are JD criteria.** Explicit required education and professional-tenure statements are recovered from source sections even when the LLM omits them or the employer wrote an unbulleted paragraph. Strong mandatory one-line requirements in otherwise unsectioned prose are also captured. Their original wording, type and source are frozen before scoring. No discipline-specific skills or degree requirements are fabricated.
2. **A years requirement cannot be satisfied by listing a related skill.** The original three-year applied-AI example retains human review of its compound work scope, but a CV explicitly reporting only two years and four months fails the independent minimum-years check. Exact months are included in numeric comparisons. A subsequent capability-focused LLM check cannot promote a numerically insufficient statement to Found.
3. **Education only affects required/preferred totals when demanded by the JD.** An applicant's BS degree alone never creates a new JD condition. For presentation, each candidate now has a separate expand/collapse view of their exact work, education and credential source segments, whether or not the JD scores them.
4. **OpenRouter failures are more actionable.** Focused cloud checks request compact, Pydantic-validated structured JSON first. HTTP 400/422 may retry in locally validated JSON-object mode; temporary 429/5xx errors get bounded retries; 401/402/403/404 are identified as account/model access blockers. A transient error does not disable every remaining check. Notices identify the sanitized HTTP reason without CV text or secrets.
5. **Supervisor review.** The full required/preferred leaderboard, Found/Transferable/Not Found table, per-criterion reasoning, source excerpts and CSV/JSON exports remain available. The frozen JD table includes minimum years and degree metadata.

## Reproduction / limits

- Run `run_ui.cmd` on Windows, verify the new sidebar build ID, then **rerun the full assessment** with the actual uploaded JD and candidates. A prior Streamlit session retains its old frozen criteria; code updates cannot retroactively add a JD requirement to a completed report.
- With `sample_data/applied_ai_jd.txt`, the frozen list contains **10 required + 7 preferred**, including the three-year requirement. The synthetic under-three-year CV is **not** awarded that years criterion. This is a source-evidence screen, not authenticated career history.
- The bundled AI JD does **not** demand a degree, so the BS Computer Science claim appears as CV background, not an eighteenth requirement. A different JD requiring a bachelor's degree will include a separately scored education criterion.
- OpenRouter requests cannot be guaranteed without a working configured key, credit balance, supported model endpoint and acceptable rate limit. Errors are surfaced; a failed remote judgment never becomes a fabricated positive match.
- User-uploaded/private candidate documents and API keys are not shipped; the clearly marked fictional `sample_data` resumes/PDFs are retained for a reproducible demo. No fixed job-family vocabulary, semantic skills list or manually assigned preferred-skill bonus was introduced.

## Verification

Run `python -m pytest -q`, `python -m cv_ranker.runtime_check` (or `run_runtime_check.cmd` on Windows), and `python doctor.py --live` where Ollama/OpenRouter are configured. In the Phase 7G V4.3 regression file, HTTP responses are mocked; it is not a live provider or credential test.
