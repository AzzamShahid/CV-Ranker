# Phase 7G — Nonpositive Evidence Review (shadow-only)

This checkpoint is built on the **603-test** relationship-consistency-review project. It addresses a concrete false-negative diagnostic blind spot observed in the next local Qwen run: `relationship_quality.json` said zero flags even though the model categorized evidence such as `Containerized backend applications using Docker.` as `related_only`.

## What's different

* Retains previous checks for dubious `transferable` labels and `direct` judgments based on a bare skill listing.
* Adds candidate-and-requirement-scoped checks for `related_only`, `not_evidenced`, and `uncertain` judgments when the *retrieved, authorized CV text* includes the exact named requirement in plausible work-context prose. These produce **review flags only**; they do not automatically relabel candidates.
* Excludes listing-only sources from this work-evidence signal; conservatively suppresses negation, learning, intention, exposure, and uncertainty wording. These are generic modality indicators, not profession-specific skill lists. Ambiguous sentences still need a reviewer.
* Flags `direct` labels that cite a named skill only in a skills list while their other cited narrative describes a different technology; the named skill is *claimed*, but use of it in that narrative has not been shown.
* Flags `not_evidenced` when the exact named requirement is listed in the skills section. This is **not automatically a direct match**: the depth of evidence and the employer's requirement must be reviewed.

## Audit of the supplied 603-test live-run JSON

6 total **potential** review signals, not six proven model mistakes:

| Candidate | Requirement | Signal |
|---|---|---|
| 01_strong.txt | R004 Docker | positive work statement overlooked by related-only label |
| 01_strong.txt | R011 FastAPI | exact name appears only in skills list while the additional cited project says Django |
| 01_strong.txt | R012 Node.js | listing of Node.js present, but model chose not-evidenced |
| 02_medium.txt | R003 PostgreSQL | database creation and maintenance overlooked |
| 04_negation_and_learning.txt | R001 Python | developed REST APIs using Python overlooked |
| 04_negation_and_learning.txt | R003 PostgreSQL | maintained PostgreSQL databases overlooked |

`03_weak.txt` has no flags under these rules. Separately, the verifier should investigate semantic inconsistencies in free-text model explanations that a mechanical audit cannot safely resolve.

## Commands (Windows PowerShell)

```powershell
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q
.\scripts\run_phase7g_shadow.cmd --decompose
.\scripts\run_phase7g_transferability.cmd
.\.venv\Scripts\python.exe -m scripts.phase7g_relationship_audit
```

You may rerun **only** the last command against existing `outputs\phase7g_shadow\retrieval.json` and `transferability.json` without any new Ollama calls. That command is read-only for those inputs and outputs `relationship_quality.json`.

## Safety and interpretation

* `source_validated` confirms citation identity and exact quotations, not proficiency, experience duration, or independent truthfulness of CV content.
* An exact keyword in a retrieved segment can still be negated or hypothetical. These generic checks are best-effort, and they do not replace complete, context-aware review.
* The command-line retrospective audit reads the provided JSON and does **not** re-open original CVs; it assumes the live pipeline already validated the retrieval JSON against original candidate segments. For adversarial, edited or untrusted reports, revalidate the originals first.
* All transferability and relationship fields remain **provisional**. This release does not change `ranking.json`, scores, eligibility gates, hiring recommendations, or employer-defined criteria.
* Benchmark recall, false-positive rates, human adjudication, Qwen batching, and role/context constraint verification are still outstanding.
