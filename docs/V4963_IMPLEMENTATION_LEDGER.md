# TextileHR AI v4.9.63 — Executed Repairs, Test Evidence, and Open Gates

**Recorded:** 13 November 2026. **Input:** v4.9.62 forensic decision/security ZIP, SHA-256 `55224c5666df3c4684662b7b3bcbd98853f7ce1d5f0efc297b33bb5749499e16` (516 readable ZIP members). **Output:** source build `phase7g-v4-9-63-source-bound-prompts-frozen-date-2026-11-13`, protocol **v49**. These tests use fictional data, a deterministic provider and the present Linux/Python 3.13 environment; they do NOT qualify Windows, paid OpenRouter, or independent human model accuracy.

## Release verdict

**PARTIAL ENGINEERING IMPLEMENTATION; NOT R0–R9 COMPLETE; REMOTE BLOCKED.** This development run implemented source-safe request serialization in the legacy/JD paths, frozen date arithmetic through core assessment, selected prompt/schema repairs and a focused-review source/window consistency guard. It does **not** establish universal semantic correctness, remove every Unverified error, rewrite every prompt, or meet all local deployment acceptance gates. Original v48 project was preserved as a separate input ZIP and can be restored.

## Concrete source changes

| Change | Files | Verified behavior and explicit limitations |
|---|---|---|
| **S01: Source-safe JD prompt** | `cv_ranker/jd.py` | The complete uploaded JD and YAKE hints are JSON string/data fields rather than XML-like delimiters; embedded `</JD>` cannot break into a new request-level system section. Does not make an LLM immune to following malicious instructions. Tests `test_jd_and_legacy_cv_untrusted_source_is_json_bound`. |
| **S02: Source-safe legacy CV prompt** | `cv_ranker/assessor.py` | Serialized original candidate S IDs/sections/text and approved JD requirements; compact trusted R-ID manifest retains existing batching adapter. No CV text in manifest. Does not change the unified engine's existing JSON builder. Same tests; old 5-R batching tested. |
| **S03: Immutable dated-tenure clock** | `cv_ranker/assessment_clock.py`, `experience_validation.py`, `pipeline.py`, `schemas.py`, `unified.py`, `assessor.py`, `ui/final_decisions.py` | New initial run records ISO `assessment_as_of_date`, completed role tenure consults that context, resume retains it, mismatched explicit resume date is rejected, core tenure LLM packet includes it where relevant, focused judge gets saved report date. New date is not sent to pure skill-only unified packets to conserve context. Same-build manually fabricated reports without dates receive a new date; old builds are rejected by build protocol. Not yet verified with real local/cloud models or native Windows recovery. |
| **S04: Independent focused review and sent-source guard** | `cv_ranker/ui/final_decisions.py`, `evidence_bridge.py` | Previous model opinions no longer anchor focused prompt; context-limited source trimming is explicitly listed; a positive citing a removed/omitted S ID fails. Performed-work structural guard is broadened using existing shared positive-action recognizers, including prior valid `orchestrated` cases. Does not prove full domain-neutral verbs or that the final model semantic judgment is correct. |
| **S05: Nonfragile batch transferability schema** | `cv_ranker/semantic/transferability.py` | Explicit independent single/batch structured response wrappers reuse an explicit `RELATIONSHIP_POLICY`, without `.replace()` or marker slicing. Input/output schema clarity improves; no claim of improved real-model transfer recall. |
| **S06: Prompt inventory automation** | `scripts/prompt_inventory.py`, `docs/V4963_PROMPT_SOURCE_INVENTORY.json` | Source-only hashes/line locations for **12 system prompt assignments** and **15 actual builder/caller entry points**. Not a call-count trace or a completed 12-prompt semantic redesign. |
| **S07: Regression tests** | `tests/test_v4963_execution_repairs.py` | 13 new focused tests: injected delimiters and fake roles, JSON field provenance, nested clock context, dated Present, unified packet, resume preservation/rejection, source-omission guard, independent focused review and schema wrapper. Tests use fictional data; no external requests. |

## Baseline and observed tests

- Verified v48 baseline archive SHA-256 and ZIP readability in this run.
- Before changes, **99 focused v48 tests passed**, and the actual `CVRanker(unified=True)` seven-case controlled benchmark returned **7/7**. These are original v48 baseline numbers.
- During development, the first full run exposed genuine **compatibility regressions** from the date/schema edit (resume fixture date absent, a model test expecting trusted R-ID manifest, and uncommon valid completed-action evidence). They were fixed; **do not omit these from the engineering history**.
- After compatibility repairs and protocol v49: the selected combined forensic/new suite yielded **112 passed**. Record full-suite totals separately in the final release summary; dependency-limited Streamlit/LangChain failures were previously observed and remain a qualification blocker until installed.
- **Actual full available suite after manifest rebuild:** **1,383 passed, 22 failed, 10 import/collection errors** (Python 3.13.5 on Linux). Failures were primarily missing `streamlit` / LangChain/Ollama packages; two unified degree-transfer test cases raised `LLMError` when their real provider was unavailable. They were **not** counted as passes or silently skipped. This is **not** a green suite or a qualified Windows build. The preceding full run before manifest rebuild briefly showed an extra strict-manifest failure caused by the in-progress build-ID change; rebuilding and verifying the manifest resolved it.
- All runs were **offline**, with no paid OpenRouter inference, no native Windows execution and no independently labeled live hiring-quality benchmark.

## R0–R10 truth ledger

| Milestone | Current status | Evidence / next actions |
|---|---|---|
| **R0 / G0 baseline** | **VERIFIED_OFFLINE for source identity and focused controls; PARTIAL overall** | Exact v48 ZIP, tests and seven-case supervisor smoke reproduced; comprehensive live UI and all source trace paths not exercised. |
| **R1 / G1 existing repair safeguards** | **PARTIAL, VERIFIED_OFFLINE** | Preserved v48 13-finding tests; omitted-source positive, old transfer positive and injection encoding added. All redirect 3xx variants and full export UI parity still pending. |
| **R2 / G2 JD and document coverage** | **OPEN except safe JD serialization** | Source-to-R span coverage, scanned page OCR flow and broad cross-domain JD semantic labeling not implemented in this changeset. |
| **R3 / G3 canonical decision authority** | **PARTIAL** | Focused judge no longer anchors to prior opinions or accepts omitted S citations; single canonical condition/evidence transition contract across all assessment paths remains unfinished. |
| **R4 / G4 fixed dates and specialist semantics** | **PARTIAL, VERIFIED_OFFLINE** | Frozen-date role tenure and resumed-report date tested. Comprehensive mixed employment status/month arithmetic, end-to-end Windows and model fact parity remain open. |
| **R5 / G5 12 prompt alignment** | **PARTIAL** | 12 definitions and 15 callsites inventoried; JD and legacy request serialization plus single/batch transferability schema fixed. No controlled 12-prompt refactor/A-B live benchmark. |
| **R6 / G6 productive no-repeat recovery** | **OPEN for new implementation** | v48's existing bounded corrective source recovery preserved; full durable per-reason attempt ledger, process death and replay remain open. |
| **R7 / G7 adversarial and cost hardening** | **PARTIAL, VERIFIED_OFFLINE for JSON boundary tests** | No cloud cost claim. Complete injection, provider request-fit and secure restart tests pending. |
| **R8 / G8 independent benchmark** | **NOT QUALIFIED** | The seven-case deterministic supervisor-path smoke is retained, **not** live-label precision/recall. Held-out adjudication and provider usage/cost metrics pending. |
| **R9 / G9 final local Windows qualification** | **NOT QUALIFIED** | v49 engineering ZIP can be tested locally after extraction; Windows UI/run/test and clean full-suite acceptance remain outstanding. |
| **R10 / G10 remote multi-user production** | **REMOTE_BLOCKED** | No IdP/TLS, tenant isolation, encryption, provider agreement, durable queue or security acceptance. Not authorized as part of this run. |

## Forensic AUD-001…AUD-013 status

This changeset carries forward the **existing v48 narrow fixes**, not blanket new closures. AUD-001 and 002 (initialism/alternatives), 003 (record retention), 004 (redirect 302), 005 (DOCX header/mixed PDF scan warning), 006 (unavailable export), 007 (seven-case supervisor harness), 008 (explicit weighted split), 009 (noun/verb hints), 010 (parser cache), 011 (atomic key), 012 (optional auth dependency), and 013 (HR fallback) retain **the v48 forensic ledger's exact dispositions**. In this changeset, AUD-005/AUD-009 source-universality, AUD-007 actual-model qualification, AUD-011 native Windows race, and AUD-012 remote authentication have **not** been independently closed. See `docs/FORENSIC_AUD_001_013_IMPLEMENTATION_STATUS_V4962.md`.

## Compatibility and privacy

- **Version/protocol changed to v4.9.63/v49.** Changed prompt/source/date semantics require a fresh candidate assessment. v48/v47 results must be kept as historical, not recast as v49 verified decisions. Weight-only projections do not cause provider calls.
- User/private `.env`, CV uploads, embedding caches, signed recovery keys and reports are not part of this source package. HMAC recovery files are **not encrypted**.
- A saved run's date is frozen in its `RankingReport`; malformed old reports cannot be treated as independently tested on that date. Preserving source/date identity is necessary but not sufficient for all recovery reliability.

## Next executable priorities

1. Install the pinned dependencies into a clean Windows 3.11 virtualenv; run full pytest, supervisor Streamlit UI/Why/export, recovery-key multiprocessing and a fresh zip extraction. Record exact failure counts; do not label missing packages as successful tests.
2. Implement reviewed `RequirementMeaning` and source-to-JD span coverage with domain-independent semantics; keep employer ambiguity separate from candidate failure.
3. Complete canonical validator/finalizer and failure-specific productive retry ledger, preserving Transferable independently of direct points.
4. Align all 12 prompts and 15 builders to a versioned schema with frozen packet controls, then conduct authorized, independently reviewed model benchmarks.
5. Repeat all prior v48 negative/positive controls and compute source-verified vs technical coverage. Release only when gates R0–R9 meet their declared acceptance criteria; keep R10 separate.
