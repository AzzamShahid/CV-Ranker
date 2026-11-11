# TextileHR AI / CV Ranker 4.9.46 — bounded final recovery

**Classification:** Supervisor-assisted testing release. Not a production-certified hiring decision engine.

## Reported issue

Multiple candidates' frozen requirements remained `Unverified` after source/response
validation. Automatic recovery correctly paused to avoid repeating identical
paid OpenRouter requests, but the final independent review had a coverage gap:
it considered only the first output-budget-sized slice of unfinished IDs. A
malformed grouped JSON final answer did not adapt into smaller requests.

## Changes

1. Every unverified criterion now reaches independent final source adjudication,
   including IDs beyond one model-output-sized group. Optional overlap reviews
   remain capped.
2. Independent review starts in groups of no more than four frozen IDs. A
   malformed larger JSON response splits **once** into smaller disjoint
   groups. When a group parses but contains invalid source citations, only
   the rejected subset may receive one smaller follow-up. Individual
   persistent failures never trigger an identical repeat.
3. Already verified assessments, frozen requirements, Python evidence
   validation, degree/experience rules, scoring, weightage and exports are
   unchanged. Unknown or fabricated citation IDs remain unverified; the
   system does not invent a ranking.
4. The UI distinguishes *source-validation no-progress* from *actual HTTP
   budget exhaustion*. Execution details show used/total/remaining attempts.
   If the configured cumulative ceiling is truly exhausted, the review pauses
   with explicit instructions rather than bypassing a spending safeguard.
5. `OPENROUTER_MAX_REQUESTS_PER_ASSESSMENT` remains a finite configurable
   ceiling (default 128 HTTP attempts across the checkpoint). Changes to this
   transport setting do not invalidate already verified source judgments.

## Verification

- Offline regression cases: invalid original citation fails closed; a malformed
  four-ID verification splits into two different two-ID requests; seven pending
  IDs are all independently considered even with a one-ID completion budget.
- All pre-existing unit/integration/UI tests are run as part of the source
  release verification. The real OpenRouter provider and the user's specific
  multi-CV inputs **were not available** for live replay.

## How to recover the affected assessment

1. Preserve/export the existing signed recovery checkpoint and complete-results
   ZIP. Keep these sensitive files private.
2. Replace the application files with this complete 4.9.46 release; keep the
   local `.env`, signing key, input CVs and checkpoint outside release folders.
3. Launch, re-upload the identical JD/CVs, reapprove the same frozen JD and
   Resume. Previously verified decisions are retained when source identities
   and policies match.
4. Inspect **Execution details** for actual HTTP attempts and remaining budget.
   Only if **remaining = 0**, raise
   `OPENROUTER_MAX_REQUESTS_PER_ASSESSMENT` deliberately in local `.env`,
   restart and Resume. Raising it is permission for more paid requests.
5. If an individual criterion remains `Unverified`, inspect its source IDs
   and validation warning. Do not force credit or repeat identical requests.
   Share a redacted execution diagnostic with the maintainer for a
   criterion-specific *root-cause* analysis.

Do not remove the cloud-request budget or raise it without authorizing
possible additional provider charges.
