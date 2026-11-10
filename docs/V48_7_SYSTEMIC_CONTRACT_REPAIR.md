# Phase 7G V4.8.7 — Systemic reliability and scoring-contract repair

28 October 2026. This release replaces the brittle V4.8.6 validation
shortcuts. It is *not* a claim that an LLM's judgment is automatically correct;
it separates technically invalid responses from negative skill findings.

## Contracts

1. **Complete frozen JD**: exactly one unique requirement ID and decision per
   frozen item. Extra model IDs, missing IDs, contradictory or identical
   duplicates, invalid citations and invented quotes trigger at most **one
   grouped correction** for the affected batch. No model can add, drop, or
   rename a JD criterion.
2. **Technical errors are not nonmatches**: if one correction still does not
   yield valid source-cited assessment, the item becomes `Unverified` with
   `assessment_state=unverified`. Known Found/Transferable/Not Found peers
   remain inspectable; the candidate's score and rank are withheld until all
   criteria receive valid decisions. Old reports retain their original
   `verified` default when reloaded.
3. **Semantic judgment belongs to the assessment model**, subject to frozen
   JD and source provenance; Python never promotes a related phrase to Found
   merely because multiple JD words or an arbitrary completed-work verb
   overlap. Invalid optional quote metadata may be cleared automatically only
   if the cited CV passage *literally* contains the JD item. Other mistakes
   require model correction and can remain Unverified.
4. **Source discovery is not proof**: EmbeddingGemma retrieval is augmented
   with source-ledger literal/negation inclusion. Denials and positive claims
   remain separate after PDF bullet normalization; supporting citations must
   still be verified. No BM25, model alias dictionary, industry-specific skill
   mapping or cosine similarity scores enter the final decision.
5. **Transferability is not direct credit**: a model-proposed functional
   transfer needs cited actual work, not a degree label, title, speculation,
   denial alone or copied JD. A named-tool denial can coexist with separately
   performed alternative work. No extra score point is granted.
6. **Same ranking everywhere**: backend, UI, ranking CSV and reports use
   primary score, then preferred coverage to break ties, then stable names.
   Equal primary and preferred percentages share a rank. Unverified or failed
   candidates have no rank and no fabricated 0% score.
7. **Truthful display**: candidate-facing rows show Unverified, including
   missing assessments after provider failure; source checkpoint explanations
   are clearly labelled as *whole-criterion* reasoning, not fabricated
   per-segment assertions. Only fully scored candidates count as completed.

## API call budget

Per 2048-token completion, each group contains at most **7 requirements**,
independent of context capacity; an 18-item JD therefore normally needs
**3 grouped assessment calls per CV** (vs 2 in V4.8.6). A group with invalid
rows gets **at most one additional grouped correction**, so at most **6
logical candidate-assessment calls** for 18 criteria. Earlier provider-level
retries for HTTP/network/JSON failures still apply and are capped by
`llm_retries` (default 2); OpenRouter's pacing and rate-limit circuit remain.
JD extraction/typing calls are separate and unchanged by these limits.
Evidence retrieval is entirely local and cannot incur OpenRouter charges.
Batch splitting prefers preserving three or more source leads per criterion
to silently reducing evidence to just one lead.

## Testing and deployment gate

Run `run_tests.cmd`, `run_runtime_check.cmd` and `doctor.py --live` using the
intended provider/model on the target Windows environment. `doctor.py` without
`--live` now says local checks passed but live assessment was not tested.
`--live` uses *unified=True* and therefore also requires local EmbeddingGemma
even when OpenRouter is selected. Do not interpret 100% mocked tests as
measured model quality. Run a **blind, manually labelled, multi-department**
holdout benchmark on the actual installed models before any production
recruiting decision support. Compare source-level false positives, false
negatives, invalid-row rate, rankings and paid request totals.

New adversarial tests cover clinical, finance, manufacturing, supply-chain,
negations plus alternative work, fake quotes, missing/extra/duplicate rows,
incomplete score suppression, API batch limits, and PDF-font bullet glyphs.

## Out of scope

No new similarity threshold, profession-specific synonyms, cloud provider,
third-party vector database, employment-gap weighting, subjective competency
formula, or automatic hiring decisions. Source statements and degrees are
self-reported and not externally authenticated. A successful syntax/contract
check cannot guarantee that a live LLM correctly understands each JD clause;
the source-backed holdout evaluation is required before production use.
