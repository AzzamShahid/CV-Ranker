# Phase 7G — Audited Provisional Transferability Proposals

## What this checkpoint actually implements

- `cv_ranker/semantic/transferability.py` takes the **existing saved ranking and shadow retrieval report**. It reopens the original CV, resegments it using the existing source parser, rechecks candidate identities, and verifies that retrieved segment IDs/text still correspond exactly to admitted original CV segments.
- Qwen receives one frozen parent JD requirement at a time, with its proposed explicit sub-capabilities (or the preserved unsplit requirement), typed JD constraints and original retrieved CV evidence. The live Qwen pathway now uses a **compact flat capability decision schema**, and Python constructs full original citations from the returned source segment IDs.
- Every `direct` / `transferable` proposal requires valid source IDs; Python reopens the real resume to attach the **unaltered original segment quotations**. Invalid or missing citations fail **closed to `uncertain`**, rather than being treated as verified skill evidence.
- Retrieval shortage, large evidence sets, context overflow and model failures are visible as `incomplete`/`uncertain` outcomes. Neither absence in top-k nor cosine similarity determines candidate competence.
- `requires_human_review=true` and `independent_semantic_verification=false` on every judgment. **No automatic verification or transferable percentage is generated here.** The existing primary score/rank and `score_verified_functional_coverage` remain unchanged.
- Does not add BM25, cross-encoder reranking, embeddings dimension changes, or a skill equivalence dictionary. YAKE remains in the existing JD workflow.

## Windows commands

First, generate fresh **v2** semantic retrieval including live JD decomposition. **Do not reuse v1 JSON from the broken build:**

```powershell
.\scripts\run_phase7g_shadow.cmd --decompose
```

Then assess the saved evidence (does not rerun embedding or original ranking):

```powershell
.\scripts\run_phase7g_transferability.cmd
```

Output: `outputs\phase7g_shadow\transferability.json`. A process exit code of 3 means some parent/candidate proposals need review, not that the original ranking failed. The JSON contains private resume content/quotations. Keep it secured.

## Interpretation

The results show which source snippets Qwen *proposes* directly or transferably demonstrate JD functionality. A citation audit establishes that Qwen's quote exists in the original candidate's CV; **it does not independently establish semantic correctness**. Review model-proposed JD splits, negative/contradictory context, qualifications, explicit tool constraints, and meaningful role/project context before generating independently adjudicated coverage.

## Limits / next work

- This stage performs one Qwen request per candidate/parent requirement and may cost substantial inference time for large sets; batching and caching these Qwen results can follow after quality is measured.
- The stage is deliberately shadow-only. Build a controlled human-adjudication workflow and detailed role/project context restoration before trusting transferred functional capability as an input to final coverage scoring.
- No claim of live quality or industrial-level ranking accuracy is made without benchmarked human-reviewed examples.
