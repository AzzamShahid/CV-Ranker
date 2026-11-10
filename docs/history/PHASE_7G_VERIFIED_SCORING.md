# Phase 7G — Verified functional evidence coverage (report-only)

This checkpoint adds a **deterministic, audit-friendly scoring contract** at `cv_ranker/semantic/coverage_scoring.py`, exposed through `CVRanker.score_verified_functional_coverage(...)`. It is not invoked by the default Streamlit/UI ranking or the Phase 7G retrieval shadow yet; it awaits JD capability decomposition and independent Qwen evidence adjudication.

## Why we don't copy `similarity.py`'s calibrated percentages

A cosine similarity of 0.78, a cross-encoder logit or a manually rescaled percentage describes a retrieval signal, not the probability that a candidate is competent. The example threshold intervals and exponent curves were not fitted to labelled CV evidence. Even a genuinely measured calibration on held-out relevance labels would predict *passage relevance*, not candidate qualification.

### Existing scoring remains authoritative

`cv_ranker/scoring.py` continues to compute matched frozen criteria / frozen criteria, with required-priority semantics, preferred reported separately, status `uncertain` earning no match, and equal scores sharing rank. NOTE: its `matched` status reflects the existing assessed requirement coverage and is **not** a guarantee of exact-name or exact-tool matching; reviewer-approved equivalences and semantic assessment may already contribute.

### New report-only scoring (not used for sorting)

`score_verified_capability_coverage` accepts:

- Original `CandidateResult`, frozen `ValidatedRequirement` list.
- `CapabilityPlan` records (each child linked to its frozen parent; `origin=search_hint` is never scoreable).
- `AdjudicatedCapability` records covering *every* plan ID, with one of `direct`, `transferable`, `related_only`, `not_evidenced`, `uncertain`.
- Independent `verification` status, preserved constraint status, and candidate-scoped allowlisted source IDs.

A capability counts toward complete functional coverage only when (a) its adjudicated relationship is `direct` or `transferable`, (b) cited IDs are valid **for this candidate**, (c) the independent verifier marked it `verified`, and (d) its conditions were `satisfied`. The model **must not** mark its own output independently verified.

A parent requirement is `direct_supported` only when **all** explicitly required capabilities are verified direct. It is `functionally_supported` only when **all** are verified direct or transferable and at least one is transferable. Mixed incomplete cases are `partially_supported`, and neither earns full-parent credit. A frozen required parent with no decomposed explicit obligations makes aggregate function coverage unavailable. Any unresolved required capability makes aggregate percentage unavailable, not zero.

We count **whole frozen parent requirements**, never raw numbers of model-generated child capabilities, for numeric diagnostic coverage: `complete required parents / total frozen required parents * 100`. Search-only expansions do not change the denominator.

**The resulting ratio is a descriptive evidence-coverage rate, not a competence probability or a production selection score.** It is not added to original `primary_score`, does not produce any partial weight, and does not change `assign_ranks()`.

## Run offline fixture and tests

```powershell
.\.venv\Scripts\python.exe -m scripts.phase7g_coverage_demo
.\.venv\Scripts\python.exe -m pytest -q
.\run_runtime_check.cmd
```

## Next phase — source-grounded JD decomposition and verification

1. Produce atomic capabilities from the *frozen* JD with Qwen, keep source ID and exact logical constraints, reject invented obligations.
2. Query EmbeddingGemma for each explicit capability and parent requirement; deduplicate source evidence.
3. Have Qwen propose evidence relationships in token-budgeted groups; independently verify source admissibility, claims, context, negation, and constraints.
4. Convert only the independently validated decisions to `AdjudicatedCapability` and call `score_verified_capability_coverage`.
5. Benchmark on held-out, labelled evidence before deciding whether scoring should ever affect final rankings.

## Benchmark plan for actual calibration

If future retrieval probabilities are desired, collect representative, human-labelled *query–evidence* pairs. Fit a separate model-specific Platt/logistic or isotonic calibrator on training data, evaluate calibration error and reliability curves on held-out samples, and recalibrate whenever the model, prefixes or text distribution change. **Do not** convert the resulting relevance probability into a competence score.
