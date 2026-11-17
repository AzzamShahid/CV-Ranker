# TextileHR AI v4.9.71 RC1 · Release notes

**Assessment protocol 57.** This is an **offline engineering release candidate**, not a production-qualified build. The v4.9.70 RC1 source archive is the verified ancestor; the separate v4.9.68 Windows-compatible baseline was unavailable.

## Repaired behavior

- The candidate can complete Found/Transferable/Not Found through unified and configured legacy supervisor paths; incomplete provider calls remain distinct and unscored.
- Independent compound review is dispatched even in the legacy LLM route, iterates through all eligible rows in bounded batches, and preserves completed siblings.
- A genuine provider rate-limit may Resume when retry-eligible. Typed HTTP 429 and Retry-After are used when provided; unknown-delivery attempts are not blindly duplicated. Retry count and previous failure transitions remain traceable.
- A successful compound adjudication is committed to an atomic, private, SHA256-verified local result store linked to the operation ledger. A fresh run can recover it without the prior in-memory report; corrupt and missing files never fabricate completion.
- The canonical finalizer validates all cited verdicts, including Transferable and Not Found, against original candidate segments; synthetic model evidence cannot attest itself. Truthful exact contextual citations for a Not Found decision are allowed without positive credit.
- A repeated structurally valid semantic dispute is not incorrectly called malformed JSON; explicit adjudication/work-required condition prevents unsupported negative or positive credit.
- Weighted official scores/ranks are withheld for incomplete candidate assessments; genuine verified zero remains 0.00. Completed results survive JSON/ZIP projection and restarted, compatible scoring tests.
- Legacy regression tests for now-prohibited model uncertainty were migrated without removing tests or granting fallback positives. Strict source integrity checks stay active.
- The future-feature extension interfaces are documented, but no hypothetical future feature was invented.

## Observed software evidence

- Seven DA probe tests were originally RED against v4.9.70 RC1; then GREEN on this successor. The protected strict verifier runs 117 focused tests (before final package checks).
- Broad dependency-limited execution: **1,554 passed, 20 failed, 10 collection errors**. Every remaining failed node or collection failure is classified as unavailable pinned Streamlit/LangChain runtime dependencies; full supported suite remains **unexecuted**.
- Windows, authenticated cloud/Ollama, human-adjudicated model quality and exact Windows-compatible historical baseline integration are open gates.

See `V4971_ISSUE_REGISTER.csv`, `V4971_BROAD_FAILURE_DISPOSITIONS.csv`, `V4971_RELEASE_QUALIFICATION.md`, and `V4971_WINDOWS_QUALIFICATION.md`.
