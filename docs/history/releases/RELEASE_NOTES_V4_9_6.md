# Phase 7G V4.9.6 — cloud run failure attribution

**Build:** `phase7g-v4-9-6-cloud-failure-attribution-2026-10-28`  
**Protocol:** `segment_ids_semantic_llm`, version 14

## Observed symptom

A real V4.9.5 OpenRouter run yielded one assessed candidate and three
unassessed candidates (`1/4`). The CSV correctly withheld ranks, but the
Streamlit page displayed placeholders (`0/11`, `0/7`) without the exception.
The supplied CSV records no provider error, so it does NOT establish whether
the actual cause was HTTP 429, HTTP 402, timeout, schema failure, context
failure, or a different processing error. A new semantic scoring rule would
not repair a failed provider request.

## Confirmed error-reporting defects fixed

1. The grouped assessment caught every exception and discarded its message,
   returning only `LLMError` as the cause. For known OpenRouter `LLMError`s,
   this release preserves the provider's already-sanitized status/timeout/
   parsing description. Unknown exceptions still reveal only the exception
   class, never arbitrary CV text or raw provider bodies.
2. The candidate screen hid its error notice inside a collapsed panel.
   Failed candidates now display a short failure reason immediately, and the
   diagnostic panel opens automatically. Zero-count placeholders remain
   explicitly marked **unassessed**, never scored zero.
3. A shared-LLM circuit-stop warning incorrectly claimed that deterministic
   fallback was used. Unified AI assessment does not permit this silent
   scoring substitution. The warning now states that later candidates were
   **unverified and unranked**, including the sanitized OpenRouter stop reason.

## Preserved scoring and API contracts

- V4.9.5 qualification, evidence, transferability and score logic is unchanged.
- The provider still uses bounded retries, pacing, one grouped correction,
  no per-requirement verification loop, and at most one final independent
  grouped check per CV. The OpenRouter HTTP request ceiling is unchanged.
- An exhausted rate limit or budget still stops remote calls instead of
  silently assigning negative candidate scores or unexpectedly spending more.
- No automatic retry of all previous candidates has been introduced: that
  requires a separate checkpoint/resume contract and proof the failure is
  transient. Prior successful results remain exportable in the run's report.

## Verified offline results

- **920 automated tests passed**, including cloud-interruption handling and
  the exclusion of private content from an unexpected exception's UI text.
- Runtime SHA-256 integrity verified for **383 release source files** and
  assessment protocol version **14**.
- The unchanged eight-department synthetic fallback benchmark scored
  **197/200** decisions (98.50%), with no false-positive direct matches.
- There was **no live OpenRouter multi-CV run** in the test environment;
  actual error cause and provider reliability remain unverified.

## What remains unknown

The real provider failure cannot be determined from `cv_ranking_summary.csv`.
After running V4.9.6, open the failed candidate and copy its now-visible
provider/validation message, plus `04 Technical details` request metrics.
This distinguishes quota/pacing errors from provider schema errors and local
context/embedding faults. Do not claim production readiness from unit tests
or synthetic benchmarks alone.
