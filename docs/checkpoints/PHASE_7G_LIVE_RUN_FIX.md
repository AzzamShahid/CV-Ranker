# Phase 7G — Live-run regression fix (19 Oct 2026)

## Why this checkpoint exists

The previous 585-test shadow build passed offline tests but a real Windows run
produced 20 Qwen structured parse failures, incomplete provisional evaluations,
and corrupt query attribution in `retrieval.json`. The primary 7F.2-derived
rankings were not modified.

## What has been repaired

1. `ShadowRetriever.retrieve_by_query()` returns per-capability cosine scores
   and exact phrase hits. The integrated diagnostic now aggregates hits *only*
   within the parent JD requirement. Cosine similarity is **not** a competence score.
2. `retrieval.json` schema is now **v2**. Legacy v1 retrieval output is rejected
   by the transferability program with a regeneration instruction.
3. For actual `StructuredLLM` Qwen runs, the provisional verifier requests a
   smaller flat schema (`capabilities` with `source_ids`) instead of nested
   requirements and LLM-copied quotations. Python reconstructs authoritative
   full-span citations directly from the originally extracted CV segment.
4. Missing, duplicate, excessive, or foreign candidate source IDs cannot
   silently produce positive judgments. A positive response without citations
   is downgraded to `uncertain`, and warnings are emitted.
5. The previous strict structured response remains available to integration
   clients; all previous offline regressions still run.

## Run on Windows (separate extracted directory)

```powershell
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q
.\scripts\run_phase7g_shadow.cmd --decompose
.\scripts\run_phase7g_transferability.cmd
```

**Always rerun shadow retrieval first.** Older `retrieval.json` schema v1
contains contaminated per-requirement diagnostic flags; the fixed verifier
will refuse it. `embeddings.db` may remain cached when the model fingerprint,
texts, and preprocessing are unchanged.

The verifier still does not change existing ranking or coverage scores. Qwen
output remains a proposal subject to human/independent review. This package
was offline-tested; live Qwen behavior needs your local Windows run.

If the final script still prints NOT complete, send the updated
`outputs\phase7g_shadow\transferability.json` and terminal notices for
troubleshooting. Never use provisional relationships as verified match credit.
