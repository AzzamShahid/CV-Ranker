# Phase 7G V4.6 — reliability audit (26 October 2026)

## Reproduced defects and repairs

| Fault | Root cause established by source-level audit | Repair |
| --- | --- | --- |
| Sara's BS Computer Science showed Not Found | A combined `EDUCATION, METHODS AND ADDITIONAL BACKGROUND` header was unrecognized and the next line inherited `projects`; the degree verifier deliberately ignored bare `BS` in non-education sections. | Parse composite education headings; cite original degree source line. |
| Sara's 4 years showed Not Found | The JD parser mistook `relevant professional` for the experience *subject*, while the validator did not recognize word-based `four years` and required an invalid literal subject. | Parse generic JD scope separately; accept explicit work-scope claims with vocabulary drawn from the actual JD and source statement. The CV now cites the four-year LLM systems engineering statement. |
| A correctly checked duration reverted to Uncertain | A later generic compound-expression pass overwrote the specialist numeric validation just because the JD included `or`. | Preserve completed tenure and qualification checks; keep conservative compound analysis for remaining skills. |
| OpenRouter HTTP 429 | Client made repeated calls with only ~1.5 seconds delay, ignored `Retry-After`, and could continue trying more CV rows after exhausting retries. | Inter-request pacing, bounded exponential backoff, capped `Retry-After`, and a run-local fast-fail circuit. No silent provider switch. |
| Local semantic retrieval appeared unavailable | The Streamlit error hid the underlying category and semantic settings were not fully passed through from `.env`; a corrupt single cached vector could abort the whole search. | `.env`-owned embedding model/URL/timeout/batch size; categorized safe UI notices; per-entry cache repair; separate persisted local retrieval diagnostics. |
| Large source-batch failures | The embedder submitted all CV segments in one request; that succeeded for the test 42 segments but was not resilient for larger content. | Send ordered chunks, normalize each and verify full output dimensions without mutating source IDs. |

## Validation boundaries

- Regression tests use fictional CVs/JDs and mocked HTTP to cover 429, Retry-After, cache corruption, ordered batching, cloud failure after successful retrieval, and concrete Sara/Farhan year/degree outcomes.
- No hardcoded job-skill taxonomy was added. Contextual duration matching extracts words from the **uploaded JD** and requires them in the **same original CV duration clause**. It does not infer unrelated years from separate skills.
- Embeddings discover evidence, never award points themselves. Each criterion still has Found, Transferable, or Not Found; transferability does not add exact-match points.
- **Unavoidable external condition:** real OpenRouter 429 may be a provider hard quota or account limit; retrying cannot override it. Choose Local or wait for reset. Actual provider availability must be checked on the supervisor PC using `doctor.py --live`.
- The legacy sample JD has 17 requirements. The new one-click supervisor JD is explicitly written with a Computer Science degree requirement and has **18** (11 required + 7 preferred). An arbitrary uploaded JD retains only its own specified requirements; never infer them from the CV.
- The source-specific root cause of an earlier UI `EmbeddingError` could not be proven from an error type alone; the new build surfaces a safe actionable category, retains independent retrieval, and repairs common cache/config/batch failure modes.

## Security and presentation

- `.env`, API keys, output databases, and private CV uploads are excluded from distributable ZIPs.
- Run `run_runtime_check.cmd` after extracting a fresh ZIP, then `run_ui.cmd`. Never merge files into an earlier phase directory; the runtime hash manifest will reject mismatched installations.
- AI-generated screening remains provisional, CV statements are self-reported, and hiring decisions require human review.
