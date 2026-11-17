# CV Ranker Supervisor Edition v4.9.59 — evidence access and cloud/recovery budgeting

**Date:** 12 November 2026. **Build:** `phase7g-v4-9-59-evidence-recovery-m3-m5-partial-2026-11-12`. **Assessment protocol:** 45 (v44 historical reports remain historical).

**Status:** **PARTIAL M3/M4/M5 reliability release**, not completion of the Unified Master Remediation Plan, and **not a claim that technical Unverified is eliminated**.

## Changes to executable assessment code

1. **Reviewable general JD duty cues** — common nominalized work activities (e.g., monitoring, scheduling, documentation, coordination, interpretation) are no longer automatically `other` merely because the employer uses a noun instead of a sentence-initial verb. These are **occupation-neutral linguistic hints**, not hardcoded technologies, departments, CV decisions, or evidence. The inferred type stays `requires_review=True`. Explicit exposure/knowledge remains a skill cue; qualitative “experience reducing ...” is recognized as experience.
2. **Type-independent work recall** — work-like `other` criteria now receive the original-CV completed-duty retrieval path, and source-grounded, explicitly related negative rows become eligible for one bounded independent semantic review. A retrieved work passage is never a direct Found/Transferable decision. Unrelated sources do not trigger this special opportunity.
3. **Provider-isolated context limits** — OpenRouter now has its own conservative application-level `OPENROUTER_CONTEXT_TOKENS=32768` and `OPENROUTER_OUTPUT_TOKENS=4096` defaults. These are **configurable operator limits, not provider maximum specifications**. Cloud preflight, API `max_tokens`, response truncation messages and assessment batch sizes use cloud settings, not the unrelated `ollama_num_ctx` and `ollama_num_predict`. A larger allowance does not change the hard HTTP attempt cap and does not require sending the entire CV.
4. **First productive source correction** — if source validation specifically says “cited segment(s) contained no qualifying capability evidence,” the grouped correction consults the **full original source ledger** for another JD-relevant completed-work or explicit-skill lead. It puts new source IDs first. If there is no new qualifying lead, it **skips an identical evidence-only correction** and leaves the existing independently validated review route available. Ordinary malformed JSON, missing IDs and citation-format errors retain their separate bounded repair policy.
5. **Regression coverage** — 11 new provider/source/type tests plus updated pre-existing tests to enforce the changed cloud-budget and non-repeated-repair contracts. No paid model calls or applicant-specific hardcoding introduced.

## Reproducible fixture observations (not universal model accuracy)

- Reconstructed 18-row weaving JD, initial v43 baseline from audit: **14** `other` types.
- On this partial release with generic work-noun cues: **1** `other` row remains, appropriately needing human review of mixed domain concepts. `complex` operator classification is **unchanged** and is not represented as solved in M3; v44 finalization safeguards remain.
- Offline dependency-independent suite: **1,297 passed, 22 deselected**, 10 other modules inaccessible at collection due to missing Streamlit/LangChain packages. Full Windows suite and live-model performance **not verified** in this environment.
- All modified Python files parse, runtime import passes, and strict source hash verification is performed on the packaged ZIP. Any actual installation must rerun the full suite with project dependencies.

## Still unfinished / important safeguards

- True all-JD semantic typing, source coverage and reviewed AND/OR trees (M3) are **not yet fully implemented**. `complex` can still occur for naturally descriptive and/or phrasing.
- Full facet-aware semantic retrieval, provider-native tokenization/usage/cost metering, and fully failure-aware resume state machine (M4/M5) remain open.
- No code can guarantee that every CV requirement produces a reliable substantive verdict. Invalid source, unavailable model, malformed response, scanned PDF or irreducible ambiguity MUST remain **technical Unverified** or **JD review needed**, **not secretly Not Found**. The supervisor sees provisional rank/score where incomplete.
- Real CV 4 R015 and CV 5 R006–R010/R013 need their exact original source ledger and cloud responses for candidate-level verification. No assumed verdicts.
- Existing Found-only weighted points; Transferable remains visible but zero by default. No source-ID, negation, numeric tenure, degree, account security or API ceiling safeguards relaxed.
- Separate Windows v4.9.58 installation remains a rollback. Run fresh assessment for protocol 45; old v44/v43 data cannot be relabeled as new.

## Windows verification

Extract into a **different directory**, configure `.env` privately, install the requirements into Python 3.11 venv, and run:

```powershell
.\run_runtime_check.cmd
.\run_tests.cmd
.\run_ui.cmd
```

Use the identical fictional/test JD and CVs to compare decisions; keep approval/weights constant. Log any remaining `Unverified` with source IDs and Execution details. The restart is required because Python module imports and cache context are versioned.
