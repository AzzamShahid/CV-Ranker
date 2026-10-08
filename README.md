# Explainable CV Ranking Engine

A lightweight local CV/resume ranker built around the supervisor-approved scope:

```text
Job Description
      ↓
YAKE candidate phrases
      ↓
LangChain + Qwen2.5:3b JD validation
      ↓
Frozen JD requirements
      ↓
Resume text extraction
      ↓
One Qwen assessment call per normal CV
(large requirement sets are batched only for context safety)
      ↓
Pydantic + Python source-grounded segment evidence/relevance checks
      ↓
Deterministic Python scoring
      ↓
Candidate ranking
```

## What is intentionally not in the current implementation

- No embeddings
- No cosine similarity
- No vector database or semantic retrieval
- No transferable-skill scoring
- No LLM-generated percentage
- No active verifier stage

A separate verifier is future work, as directed by the supervisor.

## Component responsibilities

### YAKE
Extracts candidate keywords/keyphrases from the JD. YAKE does not decide the final requirement set and does not rank candidates.

### Qwen2.5:3b through Ollama + LangChain
Used for two semantic tasks:

1. Validate actual hiring requirements from the JD using the original JD plus YAKE hints.
2. Evaluate one resume against all frozen requirements in a single main LLM call.

### Pydantic
Restricts model output to a small structured schema.

### Python
Handles document parsing, frozen IDs, source-evidence checks, obvious negation/learning safeguards, scoring, sorting, error handling, and reporting.

## CV assessment statuses

- `matched` — clear supporting evidence
- `not_matched` — no supporting evidence or explicit lack
- `uncertain` — learning, limited exposure, indirect involvement, conflict, or weak evidence

`uncertain` receives no score in the current MVP.

## Evidence rule

Every `matched` or `uncertain` result must include contextual source evidence. Python resolves that quote back to a complete source line/sentence, checks whole-term boundaries, verifies that it actually supports the requirement (or a small direct alias / explicit OR alternative), and applies high-confidence negation/learning safeguards. Isolated words cannot strip away surrounding meaning. If positive evidence is invalid or missing, only those failed rows receive one corrective LLM retry. If valid evidence is still unavailable, no credit is awarded.

## Scoring

When explicit required requirements exist:

```text
primary_score = matched_required / total_required * 100
```

Preferred coverage is shown separately and does not inflate the primary score.

If no required requirements exist, the current deterministic fallback basis is unknown-priority requirements, then preferred-only requirements.

## UI limits

The Streamlit UI allows:

- YAKE candidate phrases: 10–200, default 40
- Maximum frozen requirements: 5–100, default 30

The higher ranges are available for larger JDs, while normal runs should keep sensible defaults for speed on low-spec hardware. The local-model call refuses prompts that would exceed the configured context window instead of allowing silent truncation; large requirement sets are batched conservatively.

## Run on Windows

The `.cmd` launchers intentionally use the project virtual environment directly.

```bat
run_ui.cmd
run_tests.cmd
run_trace_demo.cmd
run_backend_demo.cmd
run_hr_demo.cmd
```

Before a live LLM demo:

```powershell
.\.venv\Scripts\python.exe doctor.py --live
```

The UI opens at:

```text
http://localhost:8501
```

## Direct CLI example

```powershell
.\.venv\Scripts\python.exe main.py --jd sample_data/backend_jd.txt --resumes sample_data/backend_resumes --details
```

## Internal trace

```powershell
.\run_trace_demo.cmd
```

The trace shows document extraction, YAKE phrases, frozen requirements, the CV assessment, source-grounded segment evidence validation, and deterministic scoring. Equal primary scores share a rank; filename ordering is display-only for tied scores.
