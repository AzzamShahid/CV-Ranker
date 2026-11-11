# Phase 7G V4.9.18 — Skill-list source recall and negative evidence visibility

Build `phase7g-v4-9-18-skill-claim-source-evidence-2026-10-29`.
Assessment protocol version 19; same frozen-JD requirements and scoring.

## Identified defects

1. Prior structured prompts explicitly instructed the model to return no
   source IDs for Not Found. Therefore an explanation could refer to a real
   CV claim while the supervisor report showed zero original checkpoints.
2. Initial retrieval only protected literal full JD names/initialisms, so a
   legitimate skill-list service could be omitted when a broader named skill
   was requested. Model decisions about the omitted source were unreliable.
3. The source-consistency audit watched for particular work-experience phrases
   in the model reason. Other phrasings of the same unstated threshold could
   survive as an unjustified verified Not Found.

## Changes

- `evidence_ids` can now cite original *examined* source checkpoints for
  Not Found as well as Found/Transferable. The decision determines whether a
  cited source is accepted proof. Not Found citations **never** award credit.
  Independent responses enforce the same contract. The supervisor UI labels
  negative checkpoints as reviewed but not credited.
- The first-pass prompt and independent prompt distinguish a positive,
  self-reported skills-list claim from a claim of professional project use.
  An unambiguously constituent named service can establish a broader skill;
  the model must genuinely verify that relation with an original citation.
- A generic source recall checks affirmative skills-list entries for shared
  meaningful wording before the embedding-ranked evidence list is truncated.
  This is **retrieval**, not an alias table, keyword-based score or a
  product-specific rule. The existing one grouped independent semantic review
  also receives plausible original skills-list sources when a first-pass
  negative needs adjudication.
- The frozen-JD scope validator flags more ways of sneaking in work-setting
  or project-use requirements not present in a bare skill criterion. Original
  negation and learning evidence remains noncreditable; a conflicting or
  persistently invalid semantic relation remains Unverified.
- An earlier persisted report now displays an explicit build mismatch warning
  rather than appearing as a fresh decision under the new build label.

## Verification and limits

Regression tests use multiple generic departments, exact affirmative claims,
semantically related service names, unrelated named products, professional
experience requirements, denials, learning-only claims, and source omission.
Only an independently source-grounded semantic Found earns a point for a
differently named service; the source alone is not an automatic alias.
No live Gemini/OpenRouter call is bundled with offline tests, so confirm on a
fresh assessment using your configured provider and inspect all source IDs.
