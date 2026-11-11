# TextileHR AI / CV Ranker 4.9.50 — cross-department regression and honest review evidence

Date: 11 November 2026. Assessment protocol: `segment_ids_semantic_llm` v36.

## What this release improves

### 1. A negative model decision no longer hides obvious original review passages

When a valid model result says **Not Found** but returns no citations, the
original CV ledger is scanned for *review-only* passages sharing multiple
meaningful words with the frozen JD. This handles both simple and composite
responsibilities, including terms with ordinary inflection (for example,
"corrective" and "corrective actions"). The exact original source ID and
passage are displayed with a human-review flag.

**This is not automatic matching.** Such excerpts are labeled retrieved,
uncredited leads. The model's Not Found decision and zero direct points are
unchanged; the reviewer can inspect the passage and decide whether a new
assessment is warranted. Source-ledger recall adds **zero** provider calls.
Completely unrelated source text is not fabricated as review evidence.

### 2. An explicit alternative named diploma can be evaluated conservatively

The frozen JD may permit one degree *or* a separately named diploma. The
existing v4.9.49 source parser handled same-level OR majors but could not
validate the separately named credential. The updated parser recognizes an
uppercase acronym explicitly present in a named **OR diploma** clause (for
example, `or a three-year ABC diploma in Field X`), requiring the CV to claim
that same acronym and exact field. When the JD explicitly states a program
duration, the CV must also state that duration before Python awards direct
Found credit. No inferred diploma equivalence or credential-duration mapping
has been added. Different diplomas, fields and pending qualifications cannot
pass these checks. Because this is an exact named-credential contract, no
industry-specific role, company, or academic field list is involved.

### 3. Cross-domain regression verification

New tests exercise explicit degree alternatives in textile engineering,
computer science, civil engineering, accounting, electrical engineering,
and generic customer-operations descriptions. Positive and negative tests
cover exact named diplomas, diploma duration, incomplete credentials, absent
skills, source citation recall, false review leads, and zero points for
uncredited passages. Pre-existing security, weighted scoring and recovery
tests remain mandatory before release.

## What this release **does not** claim

**No software can guarantee 100% accurate hiring assessments for any possible
JD or CV.** Natural-language requirements, incomplete resumes, misleading
claims, scanning/OCR quality, LLM interpretation, domain-specific jargon, and
qualifications requiring external verification all create irreducible
uncertainty. The system must preserve **Unverified/Review recommended** states
and honest Not Found explanations rather than manufacture certainty or points.
Even a 100%-matched CV score denotes *reported/source-supported agreement*,
not identity, credential, employment, or competence verification.

The added source-recall path deliberately does **not** convert Not Found to
Found or Transferable. A meaningful semantic relationship still needs a
source-grounded assessment or human review. This release also does not solve
public deployment privacy, authentication, or external Ollama connectivity;
consult `docs/PRODUCTION_SECURITY.md`. Local/offline tests cannot guarantee
live OpenRouter reliability or budget usage.

## Upgrade note

Use a fresh extraction folder and confirm interface **v4.9.50**, assessment
protocol **v36**. Because assessment evidence behavior changes, prior
checkpoint decisions must not be silently reused as new-protocol results.
Preserve historical exports for audit. Run `run_tests.cmd`,
`run_runtime_check.cmd`, and local `scripts.production_preflight` before
supervisor review. A live assessment with your JD and real CVs still needs
the locally configured Ollama embedding model and selected assessment model.
