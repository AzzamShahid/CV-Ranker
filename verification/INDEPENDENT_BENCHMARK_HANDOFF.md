# Blinded CV/JD evaluation — independent labeling handoff

**Current qualification: NOT ACCURACY-TESTED WITH HUMAN LABELS.** Never use model-generated answers as the gold standard.

Use `evaluation/independent_gold.py` and `python scripts/validate_independent_gold.py independently_labeled_gold.jsonl --output label_preflight.json` to validate annotation metadata. Each JSONL case must supply:

- Unique `case_id`, `job_family`, `document_group`, `wording_family`, source-byte SHA-256s of the candidate and JD, `requirement_id` and split (`development`,`tuning`,`holdout`). Split documents *and* template/wording families, not just row IDs.
- Exactly two separately identified reviewers, both with `model_result_visible=false`. Each reviewer independently assigns `Found`, `Transferable`, `Not Found` or `Unverified`, original `S###` IDs, missing employer facets, and a source-based explanation.
- Independent `adjudicated` review with third reviewer ID whenever verdicts or source citations disagree. Preserve disputes; do not relabel a model failure to make a score look better.

Before opening holdout outcomes, agree on minimum coverage and acceptable unsupported-Found/recall thresholds, provider/cost budget, sample sizes and which human reviewer settles conflicts. The preflight reports sample/department/split counts and disagreements **only**. It does not invoke Ollama/OpenRouter or calculate model accuracy.

Actual full-stack benchmark must separately evaluate (1) JD meaning and omitted obligations, (2) ingestion/role-source coverage, (3) final status/source entailment, (4) score/rank/Why/retry/export. Compare v52 and v53 on identical frozen source packets/date/model/settings under authorized providers; report confusion counts, direct/transfer precision/recall, per-category unsupported Found, avoidable Unverified, attempts, time, tokens, cached tokens, and actual/unknown spend. Keep existing seven and fifteen deterministic supervisor-case runners separate from human-label results.

**No applicant personal data may be sent externally without authorization.** Real provider benchmarks and live deployment remain unqualified.
