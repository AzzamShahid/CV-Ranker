# Canonical assessment and recovery contract (protocol 57)

## Verdict versus processing

A **completed** current assessment has exactly one `Found`, `Transferable` or `Not Found` verdict with a source-backed explanation. Internal `matched/not_matched/uncertain` and historical `Unverified` fields are compatibility/evidence-stage data; do not present them as a fourth current candidate verdict. An unfinished record carries **null current verdict** and one of `pending`, `paused`, `failed`, or `input_required`; `running` can be represented by the scheduler while work is executing. An error is never turned into zero credit by treating it as Not Found.

`Found` requires every material mandatory JD obligation (and an allowed OR alternative). `Transferable` requires meaningful positive related work with an explicit direct gap, and **zero direct JD points** under the approved policy. `Not Found` follows an adequate original-source examination; truthful contextual/negative citations are permitted but never credited as affirmative evidence. Missing/read-failed documents, failed API calls, invented source IDs and truncated source packet are not candidate negatives.

## Dispatch and publication

- `condition_review.review_compound_uncertainty` schedules eligible review rows repeatedly in bounded batches; a batch size of six is **not** a total candidate cap. No identical signature is sent twice in one invocation.
- `semantic_review_signature` fingerprints frozen JD, original CV, protocol, schema/prompt/provider settings, assessment date and relevant source/segmentation logic. Weight-only and display-only settings are not semantic inputs.
- `LocalOperationLedger.claim_review` atomically records each attempt against the stable logical signature; Retry-After (where known) and a finite attempt cap prevent unbounded redispatch.
- Explicit 429 rejections are retry-eligible. A claim with **unknown delivery** cannot be blindly retransmitted. Authentication and input failures require their actual cause to be corrected.
- Validated assessment bytes are written to a private content-addressed `.json` file and fsynced where supported; only **after** publishing the file is the SQLite row marked `validated_result`. Restart checks the SHA256, candidate original segment identity and verdict state. Hash alone does not constitute a recoverable result. A missing/tampered file produces `result_store_unrecoverable`, not false success or automatic repeat billing.
- The ledger is local. It cannot guarantee exactly-once remote provider execution.
- Corrected review rows retain prior attempt/failure transitions. Completed independent siblings are preserved when another row fails.

## Security and limitations

The private result store can contain validated candidate excerpts (not model prompts or credentials). Use a restricted local filesystem and organizational retention policies; do **not** include runtime SQLite ledgers/result JSON in the source release. On Windows, durability follows atomic replace plus committed SQLite reference; a POSIX directory fsync is not portable. This is a deliberate limitation, not a Windows-tested claim.

**Caveat:** A syntactically valid but irreconcilably disputed model decision may need explicit semantic adjudication (`input_required/semantic_adjudication_required`) after bounded independent review. This is not a fourth verdict, not an API error, and not permission to guess `Not Found`.
