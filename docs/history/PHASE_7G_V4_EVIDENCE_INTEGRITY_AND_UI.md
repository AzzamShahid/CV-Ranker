# Phase 7G V4: Candidate evidence integrity + truthful UI

## Important difference between counts and scoring

The UI displays the count **for the selected candidate**, not for all candidates.
Its denominators are the frozen job description criteria (required and preferred),
not the count of uploaded resumes. For example, 7/9 means seven of nine *required*
criteria were marked matched for that candidate. A JD containing 16 requirements
can legitimately have 9 required and 7 preferred. The UI explicitly displays
both the overall selected-candidate totals and the number of table rows visible
after filtering. A new assessment resets the positional candidate selector.

## Candidate-evidence safety corrections

- Explicit pasted/quoted target job descriptions tagged as not claiming experience
  are segmented as `non_candidate`. Their skill strings cannot establish proficiency.
- Coordinated denials ("no A, B or C experience", "has not used A or B")
  negate every affected item. Unrelated positive work remains eligible.
- Shared checks apply to the direct-source guard, row-level LLM citation auditing,
  deterministic fallback, and AND/OR compound assessment.
- An LLM `matched` row citing only an explicit denial is downgraded to not matched.
  A `matched` row citing non-candidate content is rejected for corrective review.
- Oversized citation lists are identified separately from unknown source IDs and
  individually retried. Valid citations remain limited to three per assessment;
  the system does not silently truncate or invent support.
- Primary and correction prompts now explain negation scope, pasted JD evidence,
  requirements' frozen source wording, and source-specific citation discipline.
- Shadow-transferability prompt is strengthened without allowing AI transferability
  proposals to change the primary score.

## Limits and verification

The offline suite includes the real bundled TXT and PDF adversarial resumes,
unit tests for source classification and citation failure, and UI source checks.
Real OpenRouter/Ollama LLM judgment cannot be certified without rerunning the
live workflow. Historical JSON reports are **not mutated** by this release.
There is no automatic rescoring of downloaded V3 reports; rerun the JD/CVs.

## Commands

```powershell
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q
.\run_ui.cmd
```

In the UI, re-upload the JD and CVs and click Analyze. Download a fresh evidence
JSON. To test semantic transferability as well, enable the existing semantic
review option; EmbeddingGemma and the configured model must be available.
