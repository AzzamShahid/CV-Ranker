# Phase 7G V4.5 — Configured Cloud/Local models with a UI provider switch

26 October 2026 · Build: `phase7g-v4-5-env-owned-dual-provider-sidebar-2026-10-26`

## Changes

1. **Both model IDs are configured in `.env`:** `OPENROUTER_MODEL` and `OLLAMA_MODEL`. `OLLAMA_BASE_URL` also belongs in `.env`. The sidebar offers only **Cloud (OpenRouter)** and **Local (Ollama)**, with the selected model ID displayed read-only.
2. **Independent provider resolution:** `Settings(llm_provider='ollama')` always resolves `OLLAMA_MODEL`, even when the `.env` default provider is OpenRouter. Similarly, Cloud always selects `OPENROUTER_MODEL`. A missing cloud API key does not prevent a Local run.
3. **Single source of provider choice per run:** The primary JD extractor, CV assessor, optional semantic relationship LLM, and focused decision verifier share the `CVRanker` instance's resolved assessment model. EmbeddingGemma still uses the local Ollama service for retrieval under either setting.
4. **No stale result confusion:** If a user switches Cloud/Local after an analysis, the UI warns that the displayed report used the earlier provider and that Analyze must run again. The old result remains intact until then.
5. **Correct local endpoint:** The ChatOllama constructor now receives `OLLAMA_BASE_URL`. The `doctor.py --provider openrouter|ollama --live` health check selects the intended path and exercises the same StructuredLLM interface as production.

## Example `.env`

```ini
CVR_LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=YOUR_PRIVATE_KEY
OPENROUTER_MODEL=google/gemini-2.5-flash-lite
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

`CVR_LLM_PROVIDER` sets only the initial sidebar choice. Change Cloud/Local inside the UI. For Cloud, CV/JD excerpts leave the machine for the configured provider. For Local, assessment requests go to Ollama; network access may still occur only if you explicitly use a remote Ollama endpoint.

## Verification and limitations

- Mocked tests verify that Cloud calls send the exact `OPENROUTER_MODEL` ID in the API JSON payload and that Local creates ChatOllama using the `OLLAMA_MODEL` and `OLLAMA_BASE_URL` values. No real CVs, API keys, or cloud calls are used by the tests.
- A SOCKS proxy-compatible transport dependency is included because importing the Ollama/httpx client can otherwise fail on machines configured with a SOCKS proxy.
- `doctor.py --provider openrouter --live` is the explicit paid live-provider smoke check. `doctor.py --provider ollama --live` requires running Ollama and a downloaded local assessment model.
- A real OpenRouter response still depends on the user's private key, credits, chosen model's structured-output support, and the selected provider's availability. Provider failures remain visible; the engine does not silently swap to another model.
- Existing V4.4 source validation, JD/education recovery, leaderboard, and reconciled Found/Transferable/Not Found design are retained.
