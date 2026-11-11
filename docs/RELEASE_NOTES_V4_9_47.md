# TextileHR AI / CV Ranker 4.9.47 - cross-domain evidence recovery

Date: 2026-11-11. Assessment protocol: v33.

## Reported reproducible failure

The fictional Weaving Production Supervisor test CV stated completed duties
such as "Supervise", "Coordinate", "Investigate", "Read", "Report" and
"Prepare" under a dated job. Version 4.9.46 rejected ten properly cited
work segments with `cited segment(s) contained no qualifying capability
evidence`, repeatedly requesting fresh model output although the source
citations themselves were valid. Because related dated-role logic used a
similarly incomplete action list, an otherwise documented period of employment
was reduced to manual-review-only tenure.

## Repairs

1. Expanded shared, **domain-neutral action grammar** for cited work evidence.
   No profession, job title, skill, candidate identity or requirement ID is
   special-cased. Provenance checks, negation checks, anti-instruction checks,
   exact citation IDs and independent model judgment are retained.
2. Linked present-tense work duties to their actual dated employer heading.
   The LLM must still cite performed work *within each credited role* before
   numeric experience may be marked Found. Bare job titles and unrelated years
   cannot independently earn credit.
3. Recognized ordinary qualified skills/certification section headings instead
   of accidentally leaving their text under Education.
4. When the JD explicitly offers an OR, a direct, completed, source-exact first
   degree alternative is allowed to satisfy that criterion. Mandatory ANDs,
   incomplete awards and *different* degrees do not receive automatic credit.
5. Fixed Oxford-comma OR-list parsing; avoided splitting shared-object
   expressions such as `A or supervision of X or Y` into fake independent
   competencies. A model-verdict for a long, non-atomic one-kind AND/OR clause
   can be retained **only** if cited performed work supports it, with a visible
   human-review flag. Mixed AND/OR and unsupported/negated/aspirational work
   still fail closed.
6. Kept bounded recovery and the cumulative OpenRouter request limit. Preventing
   *false invalid-citation retries* reduces cost; increasing the budget cap
   would not repair source-validation logic.

## Verification

- Offline real-PDF diagnostic: all ten previously rejected Adeel source
  citations now pass the same source/response validator when submitted as
  model `matched` rows. This diagnostic does **not** establish semantic match
  correctness: the live model must still choose and explain each verdict.
- Synthetic cross-domain regressions cover present-tense work, tenure linkage,
  OR-degree alternatives, long shared-object clauses, structured OR lists, and
  negative controls. The entire automated suite and source-integrity preflight
  must pass before packaging; their final counts appear in the release handoff.
- No paid OpenRouter requests were made during this repair. Live model outcomes,
  remote security, identity provider login, concurrency and hosting remain
  unverified by offline tests.

## Upgrade / first run

1. Keep a copy of the previous application directory and any safe recovery
   exports. Extract this ZIP into a **new** directory: do not merge older files.
2. Copy your private `.env` from the old installation. Do not include it in
   deployment ZIPs or send it to a public repository. Install dependencies in
   a fresh virtual environment if necessary.
3. Confirm Build ID, `ASSESSMENT_PROTOCOL_VERSION=33`, and runtime check.
4. Protocol v33 intentionally requires a fresh assessment. v32 recovery bundles
   contain decisions made with the old validation grammar; don't blindly import
   them or present an old partially verified ranking as a new result.
5. Run the same JD and test CV, inspect individual source citations, verify
   degree/experience, then perform one live supervised run before release.
6. If remote access is needed, apply the separate authentication, privacy,
   durable storage and monitoring gates described in production docs.

## Deployment choice

For this Python/Streamlit assessment engine, Streamlit is the direct app
deployment path. Lovable may supply a separate frontend prototype, but cannot
execute the Python ranking engine as a static frontend; a protected API/service
is needed for a real connected Lovable deployment. Don't expose cloud API keys,
model endpoints or applicant documents in client-side code.
