# V4.9.30 — Targeted request recovery and supervisor reliability

## Correctness repairs

- Resume reuses each previously verified requirement decision anchored to the
  same frozen JD/CV bytes and source segment text. It sends only unfinished
  criteria to the assessment engine. Prior verified decisions remain context
  for cross-criterion evidence review, and all typed validation still runs.
- Partial checkpoints are merged by requirement ID, so equal numbers of
  verified criteria cannot replace unrelated earlier verified decisions.
- Model output truncated at its token ceiling is reissued in smaller groups;
  no duplicate full-size generation is attempted for that failure.
- Provider Retry-After is never shortened to a configured in-call sleep cap.
  Recurring HTTP 503/5xx, 400/422 and network failures open the run's circuit
  rather than repeatedly contacting the provider for every remaining CV.
- Cloud assessment and Resume have a cumulative request budget tied to the
  frozen JD/CV checkpoint. The default is 128 actual HTTP attempts, separate
  from JD extraction. The prior per-run transport limit remains optional.
- Automatic recovery now regards newly verified requirements as progress,
  even before the CV has enough evidence for its final score.
- Identical filename/content uploads receive distinct stable slot keys.
- The first Analyze action and manual Resume run in the same in-memory worker
  architecture as automatic recovery. Publishing always rechecks original
  uploaded files, approved JD, model/settings, and prior checkpoint.

## Preserved contracts

- Frozen source-grounded JD, YAKE extraction, human approval, eligibility
  checks, verified/transferable/not-found/unverified evidence semantics,
  single pooled Required + Preferred weighting and existing exports.
- An unverified row never receives a fabricated zero or final ranking.
- No additional cloud model pass, new external dependency, credentials store,
  or production database migration is introduced.

## Verification and limitations

- Focused regression tests include two and three CVs, single unfinished JD
  criterion, duplicate CVs, HTTP 429/503, truncation, exhaustion and async UI.
- Normal cloud-model behavior still needs a separately authorized, bounded
  live test with local EmbeddingGemma and the configured OpenRouter model.
- Workers are session-bound; closing the tab or restarting Streamlit does not
  create a persistent queue. An already-started HTTP call is not cancelable.
- Concurrent user sessions share a worker pool and embedding database; a
  production-scale concurrency stress test is not included in this release.
