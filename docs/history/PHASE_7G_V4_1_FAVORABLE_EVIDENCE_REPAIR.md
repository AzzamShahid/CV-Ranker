# Phase 7G V4.1 — Favorable Evidence Recovery

This builds directly on the supplied V4 Windows edition. The frozen job requirements, source IDs, original V4 report, provider setup, EmbeddingGemma retrieval, and source-ledger tabs remain intact.

## Corrected final behavior

- **One final table:** `Found`, `Transferable`, or `Not Found`, with a concrete reason for every decision, including negative decisions. A separate `Review recommended` flag distinguishes unestablished/inconclusive evidence without creating a fourth public status.
- **Direct stated skills:** An affirmative CV skills-list statement is enough for an ordinary named skill. It is labeled self-reported, not proven professional work. Unambiguous aliases (e.g. GCP = Google Cloud) can be recognized by the source-grounded model.
- **Performed but implicitly named capabilities:** Source-based performed actions can substantiate a field even when the category words are absent. Training/evaluating a PyTorch transformer classifier can establish ML and Deep Learning; genuine evaluation and delivered AI app work are considered similarly. No cosine score is treated as proof.
- **Transferable:** Implemented functionality using another tool is retained as a separate transferable result if the exact requested technology is not evidenced. A denial or "transferable" label by itself is not enough. Denials (`without LangChain`, `has not used LangGraph professionally`, `rather than LangChain`) never award direct named-tool points.
- **Favorable merging:** Previously source-backed direct decisions survive a failed or incomplete semantic pass. Contradictory, objectively unsupported matches may be rejected by a grounded focused assessment. The raw original decision remains accessible for audit.
- **Ranking:** The visible candidate ranking uses final required Found / frozen required; preferred Found breaks ties. Transferable does not earn direct points. The unchanged primary V4 report can still be downloaded for technical comparison.
- **Evidence:** All checkpoint text, original source IDs, justification and true literal highlighted phrases are retained. Failed semantic retrieval can fall back to a focused original-CV source review using the configured model.

## Sara replay expectations

On the bundled `03_sara_functional_transfer.pdf`, source text includes `GCP Cloud Run, BigQuery`, `Trained PyTorch transformer classifiers`, implemented Haystack/Python routing, state-graph orchestration, and explicit LangChain/LangGraph professional-use denials. The focused reviewer must distinguish **Found** for Google Cloud/ML/DL (when source-grounded), **Transferable** for demonstrated comparable framework work, and **Not Found** for unsupported distinct tasks such as time-series forecasting. Model responses and runtime availability can vary; no fixed final score is hardcoded.

## Verification

```powershell
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q
.\run_ui.cmd
```

In the UI enable **AI-assisted assessment** and **Include AI capability cross-check**, upload the same JD and CV, then inspect **Rankings & evidence**, export `cv_final_evidence.json`, and compare original source checkpoints. The bundled tests include the Sara source replay, denial scoping, scoring reconciliation, and HTML-safe highlighting. The assessment is CV-grounded but not a verified credential check or automated hiring decision.
