# TextileHR AI v4.9.72 P1 prompt integration — release notes

**Candidate state:** Development release candidate; not production-qualified. 2026-11-16.

## Source identity and compatibility
- Base archive: `TextileHR_AI_CV_Ranker_v4.9.71_Assessment_Foundation_RC1_2026-11-16.zip`.
- Base SHA-256: `251b2db3b794cff27d24ec29f2d3baa3be3e11358b107b0220c347ab34fa8631`.
- New build: `phase7g-v4-9-72-p1-prompt-integration-rc1-2026-11-16`.
- Assessment protocol: **58** (previously 57); prompt revision `P1-2026-11-16`.
- A protocol bump is intentionally required because prompt interpretation has changed. Historical reports remain historical, and incompatible cached semantic decisions should be reassessed under the new revision. Weight-only changes preserve scoring recomputation without model calls.

## Changes
- Installed exact contents of all 13 approved application prompts under their original symbols, including JD extraction/correction, typing, unified/independent, legacy, compound, decomposition, full/compact/batch shadow, and UI focused judge.
- Wired 19 approved instruction fragments into real prompt construction and doctor calls.
- Preserved P1 common shadow policy exactly once, avoiding double injection.
- Preserved all different JSON structures for primary/independent, compound facets, legacy, shadow full/compact/batch, and UI full/compact.
- JD full replacement and targeted repair are separate; accepted siblings are not overwritten by targeted correction.
- P1 literal JSON braces are passed to local LangChain as a literal system message rather than a formatting template.
- OpenRouter and Ollama structural-correction instructions only occur on genuine malformed output, and include sanitized validation diagnostics where applicable.
- Existing source provenance, three-verdict finalizer, failure/recovery model and zero-direct-credit Transferable policy remain in place.
- Updated tests that depended on old prompt-marker strings but retained their original candidate verdicts and source safety assertions.

## Verification and limits
- The 13 exact-body and 19 exact-fragment checks pass, as do conditional JD correction, doctor, compound schema retry and selected real provider-boundary tests.
- All seven v4.9.71 deep-audit regressions remain in the focused selection.
- The broad environment here lacks Streamlit/LangChain: such failures and collection errors are reported rather than suppressed.
- Live-model comparative accuracy/cost/latency, complete dependency runtime and native Windows qualification have not been established.
- `docs/P1_CONTEXT_BUDGET_AND_QUALIFICATION.md` contains the 14 fictional packet estimates and warns about missing real-source budget measurements.

## Rollback
Keep the original v4.9.71 RC1 archive untouched. Reinstall it in a **separate** directory if reverting. Never reinterpret v4.9.72 assessments as v4.9.71 results or vice versa. Restore only compatible historically versioned checkpoints and preserve private local `.env` files independently.
