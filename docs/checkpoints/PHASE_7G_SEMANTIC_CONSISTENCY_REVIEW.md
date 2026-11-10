# Phase 7G: source-grounded relationship consistency — read-only checkpoint

**Build:** `phase7g-relationship-consistency-review-2026-10-19`

This checkpoint addresses a defect seen only after live local Qwen output became structurally complete: Qwen sometimes calls exactly demonstrated technologies or functions *transferable* merely because they were used at a previous company/project. **Different employment contexts do not by themselves imply skill transferability.**

## Audit of the user's October 19 live JSON (synthetic sample CVs)

- Regression suite before this checkpoint: 591 passing.
- Structural completion: four out of four candidates; 48 of 48 requirement proposals generated with zero execution warnings.
- Retrieval: 242 stored hits, 52 lexical exact-hit flags, none attributable to an unrelated frozen requirement (checked case-insensitively with token boundaries).
- Provisional positive classifications were often misleading: 21 **review flags**, of which 19 indicate possible direct evidence mislabeled as transferable, one indicates transfer based only on a skills-list label, and one indicates the named skill itself appears only in a skills list while different functional work is cited.
- All original primary percentages/ranking and all original direct-vs-preferred obligations remain unchanged.

These are **heuristic consistency flags, not 21 proven model errors**. They are not ground-truth assessment labels, credential checks, or independent semantic verification. A generic language-model prompt is not independent review. For example, a CV merely listing FastAPI does not establish that the person has developed production FastAPI services.

## Changes

1. Clarify compact Qwen prompt: *direct* means the requested function/tool itself is demonstrated; *transferable* means **different** tools or techniques demonstrate similar functionality. Moving between industries or employers alone does not make a direct match transferable.
2. Add `cv_ranker/semantic/relationship_consistency.py`. It uses token-boundary literal matching and structural evidence sections to **flag** suspicious classifications. No profession-specific knowledge-base or tool equivalence table is introduced.
3. Emit `relationship_consistency_flags` per proposal and aggregate counts in the shadow report. These do not change `complete` (which denotes structural completion), scores or ranks. Every decision remains provisional and `requires_human_review=True`.
4. Add `scripts/phase7g_relationship_audit.py`, which retrospectively examines existing `transferability.json` and `retrieval.json` **without calling Ollama**. Its checks are limited to agreement of the supplied JSON; the live pipeline still independently reopens the original CV for source validation.
5. Add tests for direct/transferable distinction, skills-only claims, token boundaries and old JSON report compatibility.

## Reproduce locally (PowerShell)

```powershell
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q

# Reaudit your existing successful reports without running Qwen again:
.\.venv\Scripts\python.exe -m scripts.phase7g_relationship_audit

# After inspecting the flags, obtain new Qwen classifications using the improved prompt:
.\scripts\run_phase7g_shadow.cmd --decompose
.\scripts\run_phase7g_transferability.cmd
.\.venv\Scripts\python.exe -m scripts.phase7g_relationship_audit
```

The existing audit output is: `outputs/phase7g_shadow/relationship_quality.json`.

**Next checkpoints:** independently review sampled labels across multiple job families, restore full role/project context, add contradiction and constraint audit, benchmark error rates and Qwen batch performance; only then consider connecting approved decisions to functional coverage. This code is **not** a safe automated hiring decision-maker.
