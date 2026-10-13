# Supervisor demo script (5 minutes)

1. **Show clean project folders.** `cv_ranker/` is the production engine, `evaluation/` the experiments, `tests/` the regression tests, and `docs/` the explanation.
2. **Demonstrate environment readiness.** Run `run_runtime_check.cmd` then `python doctor.py --live` using the project's `.venv`; show `READY` if Ollama is accessible.
3. **Run the UI.** Double-click `run_ui.cmd` and open http://localhost:8501. Use Backend demo (or upload one JD and 3 sample CVs).
4. **Explain stages.** YAKE only suggests keywords; Qwen interprets JD requirements and CV evidence; Python freezes IDs, validates source pointers and calculates scores.
5. **Open a ranked candidate.** Point to required-matches score, preferred coverage, matched/not-matched/uncertain, and an `S###` evidence line.
6. **Be transparent about limitations.** Current 21-case diagnostic benchmark is 76.19% (batch 20) or 80.95% (batch 3); mixed outcomes prevent claiming pure-Qwen accuracy. No verifier, embeddings or transferable-skill credit.

Likely question: **Why use AI if Python matches exact words?** Because semantics (e.g., abbreviations, paraphrases and quantified experience) require more than exact string matching; Python deliberately handles deterministic source safety and scoring. Current Qwen can still miss or misclassify these cases; the benchmark demonstrates this openly.
