# Fictional implementation-verification scenarios

`tests/web/test_api_worker.py` uses only fictional JD/CV content and a temporary local SQLite data directory. The tests call **real FastAPI routes and existing Python engine methods**, avoiding fabricated rank data. They do not call a paid LLM.

1. Upload a JD and CV, start an async extraction job, claim it with the worker, approve a source-grounded JD, submit a real assessment job, inspect persisted rankings and source-backed Why, export ZIP.
2. Repeat the same idempotency key/payload; confirm the same job ID. Reuse the key with different settings; confirm HTTP 409.
3. Open two tabs editing weights with the same revision; the second stale PUT must conflict. Weight-only projection makes zero LLM calls.
4. Upload two `Applicant.txt` files with different bytes; confirm two distinct source IDs, candidate snapshots and evidence.
5. Reject evil web Origin, missing CSRF, wrong-workspace document URL, malformed PDFs/DOCX, uploaded SVG scripts, and untrusted CSV formula text.
6. Claim a job with worker A, change its fencing owner, and prove A cannot write progress. Expired lease pauses unknown-delivery work; bare Resume must return 409 without a provider call.
7. Complete a JD job in a **real subprocess** (`python -m worker --once`) after the initiating HTTP client exits. Reconstruct a new API instance from persisted SQLite and the same signed local session cookie; confirm the durable result.
8. Back up SQLite and source files into a plaintext ZIP and restore into a new empty directory. Reject a tampered database entry.
9. Read SSE history/snapshot and ensure monotonic sequence values. Deep-link SPA and unknown API route precedence are tested via HTTP TestClient; real browser reconnect remains blocked.
10. Run existing protected engine tests for three-verdict, 429 cooldown, source-bound Transferable, compound review and scoring. Full dependency-complete engine suite is a separate qualification gate.

**Not performed:** real browser screenshot and keyboard flows; live model/provider benchmarks; Windows build/run; simultaneous multi-process chaos tests; every individual Streamlit feature. The parity register records those items honestly.
