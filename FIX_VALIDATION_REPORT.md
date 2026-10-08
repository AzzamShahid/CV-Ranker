# CV Ranker Correctness Fix Validation

## Scope

The architecture was not redesigned. It remains:

```text
JD → YAKE → JD LLM → frozen requirements → CV LLM → Python evidence validation → Python scoring → ranking
```

No verifier, embeddings, vector database, semantic retrieval, transferable-skill scoring, agent system, or LLM-generated percentage was added.

## Implemented fixes

1. Whole-term boundary matching blocks substring false positives such as Java/JavaScript, SQL/NoSQL, C/Communication and Go/Good.
2. CV evidence must resolve to meaningful source context and must be relevant to the target requirement.
3. Isolated model quotes cannot remove surrounding learning/negation meaning.
4. Generic high-confidence negation/learning patterns were expanded without turning Python into the semantic ranker.
5. JD labels may use a small direct-equivalence layer (for example NLP/Natural Language Processing and Postgres/PostgreSQL) while JD evidence remains source-grounded.
6. Direct aliases are deduplicated so they do not inflate the scoring denominator.
7. Explicit OR requirements remain one requirement; either listed option can satisfy it.
8. Invalid JD rows get one targeted correction attempt; valid rows are retained.
9. Candidate evaluation mode is visible and mixed LLM/fallback runs raise a warning.
10. Fallback handles compact lists, inline headings and explicit OR requirements conservatively.
11. Local-model context overflow is rejected before a call; requirement sets above the safe batch size are assessed in batches.
12. Equal primary scores share a rank. Filename ordering is only deterministic display ordering among ties.
13. Regression tests and adversarial probes cover the reproduced defects, including the uploaded Naqvi PDF strong-AI case.

14. If JD LLM grounding becomes empty or catastrophically incomplete against explicit Required/Preferred sections, the run switches visibly to `fallback_structural_after_llm` rather than crashing or scoring against a collapsed denominator.

## Validation performed here

- `python -m pytest -q`: **99 passed, 0 failed**
- `python -m compileall`: passed
- backend deterministic demo: passed
- HR deterministic demo: passed
- fallback trace: passed
- adversarial probe suite: all probes passed
- uploaded Naqvi PDF: extracted successfully and conservative fallback matched 8/9 strong-AI requirements; the missing `AI application development` item is intentionally not inferred from related project wording in fallback mode.

## Target-machine validation still required

This environment does not have the user's local Ollama/Qwen installation. Run on Windows:

```powershell
.\.venv\Scripts\python.exe doctor.py --live
.\run_trace_demo.cmd
.\run_ui.cmd
```

Then test the strong, partial, weak and unrelated JDs with the real CV. The live LLM should provide semantic interpretation; Python still owns evidence trust, scoring and ranking.
