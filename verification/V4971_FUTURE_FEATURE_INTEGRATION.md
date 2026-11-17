# Stable extension boundaries for a future TextileHR feature

The future feature is **unspecified** and has not been implemented.

1. **Frozen employer JD:** consume approved, versioned requirements, alternatives, modalities, date and employer meaning; do not silently change them in candidate scoring.
2. **Original candidate evidence:** use candidate-scoped source ledgers, exact segment IDs/sections/text and document-coverage indicators; never validate a citation only against an LLM's own output row.
3. **Assessment operation:** declare semantic input identity and submit eligible work to one bounded, restart-aware dispatcher. Use typed processing failures, no parallel unbounded retry loop.
4. **Decision publication:** completed results must pass `reconcile_final_assessments` (or future canonical interface) and original provenance validation, and be persisted with protocol/prompt/schema/validator identity before scoring.
5. **Score projection:** Found earns configured points; Transferable contributes zero direct points; Not Found zero. Incomplete means no official score or rank. Existing pooled versus explicit weighted-split policy is unchanged.
6. **UI/exports:** read the published result record and project it consistently into Why, counts, CSV/JSON/ZIP, saved reports and view filters. Never interpret null as Not Found.

When proposing a new feature, explicitly tag it as **semantic** (invalidates source assessment and advances protocol), **scoring** (recompute weights only, zero model calls), or **presentation-only** (no assessment invalidation). Add positive and adverse tests for changed boundaries; preserve historical versions and do not expose private evidence or keys.

**Known current limitation:** The legacy compatibility fields have not been physically eliminated everywhere, and native Windows/UI/provider qualification is pending. A future feature must not treat an RC release as a proven, fully clean boundary.
