# Legacy test-expectation migration — v4.9.71 protocol 57

**Principle:** Tests were not removed, muted or blanket skipped. Obsolete assertions were replaced with current **null current verdict + typed processing state + source validation + no-score** checks where possible; old model answers containing `uncertain` are now rejected by final three-choice schemas rather than silently normalized into a candidate decision. Deterministic provider stand-ins remain fixtures only, not production hardcoding.

- `test_surgical_fixes.py`: a timed-out model no longer produces fake fallback `matched`.
- `test_v486_domain_neutral_validation_repair.py`, `test_v487_system_contracts.py`, `test_v48_unified.py`, `test_v491_live_failure_roots.py`, `test_v4937_cited_evidence_without_model_requotation.py`, `test_v4943_mixed_batch_recovery.py`, `test_v4958_decision_integrity.py`: historical `Unverified` assertions replaced by unfinished current-decision checks, while genuine citations/siblings remain protected.
- `test_v4922_weighted_scoring_and_bundle.py`, `test_v4931_dynamic_allocation_and_reasoning.py`: incomplete candidate official score and rank must be null; provisional information stays separate. No score is implicitly zero.
- `test_v4955_uncertainty_and_editable_local.py`: old final `uncertain` replies must fail Pydantic validation, then legal `not_found` / `transferable` choices are independently tested for semantic relation consistency.
- `test_v4935_focused_verification_reliability.py`: replaced old prohibited final `uncertain` fixture with a wrong-highlight `found` that enters the same real bounded independent-review path, and preserves fabricated-excerpt and schema-error negative controls.
- `test_v494_transferable_root_contract.py`: configure the deterministic provider **before** ranker construction. Do not bypass failed model-initialization guards by assigning `ranker.llm` after constructing an unavailable engine.

**Evidence:** `V4971` seven original regressions RED against RC1 (external `DA_RED` log), GREEN after repair, and the full dependency-limited suite with 1554 passing tests and failures solely reporting missing packages. Native Windows/UI and actual model quality cannot be inferred from these checks.
