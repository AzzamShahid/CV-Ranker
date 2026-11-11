# Supervisor Edition v4.9.55 — Calibrated uncertainty and editable local source

11 November 2026 · assessment protocol 41

## What changed

- **More decisive, evidence-grounded prompts.** The primary assessment, independent adjudication and correction prompts now expressly distinguish exact claims, completed work, skills-list claims, substantive team involvement, related completed work, unsupported claims, and genuinely conflicting evidence. They decide **Found** for a supported exact condition, **Transferable** for supported related completed work, **Not Found** for unsupported claims, and reserve **Uncertain** for material contradictions or unresolved scope. They do not demand an external certificate to corroborate every truthful-looking but self-reported CV statement, nor do they introduce unrequested years, sole ownership or commercial deployment.
- **Dates, degrees, exposure and participation.** A work history can establish years through dated, relevant full-time employment even without a literal “N years” phrase. Actual completion and accepted academic field/level govern education matching; a completed *related* degree can transfer without being treated as the named degree. A demonstrable team contribution can fulfill a participation requirement without proving independent ownership.
- **Normalize internally contradictory model responses.** A model that answers `uncertain` while clearly classifying its evidence as `absent` is interpreted as **Not Found**. An `uncertain` response with `overlap` and a real source citation is a **Transferable proposal** subject to validation. A supposed direct match must still pass positive evidence and constraint checks; no status is silently promoted to **Found** by a confidence guess.
- **Useful partial results despite technical incomplete assessments.** For interrupted candidates, the UI displays the verified score floor, the maximum possible score if every unresolved criterion later proves Found, and a separate provisional comparison ordered by verified credit. Unverified work earns **zero confirmed points**. An evidence range or provisional review order is not a certified final score, rank, or assertion of absence.
- **Source files are editable in local mode.** The normal loopback-only `CVR_ACCESS_MODE=local` skips release-file hash verification, preventing a harmless local source edit from aborting the UI. Set `CVR_STRICT_SOURCE_HASHES=1` to enforce the manifest locally. All remotely accessible modes retain strict source-hash and build-identity checks. Schema/runtime compatibility checks remain active in both modes.

## Important reliability boundary

The system must not turn a model/API outage, missing CV passage, or genuinely contradictory evidence into invented Found or Not Found decisions. When a requirement is technically unverified, validated decisions are still visible and the provisional score range allows reviewer progress; final ranked scores remain withheld until that requirement can be assessed. This separation prevents false positives and false negatives in consequential HR decisions.

The model remains a decision-support tool: all judgments are based on submitted CV claims and source passages, not independent employer verification. No finite prompt guarantees perfect matching for every future CV and JD.

## Verification

- Tests include refusal to promote a contradictory `uncertain/direct` row, conservative recognition of source-backed transferable evidence, truthful provisional score bounds, and local-vs-remote source-edit behavior.
- Use `python -m pytest -q`, `python -m cv_ranker.runtime_check`, and `python -m scripts.production_preflight` in the extracted source release.
