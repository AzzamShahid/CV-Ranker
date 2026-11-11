# Phase 7G V4.9.9 — typed source validators and final-decision alignment

**Build:** `phase7g-v4-9-9-typed-validators-and-ui-reconciliation-2026-10-28`  
**Protocol:** `segment_ids_semantic_llm`, version 17

## Confirmed root causes in V4.9.8

1. **Exact-degree check discarded valid overlap.** Python correctly rejected
   a different completed major as an exact Computer Science degree, but the
   downstream decision only preserved `Transferable` if the first LLM label
   had already been exactly `Transferable`. A model could explain why BS
   Software Engineering was closely related and select `Found` instead; the
   exact-degree veto turned the row into `Not Found`, losing that overlap.
2. **Experience validator conflated scoring and transferability.** A
   genuinely completed cloud/backend project can be related to AI software
   delivery while the CV fails to establish the full required number of
   AI-specific professional years. The numeric validator properly withheld
   direct credit, but final Python reconciliation used the mere presence of
   an experience diagnostic to block **all** transferability too.
3. **UI replaced reconciled reasoning.** The display adapter unconditionally
   substituted a generic experience/degree/compound validator explanation
   for the final assessment reason, creating headings and explanations that
   disagreed or omitted the candidate-specific basis.
4. **Negated and pending claims needed explicit negative controls.** The
   qualification parser did not flag a leading `Expected BS ...` form as
   pending. That could make an unfinished qualification appear completed.
5. **A compound OR validator can validly override an LLM.** For example,
   `TensorFlow or PyTorch` should not receive direct credit merely because
   the CV says the applicant **plans to learn** one of them. We kept that
   source-protection rule and made any changed reasoning describe the
   literal option results rather than the earlier LLM guess.

## Repairs and their authority boundary

| Stage | What Python may establish or reject | What the model must still decide |
| --- | --- | --- |
| JD extraction | Exact source quote, explicit priority, typed numeric/Boolean wording | Which JD statements are requirements, semantic meaning of a compound condition |
| Evidence source checks | Original segment IDs, actual candidate claims, denials, copied JD text, duplicate citations | Whether the claimed performed task entails a JD capability |
| Qualification check | Credential's claimed level, actual written field, pending/denied state, exact named-major equality | Whether a *different* completed field is meaningfully related |
| Experience check | Numeric duration, non-overlapping dates, evidence that the cited work is actually performed | Whether each cited role's duties satisfy the JD-specific work scope |
| Compound check | Literal `A or B` or simple `A and B`, including negated and learning-only statements | Broader semantic equivalents and transferable but non-identical work, under reviewer control |
| Final UI/report | Consistent Found/Transferable/Not Found/Unverified labels, source citations, immutable scoring | No new AI judgments performed in the UI |

### Specific behavior

- BS Software Engineering / BS Information Technology for an **exact** BS
  Computer Science JD: **Transferable, not Found** if a source-grounded
  semantic explanation identifies both academic fields and their substantive
  relationship. This is not credential equivalence or a hiring guarantee.
- MSc Artificial Intelligence for a bachelor's Computer Science requirement:
  potential **Transferable** if *completed, cited, academically related*.
  A higher award does not prove the applicant earned the specific lower one.
- PhD Classical Archaeology for a CS JD: not automatically transferable just
  because a generic template says "alternative degree with overlap".
- Four years and nine months of cloud/backend engineering with a *recent,
  shorter* LLM feature period: the 3-year AI-focused minimum is **not directly
  proved**, so no required credit; independently cited completed overlapping
  work can be shown as **Transferable**, with this limitation explained.
- Four years of explicitly scoped professional LLM/software development:
  remains **Found** when the actual original numeric claim is source-verified.
- IT service desk tenure and a copied JD/denial: cannot be promoted to
  direct AI professional tenure. A future-learning list cannot be treated as
  hands-on use of its named tools.

## No new complexity or cloud requests

These are *post-assessment source and presentation repairs*, not another
LLM layer, cross-provider evaluation, synonym map, vector index, additional
shadow pass or per-JD-item API loop. The existing bounded grouped assessment,
one grouped correction per invalid group, at most one independent grouped
verification per candidate and 64-request cloud run ceiling remain.

Transferable is always **reviewer-only** and never adds an exact Found point.
Unverified source/model failures still withhold a score; the program does not
manufacture an answer to meet a target completion rate.

## Verification and limitations

The offline regression tests include actual source-text extraction from the
fictional Sara, Amal and Salman PDF fixtures, exact and related academic
credentials, unrelated-degree and pending-degree negative controls, role
duration scope and the final UI reasoning. The prior eight-department
synthetic benchmark is also run on the new release. It is not real-world
hiring ground truth.

**Not validated live:** No private OpenRouter key, local Ollama service or
user CV set is installed in this environment. These repairs are source-code
and reproducible offline tests; actual Gemini behavior, full multi-CV
ranking stability and external credentials cannot be guaranteed without a
live run on the Windows system.

On Windows, keep your old build intact as a rollback. Install this complete
release into a separate folder and preserve your private `.env` and input
CVs. Then run:

```powershell
.\run_runtime_check.cmd
.\run_tests.cmd
.\.venv\Scripts\python.exe doctor.py --live --provider openrouter
.\run_ui.cmd
```

`doctor.py --live` invokes the configured provider and can incur charges.
Afterward analyze the same JD and candidate set and inspect the original
R001/R002 citations plus all final decision explanations. Any remaining
contradiction should be reported with the new build ID and JSON evidence
export; the source ledger is the reference, not the label alone.
