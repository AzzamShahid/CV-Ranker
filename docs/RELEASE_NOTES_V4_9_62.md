# CV Ranker Supervisor Edition v4.9.62 — Forensic Decision Integrity & Security Repair

**Release date:** 12 November 2026 (Asia/Karachi)  
**Build:** `phase7g-v4-9-62-forensic-decision-security-repair-2026-11-12`  
**Assessment protocol:** `segment_ids_semantic_llm` **v48** (previous v47)  
**Scope:** supervised, local review; **not qualified for unattended hiring or shared/public production**.

## Executive disposition

Version 4.9.61 passed a large packaged suite yet a separate forensic audit demonstrated **both directions** of score corruption: unrelated initial words could be treated as a required named system, and an allowed member of a three-way OR list could be rejected. Those failures were reproduced before editing. This release corrects confirmed deterministic source/decision defects and addresses related evidence ingestion, cloud request handling, score display, cache and persistence weaknesses.

Do not import old v47 decisions as new v48 assessed outcomes. Preserve v47 files for historical viewing. Changing frozen JD semantics, extraction or validators requires new assessment. Editing **only** scoring weights does not call the model.

## Changes by area

1. **Named-system and OR/AND conditions (`assessor.py`, `unified.py`, `requirement_typing.py`).** Unrelated initials such as *equipment repair procedures* cannot prove `ERP`. A named match must be present in original source, explicitly expanded by the JD, or supported by a separately grounded reviewed alias. The two-/three-/four-way coordinated OR guard now evaluates allowed branches correctly and preserves mandatory sibling conditions and performed-work requirements. Prospective and negated mentions remain blocked. A model-proposed positive is **not** proof on its own. One legacy test relying solely on inferred acronym equivalence was updated to reflect this more conservative policy; genuine expansions not explicitly established by the JD may need reviewer approval.
2. **Duration meaning and JD fallback (`requirement_typing.py`, `fallback.py`).** Retaining records for seven years is a duty, **not seven years of candidate employment**. Explicit professional tenure stays numerical. The HR example no longer pulls a subsequent role-description paragraph into the Preferred list. JD semantic review remains necessary for genuinely ambiguous prose and unseen wordings.
3. **Provider redirect boundary (`llm.py`).** The authenticated OpenRouter client refuses HTTP redirect responses instead of following an external redirect that might receive a bearer token or CV payload. Offline intercepted-response regression includes the original 302 exposure scenario; real provider traffic was not exercised.
4. **Applicant evidence extraction (`documents.py`).** DOCX document header/footer text is included as source rather than silently dropped. Image-only or scanned-heavy pages in a mixed PDF raise an actionable extraction diagnostic before the system treats partial extracted text as complete. No OCR implementation or universal image-page detector is claimed; real complex layouts still need review.
5. **Verified versus unavailable scores (`weighted_scoring.py`, `report_bundle.py`).** A missing assessment score is now **Unavailable** in final exported CSV/ZIP, not `Verified`. A completely evaluated genuine zero remains `Verified`; incomplete candidates preserve lower/upper provisional bounds.
6. **Configurable JD group allocation (`weighted_scoring.py`, `ui/dashboard.py`, `recovery_bundle.py`).** Default remains one pooled Requirements category. A new **explicit opt-in** weighted split mode allocates JD Requirements to Required and Preferred shares, then normalizes within each group. The older `split_jd` control remains display-only for historical compatibility. Changing weights makes zero LLM calls.
7. **Stale-source reuse (`resume.py`).** Document extraction logic is included in assessment fingerprinting so changed parsing cannot silently reuse the same previously assessed ledger under an unchanged build. v48 versions the decision protocol.
8. **Signing-key initialization (`recovery_bundle.py`).** Publish a fully initialized private recovery key atomically on first use, avoiding the former reader-visible empty key window; prior valid keys are left intact. Linux synthetic concurrent tests pass; native Windows and process-death stress require qualification.
9. **Optional remote dependencies (`requirements-remote.txt`, `production_preflight.py`, security guide).** Pin `streamlit[auth]` separately from local runtime; remote preflight reports missing Authlib. This is **not** remote deployment approval.
10. **Actual supervisor evaluation (`evaluation/evaluate_supervisor.py`).** New deterministic offline assessment runs `CVRanker(unified=True)` including validation, final status, base score and ZIP projection, rather than benchmarking the legacy fallback path alone. Historical fallback evaluations remain available and must be labeled separately.

## Observed before/after examples (fictional, controlled responses)

| Fixture | Old v4.9.61 | New v4.9.62 | Scope |
|---|---|---|---|
| JD: `Use ERP for production reporting`; CV: `Managed equipment repair procedures for production reporting` | False `Found`, 100 | **No direct credit**; deterministic unified stub: `Not Found`, 0 | Source initials alone no longer accepted |
| JD: `Use ERP, MES or SAP for production reporting`; CV: `Used ERP dashboards for production reporting` | `Not Found`, 0 after second call | `Found`, 100 after one stubbed call | Source-cited direct ERP work |
| Same JD with direct MES evidence | Could fail named gate | `Found`, 100 | OR alternate verified |
| Same JD with direct SAP evidence | Could fail named gate | `Found`, 100 | OR alternate verified |
| JD: `Use ERP or manufacturing execution systems (MES) ...`; direct ERP report evidence | `Found`, 100 | `Found`, 100 | Preserves v4.9.61 working control |
| JD: `Maintain financial records for at least 7 years` | `kind=experience`, `minimum_years=7` | **Non-tenure work responsibility**, no candidate tenure threshold | Context matters |
| HR sample JD fallback | 9 criteria (extra Preferred description) | **8 criteria: 6 Required / 2 Preferred** | Source/priority check |
| Nonempty JD, zero completed candidate rows | Blank score, incorrectly `Verified` in ZIP | Score/position `Unavailable` | Do not confuse with verified score 0 |
| JD-only 100 points; one Required Found, one Preferred Not Found; share 90/10 | Legacy split toggle shows 50 | Default pooled 50; explicit weighted split **90** (or 10 with 10/90) | Opt-in changes score, not model decisions |

## Test and environment evidence

- **Deterministic offline supervisor path:** 7/7 named-control fixtures pass with controlled provider replies; not an independently adjudicated live model benchmark.
- **Focused regression tests:** 97 passed across the v4.9.62 audit cases and related prior suites in the latest focused run. See `tests/test_v4962_forensic_release.py` and `evaluation/evaluate_supervisor.py`.
- **Wider offline collection in this development container:** 1,370 passed; 22 dependency-limited failures; 10 test modules had import/collection errors for the same unavailable Streamlit/LangChain dependencies. **This is not a fully passing suite.** Runtime has Python 3.13.5 rather than the user's Windows Python 3.11 installation.
- **Not executed here:** native Windows launchers and UI screenshots, full dependency-complete test run, Ollama/EmbeddingGemma inference, live OpenRouter response/cost benchmark, real applicant CV 6/7/8 replay, end-to-end IdP/TLS remote deployment and malware/advisory scan.
- Run from an isolated new folder with your private `.env`, preserving the prior release and user data. `run_runtime_check.cmd`, `run_tests.cmd`, `run_ui.cmd` are included. On local supervised operation, technical Unverified remains visible when evaluation really cannot complete; we do not reinterpret it as a candidate failure.

## Migration, privacy, rollback

- v47 exported results remain historical. **Do not resume v47 assessments and present them as v48 recalculations.** Re-run approved JD and CVs under v48; preserve prior source/report files separately.
- Keep HMAC recovery signing keys in private storage. Signed ZIPs may still contain readable CV content; HMAC **does not encrypt**.
- Updated OCR coverage rule may interrupt CV assessment that was previously allowed to proceed with missing scan page text. This is an intentional **fail-closed behavior**, not a lost qualification or provider problem.
- An implicit standalone CV acronym expansion may now be rejected when the JD did not establish the expansion and no reviewed alias exists. This conservatively avoids the demonstrated false-Found loophole. Supply an approved alias or source evidence before credit.
- Roll back by starting the preserved, unmodified v4.9.61 folder with its own state namespace. Do **not** rewrite v48 reports to v47 or mix checkpoints. Compare source-backed differences before re-scoring.

## Remaining blockers

The 13-finding implementation ledger differentiates coded fixes from test limitations. The broad JD-meaning model, universal source layouts (including OCR), held-out live accuracy, native Windows concurrency and remote data-security deployment are **not complete**. This patch is suitable for controlled local supervisor review **after your own Windows smoke tests**, not unattended or public production.
