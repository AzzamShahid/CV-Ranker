# Phase 7G V4.9.37 — Source-ID-first independent verification

## Live diagnostic supplied by the user

The affected frozen criterion was `R008 · LLM integrations` for the bundled
Bilal CV, not `Model evaluation` as in a previous, different JD snapshot.
The user's exact source/validation notices identified:

1. Twice, `R008: matched_term was not present in the cited source segment.`
2. After grouped correction, the criterion remained Unverified.
3. The final independent model response was rejected because its written
   `proof_excerpt` was not a contiguous quotation of a cited original passage.

The actual extracted source passages include:

- `S010` (skills): `LangChain, LangGraph, hosted LLM API integrations, tool-`
- `S019` (experience): `Architected an LLM-enabled document review service
  using Python, LangChain, LangGraph, retrieval, and human approval checkpoints.`

These are original CV review passages, not automatically accepted skills.
Their sufficiency for the frozen JD remains a source-grounded model judgment.

## Root cause

Two OPTIONAL model-written presentation strings had become technical vetoes.
First, the grouped assessment could cite a genuine original segment but write
a shortened/nonexistent `matched_term` (e.g. dropping `API` from a phrase).
Second, an independent reviewer could reason about a genuine original segment
but paraphrase its `proof_excerpt` and be rejected for not repeating the
extraction word for word. The pipeline retried the first problem with the same
model/schema and then repeated the second validation failure, withholding
the candidate rank even though the cited sources existed.

## Changes

- When a first-stage decision is invalid **only** due to a model-created
  `matched_term` highlight and its original source IDs are admissible,
  immediately queue the existing, bounded independent semantic review.
  Skip the redundant identical grouped correction. The decision remains
  Unverified and unscored until the independent result passes validation.
- The independent reviewer is explicitly instructed to return
  `proof_excerpt=null`: Python resolves exact original passages from
  `evidence_ids`. Absence of quotation metadata no longer blocks validation.
- A non-verbatim model quotation with substantial lexical overlap with the
  authentic cited segments is **discarded**, recorded in technical
  diagnostics, and never displayed as CV proof or used in ranking. Completely
  unrelated invented quotations still fail, as do invented/out-of-scope
  source IDs and contradictory `decision`/`relation` pairs.
- No new request loop, no unbounded retries, no automatically promoted score,
  and no candidate/skill/JD-specific rules. Existing real source, negative
  tone, eligibility, experience and qualification validators remain active.

## Regression evidence

- A new test reproduces the user's exact S010/S019 source passages with an
  incorrect first-stage highlight and a paraphrased final quotation.
  One initial + one independent request now completes this controlled case;
  previously the same simulated responses left R008 Unverified.
- Additional tests verify that a final decision citing an invented source ID
  remains Unverified, mismatched semantic relation remains invalid, and a
  correct source-cited verdict works even with `proof_excerpt=null`.
- Earlier fake-quotation tests continue rejecting completely unrelated
  invented actions. Tests still cover the previous V4.9.35 punctuation-
  normalized exact-quotation acceptance.

## Limitations

The user did not provide the actual structured JSON response from OpenRouter,
only the precise validation notices. Consequently this is a code-level fix
with source-backed simulated model replies; actual provider behavior and
semantic accuracy still require a fresh run. Original source IDs guarantee
provenance, not that every semantic inference made by the model is correct.
