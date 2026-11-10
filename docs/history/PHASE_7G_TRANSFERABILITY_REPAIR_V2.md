# Phase 7G — live transferability regression repair, 20 October 2026

## Problem seen in the 12-resume live run

* JD extraction recovered 17 frozen criteria: 10 required, 7 preferred.
* All 12 candidates completed local EmbeddingGemma retrieval.
* 204 provisional model relationship decisions contained zero `transferable` labels.
* 29 requirement-level responses fell back to `uncertain` with `Unknown/duplicate/excessive source IDs` or missing/duplicated capability IDs.
* 22 potential relationship consistency flags were recorded.
* This is **not** a successful transferability benchmark. No production accuracy claim is justified.

## Underlying issues and changes

1. The compact model can return repeated IDs and 4+ source IDs; previously a single bad citation list aborted the *entire requirement row*. Valid, candidate-scoped citations are now deduplicated and limited to three, retaining performed-work segments preferentially. The model cannot introduce a foreign source ID: a foreign ID causes only its own capability to become `uncertain`/`audit_failed`, never a positive result. Omissions/duplicate capability IDs similarly become explicit uncertain results rather than wiping out valid sibling assessments.
2. The model was often reading an explicit *lack of direct tool experience* as disqualifying any transferable functionality. The revised prompt directs it to evaluate genuinely performed alternative work separately from denied named-tool experience; it also prohibits treating the CV's self-description "transferable" as independent evidence.
3. The original prompt lacked source-section metadata. `retrieved_cv_sources` now includes `source_section`, letting the model distinguish `skills` listings from `experience` evidence.
4. The applied AI demo now requests top-8 retrieval, instead of top-5, so more performed work is available. This is a recall experiment, not a score threshold. No BM25 or hardcoded skill synonyms were added.
5. A *single* conditional second model review checks named-tool-gap cases that also include evidence of performed work. It can only propose a source-cited transferable relationship. If the model remains nonpositive, the UI flags a **functional-overlap review candidate**, never a verified match. The existing direct score, status, rank and frozen JD requirements are unchanged.
6. The command-line report includes citation audit failures and manual functional-overlap review counts. The UI retains all proposals and shows the additional review count and source passages.

## Validation

Unit and integration tests include source ID normalization, rejection of foreign citations, one-bad-row isolation, candidate-scoped segment evidence, section-aware prompt, and a simulated two-call `uncertain -> transferable` model sequence. The latter verifies orchestration **only**, not live model accuracy.

The supplied 768-dimensional EmbeddingGemma cache was replayed offline using the *same real embedding vectors*, with no new model calls. On top-8 retrieval, Sara, Nadia and Taimoor's LangChain queries include source-grounded alternative-work passages and direct-tool-gap evidence. This confirms the new second-look path can be triggered for the intended cases. It does **not** confirm that the online model will correctly classify their professional transferability.

## Explicit limitations still open

* The 3-year AI/ML professional tenure JD requirement includes a compound contextual condition. The conservative baseline flags it for human confirmation rather than manufacturing a score. This patch **does not** claim to solve complete subject-specific tenure calculation from multiple role dates or unrelated experience.
* Existing source-grounded rankings may also exhibit model errors; semantic shadow must not silently correct primary ranking.
* Zero transferability labels remains a possible honest model outcome; no label is forced.
* Connection to OpenRouter and Ollama cannot be live-tested inside this offline build environment.

## Recommended local commands

From the extracted project root with `.env` configured:

```powershell
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe doctor.py --live
.\scripts\run_phase7g_applied_ai.cmd
.\run_ui.cmd
```

The full Applied AI script rebuilds baseline ranking, retrieves from the current CV location and generates new proposals. To retry transferability only after refreshing retrieval under this build, run `scripts\run_phase7g_transferability.cmd`, avoiding unnecessary embedding and baseline repeats. The complete run may use paid OpenRouter calls.

Treat the output as candidate-screening assistance requiring human review, not an automated hiring decision.
