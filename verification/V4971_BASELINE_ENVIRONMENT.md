# TextileHR AI · v4.9.71 RC1 · Baseline and environment

Date: 16 November 2026. **Current assessment protocol: 57**. Candidate for offline engineering tests, **not a qualified production release**.

## Authentic source

- Input ZIP: `TextileHR_AI_CV_Ranker_v4.9.70_Three_Verdict_RC1_2026-11-15.zip`
- SHA-256: `4cea91427c1ede8b3d76aee0bcc2454cea300791b6944c37251a750d2005965d` (computed from supplied archive)
- The v4.9.68 **Windows Test Compatibility** artifact with advertised SHA `813f1deb8456d78ea16d52ec1398bdd2f1c9981654a848249f686c560bd24587` was **not available**. Accordingly this branch cannot be certified as an integration of that artifact.
- The input ZIP was extracted to a separate working tree. The source archive remains unmodified.
- Build identity: `phase7g-v4-9-71-assessment-foundation-rc1-2026-11-16`, protocol 57.

## Environment and limitations

- Sandbox: Linux / Python 3.13.5 (not Windows 10 / Python 3.11).
- `pytest`, `pydantic`, `numpy`, and source utilities available. Pinned `streamlit`, `langchain-core`, `langchain-ollama`, and other runtime libraries were not fully installed.
- Attempted package installation failed due DNS/name-resolution failure for the configured package index, not a source-code assertion. Do **not** count missing dependencies as successful validation.
- Native Windows app startup, UI flows, provider network and live-LLM accuracy are **not evaluated**.
- The full suite remains partially blocked; see `V4971_RELEASE_QUALIFICATION.md` and the supplied full test log.

## Source ancestry

Input RC1 protocol 56 → new v4.9.71 RC1 protocol 57, including: durable review result store, bounded retry and scheduler, stronger source checks for Transferable and Not Found, source-aware negative contextual quotes, generic semantic-adjudication workflow condition, and historical test-contract migrations. No fixed candidate/occupation/requirement-ID verdict logic was added.
