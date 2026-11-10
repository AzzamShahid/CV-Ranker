# Phase 6E — Optional per-JD reviewed equivalences

**Build:** `reviewer-approved-equivalence-2026-10-12`  
**Offline validated only:** the reviewer-provided equivalence path is tested with deterministic source examples. There is **no new live Ollama benchmark** for this build.

## Why the change was made

The user's Phase 6D A/B run scored **5/7 without** and **6/7 with** optional exact-initialism recovery on the seven-label `semantic_positive` scenario. `Natural Language Processing` ↔ `NLP` was accepted through an exact written-initialism rule; `Google Cloud` ↔ `GCP` still failed. The independent initial Qwen responses differed between the two executions, so these runs are not a perfectly paired model-output experiment. The second result was marked **mixed** because Python changed a status; it must never be presented as Qwen-only accuracy.

Repeated model responses demonstrated that `GCP` was present in a cited source segment but the model sometimes omitted `matched_term` and later rejected its own proposed match. **GCP is not the strict initials of “Google Cloud”.** A new automatic spelling rule, domain-specific alias dictionary, or further recursive retry was not justified by the evidence.

Phase 6E adds an **explicit, reviewer-owned per-job policy input** for cases where an employer has reviewed and approved an equivalent name. It does *not* generate any approval, infer an alias from the CV, or store a fixed technology synonym catalogue.

## Input contract

The reviewer creates a JSON file such as:

```json
{
  "schema_version": 1,
  "approvals": [
    {
      "requirement": "Google Cloud",
      "alias": "GCP",
      "approved_by": "Name of the authorized HR reviewer",
      "reason": "Reviewed as an accepted name for the same platform in this job"
    }
  ]
}
```

This JSON block is only a **format example**. The system does not assume its truth or create the approval for the user. The user or authorized HR representative must **review and actually authorize** every row. A semantic relationship may be job-specific and should not automatically carry over to other jobs.

The parser is strict: the `requirement` must match a **currently frozen JD requirement by its exact name** (case/spacing ignored), and must be a **short named item** (such as a proper-name platform). Approvals cannot override minimum years, degrees, certifications, licenses, compound eligibility or general task requirements. This prevents a reviewed alias from bypassing the deterministic constraint checks. Unrecognized names, invalid JSON, blank reviewer/reason, duplicate mappings, aliases assigned to multiple different requirements, malformed phrases, unsupported schema versions, or oversized files cause a **fail-closed error** before ranking. The file's SHA-256 hash and complete reviewed entries appear in the exported `RankingReport` JSON for provenance.

## Scoring behavior

1. The existing JD extraction, Qwen assessment, evidence validation, and optional exact-initialism experiment run unchanged.
2. Only an assessment still labelled `not_matched` is eligible for an authorized alias review; prior `matched` and `uncertain` rows remain untouched.
3. Python looks for the **literal approved alias** in appropriate resume evidence (`skills`, `experience`, `projects`, `summary`) with the current tone/instruction/title safeguards.
4. An unambiguously positive mention can be credited `matched` **because the reviewer authorized the equivalence**, never because Python or Qwen autonomously inferred it. Learning or limited exposure remains `uncertain` (zero credit); positive plus negative evidence also becomes `uncertain`.
5. A credited match includes its actual `evidence_ids`, exact `matched_term`, source excerpt, `reviewed_alias_by`, and candidate diagnostic note. The evaluation mode is set to `mixed`, even when Qwen originally rejected the item. The unchanged deterministic coverage formula is used.
6. With **no JSON file**, the feature is completely disabled, so the source package behaves as before.

This is a policy and evidence review mechanism, **not proof that the applicant's self-declared capability is authentic**. It is not a license to declare different related technologies equivalent (such as Django/FastAPI) without a substantive employer decision. It does not justify automated applicant rejection.

## On Windows

Keep the current `.venv` directory when replacing the project source files.

```powershell
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe doctor.py --live
```

For the normal CLI, optionally supply the actual reviewer-owned file:

```powershell
.\.venv\Scripts\python.exe main.py --jd "path\to\job_description.txt" --resumes "path\to\candidate_resumes" --approved-aliases "path\to\hr_approved_equivalences.json" --details
```

For Streamlit, use the new **Optional HR-reviewed equivalences** JSON upload. The generated report captures `approved_aliases`, `approved_aliases_sha256` and any reviewer-backed assessment changes.

**Do not claim a reviewer-approved 7/7 on a seven-item set is Qwen model accuracy.** Count it separately as **human-assisted final ranking coverage**, and report how many requirements were decided using authorized alias declarations. Compare the original `5/7` and experimental `6/7` only in their original scope.

## What remains to be built

- Human verification/approval workflow in a persistent authenticated HR application instead of externally authored JSON.
- Richer typed JD requirements and constraints for qualifications, employment duration, licenses, AND/OR obligations, and eligibility.
- Broader independent datasets spanning several departments, negative acronym collisions and employee/applicant fairness.
- Fully source-offset-grounded evidence, audit logging, retention and user access control.
