# Phase 7F.2 — Forensic root cause and source-scope repair

**Build**: `evidence-scope-forensic-fix-2026-10-13`

## Executive finding

The defects did **not** all begin in Phase 7F. Archived source comparisons give the following narrower, reproducible chronology:

| Earliest confirmed release | Directly demonstrated behavior | Consequence |
|---|---|---|
| Phase 6B (earliest accessible archive here) through 7E | `Python\nPyTorch\n4 years of professional experience.` becomes one `other` segment: `Python PyTorch 4 years of professional experience.` | Provenance/source facts can be falsely combined; do not conclude the code first appeared in 6B without older snapshots. |
| Phase 7B | New experience verifier evaluates explicit year thresholds against resume segments | It creates a new scoring path exposed to pre-existing line concatenation. |
| Phase 7E | Broader 200-label dataset reports fallback 148/200: 43 missed matched skills and 3 false-positive matches; Qwen hybrid also 148/200 | Benchmark surfaced pre-existing extraction/validation errors, not an independent regression in Phase 7E's matching code. |
| Phase 7F | Source-line preservation and inferred unheaded skill detection improved fallback to 197/200 | `No experience with\nPython\nDjango` became `No experience with` + positive `Python` + positive `Django`: a new safety regression. |
| Phase 7F.1 | New specific safety checks for unrelated years and Qwen's unrelated tenure-based semantic citations | The split-line negative and copied nested JD section risks remained unaddressed. Live remeasurement of 7F.1 is not yet available. |
| **This release: 7F.2** | Carry explicit negative/learning scope across neighboring physical lines, keep job-ad regions non-candidate even across nested generic headings, add fallback segment IDs | Fixes these reproducible failures without modifying score or JD labels. |

### Exact failing input at 7F.1

```
No experience with
Python
Django
```

Previously the segmenter emitted positive `inferred_skills` entries for `Python` and `Django`; fallback *matched* both. Under 7F.2 both are **not_matched** and reference physically grounded source lines.

```
Currently learning
Python
Django
```

Previously both received **matched**; now both are **uncertain**, with zero required-coverage credit.

```
Requirements:
Skills
Python
Django
```

Previously the nested `Skills` heading escaped the non-candidate region. This release keeps it blocked as copied job criteria.

### Implementation changes

- `cv_ranker/segments.py`: preserves blank-line boundaries, attaches a dangling negation/learning control phrase to every contiguous compact item, treats unheaded recruiter request preambles as non-candidate, and fails closed on nested headings inside copied JD sections. `source_lines` remains the physical provenance. This is a generic grammar/layout policy, not a skills dictionary.
- `cv_ranker/fallback.py`: now attaches `evidence_ids` and `EvidenceCitation` to deterministic fallback rows as well as free-text evidence. Scores and statuses are unaffected on the old corpus.
- `tests/test_phase7f2_forensic_scope.py`: parametrized tests for first/next list item, unheaded and colon-prefixed negative and learning spans, copied nested headings, split experience, blank-line boundaries, fallback IDs, and Qwen's deterministic source guard.
- `scripts/forensic_scope_demo.py`: an eight-case demo recording raw CV lines, sections, source IDs and expected/final classifications.

### Benchmark interpretation

The original `phase7e-synthetic-v1` dataset and SHA-256 **29df6dadc386097db86de01ad233a8fde50da74ff3eac2f9432d268854ef9357** were **not changed**.

- Default fallback: **197/200** (98.5%), **0** credited-match false positives on those *existing* cases.
- Optional exact-initialism: **199/200** (99.5%), **0** credited-match false positives on those *existing* cases.
- Default outstanding: 2 NLP, 1 GCP acronym cases. The literal-initialism option can recover NLP but cannot justify GCP from the two-word text `Google Cloud` without an approved source-term relation.
- **Phase 7F.2 live Qwen accuracy is not measured in this environment**; the last submitted Phase 7F live run was 194/200. Do not claim the new source-line tests prove live model accuracy or real hiring reliability.

### Known risks and follow-up

Unheaded documents can be ambiguous; a missing header does not authenticate whether a compact line is a skill, role title or copied text. The qualifier recovery is intentionally conservative and depends on visible structural boundaries; e.g. a blank line ends its scope. Qwen can still propose a false semantic equivalence that cannot be disproved by literal validation alone. Production review requires independent evidence validation, unseen documents, adversarial PDF/DOCX testing, human HR adjudication, fairness/privacy review, and repeatability on the actual Ollama environment. **Do not auto-reject applicants on uncertain/unverified fields.**
