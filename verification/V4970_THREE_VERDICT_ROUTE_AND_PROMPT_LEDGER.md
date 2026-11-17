# v4.9.70-rc1: three-verdict route, model-prompt and execution ledger

This is a route-level **implementation inventory**, not a feature-complete certificate. An intermediate evidence relation such as `uncertain` is distinct from a final candidate verdict.

| Route / prompt | Live final response | Current behavior / evidence | State |
|---|---|---|---|
| `unified.UNIFIED_PROMPT` | `found/transferable/not_found` | Typed model decision; still requires supervisor evidence checks; preview tests carried forward | Partially qualified |
| `unified.FINAL_ADJUDICATION_PROMPT` | Three choices | Independent source-grounded response; invalid fourth choice forbidden | Partially qualified |
| `condition_review.REVIEW_PROMPT` | Three choices, `facet.relation` may be uncertain | Real supervisor flow tests all three decisions, 429, bounded response correction and distinct pending-review state | Offline e2e verified |
| `assessor.SYSTEM_PROMPT` | `matched/transferable/not_matched` | Live request uses new strict schema; source-bound Transferable/no-credit regression | Offline verified |
| `assessor.CORRECTION_PROMPT` | Same three choices | Correction live schema updated; response-invalid and provider-failed rows remain without a fabricated negative | Partially qualified |
| `ui.final_decisions._JUDGE_PROMPT` | `matched/transferable/not_evidenced` | Three outcomes; optional legacy judge retained for historical contexts; current UI reads canonical decision directly | Partially qualified |
| `semantic.transferability` full/compact/batch | `direct/transferable/related_only/not_evidenced/uncertain` | **Non-scoring shadow capability relations only**. These are not final JD requirement verdicts; separate evidence relation schema retained | Full behavior pending independent test |
| JD typing, decomposition and retrieval | May contain evidence uncertainty | No candidate verdict issued by these stages; preserve semantic diagnostics | Retained |
| `compound_validation.apply_compound_checks` | None, work scheduling | Unresolved source meaning creates pending state instead of semantic error or arbitrary negative | Tested |
| `condition_review.review_compound_uncertainty` | Three choices | Corrected malformed rows once; real rate limit pauses; successful siblings kept | Tested offline |
| `experience_validation.apply_experience_checks` | Deterministic specialist result | Numeric and role scope gates still need all ambiguous cases through final canonical assessment | Partial |
| `qualification_validation.apply_qualification_checks` | Deterministic specialist result | Degree/field constraints and source checks retained; all higher-degree and unclear credential paths still need full qualification | Partial |
| `pipeline.reconcile_final_assessments` | Canonical Found/Transferable/Not Found or null | Source identity verified; pending compound work cannot become a fake provider failure; strict score boundary | Offline verified for current fixtures |
| `CVRanker.run` resume | Canonical saved rows | Compatible completed rows reused on restarted instance; zero LLM requests; changed build rejected | Tested offline |
| `weighted_scoring` / `ranking_reasoning` | One canonical presentation | Incomplete has null official score/rank; separate provisional floor; no new Unverified from missing row | Tested offline |
| Dashboard + `ui.unified_decisions` | Three complete outcomes or `Assessment incomplete` | Three-result projection, historic Unverified only in historical display, current status icons/filter and restore logic updated | Source reviewed; native Streamlit blocked |
| `report_bundle.complete_results_zip` | Same decisions as canonical record | JSON, CSV, candidate Why, and export guard validate records | Tested offline |
| Old saved reports | Historical vocabulary preserved | Legacy `Unverified` deserializes without silent conversion; full historical migration not yet complete | Partial |

## Representative regression controls

- `tests/test_v4970_supervisor_three_verdict_e2e.py` — fictional approved compound JD; three verdicts through supervisor entry point, 429 pause, bounded response correction, legacy 3-choice schema, JSON/ZIP Why, restart and weight-only no-call behavior, missing-result UI projection.
- `tests/test_three_verdict_transition.py` — completion/no-final-verdict invariant, source identity, no official score for unfinished work, old-report text preservation, strict model schemas.
- `tests/test_v4965_independent_compound_review.py` — forged IDs and incomplete approved AND clauses are rejected after a bounded correction, with typed processing failure; no false credit.
- `tests/test_v4917_frozen_skill_scope.py` — no unapproved professional-use criterion, correction exhaustion gives schema failure rather than candidate failure.
- Previous v4.9.68 and v4.9.69 regression suites remain included. Do not count old semantic-uncertainty expectations as passing current protocol assertions without updated contract tests.
