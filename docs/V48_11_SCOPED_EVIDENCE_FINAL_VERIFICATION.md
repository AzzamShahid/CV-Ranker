# V4.8.11: Scope-safe decisions and one bounded final verification

This release repairs generic classification faults found when evaluating the
bundled fictional CVs. Matching code contains no applicant-specific exceptions
and no fixed catalog of technology skills.

## What changed

1. A future-oriented coordinated list ("plans to learn A, B and C") is **one
   learning plan**, not a current skill claim for the later list items. The
   sentence is valid, reviewable non-scoring evidence; it is no longer rejected
   as a bogus positive proof requiring endless retries.
2. The duration validator distinguishes the field noun "machine learning" or
   "deep-learning" from the activity of a person *learning* a subject. Properly
   scoped, explicit professional duration receives normal numeric checks.
   A lack of production deployment does not negate evidence of professional
   research/development where the JD accepts such work.
3. Independent completed alternative work, combined with an explicit
   function-level comparison and shared work terms, may be marked
   **Transferable** for human review. It never increases the Found score or
   counts a different tool as a direct match.
4. If standard grouped assessment and its grouped correction both leave a
   row technically invalid, a **single optional final verification request
   per CV** can re-evaluate the outstanding rows together. It is not one API
   call per skill. A further invalid result remains **Unverified**, not a
   fabricated Found or Not Found. It consumes zero extra calls for an already
   complete CV.
5. Resolved first-attempt source errors no longer appear as active ranking-
   withheld notices once final verification succeeds. Diagnostics still record
   resolved notices separately.

## How to validate on Windows

Open a new PowerShell session in the extracted release directory, then run:

```powershell
.\.venv\Scripts\Activate.ps1
.\run_runtime_check.cmd
.\run_tests.cmd
.\.venv\Scripts\python.exe doctor.py --live --provider openrouter
```

The **live** OpenRouter smoke test sends synthetic data. It does not prove the
five-CV ranking will be perfect. Rerun the actual five authorized CVs and
inspect: (1) fully assessed count, (2) Taimoor's experience source and
quantified duration, (3) future learning vs skills, (4) transferable examples,
and (5) export citations. Do not claim the benchmark is passed until this
live run has been observed.

Cloud calls: the usual grouped calls remain. One additional grouped final
verification call is possible *only if unresolved technical rows remain after
correction*. Rate-limit pacing and retry configuration remain intact.
