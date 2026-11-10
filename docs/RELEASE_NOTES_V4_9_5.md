# Phase 7G V4.9.5 — academic-level transfer and source integrity

**Build:** `phase7g-v4-9-5-higher-degree-review-and-title-parser-repair-2026-10-28`  
**Protocol:** `segment_ids_semantic_llm`, version 13

## Confirmed shared root causes

1. **Higher-level related education was categorically excluded.** Both the
   independent-review trigger and the final typed qualification gate required
   the CV degree to have *exactly the same level* as the frozen JD. An MSc or
   PhD could therefore never appear as transferable evidence for an exact-major
   bachelor's requirement, even when it was completed and closely related.
   Both now accept a completed degree at the required **or a higher academic
   level** for *unscored semantic transfer review*. This is never direct credit.
   The semantic assessor still judges field overlap; Python does not contain
   any fixed list of approved degree fields or job departments.

2. **An employment title was incorrectly parsed as an academic credential.**
   The education regex accepted the standalone word `Associate`. In a CV
   stating `Applied AI Research Associate`, the qualification validator created
   false 'associate degree' claims from that job title. It could then attach a
   degree assessment to a summary/title segment instead of the actual MSc in
   the education ledger. `Associate degree` and `Associate of Science/Arts`
   remain supported; a bare `Research Associate` or `Sales Associate` no
   longer counts as an award.

3. **The prompts reinforced the same level-only false negative.** The first
   and independent semantic prompts said related education must be at the
   *same level*, making a higher-level degree appear categorically irrelevant.
   They now explicitly separate **exact degree satisfaction** from **related
   completed education at the requested or a higher level**, with a cited
   explanation of the specific subject relationship. The model cannot assert
   that an applicant earned a particular bachelor's solely because an MSc
   is listed.

4. **Qualification citations could be displaced by an earlier parsed claim.**
   When the semantic assessor validly cites a related degree, the qualification
   post-check now keeps that cited affirmative higher/same-level degree in the
   evidence checkpoint instead of blindly selecting the earliest parsed
   credential. This protects the source-to-decision link; no citation is
   fabricated.

## Preserved safeguards

- `Found` requires the JD's level **and** field unless the JD explicitly
  accepts a degree family. A different or higher degree never earns the point
  for a specific bachelor's solely by being related.
- `Transferable` is unscored and requires a completed, affirmatively cited
  qualification of at least the JD academic level **and** a source-grounded
  model decision that the fields have meaningful overlap. An unrelated,
  missing, denied, pending, lower-level or uncited degree does not qualify.
- Existing LangChain/LangGraph alternative-work transfer safeguards, named-tool
  denials, numeric experience, Found/Not Found/Transferable displays, and
  evidence ledgers remain in place.
- No requirement-name, profession-name, or major-name hardcoded exceptions.
- No per-criterion rechecks or unbounded cloud calls. An eligible missed
  degree can join the existing **one independent grouped verification call
  per CV**; the overall HTTP limit stays unchanged.

## Verified offline results

- Added domain-neutral tests for same-level and higher-level related degrees,
  lower-level and denied alternatives, independently cited source segments,
  degree parser false positives, end-to-end rank/display contracts and the
  original synthetic PDF's actual extracted MSc statement.
- **918 tests passed** across the full automated suite, including the new
  source-to-score-and-UI contracts.
- The SHA-256 manifest was rebuilt and the runtime guard verified protocol
  version 13 against **381** distributed source files.
- The unchanged eight-department offline fallback benchmark passed **197/200**
  labelled decisions (98.50%) across 40 synthetic candidates, with no false
  positive direct matches and three missed direct matches. This benchmark
  does not use the OpenRouter model and cannot establish its live accuracy.
- **Live OpenRouter/Gemini multi-CV accuracy is NOT certified by these
  offline tests.** The model still independently decides whether a particular
  field is sufficiently related. A new live run on the user-authorized CVs
  is required before presenting the tool as production-ready.

## Windows acceptance run

```powershell
.\run_runtime_check.cmd
.\run_tests.cmd
.\.venv\Scripts\python.exe doctor.py --live --provider openrouter
.\run_ui.cmd
```

Inspect the cited education segment for the exact-major requirement. For a
related MSc shown as `Transferable`, the direct score must not rise and the
original MSc evidence must appear. For an unrelated field or incomplete
award, no transfer should be inferred. Inspect all other candidates for
regression before supervisor use.
