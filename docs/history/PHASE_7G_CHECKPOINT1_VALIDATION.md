# Phase 7G checkpoint 1 validation receipt (2026-10-19)

Source archive: `CV_Ranker_Phase7F2_Forensic_Source_Scope_Organized(1).zip`.

Baseline verified **before** modifications:
- 218 archive entries, including 217 source entries tracked in the old SHA manifest.
- `python -m pytest -q`: **513 passed**, using this hosted Python environment.

Integrated checkpoint **after** modifications:
- `python -m pytest -q`: **536 passed** (513 previous + 23 new).
- `python -m cv_ranker.runtime_check`: **PASS**, new build ID, unchanged assessment protocol v3, **229** tracked file hashes (updated upon this documentation receipt).
- `python -m scripts.forensic_scope_demo`: **8/8** forensic cases correct.
- `python -m evaluation.evaluate_industrial --mode fallback`: **197/200**, matched precision **100%**, recall **97.48%**, F1 **98.72%**, no credited false-positive matches, 3 missed matches.
- The new fallback benchmark `summary` JSON is **exactly identical** to the provided original Phase 7F.2 fallback summary, including ranking measures, on the unchanged dataset SHA-256 `29df6dadc386097db86de01ad233a8fde50da74ff3eac2f9432d268854ef9357`.
- The candidate-level benchmark scenarios are identical except for `warnings`: this hosted runtime does **not** have YAKE installed, so every scenario gained a visible "YAKE failed..." warning and used the original structural fallback; no result, score, decision, or ranking changed in this comparison. **These results must not be reported as a clean YAKE-normal-path confirmation**. The uploaded baseline's 513 tests also ran without YAKE available in this hosted environment.

Limitations:
- Real EmbeddingGemma 2 inference and live Qwen are not available in this container, so 23 new tests use deterministic fake embeddings; **no live semantic accuracy claim**.
- A working `embeddinggemma-2:latest` model via local Windows Ollama is still required to run the optional semantic sidecar.
- All previous synthetic benchmark labels are hand-authored; none establishes production hiring accuracy.
- This integrated archive is based on the **uploaded Phase 7F.2** version, not the newer 678-test/Phase7G64 build mentioned elsewhere. Do not overwrite a newer working directory with this older archive; use it as a reproducible integration reference or carefully cherry-pick reviewed changes.
