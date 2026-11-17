# TextileHR AI v4.9.66 / protocol v52 — engineering release dossier

**Date:** 13 November 2026.  **Source baseline:** uploaded v4.9.65 / v51 SHA-256 `3f15f08d9d28b5bf21c43d34043de781114ac81713878cc60bc9b1c93ad1c3cd`. **Build:** `phase7g-v4-9-66-differential-integrity-repair-2026-11-13`.

## Scope and truthfulness

This is a usable **local supervisor engineering source release** with specific repaired failures and offline qualifications. It is **not** an independently accuracy-calibrated autonomous applicant ranking system. No real applicant file, OpenRouter key, cloud API request, paid tokens, local Ollama assessment, Windows Streamlit AppTest or externally reviewed gold dataset was used. Remote/multi-user deployment is **not approved**.

## Directly reproduced eight current defects

The independent differential runner uses unmodified v51 and candidate v52 in **separate Python processes**, with separate caches, source hashes, build IDs and synthetic inputs. `verification/v4966_differential_results.json` contains complete sanitized before/after records.

| RECENT issue | Baseline v51 reproduced | Candidate v52 observed | Primary production repair |
|---|---|---|---|
| 001 | Weighted score floor 90, bounds floor 50 in 90/10 split | Both 90; ceiling 100 | `weighted_scoring.py` uses one source of allocation math |
| 002 | Unknown-priority JD item raises `KeyError('unknown')` | Original priority retained, 90-point required-side allocation | `jd_scoring_group` applied consistently |
| 003 | SQLite `TEXT` in BLOB returns raw `TypeError` | Typed `EmbeddingError`, healthy keys unaffected | `semantic/cache.py` storage-class/shape checks |
| 004 | -0.001 and 100.001 rounded into accepted 0 and 100 | Both rejected before quantization, no mutation | `rebalance_requirement_share` raw bounds |
| 005 | Approved two-work-duty prior Found stays verified via early preservation | Mandatory approved conditions trigger source-bound review before score | `compound_validation.py`; model citations retained pending validation |
| 006 | Found with one approved OR option + unused missing option remains Unverified | Found when all mandatory facets and selected OR branches pass | `condition_review.py` evaluates reviewed groups and nested expression |
| 007 | Independent review stores 0 component proof records | Four facet provenance records retained in controlled case | `CompoundCheck.components` with original S IDs, JD offset, status/role |
| 008 | Missing resume source aborts batch with `FileNotFoundError` before loop | Healthy slot processed; missing slot failed/unavailable | `source_snapshot.py`, `pipeline.py`, `ui/dashboard.py` |

**Provenance limitation:** condition-level evidence uses an independently source-bound model proposal and exact cited quotes for explicitly approved nested expressions. A model can still misinterpret an authentic unrelated passage; this is a residual semantic entailment risk. Strongly worded model statements alone never externally validate employment/credentials. The source-only syntactic guard is not an accuracy proof.

## New structural controls

- Exact-offset `JDConditionNode` leaves plus nested `all_of` / `any_of`; full-scope editor validation rejects overlapping, invented, repeated or silently omitted substantive JD spans. Partial legacy annotations remain reviewable and are never a substitute for a complete authored tree.
- Condition-level reviewer reports every leaf and accepted original source. An unused OR branch may be missing; a mandatory sibling may not. Invalid or unsent citation IDs, fabricated JD source text and missing approved source quotes do not acquire full credit. The reviewed one-row denominator is unchanged.
- `CompoundCheck.components` retains original source IDs, facet relation, exact JD positions and group metadata across JSON serialization and report exports. Historical components without new fields deserialize without fabricated proof.
- Temporary candidate source bytes are captured **once** (10 MiB limit), parsed from the same captured bytes, and hashed into a v51-compatible identity. Failures are isolated per slot. Equal basenames are never silently reused from ambiguous prior slots.
- Local SQLite `operation_ledger.py` atomically claims review operation signatures before dispatch. Subsequent concurrent/local restart claims are refused. An interrupted claimed or unknown delivery requires checkpoint/recovery review before an authorized new request: no blind paid retry. Claims are digests, not prompts or CV text; remote exactly-once is *not established*.
- Scoring projections distinguish empty/no-assessment **Unavailable** from verified zero and provisional lower-bound. All changes to policy weights are calculations, not LLM calls.

## Installed dependency and host limits

Available interpreter: Linux Python 3.13.5; Pydantic, pytest, NumPy and document libraries are installed. Streamlit, `langchain_core`, `langchain_ollama` are missing. The baseline full suite recorded **1,449 passed, 22 failed, 10 import/collection errors** here. The candidate suite recorded **1,470 passed, 22 failed, 10 collection errors**; 20 failures are missing dependencies and two require an unavailable configured LLM. The full suite is **not green**. See `verification/v4966_test_evidence.json` for IDs and exact accounting. These failures are not hidden by skipping. A native Windows Python 3.11 dependency-complete test suite and actual Ollama/OpenRouter execution are still gates, not passes.

## Migration, rollback, and permitted use

1. Keep the supplied v51 ZIP as read-only rollback; never overwrite user `.env`, private recovery keys or source CVs.
2. Extract v52 into a **new** Windows directory. Use a clean Python 3.11 environment and install declared `requirements.txt`. Start Ollama and install the selected embedding model if actually needed.
3. Review the employer JD again and reassess candidates under protocol v52. Older v51 reports can be inspected as **historical**. Do not silently certify v51 statuses as v52 outcomes.
4. A weight-only change should not reinvoke assessment; changing source bytes, reviewed JD semantics, selected provider/model or decision-bearing code invalidates compatibility. Organization branding is display-only.
5. Run `run_runtime_check.cmd`, `run_tests.cmd`, `run_ui.cmd`; follow `verification/VERIFY_ON_WINDOWS.md` for precise acceptance checks.
6. ZIP recovery archives are integrity signed **but readable plaintext**. Do not email/export protected applicant data without approval. OpenRouter mode sends CV excerpts to a third party.
7. Remote shared deployment remains blocked until approved SSO/OIDC, TLS, tenant isolation, data encryption, retention/deletion, durable worker/cost controls and access tests.

## Release qualification verdicts

| Gate | Verdict |
|---|---|
| Source-level eight-defect repair | IMPLEMENTED; controls VERIFIED_OFFLINE |
| Deterministic 7+15 scripted supervisor controls | VERIFIED_OFFLINE (not independent accuracy) |
| Clean ZIP and manifest extraction | VERIFIED_OFFLINE after packaging (see evidence JSON) |
| Native Windows Python 3.11 GUI/tests | NOT VERIFIED |
| Local Ollama model-quality benchmark | NOT VERIFIED |
| OpenRouter actual provider accuracy, cost, latency and caching | NOT VERIFIED; billable trials unauthorized |
| Independently adjudicated held-out cross-domain assessment | NOT VERIFIED; require external labels |
| Remote/tenant production security | BLOCKED / outside local release scope |

**Residual blockers:** Single final-decision owner across every legacy/optional path; full narrative JD source coverage and unusual layouts; optional OCR with reviewer provenance; live model semantic truth; complete cross-process provider idempotency; full Windows and human adjudication. See traceability register. Do not describe this release as production-ready for automatic hiring.
