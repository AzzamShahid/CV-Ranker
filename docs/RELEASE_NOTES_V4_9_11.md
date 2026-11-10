# Phase 7G V4.9.11 — resumable OpenRouter assessments

**Build:** `phase7g-v4-9-11-resumable-provider-failures-2026-10-28`  
**Assessment protocol:** `segment_ids_semantic_llm` v18 (unchanged)

## Observed production failure

Five CVs were sometimes reported as 4/5 or 1/5 fully assessed. One recorded
failure was OpenRouter HTTP 429 during a grouped candidate assessment. The
cloud client's exhausted-retry circuit then prevented all remaining calls.
Other historical 4/5 results came from malformed/missing source judgments,
which are distinct from rate limits and still correctly withhold rank.
Offline tests are not evidence that the live provider will accept every call.

## Corrective behavior

1. **Explicit resume:** The Streamlit session keeps an in-memory checkpoint
   of the frozen JD and assessed candidate reports. A user can press
   **Resume unfinished assessments** with the original upload(s) still
   selected. Completed CVs are reused without an LLM or embedding call.
2. **Strict checkpoint binding:** Reuse requires exact JD bytes, unchanged
   provider/model and semantic configuration, identical approval/eligibility
   policy bytes, current release build ID, and exact candidate filename and
   document bytes. Only changes to API credentials and pacing/retry/budget
   settings are permitted between resume attempts. The backend also verifies
   frozen JD SHA and policy hashes before trusting the checkpoint.
3. **Partial evidence safety:** Incomplete candidates are retried. If a retry
   returns fewer source-verified rows, the previous more complete partial
   candidate report is retained **without a percentage or rank**. This is not
   a silent promotion of related skills or unverified decisions.
4. **Rate-limit circuit:** Once an OpenRouter 429 exhausts retries, skip
   redundant embeddings and cloud calls for remaining CVs and keep the
   unassessed states explicit. Record HTTP 429 counts and the sanitized
   `Retry-After` delay. A session cooldown delays the next intentional run.
5. **Conservative defaults:** New installs use a 6-second minimum interval,
   15-second retry base, and 120-second max retry-after. `.env` overrides
   remain respected; an upstream daily or account limit can still require a
   longer wait or a separately authorized model/provider.
6. **Honest UI:** A partially completed analysis no longer displays a blanket
   success message. It identifies the completed count and offers resume.

## What this does not do

- No silent cloud/local provider switch or alternate-model blending.
- No scoring weight change, invented JD degree equivalences, or relaxed
  source-grounding validation.
- No persistent new on-disk CV cache. Checkpoints last only while the same
  Streamlit session exists. Export a report deliberately for longer retention.
- No claim of live OpenRouter reliability without a successful end-to-end
  run using the user's configured account, models, and authorized documents.

## Verification

The targeted regressions cover checkpoint fingerprints, frozen JD reuse,
invalidated JD rejection, retention of partial evidence, and sanitized 429
diagnostics. Run `run_runtime_check.cmd` and `run_tests.cmd` after extracting
the ZIP. For an actual cloud contract run, use `doctor.py --live --provider
openrouter`, then test the UI with one CV before the full batch.
