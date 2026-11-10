# V4.8.2 — live UI and partial-model-response repairs

The approved V4.7, previous V4.8 builds, and independent weightage page are
untouched. V4.8.2 changes only the unified assessment development branch.

## Crash fixed

The **03 CV source segments** tab was still referencing the removed optional
`semantic_ids` diagnostic, raising `NameError` on every rendered source table.
The tab now uses the verified retrieval-first batch's `selected_source_ids`
and labels them **Prioritized for assessment**. It shows both model-cited
segments and semantic-prioritized segments without a second retrieval pass.

## Partial model-row failures

Previously two invalid rows (such as R004/R005) failed an entire candidate,
even if every other row was valid. This was over-strict and hid verified work.
The candidate now keeps its independently validated rows. For invalid rows:

1. At most **one grouped correction** is sent for the invalid subset, with
   specific validation error hints and more previously retrieved passages if
   the request fits. No new search, model, or per-requirement LLM loop is used.
2. If the row still fails, the **existing exact-source validation** may recover
   a directly stated positive skill, with a supervisor-review marker.
3. Otherwise the row becomes `uncertain` internally, carries original CV
   evidence leads for review, receives **no Found point**, and displays
   `Not Found` / **Uncertain evidence** in the existing three-label final table.
   It is explicitly **unverified**, not proof of the candidate's inability.
4. Technical details include `unresolved_criteria` and
   `exact_source_recoveries`, alongside actual model calls, retries and tokens.

If an entire LLM batch or embedding model is unavailable, the candidate may
still fail without a score. The partial-row recovery applies only where the
principal LLM returned a usable batch containing individual invalid rows.

## Validation checklist

- Run `run_tests.cmd` and `run_runtime_check.cmd` in the new extracted folder.
- Start `run_ui.cmd`, open all four tabs with at least one candidate, and
  confirm the source table displays prioritized segments without exceptions.
- Test the same JD and Sara resume that previously failed R004/R005. Inspect
  actual evidence and review flags. An incomplete or uncertain skill must
  never gain an unsupported scoring point.
- Review request counts in **04 Technical details** against the prior run.
