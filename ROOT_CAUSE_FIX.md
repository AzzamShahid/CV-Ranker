# Root Cause and Fix

## Live failure
The JD was correct (9 required requirements), but the CV stage produced 0/9 because the model's legitimate short evidence quotes were rejected by `resolve_contextual_evidence()`.

The old resolver accepted a substring only when it was at least 5 words or 40 characters. Therefore valid model evidence such as `Programming: Python`, `NLP`, `LLM integrations`, `model evaluation`, and `AI/ML: TensorFlow, PyTorch` could be rejected even though the phrases were present in the source resume. A correction retry often returned another short quote and the code then converted the row to `not_matched`.

A second failure was that Qwen2.5:3b can independently miss obvious abbreviation/direct-alias matches such as ML/Machine Learning and DL/Deep Learning. The Python alias rules existed, but they were only used to validate proposed matches; they did not protect against an LLM false-negative.

## Applied solution
1. Added deterministic resume segmentation into numbered evidence units (`S001`, `S002`, ...). Physical PDF line wraps are merged into stable source units.
2. The live LLM assessment schema now returns `evidence_ids` instead of copied evidence text.
3. Python resolves IDs to exact source text and then applies relevance, alias, OR, negation, uncertainty, contradiction, and instruction guards.
4. Added ML/Machine Learning and DL/Deep Learning explicitly to the assessment prompt.
5. Added a deterministic direct-source safety net. It can correct only exact/direct-alias/OR false-negatives. It cannot award transferable credit.
6. Preserved backward compatibility for older deterministic tests that use free-text evidence.
7. Added precise validation warnings instead of one generic invalid-evidence message.
8. Added regression tests based on the Naqvi failure pattern.

## Validation
- 103/103 tests pass.
- Python compile check passes.
- The actual uploaded Naqvi PDF is segmented correctly.
- With a deliberately hostile fake LLM returning `not_matched` for every requirement, the direct source guard still recovers 8/9 explicit/direct requirements and leaves only `AI application development` unresolved for semantic judgment.
