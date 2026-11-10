# Phase 7G V4.7 — Supervisor clarity and source-backed transfer (27 October 2026)

## Findings from the latest fictional Sara evidence export

1. **LangChain misclassified Not Found:** The focused model correctly noticed an explicit denial of direct LangChain use but incorrectly treated it as proof that no functionality was transferable. Sara's source passages also document completed Haystack retrieval/tool-routing work and explicitly compare those completed functions to the requirement. A general-purpose, *source-constrained* comparison pass now retains **Transferable** for such cases. It requires a matching functional-comparison passage **and a separate performed-work source with overlapping concrete terms**. It is not based on a LangChain/Haystack hardcoded equivalence table, and it never produces Found/direct credit.
2. **Node.js displayed too much irrelevant evidence:** The focused model cited 32 paragraphs to justify a Not Found decision. The UI now shows up to four representative passages, preferring explicit mentions/denials, skills, experience and project evidence. It labels them as **4 of 32 considered**; the full evidence citations remain in the JSON export and complete raw CV source ledger in tab 03. Node.js stays Not Found when the CV lacks its claim or supported functional transfer.
3. **The UI contradicted its own semantic warning:** A previous final JSON set `Provisional: false` even though semantic verification was incomplete and/or the earlier assessment contained citation notices. Consolidation now propagates these facts into `Notices` and `Provisional`; transferable decisions and audited, flagged possible omissions show **Review recommended**, which the table, row caption, CSV and leaderboard display consistently. Earlier-model errors are correctly labeled as *prior-pass* notices rather than being mistaken for a new final model error.
4. **Time-series:** The user requested that the existing final matching judgment stay as-is. This release does not change forecasting scoring or adjudication rules. Its previously Found result is preserved in the focused regression fixture.

## Test boundaries

- The fictional Sara PDF was processed with the installed extraction pipeline, and the functional bridge found the project comparison and an independent completed-work segment.
- Offline regressions mock LLM responses and use source citations; they do not prove live cloud accuracy or professional qualifications.
- The earlier V4.6 patches for independent local EmbeddingGemma retrieval, corrupted-cache repair, `.env` model selection, and OpenRouter 429 pacing are preserved. A provider's exhausted quota still requires local selection, quota reset, or available cloud credits.
- Scoring remains: **Found required ÷ total required**; preferred Found breaks ties; transferability never earns points. No profession-specific skill taxonomy has been added.

## Supervisor machine verification

Run `run_runtime_check.cmd`, `run_supervisor_demo.cmd`, and `pytest -q` from a clean extraction. The cloud provider and local Ollama model must be healthy in the supervisor environment; safe deterministic offline tests cannot establish their availability.
