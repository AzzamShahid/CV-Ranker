# Organized project structure and boundaries

The top-level folder deliberately has only the main entry points and setup files. Historical technical milestones from the root folder were collected in `docs/checkpoints/`. Historical detailed notes already under `docs/` remain available so old references and the technical history are preserved.

```text
CV Ranker/
├── README.md                      quick start + scope
├── .env.example                   safe configuration template
├── .gitignore
├── .streamlit/config.toml
├── app.py                         minimal Streamlit entry point
├── main.py                        command-line ranking interface
├── doctor.py                      local / live diagnostics
├── run_ui.cmd                     UI launcher
├── run_supervisor_demo.cmd        supervised live launch
├── run_runtime_check.cmd         source integrity check
├── requirements.txt
├── cv_ranker/
│   ├── ui/dashboard.py            supervisor UI, separate from core
│   ├── ui_support.py              export and upload utilities
│   ├── semantic/                  shadow embedding + proposal work
│   ├── documents.py / segments.py / jd.py
│   ├── assessor.py / scoring.py / pipeline.py
│   └── build_manifest.json        immutable build hashes
├── sample_data/                   synthetic test JDs and CVs
├── scripts/                       demonstrations and validation
├── evaluation/                    baseline comparisons
├── tests/                         automated regression tests
├── docs/                          supervisor guides + architecture
│   └── checkpoints/               historical 7G release notes
└── tools/                         developer utilities
```

## Non-goals for this release

- No change to deterministic scoring, JD requirement extraction contract, candidate evidence admissibility, or fixed requirement denominator.
- No automatic promotion of semantic transferability proposals to matches.
- No embedding or vector-index modifications.
- No platform rewrite. Windows `.cmd` launchers remain functional and root-relative.

## What to present

`README.md`, `docs/SUPERVISOR_UI_GUIDE.md`, `docs/ARCHITECTURE.md`, `app.py` and `cv_ranker/ui/dashboard.py`. For technical deep dives show the original `cv_ranker/` modules and tests.

Use a separate extracted directory for this build. `.env`, `.venv`, `outputs/`, and real CVs are excluded from the release ZIP.


- `cv_ranker/ui/semantic_workflow.py` — same-run, read-only semantic-review orchestration; accesses temporary source files before cleanup.
- `docs/ONE_CLICK_TRANSFERABILITY.md` — supervisor walkthrough, limits, privacy and rollback.
