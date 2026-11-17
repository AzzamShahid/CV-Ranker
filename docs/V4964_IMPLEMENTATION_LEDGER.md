# v4.9.64 implementation and verification ledger — R0–R9

**Date:** 13 November 2026. **Starting source:** exact v4.9.63 ZIP SHA-256 `c0d7f3a44f3b727ee2c5a744bd4fd5dba0cf7d3250d8335889f48d33b794b2d7`, protocol v49. **This release:** v4.9.64, protocol v50. A separate copy was used; no real CVs, cloud keys or live providers were used in tests. This ledger is **engineering evidence**, not remote-production acceptance.

## Implemented changes and safety boundaries

| Change ID | Status | Source implementation and acceptance evidence | Remaining limitation |
|---|---|---|---|
| 64-01 Original JD source coverage | **IMPLEMENTED / VERIFIED_OFFLINE** | `jd_coverage.py`, `pipeline.py`, `jd_review.py`, `ui/dashboard.py`: exact original structural clauses + line numbers mapped to frozen R; approval recomputes after deletion; review table and diagnostic warning; `test_v4964_coverage_semantics_diagnostics.py` | Complete narrative JD gold coverage, complex heading inheritance, explicit acknowledgement not proven |
| 64-02 Evidence modality and duration subject | **IMPLEMENTED / VERIFIED_OFFLINE** | `schemas.py`, `requirement_typing.py`, `unified.py`, `jd_review.py`: distinguish knowledge/work/tenure/completed degree; unrelated retention years not candidate tenure; model packet field and metadata tests | General semantic classification and reviewer-approved condition-tree UI still incomplete |
| 64-03 JD correction failure codes | **IMPLEMENTED / VERIFIED_OFFLINE** | `jd.py` passes exact initial validator rejection even without diagnostic logging; distinct zero-row repair objective; new fixed-response tests | Not all structured extraction failure classes or repeatless restart recovery implemented |
| 64-04 Typed technical Unverified notes | **IMPLEMENTED / VERIFIED_OFFLINE** | `failure_diagnostics.py`, `unified.py` per-R sanitized IDs, categories and next actions; unit suite | No durable cross-process attempt identity/operational full state machine |
| 64-05 Gross unrelated duty rejection | **IMPLEMENTED / VERIFIED_OFFLINE** | `source_subject_guard.py` with source-attributed negative guard for freshly typed work; `assessor.py`; 15-case actual unified supervisor *stub* adversarial evaluation; model falsely proposes direct Found on unrelated acts, independent validator refuses direct credit | A full semantic entailment proof remains model/reviewer-dependent; genuine zero-word-overlap synonyms may require review; not a perfect NLP parser |
| 64-06 Inflected compound performed work | **IMPLEMENTED / VERIFIED_OFFLINE** | `compound_validation.py`: real multi-action duty stays Found when authentic cited completed work and AND work anchors support all arms; avoids rigid inflection; QA example plus unrelated negative controls | Full nested Boolean and semantic condition-tree evaluation not implemented |
| 64-07 3xx no credential forwarding | **VERIFIED_OFFLINE (intercepted)** | 20 intercepted redirect cases (5 status codes × 4 destinations), existing v48 302 test and v49 JSON serialization | No live OpenRouter call, proxy security review or native Windows test |
| 64-08 Cross-department controlled suite | **VERIFIED_OFFLINE (22 total cases)** | `evaluation.evaluate_supervisor` baseline 7/7; `--cross-domain` 15/15. Actual `CVRanker(unified=True)` → validators → scoring → ZIP; intentionally misleading synthetic provider | NOT independently human labeled or live-model accuracy. Some negative sources require up to three stub calls |
| 64-09 Cross-path legacy compatibility | **VERIFIED_OFFLINE for dependency-independent tests** | Old semantic-paraphrase/NLP and 2-R recovery tests restored green; new work guard requires typed modality to avoid changing old raw legacy fixtures | Full UI/Windows/provider tests blocked |
| 64-10 Prompt inventory | **SOURCE INVENTORY ONLY** | `docs/V4964_PROMPT_SOURCE_INVENTORY.json`: 12 prompts and 15 builders | Not all 12 prompts compactly rewritten, A/B measured or approved |

## R0–R9 status

| Gate | Current status | Key outstanding work |
|---|---|---|
| R0 baseline | **PARTIAL**: exact v49 input hash, old 7-case supervisor and source tests known | Full dependency-complete host UI and original incident CV replay |
| R1 old repairs | **PARTIAL, OFFLINE**: v48 false ERP initialism and named OR controls retained; intercepted 3xx tested; scoring unchanged | Full UI/CSV/JSON/ZIP visual/field audit on Windows |
| R2 JD/doc source | **PARTIAL, OFFLINE**: structural source coverage + new evidence modality + reviewer warning | Narrative/spans gold, OCR/rescan workflows, human-approved condition tree |
| R3 decision contract | **PARTIAL, OFFLINE**: gross mismatch guard and source-supported multi-action preservation | Single canonical decision owner across every legacy/focused/unified path |
| R4 frozen date | **CARRIED FROM v49, OFFLINE** | Native Windows and live-model temporal qualification |
| R5 12 prompts | **PARTIAL, SOURCE INVENTORY**: v49 JSON-safe builders, independent focused and batch-schema policy preserved | Unified versioned compact policy and paired live A/B measurements |
| R6 productive recovery | **PARTIAL, OFFLINE**: typed per-R failure explanations; preexisting bounded correction remains | Durable attempt state, process-death idempotence, no-repeat signature across UI restart |
| R7 security/cost/cache | **PARTIAL, OFFLINE**: redirect 3xx checks, source fingerprint includes new code, no new billable calls | Real usage/cost/cached tokens, prompt injection full-path and Windows key race |
| R8 independent benchmark | **NOT QUALIFIED**: 7+15 actual supervisor-engine stub controls | Independently adjudicated holdout, provider/model timing, token and quality measurements |
| R9 release qualification | **NOT QUALIFIED**: clean package and strict hashes can be checked offline | Windows 3.11 install/start/test/UI, full dependency-complete green suite, model and HR acceptance |
| R10 shared/remote | **REMOTE_BLOCKED** | Separate authorized OIDC/TLS/tenant-encryption/retention/durable jobs/security audit |

## Full-suite evidence and environment limitation

The available test environment is **Linux, Python 3.13.5**. The dependency-complete Windows Python 3.11 environment is not available. An attempt to install `streamlit==1.65.0`, `langchain-core==1.6.5` and `langchain-ollama==1.1.0` failed because the configured package index's hostname could not be resolved. **Do not treat these as passing tests.** The last pre-version wider suite: **1,406 passed, 22 failed, 10 collection/import errors**, all remaining failures involving absent Streamlit/LangChain/provider environment. A subsequent new source manifest and clean-ZIP verification must be recorded as separate evidence. No live OpenRouter calls or candidate-data uploads occurred.

## Migration/rollback

The source contract changed, so protocol v50 cannot silently reuse v49/v48 model judgments. Preserve those reports as historical, re-extract and review the original JD/CVs for v50. The source release never contains `.env`, raw applicant CVs, HMAC secret, local embeddings or private checkpoints. Scores use frozen Found/Transferable/Not Found/Unverified rules with Transferable worth zero and default combined Required + Preferred pooling. Local supervised use only; never assert autonomous hiring/remote readiness.
