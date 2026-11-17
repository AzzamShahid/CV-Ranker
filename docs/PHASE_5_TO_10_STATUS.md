# Phases 5–10: implementation and verification status

Snapshot: **12 November 2026** · Software version **4.9.57** · Protocol **v43**

**Meaning of status labels:** `Implemented/tested offline` applies only to the specific code behavior named. `Partial` means significant requirements remain. `Unverified live` means the effect on real CV classification has not been measured using actual Ollama/OpenRouter responses.

| Plan phase | Current work | Status | Remaining acceptance criteria |
|---|---|---|---|
| 5 — JD completeness | v4.9.54 explicit qualification recovery retained; regression covers long QA JD (7 required, 3 preferred), avoids adding Benefits | **Regression retained, not universal guarantee** | More narrative/JD department variants; independently review multi-clause requirement breakdowns |
| 6 — Model attempts/costs | bounded successful identical-prompt replay in unified engine; usage counter and no failed-response caching | **Partial** | Test real provider behavior; review repeat invalid-citation failures, prompt batching, request traces and costs over multiple runs |
| 7 — Dynamic weights | 9 Required + 7 Preferred share pooled JD category; changing weights requires no inference, Transferable stays 0 | **Existing contract regression-tested** | Compare Streamlit/CSV/JSON output consistency and under-specified inputs on full installed environment |
| 8 — Evidence transparency | model-rejected source IDs displayed separately from retrieved review leads | **Partial** | Rich per-attempt failure history, accepted proof and reviewer export parity; visual UI check in Windows |
| 9 — Local edit integrity | assessment logic SHA-256 fingerprint invalidates stale reuse without local hash start block | **Implemented/tested offline** | Test Windows Streamlit reruns after actual source change, remote strict mode and meaningful policy input updates |
| 10 — Cross-domain testing | synthetic textile, QA/CI, customer-service retrieval; dated-experience positive + unrelated-work negative; QA JD completeness and scoring pooling | **Partial; no live accuracy benchmark** | Full Windows suite + replay of Adeel and Mariam original PDFs/approved JDs; repeated unseen multi-department benchmark with measured precision, recall and costs |

## Specific result-quality objective

Improve what the LLM actually *receives and can cite*, not the percentage shown by disguising failures. Keep the original JD frozen; prevent unrelated activities from proving named requirements; avoid rejecting genuine completed work due to section labels or overly literal summaries. Continue showing provisional results if technical checks are incomplete, with zero invented credits.

## Execution environment and test limits

The source archive was built in a container with Python 3.13 and missing Streamlit/LangChain/Ollama runtime dependencies. The package index was unreachable during installation. Therefore, no claim of the full Windows test suite passing and **no claim of improved live applicant accuracy** may be made. The available dependency-independent tests and exact counts are recorded at packaging time below.

**Offline verification:** `python -m compileall -q cv_ranker tests` succeeded; `python -m pytest -q tests/test_v4957_retrieval_cache_and_transparency.py` **20 passed**. The larger feasible dependency-independent pytest subset passed **1,274 tests** with **22 tests deselected** due missing optional runtime dependencies and **10 test modules omitted from collection** because of missing `streamlit`/`langchain_*` imports. `CVR_STRICT_SOURCE_HASHES=1 python -m cv_ranker.runtime_check` passed, and `python -m scripts.production_preflight` passed for local supervised mode. **This is not a full-suite pass.**

## Windows verification steps

```powershell
# Run in a NEW extraction of v4.9.57
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# configure private .env based on .env.example; do not share keys
.\run_runtime_check.cmd
.\run_tests.cmd
.\run_ui.cmd
```

Then re-extract and approve the exact JD, configure weights and evaluate the same candidate CVs in a fresh run. Check source decisions and warnings, not just the score. Save the run diagnostic and one genuinely wrong criterion/evidence pair for targeted regression improvements. For comparative accuracy, label outcomes manually before changing code and use multiple roles and CVs.

## Security and source neutrality

- No named candidate, employer, tool equivalence, industry or requirement ID is hardcoded into **matching decisions**. Named examples appear only in regression fixtures and documentation.
- The new lexical ranking signal is not a semantic proof mechanism and never converts Transferable/Not Found into Found.
- No private CVs, `.env`, passwords, API keys, recovery-signing keys or user-generated assessment exports belong in the release ZIP.
