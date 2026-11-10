# Project status — CV Ranker Supervisor Edition

Build: V4.9.32, 10 November 2026.

## Working implementation

- JD extraction, editable approval, frozen criteria, source-cited assessments,
  Required/Preferred counts, pooled JD weighting and supervisor exports.
- Cloud OpenRouter / local Ollama selection with local EmbeddingGemma evidence
  retrieval for unified assessment.
- Requirement-level Resume, cumulative cloud CV-assessment HTTP limit,
  bounded provider-aware background recovery and partial-result preservation.
- Background initial/manual candidate assessment with stale-result protection.
- Post-approval category and per-requirement scoring allocations; editing
  automatically rebalances peers and rescoring does not issue provider calls.
- Requirement/candidate/leaderboard Why explanations, traceable scoring segments,
  deterministic structural integrity checks and call-free explanation repair.
- Correct candidate-index mapping of review metadata across differing score orders.
- Six visibly sequential setup steps and null-safe Why rendering for candidates
  whose score/rank is withheld due to unverified criteria.

## Verification state

- V4.9.32 passes **1,141 offline tests**, including actual Streamlit rendering
  for two complete CVs, mixed complete/unverified CVs and all-unverified CVs.
- Streamlit's offline application harness loaded the `CV Ranker` screen with
  **zero application exceptions**. This proves initial UI rendering, not an
  authenticated provider call or complete live browser workflow.
- The packaged build's hash manifest and ZIP integrity are checked as part of
  the release verification procedure.
- Unit tests use mocks and do not prove the live provider meets its API quotas,
  response quality or latency requirements.
- Live two-CV versus three-CV behavior is **not verified** without a user-
  authorized model run. Do not claim otherwise in a supervisor demonstration.

## Known limitations / next priority

1. Streamlit's worker pool and result checkpoints are session-memory based,
   not durable across server restarts or disconnects.
2. The initial JD extraction and typing approval step remains synchronous;
   background execution covers CV evaluation after approval.
3. Cloud mode's unified evidence retrieval requires a reachable local Ollama
   installation with the configured embedding model.
4. The assessment HTTP budget excludes earlier JD-extraction calls; those
   remain an independently bounded structured-model workflow.
5. Multiple Streamlit sessions and SQLite cache concurrency require a
   production-scale stress test before unattended multi-user deployment.
6. The report JSON retains the legacy raw primary score/rank beside the
   supervisor's configurable weighted leaderboard; use weighted outputs for
   the actual displayed supervisor order. Split JD changes display only;
   individual priorities are editable within the one pooled JD group.
7. Explanation validation is structural/source-consistency checking. It cannot
   prove that every phrase of the underlying model's prose is factually true;
   original evidence and human review remain necessary.

## Safe checks

- `run_runtime_check.cmd` validates the packaged build identity and hashes.
- `run_tests.cmd` runs all offline regressions in the project's configured
  Python environment.
- `docs/DEMO_GUIDE.md` describes sample inputs and the evidence to show.
