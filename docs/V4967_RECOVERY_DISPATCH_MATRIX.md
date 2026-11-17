# Local semantic operation lifecycle and observable crash boundaries

| Boundary | Durable SQLite state | Automatic retry | Expected next action / limitations |
|---|---|---|---|
| Before claim | No entry | Eligible | Claim exact operation signature atomically |
| Claimed, before request | `claimed_unknown_delivery` | **No** | Operator/recovery review; cannot tell unsent from delivered after crash |
| Preflight refuses context or source | `invalid_response` (no network) | **No identical automatic retry** | Fix source/context; changed assessment identity may be retried |
| Claimed, different worker sees claim | `claimed_unknown_delivery` | **No** for same key | Other worker can claim unrelated fresh siblings |
| Request transmitted, provider times out | `provider_unknown_delivery` | **No** | Inspect provider/billing and checkpoint; explicit decision before repeat |
| Response schema invalid | `invalid_response` | **No identical semantic retry** | Correct schema/context; valid sibling rows can still commit |
| Validated source-bound decision | `validated_result`, SHA-256 reference | **No** | Use compatible saved *candidate report*; digest alone is not applicant source or result body |
| Model replied, process dies before commit | Prior claim may remain `claimed_unknown_delivery` | **No** | Actual response could be lost; external provider reconciliation is not available |
| Ledger committed, report not yet saved | `validated_result`, result SHA only | **No** | Explicit historical-uncertainty/review; do not fabricate restored original evidence |
| New B alongside blocked A | B `claimed_unknown_delivery`, A unchanged | **Yes for B only** | Send only B; no false attempted stamp for A |
| Concurrent [A,B] / [B,C] | One owner per signature | **Only owner** | A and C proceed independently; B at most one automatic owner |

The local ledger stores **no CV text, prompts, credentials or raw provider response**. It is *not* an exactly-once billing mechanism for cloud inference. Tests simulate concurrent connections and process restart; deliberate process kill at every network/commit boundary plus live provider reconciliation are **open** qualification items.
