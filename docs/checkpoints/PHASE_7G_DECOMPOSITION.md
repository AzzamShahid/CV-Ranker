# Phase 7G Checkpoint — Source-Anchored Dynamic JD Decomposition

## What actually changed

- Added `cv_ranker/semantic/decomposition.py`: injectable structured-Qwen decomposition with Pydantic models and exact, parent-scoped JD quote validation.
- All frozen requirements stay intact as primary search queries. Proposed sub-capabilities add only *retrieval* queries; they are **not verified requirements**, and cannot alter the scoring denominator.
- Every generated sub-capability is marked `requires_human_review=true`, whether labelled `explicit` or `search_hint` by the model. Only validated/cited evidence assessed in a later stage may contribute to coverage.
- Typed degree, certification, license, experience, eligibility, complex and alternative requirements remain unsplit; duration and disjunction text is protected even when typing missed it.
- Invalid/missing/duplicate IDs or out-of-source quotes fail back to original queries, with `complete=false` and visible warnings.
- Added optional `--decompose` to the existing shadow command. The default `--no-llm` workflow and legacy ranking are unchanged.
- Retrieval results include `matched_query_ids` for each candidate hit, providing the links needed for later capability-level verification.

## Run on Windows

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m scripts.phase7g_decomposition_demo
.\scripts\run_phase7g_shadow.cmd --decompose
```

`--decompose` **requires the configured Qwen model** and calls it after the original ranking run. Do not combine with `--no-llm`. The command uses `sample_data/backend_jd.txt` and `sample_data/backend_resumes` by default; see the Python CLI for custom document paths.

Existing 7G command remains valid:

```powershell
.\scripts\run_phase7g_shadow.cmd --no-llm
```

Check `outputs/phase7g_shadow/retrieval.json`: `decomposition_enabled`, `decomposition_complete`, `capability_search_plan`, plus `candidates[].hits_by_requirement[].matched_query_ids`. This file contains private CV evidence. Treat it as sensitive.

## Limitations and the next checkpoint

- The local test suite uses mock LLM/embedding fixtures; Qwen-generated functional decomposition on the user's Ollama installation has **not** been tested here.
- A plausible sub-capability is not proof that the JD requires it. The model-produced `origin` and `requires_human_review` fields are explicit reminders to review the proposal.
- The verification layer still needs to analyze original CV statements with relevant role/project context, human-reviewed JD decomposition, constraints, and provenance. Only then should downstream `score_verified_capability_coverage` be called with independently verified judgments.
- This release **does not** introduce transferable credit or change rankings. No BM25, cross-encoder or cosine threshold is used as hiring score.
