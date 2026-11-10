# Phase 7G V4.9.17 — Frozen skill-scope enforcement

Build `phase7g-v4-9-17-frozen-skill-scope-enforcement-2026-10-29`.
Assessment protocol remains version 18; final scoring weights are unchanged.

## Root cause

The grouped LLM prompts described the evidence standard for ordinary skill
criteria, but final validation checked source IDs and status/relation structure
without enforcing that standard. Consequently a model could return a
technically valid Not Found or Transferable reason which silently required
demonstrated professional experience even though the frozen JD only named a
skill. Earlier recall fixes could invite another model answer, but repeated
wrong reasoning was still accepted as a completed assessment.

## Enforced scope contract

1. `criteria_scope.py` derives an ordinary named-skill policy only from a
   single typed skill and its matching frozen JD quote, excluding explicit
   experience, duration and deployment conditions. The current model payload
   carries that evidence standard for each requirement.
2. For a plain named skill, a *literal affirmative original CV claim* may be
   recovered by the existing conservative source validator. It rejects
   negations, learning intentions, copied JDs and non-candidate text. This
   does not infer acronym or related product equivalence.
3. If a negative or transferable model verdict relies on unstated work-history
   or deployment depth **and the original CV contains a supporting positive
   review lead**, Python marks the decision Unverified and preserves original
   source quotes for the existing single independent grouped review.
4. The independent model must still verify semantic relationships and cite a
   verbatim original excerpt for a Found decision. Repeating the same
   unsupported work-depth objection no longer becomes a verified nonmatch;
   it stays Unverified with no score until genuine human/model resolution.
5. If no relevant positive source lead exists, a valid Not Found stays a
   nonmatch, but its explanation does not add a professional experience
   condition that the JD did not state.

## Unchanged protections

Professional experience minima, exact degrees, licenses/certifications,
actual deliverables, multi-part conditions, source tone/negation checks,
Transferable scoring, cloud rate-limit recovery and resumable assessments
retain their previous rules. There is no occupation, vendor or candidate
exception in production matching code.

## Verification

Cross-domain unit and pipeline tests cover plain skills, explicitly qualified
skills, professional-tenure safeguards, literal claims, negations, learning
plans, ambiguous semantic alternatives and a persistently erroneous model.
The bundled synthetic CV data is for regression only. Live verification of
the configured Gemini/OpenRouter provider remains necessary; no offline
test certifies universal real-world model accuracy.
