# Supervisor demonstration — safe reproducible workflow

## Preparation (Windows)

1. Extract the release ZIP into a fresh directory, not over an older build.
2. Create the virtual environment and install `requirements.txt` using the
   steps in `README.md`; run `run_runtime_check.cmd` and `run_tests.cmd`.
3. Copy `.env.example` to `.env` and set your provider and model credentials.
   Do not show or share `.env` or applicant documents in the demo.
4. For cloud unified assessment, confirm local Ollama is running with the
   configured EmbeddingGemma model. This is a required local retrieval service.
5. Start with `run_ui.cmd` and verify the Phase 7G V4.9.32 build label.

## Two-CV and three-CV examples

- JD: `sample_data/backend_jd.txt`.
- Two synthetic CVs: `sample_data/backend_resumes/01_strong.txt` and
  `sample_data/backend_resumes/02_medium.txt`.
- Third comparison CV: `sample_data/backend_resumes/03_weak.txt`.
- First extract and review the JD. Then explicitly approve/freeze its criteria.
- Set category totals to 10/10/80, then inspect editable individual category
  shares. Increase a single relevant criterion's JD share (e.g. Python to 25%).
  Confirm its maximum overall score contribution is 20/100 points and that
  the other JD requirements rebalance automatically; do not re-extract the JD.
- Press Analyze after weight configuration. Change the allocation again after
  assessment and confirm score, rank, individual Why and comparative Why all
  update immediately without additional HTTP requests.
- Inspect the completed/unverified status, weighted leaderboard, requirement
  evidence, ranking explanations, reasoning integrity notices and exact
  original CV segment citations.
- If a candidate is unverified, confirm its partial source evidence remains
  visible without a weighted score or rank. Both the individual and overall
  Why panels must display the withheld state without an exception.
- The candidate pass now runs in the background; finished results are only
  published while their original inputs and approval remain unchanged.
- The explicit offline two/three CV regression can be demonstrated through
  `tests/test_v4930_reliability_repairs.py` without any paid API calls.
- Test the new score and reasoning contract offline with
  `tests/test_v4931_dynamic_allocation_and_reasoning.py`.

## Recovery demonstration (offline)

Use the regression tests to show a partial CV with one unresolved criterion,
then confirm only that criterion is reassessed while earlier verified rows
remain in place. Other tests exercise 429/503, truncated JSON, duplicate CVs,
and stale background results. Mocked outcomes must be labeled **offline test**,
not a successful live OpenRouter screening.

## Live-provider disclosure

Any live evaluation needs an explicit request budget, available OpenRouter
credits, local Ollama retrieval, and separate permission to send synthetic
CV text. Actual response quality and external quota recovery are not proven
by the offline tests alone. A score is never assigned while a requirement
decision remains technically unverified.
