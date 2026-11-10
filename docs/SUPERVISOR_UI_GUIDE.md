# Supervisor UI — Phase 7G V4.5

The Streamlit UI has four tabs:

1. **01 Analyze** — paste or upload a job description, add multiple PDF/DOCX/TXT/MD CVs, and run one analysis. In the sidebar, choose **Cloud (OpenRouter)** or **Local (Ollama)**; the actual model for each option is configured in `.env`, not an editable UI value. Optional AI capability cross-check uses local EmbeddingGemma plus the selected assessment model. The sidebar displays its build identity and selected model read-only. Switching requires another Analyze run; existing scores are not recalculated silently.
2. **02 Rankings & evidence** — first the total criteria and analyzed CV counts; then a **leaderboard of all candidates sorted high-to-low** with Required X/Y, Preferred X/Y, Transferable, and any review status; below that a selector and **one reconciled requirement table** for the selected candidate. Expand a row for the why, exact CV citation, and highlighted source text. Export the ranking or a candidate's final decisions to CSV.
3. **03 CV source segments** — all original captured source segments and section metadata for inspection, not just accepted evidence.
4. **04 Technical details** — original assessment and optional model relationship proposals for forensic comparison. These do not create a competing set of user-facing decisions.

Required score is `100 × Found required / total required`. Preferred Found breaks ties; Transferable remains visible but earns no direct points. An explicit, affirmative ordinary skill claim can count as Found with the source noted as CV-reported; project application is separate evidence. Incomplete checks are marked for review and are not proof of candidate inability.

When the JD explicitly demands a professional-duration minimum, **years of experience are a standalone Required/Preferred row**, validated against stated CV duration. A degree/field requirement is separately validated against the candidate's reported education. Related but different same-level studies may be marked **Transferable** after model review with an actual degree citation; an unrelated major cannot count as the requested field. If the JD has no explicit years or education criterion, the table flags that fact; educational history still appears under **CV background**, not as an invented scoring row. PDF line wraps do not create extra criteria.

For exact supervisor talking points, screen order and worked examples, see [SUPERVISOR_WALKTHROUGH.md](SUPERVISOR_WALKTHROUGH.md). The package includes fictional sample CVs; handle uploaded real applicant data and exported detailed JSON as sensitive.

