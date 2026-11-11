# Repository audit and cleanup plan

**Repository:** CV Ranker, Supervisor Edition, Phase 7G  
**Reviewed:** 2026-11-10  
**UI release:** 4.9.45  

**Phase 2E packaging safeguard (4.9.45):** Streamlit's `.streamlit/secrets.toml` and `secrets.*.toml` (OIDC credentials/cookie secrets), non-example `.env.*` variants and private-key extensions are explicitly excluded from the hashed source distribution. A synthetic regression test exercises the manifest builder with planted fake secrets; those items must never be included in release ZIPs. No applicant output or database is deleted as part of this change.

**Phase 2C disposition (4.9.44):** Added one cohesive `cv_ranker/recovery_bundle.py` module for signed portable checkpoints. Reused existing frozen-JD/input identities and report models; did not duplicate assessment, scoring or source verification logic. The generated per-installation key lives in ignored `.cv_ranker_cache/` and must never be packaged. No additional source files were deleted in this phase.
**Assessment build:** `phase7g-v4-9-43-mixed-batch-recovery-2026-11-10`; protocol 32

This is a source-inventory and reference audit, **not** a declaration that every unimported function is dead. Streamlit callbacks, CLI entry points and test fixtures can be referenced dynamically. Suggestions below distinguish deletion from archiving and refactoring. The 4.9.43 pass archived documentation and fixed one validated recovery bug, but did not delete tests, scoring formulas, model prompts, compatibility scripts or historical benchmark evidence.

## Completed safe cleanup (4.9.43)

| Disposition | Exact action | Recoverability |
|---|---|---|
| Archived | All 47 prior `docs/RELEASE_NOTES_V4_*.md` moved into `docs/history/releases/`. | The original Markdown contents remain in the distributed source ZIP. |
| Archived | `PROJECT_MAP.md`, `PROJECT_SUMMARY.md`, `PROJECT_STATUS.md`, `TECHNICAL_DECISIONS.md` and `VALIDATION.md` moved into `docs/history/legacy_reference/`. | Complete original files retained; the canonical content is in `docs/ARCHITECTURE.md`. |
| Added | `docs/INDEX.md` and 4.9.43 release notes; updated canonical README and architecture references. | Navigation is explicit; the older release records are linked as history. |
| Preserved | Python modules, older diagnostic launchers, `.venv`, evaluation evidence and all sample fixtures. | No unverified dead-code deletion was performed. Build packaging excludes generated environments and sensitive output. |

**External links:** Historical notes may contain old relative file links. They were preserved as records rather than rewritten to appear current; use the [documentation index](INDEX.md) and the archived filename to locate a moved reference. No application code or tests depend on the old documentation paths (manifest hashes were regenerated after these moves).

## 1. Proposed removal and consolidation actions

| Priority | Scope | Concrete action | Safety / reason |
|---|---|---|---|
| P0 | `.venv/` (approximately 553 MiB locally) | **Exclude from commits and distributable ZIPs; do not delete the installed developer environment.** Recreate locally from `requirements.txt` when needed. | Reproducible dependency environment; already excluded by `.gitignore` and manifest builder. Removing it would break the Windows launch scripts until reinstalled. |
| P0 | `**/__pycache__/`, `**/*.pyc`, `.pytest_cache/` | **Delete generated copies** when cleaning a checkout or artifact staging directory; keep excluded by `.gitignore`. | Python/pytest rebuild them automatically. No need to store or ship. |
| P0 | `.env`, `outputs/`, `.cv_ranker_cache/`, applicant exports and temporary upload files | **Never ship, commit or move into `/docs`.** Delete only after retention/security review. | Secrets and applicant-derived evidence may be sensitive; the manifest builder and Git ignore these paths. |
| P1 | Root `README.md` (old 56 KB chronological changelog) | **Replace with concise current-state README.** Preserve the old text as `docs/history/README_RELEASE_CHRONICLE_PRE_UNIFIED.md`. | The old README repeats dozens of milestone notes and outdated instructions. The original remains traceable in history. |
| P1 | `docs/ARCHITECTURE.md` (old description) | **Replace with authoritative current architecture.** Preserve superseded text in `docs/history/ARCHITECTURE_PRE_UNIFIED.md`. | Previous document incorrectly excluded embeddings/cloud inference and described older scoring. |
| P1 | `docs/history/legacy_reference/` (five former root-level docs) | **Done: consolidated current facts into `docs/ARCHITECTURE.md` and archived original files.** Do not treat their historical benchmark figures as current. | No code/test dependencies found for the prior paths; retained for provenance. |
| P1 | `docs/SUPERVISOR_UI_GUIDE.md`, `docs/SUPERVISOR_WALKTHROUGH.md`, `docs/DEMO_GUIDE.md`, `docs/OPENROUTER_SETUP.md`, `docs/BENCHMARK_GUIDE.md` | **Retain as targeted operating manuals**, but update/version them and link from the unified guide; avoid restating complete architecture in each. | Useful task-specific details, though older guides may describe now-superseded behavior. |
| P2 | `docs/history/releases/` (47 archived releases), `docs/V48_*.md`, `docs/checkpoints/` | **Done:** archive prior release notes. **Remaining:** evaluate possible archival of `V48_*` and checkpoints in a later link-repair release. | Chronological development and prior decisions are records, not the live specification; historic link text is retained. |
| P2 | `scripts/run_phase7d_demo.cmd`, `scripts/run_phase7e_*.cmd`, `scripts/run_phase7f*.cmd`, old benchmark/trace wrappers (22 `run_*.cmd` in `scripts/`) | **Mark as legacy/diagnostic; move only genuinely unused launchers to `scripts/legacy/` after test and documentation reference migration.** Keep `run_ui.cmd`, `run_tests.cmd`, `run_runtime_check.cmd`, `run_supervisor_demo.cmd` in root. | Several wrappers are referenced by tests or other wrappers; unverified blanket deletion is unsafe. |
| P2 | `evaluation/results/repeatability/trial_01_*.json`, `trial_02_*.json`, `trial_03_*.json` | **Optionally deduplicate storage via an indexed archive**, retaining all six logical trial IDs, metadata and hashes. | Same-batch trials have byte-identical output (two groups of three), but those repeats are evidence of repeatability; never simply erase them. |
| P2 | `sample_data/applied_ai_jd.txt` and `sample_data/applied_ai_documents/jd/Applied_AI_ML_Engineer_Updated_JD.txt` | **Keep both aliases until consumers migrate to one canonical fixture.** Then replace the secondary copy with a documented fixture-generation step. | Byte-identical, but both paths are referenced by different tests and a demo launcher. |

### Exact duplicate-content result

An SHA-256 comparison of non-generated project files (excluding `.venv`, Python caches and the manifest itself) identified only these duplicate groups:

1. Three `evaluation/results/repeatability/trial_0{1,2,3}_batch_3.json` files.
2. Three `evaluation/results/repeatability/trial_0{1,2,3}_batch_20.json` files.
3. `sample_data/applied_ai_jd.txt` and `sample_data/applied_ai_documents/jd/Applied_AI_ML_Engineer_Updated_JD.txt`.

No byte-for-byte duplicate production Python module was found in that comparison.

## 2. Refactor candidates, not safe deletions

- **Two presentation reconciliation adapters:** `cv_ranker/ui/unified_decisions.py` is the current LLM-assessment projection; `cv_ranker/ui/final_decisions.py` handles legacy/offline focused judgments. `ui/dashboard.py` invokes both deliberately. Consolidate their shared row schema, citation formatting and notice handling behind one interface **after** cross-mode regression tests; deleting either now would break an active path.
- **Two scoring layers:** `cv_ranker/scoring.py` holds the legacy/base coverage and immutable score-boundary validations; `cv_ranker/weighted_scoring.py` computes the supervisor's editable weighted view. They are different contracts, not redundant implementations. Use clear names (`base_coverage`, `supervisor_weights`) in a future non-breaking migration only.
- **Scattered presentation shaping:** `cv_ranker/ui_support.py`, `cv_ranker/ranking_reasoning.py`, `cv_ranker/report_bundle.py`, and `ui/dashboard.py` each build some display/export objects. Introduce a single immutable `SupervisorResultView`/schema and test UI/CSV/ZIP parity before merging functions.
- **Large orchestration modules:** `cv_ranker/unified.py` and `cv_ranker/ui/dashboard.py` combine numerous responsibilities. Future extraction targets include evidence batching, source validation, recovery state machines, and view components. Preserve source-grounding and request-budget invariants throughout; this audit does not authorize a semantic rewrite.
- **Trace utilities are distinct:** `tools/trace_demo.py` is a runnable diagnostic walkthrough; `evaluation/trace.py` records LLM attempts for benchmarks. Both are referenced by tests and should **not** be merged merely because of their names.
- **Shadow/legacy semantic tools:** `cv_ranker/semantic/integration.py`, `cv_ranker/semantic/transferability.py` and `scripts/phase7g_shadow.py` are compatibility/diagnostic paths, whereas `cv_ranker/unified.py` owns live LLM evidence retrieval. A retirement plan must enumerate CLI users and benchmark dependencies before removing any of them.

## 3. Recommended directory structure

```text
CV_Ranker_Supervisor_Edition/
├── README.md                      # concise setup and status
├── .env.example                   # non-secret settings reference
├── requirements.txt
├── app.py | main.py | doctor.py    # UI, CLI, health
├── run_*.cmd                      # four supported root launchers
├── cv_ranker/
│   ├── config.py | schemas.py | pipeline.py | unified.py
│   ├── documents.py | jd.py | segments.py | scoring.py
│   ├── weighted_scoring.py | ranking_reasoning.py
│   ├── ui/                     # presentation/reconciliation adapters
│   ├── semantic/               # embeddings, cache, research/diagnostics
│   └── build_manifest.json     # signed-by-hash inventory (not cryptographic signature)
├── docs/
│   ├── ARCHITECTURE.md          # authoritative current behavior
│   ├── INDEX.md                  # current versus historical navigation
│   ├── REPOSITORY_AUDIT.md      # disposition and migration register
│   ├── RELEASE_NOTES_V4_9_43.md # current release changes
│   ├── guides/                  # optionally relocate maintained how-tos
│   └── history/                 # preserved releases and legacy references
├── scripts/
│   ├── rebuild_manifest.py | package_source_release.py
│   ├── diagnostics/            # maintained investigations
│   └── legacy/                 # old command wrappers, after reference migration
├── sample_data/                 # regression input fixtures
├── evaluation/                  # benchmark datasets and historical results
├── tests/                       # automated regressions
└── tools/                       # developer-only tracing utilities
```

The tree is a **target architecture**, not a claim that the future `guides/`, `diagnostics/`, or `legacy/` folders were already created.

## 4. Migration gates

1. Search exact references (`rg`) before moving each file. Update all relative Markdown paths, `.cmd` dependencies, tests and documented commands.
2. Preserve historical benchmark outputs and original source test fixtures by hash; avoid rewriting them to make results appear better.
3. Run `python -m pytest -q`, `python -m cv_ranker.runtime_check`, and smoke-test both model and offline UI paths. The live cloud path requires authorization and costs money.
4. Rebuild the manifest **after** every approved documentation/file move with `python scripts/rebuild_manifest.py` and package using `python scripts/package_source_release.py ABSOLUTE_OUTPUT_ZIP`.
5. Do not claim production deployment certification from unit tests: multi-user concurrency, storage retention, privacy review, provider reliability and blinded ranking quality still need separate acceptance testing.
