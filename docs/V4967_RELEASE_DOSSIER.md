# TextileHR AI v4.9.67 / protocol v53 — engineering release dossier

**Date:** 14 November 2026. **Input:** exact v4.9.66/v52 release ZIP with SHA-256 `1e1c8d6e682e1fcf53d2127a9c9d50d79c80b2c1ec47ac22a5d12510fd96eb09`. Original untouched. **Candidate build:** `phase7g-v4-9-67-recovery-oracle-repair-2026-11-14`.

## Implemented source repairs

1. **NEXT-001:** `LocalOperationLedger.claim_each` atomically partitions claimed and already-held operation signatures. Existing complete/unknown A no longer blocks fresh B. The independent condition review selects only newly owned rows, scans past blocked rows up to the configured batch limit, stamps only sent rows, and saves per-operation terminal state with a SHA-256 reference for verified results. A migrated v52 table is updated without losing prior states. An uncertain provider delivery is not retried automatically. Preflight errors are recorded without fictitious provider calls.
2. **NEXT-002:** The old differential runner returned success when comparing v52 with itself. The new runner requires distinct physical trees and manifests; verifies hashes of all listed files and no unlisted Python sources; checks child module imports, build/protocol identity, a versioned independent oracle for every required probe, and nonzero errors for wrong/missing/timeout/crash/mutated outputs. It supports authentic historical v51→v52 and current v52→v53 comparisons separately.
3. **R3 defense-in-depth:** The active unified supervisor finalizer verifies matched original `S###` references, exact candidate source text and section against the actual source ledger before allowing a verified Found. Forged/mismatched evidence remains technical Unverified, not Not Found or full credit. Existing standalone/legacy policy paths remain unchanged; complete consolidation is still open.
4. **Condition review completeness:** A free-form complex JD cannot claim full Found on arbitrary satisfied fragments while leaving a substantive clause unexamined. Source-exact facets must span every non-connector JD word; a complete original-source reviewed tree is still preferable. An all-uncertain facet report cannot produce verified Not Found. Independently valid rows in a structurally partly malformed batch survive; invalid siblings remain Unverified.
5. **Source/retry identity:** Condition-review operation keys now bind relevant model settings, response-schema hash, immutable assessment date, JD meaning, whole candidate source hash, and prompt; batch dispatch stores the hash of the actual outgoing packet. The operation database stores no source prose, credentials or raw responses.
6. **R8 runnable human-label preflight:** A standalone tool checks double-blind independent reviewers, mandatory adjudication of disagreement and candidate/document/JD/wording-family leakage across development/tuning/holdout. It DOES NOT invent labels or calculate live-model accuracy.

## Demonstrated failure and repair

| Gate | Original v52 | v53 verified offline |
|---|---|---|
| NEXT-001 mixed A+B | A existed; B not sent; both stamped | B sent alone once; A not stamped; B result independently recorded |
| NEXT-002 same-tree differential | Returned exit 0 | Returns nonzero without running a misleading comparison |
| Copied/symlinked/reversed builds | Not authenticated | Rejected by source identity/version checker |
| Missing/altered probe or child import root | Could be accepted if process succeeded | Rejected by independent versioned oracle |
| Partial malformed model batch | Valid sibling could be discarded | Unique, structurally valid sibling verified independently; malformed row remains unresolved |
| Verified Found with forged citation at final scoring | Not checked by canonical finalizer itself | Requires exact original candidate ledger match in actual unified run |
| Unreviewed JD with uncovered material qualifier | Could be supported by arbitrary two short facets | Not Found/Found cannot be claimed without adequate original JD scope |

**Test intent:** All differential inputs, JD/CV fixtures and model replies are fictional; external provider calls are **zero**. Passing a scripted model fixture is not a general accuracy estimate. The vendor may still hallucinate semantic entailment even when its citation is genuinely present.

## Scope still OPEN

- R2: complete narrative JD/source-span adjudication and unreadable scanned-page/OCR workflows.
- R3: one canonical decision owner across all *legacy, optional, fallback, UI* routes; human-adjudicated equivalence against unrelated but genuine sources.
- R4: independently reviewed multi-role tenure and credential complexity in varied layouts.
- R5: A/B-quality-tested prompt and dynamic-builder alignment. Source inventory consists of 13 prompt definitions and 16 builder/caller references, **not** a quality benchmark.
- R6: durable reconciliation when a provider accepts a request, charges, returns a response, then the process dies before checkpoint commit. SHA references are not plaintext result storage and cannot reconstruct missing evidence. Local claim policy deliberately **blocks** the uncertain retry.
- R7: real-provider token/latency/cost cache measurements; full native Windows concurrency/security/privacy testing.
- R8: two independent *human* annotators and an adjudicated unseen gold set; no actual live benchmark metrics.
- R9: native Windows Python 3.11 dependency-complete Streamlit UI/full suite/accessibility/source/Why/export/restore qualification.
- R10: shared/public remote use remains blocked pending identity/TLS/tenant isolation/privacy lifecycle controls.

**Use:** Local supervised decision support only. CVs are self-reported, model judgments are not independent credential verification. Signed checkpoint archives and reviewer ZIPs contain readable sensitive text and require appropriate handling. Preserve original v52 and historical v51/v50 reports for read-only rollback; a v53 report must come from a new v53 assessment, not be silently reclassified from v52. Changing weights alone does not require model calls.

## Executed test accounting (release candidate, before final ZIP extraction)

Environment: Linux Python 3.13.5 with pytest/Pydantic/PyMuPDF/python-docx; Streamlit, `langchain_core`, `langchain_ollama` and real Ollama/OpenRouter inference were unavailable. Exact commands and sanitised logs are recorded in the separately supplied release verification artifacts.

- `python -m pytest -q --continue-on-collection-errors`: **1,496 passed, 22 failed, 10 collection errors**. This is NOT a green suite. Twenty failures are missing Streamlit/LangChain imports; two older transferability integration tests require an explicitly configured LLM. The ten collection errors involve missing Streamlit imports. No such failure was reclassified as passed.
- Focused regression command using `tests/test_v4967_*`, relevant previous defect and supervisor modules: **78 passed**.
- Controlled actual `CVRanker(unified=True)` supervisor regressions: **7/7 original** plus **15/15 adversarial cross-domain**, with synthetic provider responses only; not a measured independent hiring accuracy benchmark.
- `scripts/prompt_inventory.py`: **13 prompt assignments, 16 builder/caller references**; no real-model prompt A/B completed.
- Source runtime manifest strict verification passes. Final ZIP extraction, hash check and patch application must be verified against the actual packaged output rather than assumed from this source tree.

A prior full-suite run surfaced an older synthetic resumed-assessment test whose fake model returned a bare Found without any S citation. The fixture was strengthened to supply the original source ID/unchanged text while retaining its existing expected 100-point result and original assertions; the source-bound finalizer was **not** weakened. That correction is included in the patch and was rerun.
