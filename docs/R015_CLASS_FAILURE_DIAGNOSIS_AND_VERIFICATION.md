# R015-class named-alternative failure: diagnosis and verification

## What the failing message meant

The employer's requirement: “Use of ERP or manufacturing execution systems (MES) for weaving production reporting.” Its logical choice is **ERP OR MES**, not ERP AND MES. In v4.9.59 the mandatory-name verifier independently demanded every uppercase JD token in a long requirement and rejected even an original positive statement of ERP work because MES was absent (and vice versa). A second source-repair defect compared new leads to the **entire retrieval shortlist**, rather than the specific invalid model citation, so a useful ERP passage already on the shortlist could be skipped as “no new evidence” while the LLM kept citing the wrong passage.

These are engine-level defects and are not specific to weaving, R015, or any hardcoded product mapping. The user's actual CV6/CV7/CV8 S011 passage content was not available in this build and **no actual person's qualification status has been inferred**.

## How v4.9.60 behaves

1. Validated original source: “Used ERP dashboards for weaving production reporting.” The named-condition check accepts the **ERP alternative**, with no compulsory MES mention. Other source/capability/scope checks still apply.
2. Validated original source: “Used MES dashboards for weaving production reporting.” The named-condition check accepts **MES**, without compulsory ERP mention.
3. Validated original source: “Used manufacturing execution systems for weaving reports.” The checker accepts the source-worded acronym expansion as a lexical clue, while the model verifies semantic identity.
4. “Prepared weaving reports manually, without ERP or MES.” Both names are negated. This is not direct named-system evidence, though the completed reporting duty may be relevant to a separately supported Transferable conclusion.
5. “Skills: ERP; looms; reporting.” This lists ERP but does **not** by itself prove completed use of ERP **for weaving production reporting**. Source validation respects the JD's performed-duty modality.
6. “Use ERP AND MES for reporting” still requires both alternatives; it is not made into an OR.
7. When an invalid model answer cited S011 but a different S015 contained a directly relevant named source, a bounded corrective model request now prioritizes S015 even if S015 was already among the earlier broad retrieval hits. The source itself earns no credit until the full original-source model assessment validates the requested action and scope.
8. A successful bounded review can return **Found** (exact work), **Transferable** (completed related work with missing named condition; zero points), or **Not Found** (no direct or meaningful related evidence). Permanent provider/JSON failures remain technical **Unverified**, never silently reclassified.

## Reproduction evidence

- Source reproductions against v45: ERP-only, MES-only and full-name MES sources were rejected with the other alternative “missing”.
- v46 regression file: `tests/test_v4960_named_alternatives_and_recovery.py` covers named-OR, explicit-AND, acronym expansion, shared negation, source repair and controlled full inference/compound/score pathways.
- Offline dependency-independent suite: **1,324 passed, 22 deselected**. **10 collection modules excluded** because the container lacks Streamlit; another 22 individual runtime/provider/UI tests were deselected due to Streamlit/LangChain/Ollama dependencies. The full Windows and live-provider suites were not run here.
- `CVR_ACCESS_MODE=oidc python -m cv_ranker.runtime_check` returned `SOURCE_INTEGRITY=strict_verified` after manifest rebuild. This only tests code-file integrity, **not** remote deployment security.

## On your Windows machine: exact next check

1. Extract the v4.9.60 ZIP to a new folder. Do not overwrite v4.9.59 or your old applicant recovery ZIPs. Copy private `.env` settings, not stored candidate caches.
2. Install pinned dependencies in the new venv; run `run_runtime_check.cmd`, then `run_tests.cmd`, then `run_ui.cmd`.
3. Start a fresh assessment: upload the same JD/CVs, approve the frozen JD and use the selected cloud/local model. **Do not resume a v45 result as a v46 reassessment.**
4. For each formerly failed CV R015, inspect **model-cited**, **validator-accepted**, **validator-rejected** source IDs, and whether an ERP or MES source actually describes completed weaving production reporting. Retrieved leads such as S015 are only candidates for evaluation.
5. If one remains Unverified, save its run details (with personal data/API keys redacted). Distinguish missing source, invalid citation, JSON truncation, model outage, and semantic mismatch. Never award points solely to suppress a technical warning.

**Known scope limit:** This milestone fixes the deterministic mandatory-name OR defect and its named-source correction path. It does not establish that all semantic misjudgments, unusual JDs, or all model-response failures are resolved. Full cross-domain, held-out, real-provider benchmarking and broader recovery work remain in the master plan.
