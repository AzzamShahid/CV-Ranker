# V4.8.1 test-failure resolution

This is a hotfix to the independent V4.8 development branch. The approved
V4.7 archive and the weightage prototype remain unchanged.

The first full V4.8 test run on Windows reported **784 passed, 4 failed**:

| Failure | Cause | V4.8.1 resolution |
| --- | --- | --- |
| Prior "Earlier model-pass notices" text | Stale UI-copy assertion from V4.7 | Test now expects the unified "Assessment and validation notices" label. |
| Protocol version 3 expected | V4.8 intentionally uses version 4 | Test now asserts the V4.8 protocol version. |
| Failed candidate label "Incomplete" expected | New failure handling communicates unavailable assessment | Test now checks "Assessment unavailable · rerun" and "Not assessed". |
| `logical_calls` AttributeError on an object made with `__new__` | Counters were assumed to exist before context-budget validation | Counters now initialize lazily, **after** the first size check; refusals send zero requests and count as zero model calls. |

An additional regression test covers both Ollama and OpenRouter structured
LLM clients built without their normal constructor, and verifies that oversized
prompts fail cleanly without incrementing any model-request counter.

Re-run `run_tests.cmd` inside the V4.8.1 extracted folder on Windows, then
`run_runtime_check.cmd`, followed by the six-resume live comparison. No live
model accuracy or request-volume claim can be made from mocked unit tests.
