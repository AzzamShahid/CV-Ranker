# Phase 7G V4.9.20 · Evaluator-approved JD freeze

## JD extraction now pauses for approval

The supervisor UI now follows three stages:

1. Upload or paste the employer's JD (or select a bundled demo JD) and extract candidate requirements. No resumes are assessed in this stage.
2. Review the extracted JD criteria. Edit a criterion's name, required/preferred priority, kind or original JD quotation; add or remove rows; then explicitly approve and freeze the set. Every quotation must be present in the actual JD document. Years and degree details are derived from the source text, not invented by the editor.
3. Assess candidate CVs using exactly the approved frozen criteria. Extraction does not run a second time after approval. Changes to the source JD, provider, settings or policy inputs invalidate the pending approval; edits to the frozen requirements invalidate candidate resume reuse.

The approved/edited status is recorded on the ranking report. Legacy programmatic `CVRanker.run` remains available for existing scripts; the supervisor interface enforces review before any assessment.

## Negative evidence is reviewer-readable

When a Not Found result has no LLM-cited sources but source-ledger review leads exist, the model's original explanation remains the sole visible *reason*. Reconstructed original CV citations still appear as non-scoring reviewer context. The technical source (`review_checkpoint_origin: retrieval`) is retained in structured data, without injecting implementation diagnostics such as `model omitted evidence_ids` into the explanation, checkpoint commentary, or CSV export.

Neither change adds scoring shortcuts, occupation-specific matching rules, or candidate evidence.

## Regression coverage

- Human approval, edits, added/deleted requirements, source grounding, and stale-JD invalidation.
- CV assessment consumes the approved JD without a second extraction.
- Not Found review checkpoints remain visible without internal audit wording.
- Existing candidate-scoring, source-validation and resume tests retained.
