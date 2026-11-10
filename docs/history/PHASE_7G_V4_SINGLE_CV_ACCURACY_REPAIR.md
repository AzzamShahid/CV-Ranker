# Phase 7G — V4 single-CV evidence and accuracy repair

**Baseline:** The original Phase 7G V4 archive (2026-10-20), **not V5**.
V4's candidate decision table, detailed primary assessments, separate semantic
relationship review, and original source citations are preserved.

## Purpose

Get one candidate's source-backed decisions right before optimizing batch
ranking. A CV **mention**, a CV **skill claim**, a **performed action**, and
**independently verified proficiency** are different evidence levels.

## UI workflow

1. Start `run_ui.cmd`. Leave **Recognize literal initials (e.g., NLP)** checked.
   This check only recognizes an acronym supplied by the JD or formed from the
   exact JD words. It is not a dictionary of technology aliases.
2. Upload one JD and **one PDF, DOCX, or TXT CV**, then select Analyze.
3. Under **02 Rankings & evidence**, read the original V4 primary result and
   separate AI relationship proposal. Expand a requirement to see:
   - The primary decision and its source-backed reason (if supplied).
   - **Evidence checkpoint 1, 2, ...:** all accepted original assessment
     citations (up to the original model protocol's three IDs), each showing
     its segment ID, section, named-term check, and full source text.
   - **Mention checkpoint 1, 2, ...:** *every* exact mention in the extracted
     CV, including derived literal initials, negatives, learning, and copied
     job-ad wording. These are an inspection tool, **not automatic scoring**.
   - Experience, qualification, and compound-condition checks as in V4.
   - In the separate AI relationships section, each cited source is displayed
     individually, with the actual full CV segment and the model's reasoning.
4. Under **03 CV source segments**, search all parsed segments by text or
   section. Review the segment IDs, citation indicators, normalized content,
   and original physical lines. Download `cv_source_segments.json` if needed.

The uploaded file is temporary, so the UI retains this parsed ledger in the
active Streamlit session before removing the upload directory. Re-run a CV to
refresh it. No personal CVs or `.env` are included in this release.

## Accuracy corrections

| Problem | V4-based repair |
| --- | --- |
| Natural Language Processing reported absent even though CV says NLP | UI enables strictly source-checked initials; also accepts explicitly written `Name (ABC)` aliases in the frozen JD. |
| Python matched but cited passage doesn't say Python | Prefer a real named Python source checkpoint if the model cited only unrelated context and direct literal evidence exists elsewhere. |
| Only one explicit source proof survives a deterministic correction | Source guards now retain up to three relevant, distinct original checkpoints. |
| Model says not evidenced because embeddings omit exact skill mention | Shadow retrieval also supplies the source's actual literal named-skill mentions and exact initials as context, marking these additions clearly with **no fabricated cosine score**. |
| An ordinary skills-list claim is described as absence of experience | Primary and semantic prompts distinguish a legitimate self-reported skill from proof of professional delivery. |
| Every row appears to require human review | Universal review flag is not displayed per row; only actual consistency or functional-overlap flags appear when relevant. |
| Transferability counts vanish when one candidate review is incomplete | Available counts are labeled partial; missing reviews are left blank rather than presented as zero. |
| Source text from uploaded CV disappears after analysis | Full, searchable segment ledger is retained in the session and downloadable. |

## Proof of single-CV regression

Bundled `03_sara_functional_transfer.pdf` was checked against the original
Applied AI JD. In the **offline** source-check run, it correctly reports:

- **Python** — matched, citing CV source `S006`.
- **Natural Language Processing (NLP)** — matched, citing `S007`, `S018`, and
  `S005` (different mentions across skills, work history, and summary).
- **Google Cloud** — offline literal fallback still says not matched when the
  CV uses `GCP`; that conventional but *nonliteral* abbreviation is left to
  the configured live model's grounded equivalence evaluation. The UI exposes
  the `GCP` segment so the discrepancy is inspectable; no guessed equivalence
  is silently promoted to a scored match.

Tests include original PDF extraction, an intentionally incorrect model citing
Docker for Python, NLP false-negative correction, negative and copied source
exclusion, all-segment retention, and retrieval top-k omission recovery.

## Verification and limits

Run on Windows after extracting into a **new** folder:

```powershell
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q
.\run_ui.cmd
```

The deterministic single-CV PDF checks and automated regression tests do not
replace a live OpenRouter/Ollama run. The semantic relationship model can still
make errors; its explanations and transferability labels remain proposals and
do not change the primary score. Claims in CVs are not independently verified.
