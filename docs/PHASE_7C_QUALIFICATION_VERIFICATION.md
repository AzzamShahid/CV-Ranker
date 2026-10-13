# Phase 7C — Qualification claim verification

**Build ID:** `typed-qualification-verification-2026-10-12`  
**Baseline:** Phase 7B `typed-experience-verification-2026-10-12` (308 tests, verified live on Windows).  
**New release status:** offline-tested only; run the local Ollama validation to measure live behavior.

## Why this stage exists

An LLM may cite genuine CV text but still give credit to the wrong educational field, an unfinished degree, an unrelated certificate, an expired license, or a job title that is not proof of a credential. Phase 7C introduces an additional, deterministic source-claim check after the existing Phase 7B experience evaluator and before unchanged percentage scoring. No embedding model, new LLM, skill catalogue, credential-provider API or extra score weighting is introduced.

## What this stage verifies

1. **Education:** Match an explicitly stated degree *level* plus an explicitly stated *field* where the JD specifies it. `BSc`/`BS`/`Bachelor of Science` are degree-format vocabulary, not a profession-specific dictionary. `BS CS` is admitted only via the mechanically exact initials of `Computer Science`. Different degree fields do not qualify. Higher-level degrees are marked ambiguous rather than automatically substituted, because employer policy for degree equivalence has not been supplied. In-progress, expected, incomplete, negated and conflicting claims do not earn automatic credit.
2. **Certificates:** Preserve the employer's frozen name. Generic `AWS certification` (as an *example*, not hardcoded in code) can be supported by an explicit `AWS Certified ...` claim. A specifically named credential such as `AWS Certified Cloud Practitioner` cannot be substituted by `AWS Certified DevOps Engineer`. Plain skills listings, training, certification preparation, expired and negated credentials do not pass as completed certificates. Short credential identifiers can be credited from the resume's Certifications section when they clearly name a credential.
3. **Licenses/registrations:** Require an explicit named license/registration claim. If JD states `valid`, `current` or `active`, CV must also claim current validity; unknown expiration, pending, revoked, expired and contradictory information cannot receive full credit. A title such as `Licensed Nurse` alone is not proof of a license. Expiry dates are not calculated from dates or checked against authorities; date-dependent validity requires review.
4. **Provenance:** Each interpreted claim records its exact extracted physical CV text, associated source segment ID and claim status (`claimed`, `pending`, `denied`, `expired`). Reports record the outcome (`satisfied`, `mismatch`, `ambiguous`, `not_evidenced`) and whether the Python gate modified the model status. If the status changes, evaluation mode becomes `mixed`.

## Claim verification is not credential authentication

**`satisfied` means only "the document explicitly claims to satisfy the requirement".** It does *not* mean an accredited university, training provider or licensing authority confirmed the credential. `independently_verified` is **always `false`** in this phase. Employment authorization, licensing eligibility decisions and protected-characteristic screening must not be auto-determined from these reports. Recruiters should confirm important credentials through an authorized external process and give candidates an opportunity to clarify ambiguous data.

## Decision states and scoring

| Evidence | Outcome | Assessment |
| --- | --- | --- |
| `BSc Computer Science` vs JD bachelor CS | satisfied | matched (CV claim only) |
| Bachelor in Chemistry vs JD bachelor CS | mismatch | not_matched |
| Pursuing bachelor CS | ambiguous | uncertain (no credit) |
| Master CS vs JD bachelor CS | ambiguous | uncertain pending employer level policy |
| `AWS Certified Cloud Practitioner` vs JD `AWS certification` | satisfied | matched (CV claim only) |
| `AWS` listed in Skills, no certification claim | not_evidenced | not_matched unless prior matched then uncertain |
| Explicit Azure certificate vs AWS certificate | mismatch | not_matched |
| Valid nursing license, claimed active | satisfied | matched (CV claim only; authority review pending) |
| Nursing license without validity claim | ambiguous | uncertain |
| Expired license | mismatch | not_matched |
| `Licensed Nurse` title only | not_evidenced | no automatic match |

No score multiplier, bonus, or denominator change. The *same* Python `score_candidate()` formula counts only `matched` requirements. `uncertain` earns zero credit, but remains distinguishable from `not_matched` in recruiter review. Where a credential was not evidenced, a prior `not_matched` remains `not_matched`; unsupported model `matched` is downgraded to `uncertain` for review.

## Source files

- `cv_ranker/qualification_validation.py`: `QualificationClaim`, `QualificationCheck`, `check_qualification` and `apply_qualification_checks`, with degree-level, field, credential identity, completion-state and license-claim logic.
- `cv_ranker/schemas.py`: adds `RequirementAssessment.qualification_check` while preserving all existing fields.
- `cv_ranker/pipeline.py`: invokes the qualifier check after optional reviewer aliases and numeric experience checks, before unchanged scorer.
- `cv_ranker/report.py`: source-backed CLI explanations.
- `app.py`: displays qualification outcome, exact source excerpt, claim state, and authenticity warning in the candidate detail expander.
- `tests/test_phase7c_qualification_verification.py`: positive, negative, uncertain, conflict, provenance, injection and end-to-end ranking tests.
- `sample_data/qualification_jd.txt` and `sample_data/qualification_resumes/`: two criteria across three resumes.
- `sample_data/license_jd.txt`, `sample_data/license_resumes/`: independent nursing-license wording scenario to prove that the logic is not restricted to IT.

## Phase 7B compatibility verification

All 11 pre-existing candidates in the bundled Backend (4), HR (3), and numeric experience (4) demos retained their exact old ranks, primary scores and per-requirement statuses. These scenarios do not include typed qualification requirements.

## Commands — Windows PowerShell

**Baseline integrity and live checks** (from the extracted project root, preserving `.venv`):

```powershell
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe doctor.py --live
.\scripts\run_benchmark.cmd
.\scripts\run_benchmark_pipeline.cmd
```

**Qualification CV-claim demo:**

```powershell
.\.venv\Scripts\python.exe main.py --no-llm --details --jd sample_data\qualification_jd.txt --resumes sample_data\qualification_resumes --output outputs\qualification_ranking.json
```

Expected: qualified 100%; pursuing degree and preparing certificate 0% uncertain; unrelated completed claims 0% not_matched. Note that first candidate's 100% refers to *stated* education/certificate conditions, not verified authenticity.

**License claim demo:**

```powershell
.\.venv\Scripts\python.exe main.py --no-llm --details --jd sample_data\license_jd.txt --resumes sample_data\license_resumes --output outputs\license_ranking.json
```

Expected: active claim 100%; unverified-current status uncertain/0%; expired mismatch/0%; title-only no credential evidence/0%.

Run `run_ui.cmd` to view trace details in Streamlit. The live benchmark may differ from earlier releases because invalid CV qualification claims are no longer treated as adequate evidence, even if Qwen cited them. **Never claim improved Qwen-only accuracy from Python status changes or mixed-mode runs.**

## Known limitations and Phase 7D dependencies

- English-source surface rules, not general academic credential ontology. `BSc`/`BS`/`MBA` formats are recognized, but international qualifications and nonstandard terminology may require recruiter review.
- Semantically similar but textually different academic fields and credential aliases are *not* mapped automatically. This is deliberate: no fixed profession dictionaries. Complex qualification alternatives belong to Phase 7D.
- Parsed PDF lines may be wrapped, tables can lose meaning and scanned PDFs may lack extracted text. The engine must not assert missing evidence means the applicant lacks the qualification.
- `JD: Bachelor degree or equivalent experience` is not a typed single credential; needs explicit employer choice and Phase 7D policy.
- `satisfied` is a CV-claim consistency result only; independent credential authentication, license expiry calculations, work authorization and automated hiring decisions are out of scope.
- The small 21-case benchmark does not establish production recruitment accuracy. More independently labelled real-world JD/CV cases are needed under Phase 7E.
