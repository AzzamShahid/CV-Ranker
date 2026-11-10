# Phase 7G V4.9.35 — Final source-proof and structured-response reliability

## Confirmed defects in V4.9.34

1. `cv_ranker/unified.py::_independently_adjudicate` demanded a case-insensitive,
   character-perfect substring for every independent positive `proof_excerpt`.
   The bundled Bilal PDF contains `Prepared held-out evaluation sets; tracked
   retrieval recall@5`, while a model may quote the **same original words** as
   `Prepared held out evaluation sets tracked retrieval recall 5`. Before the
   repair, that independently cited Found decision was silently rejected and
   R008 stayed Unverified even though all words and their order were correct.
2. The rejected final verdict was logged as an absent assessment row. Reasons
   such as citation outside the submitted sources, inconsistent verdict/relation,
   a missing quote, or an altered quote were discarded. The UI consequently
   lacked the precise validation cause.
3. `cv_ranker/llm.py::OpenRouterStructuredLLM.invoke_structured` retried a
   malformed model result with the **same strict response format** even when
   the next attempt could use JSON-object mode and still pass local validation.
4. The final verification repeated many generic policy paragraphs in the task
   field even though those policies were already in the system prompt. This
   increased context pressure for a focused one-requirement recovery.

## Changes

- Prefer exact proof substring matching, then accept only the **same contiguous
  sequence** of at least four source words and 18 alphanumeric characters
  after punctuation/whitespace normalization. No paraphrase, synonyms,
  unordered keywords or fictional source is accepted.
- Report exact per-JD-ID final-verification rejection reasons (without model
  output or API secrets) into the existing execution diagnostics and
  incomplete-CV details. Any final provider/schema failure gets the affected
  IDs and a safe failure category.
- On a structured response validation error, switch the next bounded
  OpenRouter attempt to JSON-object mode; continue to require local typed
  Pydantic validation and original-source grounding. The HTTP attempt limit
  and financial safety behavior are unchanged.
- Replace the duplicate final user task essay with one concise instruction.
  The full source, skills, education, experience and transferable evidence
  rules are still specified in `FINAL_ADJUDICATION_PROMPT`.

## Evidence and boundaries

- The new tests first failed against V4.9.34, reproducing both invalid
  punctuation rejection and a failed R008 recovery using the real bundled
  `02_bilal_direct_fullstack.pdf`.
- After the repair, those tests pass, and a fabricated proof excerpt still
  fails closed with zero scoring credit and precise diagnostics.
- No production OpenRouter credentials or failing HTTP response were
  available in the test environment. This is **not** proof that every cause
  of the live R008 pause has been eliminated; the new diagnostics distinguish
  any remaining provider, syntax, source, or reasoning rejection.
- No candidate, JD ID or profession is special-cased in production logic.
