# CV Ranker V4.8 — retrieval-first unified assessment

## Status and isolation

V4.8 is an independent development copy of the supervisor-approved V4.7
release. The original ZIP is not modified. V4.8 changes the route by which CV
evidence reaches the main LLM; it does **not** introduce a new search engine or
change the original scoring and eligibility rules.

## Runtime flow

1. Extract the JD and CVs with the existing document readers.
2. YAKE proposes JD phrases. The existing LLM/Python coverage audit freezes
   one fixed required/preferred JD requirement list.
3. Split each candidate CV into source segments with stable IDs. Retain every
   source segment for the CV source inspection screen and future HR features.
4. Use the **existing** local `EmbeddingGemma-2` encoder, SQLite vector cache,
   cosine retrieval and the original exact-phrase boost to prioritize evidence
   for every frozen JD requirement. No BM25, keyword-search service, reranker,
   vector database or replacement embedding model is introduced.
5. Assemble one evidence dictionary **per model request**. Each retrieved CV
   passage appears once; each JD requirement refers to relevant segment IDs.
   The user prompt contains only prioritized source passages, not the complete
   CV. The full CV is still available to deterministic Python validators and
   to the source-inspection screen.
6. The configured OpenRouter or Ollama LLM returns `found`, `transferable`,
   `not_found` or `uncertain` for each frozen requirement, with 1–3 source IDs
   for favorable/uncertain claims and an explanation for **every** decision.
   Larger JDs may be split into context-safe **groups** of requirements.
7. Reuse the existing source-citation, negation, experience, education,
   qualification, compound-condition, and reviewed-equivalence checks. Python
   overrides unsupported direct credit. Transferable evidence is disclosed for
   human review, but earns **zero Found points**.
8. Build the existing required/preferred counts, ranking and one final evidence
   table. No optional shadow LLM pass and no 1-call-per-requirement final loop.

## Request-volume controls

- One initial structured LLM request per context-safe requirement group,
  typically 1–2 groups per CV. Each group permits at most one **grouped**
  correction if source citations or rows are invalid.
- Built-in transport retries remain bounded by existing `.env`/Settings retry
  configuration. An HTTP 429 cannot quietly turn unverified evidence into
  `Not Found` scores. The candidate is marked failed when a necessary LLM
  batch cannot be validated.
- The Technical details tab reports actual LLM request attempts including
  retries, logical model calls, candidate unified calls, and provider-reported
  token usage (if available). Local embedding work is separate from remote
  cloud LLM requests.
- Source vector embeddings are reused from the approved SQLite cache.

## Not part of V4.8

- No BM25 or other new search implementation.
- No employment-gap calculation, recommendations, or extra CV filtering.
- No 10% education / 10% experience / 80% JD weighting yet. The isolated
  weightage UI prototype remains independent for the future integration phase.
- No inferred or hardcoded education/experience tags absent from the frozen JD.

## Verification before supervisor demonstration

1. On the Windows machine, extract V4.8 into a **new folder** beside V4.7,
   install `requirements.txt` into a separate Python virtual environment,
   configure `.env` locally and start Ollama with its approved embedding model.
2. Run `python -m pytest -q` and `python -m cv_ranker.runtime_check`.
3. Compare six identical resumes on V4.7 and V4.8. Record actual OpenRouter
   HTTP attempts, tokens, runtime, failed candidates, frozen JD requirements,
   source citations, Found/Transferable/Not Found and the final leaderboard.
4. Include adversarial cases: GCP skill-list claim, LangGraph alternatives,
   negated named frameworks, stated Python, education/degree mismatch,
   numeric experience threshold, direct and transferable evidence together,
   and a copied JD/instruction inside a CV.
5. Any changed status needs citation review; a reduced number of calls by
   itself is not evidence of improved accuracy.
