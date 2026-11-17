# Supervisor scoring decision ownership and remaining consolidation

This is a *traced current-source route map*, not proof that one canonical state machine exists across all modes.

| Reachable path | Current decision/side effect | Authority classification | Status |
|---|---|---|---|
| `CVRanker.prepare_jd_review` → `jd.py`/`requirement_typing.py`/review approval | Proposes then freezes employer source criteria | Frozen JD authority after supervisor approval | Existing; narrative edge cases open |
| `unified.assess_candidate` / `assessor._validate_rows` | Model proposals, retries, original S ID validation | Proposal + source constraint, not scoring owner | Existing; multiple policy paths remain |
| `experience_validation` / `qualification_validation` | Sourced role months, completed credential/field constraints | Specialist constraints | Existing; held-out multi-role quality open |
| `compound_validation` | Condition gates and syntax-review designation | Condition constraint | Existing; unsupported syntax must not force Not Found |
| `condition_review.review_compound_uncertainty` | Source-bound semantic facets, per-op dispatch, verified R updates | Bounded semantic proposal after source constraint | NEXT-001 subset dispatch fixed; semantic truth still requires independent review |
| `pipeline.reconcile_final_assessments` | Official Found/Transferable/Not Found/Unverified for unified route | Finalizer; v53 adds original-ledger Found backstop | Tested; legacy/optional consistency still open |
| `scoring.score_candidate`, `weighted_scoring` | Points, category weights and provisional bounds | Read-only score projection | Prior v52 controls preserved |
| `ui/unified_decisions`, `ui/final_decisions`, `ranking_reasoning` | Individual Why and optional focused review | Presentation and optional additional reasoning | Must not silently overwrite official finalizer; full AppTest open |
| `report_bundle.complete_results_zip` | CSV, JSON and reviewer ZIP projections | Read-only export | Offline tests; native UI parity open |
| `resume`/`recovery_bundle`/`LocalOperationLedger` | Restore verified results or preserve unresolved operation states | Historical identity + recovery integrity | NEXT-001 fixed for local claim; power-loss and cloud idempotency open |

**Invariant implemented:** When the active unified pipeline finalizes a row as Found, it must cite original candidate S IDs with unaltered source segment text/section. Missing, foreign or rewritten source is a technical Unverified state; verified siblings survive. Finalization is idempotent in tested inputs and does not spend model credits.
