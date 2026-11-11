# TextileHR AI / CV Ranker 4.9.52 — dated experience recovery and readable controls

11 November 2026 · `segment_ids_semantic_llm` protocol v38

## The reported issue

A JD required **at least 3 years of full-time native Android development**. The CV had dated full-time work records such as **Sep 2018–Feb 2022** and **Mar 2022–Oct 2026**, each with performed duties in its own text. The previous numeric validator could return *Not Found* with **“No explicit, appropriately scoped duration with valid year units was found”** because it only considered shorter segments classified as `experience`, while the original PDF extractor had classified these dated work paragraphs as `summary`.

## Fixes

1. **Month/year role spans now count as duration evidence.** A properly documented full-time role can establish numeric experience through calendar ranges without repeating the literal phrase “3 years.” The duration parser accepts complete, long original source passages and recognizes a dated full-time role with performed duties in a `summary` or unheaded section. It does not fabricate a new employer or attach dates to unrelated work.
2. **Evidence remains role-scoped.** An independently model-judged *Found* must cite a completed duty in every credited role. Calendar years alone, title-only claims, project timelines, future dates, copied job requirements and double-counted overlapping employment do not receive a numeric match. The original employer/date source ID is retained for review.
3. **Better discovery beyond imperfect PDF headings.** Added common academic, career, tools and frameworks heading variants. Explicitly documented BS/MS academic awards can be considered even when a PDF lost the Education heading, while a bare ambiguous abbreviation in a skill list is still insufficient. Performed-work retrieval prioritizes work-history evidence over broad summaries and considers a narrow first-person completed-work grammar when uncommon action verbs are used.
4. **Stronger assessment instructions.** Both primary and independent prompts now expressly describe month/year employment arithmetic, role-specific duties, PDF text that combines header and first action on one long line, academic award discovery and cross-section skill evidence. Nothing assumes a particular software field, framework, employer, credential equivalence, or fixed vocabulary of job requirements.
5. **Readable actions in both modes.** Restored light/dark native Streamlit themes from 4.9.51 and added explicit high-contrast text/background colors for primary/secondary action and download buttons, including hover states and nested Markdown button labels.
6. **New regression tests.** Added the reported Android wording, summary-tagged dated roles, project-only timeline, future dates, title-only experience, missing education headers, alternative academic/skill headings and primary button contrast. Older source, qualification, transferability, scoring and cloud budget tests still apply.

## Scope and limitations

This is a general source-to-requirement policy fix, not an Android-specific match rule. The same date parsing and section handling applies to software, hardware, operations, finance, medical and other JDs. **However, no finite parser or LLM can guarantee a correct assessment for every future résumé layout.** Difficult, contradictory or unavailable evidence can still remain Unverified. This is intentional: falsely awarding or denying a qualification would be worse than flagging it for a reviewer.

The tests use deterministic mocked model responses for source validation. They do not prove that an arbitrary OpenRouter/Ollama response will be correct. A supervisor acceptance run must confirm a live configured provider with real CVs. Test results, CI details and local security preflight belong to this exact release build and should be rerun after changing source files.

## Run and verify

```powershell
.\run_runtime_check.cmd
.\run_tests.cmd
.\run_ui.cmd
```

Select **app menu → Settings → Theme → Light/Dark/System** and inspect buttons, sidebars, citations and download controls. For dated experience, verify the **original role IDs and performed duties** under each result. A valid month/year span cannot automatically be assigned to a different project or named specialty.

### Deployment dependency

This edition still requires the configured Ollama EmbeddingGemma model for retrieval, even when OpenRouter is selected for cloud assessment. It is not a stand-alone Streamlit Community Cloud deployment. Review network isolation, access controls and credential storage in `PRODUCTION_SECURITY.md` before a public deployment.

If a candidate fails with `EmbeddingError` after Ollama was closed, **start Ollama and confirm the configured embedding model is available, then retry the assessment**. This release intentionally does not change the embedding engine: a stopped retrieval service cannot produce completed evidence decisions, and the resulting `Unverified` rows are not evidence that a skill is missing.
