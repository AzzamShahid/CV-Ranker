# Phase 7G V4.9.16 — Source-claim scope reconciliation

Build `phase7g-v4-9-16-source-claim-scope-reconciliation-2026-10-29`.
Assessment protocol: unchanged, version 18.

## General defect

For an ordinary single skill JD criterion, an LLM may recognize a positive
skills-list claim in its explanation, yet return Not Found because the CV does
not separately describe use in a professional work-history entry. Such a
threshold is not part of a bare named-skill requirement. The existing
independent recall gate focused on completed performed work, and could miss
this case because a skills list does not need an action verb.

## Repair

- When a negative explanation affirmatively acknowledges a listed candidate
  skill, identify the *actual original skills segment* whose individual claim
  appears in that explanation. This is a generic text-to-source check for
  review eligibility, not an equivalence, synonym, or scoring rule.
- Exclude future learning, negations, instructions, copied JD text and claims
  absent from the original source ledger.
- Put that segment first in the existing ONE independent grouped review for
  the candidate. The independent model compares the real reported skill to
  the original frozen JD, including whether an acronym, service or differently
  named product belongs to the requested capability.
- Found requires the separate independent decision and exact original CV
  quotation to pass all source validators. If the model cannot substantiate
  the relationship, no point is granted.
- Prioritize self-contradictory Transferable decisions, then explicit
  skills-list omissions, then weaker recall leads within the existing fixed
  completion capacity; technical unverified rows remain first.
- No provider name, profession, technology, qualification, or example CV is
  introduced into the scoring logic. The tested positive and negative cases
  are regression fixtures, not production rules.

## Validation

Regressions cover cloud platform/service claims, warehouse systems, database
skills, absent claims, negated claims, learning intentions, original PDF source
selection, independent Found, and independent Not Found. Existing cross-domain
benchmark, experience, education, compound, named-tool and evidence tests must
all pass before packaging. Live provider variability and applicant self-report
still require human hiring review.
