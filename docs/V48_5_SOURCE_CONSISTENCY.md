# Phase 7G V4.8.5 — Source consistency and clean audit

Release: 27 October 2026

## Scope

This release retains the approved V4.8 retrieval-first architecture:
YAKE/frozen JD -> local EmbeddingGemma-2 evidence -> grouped domain-neutral
model assessment -> Python validators -> one final evidence-backed result.
There is no BM25, new search engine, embedding change, new model call, or
profession-/tool-specific skill-equivalence table. The V4.8.4 prompts are
unchanged. Scores and denominators are unchanged.

## Corrections

1. The existing V4.7 conservative functional bridge is now shared by the
   unified assessment. A Not Found proposal may be marked Transferable only
   when a CV passage explicitly compares named-tool functionality with
   an alternative and a **separate completed-work passage** shares multiple
   substantive source words. The output retains both plus all initial source
   checkpoints, gives a reason, and always requires human review. It is
   never a direct Found match or a point. Denial-only, comparison-only,
   unrelated work, and adjacent tasks still receive no invented credit.
2. When the existing single grouped correction resolves a first-pass
   citation/format error, the earlier error is moved from candidate warnings
   to `resolved_validation_notices` within per-CV technical metrics.
   Failed corrections and final unresolved errors remain visible. The
   model call budget and provider retry behavior are unchanged.
3. An accepted broad experience clause with illustrative 'including' choices
   records a matched `compound_check` in the audit and keeps the
   review-recommended flag, but no longer produces a misleading
   assessment-failure message. Actually uncertain or unsupported evidence
   retains its warning/fail-closed behavior.
4. Streamlit UI controls use the supported `width="stretch"` argument.

## Synthetic regression coverage

- Explicit comparison + independently completed alternative work can
  support Transferable only, without another LLM call or ranking point.
- A bare denial, self-comparison, or unrelated activity cannot do so.
- Corrected source-term errors remain in technical audit but do not make
  a successful final candidate look invalid.
- Prior generic evidence, compound, prompt-neutrality and grouped-batching
  tests remain applicable.

## Required Windows verification

```powershell
.\run_tests.cmd
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe doctor.py --live
.\run_ui.cmd
```

Review the fictional Sara CV and an unrelated department's JD/CV. In the
fictional Sara case, an explicitly denied named tool with separately
completed comparable work can be Transferable, not Found. A time-series
anomaly workflow must not become a direct forecasting match. Check
the final evidence IDs, candidate warnings, grouped call metrics, and
resolved first-pass notices in Technical details. Full live LLM output
remains probabilistic and must be tested on the user's configured models.
