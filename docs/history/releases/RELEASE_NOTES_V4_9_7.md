# Phase 7G V4.9.7 — role-scoped tenure and semantic evidence recall

**Build:** `phase7g-v4-9-7-role-scoped-experience-and-recall-2026-10-28`  
**Protocol:** `segment_ids_semantic_llm`, version 15

## Root causes confirmed in source and sample PDFs

1. **Dates and duties were separated:** The experience validator accepted a
   literal numeric statement but could not connect a dated job header with
   its OWN following completed duties. Genuine tenure could be flagged as
   ambiguous even when the CV clearly listed the qualifying role.
2. **Consecutive jobs were not combined:** A two-year relevant role followed
   by another relevant two-year role could never satisfy a three-year JD
   threshold through dated-role evidence. Dates now combine conservatively,
   with overlapping calendar months counted once and independent source
   citations required for each credited job. Up to three roles are supported.
3. **Citation limits disagreed across layers:** The schema, response mapper,
   generic row validator, and physical segment resolver had a three-ID cap.
   A valid two-role demonstration needs four distinct original source IDs.
   Numeric experience now permits up to six IDs end-to-end, and other JD
   types retain a three-ID limit.
4. **A generic action verb was omitted:** A source stating "Performed quality
   assurance audits" was rejected as lacking a qualifying capability cue,
   even when the model cited the correct source. Generic completed-work
   verbs have been restored without naming professions or technologies.
5. **The retrieved comparison lacked the performed alternative:** In the
   fictional Sara PDF, the LangChain comparison and a tool-routing bullet
   could be selected while a stronger, separately completed "using Haystack"
   work-history source was omitted. Evidence discovery now also follows
   specific alternative names IN THE CV's own comparison to separately
   performed-work passages. This is source recall, not Python equivalence
   or automatic scoring.
6. **Education comparison evidence lost priority:** Retrieval could select
   generic education-section lines before the actual completed degree
   claim. Source-verified same-level or higher-level degree claims are now
   anchored first for the model's exact-versus-related decision.

## Behavioral contracts

- **Found experience:** For role-derived numeric tenure, the grouped LLM
  must directly establish JD work relevance and cite EACH credited role's
  date heading and a genuine completed duty in that role. Python verifies
  that these source IDs and a non-overlapping duration cover the minimum.
  Dates alone, denied work, unrelated work, or an incomplete citation group
  cannot earn the point. Explicit, subject-scoped year claims preserve their
  existing deterministic contract.
- **Transferable degree:** A completed BS Software Engineering or a related
  higher degree can receive **Transferable** for an exact BS Computer Science
  JD only after the source-grounded LLM explicitly determines academic
  overlap. This does NOT satisfy the requested exact degree and does NOT add
  a point. Python checks the actual cited degree claim, completion state,
  and academic level. The same logic applies to other disciplines.
- **Transferable named-tool functions:** Explicitly compared alternatives
  and independently performed work are surfaced as evidence. The LLM must
  still judge overlap; a denial alone, similarity ranking, or another brand
  name does not earn any direct match.
- **No speculative score:** Missing/invalid assessment responses still
  remain Unverified without a rank; this change does not substitute
  retrieval similarity for a model verdict.
- **No applicant-data scope expansion:** Only the configured bounded CV
  excerpts are sent to OpenRouter. An earlier idea to send the entire CV
  ledger was NOT implemented. More source IDs for documented multi-role
  experience use the existing context-sized grouping. There is still at
  most one grouped correction and one optional independent grouped final
  verification call per CV, never per-requirement requests.

## Test scope and limits

- New regression contracts cover four different job domains, one-versus-two
  job segments, consecutive roles, overlapping simultaneous roles, genuine
  source citations, incomplete citations, bounded request count, unrelated
  career history, false first-pass degree nonmatches, and selected excerpts
  from the real fictional Bilal and Sara PDFs.
- The unchanged eight-department *fallback* benchmark still reports
  197/200 decisions (98.50%) with zero false-positive direct matches. This
  measures synthetic fallback fixtures, NOT live Gemini/OpenRouter accuracy.
- **Important:** No OpenRouter key, local Ollama embedding service, or
  protected applicant data was available in the verification workspace.
  Offline tests cannot guarantee Gemini will choose correct relationship
  labels on every live run or that an API quota/network failure will not
  produce an unassessed candidate. Review the original cited passages.

## Deployment

On Windows, replace the *project source* with this complete release while
preserving your own private `.env` and input files separately. Check the
build and run the local tests before re-analyzing all candidates:

```powershell
.\run_runtime_check.cmd
.\run_tests.cmd
.\.venv\Scripts\python.exe doctor.py --live --provider openrouter
.\run_ui.cmd
```

`doctor.py --live` makes real provider requests and can incur charges. The
synthetic doctor test alone is not a full multi-resume accuracy benchmark.
