# TextileHR AI React/FastAPI migration — 0.2.1 source checkpoint

**16 November 2026 · assessment protocol 58 unchanged.** Source identity and test evidence are recorded in `COMPLETION_V3.md` and `verification/completion_v3`.

Compared with the verified supplied completion checkpoint, this release adds durable submission-key recovery across lost responses and tabs; deleted-intent tombstones in SQLite schema 4; case-specific unreadable-input continuation; persistence of received candidate results during cooperative cancellation; SSE observation sequencing/coalescing/terminal cleanup; explicit typed candidate checkpoints and JD source details; canonical weighted score in candidate view; and five candidate-batch size tests. New Node intent/observation tests and API/worker tests are included.

All 61 original `cv_ranker/` Python files match the supplied checkpoint, and the Streamlit fallback remains available. No prompts, three-verdict policy or scoring rules have been changed.

**Not a production release:** full modern React/npm dependencies, authentic lockfile, Vite built assets, shadcn integration, browser QA and Windows/provider qualification remain unfinished. Focused review, operator semantic shadow and automatic retention need further work. See the authoritative 56-row `PARITY_REGISTER.csv`.
