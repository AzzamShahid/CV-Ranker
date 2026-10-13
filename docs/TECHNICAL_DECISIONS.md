# Technical choices and alternatives | Supervisor Q&A

## Why this stack?

| Technology | Role | Reason chosen | Alternatives / why not now |
|---|---|---|---|
| **Python 3.11** | Core application, text processing, scoring | Readable NLP ecosystem, fast prototyping and deterministic rules | Java/Node: possible but additional rewrite with no project advantage |
| **YAKE** | Unsupervised candidate JD phrases | Does not need training corpus or embeddings; extracts useful hints | TF-IDF needs a corpus; KeyBERT uses embeddings (out of scope); regex alone misses phrases |
| **Qwen2.5:3b** | Local JD and CV interpretation | Available and tested on user's Ollama setup; compact local model | Larger model may improve semantics but is slower/heavier; no accuracy claim |
| **Ollama** | Local model serving | Easy setup, no cloud inference credentials | Hosted API adds cost/privacy/external dependency; direct Transformers adds serving complexity |
| **LangChain** | Structured model integration | Central adapter and schema-driven calls | Direct Ollama API is possible; kept because LangChain was already in project |
| **Pydantic** | Structured LLM result contracts | Field validation for IDs, statuses, priorities | Untyped ad-hoc JSON is harder to diagnose |
| **PyMuPDF / python-docx** | Document extraction | Practical PDF and DOCX text processing | OCR is outside current MVP; document conversions add tooling complexity |
| **Streamlit** | Live presentation interface | Fast local upload/display and visible ranked evidence | FastAPI+React requires a larger UI system for an MVP |
| **pytest** | Code regression coverage | Repeatable unit tests and adversarial tests | Manual testing alone cannot protect regressions |

## What is the distinction between YAKE and Qwen?

YAKE proposes **candidate phrases**. Qwen uses the original JD to decide which phrases are actual hiring requirements and their priorities. YAKE hints are never directly promoted to the ranking denominator without source-grounded validation.

## How are requirements verified?

Requirements are grounded against actual source JD sections and evidence text. For explicit lists, missing items can be structurally restored and the run labelled as recovery, not pure LLM validation. This is *source consistency*, not a semantic verifier.

## Why no embeddings or vector database?

The task is one JD versus a modest set of CVs; it requires requirement-wise decisions, not a search index. The supervisor requested avoiding embeddings and similarity search in the MVP.

## What does Python verify?

It checks IDs are valid, cited segments exist, optional exact supporting phrases occur within the source, obvious negation/learning/conflict/title-only cases, and deterministic scores. It does **not** encode a Django/FastAPI or NLP/expanded-term equivalence dictionary. The current LLM can still produce incorrect semantic decisions.

## Why no separate verifier yet?

It was explicitly postponed as future work. Adding it now would complicate the MVP and make it harder to isolate the actual ranking mechanism.

## What would you improve next?

Evaluate source-grounded decisions on a larger, blinded set of varied JDs/CVs, reduce unrelated-evidence false positives, improve abbreviation handling by the model without domain-specific hardcoded mappings, and measure performance and latency. Do not claim high general accuracy from 21 cases.
