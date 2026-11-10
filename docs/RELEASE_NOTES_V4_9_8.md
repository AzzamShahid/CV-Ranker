# CV Ranker Phase 7G V4.9.8 — source-grounded semantic decision repair

**Build:** `phase7g-v4-9-8-semantic-decision-and-prompt-repair-2026-10-28`  
**Protocol:** `segment_ids_semantic_llm`, version 16

## Why the prior build could fail on an otherwise strong candidate

The V4.9.7 screenshots showed a **format-validation failure** for a credible
Machine Learning criterion, rather than a lack of source evidence: the model
cited four source IDs instead of three and supplied a non-verbatim optional
`matched_term`. A second model call could repeat this formatting mistake, so
the entire candidate's rank was withheld. Other runs explained an adjacent
completed degree accurately but labeled it `Not Found` rather than unscored
`Transferable`. Sometimes a matched dated role was downgraded after its
independently cited duty was not accompanied by the model's citation of the
same role's heading.

## Repairs

1. **JD extraction prompt rebuilt.** Three explicit passes separate actual
   employer-stated requirements from marketing copy, retain independent
   list items without splitting compound minimums, preserve genuine OR vs
   AND and illustrative examples, and require source-exact quoted evidence.
   JD criteria remain frozen across candidates. No profession-specific
   dictionaries, employer assumptions, or new API passes were added.
2. **Unified assessment prompt rebuilt.** Every criterion asks (a) whether
   affirmative original CV evidence *actually entails* the precise JD, then
   (b) if not, whether independently completed related work or a related
   completed degree is transferable for review. Related academic majors are
   **not** automatically exact-major matches. A positive ordinary skill
   assertion remains acceptable without fabricated project history.
3. **Structured relationship contract.** Production Ollama/OpenRouter
   responses must supply `direct`, `entailed`, `overlap`, `absent`, or
   `uncertain`, as applicable, in addition to the decision. The correction
   and independent final-verification prompts align labels, reasons, source
   quotations, and employment context. Compatibility is preserved for older
   offline deterministic test stubs.
4. **Non-destructive citation normalization.** Four to six distinct, allowed
   citations for a normal three-citation requirement are bounded to the
   first three original IDs. Invented/duplicate IDs and larger malformed
   lists remain invalid. This changes only display/source metadata, never
   a status or score. For an explicitly source-entailed completed-work
   verdict, an invalid optional `matched_term` highlight is removed; the
   genuine cited completed action is still validated. Exact-quotation
   checks remain on ordinary named-item claims.
5. **Related-field mismatch handling.** A model `not_found` decision that
   explicitly declares `overlap` and cites a completed related credential
   is normalized into an **unscored Transferable** case, which must still
   pass the existing independent source-verified qualification validator.
   A different degree is **never** promoted to an exact named degree Found.
6. **Experience source linking.** For an already model-matched numeric
   experience criterion, original dated role headings may be attached
   deterministically to model-cited completed duties in that very role.
   Each role's actual cited performed duties must still establish work
   scope; a header/date or unrelated general tenure alone earns no point.
   Failed experience validation retains genuine cited review leads instead
   of silently erasing their provenance.
7. **Incomplete UI wording.** A candidate whose ranking is withheld no
   longer receives the caption implying its partial counts are final. An
   Unverified row without citations is described as an incomplete assessment,
   not as proof that no evidence exists.

## Safety, budget, and known limits

- Scores still equal **Found required ÷ required count**. Preferred Found
  only breaks ties. Transferable never inflates the score; Not Found and
  Unverified remain distinct. Denials, learning plans, copied JD text,
  unsourced claims, and invalid source IDs are not counted as Found.
- The current context-sized source batches still deduplicate CV source
  segments and transmit only bounded excerpts. The system does **not** send
  the full CV to OpenRouter by default. No optional shadow search was added.
- The existing **one grouped correction per invalid batch** and **at most
  one independent grouped final verification per CV** remain. The cloud
  run HTTP request ceiling remains 64. Prompt refinements can slightly
  change token consumption and batch size, but add no new retry stage.
- A source citation is evidence of what an applicant wrote, **not** an
  independently authenticated credential or proof of hiring eligibility.
  Explicitly exact academic major requirements should be treated as exact
  for scoring; a substantially related degree is shown separately for HR.
- This build can still display Unverified when an API/model fails or a
  semantically unsupported result cannot be justified. It must not fake a
  valid score to meet a completion target.
- **Live-provider limitation:** These repairs are tested offline against
  original synthetic source passages, original sample resume PDFs, and
  prior failure patterns. The release environment does not have the user's
  configured private `.env`, OpenRouter API token or local Ollama service.
  Therefore an actual five-CV Gemini run on the user's machine remains
  necessary before declaring production reliability.

## Windows smoke test

Keep the previous project folder as a rollback copy. Preserve your private
`.env` and applicant files separately. Install the full source release in a
new directory (do not merge half the modules from separate versions).

```powershell
.\run_runtime_check.cmd
.\run_tests.cmd
.\.venv\Scripts\python.exe doctor.py --live --provider openrouter
.\run_ui.cmd
```

`doctor.py --live` makes real provider calls. A successful synthetic doctor
check does not verify rankings for all live applicant PDFs. For a final
acceptance check, analyze the complete same JD and original CV set, verify
all candidates are fully assessed, and review R001/R002 and the candidate's
previously Unverified R004 with their original cited CV passages.
