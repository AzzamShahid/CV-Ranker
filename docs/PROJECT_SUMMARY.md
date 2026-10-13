# CV Ranker — Supervisor Project Summary

**Objective:** Rank resumes fairly against a single job description using clear, source-linked requirement decisions and deterministic scores.

**Implementation:** Python 3.11; YAKE for JD phrase hints; local Qwen2.5:3b through Ollama/LangChain for requirement interpretation and CV assessment; Pydantic for structured responses; PyMuPDF/python-docx for extraction; Streamlit for UI.

## Working prototype

- Accept a JD and multiple resumes (TXT, MD, PDF or DOCX).
- Freeze the JD requirements so all candidates share the same denominator.
- Return `matched`, `not_matched`, or `uncertain` for each requirement.
- Attach source segment IDs and full resume evidence lines.
- Calculate the required-match percentage in Python and rank candidates deterministically.
- Supply trace logs, unit tests, build integrity and local live-health checks.

## Current results and research limitations

Latest **user-run** Windows health check on the pre-reorganization code: **READY**, with the local Ollama model correctly completing the small 1/1 live contract.

A fixed 21-labelled-case *assessment-only diagnostic benchmark* was run three times at each batch size. Batch 20: **16/21 (76.19%)**. Batch 3: **17/21 (80.95%)**. Both groups included Python recovery and mixed assessment modes, and **neither had a clean Qwen-only run**. This does **not** establish general CV ranking accuracy or production safety.

Known semantic issues include missing abbreviations and incorrect matches to unrelated technologies. These are acknowledged future work, not hidden behind a 99% accuracy claim. No human hiring decision should rely solely on the prototype.

## Scope agreed for supervisor review

**Included:** YAKE, a single local LLM, source-grounded candidate evidence, Python ranking, multi-resume demo, architecture explanation and tests. **Deferred/excluded:** embeddings, vector similarity, transferable-skill scoring, semantic alias dictionaries, and a separate verifier.

## Live presentation (quick order)

1. `run_runtime_check.cmd`
2. `.venv\Scripts\python.exe doctor.py --live`
3. `run_ui.cmd` (open http://localhost:8501)
4. Choose the bundled Backend demo and open an evidence panel.
5. Refer to `docs/ARCHITECTURE.md` and `docs/TECHNICAL_DECISIONS.md` for questions.
