# CV Ranker Supervisor Edition — v4.9.57: retrieval calibration and assessment reuse

Date: **12 November 2026**  
Build: `phase7g-v4-9-57-domain-neutral-retrieval-evidence-2026-11-12`  
Assessment protocol: `segment_ids_semantic_llm` **v43**  
Base: **v4.9.56**, including its Windows portability test fix

## Purpose

Continue the Phase 5–10 maintenance plan with changes intended to improve **real JD-to-CV evidence selection**, without hardcoded occupations, technologies, candidate records, scoring overrides or automatically accepted skill equivalences. The preceding v4.9.56 Phase 1–4 source safeguards and provisional scoring remain intact.

## Implemented changes

1. **More relevant evidence at the front of the retrieval shortlist.** `cv_ranker/retrieval_priorities.py` assigns a modest, domain-neutral lexical ordering to *original retrieved passages* based on informative words in the **uploaded and approved JD**. It is used in `cv_ranker/unified.py` to prioritize focused work evidence before generic performed-work leads. Existing semantic candidates remain in the shortlist, even if they share no literal words, so genuine paraphrases can still be evaluated by the model. This code **never awards points**, decides Found, or adds aliases.
2. **Nonstandard source headings.** `cv_ranker/segments.py` recognizes general headers such as `Experience Highlights`, `Relevant Work Experience` and `Project Experience`. The original CV source text and source IDs are preserved. Heading detection remains heuristic and is not a complete document-layout parser.
3. **Better corroborated experience interpretation.** `cv_ranker/experience_validation.py` no longer demands every word of a longer generic JD subject to appear in the candidate's narrative summary when dated qualifying roles and original corroborating duties support the model's proposed match. The check still requires source-backed duration and role responsibilities; unrelated employment still cannot earn specialized professional experience credit.
4. **Skip genuinely redundant successful model calls.** `cv_ranker/llm.py` supports a bounded **instance-local** successful-structured-response replay keyed to the *exact* provider, model, schema, system prompt and user prompt. It is enabled only by the unified candidate assessment engine, not in standalone LLM adapters. Failed, malformed, incomplete or differently prompted requests are not cached. The pipeline records `validated_identical_prompt_reuses`; this is an efficiency guard, not a promise to eliminate all retries.
5. **Expose rejected model citation IDs.** `cv_ranker/unified.py` records which source IDs were proposed for rows that failed source validation. `cv_ranker/ui/dashboard.py` distinguishes these IDs from *retrieved human-review leads*. This helps isolate retrieval failures from model misjudgments, without displaying review suggestions as proven qualifications.
6. **Local code changes invalidate old assessment reuse.** `cv_ranker/resume.py` includes the bytes of assessment-related modules in a SHA-256 assessment-context identity. This prevents editing substantive validation or ranking code from silently reusing old in-session decisions. The local-development startup remains editable: this is **not** an application-blocking release-hash mismatch. Restart the Streamlit process after editing Python files.
7. **Additional offline regression coverage.** New tests use source passages from **textile manufacturing**, **QA/CI automation**, **operations/customer support**, and contrasting completed vs. unrelated experience. The narrative QA JD remains 7 Required + 3 Preferred; the combined Required/Preferred scoring pool and zero-point Transferable policy remain unchanged.

## What is NOT claimed as completed

- This is **not** an independently measured improvement in real-model accuracy. No live Ollama or OpenRouter assessment has been run in the development container.
- Improvements to every possible mixed AND/OR JD, academic degree ambiguity, tenure interpretation, or CV PDF heading are **not complete**; the safeguards remain conservative where source evidence is insufficient.
- Exact replay of successful prompts reduces some duplicate requests, but it does not solve **all** recovery loops, provider rate limits, malformed response repairs, or full crash-durable progress persistence.
- Retrieved source overlap is a lead-ranking signal, **not verified proof**. In particular, Kubernetes operations alone must never automatically prove AWS IAM, and a generic service restoration must never automatically prove a named Terraform-module requirement.
- The v4.9.56 provisional-ranking contract remains: unresolved requirements are visible with no invented credit, and a provisional leaderboard position is **not** a fully verified hiring decision.
- A full Windows and live-provider end-to-end assessment is still required before claiming production-readiness or accuracy improvements.

## Verification status

The project was compiled with `python -m compileall -q cv_ranker tests`, and new focused tests passed. The development container has Python 3.13 and pytest/pydantic, but lacks `streamlit`, `langchain_core`, `langchain_ollama` and `yake`. Dependency installation could not reach the package index, so the full Streamlit/LangChain-dependent suite **could not run here**. A large dependency-independent regression subset was exercised; exact counts are recorded in `docs/PHASE_5_TO_10_STATUS.md`.

**Required Windows acceptance:** On the user's Windows Python 3.11 machine, install requirements, run `run_runtime_check.cmd`, `run_tests.cmd` and `run_ui.cmd`, and check the same approved JD and CVs against v4.9.56 using a fresh assessment. For a meaningful result-quality check, record required/preferred counts, accepted/Transferable/Not Found classifications, actual source IDs and snippets, provisional coverage, model attempts/tokens/cost and reviewer corrections. No cloud charges are needed for the offline tests; live OpenRouter calls may cost money.

## Compatibility / safety

- Use a **new extracted folder**; preserve existing private `.env`/saved CV documents separately and do **not** include them in a shared source ZIP.
- v4.9.57 uses **protocol 43** because changes to retrieval and experience assessment invalidate v42 model judgments. Start a new assessment rather than claiming that a restored v42 checkpoint was evaluated by the improved engine.
- Only source-backed **Found** earns direct points. **Transferable** is separately displayed at **zero** points; no scoring-policy change was made.
- The original Windows symlink and Unix permission-bit portability test correction is carried forward.
- Keep Ollama and the configured embedding model running even if an OpenRouter LLM is selected. Applicant CV excerpts sent to cloud models are private data; handle them in accordance with organizational approval.
