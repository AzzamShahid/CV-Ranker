# Phase 7G V4 — One Final Evidence-Based Decision Table

**Baseline:** Original Phase 7G V4 with source checkpoints and the complete CV source ledger. This release is **not** derived from the rejected V5 design.

## The user-facing result

The **Rankings & evidence** tab contains exactly one decision matrix for the selected CV. Each original frozen JD requirement appears once, in JD order, with:

1. Requirement ID and original JD name.
2. Required/Preferred priority.
3. **One final decision:** Matched, Transferable, Not evidenced, or Needs review.
4. CV evidence level: skills-list claim, described work/project, comparable function, or not established.
5. Every unique cited CV segment ID and a concise final explanation.

Above the matrix, final **Required matched X/Y** and **Preferred matched X/Y** replace misleading primary-only percentages. Transferable work is listed but is **not counted** as the named tool/requirement being matched.

Expand a requirement to inspect the **original extracted text of every recorded source checkpoint**, numbered individually. Each checkpoint shows its CV section, whether V4 and/or semantic AI cited it, exact original wording, and a separate explanation of why it was considered. Literal source cross-checks—including explicit denials, learning-only claims, and unaccepted citations—are never silently discarded. The existing **CV source segments** tab still provides all parsed CV segments and original physical lines, even those not connected to a requirement.

The raw V4 report and semantic relationship report remain downloadable under **Technical details** for audit. They no longer appear as two contradictory user-facing assessment tables. Existing V4 scoring data is not overwritten; this is a separately persisted unified result.

## How conflicting labels are resolved

- **Affirmative named skill in CV:** an ordinary skill requirement can be reported as Matched even when the CV has not identified a specific project where it used that skill. The evidence level states *Stated in skills*, not *Demonstrated in work*. For example, GCP Cloud Run / BigQuery, cited by V4 as Google Cloud evidence, remains a CV-reported Google Cloud match even if another model mistakenly says that the name is not evidenced.
- **Performed equivalent function but not named tool:** marked **Transferable**, with the exact functional evidence and distinction. A denial such as “without LangChain” cannot become an affirmative LangChain claim.
- **V4 says Not matched, semantic AI says Direct:** a **focused Gemini/OpenRouter verification** receives both previous rationales and their exact source IDs. It can award Matched only with original CV segment IDs and concrete reasons. If the provider is unavailable or cites unsupported IDs, the disputed requirement stays **Needs review** instead of being silently counted.
- **Both analyses agree but rely on implicit functional equivalence:** the focused check can still re-examine the interpretation. For example, demand-anomaly screening and time-series forecasting should not automatically be treated as the same task.
- **No evidence:** label is **Not evidenced**, not “candidate does not know this skill.” No model is asked to certify real-world competency from a CV.
- **Professional years, degrees, licenses, AND/OR expressions:** the judge is told to enforce actual JD qualifiers, not substitute related buzzwords.

Focused verification uses the same configured model (such as `google/gemini-2.5-flash-lite`) and incurs additional model calls only for source-backed disputed or implicit requirements. If a source-ledger or citation validation fails, it cannot automatically award a match. Uncontested positive evidence does not receive a repetitive human-review badge. Hiring decisions still require appropriate employer oversight.

## Files changed / added

- `cv_ranker/ui/final_decisions.py` — audit-safe reconciliation, per-segment reasons, optional focused adjudication, final numeric counts.
- `cv_ranker/ui/dashboard.py` — single user-facing matrix, source checkpoint expanders, final CSV/JSON exports, original technical audit exports.
- `cv_ranker/text_utils.py` — fixes false positive on a denial such as “built X without LangChain.”
- `cv_ranker/build_info.py`, `cv_ranker/build_manifest.json` — distinct integrity-tracked V4-derived build.
- `tests/test_phase7g_v4_unified_final_decisions.py` — targeted regression suite for the reported conflicts and evidence preservation.
- Existing UI expectation tests updated for one final table.

## Run the new build on Windows

Extract this ZIP to a **new folder** and copy in only your private `.env` (not an old output/cache folder).

```powershell
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q
.\run_ui.cmd
```

Upload the same single Sara CV and applied AI JD. Keep **AI-assisted assessment** and **Include AI capability cross-check** enabled, then inspect **Rankings & evidence** and **CV source segments**. Download **final evidence (JSON)** to preserve every checkpoint. Previously exported V4 files are old analyses and will not contain this new final result.

**Verification boundary:** automated tests exercise fake/adversarial source citations and fake focused Gemini responses, so their counts prove the code path, not the real model's predictive accuracy. Real Gemini behavior, hosted API availability, PDF extraction on the user's Windows machine, and the interactive visual layout must be retested in that environment. The original primary ranking remains available for forensic comparison, but final required/preferred counters are derived from the reconciled decisions shown to the user.
