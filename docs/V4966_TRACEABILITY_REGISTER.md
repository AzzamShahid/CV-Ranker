# v4.9.66 / protocol v52 — source-specific traceability register

The 8 RECENT, 13 V4962 and 35 V4957 identifiers are independent namespaces. An old audit claim does not prove a current defect. Never count a past stub pass as a human/life-model acceptance.

## RECENT (8 current defects)

### RECENT-001 — VERIFIED_OFFLINE
- **Historical ID:** `AUDIT-001`; **source:** v4.9.65 / protocol v51
- **Expected:** Candidate details disagree with leaderboard
- **Code:** `cv_ranker/weighted_scoring.py`; **test:** `tests/test_v4966_current_defects.py::test_RECENT001_provisional_bounds_share_exact_split_formula_and_do_not_mutate_candidate`
- **Baseline observation:** {"consistent": false, "main_floor": 90.0, "reported_bounds_floor": 50.0}
- **Candidate observation/change:** {"consistent": true, "main_floor": 90.0, "reported_bounds_floor": 90.0}; v4.9.66 / v52: Candidate details disagree with leaderboard
- **Evidence class:** actual separate-process offline synthetic reproduction; **remaining:** Live model, Windows GUI and external human accuracy not qualified
- **Next step:** Run dependency-complete Windows and independently adjudicated held-out scenarios

### RECENT-002 — VERIFIED_OFFLINE
- **Historical ID:** `AUDIT-002`; **source:** v4.9.65 / protocol v51
- **Expected:** Unknown priority crashes weighted split
- **Code:** `cv_ranker/weighted_scoring.py`; **test:** `tests/test_v4966_current_defects.py::test_RECENT002_unknown_priority_uses_required_group_but_preserves_label`
- **Baseline observation:** {"crash": "KeyError"}
- **Candidate observation/change:** {"crash": false, "original_priority": "unknown", "score": 90.0}; v4.9.66 / v52: Unknown priority crashes weighted split
- **Evidence class:** actual separate-process offline synthetic reproduction; **remaining:** Live model, Windows GUI and external human accuracy not qualified
- **Next step:** Run dependency-complete Windows and independently adjudicated held-out scenarios

### RECENT-003 — VERIFIED_OFFLINE
- **Historical ID:** `AUDIT-003`; **source:** v4.9.65 / protocol v51
- **Expected:** Malformed SQLite vector bypasses repair
- **Code:** `cv_ranker/semantic/cache.py`; **test:** `tests/test_v4966_current_defects.py::test_RECENT003_SQLite_malformed_values_are_key_local_typed_corruption`
- **Baseline observation:** {"result": "TypeError"}
- **Candidate observation/change:** {"result": "EmbeddingError"}; v4.9.66 / v52: Malformed SQLite vector bypasses repair
- **Evidence class:** actual separate-process offline synthetic reproduction; **remaining:** Live model, Windows GUI and external human accuracy not qualified
- **Next step:** Run dependency-complete Windows and independently adjudicated held-out scenarios

### RECENT-004 — VERIFIED_OFFLINE
- **Historical ID:** `AUDIT-004`; **source:** v4.9.65 / protocol v51
- **Expected:** Raw bounds lost during rounding
- **Code:** `cv_ranker/weighted_scoring.py`; **test:** `tests/test_v4966_current_defects.py::test_RECENT004_reject_raw_invalid_shares_without_mutation`
- **Baseline observation:** {"-0.001": "ACCEPTED", "100.001": "ACCEPTED"}
- **Candidate observation/change:** {"-0.001": "ValueError", "100.001": "ValueError"}; v4.9.66 / v52: Raw bounds lost during rounding
- **Evidence class:** actual separate-process offline synthetic reproduction; **remaining:** Live model, Windows GUI and external human accuracy not qualified
- **Next step:** Run dependency-complete Windows and independently adjudicated held-out scenarios

### RECENT-005 — VERIFIED_OFFLINE
- **Historical ID:** `AUDIT-005`; **source:** v4.9.65 / protocol v51
- **Expected:** Mandatory duties lose their evidence gate
- **Code:** `cv_ranker/compound_validation.py`; **test:** `tests/test_v4966_current_defects.py::test_RECENT005_approved_expression_routes_initial_found_to_independent_review`
- **Baseline observation:** {"checked_status": "matched", "initial_status": "matched", "requires_condition_review": false, "verified": true}
- **Candidate observation/change:** {"checked_status": "uncertain", "initial_status": "matched", "requires_condition_review": true, "verified": false}; v4.9.66 / v52: Mandatory duties lose their evidence gate
- **Evidence class:** actual separate-process offline synthetic reproduction; **remaining:** Live model, Windows GUI and external human accuracy not qualified
- **Next step:** Run dependency-complete Windows and independently adjudicated held-out scenarios

### RECENT-006 — VERIFIED_OFFLINE
- **Historical ID:** `AUDIT-006`; **source:** v4.9.65 / protocol v51
- **Expected:** An unused allowed option can invalidate a correct Found
- **Code:** `cv_ranker/condition_review.py; cv_ranker/jd_expression.py`; **test:** `tests/test_v4966_current_defects.py::test_RECENT006_unused_or_branch_missing_does_not_veto_satisfied_nested_expression`
- **Baseline observation:** {"resolved": 0, "verdict": "Unverified"}
- **Candidate observation/change:** {"resolved": 1, "verdict": "Found"}; v4.9.66 / v52: An unused allowed option can invalidate a correct Found
- **Evidence class:** actual separate-process offline synthetic reproduction; **remaining:** Live model, Windows GUI and external human accuracy not qualified
- **Next step:** Run dependency-complete Windows and independently adjudicated held-out scenarios

### RECENT-007 — VERIFIED_OFFLINE
- **Historical ID:** `AUDIT-007`; **source:** v4.9.65 / protocol v51
- **Expected:** Condition proof disappears on save
- **Code:** `cv_ranker/condition_review.py; cv_ranker/schemas.py`; **test:** `tests/test_v4966_current_defects.py::test_RECENT006_unused_or_branch_missing_does_not_veto_satisfied_nested_expression`
- **Baseline observation:** {"proof_component_count": 0}
- **Candidate observation/change:** {"proof_component_count": 4}; v4.9.66 / v52: Condition proof disappears on save
- **Evidence class:** actual separate-process offline synthetic reproduction; **remaining:** Live model, Windows GUI and external human accuracy not qualified
- **Next step:** Run dependency-complete Windows and independently adjudicated held-out scenarios

### RECENT-008 — VERIFIED_OFFLINE
- **Historical ID:** `AUDIT-008`; **source:** v4.9.65 / protocol v51
- **Expected:** An unreadable CV aborts a resumed batch
- **Code:** `cv_ranker/source_snapshot.py; cv_ranker/pipeline.py; cv_ranker/ui/dashboard.py`; **test:** `tests/test_v4966_current_defects.py::test_RECENT008_unreadable_slot_does_not_abort_healthy_candidates`
- **Baseline observation:** {"fatal": "FileNotFoundError"}
- **Candidate observation/change:** {"candidate_count": 2, "fatal": false, "missing_is_failed": true}; v4.9.66 / v52: An unreadable CV aborts a resumed batch
- **Evidence class:** actual separate-process offline synthetic reproduction; **remaining:** Live model, Windows GUI and external human accuracy not qualified
- **Next step:** Run dependency-complete Windows and independently adjudicated held-out scenarios

## V4962 (13 source-specific issues)

### V4962-001 — VERIFIED_OFFLINE controlled
- **Historical ID:** `AUD-001`; **source:** v4.9.62 / protocol v48
- **Expected:** Prevent unrelated initials from establishing a named capability. Verify explicit term, source-defined expansion and separately approved aliases as positives. Add adversarial initialism, future-only and third-party controls in unrelated domains.
- **Code:** `cv_ranker/assessor.py; cv_ranker/unified.py`; **test:** `tests/test_v4962_forensic_release.py`
- **Baseline observation:** Historical report and prior synthetic controls; not separately rerun on original v48 in this task
- **Candidate observation/change:** Current available suite ran; see logs for exact node status; do not infer live acceptance; Retained v51 mechanisms; v52 targeted changes only where mapped to RECENT items
- **Evidence class:** historical and current offline suite (not independent live proof); **remaining:** Windows/provider and/or original applicant replay unverified
- **Next step:** Run named controls on native Windows; inspect reviewer citation and full export

### V4962-002 — VERIFIED_OFFLINE controlled
- **Historical ID:** `AUD-002`; **source:** v4.9.62 / protocol v48
- **Expected:** Each of three and four coordinated alternatives independently suffices when the required shared work is present. Test mandatory siblings outside the group, reordering, and ambiguous prose requiring review.
- **Code:** `cv_ranker/compound_validation.py; cv_ranker/unified.py`; **test:** `tests/test_v4960_named_alternatives_and_recovery.py`
- **Baseline observation:** Historical report and prior synthetic controls; not separately rerun on original v48 in this task
- **Candidate observation/change:** Current available suite ran; see logs for exact node status; do not infer live acceptance; Retained v51 mechanisms; v52 targeted changes only where mapped to RECENT items
- **Evidence class:** historical and current offline suite (not independent live proof); **remaining:** Windows/provider and/or original applicant replay unverified
- **Next step:** Run named controls on native Windows; inspect reviewer citation and full export

### V4962-003 — PARTIAL
- **Historical ID:** `AUD-003`; **source:** v4.9.62 / protocol v48
- **Expected:** Attach each duration to its subject. Compare record retention, project target, equipment lifetime, training duration and actual minimum professional tenure.
- **Code:** `cv_ranker/requirement_typing.py; cv_ranker/experience_validation.py`; **test:** `tests/test_v4962_forensic_release.py`
- **Baseline observation:** Historical report and prior synthetic controls; not separately rerun on original v48 in this task
- **Candidate observation/change:** Current available suite ran; see logs for exact node status; do not infer live acceptance; Retained v51 mechanisms; v52 targeted changes only where mapped to RECENT items
- **Evidence class:** historical and current offline suite (not independent live proof); **remaining:** Windows/provider and/or original applicant replay unverified
- **Next step:** Run named controls on native Windows; inspect reviewer citation and full export

### V4962-004 — VERIFIED_OFFLINE intercepted
- **Historical ID:** `AUD-004`; **source:** v4.9.62 / protocol v48
- **Expected:** Intercept 301/302/303/307/308 on actual authenticated HTTP transport; same/cross-origin, relative Location and repeated redirect. Assert no redirected authenticated request or exposed bearer. Use dummy credentials. Qualify authorized ordinary provider calls separately.
- **Code:** `cv_ranker/llm.py`; **test:** `tests/test_v4964_coverage_semantics_diagnostics.py`
- **Baseline observation:** Historical report and prior synthetic controls; not separately rerun on original v48 in this task
- **Candidate observation/change:** Current available suite ran; see logs for exact node status; do not infer live acceptance; Retained v51 mechanisms; v52 targeted changes only where mapped to RECENT items
- **Evidence class:** historical and current offline suite (not independent live proof); **remaining:** Windows/provider and/or original applicant replay unverified
- **Next step:** Run named controls on native Windows; inspect reviewer citation and full export

### V4962-005 — PARTIAL
- **Historical ID:** `AUD-005`; **source:** v4.9.62 / protocol v48
- **Expected:** Prove supported DOCX headers/footers, mixed-image PDF qualification, blank-page control, tables/columns and partial ingestion handling. Carry extraction limitations to UI, eligibility, score and exports.
- **Code:** `cv_ranker/documents.py`; **test:** `tests/test_v4962_forensic_release.py`
- **Baseline observation:** Historical report and prior synthetic controls; not separately rerun on original v48 in this task
- **Candidate observation/change:** Current available suite ran; see logs for exact node status; do not infer live acceptance; Retained v51 mechanisms; v52 targeted changes only where mapped to RECENT items
- **Evidence class:** historical and current offline suite (not independent live proof); **remaining:** Windows/provider and/or original applicant replay unverified
- **Next step:** Run named controls on native Windows; inspect reviewer citation and full export

### V4962-006 — VERIFIED_OFFLINE controlled
- **Historical ID:** `AUD-006`; **source:** v4.9.62 / protocol v48
- **Expected:** Distinguish unavailable, verified zero and provisional floor in details, leaderboard, saved JSON, CSV, ZIP and Windows visual workflow. Cover genuine zero, empty rows and technical errors.
- **Code:** `cv_ranker/scoring.py; cv_ranker/report_bundle.py`; **test:** `tests/test_v4962_forensic_release.py`
- **Baseline observation:** Historical report and prior synthetic controls; not separately rerun on original v48 in this task
- **Candidate observation/change:** Current available suite ran; see logs for exact node status; do not infer live acceptance; Retained v51 mechanisms; v52 targeted changes only where mapped to RECENT items
- **Evidence class:** historical and current offline suite (not independent live proof); **remaining:** Windows/provider and/or original applicant replay unverified
- **Next step:** Run named controls on native Windows; inspect reviewer citation and full export

### V4962-007 — VERIFIED_OFFLINE scripted
- **Historical ID:** `AUD-007`; **source:** v4.9.62 / protocol v48
- **Expected:** Benchmark the actual supervisor engine with trace proving the branch, settings, source IDs and calls used. Keep 7/7 and 15/15 scripted suites as regressions. R8 supplies independent evidence.
- **Code:** `cv_ranker/pipeline.py`; **test:** `evaluation/evaluate_supervisor.py`
- **Baseline observation:** Historical report and prior synthetic controls; not separately rerun on original v48 in this task
- **Candidate observation/change:** Current available suite ran; see logs for exact node status; do not infer live acceptance; Retained v51 mechanisms; v52 targeted changes only where mapped to RECENT items
- **Evidence class:** historical and current offline suite (not independent live proof); **remaining:** Windows/provider and/or original applicant replay unverified
- **Next step:** Run named controls on native Windows; inspect reviewer citation and full export

### V4962-008 — VERIFIED_OFFLINE controlled
- **Historical ID:** `AUD-008`; **source:** v4.9.62 / protocol v48
- **Expected:** Keep pooled scoring, display-only splitting for old snapshots and opt-in weighted split distinct. Test custom group and item shares through edit, restore and export.
- **Code:** `cv_ranker/weighted_scoring.py`; **test:** `tests/test_v4966_current_defects.py`
- **Baseline observation:** Historical report and prior synthetic controls; not separately rerun on original v48 in this task
- **Candidate observation/change:** Current available suite ran; see logs for exact node status; do not infer live acceptance; Retained v51 mechanisms; v52 targeted changes only where mapped to RECENT items
- **Evidence class:** historical and current offline suite (not independent live proof); **remaining:** Windows/provider and/or original applicant replay unverified
- **Next step:** Run named controls on native Windows; inspect reviewer citation and full export

### V4962-009 — PARTIAL
- **Historical ID:** `AUD-009`; **source:** v4.9.62 / protocol v48
- **Expected:** Judge equivalent occupational duties consistently across domains; preserve uncertainty for genuinely ambiguous JDs. Check unfamiliar verbs and same-verb/wrong-object pairs.
- **Code:** `cv_ranker/requirement_typing.py; cv_ranker/assessor.py`; **test:** `tests/test_v4965_supervisor_end_to_end.py`
- **Baseline observation:** Historical report and prior synthetic controls; not separately rerun on original v48 in this task
- **Candidate observation/change:** Current available suite ran; see logs for exact node status; do not infer live acceptance; Retained v51 mechanisms; v52 targeted changes only where mapped to RECENT items
- **Evidence class:** historical and current offline suite (not independent live proof); **remaining:** Windows/provider and/or original applicant replay unverified
- **Next step:** Run named controls on native Windows; inspect reviewer citation and full export

### V4962-010 — PARTIAL
- **Historical ID:** `AUD-010`; **source:** v4.9.62 / protocol v48
- **Expected:** Inventory assessment-affecting dependencies including extraction, normalization, segmentation, prompt builders, validators and runtime config. Change a real dependency in an isolated test and verify invalidation. Exclude display-only branding and weight-only inputs from model reruns.
- **Code:** `cv_ranker/resume.py`; **test:** `tests/test_v4962_forensic_release.py`
- **Baseline observation:** Historical report and prior synthetic controls; not separately rerun on original v48 in this task
- **Candidate observation/change:** Current available suite ran; see logs for exact node status; do not infer live acceptance; Retained v51 mechanisms; v52 targeted changes only where mapped to RECENT items
- **Evidence class:** historical and current offline suite (not independent live proof); **remaining:** Windows/provider and/or original applicant replay unverified
- **Next step:** Run named controls on native Windows; inspect reviewer citation and full export

### V4962-011 — PARTIAL
- **Historical ID:** `AUD-011`; **source:** v4.9.62 / protocol v48
- **Expected:** Test first-use key publication with interleaved readers/writers, native Windows multiprocess races, termination around publication, restart, permissions, unsupported filesystem behavior and cleanup. A reader never receives a partial or empty key; no silent regeneration invalidating prior bundles.
- **Code:** `cv_ranker/recovery_bundle.py`; **test:** `tests/test_v4962_forensic_release.py`
- **Baseline observation:** Historical report and prior synthetic controls; not separately rerun on original v48 in this task
- **Candidate observation/change:** Current available suite ran; see logs for exact node status; do not infer live acceptance; Retained v51 mechanisms; v52 targeted changes only where mapped to RECENT items
- **Evidence class:** historical and current offline suite (not independent live proof); **remaining:** Windows/provider and/or original applicant replay unverified
- **Next step:** Run named controls on native Windows; inspect reviewer citation and full export

### V4962-012 — REMOTE_BLOCKED
- **Historical ID:** `AUD-012`; **source:** v4.9.62 / protocol v48
- **Expected:** Verify clean remote-extra installation, fail-closed config/preflight and absence of an accidental public bind. Keep live IdP, tenant boundaries, storage and operational acceptance as R10 external work.
- **Code:** `cv_ranker/access_control.py; scripts/production_preflight.py`; **test:** `scripts/production_preflight.py`
- **Baseline observation:** Historical report and prior synthetic controls; not separately rerun on original v48 in this task
- **Candidate observation/change:** Current available suite ran; see logs for exact node status; do not infer live acceptance; Retained v51 mechanisms; v52 targeted changes only where mapped to RECENT items
- **Evidence class:** historical and current offline suite (not independent live proof); **remaining:** Windows/provider and/or original applicant replay unverified
- **Next step:** Run named controls on native Windows; inspect reviewer citation and full export

### V4962-013 — PARTIAL
- **Historical ID:** `AUD-013`; **source:** v4.9.62 / protocol v48
- **Expected:** Preserve the bundled six Required plus two Preferred fixture. Add independent narrative JDs with descriptions beside real responsibilities, no standard headings, and mixed lists; neither invent a criterion nor drop a genuine duty.
- **Code:** `cv_ranker/jd.py; cv_ranker/fallback.py`; **test:** `tests/test_v4962_forensic_release.py`
- **Baseline observation:** Historical report and prior synthetic controls; not separately rerun on original v48 in this task
- **Candidate observation/change:** Current available suite ran; see logs for exact node status; do not infer live acceptance; Retained v51 mechanisms; v52 targeted changes only where mapped to RECENT items
- **Evidence class:** historical and current offline suite (not independent live proof); **remaining:** Windows/provider and/or original applicant replay unverified
- **Next step:** Run named controls on native Windows; inspect reviewer citation and full export

## V4957 (35 source-specific issues)

### V4957-001 — OPEN / NOT QUALIFIED
- **Historical ID:** `AUD-001`; **source:** v4.9.57 / protocol v43
- **Expected:** Compare type and modality on unfamiliar equivalent duties across departments.
- **Code:** `cv_ranker/requirement_typing.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; Not claimed complete in v52
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-002 — OPEN / NOT QUALIFIED
- **Historical ID:** `AUD-002`; **source:** v4.9.57 / protocol v43
- **Expected:** Compare single duty with shared objects to genuinely separate mandatory actions.
- **Code:** `cv_ranker/compound_validation.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; Not claimed complete in v52
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-003 — PARTIAL / PRIOR OFFLINE CONTROLS
- **Historical ID:** `AUD-003`; **source:** v4.9.57 / protocol v43
- **Expected:** Retain a supported adjacent-work result in final reconciliation and export.
- **Code:** `cv_ranker/pipeline.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; v52 partial; see related RECENT repair or preserved prior test
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-004 — PARTIAL / PRIOR OFFLINE CONTROLS
- **Historical ID:** `AUD-004`; **source:** v4.9.57 / protocol v43
- **Expected:** Preserve an established direct result across validators subject to genuinely applicable constraints.
- **Code:** `cv_ranker/pipeline.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; v52 partial; see related RECENT repair or preserved prior test
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-005 — OPEN / NOT QUALIFIED
- **Historical ID:** `AUD-005`; **source:** v4.9.57 / protocol v43
- **Expected:** Search and assess qualifying content in poorly classified sections without blanket approval of irrelevant text.
- **Code:** `cv_ranker/unified.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; Not claimed complete in v52
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-006 — OPEN / NOT QUALIFIED
- **Historical ID:** `AUD-006`; **source:** v4.9.57 / protocol v43
- **Expected:** Set different provider contexts and show the outgoing payload respects the selected provider.
- **Code:** `cv_ranker/llm.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; Not claimed complete in v52
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-007 — OPEN / NOT QUALIFIED
- **Historical ID:** `AUD-007`; **source:** v4.9.57 / protocol v43
- **Expected:** A correction supplies materially new evidence or stops with the correct cause.
- **Code:** `cv_ranker/unified.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; Not claimed complete in v52
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-008 — PARTIAL / PRIOR OFFLINE CONTROLS
- **Historical ID:** `AUD-008`; **source:** v4.9.57 / protocol v43
- **Expected:** Show a cause-specific next step after a no-progress pause and verify its effect.
- **Code:** `cv_ranker/failure_diagnostics.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; v52 partial; see related RECENT repair or preserved prior test
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-009 — OPEN / NOT QUALIFIED
- **Historical ID:** `AUD-009`; **source:** v4.9.57 / protocol v43
- **Expected:** Compare all reachable decision writers against the canonical decision.
- **Code:** `cv_ranker/pipeline.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; Not claimed complete in v52
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-010 — OPEN / NOT QUALIFIED
- **Historical ID:** `AUD-010`; **source:** v4.9.57 / protocol v43
- **Expected:** Measure clause coverage against independently marked whole JDs.
- **Code:** `cv_ranker/jd_coverage.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; Not claimed complete in v52
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-011 — PARTIAL / PRIOR OFFLINE CONTROLS
- **Historical ID:** `AUD-011`; **source:** v4.9.57 / protocol v43
- **Expected:** Use a genuine but irrelevant source ID and an entailing paraphrase as paired controls.
- **Code:** `cv_ranker/assessor.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; v52 partial; see related RECENT repair or preserved prior test
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-012 — PARTIAL / PRIOR OFFLINE CONTROLS
- **Historical ID:** `AUD-012`; **source:** v4.9.57 / protocol v43
- **Expected:** Mutate each decision-affecting dependency and prove incompatible reuse is refused.
- **Code:** `cv_ranker/resume.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; v52 partial; see related RECENT repair or preserved prior test
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-013 — OPEN / NOT QUALIFIED
- **Historical ID:** `AUD-013`; **source:** v4.9.57 / protocol v43
- **Expected:** Produce independent held-out measurements on the current protocol and disclose limits.
- **Code:** `evaluation/evaluate_supervisor.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; Not claimed complete in v52
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-014 — REMOTE_BLOCKED
- **Historical ID:** `AUD-014`; **source:** v4.9.57 / protocol v43
- **Expected:** Qualify local controls and retain independent remote persistence/privacy gates.
- **Code:** `cv_ranker/access_control.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; Not claimed complete in v52
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-015 — OPEN / NOT QUALIFIED
- **Historical ID:** `AUD-015`; **source:** v4.9.57 / protocol v43
- **Expected:** Link position heading, employer, dates and work across blocks; prevent transfer between roles.
- **Code:** `cv_ranker/segments.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; Not claimed complete in v52
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-016 — OPEN / NOT QUALIFIED
- **Historical ID:** `AUD-016`; **source:** v4.9.57 / protocol v43
- **Expected:** Detect scan/partial loss and qualify OCR or visible blocked handling for unsupported pages.
- **Code:** `cv_ranker/documents.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; Not claimed complete in v52
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-017 — PARTIAL / PRIOR OFFLINE CONTROLS
- **Historical ID:** `AUD-017`; **source:** v4.9.57 / protocol v43
- **Expected:** Compare provider-reported usage, estimates and missing usage without fabricated cost.
- **Code:** `cv_ranker/llm.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; v52 partial; see related RECENT repair or preserved prior test
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-018 — OPEN / NOT QUALIFIED
- **Historical ID:** `AUD-018`; **source:** v4.9.57 / protocol v43
- **Expected:** Verify cache retention, deletion, account/workspace isolation where applicable and Windows races.
- **Code:** `cv_ranker/semantic/cache.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; Not claimed complete in v52
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-019 — OPEN / NOT QUALIFIED
- **Historical ID:** `AUD-019`; **source:** v4.9.57 / protocol v43
- **Expected:** Test signed readable recovery, explicit handling of sensitive contents, restore and tamper detection.
- **Code:** `cv_ranker/recovery_bundle.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; Not claimed complete in v52
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-020 — REMOTE_BLOCKED
- **Historical ID:** `AUD-020`; **source:** v4.9.57 / protocol v43
- **Expected:** Check fail-closed remote configuration; keep live IdP qualification separate.
- **Code:** `cv_ranker/access_control.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; Not claimed complete in v52
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-021 — REMOTE_BLOCKED
- **Historical ID:** `AUD-021`; **source:** v4.9.57 / protocol v43
- **Expected:** Keep multi-user durable remote dispatch pending a separately qualified deployment.
- **Code:** `cv_ranker/ui/dashboard.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; Not claimed complete in v52
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-022 — OPEN / NOT QUALIFIED
- **Historical ID:** `AUD-022`; **source:** v4.9.57 / protocol v43
- **Expected:** Enforce aggregate and per-file byte/count limits at entry, including mixed upload types.
- **Code:** `cv_ranker/ui/dashboard.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; Not claimed complete in v52
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-023 — OPEN / NOT QUALIFIED
- **Historical ID:** `AUD-023`; **source:** v4.9.57 / protocol v43
- **Expected:** Compare supported CLI/UI candidate defaults, documented intentional differences and cap diagnostics.
- **Code:** `main.py; cv_ranker/ui/dashboard.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; Not claimed complete in v52
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-024 — PARTIAL / PRIOR OFFLINE CONTROLS
- **Historical ID:** `AUD-024`; **source:** v4.9.57 / protocol v43
- **Expected:** Test changed code in a long-lived process and restart; no falsely current cache identity.
- **Code:** `cv_ranker/resume.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; v52 partial; see related RECENT repair or preserved prior test
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-025 — OPEN / NOT QUALIFIED
- **Historical ID:** `AUD-025`; **source:** v4.9.57 / protocol v43
- **Expected:** Identify coupled decision writes; refactor only with caller contracts and targeted regressions.
- **Code:** `cv_ranker/unified.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; Not claimed complete in v52
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-026 — OPEN / NOT QUALIFIED
- **Historical ID:** `AUD-026`; **source:** v4.9.57 / protocol v43
- **Expected:** Update architecture docs to match traced runtime owners and modes.
- **Code:** `docs/ARCHITECTURE.md`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; Not claimed complete in v52
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-027 — PARTIAL / PRIOR OFFLINE CONTROLS
- **Historical ID:** `AUD-027`; **source:** v4.9.57 / protocol v43
- **Expected:** Verify configurable escaped display name across screens/exports and zero model reruns.
- **Code:** `cv_ranker/ui/dashboard.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; v52 partial; see related RECENT repair or preserved prior test
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-028 — OPEN / NOT QUALIFIED
- **Historical ID:** `AUD-028`; **source:** v4.9.57 / protocol v43
- **Expected:** Exercise keyboard, focus, readable status and responsive details under native UI.
- **Code:** `cv_ranker/ui/dashboard.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; Not claimed complete in v52
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-029 — PARTIAL / PRIOR OFFLINE CONTROLS
- **Historical ID:** `AUD-029`; **source:** v4.9.57 / protocol v43
- **Expected:** Compare row IDs, source evidence, statuses, weights and reasons across all outputs.
- **Code:** `cv_ranker/report_bundle.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; v52 partial; see related RECENT repair or preserved prior test
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-030 — OPEN / NOT QUALIFIED
- **Historical ID:** `AUD-030`; **source:** v4.9.57 / protocol v43
- **Expected:** Check supported pinned dependency advisories with dated evidence if available; isolate unresolved advisories.
- **Code:** `requirements.txt`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; Not claimed complete in v52
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-031 — OPEN / NOT QUALIFIED
- **Historical ID:** `AUD-031`; **source:** v4.9.57 / protocol v43
- **Expected:** Inspect actual CI configuration and runs; report observed jobs, platforms and regression coverage.
- **Code:** `.github/`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; Not claimed complete in v52
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-032 — OPEN / NOT QUALIFIED
- **Historical ID:** `AUD-032`; **source:** v4.9.57 / protocol v43
- **Expected:** Validate clean setup from documented environment example and CLI defaults with secrets absent.
- **Code:** `README.md`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; Not claimed complete in v52
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-033 — OPEN / NOT QUALIFIED
- **Historical ID:** `AUD-033`; **source:** v4.9.57 / protocol v43
- **Expected:** Index release identities, protocols, migrations and rollback artifacts.
- **Code:** `docs/`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; Not claimed complete in v52
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-034 — PARTIAL / PRIOR OFFLINE CONTROLS
- **Historical ID:** `AUD-034`; **source:** v4.9.57 / protocol v43
- **Expected:** Distinguish retrieved, sent, accepted, rejected and unexamined passages in supervisor diagnostics.
- **Code:** `cv_ranker/ui/evidence_inspection.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; v52 partial; see related RECENT repair or preserved prior test
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

### V4957-035 — OPEN / NOT QUALIFIED
- **Historical ID:** `AUD-035`; **source:** v4.9.57 / protocol v43
- **Expected:** Include build, assessment protocol, date and scoring policy identity in authorized exports.
- **Code:** `cv_ranker/ui/dashboard.py`; **test:** `tests/ and evaluation/ source audit; no independently adjudicated holdout`
- **Baseline observation:** Historical v43 forensic observation; no fresh v43 source available in the supplied v51 ZIP
- **Candidate observation/change:** Open evidence gate; do not infer a verified result from source inventory; Not claimed complete in v52
- **Evidence class:** historical requirement or qualitative coverage gap; **remaining:** Requires dedicated input / Windows / live provider / human validation as applicable
- **Next step:** Reproduce against current source with an independently labeled positive and negative through supervisor export

## R0–R10 release-gate qualifications

| Gate | Status and next evidence |
|---|---|
| R0/G0 | BASELINE FROZEN: v51 ZIP, hash and separate process differential; Windows not verified |
| R1/G1 | PARTIAL: prior 13 controls and new eight covered offline; missing full Windows |
| R2/G2 | PARTIAL: exact-offset nested expression added; narrative/OCR unqualified |
| R3/G3 | PARTIAL: unified paths repaired; legacy/optional finalizer consolidation open |
| R4/G4 | PARTIAL: earlier tenure/education tests preserved; live real-CV proof unavailable |
| R5/G5 | PARTIAL: 13 system prompts inventoried; no all-prompt A/B live qualification |
| R6/G6 | PARTIAL: SQLite at-most-once semantic claim, cross-process ledger; crash billing/replay not fully durable |
| R7/G7 | PARTIAL: source checks, cache validation, redirect controlled tests; remote privacy open |
| R8/G8 | NOT QUALIFIED: no independently adjudicated human gold or authorized live model trials |
| R9/G9 | NOT QUALIFIED: no native Windows/Streamlit dependency-complete full suite |
| R10/G10 | REMOTE BLOCKED: needs separately authorized security/operations |

## P0–P8 mapping (roadmap, not separate bug IDs)

| Phase | Related milestones | Status |
|---|---|---|
| P0 | R0 | Open/partial in the same gate; see rows above |
| P1 | R2/R3 | Open/partial in the same gate; see rows above |
| P2 | R1/R3/R4 | Open/partial in the same gate; see rows above |
| P3 | R5 | Open/partial in the same gate; see rows above |
| P4 | R4 | Open/partial in the same gate; see rows above |
| P5 | R6 | Open/partial in the same gate; see rows above |
| P6 | R7 | Open/partial in the same gate; see rows above |
| P7 | R8/R9 | Open/partial in the same gate; see rows above |
| P8 | R9 | Open/partial in the same gate; see rows above |

## Evidence and source integrity

Each RECENT row has an independently executed before/after serialized probe in `verification/v4966_differential_results.json`. `verification/v4966_test_evidence.json` distinguishes focused tests, full-suite import failures and scripted 7/15. The original v51 ZIP is not altered. Candidate source changes can be reproduced using the verified patch, or audited by the strict build manifest. Source names in this register are release-relative; exact line offsets are available in the source audit JSON and may change with code formatting. No real applicant data or provider secrets are included.
