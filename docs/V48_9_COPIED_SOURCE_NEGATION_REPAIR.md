# Phase 7G V4.8.9 — Copied-source and negative-evidence integrity

## Observed failure in the V4.8.8 live UI

Five fictional CVs were uploaded. Four received results; the fifth was
unranked. The warning on one broad application-development criterion was:

- `cited segment(s) contained no qualifying capability evidence`
- then `assessment row was missing or duplicated`
- then `unresolved after grouped correction`

The keyed schema in V4.8.8 did improve completeness, but did not prevent
individual *citations* from being rejected. In the unified verifier, the
second “missing” warning can mean `_map_response` removed a rejected row;
it does **not** necessarily mean the model omitted the required JSON key.

## Root causes confirmed from PDF extraction

1. **Physical wrap boundary:** A source line explicitly marked `TARGET JOB
   DESCRIPTION - NOT A CLAIM OF EXPERIENCE` was correctly labelled
   `non_candidate`, but its following physical line was mistakenly emitted in
   the previous `projects` section. The engine could therefore retrieve
   copied requirements as apparent candidate evidence.
2. **Missing grammatical negation patterns:** The tone checker understood
   `never used` and `no experience with`, but not common forms like `I have
   not developed...`, `we have no...`, and `No ... has been performed`.
   A negative claim without an exact frozen-JD phrase then appeared
   positive-toned; its lack of performed capability verbs triggered a
   technical rejection rather than a valid negative decision.
3. **Diagnostic masking:** A citation rejected by `_map_response` was removed
   before the generic assessor received the response. That assessor then
   reported the row as “missing or duplicated”, obscuring the actual
   out-of-scope or malformed source ID. The corrective prompt lacked that
   feedback and could repeat the mistake.

## Changes

- Copied-ad paragraph continuation is quarantined until a new bullet, section
  heading, blank boundary, or prior-sentence boundary. Later authentic
  resume work is preserved. This uses **document provenance**, not skill terms.
- Eligibility filters additionally veto explicitly copied job requirements,
  independently of the segment label.
- Generic applicant denial grammar is recognized. A model-proposed positive
  citing an explicit negative-only statement resolves to `Not Found` with the
  original source retained; no additional model call is necessary.
- Citation preflight reports meaningful technical reasons (unsupplied source
  ID, too many IDs, duplicate evidence ID, or positive decision without a
  citation). The correction sees these reasons. No source text or API key is
  included in diagnostic messages.
- The V4.8.8 required-ID schema, evidence-grounding, conservative
  `Unverified` fallback, and required-only score remain unchanged.

## What is and is not verified

The generic copied-paragraph, denial, source-ID and end-to-end negative-only
contracts are covered by additional tests. A bundled fictional PDF is also
used **only as a parser fixture** to verify that the original physical wrap
is handled; no filename or individual skill appears in runtime matching
rules. Existing cross-department and anti-hallucination regressions remain.

The next real OpenRouter run still determines whether **5/5 candidates are
fully assessed**. Unit tests and a successful three-requirement live doctor
smoke test do not measure the model's semantic ranking precision. Persistent
Transferable=0 outcomes should undergo a separate evidence-level review;
they are not declared correct by this parsing repair.

## Windows check

```powershell
.\run_runtime_check.cmd
.\run_tests.cmd
.\.venv\Scripts\python.exe doctor.py --live --provider openrouter
.\run_ui.cmd
```

Expect `BUILD_ID=phase7g-v4-8-9-wrapped-source-negation-integrity-2026-10-28`
and `ASSESSMENT_PROTOCOL_VERSION=7`. Close the earlier Streamlit process
and rerun the original five fictional CVs after selecting the new build.
Retain the score CSV, candidate table, and technical diagnostics for the
semantic review; no new private resume upload is needed.
