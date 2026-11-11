# TextileHR AI / CV Ranker 4.9.53 — complete JD source coverage and bounded semantic re-review

11 November 2026 · `segment_ids_semantic_llm` protocol v39

## Why this release exists

Some multi-specialty job descriptions lost explicit criteria during extraction, especially when they exceeded the old 30-row default or contained nested subsections such as `Backend:` beneath `Required Qualifications:`. Separately, the final independent evidence check reviewed no more than four potential false-negative/transferable decisions per CV. Later rows, including Preferred criteria, could therefore be left at a first-model `Not Found` without the same recovery opportunity.

## Changes

1. The normal JD processing limit rises from 30 to 100 (editable to 250 in the UI). Context-aware batching remains independently bounded. If a user-selected limit would truncate explicit JD rows, both the approval screen and CLI ranking now reject the incomplete denominator and direct the reviewer to increase the limit and re-extract.
2. JD structural recovery preserves explicitly listed criteria within nested unknown subject labels, such as `Backend:`, `Cloud Services:`, or an inline category followed by a short tool list. It also recognizes generic capabilities/competencies headings. It still excludes clearly marked Benefits and role advertising text. These are document-structure rules, **not a technology dictionary**.
3. Plausible false-negative/transferable findings are independently source-reviewed across **all** eligible JD IDs instead of silently dropping the fifth and later items. Incomplete technical results remain the first priority. Checks are grouped in batches of up to four and obey the existing provider request and credit ceiling; no scoring is awarded from search similarity alone.
4. A negative model decision citing completed work with an alternative tool can trigger independent transferable review when the model's own explanation explicitly contrasts the capabilities. The actual relationship must still be adjudicated and cited. An exact named tool does not become Found merely because a different tool appears in a resume.
5. Retains v4.9.52's dated role/academic evidence improvements and readable native light/dark themes.

## Supervisor and operator instructions

- Inspect and approve the entire frozen JD before assessing a CV. Do not proceed if the UI reports a requirement cap, unresolved extraction warnings or a missing source line.
- A `Found` score requires validated original CV evidence of the **exact** criterion. `Transferable` is unscored and is not a claim of equivalence. `Not Found` means not established by the CV.
- Ollama and the configured EmbeddingGemma model must be running even when the OpenRouter cloud provider is selected for the assessment LLM. This release does not introduce an embedding fallback.
- Live model outputs can still be imperfect or unavailable. The test suite uses synthetic original sources and deterministic model doubles, and does not guarantee every future JD/resume combination. Review actual sources with a supervisor before making employment decisions.

## Verification

On Windows PowerShell after extracting this package:

```powershell
.\run_runtime_check.cmd
.\run_tests.cmd
.\run_ui.cmd
```

Check extraction with a JD that includes several technical subheadings; verify every source criterion appears in Step 3 before approval. For any initially Not Found or Transferable result, expand the original citations and compare them against the exact frozen JD wording.
