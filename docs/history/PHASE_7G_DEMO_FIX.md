# Phase 7G sample-dataset and transferable-proposal repair

## Confirmed root cause

`run_phase7g_shadow.cmd` had a hardcoded backend JD and backend CV folder.
`run_phase7g_transferability.cmd` consumed these saved backend artifacts.
That workflow was not the Applied AI sample, regardless of the release build ID.

The Streamlit AI proposal filter defaulted to "Transferable first" and hid
other verdicts, giving an empty table for candidates with zero transferable
labels. A structurally complete model result was not a transferability-quality
measurement.

## Source repairs

- Demo CLI defaults now point to the Applied AI JD and the 12 fictional resumes.
- Old backend demo is a separate explicit command.
- New `run_phase7g_applied_ai.cmd` chains retrieval and transferability.
- UI defaults to showing every AI proposal, sorted with transferables first,
  displays reasons, source quotations and review notices.
- Structural headings exclude explanatory instructions and preserve the long
  `Required Experience` bullet. This fixes source obligation completeness in
  the supplied Applied AI JD, not arbitrary JDs.
- Simple OR parsing ignores explanatory '(at least one)' annotation while
  preserving original source quotation; the OR options are TensorFlow/PyTorch.
- Duplicate model-generated JD capability queries are omitted. General
  functional search hints remain model-proposed and review-only.
- Transferability prompt demands demonstrated functionality, not high cosine
  or general topical similarity. Direct named-tool proposals supported only
  by negated cited evidence are downgraded to `uncertain`.
- CLI prints relationship counts and a notice when transferable count is zero.

## Tests and limits

`tests/test_phase7g_demo_repair.py` tests source-structure conservation,
experience criterion presence, OR option normalization, command selection,
search duplicate suppression, and positive-denial auditing using fake models.

Tests cannot establish live OpenRouter or Ollama inference performance.
The semantic results remain provisional. The primary scoring contract is
not modified by the semantic subsystem. Complex tenure and ambiguous skill
interpretations still require human review. No transferable count is forced.
