# Supervisor Technical Brief

## Goal

Given one job description and multiple CVs, rank candidates against the same frozen requirement set with source-grounded evidence and deterministic scoring.

## Current architecture

```text
JD
↓
YAKE
↓
Qwen JD requirement validation
↓
Python freezes requirement IDs
↓
CV text + all frozen requirements
↓
ONE main Qwen assessment call per normal CV
(large requirement sets batch only for context safety)
↓
Pydantic + Python source-grounded segment evidence/relevance checks
↓
matched / not_matched / uncertain
↓
Python score
↓
Python ranking
```

## Why YAKE

YAKE performs unsupervised candidate keyphrase discovery from the JD. It avoids a hardcoded profession/skill dictionary. Its output is only a candidate pool; Qwen decides which items are actual hiring requirements.

## Why an LLM

The LLM handles language interpretation that exact string rules cannot reliably handle, such as abbreviations and equivalent wording. It is also instructed not to give credit for merely related technologies.

Examples of valid naming equivalence:

- NLP ↔ Natural Language Processing
- Postgres ↔ PostgreSQL
- JS ↔ JavaScript

Examples that must not be treated as equivalent:

- FastAPI ≠ Django
- PostgreSQL ≠ Redis
- Docker ≠ Kubernetes
- AWS ≠ Google Cloud

## Why LangChain

LangChain is used only as a small orchestration layer for `ChatOllama.with_structured_output(...)`. There are no agents, memory systems, vector stores, RAG flows, or LangGraph workflows in the ranker.

## Why Pydantic

Pydantic restricts model output to expected fields and allowed statuses. The CV-assessment output is intentionally small:

```text
requirement_id
status
evidence
matched_term (optional direct alias / OR alternative)
```

## Why the LLM does not score

The LLM only classifies evidence. Python owns every numeric score so the result is reproducible and explainable.

```text
primary_score = matched_required / total_required * 100
```

`uncertain` and `not_matched` receive zero credit in the current implementation.

## Evidence control

For every positive or uncertain classification, the model must quote source-grounded segment evidence exactly from the CV. Python resolves the quote back to a complete source context, checks token boundaries, verifies relevance to the requirement (including only a tiny set of direct aliases and explicit OR alternatives), and applies generic high-confidence negation/learning safeguards. This blocks examples such as Java→JavaScript, SQL→NoSQL, or Docker being "proved" by a Git sentence.

If evidence is missing, non-contextual, or irrelevant, only the failed requirement rows receive one corrective retry. This is a retry of the same assessment task, not a separate verifier.

## Verifier status

A separate semantic verifier is intentionally **not active**. It is reserved for future implementation according to the current supervisor direction.

## Why no embeddings or similarity search

The system already has a finite set of known JD requirements. It directly evaluates each CV against those requirements, so a vector retrieval layer is unnecessary for the current problem.

## Why no transferable-skill scoring

The current ranker answers a simpler question: does the CV support this explicit requirement? Related but different technologies do not earn partial credit.

## Fair comparison

The JD is interpreted once. Python assigns stable IDs such as `R001`, `R002`, and the same frozen set is supplied to every candidate. The JD is not reinterpreted separately for each CV.

## Performance model

For a normal run with N CVs and a normal-sized JD:

```text
1 JD LLM call
+ N main CV assessment calls
```

A CV may trigger one extra corrective call only when its model output has missing or invalid evidence. Requirements are assessed together, not one-by-one. If a user deliberately raises the frozen-requirement limit to a very large value, the requirements are split into conservative batches only to protect the local model context window.

## Current scope limitations / future work

- separate verifier stage
- labelled real-world accuracy benchmark
- specialized numeric years-of-experience rules
- specialized education/certification/license hard gates
- long-document chunking (current build refuses unsafe context overflow rather than silently truncating)
- OCR for scanned/image-only resumes
