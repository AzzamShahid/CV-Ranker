# TextileHR React/FastAPI preview test evidence

Actual runs in the engineering container, 16 November 2026:

| Test gate | Result | Record |
|---|---|---|
| Backend real FastAPI+worker integration | **14 passed** | `web_api_worker_pytest.log` |
| Existing full Python suite (including new tests) | **1,615 passed; 20 failed; 10 collection errors** | `broad_pytest.log` |
| Failed tests / collection | All documented missing `streamlit`, `langchain_core`, or `langchain_ollama` | `broad_pytest.log` |
| TypeScript offline build | Passed | `frontend_build_checks.txt` |
| JavaScript syntax | Passed | `frontend_build_checks.txt` |
| OpenAPI/TypeScript schema drift | Passed | `frontend_build_checks.txt` |
| Source package strict hash | After final archive rebuild; external extracted-package verification required | Report |
| Real Playwright browser localhost navigation | **Blocked by administrator** | `docs/migration/BRANDING_AND_VISUAL_CHECKLIST.md` |
| Modern npm/Vite/Tailwind/shadcn build | **Not run** | Missing package registry / lockfile |
| Native Windows / Python 3.11 | **Not run** | Linux/Python 3.13 environment |
| Actual Ollama/OpenRouter model quality | **Not run** | No authorized live-provider evaluation |

The 14 integration tests use fictional CVs and the actual engine in non-generating fallback mode. They demonstrate service state transitions, not a live-model accuracy gain or comprehensive UI parity.
