# Phase 7E frozen synthetic dataset — labelling protocol

**Status:** manually authored synthetic test fixtures, **NOT independently adjudicated by a recruiter**. The benchmark is independent of the ranker's predictions, not independent human validation of clinical/professional hiring standards.

- 8 job descriptions from distinct role areas; 5 candidate resumes per JD; 5 JD criteria per role (4 required and 1 preferred).
- Each combination of candidate and JD criterion is assigned exactly one gold `matched`, `not_matched`, or `uncertain` value **before** running the engine.
- `matched`: the candidate's CV text explicitly supports the claimed requirement under the frozen JD wording; it is not external credential verification.
- `not_matched`: the source text explicitly contradicts a required claim, establishes too little experience, supplies a different credential, or contains no corresponding evidence.
- `uncertain`: learning-only evidence, a pending qualification, unclear scope of years, or other claims needing further review. This earns zero primary match credit.
- `evidence_quote` is copied exactly from the synthetic resume. Positive and uncertain gold labels must include a quote; an explicitly negative line may also be quoted.
- The benchmark requires exact **source wording** of each gold JD requirement in the JD file. The evaluator does not silently infer that renamed requirements are equivalent.
- Each label is a claim about evidence provided in the synthetic CV, **not independent verification of a degree, certification, or license**.
- Gold candidate coverage uses the same declared required-only scoring policy used by the user and supervisor: matched required / total required. It is not a hiring or job-performance outcome.

**Dataset limitations:** TXT-only fixtures, short and stylized CVs, English, no OCR/PDF/DOCX layout evaluation, no multi-rater label audit, no fairness study, no resume forgery detection, no production users, and no empirical hiring-outcome validation. External HR reviewers should revise and sign off labels before any industrial-quality claim.

To add fixtures, edit `labels.json`, create the corresponding JD/resume text files, and run the validator/test suite. Missing, duplicated or ungrounded labels fail closed.
