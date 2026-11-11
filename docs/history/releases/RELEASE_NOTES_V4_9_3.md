# Phase 7G V4.9.3 — typed scope, degree families and stable final UI

**Build:** `phase7g-v4-9-3-broad-qualification-scope-stability-2026-10-28`  
**Protocol:** `segment_ids_semantic_llm` version 11

## Confirmed root causes in V4.9.2

1. **A source-written OR was treated as one literal experience subject.** The frozen JD `3 years of Python or Django experience` produced the typed subject `Python or Django`, which the numeric validator then sought *verbatim* in a candidate's single duration clause. An affirmative four-year Django claim was therefore turned into *uncertain* even when the stated JD alternative was satisfied.
2. **A degree category was treated as one exact major name.** The JD `Bachelor's degree in computing programs` generated `field_of_study='computing programs'` and the post-model validator demanded literal equivalence to that string. It could thus veto a model's otherwise valid decision about a named bachelor's major belonging to the JD's broader field family.
3. **Old citation-format warnings survived successful corrections.** The final warnings filter suppressed only specific error strings; the other resolved errors such as a wrong `matched_term` still appeared as candidate warnings, and the UI displayed each notice twice. Even a completed report was labeled provisional solely because a non-final diagnostic existed.
4. **Typed source evidence was not guaranteed to reach the model.** A broad field-family JD may share few literal or vector-search terms with a specific degree title. Evidence selection now reserves a small source-type-aware lead for stated education/credentials and explicit work-duration statements, without using occupation aliases or changing scores by embedding similarity.
5. **Each new Streamlit run overwrote the current report.** The UI now keeps a reversible, in-memory history of the last three runs in the same browser session. It preserves the source ledger, final decision matrix and previous report when a new analysis is made. The user may restore a prior run without spending more model calls. This history is not stored to disk and will not survive a closed/restarted Streamlit session; export JSON for lasting retention.

## Decision contracts after repair

- The JD defines the scope. Where it says **A OR B**, source-attested positive tenure meeting the threshold in *either stated alternative* qualifies. Mixed **AND/OR** expressions without unambiguous precedence remain review-required. Generic duration in unrelated work does not become years in a specialized requirement merely because the candidate performed that specialization at some other point.
- **Exact degree field**: a different named major does not automatically count. **Inclusive degree family or explicitly related discipline**: the numeric credential level and completion status are still checked deterministically, but the relationship between the candidate's named field and the JD's field category belongs to the cited LLM decision or HR review. No Python dictionary of computing, medical, finance, HR or other majors is used. A generic category never automatically earns a degree point, and an uncited or pending credential does not qualify.
- Every final source-backed verdict still passes citation integrity, original source checks and existing type validators. A resolved first-pass model error is audit history, not grounds for a spurious provisional badge. A genuinely uncertain or transferable final verdict still recommends review.
- Assessment and correction requests remain grouped. No new per-JD API call was added. The hard HTTP budget remains `OPENROUTER_MAX_REQUESTS_PER_RUN` (64 by default). Typed source coverage can affect group size and input tokens but does not trigger an independent retrieval-model call.
- Prior run restoration is a presentation feature only. It does not overwrite a score, change requirement counts, or store private source documents to persistent history.

## Offline validation

The complete synthetic test suite includes previous segmentation, negation, scored/withheld ranking, source provenance, typed duration/credentials, and source-cache tests plus new OR-work, inclusive education, wrong-field, false-positive and session-history contracts.

The eight-department deterministic fallback benchmark was rerun on **40 candidates and 200 fixed synthetic labels**: **197/200** statuses agreed (98.50%), with zero false-positive matches and three false-negative matches. This is the *offline fallback*, not OpenRouter's model-based accuracy.

## Windows supervisor verification

Extract into a **new folder**, then run:

```powershell
.venv\Scripts\Activate.ps1
.\run_runtime_check.cmd
.\run_tests.cmd
.\.venv\Scripts\python.exe doctor.py --live --provider openrouter
```

In the Streamlit UI, compare the original exact major JD and an explicit inclusive-family JD against the *same* diverse sample CVs. Verify actual quoted degree sources, work-duration scope, final row statuses, source-ledger consistency, and whether any candidate remains unverified. The synthetic doctor contract and offline tests cannot certify real-world Gemini semantic recall or HR acceptability; a representative live multi-CV benchmark is still necessary before production use.
