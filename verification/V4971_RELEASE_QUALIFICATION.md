# TextileHR AI · 4.9.71 RC1 / protocol 57 · Qualification

**Result:** Code repair candidate; **not certified as production-ready**.

## Demonstrated

- Seven DA-01–DA-07 regression probes were first reproduced as seven failures in RC1, then passed after repair.
- Controlled tests cover 1/6/7/12/13 compound requirements, correct three-way verdicts, ordinary semantic scope disagreement, negative contextual citations, original-source protection across all verdicts, operation cooldown/exhaustion, concurrent claim, unknown delivery, missing/corrupt result, repeat restart and no extra model call on compatible recovery.
- A typed OpenRouter 429 with Retry-After >90 seconds prevents immediate Resume; an explicit rate limit with no cooldown is bounded to three attempts.
- The broad suite after deliberate legacy-contract migrations completed: **1,554 passed; 20 failed; 10 collection errors**. The 20 failed test nodes report missing `streamlit`/`langchain_*`; 10 collection errors are missing runtime packages. These are **not passing tests**, nor are they evidence that the source is fully compatible with pinned dependencies.
- Local source manifest must be regenerated **after final file changes** and verified against an independently extracted source ZIP. Release final checks and exact archive hash are recorded in the final handoff, not assumed here.

## Externally blocked

- Complete pinned dependency installation (package index DNS failure).
- Native Windows Python 3.11 / UI / PowerShell / crash-restart and concurrent filesystem tests.
- Ollama/OpenRouter live-model quality, latency, tokens, costs, human-labeled holdouts.
- Requested historical v4.9.68 Windows Test Compatibility archive (SHA starts `813f1deb`) not supplied; release ancestry against that exact base cannot be asserted.
- Remote deployment approval not requested; multi-user security and external auth unqualified.

## Remaining engineering uncertainty

A developer should rerun the full suite in an actual supported, pinned runtime and investigate any failures after dependency installation. Intermediate `uncertain` relation remains allowed at facet/retrieval stage. A bounded semantic dispute can be held with explicit `semantic_adjudication_required`; an unresolved semantic issue is **not** a fake JSON/transport failure and not a completed `Not Found`.

## Execution commands

```bash
bash verification/V4971_VERIFY.sh
python -m pytest -q --continue-on-collection-errors
```

Refer to `V4971_ISSUE_REGISTER.csv`, `V4971_DECISION_RECOVERY_CONTRACT.md`, `V4971_PROMPT_BUILDER_SCHEMA_LEDGER.md` and `V4971_WINDOWS_QUALIFICATION.md`.
