# CV Ranker — supervisor demonstration

## What to show (about 5 minutes)

**Before the meeting**

- Use fictional CVs for the demonstration; never add personal resumes, API keys, or results to a release ZIP.
- Confirm the build with `run_runtime_check.cmd`. If using OpenRouter and optional EmbeddingGemma, run `doctor.py --live` to check connectivity. Be mindful of cloud charges.
- Put both `OPENROUTER_MODEL` and `OLLAMA_MODEL` in private `.env`. Choose the assessment provider from the sidebar. For separate provider tests use `doctor.py --provider openrouter --live` and `doctor.py --provider ollama --live`.
- Launch using `run_ui.cmd` and verify the new build label in the sidebar. Streamlit runs locally on `http://localhost:8501`.

**1. Analyze** — Open `01 Analyze`, select the bundled fictional `Applied AI / ML (5 CVs)` sample, or upload a JD and a small set of authorized CVs. Explain that the criteria are derived from the supplied JD, and CV statements are collected as line/segment evidence.

**2. Compare candidates** — Open `02 Rankings & evidence`. Immediately above candidate details is the full leaderboard, sorted highest-to-lowest by required coverage. Point out:

| Display | Meaning |
| --- | --- |
| `Required 8/9` | Eight of nine frozen *required* criteria have a reconciled **Found** result |
| `Preferred 3/7` | Three of seven frozen *preferred* criteria are **Found**; breaks ties in required score |
| `Score 88.9%` | `8 ÷ 9 × 100`, not an embedding similarity or LLM confidence number |
| `Transferable 2` | Two requirements supported by comparable functions, **not** counted as Found |
| `Provisional · review` | An AI check, citation, or other assessment issue needs human review |

These numbers are *illustrative*, not fixed or promised scores for the bundled examples. The actual table reflects the current run and its JD.

**3. Show one definitive record** — Select a candidate below the leaderboard. Expand two or three requirements: a straightforward Found (such as a named Python skill), a Transferable (e.g. similar workflow built in a different framework), and Not Found. Show the final reason, cited CV sections, and highlighted original source text. A self-reported skill is accepted as a stated skill but not independently verified proficiency.

**4. Demonstrate traceability** — In `03 CV source segments`, find a cited segment and show that the full CV-source ledger remains available. In `04 Technical details`, show model diagnostics/earlier assessments separately: they do **not** create a second contradictory user-facing verdict.

**Check explicit experience/education requests** — With the bundled fictional Applied AI JD (TXT, DOCX or PDF), show the **10 Required / 7 Preferred** rows: the 3-year professional experience threshold is its own Required item; Farhan's self-reported 2 years 4 months does not pass it. That particular JD does not request any degree. For a separate JD that explicitly requires a completed bachelor's degree in Computer Science, the system can distinguish a same-field degree (Found), a source-cited related field such as Software Engineering (Transferable after successful semantic judgment, zero point), and an unrelated field (Not Found). Do not claim these results if the degree is absent from the uploaded JD.

**5. Export** — Download the leaderboard CSV and final-decision CSV for a supervisor review meeting. Detailed JSON contains CV text and should be handled as sensitive material.

## Likely supervisor questions

- **Why is the candidate ranked first?** Highest final Found fraction among required criteria; higher preferred Found breaks equal required fractions. Transferable never awards points.
- **What if GCP is in the Skills section, but no project mentions it?** A non-negated affirmative skills-list claim can be Found for an ordinary skill requirement. We separately label whether CV evidence is merely stated or demonstrated in a project.
- **Where are years and education?** Only explicit employer JD requirements join the frozen denominator. The CV's education/work background does not itself become a criterion. If an expected criterion is missing, first inspect the actual uploaded JD and its extracted text; the interface now warns when no numeric-years or degree item survived extraction.
- **What about LangChain-style functionality built without LangChain?** It can be Transferable with cited comparable work. A named-tool denial cannot quietly become a direct match.
- **Why was a requirement Not Found?** The visible explanation and segments show the exact evidence boundary. It means *not established by this CV*, not proof the applicant cannot do it.
- **Can we use this alone for hiring?** No. Candidates must receive human review; the tool does not validate professional claims or settle suitability.

## If anything looks wrong

- Verify the `phase7g-v4-5-env-owned-dual-provider-sidebar-2026-10-26` sidebar build label. Close an old Streamlit server on port 8501 before starting the new version.
- Do not mix source files from prior releases. Re-extract into a new folder and run `run_runtime_check.cmd`.
- If the semantic model is offline, disable optional cross-check and clearly label the run's assessment mode. Missing checks must not be portrayed as proof of missing skills.

