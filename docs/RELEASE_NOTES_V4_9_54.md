# TextileHR AI / CV Ranker 4.9.54 — preserve standalone qualification sentences

11 November 2026 · `segment_ids_semantic_llm` protocol v40

## Critical extraction repair

A QA Automation Engineer JD at Orchardline Payments included seven explicit Required and three Preferred qualification sentences. The previous structural parser retained only the first two sentences, because later sentences such as "Integrate automated regression tests into a CI pipeline" and "Design reproducible test data for independent test runs" had no bullet marker or numeric degree/experience cue. If the first LLM pass omitted those sentences, they silently disappeared from the frozen scoring denominator.

Version 4.9.54 preserves *concise standalone qualification sentences inside explicitly marked Required/Preferred source sections*. It applies to any field and any technical specialty: there is no library of named software roles, skill names, technologies, degree titles, or fixed example JDs in the matcher. Clear excluded sections such as Benefits remain excluded; long narrative paragraphs continue to end paragraph-like section parsing.

The supplied full QA JD is now an offline regression fixture. It asserts **10/10 source requirements with the original 7 Required and 3 Preferred priorities** and checks the full LLM-reconciliation stage by simulating the observed partial model output (8/10) and verifying deterministic recovery of both missing requirements without a second provider call.

The assessment protocol was incremented because frozen JD source coverage affects every candidate's scoring denominator. Previously saved assessments from protocol v39 must not be mixed with v40 results.

## Operational cautions

- Before running assessments, inspect the frozen JD against the source and approve all rows. For the supplied QA example, the screen must show seven Required/Experience/Education entries plus three Preferred entries (ten requirements overall).
- An exact CV source quotation is still necessary to award `Found` for a specific JD condition; related, non-equivalent professional work can be `Transferable` without score credit.
- Keep Ollama and EmbeddingGemma running for the local embedding pipeline; the OpenRouter option still uses local embedding retrieval.
- Automated source-coverage tests do not prove that an AI assessment is accurate for every JD, CV, or provider response. A supervisor should check source evidence before employment decisions.

## Verification

```powershell
.\run_runtime_check.cmd
.\run_tests.cmd
.\run_ui.cmd
```
