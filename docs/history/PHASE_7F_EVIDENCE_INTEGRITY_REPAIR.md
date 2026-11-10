# Phase 7F — Evidence Integrity, Recall and Error Containment

**Build:** `evidence-integrity-repair-2026-10-13`  
**Parent:** Phase 7E `industrial-benchmark-v1-2026-10-13`  
**Scope:** targeted, general-purpose repairs to source segmentation, literal CV list evidence, and experience attribution. No new embeddings, model, arbitrary weights, catalogue of skill synonyms, or hiring auto-rejection.

## Summary of the independently labelled *synthetic* benchmark

The **same** eight job descriptions, 40 CV text files, 200 manually authored requirement labels and exactly the same dataset SHA-256 were used for this comparison. No labels, resume fixtures, required/preferred flags or scoring rules were edited. The pre-existing Phase 7E snapshot is `evaluation/results/industrial/phase7e_fallback_baseline.json`.

| Metric | Phase 7E fallback | Phase 7F fallback, default | Phase 7F fallback, optional exact initialism |
|---|---:|---:|---:|
| Three-class accuracy | 148/200 (74.0%) | 197/200 (98.5%) | 199/200 (99.5%) |
| False-positive matches | 3 | 0 | 0 |
| Missed matches | 43 | 3 | 1 |
| Matched precision | 96.20% | 100.00% | 100.00% |
| Matched recall | 63.87% | 97.48% | 99.16% |
| Macro pairwise agreement (ties included) | 76.25% | 98.75% | 100.00% |
| nDCG@3 | 98.91% | 100.00% | 100.00% |

The comparison tool reports **49 corrected decisions and zero regressions** versus the Phase 7E default fallback baseline. The optional initialism option adds two correct NLP cases. **These figures are synthetic text-fixture performance, NOT real hiring accuracy, Qwen-only performance, a guarantee against false positives in real data, or an independently reviewed HR validation.** They must not be presented as 99.5% industrial correctness.

### What was fixed (and why)

1. **Physical-source provenance.** `ResumeSegment` now stores `source_lines` (immutable tuple), separately from the whitespace-normalized text that Qwen cites. This prevents a display join of independent lines from becoming a fabricated claim tying a skill to general career duration. Numeric verification examines physical clauses; genuinely incomplete PDF wraps can be joined when the actual grammar is incomplete.
2. **Unheaded standalone resume lists.** A compact term on its own CV line is classified as `inferred_skills`, separate from explicit `skills`. Only an **entire literal line** equal to a frozen requirement or its explicit JD alternative can earn deterministic skill credit; partial words, a job title containing a skill name, unrelated tools, or fuzzy transferable skills do not count. The line is still only a *self-report*, never proof of actual proficiency.
3. **Section/safety boundaries.** Explicit JD-style headings embedded in CV text are classified `non_candidate`. Lines saying `No experience with:` or `Currently learning:` retain controlling tone even when the CV puts the capability name on the next line. Candidate target-role header is `metadata`, not capability/tenure evidence.
4. **Experience scope.** Explicit subject-bound numeric statements can meet or fail a minimum. Generic overall career experience stays ambiguous if target subject is otherwise suggested; tenure stated for a different subject does not satisfy the target or imply generic tenure. Unrelated work does not become subject-specific because lines were joined. Source line IDs remain traceable.
5. **Evidence tone.** The source checks recognize explicit training/preparation as uncertain rather than proficiency.
6. **Optional initialism recovery in both modes.** Previously `--exact-initialism` worked only with model responses. The existing Phase 6D guard now works consistently in deterministic fallback, too. It is **off by default**, is counted as Python-assisted (`mixed`) when it affects a decision, and can only derive exact initials from a spelled-out requirement. No alias catalogue was added.
7. **Independent adversarial regression tests** (not copied from the 200 evaluation labels) cover domain-independent standalone skills, prompt/requirement copying, negative learning cues, title-only claims, PDF wrapping, general vs unrelated tenure, citation IDs and opt-in behavior.

### What is deliberately NOT fixed by inventing evidence

- **Remaining default errors:** Two `Natural Language Processing` requirements backed by CV `NLP` and one `Google Cloud` requirement backed by CV `GCP`. NLP recovers under optional strict initialism mode; GCP is **not** literal initials of `Google Cloud`. A correct match requires a source-grounded successful Qwen semantic citation or a genuinely authorized **JD-specific, reviewer-approved equivalence**. Do not hardcode `GCP = Google Cloud` into a universal skills dictionary to force this benchmark to 200/200.
- **Real-world validation:** The data consists of short, artificial TXT resumes. PDFs, DOCX columns/tables, OCR, CV authenticity, employment references, license authority validation, demographic fairness, audit identity, authorization and privacy have not been established here. Do not reject any applicant automatically.
- **Model contribution:** Offline results do not test Ollama. Only the user's Windows live benchmark can measure end-to-end performance of the current Qwen system, and the report combines model and Python decisions.

### Windows commands

Backup your current Phase 7E folder. Extract this ZIP and preserve `.venv` from the previous installation.

```powershell
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe doctor.py --live
.\scripts\run_phase7f_fallback.cmd
.\scripts\run_phase7f_initialism.cmd
.\scripts\run_phase7f_live.cmd
.\scripts\run_phase7f_compare.cmd
```

- Default baseline: `outputs/phase7f_fallback.json`, `outputs/phase7f_fallback_report.md`
- Optional exact-initialism report: `outputs/phase7f_initialism.json`, `outputs/phase7f_initialism_report.md`
- Combined Qwen/Python live: `outputs/phase7f_live.json`, `outputs/phase7f_live_report.md`
- Old synthetic baseline vs new fallback: `outputs/phase7f_comparison.json`. The comparison checks the dataset checksum and full row identity.

You can also run the older 21-case assessment and full-pipeline benchmarks with `scripts/run_benchmark.cmd` and `scripts/run_benchmark_pipeline.cmd`. Their labels may disagree with Phase 7B's conservative experience policy; do not silently alter reference labels to mask this.

### A note for supervisor review

The primary score remains `(matched required) / (all frozen required) × 100`; `uncertain` and `not_matched` each contribute zero. Preferred claims do not add arbitrary points. Eligibility stays a separate, optional HR-review policy. Review literal self-report assumptions and manually confirm the remaining abbreviation cases. Prefer unseen, independently reviewed documents before making reliability claims.
