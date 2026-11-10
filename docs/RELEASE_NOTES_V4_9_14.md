# Phase 7G V4.9.14 — Provider-aware continuous resume and skill-only recall

Build `phase7g-v4-9-14-provider-aware-continuous-resume-2026-10-29`.

## Three reported failures

1. On Windows, a pasted JD can contain LF line endings. `Path.write_text()` translated them to CRLF for the temporary JD file, but the checkpoint identity was computed from the original widget bytes. Automatic resume therefore rejected **unchanged** inputs as changed.
2. A plain preferred criterion such as *Medical imaging* received **Not Found** even though the LLM's own explanation cited a completed research pilot and segmentation work. The model had silently demanded core-specialist or production/clinical experience not contained in the frozen JD.
3. A 12-CV cloud run completed only partway. The previous scheduler imposed a separate 24-HTTP-attempt ceiling and stopped after two extra batches, requiring repeated manual clicks even for transient OpenRouter HTTP 429.

## Corrections

- Write pasted JD text using `write_bytes(jd_text.encode('utf-8'))`, exactly matching the source-fingerprint bytes on Windows and Linux.
- Assess completed relevant research projects, pilots, and prototypes as potential direct evidence for *skill-only* criteria. If a Not Found explanation quotes an independently performed CV project, the existing one-per-CV independent semantic review checks the original source. This recall check never grants credit automatically, and planned-only or denied work does not pass.
- `OPENROUTER_MAX_REQUESTS_PER_RUN=0` disables the application-defined *per-run* request ceiling; it is now the template/default. An explicit positive `.env` value still provides a per-run cap for users who want one. Cross-batch recovery remains automatic when enabled.
- Keep the default-enabled cloud auto-resume active while the Streamlit browser session is connected, until the batch completes or an unrecoverable condition occurs. There is **no fixed overall number of retry batches or HTTP attempts** in the user-authorized mode.
- On HTTP 429, honor the full `Retry-After` delay (including a long reset window), otherwise use exponential backoff (60 s up to 3600 s), plus any existing provider cooldown. A long hint is delegated to the scheduler instead of blocking an individual UI request for hours.
- Detect rate-limit errors reported through OpenRouter's typed error metadata inside an HTTP 200 provider-response envelope, not only transport-level HTTP 429.
- Stop automatically on HTTP 401/402/403/404 and after two consecutive *non-rate-limited* retries with no newly verified candidate. Never switch model/provider or convert incomplete CVs to a scored Not Found.

## Privacy and cost

- The setting **Automatically resume unfinished cloud assessments** is a conspicuous, opt-out control; further OpenRouter requests may incur charges with **no application-defined overall spending ceiling**. It uses only the candidate documents already authorized for the initial cloud assessment.
- Source/decision checkpoints and scheduling live only in the current Streamlit session. Closing the tab or restarting the server stops the scheduler; no encrypted durable job queue or background service is claimed.
- A JD extracted through structural fallback cannot be reused as a validated frozen JD. That case needs a fresh JD extraction after provider recovery.
- No scoring weight, Found/Transferable rules, or hiring eligibility criteria were broadened. A source-recalled lead must still pass LLM and Python validation.

## Verification

Offline regression coverage includes exact JD bytes and context identity, the cited completed-skill recall versus a learning-only negative control, waiting indefinitely after repeated 429 without immediate rapid retries, a long Retry-After, explicit per-run cap overrides, no-cap transport mode, and typed provider errors in an HTTP 200 body. The full regression suite and runtime manifest are mandatory before release. A live OpenRouter run remains user-side verification because no provider key or private CV contents are included in the source ZIP.
