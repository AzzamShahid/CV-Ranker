# Phase 7G V4.9.19 — Reviewer-visible Not Found checkpoints

Build `phase7g-v4-9-19-negative-evidence-checkpoints-2026-10-29`.
Assessment protocol version 20. No changes to scoring or the frozen JD.

## Why the previous change was insufficient

V4.9.18 corrected the prompt and allowed negative source citations in its
structured schema. However, `evidence_ids` remained an optional empty list.
A model could still disregard the instruction and respond `not_found` with
`evidence_ids: []`, leaving the supervisor no source to inspect even though
the CV ledger contained an explicit denial or related claim.

## Enforced evidence contract

1. The first and independent model prompts explicitly demand original source
   IDs for Not Found when any relevant source exists, including explicit
   denials, claimed adjacent skills and insufficient performed work. Their
   explanation must say why these checkpoints fail the exact JD.
2. When a verified Not Found arrives with zero citations, the final evidence
   boundary retains up to three permissible original CV passages: literal JD
   mentions first (including negations), followed by positive skills-list
   retrieval leads and the nearest evidence-retrieval lead. If the CV contains
   no eligible sources, the evidence list stays empty.
3. These fallback source IDs are **not represented as model citations**.
   The reason and supervisor label state that the model omitted IDs and the
   original snippets are uncredited reviewer leads. No segment text is
   generated, rewritten or trusted outside the original ledger.
4. The assessment status, score, required/preferred matched counts,
   transferability, scope constraints and negation/learning-only protections
   remain unchanged. A related passage does not become a Found point merely
   because it is displayed.

## Verification

Tests cover model-omitted negative citations, explicit denials, unrelated
retrieval leads, forbidden/non-candidate segments, correctly cited negatives,
and explicit professional-experience requirements. Live OpenRouter/Gemini
verification is still a separate requirement for deployed model quality.
