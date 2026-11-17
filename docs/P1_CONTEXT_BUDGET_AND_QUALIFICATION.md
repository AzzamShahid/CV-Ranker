# P1 prompt budget — rendered fictional packet size audit

**Scope:** approximate input/schema token budgeting for 14 schema-specific fictional packets (13 approved prompt texts; focused judge measured in full and compact forms).
The source script `scripts/p1_prompt_budget_audit.py` generates `docs/P1_FICTIONAL_PROMPT_BUDGET_AUDIT.json`. This is a local estimator, **not an exact tokenizer or a real CV corpus**. It uses the application’s own conservative `estimate_tokens()` function.

The default configured local ceiling is 8,192 context tokens with 2,048 reserved for output; the application cloud request ceiling is 32,768 with 4,096 reserved for output. These are settings, not provider capacity guarantees.

| Request stage | System characters | Estimated combined tokens* | Local remaining tokens** | Cloud remaining tokens** |
|---|---:|---:|---:|---:|
| JD extraction | 2,440 | 964 | 5,180 | 27,708 |
| JD correction | 1,026 | 560 | 5,584 | 28,112 |
| Requirement typing | 1,116 | 584 | 5,560 | 28,088 |
| Unified primary | 5,832 | 2,081 | 4,063 | 26,591 |
| Unified independent | 5,860 | 2,097 | 4,047 | 26,575 |
| Legacy initial | 5,551 | 2,042 | 4,102 | 26,630 |
| Legacy correction | 6,097 | 2,198 | 3,946 | 26,474 |
| Compound review | 7,249 | 2,814 | 3,330 | 25,858 |
| Search decomposition | 1,344 | 792 | 5,352 | 27,880 |
| Shadow full | 6,950 | 2,511 | 3,633 | 26,161 |
| Shadow compact | 6,751 | 2,292 | 3,852 | 26,380 |
| Shadow batch | 6,888 | 2,463 | 3,681 | 26,209 |
| Focused judge full | 5,511 | 1,892 | 4,252 | 26,780 |
| Focused judge compact suffix | 5,715 | 1,862 | 4,282 | 26,810 |

*Combined estimate includes approved expanded system text, one minimal fictional user payload, and serialized JSON schema overhead.
**Remaining capacity is computed after model output reserve and the minimal fictional packet; real multi-page CVs, long JD trees, retries and additional source segments reduce this headroom.

## Interpretation and required real-call checks

These small synthetic packets fit the configured application ceilings. This **does not certify** full CV packets, input truncation behavior or token count against the actual tokenizer.
At runtime, capture the full selected source packet, actual schema and output reserve before dispatch; require `prompt_fits()` or the provider-specific equivalent.
If a large payload cannot fit, use existing safe segmentation/batching or mark source coverage incomplete. Never silently omit a qualification page or produce Not Found from missing context.
Correction and independent review can add substantial context. Reevaluate each retry as a new request; budgets are not inherited from first call.
No paid model calls, latency/cost comparison, real tokenizer counts or human-labelled accuracy experiments were performed.
