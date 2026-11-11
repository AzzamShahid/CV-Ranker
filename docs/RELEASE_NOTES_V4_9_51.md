# TextileHR AI / CV Ranker 4.9.51 — readability and generalized evidence reliability

11 November 2026 · `segment_ids_semantic_llm` protocol v37

## Changes

1. **Native theme choice restored.** `.streamlit/config.toml` now defines separate light and dark palettes, including matching sidebars. Streamlit's app menu offers Light, Dark and System. Every custom ranking, summary and source card receives its foreground/background color from the active Streamlit theme, instead of relying on light-mode text variables that were washed out in dark mode. Both theme foreground/background combinations are checked with automated contrast-ratio tests; this does not change the brand's Reliance-inspired green accent or the scoring code.
2. **Stronger domain-neutral assessment prompts.** The initial assessor and independent reviewer explicitly separate implementation, testing, deployment, operations and leadership; respect exact named tools, degrees, credentials, seniority and the complete frozen JD; prohibit invented unstated conditions; and recognize genuinely entailing completed work despite different terminology. A related but different named skill remains *Transferable* without score credit. Source-specific explanations are requested in 15–45 words. **No named product, profession, programming-language or degree equivalence list was added.**
3. **Shorter, targeted corrections.** After a failed validation, the retry payload includes the actual failed ID and validation reasons plus a short direction to follow the system contract. It does not repeat a second, long version of the decision policy. This reduces cloud prompt size and contradictory instructions.
4. **Locally repaired duplicate citations.** Duplicate copies of an otherwise eligible source ID are removed before source-count limits are applied, without changing the model's status or allowing any unknown source ID. A pure duplicate no longer creates a paid correction request. Unknown IDs, invented JD IDs and unsupported positive claims still fail closed.
5. **More conservative group sizes.** Default 2,048-token output budgets now plan up to **five** JD decisions per model call rather than seven. An 18-item JD uses four initial model calls rather than three, trading slightly more fixed overhead for lower JSON truncation risk and fewer repeated large completion failures. The existing bounded split, correction, checkpoint, and independent review behaviors remain.
6. **Expanded regressions.** Added source-validation and degree tests covering representative computing disciplines and specialties, alongside the existing cross-industry tests. A live model run against arbitrary CVs is *not* simulated by these tests.

## Non-negotiable safety behavior

- **Unverified is not a fabricated Not Found.** No model, parser, or remote provider can guarantee correct answers for every unseen JD/CV. If supplied evidence or provider output cannot be validated even after bounded recovery, the candidate remains Unverified and is not ranked until a human checks or a valid response succeeds.
- **No automatic score inflation.** Transferable, uncertain and inspected-but-not-credited citations do not become Found by retry normalization or by a matching-looking skill name.
- **Security unchanged.** Local bind only, CORS/XSRF protections and private-file static serving remain unchanged. CV excerpts still leave the device if a cloud provider is selected.
- **Old release checkpoints.** Assessment protocol and build identity have advanced, so older reports/recovery snapshots must not be silently mixed with v37 judgments. Retain previous release and recovery files for audit purposes.

## Run locally / acceptance checklist

```powershell
.\run_runtime_check.cmd
.\run_tests.cmd
.\run_ui.cmd
```

1. Confirm **Interface v4.9.51** and **Assessment protocol v37**.
2. Use **app menu → Settings → Theme**; switch between Light and Dark. Check sidebar controls, unverified warnings, source boxes, scorecards, selected tabs and download buttons.
3. Review a frozen DevOps/SRE, full-stack, data engineering, embedded or other specialty JD using resumes with explicit direct matches, only related work, denied skills and missing proof. Inspect the **original source IDs** behind every verdict. If in doubt, retain the review flag.
4. Check OpenRouter credit/HTTP attempts and capture a signed checkpoint before restarting the app. The request limit and recovery controls are still configurable; do not treat an exhausted remote budget as a factual CV nonmatch.

## Environment note

Ollama EmbeddingGemma is still required locally for current retrieval, even when the assessment model is OpenRouter. Streamlit Community Cloud alone does not supply your local Ollama service. For remote deployment use a private managed host with Ollama access, or separately implement and validate a cloud embedding adapter and secure access controls.
