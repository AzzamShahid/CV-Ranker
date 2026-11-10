# Phase 7G — Use already-installed EmbeddingGemma 2 latest

This checkpoint changes only the DEFAULT embedding model tag from `embeddinggemma-2:270m` to `embeddinggemma-2:latest` in the existing read-only Phase 7G shadow integration. The original Phase 7F.2 scoring, YAKE, Qwen, fallback, JSON ranking and assessment protocol remain unchanged.

## Important: `ollama list` alone is not runtime verification

The user reported `embeddinggemma-2:latest` installed (1.3 GB). Some Ollama versions on Windows could store EmbeddingGemma 2 but did not support the relevant runtime/model architecture. Execute a real embedding request first; no separate model pull is needed.

From **the project root** (not `C:\Windows\System32`):

```powershell
ollama --version
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q
.\scripts\run_phase7g_embedding_preflight.cmd
```

On success, the preflight prints `PASS`, vector dimensions and a finite cosine similarity for the configured local model. It does NOT certify model retrieval accuracy or verify transferability.

Then run the shadow retrieval:

```powershell
.\scripts\run_phase7g_shadow.cmd --no-llm
```

For a live Qwen+YAKE ranking pass, omit `--no-llm`, provided `qwen2.5:3b` is also installed.

```powershell
.\scripts\run_phase7g_shadow.cmd
```

The model tag can still be overridden with `--embedding-model TAG`; native dimensions remain the default. Cache keys include the model digest and selected dimension; vectors from older models won't be mistaken for vectors from the installed latest model.

The shadow retrieval writes a separate source-text diagnostic JSON file. Treat its content and the SQLite cache as sensitive CV data. Shadow search never changes rank positions or matching decisions.

If preflight returns `MLX` or `unknown model architecture`, this is an Ollama runtime compatibility issue. Upgrade a supported Ollama Windows release / check model formats before relying on it; do not assume a locally listed model is runnable.
