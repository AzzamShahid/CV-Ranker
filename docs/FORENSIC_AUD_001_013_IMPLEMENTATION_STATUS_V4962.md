# v4.9.62 Forensic AUD-001…AUD-013 implementation & verification ledger

**Basis:** 12 November 2026 independent v4.9.61 forensic audit and exact v4.9.61 ZIP SHA-256 `1f9fe38946a586820463df69f8b868ebc741b069d38aa9cec3ef1c7c3a99eafa`. Current build **v4.9.62 / protocol v48**. Reproductions used fictional candidates and stubbed provider replies, not real applicant records or a cloud account. Working copy kept separate. This is a development engineering ledger, not remote-production acceptance.

| Audit | Diagnosis | Implemented change / source | Regressions and observed checks | Current disposition |
|---|---|---|---|---|
| **001** | Unrelated acronym initials earn direct Found | `assessor.py`, `unified.py`: candidate source must actually attest term, explicit JD expansion, or separately approved alias; avoid generic initials | `test_unrelated_initials_and_non_performed_mentions_cannot_award_erp`, unified `erp_false_initialism`, 4-option positives | **Fixed for reproduced class**, broader semantic aliases may require human review |
| **002** | Three-way OR wrongly requires extra branches | `assessor.py` alternatives parser, `requirement_typing.py` shared-work coordination | `test_three_way_alternative_any_branch`, `test_four_option_list_and_mandatory_sibling`, unified ERP/MES/SAP; pre/post score | **Fixed for curated coordinated lists**; unconstrained prose still reviewable |
| **003** | Retention period mapped to candidate experience | `requirement_typing.py`: duration subject/scope review before minimum tenure | `test_duration_scope_must_be_candidate_tenure`; 7-year retention vs explicit professional years | **Fixed for controls**, unseen time expressions require JD semantic review |
| **004** | Cross-origin redirect forwards cloud bearer | `llm.py`: refuse all redirects at actual authenticated urllib transport | `test_cloud_transport_does_not_follow_redirect_with_token` intercepted 302 and dummy bearer; no external request | **Mitigated**; full 301/302/303/307/308 variants and live provider not qualified |
| **005** | DOCX header / image-only PDF page silently omitted | `documents.py`: headers/footers + scan-page warning instead of partial silent success | `test_docx_header_degree_is_not_silently_lost`; `test_mixed_pdf_image_only_qualification_page_blocks_scoring` | **Partially repaired**; no OCR, not all exotic PDF/DOCX layouts guaranteed |
| **006** | Missing score exported as Verified | `weighted_scoring.py`, `report_bundle.py` canonical unavailable status | `test_unavailable_score_is_not_exported_verified`, `test_verified_zero_remains_verified_not_unavailable` | **Fixed for reproduced CSV/ZIP states**; Windows UI visual test pending |
| **007** | Benchmark uses legacy path, not supervisor engine | `evaluation/evaluate_supervisor.py` uses `CVRanker(unified=True)` with deterministic stub, publishes status/call/score | `test_actual_unified_supervisor_branch_has_offline_regressions`; `python -m evaluation.evaluate_supervisor` **7/7** | **Engineering path repaired**, independent/live cross-domain benchmark remains unverified |
| **008** | Split visual toggle ignores configured Required share | `weighted_scoring.py` explicit `jd_allocation_mode=weighted_split`; dashboard control; recovery snapshot | `test_opt_in_weighted_split_and_legacy_display_split` pooled 50, opt-in 90 and 10 | **Implemented and offline verified**; new opt-in policy, old snapshots preserved |
| **009** | Equivalent JD verbs classified inconsistently | `requirement_typing.py` broader general action handling; preserves review | `test_equivalent_operational_duties_type_consistently` customer complaints / fabric inspection | **Partially improved**, not a comprehensive model-based cross-domain semantics rewrite |
| **010** | Parser edits omitted from cache assessment context | `resume.py` includes `documents.py` in logic fingerprint | `test_ingestion_logic_is_in_resume_fingerprint`; source hash changes trigger invalidation | **Fixed for named omitted parser dependency**; broader dependency inventory future |
| **011** | First-use recovery key published empty until write complete | `recovery_bundle.py` write temp then publish atomic hard link | `test_key_publication_is_atomic_for_two_readers` controlled reader/writer interleaving | **Repaired in Linux test**, native Windows/kill-process not independently verified |
| **012** | Remote OIDC install misses Streamlit auth extra | `requirements-remote.txt`, `scripts/production_preflight.py`, `docs/PRODUCTION_SECURITY.md` | Static optional dependency check and fail-closed preflight | **Package config implemented**, live IdP/security test incomplete; remote NOT approved |
| **013** | HR role description extracted as extra Preferred | `fallback.py` paragraph/list boundary handling | `test_fallback_excludes_role_description_but_preserves_explicit_criteria`; six Required plus two Preferred | **Fixed for bundled HR fixture**; narrative JD gold coverage future |

## What has NOT been established

- These deterministic cases do not establish universal source entailment, fairness or performance for actual applicants. The original CV 6/7/8 source ledgers and model outputs were not supplied to this run.
- The implementation plan also requested independent held-out live tests and native Windows validation; unavailable here. The included seven-case engine benchmark is useful but **not sufficient for release accuracy certification**.
- Domain-neutrality is a design requirement: production matching code has no candidate name, R015 or ERP/MES hard-coded answer exceptions. Named examples in tests do not constitute special-case production behavior.
- Signed restart archives are **plaintext**; local operating-system permissions matter. Cloud-assisted mode sends private excerpts to the selected provider with operator authorization and spend caps. Public/multi-user production remains blocked.
- A changed protocol and parser require a **fresh** assessment. Weight-only changes do not rerun models. Prior v47 checkpoints are historical, not revalidated under v48.

## Commands and release evidence

```powershell
.\run_runtime_check.cmd
.\run_tests.cmd
.\run_ui.cmd
```

Offline development checks:

```text
python -m pytest -q tests/test_v4962_forensic_release.py
python -m evaluation.evaluate_supervisor --output <temporary output path>
python -m scripts.production_preflight
CVR_STRICT_SOURCE_HASHES=1 python -m cv_ranker.runtime_check
```

Full pinned requirements install is needed before judging all test modules; 22 failures and 10 collection/import errors occurred in this container from missing Streamlit/LangChain. Native Windows runner, actual provider and independently adjudicated CV replay are outstanding acceptance gates. Track failures and source identities separately from final Found/Transferable/Not Found/Unverified decisions.
