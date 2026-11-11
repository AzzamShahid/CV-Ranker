# Phase 7G V4.9.36 — Numeric work tenure and frozen-JD skill-scope reliability

## Reproduced root causes

1. **Unrelated numeric duration misclassified as a CV career claim.** The
   bundled Aisha PDF says `Professional experience: 5 years 9 months` and
   separately describes `two years of retail series` in a research work
   sample. PDF section parsing can retain a Work Samples entry in the
   `experience` section. `experience_validation._scope` previously considered
   any number of years in that section to be employment if generic work
   vocabulary appeared nearby. It incorrectly formed both 5.75-year and
   2-year experience claims, so the validator reported a false contradiction
   and declined the JD minimum of three years.
2. **A reason-level negation prevented a justified independent skill review.**
   The bundled Aisha PDF contains completed medical-image pilot, segmentation
   research and experimental prototype work. The first model called the
   frozen, bare `Medical imaging` skill only Transferable because the work
   was not commercial or deployed. Existing independent-review detection
   rejected the whole sentence after seeing a late `not deployed` clause,
   even though the same sentence affirmed completed research in the named
   skill. As a result, that downgrade was never reexamined.

## Repairs

- General experience durations now require a grammatical link between **each**
  numeric interval and tenure, professional work, service or professional
  research. An `experience` section label or generic work verb somewhere in
  the sentence is not sufficient. Dated role-specific evaluation remains
  separate and unchanged. The patterns use grammatical words, not titles,
  professions, CV names, domains or JD IDs.
- A completed, cited named-skill claim that is downgraded specifically for an
  unstated deployment/employment condition enters the **existing bounded
  independent adjudication**, even when the model states its objection in the
  same sentence. The final LLM must still cite original CV source and evaluate
  what the frozen JD actually requires. Python neither promotes a skill to
  Found automatically nor changes its score without that review.
- Reinforced the final adjudicator's instructions: completed, genuinely
  relevant research or pilots can demonstrate an ordinary skill when no
  production threshold exists in the JD. Mere adjacent or learning-only
  exposure remains Transferable or Not Found, as supported.

## Test evidence and boundaries

- Tests use the original bundled fictional Aisha PDF and verify the complete
  experience validator → final reconciliation route restores an appropriately
  cited Found for the 3-year condition, without counting dataset years.
- Additional generic examples cover datasets inside Experience, working
  **with** several years of data, a real statement of years **working for**
  an employer, work performed **for** years, and two distinct intervals in
  the same physical sentence. The previous research-tenure calibration remains
  intact.
- The skill tests verify the original-source independent recheck trigger for
  both medical imaging and a fabric-weaving research pilot, plus a complete
  two-pass fake-model adjudication that promotes a correctly cited result.
- Unverified and unsupported claims still receive **zero** credit. The system
  preserves its request budgets and fail-closed source validation; no extra
  automatic retry loop was introduced.
- The actual OpenRouter response in the user's Windows session was not
  available. Offline simulations are not evidence of a successful live cloud
  model response. A real provider test is still needed to confirm behavior
  under that account, its settings and any remaining rate limits.
