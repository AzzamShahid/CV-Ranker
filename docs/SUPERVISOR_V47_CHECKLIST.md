# Phase 7G V4.7 — Final supervisor checklist

1. Extract V4.7 into a **new** folder; do not combine files from previous builds.
2. Create private `.env` from `.env.example`, set cloud/local models and required API key, and start Ollama. Never share API secrets or applicant data in the ZIP.
3. Run `run_runtime_check.cmd`, then `run_tests.cmd` and `doctor.py --live`. A cloud HTTP 429 means quota/rate limit; it cannot be bypassed by the application.
4. Load the fictional demo JD with **11 Required / 7 Preferred**. Confirm separate years and degree requirements were frozen from the JD itself.
5. Verify the leaderboard Required/Preferred/Transferable counts equal each candidate's final table; only **Found** scores.
6. For Sara, inspect **LangChain**: performed alternative work + explicit functional comparison should be **Transferable**, not Found. Expand source text. **LangGraph** analogies remain reviewable.
7. Inspect **Node.js**: Not Found with a representative evidence sample, an honest total-segments-considered number, and the full original ledger in tab 03.
8. Keep the **Time-series forecasting** final decision unchanged in this presentation build.
9. Confirm the leaderboard and candidate panel say **Provisional/review** when an upstream AI pass was incomplete or a citation issue remains; distinguish earlier-pass notices from final decisions.
10. If the cloud model is rate-limited, choose **Local (Ollama)** in the sidebar and rerun Analyze. Local embeddings are still required for the optional semantic cross-check; their health and retrieval diagnostics are shown separately.

**Caution:** This research screening prototype only compares self-reported CV evidence. It is not a substitute for credential checks, interviews, or fair, human-reviewed hiring decisions.
