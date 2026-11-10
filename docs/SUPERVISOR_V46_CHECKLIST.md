# Supervisor demonstration checklist — Phase 7G V4.6

1. Extract the new ZIP to a **new folder**. Do not overwrite or mix with V4.5.
2. Create `.venv`, install requirements, copy `.env.example` to the **private** `.env` and set Cloud and Local model IDs there. Set a real OpenRouter key if Cloud will be used. The sidebar changes only provider (`Cloud` or `Local`).
3. Verify `ollama list` includes the configured embedding model; run `python -m scripts.phase7g_embedding_preflight`. Cloud assessment with cross-check ON still needs local Ollama.
4. Run `run_runtime_check.cmd`, `python -m pytest -q` and `doctor.py --provider ollama --live`; check `doctor.py --provider openrouter --live` only if Cloud credentials and quota are available.
5. For CV screening, upload the exact final JD. Required years/degree can only appear in Required when the uploaded JD says so. Check that the frozen JD list includes them before trusting the final scores.
6. Upload fictional Sara and Farhan test CVs. Sara's LLM-related four years are expected to satisfy a three-year **relevant AI/LLM** minimum; Farhan's two years and four months must not. Sara's reported BS Computer Science must satisfy a *JD-explicit* Computer Science bachelor's criterion.
7. Verify the leaderboard sorts all candidates highest to lowest, with `Required Found/Total`, `Preferred Found/Total`, and independent `Transferable` count. No extra preferred percentage or transferable points are awarded.
8. Open a candidate and review source-cited **Found / Transferable / Not Found** outcomes and explanations. Check negations and explicitly stated gaps. Reproduce the same outcome after switching provider and rerunning only when the provider is healthy.
9. Check `04 Technical details` for local semantic retrieval completed counts. If OpenRouter rate limits, the cloud interpretation is incomplete; the retrieval and baseline should remain visible rather than claiming a negative match.
10. Do not present the app as an automated hire/reject authority. The prototype evaluates CV-reported evidence, not verified work history or educational credentials. Only authorized CVs should be sent to external providers.
