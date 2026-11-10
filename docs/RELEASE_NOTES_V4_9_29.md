# V4.9.29 — Non-blocking, bounded cloud recovery

## Why 1/2 CVs could appear stuck

The existing scheduler treated every OpenRouter HTTP 429 response as transient,
reset its no-progress counter, and scheduled another batch indefinitely. A
manual Resume could repeat the same requests during the provider's cooldown.
Also, recovery ran synchronously inside Streamlit's fragment, occupying the
UI script thread until the assessment returned. A progress notice was not a
separate background job.

## Repairs

- Each opted-in retry runs in a bounded, in-memory worker pool, off the UI
  script thread. Streamlit state is read and written only by the UI thread.
- Before publication, the UI rechecks the frozen approved JD, CV contents,
  provider/model and matching checkpoint. Changed inputs discard stale work.
- Repeated provider 429s **without new verified CVs** pause after three
  attempts. Two other no-progress retries also pause. A provider delay over
  one hour pauses instead of displaying an apparent hang. The full smaller
  Retry-After value is respected. A true progress event resets the streak.
- A background Future is never submitted twice. Analyze/Resume buttons are
  disabled during a scheduled or running automatic attempt; manual resumes
  respect the recorded provider cooldown.
- A **Pause automatic retries** control stops future scheduling, and **View
  partial results** opens the preserved evidence and rankings immediately.
- Previously verified CVs remain cached, and no unverified candidate receives
  a score. JD approval, YAKE, one-pool JD weighting and all other decisions
  remain unchanged.

## Important limitations

The current Streamlit session must remain connected to schedule further
recovery attempts. A single already-started background worker may finish
while the UI is busy, but this is not a durable, cross-restart server queue.
If the provider is out of quota or has suspended requests, software retries
cannot make it complete until access is restored. No private applicant CV is
persisted to a new queue, and background results are kept in memory until
publication or discard.

## Verification

Regression cases cover rate-limited and mixed no-progress loops, long
Retry-After, changed CVs during an in-flight request, duplicate prevention,
worker isolation, successful completion and preserved resume restrictions.
