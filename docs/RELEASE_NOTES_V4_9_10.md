# Phase 7G V4.9.10 — source-defined academic categories

**Build:** `phase7g-v4-9-10-singular-degree-family-semantic-contract-2026-10-28`  
**Protocol:** `segment_ids_semantic_llm`, version 18

## Reproduced root cause

The JD `Completed Bachelor's degree in a Computer Program` correctly froze the
JD wording and typed `degree_level=bachelor`,
`field_of_study=a Computer Program`. The Python qualification gate recognized
plural `programs` as an inclusive category but did **not** recognize the
indefinite singular `a ... Program`. It therefore compared the entire category
name to the literal CV field and vetoed correctly cited BS Computer Science,
BS Software Engineering and BS Information Technology as `mismatch`.

This was a code-level false negative, not missing embedding retrieval. The
source ledger already contained the explicit completed degree claims.

## Repair

1. Generic *grammatical* field-family recognition accepts indefinite singular
   `a/an/any/some [modifier] program/field/discipline/major/area` as well as
   existing plural families and explicit `related/equivalent` language. This
   is NOT an accepted-major/occupation vocabulary. A specific named major
   remains strict. The exact original JD wording is unchanged.
2. The source-grounded unified LLM receives `education_field_scope` for each
   education criterion (`inclusive_category`, `exact_named_field`, or
   `unspecified`), plus prompt instructions to distinguish family membership
   from exact degree-title identity. The model decides whether the actual
   completed field *belongs* to the source-defined family; the hint does not
   establish an applicant's qualification by itself.
3. Existing Python qualification validation still checks claimed level,
   explicit completion, negation and cited original CV segment ID. For a
   broad category with a valid same-level claim, it defers academic membership
   to the model (`field_semantic`) rather than enforcing exact text equality.
4. If the initial LLM reports `Not Found` for a broad family despite a claimed
   same-level degree, the pre-existing **at most one** independent grouped
   verification call per CV may revisit that judgment. No extra per-criterion
   calls, embedding model, scoring weights or unlimited retries were added.

## Decision contract

| JD | CV evidence | Correct direct-credit rule |
| --- | --- | --- |
| Bachelor's in **a computing program** | Completed BS Computer Science | Found when semantically classified in that family and cited |
| Same inclusive JD | Completed BS Software Engineering | Found when semantically classified in that family and cited |
| Same inclusive JD | Completed BS Information Technology | Found if the employer's intended computing family includes IT and the model establishes it |
| Bachelor's in **Computer Science** (exact) | Completed BS Software Engineering | Not direct Found; potential unscored Transferable |
| Inclusive computing-family bachelor's | MSc alone | No automatic bachelor's Found |
| Inclusive computing-family bachelor's | In-progress BS | No completed-degree Found |
| Inclusive computing-family bachelor's | Unrelated BA | Never automatically converted to Found by Python |

**Important:** The model is responsible for semantic field-family membership;
source/degree validation does not magically make a wrong model judgment correct.
For an unclear employer category, HR confirmation is still appropriate. A
candidate-reported degree is not an independently authenticated credential.

## Verification

The release adds deterministic tests for singular and plural field families,
other departments, exact-name control cases, completion/degree-level denials,
preserved source IDs, model-sourced direct credit and an initial incorrect
literal-name rejection repaired by ONE independent grouped verification.
It also retains the previous negative and transferability regression tests.

**Not a real-world accuracy claim.** These tests prove code contracts in an
offline environment. No authenticated live OpenRouter/Gemini + EmbeddingGemma
evaluation against a human-reviewed JD/CV truth set was possible here.
Monitor actual results, cloud cost and original evidence citations in the
user's Windows setup before using the ranking for any consequential decision.

### Windows installation and verification

Install into a **new directory** so V4.9.9 remains recoverable. Restore the
user's own private `.env` and authorized JD/CV inputs separately; do not place
them in distributable source ZIP. From an activated environment:

```powershell
.\run_runtime_check.cmd
.\run_tests.cmd
.\.venv\Scripts\python.exe doctor.py --live --provider openrouter
.\run_ui.cmd
```

The live doctor command uses network credentials and may incur API charges.
Re-run both singular-category and explicit exact-major JDs, check their frozen
R002 source quotes, model explanations and final original CV evidence IDs.
