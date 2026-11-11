# Phase 7G V4.9.4 — transferable decisions, evidence recall and source consistency

**Build:** `phase7g-v4-9-4-related-degree-transfer-source-recall-2026-10-28`  
**Protocol:** `segment_ids_semantic_llm`, version 12

## Failure analysis and corrective contracts

The V4.9.3 model could produce accurate source citations and still lose
transferable findings in later code stages. This was a decision-contract
conflict, not primarily a model creativity issue.

1. **Typed degrees erased transferable judgments.** The qualification checker
   quite properly returned `mismatch` when an exact academic major differed
   from the completed CV degree. But the pipeline treated the existence of
   *any* qualification check as a ban on `Transferable`. This conflated
   **direct eligibility** (must stay unmatched) with **related training**
   (may warrant human review). The final view also hid semantic reasoning
   beneath a generic mismatch notice.
2. **Section labels vetoed real completed work.** The transfer gate only
   permitted evidence from a handful of section names. A source discussing
   independent completed activity in an education/background section could
   be rejected even though the model correctly understood it. The gate now
   checks the original action and disqualifying context independently of a
   rigid section allowlist. Substantive outcomes in a Projects section can
   also support review when the CV uses a project-title format rather than a
   past-tense verb, while planned/hypothetical and negated activities stay out.
3. **Named-tool denials crowded out comparable project evidence.** The
   evidence retriever prioritized up to three explicit mentions, followed by
   embedding hits. This could fill the prompt's segment budget with negative
   statements while a different completed workflow disappeared. V4.9.4
   reserves retrieval room for performed-work leads and independently
   compared project outcomes, using only tokens written in the candidate's
   source; the model still judges the functional relationship.
4. **One-pass `not_found` occasionally ended at lexical identity.** The main
   and independent model prompts now require TWO separate judgments: whether
   the JD item is directly established, and (only if not) whether completed
   alternative work or same-level related education merits an unscored
   `transferable` review. A plausible missed overlap can be checked in the
   existing, capped ONE independent grouped verification request per CV.
5. **Negated possessive degrees were parsed as complete claims.** `No
   bachelor's degree ...` previously bypassed the simple credential-denial
   parser. That negation is now correctly classified; pending, denied and
   wrong-level degrees cannot inherit transferability.

## What the repair does NOT do

- **No field or technology alias table.** Related-degree fields and alternative
  frameworks are judged from source-grounded semantic relationships, not a
  Python list of approved occupations, majors, vendors or tools.
- **No extra direct score for transferability.** A completed related major is
  not an exact-major match unless the JD explicitly permits that major/family.
  Transferable is retained separately with original citations and human review.
- **No automatic proof from cosine similarity or action verbs.** Retrieval
  leads only decide what evidence the model can see; the model must cite
  independent completed work and justify functional overlap. Missing,
  learning-only and copied-job claims cannot earn credit.
- **No unbounded API loop.** Grouped first assessment and at most one grouped
  correction for invalid citations remain. One independently adjudicated group
  per CV is the hard additional limit for unresolved or possibly missed
  transferable decisions. The configured total OpenRouter HTTP cap also
  remains in force. This may add one call on a CV with a plausible gap;
  it does not add one call per criterion.
- **No production accuracy claim.** Offline tests and synthetic source fixtures
  verify software invariants. OpenRouter's actual wording, adjudication,
  provider availability and HR acceptance still need a real authorized live
  multi-CV acceptance run before production use.

## Verified offline results on the release candidate

- Full source-based test suite: **906 automated tests** (including the new
  end-to-end typed-transfer, denial-only, late-segment-recall, and unrelated
  qualification controls).
- Existing eight-department synthetic *fallback* benchmark: **197/200**
  decisions matched (98.50%) across 40 candidates, with **zero false-positive
  direct matches** and three missed direct matches. The baseline was unchanged
  by this release.
- The SHA-256 source manifest and Windows runtime protocol guard are rebuilt
  for protocol version 12.
- No live OpenRouter/Gemini multi-CV measurements were available in this
  environment. Passing source contracts cannot guarantee live model quality.

## Core acceptance examples (field-independent)

| Frozen JD | CV source | Final expected class | Direct point |
|---|---|---|---|
| Exact bachelor's major | Completed *different but related* bachelor's major, cited and independently assessed as related | Transferable / HR review | No |
| Broad family of degree programs | Completed bachelor's in a member of the explicitly requested family | Found, when source-grounded | Yes |
| Exact bachelor's major | Unrelated, incomplete, denied or wrong-level degree | Not Found / review | No |
| Specific named tool | Completed alternative workflow with overlapping demonstrated function | Transferable / HR review | No |
| Specific named tool | Denial alone or a tool-learning plan | Not Found / uncertain | No |
| Specific named tool | Positive self-reported named skill without a denial | Found (self-reported, unverified externally) | Yes |

## Before a supervisor demonstration

Run the following from the newly extracted Windows project folder:

```powershell
.\run_runtime_check.cmd
.\run_tests.cmd
.\.venv\Scripts\python.exe doctor.py --live --provider openrouter
.\run_ui.cmd
```

Compare both a precise-major JD and a broad-degree-family JD with the same
authorized candidate set. In the results, inspect **R002 education, named
frameworks, transferred practical work, positive/negative citations, and
per-candidate `CVs fully assessed`**. Compare the JSON export and tab 03
against the original source. Do not rely only on aggregate percentages.
