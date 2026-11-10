# Phase 7G V4.8.10 — Tentative-evidence versus technical-error contract

## Observed problem

The latest five-CV cloud run of V4.8.9 had four ranked candidates. One CV
had an `R009: cited segment(s) contained no qualifying capability evidence`
warning both before and after the grouped correction. The source was an
education/background statement about **exploring a tool through tutorials**.

Independent source extraction confirmed that the frozen requirement's name
appeared in that statement. The source was **not** proof of completed tool use
and did not deserve a Found point. It was, however, real evidence of limited
exposure, which is the purpose of the `uncertain` intermediate status.

## Root cause

The generic positive-capability gate ran before the frozen-requirement-scoped
tone was evaluated. Its narrow whole-segment language cues did not understand
"currently exploring" or "tool tutorials". Consequently, genuine tentative
claims appeared as *positive* text without qualifying performed work and
were rejected as citation failures. The single bounded correction repeated
the same rejection and withheld the entire candidate rank.

## Corrections and invariants

1. **Recognize documented tentativeness:** Learning, exploring, tutorials,
   and experimentation are generalized language cues, not a list of skills,
   departments, applicants, or score overrides.
2. **Validate source tone first:** A source-cited tentative claim is valid
   as tentative, but it cannot grant a direct Found point. A source-cited
   denial likewise cannot grant Found.
3. **Reject unsupported uncertainty:** A job title or unrelated degree alone
   still cannot substantiate skill exposure. Old corrective guards remain.
4. **Aggregate distinct citations:** An independently affirmative ordinary
   skills-list assertion is not erased merely because the applicant also
   reports studying it. A genuine denial alongside a positive assertion
   remains contradictory and requires review.
5. **Preserve system contracts:** Frozen JD criteria, cited source IDs,
   withheld scores for genuinely unverified technical failures, required
   match denominator, preferred tie-break, and separate transferability are
   unchanged.
6. **Keep API costs bounded:** This is a validation-order/source-tone change,
   not a new LLM invocation. Existing grouped calls, corrective limit, and
   provider retry settings remain unchanged.

## Verification

Automated tests exercise independent examples from operations and logistics,
plus the previously failing fictional PDF *only as a parser fixture*.
They prove a tentative source can resolve without a retry; a performed-work
claim stays Found; unrelated titles/degrees stay invalid; affirmative
skills-list claims survive learning notes; and genuine contradictions do not
become Found. The full regression suite and runtime source-hash manifest
must pass before packaging.

**Live completion and semantic accuracy remain unproven until a fresh run.**
Offline tests are not a substitute for model-quality evaluation. The zero
Transferable scores in earlier batches also remain a separate concern.

## Windows verification

```powershell
.\run_runtime_check.cmd
.\run_tests.cmd
.\.venv\Scripts\python.exe doctor.py --live --provider openrouter
.\run_ui.cmd
```

The new build must identify itself as
`phase7g-v4-8-10-tentative-claim-validation-2026-10-28` with protocol `8`.
Reanalyze the five CVs in a newly restarted UI session; earlier outputs are
snapshots, not live-updated results.
