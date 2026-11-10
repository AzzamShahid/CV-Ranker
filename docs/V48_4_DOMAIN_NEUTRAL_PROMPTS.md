# V4.8.4 — Domain-neutral model instructions

27 October 2026. Separate version; the approved V4.7 and earlier V4.8 ZIPs
remain unchanged.

## Scope

The V4.8.3 prompts explained some matching and transferability decisions with
named technology or industry examples. Even when intended as illustrations,
such examples can prime a model toward one department. V4.8.4 removes named
skill/technology examples from every literal runtime prompt in these modules:

- `cv_ranker/unified.py`: primary grouped CV judgment and its targeted
  one-time correction instructions.
- `cv_ranker/jd.py`: original frozen-JD extraction and correction prompts.
- `cv_ranker/assessor.py`: retained legacy assessment/correction prompts.
- `cv_ranker/semantic/transferability.py`: retained capability-review prompts.
- `cv_ranker/semantic/decomposition.py` and `cv_ranker/ui/final_decisions.py`:
  inspected for consistency; the former was already domain-neutral and the
  latter now uses generic capability/entailment wording.

## Invariant decisions

1. The uploaded JD, not the prompt, determines required and preferred criteria.
2. Found requires a positive listed ordinary skill or actually completed work
   logically entailing the exact employer-requested task, subject to specific
   experience and qualification constraints.
3. Transferable requires **independently cited performed work** with genuine
   functional overlap but insufficient direct evidence; it does not score a point.
4. A denial cannot establish positive use of the named item. A separate
   completed action may still support functional transferability.
5. Similarity, preparation, diagnostic adjacency, or the same general category
   cannot substitute for the exact JD output/activity. A related completed
   activity may merit Transferable rather than being discarded.
6. Illustrative examples in a broad non-numeric experience JD do not
   automatically become mandatory AND requirements. Explicit conjunctions,
   numeric years, degree/field/completion and licensing remain strictly checked.
7. Segment IDs, original CV text, citations, rationale, review flags and final
   scores remain audited by Python, not model-generated scores.

## Performance and architecture

- The main unified prompt decreased from about 376 words to about 344 words.
- **No BM25, hardcoded skill-to-skill dictionary, lexical-search stage, new
  reranker, optional shadow pass, or per-requirement model call was added.**
- Existing EmbeddingGemma-2 retrieval still prepares one deduplicated evidence
  set for each grouped LLM request; a maximum of one grouped correction remains.
- General grammatical/action verb patterns in Python are validation guards,
  not a catalogue of professions, required skills, equivalents, or scores.
- The V4.8.3 production-experience, time-series-related work, transferability,
  and JSON audit fixes remain. Examples occur only in non-executed regression
  fixtures and historical documentation, not in runtime model prompts.

## Verify on Windows

```powershell
.\run_tests.cmd
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe doctor.py --live
.\run_ui.cmd
```

Run the same fictional CV benchmark and at least one CV/JD from another
department. Confirm that judgments cite actual work, that no unrelated skill
is promoted by superficial similarity, and that actual API request counts stay
within the configured budget. This package was not tested live against the
configured cloud model in the isolated build environment.
