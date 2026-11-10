# Phase 7F.1 — Live Qwen Safety Corrections

**Build:** `evidence-integrity-live-safety-2026-10-13`  
**Parent:** Phase 7F `evidence-integrity-repair-2026-10-13`

## Why this patch exists

The user's October 13, 2026 Windows trace confirmed build integrity (141 tracked files), 467 passing tests, live Ollama `READY`, and the **same** 200 synthetic labels (`29df6dadc386097db86de01ad233a8fde50da74ff3eac2f9432d268854ef9357`). Results:

| Mode | Correct | False-positive matches | Missed matches |
|---|---:|---:|---:|
| Phase 7F fallback | 197/200 | 0 | 3 |
| Phase 7F fallback + optional exact initials | 199/200 | 0 | 1 |
| Phase 7F *live* Qwen/Python | 194/200 | 1 | 3 |

Six Qwen/Python mismatches in the live trace, with **no user credential verification**:

1. AI/ML abbreviations: 2 `NLP` cases and 1 `GCP` case missing. Those are not automatically resolved by this safety patch.
2. `hr/different/R004`: `3 years in marketing` must not satisfy or suggest 3 years HR experience solely because Qwen proposed a match.
3. `healthcare/different/R004`: `3 years of reception experience` does not establish nursing tenure solely because the CV targets a nursing role.
4. `healthcare/studying/R005`: **Electronic health records** was incorrectly marked `matched` using citation `S005 = 1 year of nursing experience`. That cited text does not establish electronic records experience.

## Code corrections

- `cv_ranker/assessor.py`: A **generic syntactic tenure-only citation** with no explicit frozen competency cannot support a Qwen `matched` decision on an unrelated named skill/responsibility. A candidate's source term guess cannot bypass that boundary. Source cites that actually name the requirement and action-based paraphrases remain eligible. Rejecting invalid rows triggers the existing correction/fallback contract, not an unlogged score edit. No profession dictionary was added.
- `cv_ranker/experience_validation.py`: For `not_evidenced` experience, the final status cannot stay `matched` or `uncertain` merely from the model's proposal if the resume lacks a direct source claim for that subject. A genuine skill claim **without numeric duration** remains `uncertain` for HR review, retaining prior policy.
- `tests/test_phase7f_live_safety.py`: Reproduces the live EHR citation and irrelevant subject durations, attempts to launder them via model-supplied `matched_term`, and tests permitted direct claims and actionable paraphrases.

## Verification and limitations

The complete suite, build manifest, and ZIP extraction were validated offline. The **unmodified** 200-case fallback benchmark still yields 197/200, and optional exact-initialism fallback still yields 199/200. A **new live Windows run is REQUIRED** before claiming Qwen-assisted performance is improved. The hotfix is designed to prevent those specific observed model failures; it does not prove no other unrelated semantic match is possible.

The full dataset consists of **short, synthetic TXT resumes**. It does not measure real-world CV validity, independent labels, OCR or complex PDF/DOCX layouts, HR fairness, license authentication, or deployment privacy/security. Preserve human review and do not auto-reject applicants. Matched qualifications are still self-reported CV claims.

## Windows validation

Backup previous installation, replace project files, and preserve `.venv`:

```powershell
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe doctor.py --live
.\scripts\run_phase7f_fallback.cmd
.\scripts\run_phase7f_initialism.cmd
.\scripts\run_phase7f_live.cmd
```

Keep the new `outputs/phase7f_live.json` and `outputs/phase7f_live_report.md` for decision-level comparison with the uploaded previous Phase 7F live results. **Do not confuse the Phase 7E-versus-7F fallback comparison with current live-versus-fallback results.**
