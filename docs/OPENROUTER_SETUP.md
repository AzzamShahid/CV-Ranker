# Phase 7G V4.5 — Cloud / Local model selection

The ranker can send **all structured LLM calls** (JD extraction, base CV
assessment, JD decomposition, and provisional transferability assessment) to
OpenRouter. Existing YAKE, direct scoring, Pydantic evidence validation, SQLite
vector cache, and local Ollama EmbeddingGemma 2 remain unchanged.

**Privacy warning:** when enabled, the raw JD and excerpts of the CV are
transmitted off your computer to OpenRouter and the selected model provider.
Only use this with consent and an appropriate data processing policy. Never
upload real applicants to a third-party service without authorization.

## Setup (Windows PowerShell)

1. Create a restricted API key with a spending limit from
   https://openrouter.ai/settings/keys . Do not paste it into chats.
2. Install dependencies in your existing Python virtual environment:

       .\.venv\Scripts\python.exe -m pip install -r requirements.txt

3. Copy `.env.example` to `.env` in the **project root** and edit it locally:

       Copy-Item .env.example .env
       notepad .env

   Keep BOTH model names here, regardless of which provider you choose in the UI:

       CVR_LLM_PROVIDER=openrouter
       OPENROUTER_API_KEY=YOUR_PRIVATE_API_KEY
       OPENROUTER_MODEL=google/gemini-2.5-flash-lite
       OLLAMA_MODEL=qwen2.5:3b
       OLLAMA_BASE_URL=http://127.0.0.1:11434

   `.env` is ignored by Git, never included in source archives, and the key
   is suppressed from error messages. `CVR_LLM_PROVIDER` sets only the initial
   UI selection. Select **Cloud (OpenRouter)** or **Local (Ollama)** at any time
   in the sidebar; the actual model IDs come exclusively from `.env` for UI runs.
   The `OPENROUTER_MODEL` must support
   structured JSON schema output through an OpenRouter endpoint. Model costs
   and structured output support can vary by provider and time.

4. Test the configuration locally (no remote LLM call):

       .\run_runtime_check.cmd
       .\.venv\Scripts\python.exe doctor.py

5. Test a minimal remote structured call and synthetic JD/CV end-to-end run
   (uses billable tokens):

       .\.venv\Scripts\python.exe doctor.py --provider openrouter --live

6. Run the semantic retrieval pipeline and transferability evaluation:

       .\scripts\run_phase7g_shadow.cmd --decompose
       .\scripts\run_phase7g_transferability.cmd
       .\.venv\Scripts\python.exe -m scripts.phase7g_relationship_audit

## Switch to local Ollama Qwen

In the UI, select **Local (Ollama)**. The installed model must match
`OLLAMA_MODEL` in `.env` (for example, run `ollama pull qwen2.5:3b`).
No API key is required for local-only assessments. You do not need to edit
`CVR_LLM_PROVIDER` every time you switch. Check Local independently with
`doctor.py --provider ollama --live`. **Local EmbeddingGemma always uses Ollama**,
regardless of the structured assessment provider.

## Technical notes

- LLM output is validated locally using the same Pydantic source/assessment schemas.
- OpenRouter calls use `/api/v1/chat/completions`, `temperature=0`,
  `response_format=json_schema`, `provider.require_parameters=true`, and the
  original configurable context/output token budgets.
- Some model endpoints may not support strict JSON schema. The existing
  bounded fallback to JSON-object mode still validates results locally with
  Pydantic, without bypassing source evidence checks.
- If auth, billing, rate limit, or networking fails, the OpenRouter circuit
  fails closed rather than silently retrying against another model provider.
- The original fallback behavior inside the ranker remains governed by its
  existing failure handling; compare its `evaluation_mode` and warnings rather
  than assuming all results were AI-assessed.
- Shadow transferability does not modify ranking or existing scores.
- API usage incurs third-party charges; models and prompts can alter assessment
  results. Benchmark and review before any HR deployment.
