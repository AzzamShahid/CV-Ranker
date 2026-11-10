# Phase 7G V4.9.33 — interrupted assessment recovery

Date: 10 November 2026

## Confirmed root cause

Before this patch, `UnifiedEvidenceEngine.assess` raised an `LLMError` if a
later candidate-assessment batch failed. Although preceding JD batches could
already contain valid source-grounded judgments, the exception prevented their
return to `CVRanker.run`. The candidate was saved with an empty assessment
list; the next Resume reassessed the same completed batches and paid again.
This is especially visible with the second candidate when the first CV has
already consumed cloud quota or the second CV has harder-to-parse evidence.
There is no special two-CV branch; a live provider trace would be required to
identify the exact failure affecting a particular uploaded CV.

An HTTP attempt is NOT the same as one CV. The default 2,048 output-token
budget plans at most seven JD decisions per model completion; 17 requirements
therefore require at least three initial model calls per CV. Validation
corrections, independent final verification, and up to two configured provider
retries can multiply the physical requests. The Technical details panel
reports physical HTTP attempts and model calls separately.

## Changes

1. **Preserve candidate decisions between batches.** On a known provider/model
   failure after one or more valid batches, completed rows are returned and
   only pending IDs become Unverified. No provisional points or ranks are
   issued for them. The next Resume reuses verified rows after exact CV/JD
   source identity checks. If the very first batch fails, the candidate still
   reports a true failed assessment rather than manufactured judgments.
2. **Bound failed JSON/schema handling.** A grouped completion that repeatedly
   violates its structured schema is divided into smaller groups. The group
   sizes decrease monotonically; a one-row failure ends the attempt. Transport
   problems (429, 503, network timeouts) are not treated as JSON schema
   problems and do not trigger this splitting.
3. **Remember strict schema incompatibility.** If a route rejects JSON Schema
   but accepts JSON Object, future calls in the current client use the proven
   mode while still applying full local Pydantic validation.
4. **Show real progress.** The initial and recovery worker publish sanitized,
   thread-safe progress events for current CV, JD batch, HTTP attempt and
   elapsed time. An unfinished CV's source-validation errors and unfinished
   IDs appear near the results summary and in per-candidate technical details.
5. **Prevent repeat validation loops.** When a recovery attempt makes no
   verified progress and the same JD IDs are still unverified due to response
   or evidence validation, automatic retries pause with an actionable reason.
   Provider rate limits retain their separate cooldown policy.
6. **Protect diagnostics.** Unexpected dependency exception bodies are not
   copied to applicant reports. Known HTTP status codes are retained; CV text,
   provider response bodies and credentials are not logged by these changes.

## Verification

- Added `tests/test_v4933_partial_batch_survival.py` with offline scenarios:
  two CVs, a later 503, targeted resume, malformed grouped JSON, persistent
  JSON-object fallback, progress reporting, validation-retry pause, and 429
  handling.
- Run `run_tests.cmd` and `run_runtime_check.cmd` on the installed Windows
  directory, and then perform a controlled two-CV test with the selected
  OpenRouter model. Offline test mocks cannot guarantee live provider success.
- If the second CV is still incomplete, open **Technical details → Execution
  details**. Preserve the HTTP status, `interrupted_cause`, `unresolved_ids`,
  model name and attempt counts; share them with the developer without sharing
  your API key. A redacted run log and the affected CV may be necessary to
  distinguish a 429 quota, timeout, strict schema incompatibility, and a
  source-validation issue.

## Known limits

- This is not an always-on job queue across a Streamlit server restart.
- Already-sent provider requests cannot be safely interrupted mid-flight.
- If the provider fails on the first JD batch, there are no valid new rows to
  preserve; the saved failed candidate is available for later Resume.
- Model judgments are still checked against original cited CV segments.
  The application will not assign points to unsupported or unverified claims.
