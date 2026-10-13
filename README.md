**Phase 7F.2 Forensic Source Scope Repair** — Build `evidence-scope-forensic-fix-2026-10-13`. See `docs/PHASE_7F2_FORENSIC_ROOT_CAUSE.md`. Existing coverage and scoring rules unchanged.

# Phase 7F.1 — Live Qwen Safety Corrections (latest)

**Build:** `evidence-integrity-live-safety-2026-10-13`. Phase 7F's Windows live benchmark exposed 6/200 mismatches: 3 existing acronym misses, 2 unrelated-tenure decisions wrongly left `uncertain`, and one unsafe Qwen `matched` decision for Electronic health records citing only "1 year of nursing experience." This hotfix makes a cited, unrelated generic tenure sentence insufficient to support a distinct named competency, and prevents unsupported model experience matches from being upgraded to `uncertain` when the required subject is absent. See [Phase 7F.1 live safety notes](docs/PHASE_7F1_LIVE_SAFETY.md). **No semantic synonyms, model changes, embeddings, or score formula changes.** The last measured 194/200 **live** score belongs to the preceding Phase 7F build; rerun live on Windows for this version.

---

# Phase 7F — Evidence integrity repair (latest)

**Latest build:** `evidence-integrity-repair-2026-10-13`. Same 200 independently authored synthetic labels: Phase 7E fallback 148/200 → Phase 7F default fallback **197/200**, zero false-positive matches (synthetic); optional strict initialism 199/200 with one intentionally unresolved non-literal GCP mapping. **Not industrial/real CV accuracy.** Full technical notes: [Phase 7F documentation](docs/PHASE_7F_EVIDENCE_INTEGRITY_REPAIR.md). Windows checks: `run_runtime_check.cmd`, `python -m pytest -q`, `python doctor.py --live`, `scripts\run_phase7f_fallback.cmd`, `scripts\run_phase7f_initialism.cmd`, `scripts\run_phase7f_live.cmd`. No embeddings, synonym catalogue, arbitrary preferred bonuses, or score changes.

---

## Phase 7E — Expanded benchmark and ranked-candidate evaluation (latest)

**Current build:** `industrial-benchmark-v1-2026-10-13`. Based on the **unchanged production Phase 7D matching/scoring engine**, Phase 7E adds 8 new labelled synthetic JDs, 40 resumes, 200 labelled decisions, independent per-requirement oracle status comparisons, ranking-order metrics, benchmark checksum validation and a supervisor-facing report. **No new Qwen prompts, no embeddings, no scoring changes.**

Run the new benchmark using `scripts\run_phase7e_fallback.cmd` (no Ollama needed) or `scripts\run_phase7e_live.cmd` (requires local Ollama); results go into `outputs\phase7e_*.json` and `outputs\phase7e_*report.md`. Read [Phase 7E documentation](docs/PHASE_7E_INDUSTRIAL_BENCHMARK.md) and [labeling protocol](evaluation/industrial_dataset/LABELING_PROTOCOL.md).

**Observed offline synthetic baseline:** 148/200 status decisions correct (74.00%), 3 false-positive credited matches, 43 missed matches, 76.25% mean pairwise ranking agreement. **This is neither Qwen accuracy nor production validation**; the Windows live run is pending.

---

# CV Ranker | Explainable Local Resume Ranking

**Status:** Working local prototype (not a validated production hiring system).
**Current build:** `industrial-benchmark-v1-2026-10-13` (evaluation-only additions; Phase 7D production engine unchanged). Previous build: `compound-eligibility-verification-2026-10-13`. — Phase 7D adds conservative source-backed AND/OR verification and optional reviewer-selected eligibility gates (document evidence only). See [Phase 7D notes](docs/PHASE_7D_COMPOUND_ELIGIBILITY.md). Phase 7B enforces explicit, source-grounded numeric experience minimums using Phase 7A typed JD constraints. See [Phase 7B notes](docs/PHASE_7B_EXPERIENCE_VERIFICATION.md). Phase 7A adds source-grounded typed JD metadata. See [Phase 7A notes](docs/PHASE_7A_TYPED_REQUIREMENTS.md). Based on Phase 6E optional reviewer-approved equivalence input with full source and approval provenance. See [Phase 6E notes](docs/PHASE_6E_REVIEWED_EQUIVALENCE.md), [Phase 6D experiment](docs/PHASE_6D_EXACT_INITIALISM_EXPERIMENT.md) and [Phase 6C notes](docs/PHASE_6C_ACRONYM_DIAGNOSTICS.md). It retains Phase 6B focused abbreviation clarification on top of Phase 6A safety checks. See [Phase 6B notes](docs/PHASE_6B_ABBREVIATION_CLARIFICATION.md), [Phase 6A](docs/PHASE_6_INTEGRITY_HOTFIX.md), [Phase 5](docs/PHASE_5_SECOND_LOOK.md) and [Phase 4](docs/PHASE_4_SOURCE_ANCHOR.md).  
**Model:** `qwen2.5:3b` via Ollama + LangChain.  
**Main interface:** Streamlit. **Language:** Python 3.11.

## Supervisor demo — start here

With Ollama running and `qwen2.5:3b` installed, open PowerShell in this folder.

```powershell
# First-time setup only (omit these three commands if .venv already works)
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
ollama pull qwen2.5:3b

# Quick check and live UI
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe doctor.py --live
.\run_ui.cmd
```

Open **http://localhost:8501**, select the supplied **Backend demo** or **HR demo** (or upload a JD and resumes), and show the ordered rankings plus the requirement-by-requirement evidence.

**One-click option:** `run_supervisor_demo.cmd` performs the integrity check, the live health check, then opens the Streamlit launcher. (Running the health check calls local Ollama.)

**Requirements:** Windows, Python 3.11, local Ollama installed/running, sufficient RAM for the Qwen 3B model, and a `.venv` created in this folder. No cloud API keys, embedding models, PostgreSQL or SQLite required for this prototype.

## Project layout

```text
CV Ranker/
├── README.md                      # this start page
├── app.py                         # Streamlit UI
├── main.py                        # CLI entry point
├── doctor.py                      # environment + end-to-end live check
├── requirements.txt               # pinned dependencies
├── run_supervisor_demo.cmd        # guided live demo
├── run_ui.cmd                     # UI launcher (checks port 8501)
├── run_runtime_check.cmd          # build file integrity
├── run_tests.cmd                  # automated tests
├── cv_ranker/                    # production ranking implementation
├── evaluation/                   # labelled benchmarks and results (NOT production)
├── tools/                        # detailed stage-by-stage trace demo
├── scripts/                      # optional demo/benchmark utilities
├── sample_data/                  # backend and HR test inputs
├── tests/                        # automated regression tests
├── docs/                         # architecture, validation, technical choices
└── .streamlit/                   # UI settings
```

Generated `outputs/`, `.venv/`, caches and temporary files are **not** included in the distribution.

## How ranking works

1. Read the job description (TXT, MD, DOCX or selectable-text PDF).
2. Generate possible JD keyphrases with **YAKE**; they are only hints.
3. Use **Qwen through LangChain** to interpret the source JD into required/preferred/unknown requirements. Python preserves explicit JD items if Qwen omits them; recovery is flagged.
4. **Phase 7A:** enrich every frozen JD requirement with its source-based kind, explicit numerical/degree attributes, logical wording, original line numbers, and review-needed status. Optional Qwen type suggestions for ambiguous lines are marked for human review, disabled by default and do not change scores.
5. Read each CV and create source segments `S001`, `S002` … with section context.
6. Assess each CV against the **same frozen requirements** using structured Qwen output.
7. Check cited source IDs (strict 1–3 distinct IDs), literal supporting terms where present, explicit numerical years contradictions, and generic safety/context rules. An optional **second Qwen look** reconsiders only negative decisions with plausible orthographic source clues; a bounded focused acronym clarification may then ask Qwen again for a missing quoted source term. Python never treats those clues as verified synonyms. No separate verifier or semantic alias dictionary.
8. Validate the one-to-one frozen requirement/assessment scoring contract, then calculate the primary score from **matched required / total required x 100**, with preferred coverage separate; sort by deterministic score.
9. Optionally, when an authorized HR reviewer supplies a per-JD JSON approval file, explicitly approved aliases can be source-checked and marked as **reviewer-assisted**, never as pure Qwen. Without a file, behavior is unchanged.
10. Show ranked candidates, evidence source lines, decisions and diagnostic warnings.

See **[Architecture](docs/ARCHITECTURE.md)** and **[Technical decisions](docs/TECHNICAL_DECISIONS.md)** for supervisor questions.

## Known boundaries

No embeddings, cosine similarity, vector database, related-skill credit, LLM-generated rank, or active verifier. A verifier is potential future work, not part of this prototype. Learning-only/uncertain assessments receive no primary-score credit.

**Latest user-observed full 21-case Phase 6C results (2026-10-12):** The 21-case labelled assessment and full pipeline each scored **19/21 (90.48%)** with 100% matched precision and 83.33% matched recall. The user's Phase 6D focused seven-case A/B scored **5/7 baseline and 6/7 with exact-initialism enabled**, with `NLP` recovered by Python and `GCP` still unresolved. Model raw outputs varied across the two executions. These measurements are a small synthetic benchmark, **not** validated recruitment accuracy. Phase 7A adds offline-tested metadata only; no new Ollama ranking benchmark has yet been measured. See [Phase 6E](docs/PHASE_6E_REVIEWED_EQUIVALENCE.md).

## Optional commands

```powershell
.\run_tests.cmd
.\scripts\run_backend_demo.cmd
.\scripts\run_hr_demo.cmd
.\scripts\run_trace_demo.cmd
.\scripts\run_benchmark.cmd
.\scripts\run_benchmark_pipeline.cmd
.\scripts\run_repeatability_probe.cmd
```

> The `evaluation/` folder is for experiments and measuring limitations. It is not imported by the ranking engine to make a candidate decision.

## Optional Phase 6D exact-initialism experiment

The optional `--exact-initialism` flag recognizes *literal initialisms* formed by the initials of 3–5 Title-Case words in a JD requirement. It is disabled by default and never maps the different-length acronym `GCP` to `Google Cloud`. Use a same-build benchmark A/B instead of assuming better accuracy. See [Phase 6D notes](docs/PHASE_6D_EXACT_INITIALISM_EXPERIMENT.md).

## Optional Phase 6E reviewed equivalence input

For a reviewer-authorized, job-specific alias use `--approved-aliases path\to\approved.json` with the CLI, or upload JSON under **Optional HR-reviewed equivalences** in Streamlit. The file must name the **exact frozen JD requirement** as shown in the results table; the UI provides a blank JSON template. The reviewer must enter the alias, identity and rationale; no synonyms are pre-approved. See [Phase 6E](docs/PHASE_6E_REVIEWED_EQUIVALENCE.md).

## Phase 7A typed JD output

In both CLI JSON and Streamlit, each frozen JD requirement now has a `constraint` containing source-derived `kind`, `minimum_years` (when explicit), `subject`, `degree_level`, `field_of_study`, `operator`, `options`, original JD `source_line_numbers`, `origin`, and `requires_review`. These are **descriptive only** and cannot change scoring or eligibility. Qwen suggestions for unresolved type labels are optional via `--llm-type-review` / UI checkbox and are always marked for review. The exact Phase 6E ranking behavior remains the default. See [Phase 7A documentation](docs/PHASE_7A_TYPED_REQUIREMENTS.md).

## Phase 7B — Experience verification demo

Phase 7B verifies explicit years for typed JD `experience` requirements without inferring durations from calendar dates or awarding transferable-skill credit. Results include an `experience_check` diagnostic for each numeric requirement (source segments, numerical bounds, rationale, status). Conflicting/ambiguous claims get no automatic credit.

```powershell
.\.venv\Scripts\python.exe main.py --no-llm --details --jd sample_data\experience_jd.txt --resumes sample_data\experience_resumes --output outputs\experience_ranking.json
```

The existing Backend and HR fallback demos retain the same scores/ranks as Phase 7A. **This Phase 7B release has not been validated against live Qwen**; rerun live smoke checks and both 21-case benchmarks on the target Windows PC. This new gate may intentionally disagree with legacy subjective experience benchmark labels where they infer skill-specific tenure from general career years.


### Phase 7D commands

```powershell
.\.venv\Scripts\python.exe main.py --no-llm --details --jd sample_data\compound_jd.txt --resumes sample_data\compound_resumes --output outputs\compound_no_gates.json
.\.venv\Scripts\python.exe main.py --no-llm --details --jd sample_data\compound_jd.txt --resumes sample_data\compound_resumes --eligibility-policy sample_data\compound_eligibility_policy.EXAMPLE.json --output outputs\compound_with_gates.json
```

With no HR policy, `eligibility.status=not_configured`. With a supplied policy, required frozen criteria can act as *document-evidence review gates* (satisfied, unmet, needs review) without changing match percentages or ranking positions. A claim is never independent credential authentication. For the exact schema, source limits and scope, see [Phase 7D documentation](docs/PHASE_7D_COMPOUND_ELIGIBILITY.md). The last observed Windows Phase 7C full-pipeline benchmark was **18/21, 85.71%, mixed mode**. Phase 7D live Ollama benchmarks have not been run.
