# Phase 7G V4.9.12 — Automatic bounded recovery

Build `phase7g-v4-9-12-automatic-bounded-resume-2026-10-28`.

## What changed

- The upload form now enables **Automatically resume unfinished cloud assessments** by default when OpenRouter and AI assessment are selected. The option is disabled for offline/local runs.
- After an incomplete initial batch, the current browser session schedules up to **two additional batch attempts**, beginning after at least 60 seconds and observing a provider cooldown. If the first automatic attempt remains incomplete, another is scheduled after at least 180 seconds (plus any provider cooldown).
- Each automatic attempt has a separate **24 HTTP-attempt ceiling**, including internal retries, on top of the original run's limit. Additional calls can incur charges; the user can disable automatic recovery before running.
- Previously fully assessed CVs are reused without more LLM calls; only incomplete CV results are retried. A repeated click on **Analyze and rank candidates** also resumes a compatible incomplete session instead of needlessly discarding completed results.
- The recovery guard requires the same JD bytes, candidate filenames and bytes, provider/model, assessment settings, reviewed aliases, eligibility policy, and the same build. Changed inputs cancel the scheduler.
- A JD extracted by structural fallback is *not* eligible for an automatic or manual frozen-JD resume. The user must initiate a fresh assessment after the model recovers to revalidate the JD denominator.
- The scheduler uses Streamlit's periodic fragment and runs **only while the Streamlit browser session is connected**. It is not a background queue, cannot survive lost browser sessions or server restarts, and does not persist private CV data beyond the existing transient session.

## Verification

Offline regression tests cover automatic completion without a second click, no duplicate calls after completion, cancellation on changed CV bytes, the two-attempt maximum, rejection of a fallback JD, and exact checkpoint identity. Existing runtime-identity and ranking tests remain required before distribution.

## Boundaries

This fixes recovery orchestration, **not** upstream OpenRouter account limits. A persistent HTTP 429 can still leave unverified CVs. It does not silently select another provider/model, invent absent decisions, or relax scoring and source citation standards. The privacy-sensitive live OpenRouter workflow must be verified by the authorized user with their own key and CVs; offline tests cannot promise 100% assessment completion under a provider quota.
