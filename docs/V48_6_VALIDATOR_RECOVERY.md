# Phase 7G V4.8.6 — Domain-neutral source-validation recovery

## Problem reproduced

The V4.8.5 twelve-candidate assessment under-credited the fictional direct-fit
CV because source-backed rows could fail on an unsupported **optional**
`matched_term`. A grouped correction might then omit the row, leaving valid
work as an unverified Not Found. Other fully recovered claims were still
listed as unresolved zero-credit warnings. This is a validation/recovery
defect, not evidence that the candidate lacks the capability.

## Scope

- Preserve the frozen JD, existing EmbeddingGemma-2 retrieval, grouped LLM
  assessment, one correction request per group, and scoring formula.
- For longer task/experience categories, discard an invented optional quoted
  term **only** when the model already produced a Found decision with real
  candidate source IDs, completed work, multiple lexical JD anchors, and no
  direct denial. Do not award a new Found from this metadata repair.
- Preserve exact quotation requirements for atomic named tools, products and
  platforms. Contradictory duplicate rows still fail validation; identical
  duplicate answers can be collapsed without an extra LLM request.
- Treat punctuation-separated whole words as the same spelling, and permit
  a limited ordinary-inflection direct-work check on a standalone JD skill
  criterion. The check requires real completed work and full lexical coverage;
  it does not use synonym tables, embeddings as proof, or profession examples.
- When the existing direct-source validator independently recovers an invalid
  row, record it as a recovery, not an unresolved zero-credit failure.
- Accept explicit completed-delivery assertions in a CV summary when checking
  illustrative nonnumeric experience clauses; a bare skills list, negation, or
  unperformed plan remains insufficient.
- Improve the neutral LLM prompt so research performance is not automatically
  downgraded for lack of deployment when the JD did not demand deployment.

## Test coverage

The new `tests/test_v486_domain_neutral_validation_repair.py` uses the bundled
fictional two-page Aisha PDF and simulated model output reproducing missing
rows, invented source terms, and under-credited direct research experience.
It also contains a different-department false-positive counterexample,
conflicting duplicate rows, learning-only claims, and strict whole-word checks.

No live OpenRouter/Ollama candidate run was executed in this package build.
Run the included full automated tests and provider smoke checks on Windows,
then reassess all twelve fictional CVs for final scoring calibration.

## Unchanged

No hardcoded candidate scores, job requirements, industry skill dictionary,
tool-to-tool transferability mapping, BM25 search, new model, additional
assessment pass, preferred-score weight, or employment-gap integration.
Unresolved semantic evidence still earns no direct match point and requires
human review; scored positive claims are CV-reported, not independently
authenticated qualifications.
