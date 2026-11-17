# Environment and test disposition

- OS: Linux-6.18.57-x86_64-with-glibc2.41
- Python: 3.13.5
- Node: v22.16.0
- npm: 10.9.2
- TypeScript globally: Version 5.8.3

## Installed Python packages
- fastapi: 0.128.2
- starlette: 0.50.0
- pydantic: 2.13.5
- uvicorn: 0.48.0
- httpx: 0.28.1
- pytest: 9.0.2
- python-multipart: 0.0.29
- psutil: 7.2.2
- PyMuPDF: 1.26.7
- streamlit: MISSING
- langchain-core: MISSING
- langchain-ollama: MISSING
- yake: MISSING
- python-dotenv: 1.2.2

## Final broad suite

- 1,624 passed, 21 failed, 10 collection errors.
- 20 test failures and 10 collection errors: missing Streamlit/LangChain packages in this container.
- 1 additional test failure: previous UI expected HTTP 200; modern frontend production assets are unavailable. API deliberately returns HTTP 503 rather than serving stale React 16.
- No assertions were skipped or weakened to achieve those counts.

## Focused acceptance

- 23 passing API/worker tests; one original static UI build test intentionally remains open.
- 64 protected engine tests passed.
- 5 frontend router tests passed.
- 7 frontend TypeScript/TSX implementation files transpiled for syntax with no diagnostics; **not full typechecking**.
- Generated OpenAPI/TypeScript contracts match FastAPI.

## npm blocker

The recorded offline npm command returned ENOTCACHED; exact registry request unavailable: `https://registry.npmjs.org/@eslint%2fjs`. A separate registry query timed out.
Consequently there is no verified lockfile, node_modules, Vite dist, lint, full typecheck or browser screenshots.

## Native OS and live provider

Linux local API-worker start/stop smoke passed. Windows Python 3.11 not executed; Ollama/OpenRouter live testing not executed.

## Repro commands

```text
python -m pytest -q tests/web
python -m pytest -q --continue-on-collection-errors
python -m pytest -q tests/test_v4972_p1_prompt_integration.py tests/test_v4972_p1_conditional_boundaries.py tests/test_v4971_deep_audit.py tests/test_v4970_supervisor_three_verdict_e2e.py
python scripts/generate_web_contract.py --check
cd frontend && npm install --package-lock && npm ci && npm run typecheck && npm run lint && npm run test:route && npm run build
```
