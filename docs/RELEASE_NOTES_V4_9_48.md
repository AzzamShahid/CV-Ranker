# TextileHR AI / CV Ranker 4.9.48 - compound and tenure reliability

Date: 2026-11-11. Assessment protocol: v34.

## Reproduced live failure

The 4.9.47 supervisor report assessed the sample weaving supervisor as 80%
despite the PDF containing original evidence for three previously rejected
requirements:

- **R001, minimum professional tenure:** the AI cited the summary's 7 years
  4 months of full-time weaving supervision plus the June 2019-present role,
  but the numeric validator required the AI to additionally cite an individual
  duty segment. This dropped the criterion to Not Found.
- **R007, troubleshooting:** the cited work investigated warp/weft breaks and
  loom stoppages, but the mixed AND/OR syntax was invariably downgraded by a
  structural parser that cannot understand descriptive work clauses.
- **R008, defects and corrective action:** the CV described investigating
  fabric faults and documenting corrections, but a literal option check
  expected the JD's *exact wording*, overriding the model's cited semantic
  verdict and discarding the original source passages.

These were final validation errors, **not evidence that the candidate lacked
the skills**. No applicant identity, profession, CV filename, requirement ID,
or weaving-specific keyword is used as a runtime matching exception.

## Changes

1. For a cited, affirmative professional summary containing the JD's own
   work-scope words and numeric tenure, the role validator can corroborate
   the duration against a model-cited dated employer and its **own** affirmative
   duties. It attaches the original duty citation itself and explains the
   provenance. A role title alone, unscoped years, a career in another field,
   an uncited role, or a contradictory duration cannot earn this credit.
2. The compound validator distinguishes short independently named skill
   alternatives from descriptive, performed-work requirements. For the latter,
   it can retain a **source-validated positive model judgment** when original
   citations show performed work and each mandatory AND branch has source
   vocabulary evidence. Mixed AND/OR still requires HR review; this is not
   automatic approval of any keyword combination.
3. Grammatical variants, hyphenated words, and uppercase abbreviations are
   treated as cautious lexical evidence anchors, with no profession dictionary
   or inferred equivalence table.
4. An uncertain/nonmatching compound result no longer automatically erases
   otherwise valid original model citations. Such passages remain visible as
   reviewed but **uncredited**, so a reviewer can inspect discrepancies.
5. Corrected awkward validator prose such as "all of of" in the UI and exports.
6. The **existing cumulative cloud request cap and recovery safeguards remain**.
   This release makes zero additional AI/API calls and does not raise the cap.

## Verification and remaining limits

- Regression replays cover all **18 frozen criteria** (16 JD skills plus one
  experience and one education) from a synthetic counterpart of the supplied
  weaving CV. A fully valid set of cited positive responses retains all 18
  after experience, qualification, compound and final reconciliation checks.
- Negative tests cover unrelated dated duties, different professional field,
  missing half of an AND clause, negated corrective actions, title-only evidence
  and bare skill lists. Existing multi-profession tests remain part of the
  complete suite.
- A direct read-only replay of the actual uploaded Adeel PDF's R001/R007/R008
  citations succeeded. The original CV is **not included in this ZIP**.
- No live OpenRouter assessment was run. Tests prove the final-validator logic
  on known source/citation inputs, **not** that the live model will always choose
  or correctly cite every true work capability. A final supervised end-to-end
  run is mandatory before using results operationally.
- Applicant records remain self-reported. Human reviewers must verify real
  employment, credentials and suitability. Remote deployment privacy,
  authentication, durable recovery, concurrency and incident response gates
  remain open (see `docs/PRODUCTION_SECURITY.md`).

## Install and regression test

1. Preserve the previous installation and its private `.env` and signing-key
   backups. Extract this ZIP into a **fresh** directory; do not merge versions.
2. Recreate the Python environment, restore local private configuration, and
   start Ollama/EmbeddingGemma as required by your assessment mode.
3. Run `run_runtime_check.cmd`, `run_tests.cmd` and `run_ui.cmd` on Windows.
4. Confirm **Interface V4.9.48 / protocol v34**. The new protocol deliberately
   rejects checkpoints created with v33 validator semantics; re-assess the same
   JD/CVs with the corrected version and preserve a fresh recovery export.
5. Approve the same frozen JD and weights. Compare the Adeel and transferable
   candidate using the complete source ledger. Check R001, R007 and R008, all
   warnings, score totals, and CSV/JSON exports. No synthetic 100% result is
   a guaranteed forecast of the live model's answer.

**Deployment:** The bundled Streamlit app can be installed on an appropriately
secured, model-capable Python server. Lovable is a frontend-builder and cannot
host this Python/Ollama engine without a separate protected backend. Neither
frontend choice bypasses the open production-security requirements.
