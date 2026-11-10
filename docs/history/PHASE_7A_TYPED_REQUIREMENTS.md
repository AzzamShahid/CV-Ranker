# Phase 7A — Source-Grounded Typed JD Requirements

**Build:** `typed-jd-requirements-2026-10-12`  
**Base:** `reviewer-approved-equivalence-2026-10-12` (Phase 6E)  
**Status:** Offline validated. No live Ollama acceptance benchmark for Phase 7A has been run here.

## Objective

Preserve the existing source-frozen JD list and candidate ranking behavior while adding **descriptive, source-backed type metadata** to every JD requirement. Phase 7A is *not* an experience verification engine, an educational credential verifier, or a change to scoring policy.

The supervisor's restrictions remain in force: no embeddings or vector search, no per-skill hardcoding/synonym table, no transferable-skill bonuses, and no new score percentages invented by the LLM.

## Key design choices

1. **The frozen JD remains authoritative.** Python still freezes `R001...`, source-quoted `name`, `priority` and `jd_evidence` as before. `ValidatedRequirement.constraint` is an additive nested Pydantic object. Both old direct constructions and historical report dictionaries without `constraint` retain schema compatibility through safe defaults.
2. **Conservative source rules work by default.** `cv_ranker/requirement_typing.py` classifies explicitly signaled text into `skill`, `experience`, `education`, `certification`, `license`, `responsibility`, `eligibility`, or `other`. It detects literal duration minima, explicitly named degree levels/fields, simple spelled-out AND/OR alternatives, and original JD line numbers. It does **not** infer unstated experience, degrees, or arbitrary job-related skills.
3. **Ambiguity is visible.** `requires_review=True` flags unfamiliar/unclear source text, complex compounds, partial education levels, and simple AND/OR that will require future policy approval before operational enforcement. A typing result is not an eligibility judgment.
4. **Qwen typing assistance is separate and opt-in.** `--llm-type-review` / the Streamlit checkbox invokes the *same* local Qwen only for `other` source lines; it returns a type label with an exact frozen requirement ID. An incomplete, duplicate or invented ID set is rejected. Suggestions are labelled `llm_suggestion` and *always* `requires_review=True`; they cannot introduce years, credentials, new requirements or scoring changes. Disabled by default to preserve call patterns and the Phase 6E baseline.
5. **No ranking changes.** `scoring.py`, `assessor.py`, existing JD prompts, existing status handling, and optional Phase 6E reviewer equivalences were not altered. The typed metadata is appended after JD reconciliation and before resumes are evaluated, and is not read by the scorer.
6. **Reproducibility.** The report JSON contains source-backed typed metadata and a `typed_requirements` diagnostic event, inserted before the existing final-denominator diagnostic for compatibility. The CLI details and Streamlit JD requirements table display the type, literal attributes and review status.

## Added data contract

```json
{
  "requirement_id": "R002",
  "name": "5+ years of Python experience",
  "priority": "required",
  "jd_evidence": "5+ years of Python experience",
  "constraint": {
    "kind": "experience",
    "operator": "single",
    "options": [],
    "minimum_years": 5.0,
    "subject": "Python",
    "degree_level": null,
    "field_of_study": null,
    "source_line_numbers": [4],
    "origin": "source_rules",
    "requires_review": false
  }
}
```

*Line numbers above are illustrative and depend on the actual JD.* `minimum_years=5` describes what the JD explicitly requires; it does **not** imply any applicant has that much experience.

## Touched files

- `cv_ranker/schemas.py`: typed `RequirementConstraint` and optional `ValidatedRequirement.constraint`; optional Qwen type-response schema
- `cv_ranker/requirement_typing.py`: strict conservative source classifier and optional bounded type-suggestion stage
- `cv_ranker/config.py`: new `llm_type_review=False` opt-in flag
- `cv_ranker/pipeline.py`: source-first typing after frozen JD reconciliation, without changing IDs or scores
- `main.py`: `--llm-type-review` and display of typed attributes
- `app.py`: optional Qwen type checkbox; type/review/source display in JD table and candidate evidence
- `cv_ranker/report.py`: concise types in CLI requirement display
- `tests/test_phase7a_typed_requirements.py`: schemas, cross-domain cases, source audit, numerical wording, AND/OR and scoring preservation
- `README.md`, `docs/ARCHITECTURE.md`, `docs/VALIDATION.md`: updated release guidance

## Validation performed

- Original Phase 6E ZIP clean extraction: **245/245 tests passing**.
- Phase 7A automated suite: **264/264 tests passing** after updates.
- Build SHA-256 manifest and fresh extraction: see terminal release validation.
- `python -m compileall` passing.
- Cross-version deterministic comparisons: **4 backend resumes + 3 HR resumes** had identical frozen requirement IDs/names/priorities/source strings, assessment statuses, ranks, primary scores and score bases relative to Phase 6E.
- **No new model accuracy figure.** Latest known full 21-label mixed benchmark is 19/21 from Phase 6C. The Phase 6D focused A/B result was 5/7 versus 6/7 with optional initialism; Phase 6E/7A live results require a local Windows Ollama run.

## Windows test commands

```powershell
.\run_runtime_check.cmd
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe doctor.py --live
.\scripts\run_benchmark.cmd
.\scripts\run_benchmark_pipeline.cmd

# Optional: ask Qwen to suggest types ONLY for unresolved JD criteria
.\.venv\Scripts\python.exe main.py --jd sample_data\backend_jd.txt --resumes sample_data\backend_resumes --details --llm-type-review --output outputs\phase7a_typed_demo.json
```

For the no-Qwen baseline, use `--no-llm` and omit `--llm-type-review`.

## Known limitations deliberately deferred

- Simple AND/OR is **recorded, not enforced**. Its actual scoring/eligibility behavior belongs to Phase 7D with HR-approved policy.
- Duration minimums/degree attributes are **JD metadata**, not a candidate-verification engine. Evidence sufficiency, explicit CV durations and employer-approved degree-equivalence rules belong to Phases 7B/7C.
- Date ranges, overlapping employment, qualification authenticity, OCR quality, cross-language variants and complicated natural-language logic are unimplemented. `other` means the type is not established—not that the criterion is unimportant.
- The optional Qwen typing stage is advisory only; it has not been evaluated live, and it may add latency.
- The 21-case benchmark does not establish readiness for unattended or high-impact employment selection. Keep human oversight.
