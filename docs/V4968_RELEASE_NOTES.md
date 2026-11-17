# TextileHR AI v4.9.68 — Prompt-first request contracts and paired evaluation

**Build** `phase7g-v4-9-68-prompt-first-contract-evaluation-2026-11-14`  
**Assessment protocol** `segment_ids_semantic_llm` **v54**  
**Input baseline** v4.9.67 / protocol v53 ZIP with SHA-256 `edecb96c8193d31dd84a01b7b2f99f05e3ec5a51ad7053c4fea03b5f85142d84`  
**Release category:** Offline-tested engineering release with *experimental* prompt wording; **NOT** evidence of higher live-model accuracy.

## Implemented source changes

1. **Primary unified assessment — `unified.UNIFIED_PROMPT`:** explicit separation of frozen JD authority, source text, retrieval order, candidate attribution and completed duties; explains when source excerpts are incomplete and cannot support a conclusive claim.
2. **Independent unified adjudication — `unified.FINAL_ADJUDICATION_PROMPT`:** explicitly checks both genuine equivalent work missed by the first pass and plausible unsupported Found decisions built from an original but irrelevant segment; prevents prior model rationale from becoming its own evidence.
3. **Compound condition review — `condition_review.REVIEW_PROMPT`:** matches the actual `ConditionReviewResponse`/`ReviewedFacet` wire fields, requires precise original JD offsets, original-source proof quotations and every approved AND/OR leaf including unused branches. The old prompt's literal JSON `{...}` example was removed, avoiding a system-message template placeholder hazard under LangChain's ChatPromptTemplate.
4. **JD extraction — `jd.SYSTEM_PROMPT`:** makes heading-inherited priorities and source-grounded narrative requirements explicit, without turning unrelated company background into criteria.
5. **JD correction — `jd.CORRECTION_PROMPT`:** preserves accepted siblings and corrects only source-rejected/omitted rows, avoiding invented denominator changes.
6. **JD typing — `requirement_typing.TYPE_SYSTEM_PROMPT`:** clarifies knowledge versus completed work, tenure versus record/process duration, and exact credentials versus generic skills.
7. **Optional typing request builder:** `requirement_typing.enrich_ambiguous_types()` now JSON-serializes untrusted original JD strings instead of using breakable `<QUOTE>` tags. Its older `<QUOTE>`-specific test was updated to check the stronger exact JSON source/ID contract.
8. **Retrieval decomposition request builder:** `semantic.decomposition._prompt()` now JSON-serializes frozen original JD evidence, guarding against fake `requirement_id:` and role markers in uploaded employer text. Decomposition remains retrieval-only, not a source of new criteria.
9. **Paired experiment harness:** `scripts/prompt_first_pair.py` invokes two isolated source trees with identical frozen fictional source packets and response schemas. Separate worker processes prevent one version's import paths from contaminating the other. Its default packet mode has zero provider calls. Local/cloud calls require explicit opt-in and a per-arm request ceiling; no paid calls were made in this release.
10. **Prompt and builder inventory:** a reproducible 13-row changed/retained prompt ledger, 16-row builder map, and eight full fictional pre-provider prompt/schema examples accompany the source.

**Retained with justification:** assessor legacy system/correction; semantic decomposition system; transferability full/compact/batch; UI optional judge. Their existing source/response contracts were not rewritten without isolated evidence of actual model improvement. They are still inventoried and remain candidates for controlled Level B experiments.

## Controlled packet comparison (Level A only)

Exactly **15** fictional cases (9 primary, 3 independent, 2 compound, 1 JD extraction) were built through the relevant source builders in separate v53 and v54 processes. Each pair had **identical user-packet SHA-256 and response-schema SHA-256**, with changed system-prompt hashes. No schema or scoring contract was changed by the paired wording arms.

For one representative case per stage, the approximate combined request token estimates (simple character estimator; **not provider-reported tokens**) changed as follows:

| Stage | v53 approximate tokens | v54 approximate tokens | Interpretation |
|---|---:|---:|---|
| Primary unified | 4,100 | 4,274 | More explicit source-scope instructions; small context increase |
| Independent unified | 3,302 | 3,452 | Extra reversal calibration; not a measured quality win |
| Compound review | 1,176 | 1,379 | Explicit schema and correct AND/OR facet instructions |
| JD extraction | 1,351 | 1,417 | Inherited headings and narrative priorities |

**No accuracy improvement claim** follows from these measurements. The extra system instructions increase context usage; future model tests may find a regression, in which case revert or tighten wording. The two JSON builder changes require a separate combined/full-pipeline experiment rather than treating the isolated wording arm as a fair comparison.

## Protected behavior and release status

- Preserve Required/Preferred pooling and opt-in split; Found earns the configured direct share once, Transferable earns zero, technical Unverified is never verified absence.
- Original source IDs, source-text provenance, frozen JD meaning, date/degree specialists, correction bounds, per-operation recovery and version-aware differential verification remain application-authoritative.
- A passing prompt contract test shows request/schema compatibility, **not** ability to interpret a new profession. Structured responses still need downstream source/meaning validation.
- Cache/report protocol bumped from v53 to v54: old v53 assessments are historical and must not be silently certified under changed instructions. Weight-only and branding-only changes remain display/projection operations and must not spend tokens.
- R2/R3 canonical JD/finalizer; R4/R6 recovery; R7 provider/privacy; R8 independent accuracy; R9 Windows; R10 remote multiuser remain open as documented in the verification ledger.

## Reproduction

```powershell
python scripts/prompt_inventory.py > prompt_inventory.json
python scripts/emit_prompt_first_examples.py
python -m pytest -q tests/test_v4968_prompt_first_contracts.py
python -m evaluation.evaluate_supervisor --cross-domain
```

The baseline v4.9.67 release must be extracted into a separate folder to run the A/B experiment; see `verification/PROMPT_FIRST_WINDOWS_HANDOFF.md` and `docs/V4968_VERIFICATION_REPORT.md`. No API keys, authentic applicant CVs or production recovery databases are included in this source package.
