# v4.9.70-rc1 — protected broad-suite failure inventory

**Observed:** 1,499 passed; 52 failed on the dependency-limited Linux/Python runtime (15 Nov 2026).
**Not a qualified release:** This inventory includes unchanged historical assertions that expect the retired Unverified/fourth-choice model response, actual missing third-party packages, and code-path/schema failures. The short cause labels are the pytest summaries, not root-cause certification.

20 of these 52 summary lines explicitly report `ModuleNotFoundError` (Streamlit or LangChain). Other failures are not automatically assumed harmless; they remain release blockers until reviewed and passed under the approved new contract.

## Test-by-test observations

1. `tests/test_llm_contracts.py::test_invalid_evidence_after_correction_receives_no_credit` — Retired-contract expectation (needs adjudication). `AssertionError: assert 'uncertain' == 'not_matched'`
2. `tests/test_llm_contracts.py::test_main_llm_failure_uses_conservative_technical_fallback` — Other failing assertion (needs investigation). `AssertionError: assert 'failed' == 'fallback_exact'`
3. `tests/test_phase7g_v43_duration_and_cloud_reliability.py::test_openrouter_strict_schema_rejection_uses_locally_validated_json` — Provider/schema behavior (needs investigation). `cv_ranker.llm.ModelStructuredResponseError: OpenRouter structured call failed after at most 2 attempt(s): ValidationError: structured JSON did not validate`
4. `tests/test_phase7g_v45_provider_switch.py::test_local_dispatch_uses_ollama_model_and_url_from_env` — Missing dependency. `ModuleNotFoundError: No module named 'langchain_core'`
5. `tests/test_phase7g_v45_provider_switch.py::test_cloud_dispatch_uses_openrouter_model_and_does_not_initialize_ollama` — Missing dependency. `ModuleNotFoundError: No module named 'langchain_ollama'`
6. `tests/test_phase7g_v46_release_regressions.py::test_openrouter_respects_retry_after_and_preserves_local_schema_validation` — Provider/schema behavior (needs investigation). `cv_ranker.llm.ModelStructuredResponseError: OpenRouter structured call failed after at most 2 attempt(s): ValidationError: structured JSON did not validate`
7. `tests/test_runtime_identity.py::test_runtime_protocol_is_segment_ids` — Other failing assertion (needs investigation). `AssertionError: assert '56' == '54'`
8. `tests/test_surgical_fixes.py::test_llm_technical_failure_is_visibly_fallback` — Retired-contract expectation (needs adjudication). `AssertionError: assert 'uncertain' == 'matched'`
9. `tests/test_v484_domain_neutral_prompts.py::test_unified_contract_is_decision_based_and_source_grounded` — Other failing assertion (needs investigation). `AssertionError: uncertain`
10. `tests/test_v486_domain_neutral_validation_repair.py::test_missing_row_and_invented_quote_cannot_create_a_fabricated_score` — Retired-contract expectation (needs adjudication). `AssertionError: assert None == 'Unverified'`
11. `tests/test_v487_system_contracts.py::test_technical_error_after_one_correction_is_unverified_not_absent` — Other failing assertion (needs investigation). `AssertionError: assert ('unverified' == 'unverified'`
12. `tests/test_v48_unified.py::test_unresolved_model_row_does_not_discard_verified_peer` — Retired-contract expectation (needs adjudication). `AssertionError: assert ('uncertain' == 'uncertain'`
13. `tests/test_v4911_resume_rate_limit.py::test_dashboard_resume_checkpoint_tracks_source_hash_not_leaderboard_order` — Missing dependency. `ModuleNotFoundError: No module named 'streamlit'`
14. `tests/test_v491_live_failure_roots.py::test_single_bounded_final_verification_never_invents_credit[False]` — Retired-contract expectation (needs adjudication). `AssertionError: assert None == 'Unverified'`
15. `tests/test_v4920_jd_review_gate.py::test_streamlit_jd_editor_renders_and_freezes_approved_rows` — Missing dependency. `ModuleNotFoundError: No module named 'streamlit'`
16. `tests/test_v4922_weighted_scoring_and_bundle.py::test_unverified_gets_only_provisional_zero_credit_not_verified_match` — Other failing assertion (needs investigation). `assert None == 0.0`
17. `tests/test_v4922_weighted_scoring_and_bundle.py::test_yake_display_is_ranked_by_raw_lower_is_better_scores` — Missing dependency. `ModuleNotFoundError: No module named 'streamlit'`
18. `tests/test_v4922_weighted_scoring_and_bundle.py::test_results_button_switches_stateful_streamlit_tab` — Missing dependency. `ModuleNotFoundError: No module named 'streamlit'`
19. `tests/test_v4931_dynamic_allocation_and_reasoning.py::test_incomplete_candidates_get_provisional_floor_and_why` — Other failing assertion (needs investigation). `assert (None == 0)`
20. `tests/test_v4931_dynamic_allocation_and_reasoning.py::test_actual_streamlit_editor_rebalances_after_one_requirement_is_changed` — Missing dependency. `ModuleNotFoundError: No module named 'streamlit'`
21. `tests/test_v4931_dynamic_allocation_and_reasoning.py::test_actual_streamlit_ranking_and_individual_why_render_with_two_candidates[complete]` — Missing dependency. `ModuleNotFoundError: No module named 'streamlit'`
22. `tests/test_v4931_dynamic_allocation_and_reasoning.py::test_actual_streamlit_ranking_and_individual_why_render_with_two_candidates[first_withheld]` — Missing dependency. `ModuleNotFoundError: No module named 'streamlit'`
23. `tests/test_v4931_dynamic_allocation_and_reasoning.py::test_actual_streamlit_ranking_and_individual_why_render_with_two_candidates[all_withheld]` — Missing dependency. `ModuleNotFoundError: No module named 'streamlit'`
24. `tests/test_v4933_partial_batch_survival.py::test_background_progress_caption_updates_without_streamlit_calls_from_worker` — Missing dependency. `ModuleNotFoundError: No module named 'streamlit'`
25. `tests/test_v4933_partial_batch_survival.py::test_identical_invalid_model_rows_pause_without_another_cloud_retry` — Missing dependency. `ModuleNotFoundError: No module named 'streamlit'`
26. `tests/test_v4933_partial_batch_survival.py::test_provider_rate_limit_keeps_cooldown_instead_of_blind_validation_pause` — Missing dependency. `ModuleNotFoundError: No module named 'streamlit'`
27. `tests/test_v4935_focused_verification_reliability.py::test_unverified_r008_is_recovered_by_a_valid_focused_final_judgment` — Provider/schema behavior (needs investigation). `cv_ranker.llm.LLMError: Unified candidate assessment unavailable: ValidationError`
28. `tests/test_v4935_focused_verification_reliability.py::test_fabricated_final_excerpt_still_withholds_credit_and_explains_why` — Provider/schema behavior (needs investigation). `cv_ranker.llm.LLMError: Unified candidate assessment unavailable: ValidationError`
29. `tests/test_v4935_focused_verification_reliability.py::test_final_model_schema_failure_has_requirement_specific_diagnostic` — Provider/schema behavior (needs investigation). `cv_ranker.llm.LLMError: Unified candidate assessment unavailable: ValidationError`
30. `tests/test_v4937_cited_evidence_without_model_requotation.py::test_failed_independent_source_validation_still_withholds_credit` — Retired-contract expectation (needs adjudication). `AssertionError: assert None == 'Unverified'`
31. `tests/test_v4939_individual_decision_why.py::test_streamlit_individual_requirements_show_why_in_table_and_expander` — Missing dependency. `ModuleNotFoundError: No module named 'streamlit'`
32. `tests/test_v4943_mixed_batch_recovery.py::test_grouped_correction_does_not_erase_highlight_only_unverified_row[False]` — Retired-contract expectation (needs adjudication). `AssertionError: assert None == 'Unverified'`
33. `tests/test_v4945_security_and_concurrency.py::test_local_access_gate_runs_in_streamlit_without_external_identity` — Missing dependency. `ModuleNotFoundError: No module named 'streamlit'`
34. `tests/test_v4945_security_and_concurrency.py::test_supervisor_full_app_renders_under_safe_local_policy` — Missing dependency. `ModuleNotFoundError: No module named 'streamlit'`
35. `tests/test_v494_transferable_root_contract.py::test_complete_pipeline_and_display_keep_related_degree_as_unscored_transfer` — Provider/schema behavior (needs investigation). `cv_ranker.llm.LLMError: Unified semantic assessment requires the configured LLM; cannot silently use fallback`
36. `tests/test_v494_transferable_root_contract.py::test_full_pipeline_higher_level_degree_is_unscored_transfer` — Provider/schema behavior (needs investigation). `cv_ranker.llm.LLMError: Unified semantic assessment requires the configured LLM; cannot silently use fallback`
37. `tests/test_v4951_contrast_and_prompt_budget.py::test_custom_result_cards_follow_selected_streamlit_theme[light-#183025-#EFF5EF]` — Missing dependency. `ModuleNotFoundError: No module named 'streamlit'`
38. `tests/test_v4951_contrast_and_prompt_budget.py::test_custom_result_cards_follow_selected_streamlit_theme[dark-#EDF7EF-#1B2D23]` — Missing dependency. `ModuleNotFoundError: No module named 'streamlit'`
39. `tests/test_v4951_contrast_and_prompt_budget.py::test_all_primary_buttons_get_explicit_high_contrast_palette[light-#12613C-#FFFFFF]` — Missing dependency. `ModuleNotFoundError: No module named 'streamlit'`
40. `tests/test_v4951_contrast_and_prompt_budget.py::test_all_primary_buttons_get_explicit_high_contrast_palette[dark-#6FDEAA-#092017]` — Missing dependency. `ModuleNotFoundError: No module named 'streamlit'`
41. `tests/test_v4955_uncertainty_and_editable_local.py::test_both_primary_and_independent_prompts_prioritize_evidence_based_decisiveness` — Retired-contract expectation (needs adjudication). `AssertionError: assert 'uncertain' in 'assess one cv against frozen jd criteria. the only\ncompleted model verdict choices are found/transferable/not_found ...all: cite the minimum sufficient original\n  source ids, never copy cv text into reason or an invented matched_term.\n'`
42. `tests/test_v4955_uncertainty_and_editable_local.py::test_uncertain_with_absent_relationship_becomes_non_scoring_not_found` — Other failing assertion (needs investigation). `pydantic_core._pydantic_core.ValidationError: 1 validation error for UnifiedItem`
43. `tests/test_v4955_uncertainty_and_editable_local.py::test_uncertain_with_cited_overlap_becomes_unscored_transferable_proposal` — Other failing assertion (needs investigation). `pydantic_core._pydantic_core.ValidationError: 1 validation error for UnifiedItem`
44. `tests/test_v4955_uncertainty_and_editable_local.py::test_uncertain_with_claimed_direct_relationship_cannot_skip_positive_validation` — Other failing assertion (needs investigation). `pydantic_core._pydantic_core.ValidationError: 1 validation error for UnifiedItem`
45. `tests/test_v4955_uncertainty_and_editable_local.py::test_independent_uncertainty_overlap_normalization_preserves_source_id` — Other failing assertion (needs investigation). `pydantic_core._pydantic_core.ValidationError: 1 validation error for IndependentSemanticDecisionByID`
46. `tests/test_v4956_phase1_to4_reliability.py::test_unverified_is_scored_only_as_provisional_verified_floor` — Other failing assertion (needs investigation). `assert None == 1`
47. `tests/test_v4958_decision_integrity.py::test_technical_failure_stays_unverified` — Retired-contract expectation (needs adjudication). `AssertionError: assert None == 'Unverified'`
48. `tests/test_v4962_forensic_release.py::test_verified_zero_remains_verified_not_unavailable` — Other failing assertion (needs investigation). `assert None == 0.0`
49. `tests/test_v4965_compound_semantic_resolution.py::test_parser_uncertainty_does_not_export_a_verified_negative[R005-Interpretation of woven fabric construction, including weave pattern, ends per inch (EPI), and picks per inch (PPI).-Check weave patterns, EPI, PPI, pick density, and selvage settings against fabric style sheets.]` — Retired-contract expectation (needs adjudication). `AssertionError: assert None == 'Unverified'`
50. `tests/test_v4965_compound_semantic_resolution.py::test_parser_uncertainty_does_not_export_a_verified_negative[R008-Fabric defect identification and corrective action during weaving.-Recorded defect observations at shift handover.]` — Retired-contract expectation (needs adjudication). `AssertionError: assert None == 'Unverified'`
51. `tests/test_v4967_finalizer_identity.py::test_forged_or_foreign_source_can_never_become_verified_found` — Retired-contract expectation (needs adjudication). `AssertionError: assert (None == 'Unverified')`
52. `tests/test_v4967_finalizer_identity.py::test_one_rejected_positive_does_not_change_verified_sibling` — Retired-contract expectation (needs adjudication). `AssertionError: assert ['Found', None] == ['Found', 'Unverified']`

## Environment and next actions

- Some collection modules were excluded because `streamlit`, `langchain_core`, `langchain_ollama`, and `yake` could not be installed. These exclusions were identical for the available preview and successor comparison.
- Provider mocks written for historical final `uncertain` JSON now fail the intentionally stricter three-choice schema. Recreate the same negative/transferable tests with legal final responses and assert both source validation and processing states.
- Complete native Windows/Streamlit UI, source restoration, provider failure, specialist experience/degree, and live-quality qualification before deployment.
- Do not silently rewrite candidate evidence, benchmark gold labels, or original CVs to make old assertions pass.
