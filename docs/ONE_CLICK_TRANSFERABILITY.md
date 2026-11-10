# One-click candidate ranking + transferable-capability review

## What changed

The **Analyze and rank candidates** action can now execute two independent paths for **the same uploaded JD and CV files**:

1. **Primary ranking (unchanged):** JD extraction, YAKE, configured OpenRouter/Ollama assessment, original-source citation checks and deterministic required/preferred scoring. This result is saved first.
2. **Optional read-only Phase 7G review:** Dynamic JD search plan, local Ollama EmbeddingGemma 2 dense/exact retrieval, source-audited configured-LLM proposed relationships. It runs before uploaded temporary files are removed. It never changes the primary result.

Both paths use the existing `CVRanker` methods. A new `cv_ranker/ui/semantic_workflow.py` is orchestration and presentation only, **not** a second ranking algorithm.

## Demo steps

1. Set `CVR_LLM_PROVIDER=openrouter`, your private `OPENROUTER_API_KEY`, and `OPENROUTER_MODEL` in a local `.env` file.
2. Start local Ollama and install `embeddinggemma-2:latest` (e.g. `ollama pull embeddinggemma-2:latest`). Only embeddings use Ollama; the configured LLM handles the assessments.
3. Run `run_ui.cmd`. In the sidebar, turn on **AI-assisted assessment** and **Show potential transferable skills** (on by default when AI-assisted assessment is enabled).
4. Upload a JD and resumes, or launch the **Transferability** synthetic sample. Its JD names FastAPI, PostgreSQL and Redis while one candidate demonstrates analogous functionality using Flask, MySQL and Memcached. The LLM may still return `related_only` or `uncertain`; no positive classification is guaranteed. Click **Analyze and rank candidates** once.
5. In **Rankings & evidence**, inspect the original score/rank, optional **Transferable (review)** column, matching/missing requirements, and **Potential transferable skills** for each selected candidate. No separate terminal script or JSON upload is needed.
6. The filter defaults to **Transferable first**. Use **All** to inspect the full provisional model assessment, including direct and uncertain labels.

## Important limitations

- The optional stage may make many extra remote LLM calls (roughly candidate × frozen requirement for the current implementation) and can take noticeably longer and incur additional API charges.
- EmbeddingGemma 2 requires a running **local** Ollama server. If it is unavailable, the original ranking still completes; the app displays an explicit semantic-unavailable warning. Never reinterpret a failed semantic stage as an unsupported skill.
- If the original model's full primary ranking cannot complete, that is reported separately. Failed or ambiguous semantic results do **not** earn credit.
- Single-word skill JDs often have *zero transferable proposals*. To demonstrate functional transferability, use a JD describing tasks and functionality and CVs showing the same functions with different tools. Decomposition and relationship proposals are experimental, not independent proofs of skills.
- A self-reported skill under Skills can satisfy an ordinary named-skill JD requirement in the baseline. An LLM proposal may disagree; the UI preserves both with distinct labels and never silently overwrites the baseline.
- Every transferability relationship is **provisional and requires human review**, including `direct`. Neither cosine nor AI relationships increase a candidate's score.
- The UI holds semantic reports (including copied CV source text) only in its Streamlit session; it does not export them by default. SQLite caches normalized embeddings only under `outputs/ui_semantic_cache.db`, which is excluded from the ZIP via `outputs/` in `.gitignore`. Protect or delete local caches according to your retention policy.
- OpenRouter sends CV and JD text to external services. Only process applicant material for which you have authorization. Keep `.env` private.

## Rollback

Uncheck **Show potential transferable skills**. The app uses the existing scoring pipeline without EmbeddingGemma retrieval or transferability model calls.

## Adaptive Phase 7G transferability batching

The current compact-output provider groups up to three independent frozen parent requirements for a single candidate in one structured call. Its response includes independent per-requirement ID and candidate-specific citations. If a batch exceeds the prompt budget, is malformed, or fails, it is recursively split. Missing or invalid parent decisions are individually retried, with uncertain/audit-failed status instead of invented positives on final failure. A focused optional second look remains separately scoped for certain named-tool gaps.

Run `scripts\run_phase7g_transferability.cmd --batch-size 3` (default) or `--batch-size 1` to return to original one-parent mode. Batch size is a maximum, not a guarantee: model context capacity and retrieval length may force smaller groups. New `batching` stats in `transferability.json` show initial batch calls, single calls, splits, retries and successfully processed batches. Additional model calls still depend on the number of focused reviews and provider-level retries.
