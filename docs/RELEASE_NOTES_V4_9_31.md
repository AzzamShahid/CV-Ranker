# V4.9.31 · Dynamic frozen-JD allocation and explainable leaderboard

Build: `phase7g-v4-9-31-dynamic-jd-weights-and-reasoning-2026-11-10`

## Approved workflow

1. Upload/paste the JD and select the CV files.
2. **Extract** JD criteria (weight totals no longer block extraction).
3. Edit, explicitly approve, and **freeze** the JD requirements.
4. Configure category weights: Experience, Education, JD Requirements. Totals must equal 100%.
5. Edit every criterion's **percentage of its category**. The initial percentages are equal across present criteria; changing one share automatically redistributes its category peers while the category remains at 100%.
6. Run the CV assessment. Afterwards, changing the weighting values instantly recalculates the published weighted leaderboard and the ranking explanations. The frozen JD, assessment, source citations, underlying candidate scores, and cloud request budgets are not altered.

Required and Preferred criteria share the same JD allocation. The sidebar split reveals separate count columns only. A numeric minimum-years requirement belongs to Experience; an education requirement belongs to Education. A qualitative work capability remains in JD. Categories missing from the actual JD are excluded and the remaining category weights are renormalized exactly as before.

Example: 80% overall JD weight, 16 pooled JD criteria. Set Python's share of the JD category to 25%; its maximum earned contribution is **20 overall percentage points** (80 × 0.25). The other fifteen entries automatically share the remaining 75% of the JD category. A Found Python earns the 20; Not Found and Transferable earn zero. No LLM call is needed to reweight a completed evaluation.

## New explanations

- **Each candidate:** `Why this CV received its ranking` summarizes the current weighted position, strongest credited requirements, highest-impact gaps, transferable (non-scoring) capabilities, requirement-level original Why explanations, and validated source segment identifiers.
- **Overall results:** a top-priority summary, explicit tied-first recognition, comparison against all other ranked candidates, and candidate-by-candidate summaries. Comparative advantages are derived from the same frozen decisions and current per-requirement point contributions that compute leaderboard scores. Incomplete assessments stay unranked.
- **Reliability check and repair:** an independent deterministic audit checks explanation presence, final/assessment decision agreement, verified source segment references, completeness, and contribution arithmetic. Missing or structurally conflicting narrative is regenerated from stored frozen results, with a visible repair log. Neither scores nor rankings are modified. Repairs require **zero** additional OpenRouter or Ollama calls, with no recursion or retry loop.
- **Scope limitation:** mechanical checks cannot prove the full semantic truth of arbitrary AI-generated sentences, authenticate CV claims, or independently verify qualifications. Human source review remains necessary. Unsupported source references are excluded from synthesized evidence rather than claimed as verified.

## Exports

The complete ZIP includes the existing original JD, all frozen requirements, all CV source ledgers, original assessment decisions, and a new:

- `weighted_requirement_allocations.json`: criterion-by-criterion possible and earned score points per candidate.
- `overall_ranking_reasoning.json`: winner/tie statement, comparative differences, individual position explanations, and audit notices.
- `candidates/candidate_NNN_results.json` → `candidate_ranking_why`: candidate-specific reasons and deterministic repair diagnostics.
- `scoring_weights.json` → `requirement_shares_percent_of_category`: saved edited percentages; defaults remain reported as equal, with actual percentages visible in the contribution export.

## Additional correction discovered during the audit

Legacy review and Transferable metadata was looked up by its position in a **primary-score-sorted** list while the new leaderboard was sorted by the **weighted** score. The two orders could differ and assign one candidate's review label to another. The cross-reference is now by immutable source candidate index, so duplicate candidate names also remain safe.

## Verification / non-goals

Relevant deterministic tests cover unchanged equal-weight baselines, arbitrary per-category shares, rebalancing, pooled Required/Preferred behavior, ties, reordered candidates, unverified scores, explanations, contradiction/missing-source repair, and ZIP exports. The full offline pytest suite, Streamlit startup, and integrity manifest are part of release packaging.

No source CVs or credentials are embedded in the release. No live paid provider assessment is performed as part of the offline test suite. Real-world ranking semantics remain limited by the source-grounded assessment and human review.
