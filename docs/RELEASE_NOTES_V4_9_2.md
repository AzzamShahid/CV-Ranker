# Phase 7G V4.9.2 — consolidated evidence-contract release candidate

**Build:** `phase7g-v4-9-2-consolidated-evidence-contract-2026-10-28`  
**Protocol:** `segment_ids_semantic_llm`, version 10

## Why this build exists

Earlier releases repeatedly added literal-source and named-term gates to protect against fabricated citation text. Those checks sometimes rejected valid *implicit* performed work because the CV described an action without repeating the exact JD name. The resulting sequence was repeated corrective calls, missing final IDs, and scores withheld even when real evidence existed. Conversely, blindly removing the source-term guard could award unrelated completed work as a direct match. Neither extreme is acceptable.

## Consolidated contracts

1. **Freeze requirements, preserve every ID.** All ordinary assessment responses must include exactly one structured property per frozen JD ID. A result missing an ID remains unverified; it must never become an implicit Not Found or quietly disappear from a candidate's denominator.
2. **Original CV evidence only.** An `evidence_id` is checked against an actual permitted CV segment. A quoted alias/term must occur in the cited source on the ordinary initial/correction path. Source IDs by themselves are *not* proof of competence.
3. **One separate-prompt final semantic adjudication if technically necessary.** For remaining unverified IDs, one additional grouped call (to the **same configured model**, not a second independent provider) uses a different response schema: `decision`, `relation`, `evidence_ids`, an *exact CV proof excerpt*, and a reason. The relationship must be direct/entailed for Found, shared function for Transferable, absent for Not Found, or uncertain. The excerpt must appear in a cited allowed source. It can accept a legitimately entailed competency without imposing JD-literal casing or a fabricated alias. Invalid final claims remain unverified and the score is withheld.
4. **Qualifying scope matters.** A listed skill can be accepted as a *self-reported skill* when the JD asks for a skill; a copied job requirement or the same wording in an isolated skills list does not automatically establish completed duties, numeric professional tenure, or completed credentials. This rule derives from the frozen requirement type, not from a hardcoded skill or occupation list.
5. **Negation is scoped to the claim.** A negative statement about unrelated working conditions does not cancel a positive tenure or credential claim. Explicit denials of the relevant credential/work remain denials. PDF-wrapped degree-and-field phrases can be joined only across adjacent original source lines from the same ledger segment.
6. **Status, score and UI remain aligned.** Found counts toward the required score. Preferred Found breaks ties. Transferable earns zero match points and asks for human review. Not Found is distinguished from *Unverified*. If even one required/overall frozen ID remains technically unverified, a candidate's score/rank is withheld, but all validated Found/Transferable/Not Found rows and partial counts remain visible in the detailed UI and leaderboard.
7. **Bounded cloud spending.** One grouped model assessment per context-sized batch; at most one correction per failed group; at most one *additional* independent grouped verification call for technically unresolved items per CV. OpenRouter's retries and all pipeline stages share a hard HTTP ceiling: `OPENROUTER_MAX_REQUESTS_PER_RUN=64` by default. The cap is checked **before** sending CV data. No optional semantic shadow, no per-requirement retry loop.

## Regressions explicitly tested

- Same implicit evidence under differently capitalized JD wording; source-attested quoted action is required for final adjudication.
- Invented evidence phrases, irrelevant work, technical source gaps and missing IDs must not manufacture Found.
- Work-history and credential positives with separate negative clauses; actual denied credentials.
- Skills-list versus completed-duty and experience criteria; adjacent physical PDF wraps.
- The UI does not erase an otherwise verified candidate's rows when a single criterion remains unverified.
- Provider request ceiling enforcement; at most one additional independent grouped call in a synthetic full-path failure.
- The existing cross-domain, scoring, ranking, source ledger and report-export contracts from the rest of the test suite remain part of the release gate.

## Offline release measurements

`python -m evaluation.evaluate_industrial --mode fallback` was executed over **8 synthetic departments, 40 candidates and 200 manually labeled requirement decisions**: 197/200 statuses agreed (98.50%); matched precision 100.00%, recall 97.48% (3 false-negative matches, 0 false-positive matches); 98.75% macro pairwise ranking agreement and nDCG@3 100.00%. These are **fallback-only** numbers. They are not Gemini accuracy and do not establish production performance. The untouched synthetic labels and case inputs remain in `evaluation/industrial_dataset/` for reproduction.

## Supervisor verification / known limits

From the top-level Windows project folder:

```powershell
.venv\Scripts\Activate.ps1
.\run_runtime_check.cmd
.\run_tests.cmd
.\.venv\Scripts\python.exe doctor.py --live --provider openrouter
```

Then run the same JD and varied CVs in the Streamlit UI, confirm *all* candidate rows are fully assessed, and manually review the evidence citations alongside scoring. The doctor live contract tests a **synthetic** flow, not production recall or ranking accuracy. Automated tests predominantly use synthetic, deterministic model responses. A live multi-CV benchmark with real configured provider credentials and local EmbeddingGemma is still required before treating this research prototype as production-ready.

**No domain-specific answer list or candidate-specific score override is encoded.** The frozen JD and candidate source passages remain the inputs. The semantic verification is a fallible model judgment, not independent proof that every inferred competency is true. Credentials and years are CV claims, not externally authenticated facts. Human review is required for consequential hiring decisions.
