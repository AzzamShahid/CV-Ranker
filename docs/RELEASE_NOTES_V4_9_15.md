# Phase 7G V4.9.15 — Domain-neutral skill-scope consistency audit

Build `phase7g-v4-9-15-domain-neutral-skill-scope-audit-2026-10-29`.
Assessment protocol remains version 18; no scoring policy or evidence format changes.

## Problem

A model could identify completed work in the exact skill named by a bare JD
criterion yet choose Transferable because the work was a research pilot or was
not deployed at an unstated commercial scale. That decision was source-valid,
so citation validation alone preserved its unscored status. The independent
second review previously only revisited Not Found or technically unverified
rows, missing this internal inconsistency.

## Repair

- A general, selective review gate detects an affirmative named-skill claim
  in the model's own explanation alongside a Transferable status supported by
  completed original work. It does not assume that lexical similarity proves
  the skill or contain a profession-specific list of accepted projects.
- Contrastive language such as "related to [different tool]" and explicit
  negations are not treated as affirmative direct-use claims.
- Such cases share the existing maximum ONE independent grouped verification
  call per CV. The frozen JD and original cited CV sources are provided;
  previously cited original segments take priority over new retrieval leads.
- Only a valid independent Found decision with original source IDs and an
  exact proof excerpt can grant direct credit. Related work remains
  Transferable, and unverified output cannot invent a score.
- Existing degree, tenure, compound criterion, strict named-tool and
  OpenRouter continuous-recovery safeguards remain unchanged.

## Verification scope

Offline cases cover medical imagery, warehouse inventory and payroll research,
named-tool alternatives, future learning, explicitly scoped responsibilities,
and end-to-end independent Found/Transferable decisions. A live configured
provider evaluation is still required to establish real-world reliability.
All CV facts remain applicant-reported; the tool is decision support, not a
substitute for human hiring review.
