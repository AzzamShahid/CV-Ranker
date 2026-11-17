# v50 technical failure diagnostics and recovery boundary

`cv_ranker.failure_diagnostics.classify_failure` maps sanitized available execution facts to codes/actions without leaking candidate CV text or model responses. `UnifiedMetrics.unresolved_diagnostics` provides per-R details for incomplete unified assessments. This **diagnostic** patch does not install a new durable retry scheduler.

| Code | Appropriate next operator action |
|---|---|
| `MODEL_SCHEMA_INVALID` | Correct failed R schema only within configured cap; keep valid siblings |
| `OUTPUT_TRUNCATED` | Split R batches, reserve output capacity, preserve sources |
| `CONTEXT_OVERFLOW` | Repack against provider-specific fully serialized context; disclose omitted source IDs |
| `PROVIDER_RATE_LIMIT` | Honor cooldown/budget; no instant identical retry |
| `PROVIDER_UNAVAILABLE` | Retry only after provider recovery and within the original cap |
| `PROVIDER_TRANSPORT` | Diagnose connection/timeout, preserve checkpoint and prior results |
| `REQUEST_BUDGET_EXHAUSTED` | Preserve prior results; only proceed after explicit authorization |
| `REJECTED_MODEL_CITATION` | Review rejected IDs, search materially different original source or permitted citation correction |
| `SOURCE_VALIDATION_INCOMPLETE` | Inspect exact original R/S trace; avoid repeated identical semantic requests |
| `PROVIDER_REQUEST_FAILED` | Inspect sanitized provider error and prerequisites |

`selected_source_ids` are transmitted/selected **candidate-specific IDs**, `rejected_model_ids` are not accepted proof, `review_source_ids_not_verified` are only clues. **An `Unverified` result is a technical failure, not an assertion that the candidate lacks capability**. Do not relabel it `Not Found` merely to produce a complete-looking rank. The current grouped correction/independent source review remains bounded, and it preserves successful siblings. No full process-death durable deduplication or per-cause attempt signature persistence is claimed by v50; that remains R6/G6 work.
