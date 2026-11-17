# Windows Python 3.11 handoff — v4.9.68 prompt-first evaluation

**No native Windows qualification was performed by the source authoring environment.** Run these steps on an authorized Windows 10/11 host with Python 3.11 and separate untouched release folders. Do **not** copy private real applicant CVs, account secrets or operation databases into this test setup.

```powershell
# From a clean extraction of TextileHR v4.9.68 source ZIP:
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m cv_ranker.runtime_check
python -m pytest -q
python -m pytest -q tests/test_v4968_prompt_first_contracts.py
python -m evaluation.evaluate_supervisor --cross-domain
python -m streamlit run app.py
```

The full suite must collect all modules and run without environment-driven missing imports. Compare JD upload, review/freeze, evidence extraction, score and original source Why, two CVs, three CVs, weight-only reprojection, exports and resumed status. Confirm sources and UI columns remain consistent across save/restart. The native Windows result must be recorded separately from scripted model tests.

## Reproducible paired request-packet experiment (no model or API calls)

Extract the unmodified **v4.9.67** ZIP into `C:\Work\TextileHR-v4967` and **v4.9.68** ZIP into `C:\Work\TextileHR-v4968` (each containing `CV_Ranker_Supervisor_Edition`). From the v4.9.68 project root:

```powershell
python scripts/prompt_first_pair.py `
  --baseline 'C:\Work\TextileHR-v4967\CV_Ranker_Supervisor_Edition' `
  --candidate 'C:\Work\TextileHR-v4968\CV_Ranker_Supervisor_Edition' `
  --cases evaluation/prompt_first/development_cases.json `
  --mode packet --output prompt_ab_packet_results.json
```

It should compare 15 fictional fixed packets, check each arm's source manifest, and verify exact input/schema parity. It **does not** assess model quality. Use `docs/V4968_FICTIONAL_PRE_PROVIDER_PACKETS.json` for complete synthetic examples.

## Optional actual-model A/B (explicit local/cloud authorization required)

Local Ollama (requires locally installed model and separate provider logs):

```powershell
python scripts/prompt_first_pair.py --baseline 'C:\Work\TextileHR-v4967\CV_Ranker_Supervisor_Edition' --candidate . --mode ollama --authorize-local --request-ceiling 30 --output prompt_ab_ollama.json
```

Cloud OpenRouter: **do not execute until authorized for data transfer and budget, and only with the packaged fictional cases**:

```powershell
# Make a deliberate operator decision about cost, provider model, credentials, retention, privacy.
python scripts/prompt_first_pair.py --baseline 'C:\Work\TextileHR-v4967\CV_Ranker_Supervisor_Edition' --candidate . --mode openrouter --authorize-external-fictitious-data --request-ceiling 30 --output prompt_ab_openrouter.json
```

Record actual model ID, local/cloud versions, available cached tokens, output usage and any observed rate errors. Do not interpret the harness's estimated token counts as billed token usage. The `--request-ceiling` applies **per arm**, not across both arms. Running the same worker with an unchanged source prompt may still cost model requests.

## Rollback and migration

Preserve v4.9.67/v53 and saved reports as historical. This build changes prompt behavior and explicitly bumps the assessment protocol to v54; re-assess candidates under v54 rather than silently relabeling older verified results. Weight changes and employer display branding do not require new model calls when reprojecting a compatible source assessment. Restore previous release by returning to its untouched ZIP and the corresponding historical report, not by mutating a v54 report back to v53.
