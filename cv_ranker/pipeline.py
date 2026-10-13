from pathlib import Path

from .assessor import assess_resume
from .alias_approvals import apply_reviewed_aliases, load_approved_aliases
from .config import Settings
from .documents import DocumentError, extract_text
from .jd import validate_jd_requirements
from .llm import LLMError, StructuredLLM
from .schemas import CandidateResult, RankingReport
from .scoring import assign_ranks, score_candidate
from .requirement_typing import add_requirement_types
from .experience_validation import apply_experience_checks
from .qualification_validation import apply_qualification_checks
from .compound_validation import apply_compound_checks
from .eligibility import jd_source_sha256, load_eligibility_policy, check_eligibility
from .yake_extractor import extract_yake_candidates


class CVRanker:
    def __init__(self, settings: Settings | None = None, use_llm: bool = True):
        self.settings = settings or Settings()
        self.use_llm = use_llm
        self.llm: StructuredLLM | None = None
        self.startup_warnings: list[str] = []

        if use_llm:
            try:
                self.llm = StructuredLLM(self.settings)
            except LLMError as exc:
                self.startup_warnings.append(
                    f"LLM initialization failed; technical fallback mode active: {exc}"
                )

    def run(self, jd_path: str | Path, resume_paths: list[Path]) -> RankingReport:
        jd_path = Path(jd_path)
        jd_text = extract_text(jd_path)
        warnings = list(self.startup_warnings)

        try:
            yake_candidates = extract_yake_candidates(jd_text, self.settings)
        except Exception as exc:
            warnings.append(f"YAKE failed: {exc}. Structural fallback will be used.")
            yake_candidates = []

        jd_diagnostics: list[dict] = []
        requirements, jd_mode, jd_warnings = validate_jd_requirements(
            jd_text=jd_text,
            candidates=yake_candidates,
            settings=self.settings,
            llm=self.llm if self.use_llm else None,
            diagnostics=jd_diagnostics,
        )
        warnings.extend(jd_warnings)

        if not requirements:
            raise RuntimeError("No usable JD requirements were produced; ranking cannot proceed.")

        # Add source-grounded, descriptive constraint metadata AFTER the JD is
        # frozen. It does not alter IDs, names, priority, scoring or assessment.
        typing_diagnostics: list[dict] = []
        requirements = add_requirement_types(
            requirements, jd_text,
            llm=self.llm if self.use_llm else None,
            enable_llm=self.settings.llm_type_review and self.use_llm,
            diagnostics=typing_diagnostics,
        )
        # Retain the historical final_denominator event at the end of the JD
        # trace, so supervisor tools and existing consumers keep their contract.
        if jd_diagnostics and jd_diagnostics[-1].get("stage") == "final_denominator":
            jd_diagnostics[-1:-1] = typing_diagnostics
        else:
            jd_diagnostics.extend(typing_diagnostics)
        if any(r.constraint.requires_review for r in requirements):
            warnings.append(
                "Some JD requirement types or logical expressions need HR review. "
                "Phase 7D evaluates only simple, source-supported AND/OR clauses; "
                "other typed fields follow their existing validators."
            )

        # Optional per-JD approvals are validated against FROZEN requirements.
        # No approval file means no behavior changes or hidden alias catalogue.
        approved_aliases, approved_alias_hash = load_approved_aliases(
            self.settings.approved_aliases_path, requirements
        )
        if approved_aliases:
            warnings.append(
                f"{len(approved_aliases)} human-reviewed JD-specific equivalence(s) loaded; "
                "their credited rows are NOT pure Qwen decisions."
            )

        eligibility_policy, eligibility_policy_hash = load_eligibility_policy(
            self.settings.eligibility_policy_path, jd_text=jd_text, requirements=requirements
        )
        if eligibility_policy:
            warnings.append(
                f"HR selected {len(eligibility_policy.gates)} required eligibility gates; "
                "result concerns CV evidence, not identity, legal eligibility or credential authenticity."
            )
        candidate_results: list[CandidateResult] = []
        for resume_path in resume_paths:
            errors: list[str] = []
            try:
                resume_text = extract_text(resume_path)
            except DocumentError as exc:
                candidate_results.append(
                    CandidateResult(
                        candidate_name=resume_path.name,
                        candidate_source=str(resume_path),
                        primary_score=None,
                        evaluation_mode="failed",
                        errors=[str(exc)],
                    )
                )
                continue

            try:
                assessments, assessment_mode, assessment_warnings = assess_resume(
                    resume_text=resume_text,
                    requirements=requirements,
                    llm=self.llm if self.use_llm else None,
                    exact_initialism_guard=self.settings.exact_initialism_guard,
                )
                errors.extend(assessment_warnings)
                assessments, alias_notes, alias_changed = apply_reviewed_aliases(
                    requirements=requirements,
                    assessments=assessments,
                    resume_text=resume_text,
                    approvals=approved_aliases,
                )
                errors.extend(alias_notes)
                if alias_changed:
                    assessment_mode = "mixed"
                # Phase 7B: enforce typed numeric experience criteria before
                # scoring. Preserve the frozen JD denominator and all other
                # requirement decisions.
                assessments, experience_notes, experience_changed = apply_experience_checks(
                    requirements=requirements,
                    assessments=assessments,
                    resume_text=resume_text,
                )
                errors.extend(experience_notes)
                if experience_changed:
                    assessment_mode = "mixed"
                # Phase 7C: substantiate claimed academic/credential identity.
                # This checks resume assertions, NOT external authenticity.
                assessments, qualification_notes, qualification_changed = apply_qualification_checks(
                    requirements=requirements,
                    assessments=assessments,
                    resume_text=resume_text,
                )
                errors.extend(qualification_notes)
                if qualification_changed:
                    assessment_mode = "mixed"

                # Phase 7D: enforce only simple, literal, JD-explicit compound
                # options. Complex expressions stay review-needed, with zero
                # inferred credit. Keep one assessment per frozen JD item.
                assessments, compound_notes, compound_changed = apply_compound_checks(
                    requirements=requirements,
                    assessments=assessments,
                    resume_text=resume_text,
                )
                errors.extend(compound_notes)
                if compound_changed:
                    assessment_mode = "mixed"

                candidate_result = score_candidate(
                        candidate_name=resume_path.name,
                        candidate_source=str(resume_path),
                        requirements=requirements,
                        assessments=assessments,
                        evaluation_mode=assessment_mode,
                        errors=errors,
                    )
                candidate_result.eligibility = check_eligibility(
                    candidate=candidate_result, requirements=requirements,
                    policy=eligibility_policy,
                )
                candidate_results.append(candidate_result)
            except Exception as exc:
                candidate_results.append(
                    CandidateResult(
                        candidate_name=resume_path.name,
                        candidate_source=str(resume_path),
                        primary_score=None,
                        evaluation_mode="failed",
                        errors=errors + [f"Unexpected candidate evaluation failure: {exc}"],
                    )
                )

        successful_modes = {
            item.evaluation_mode
            for item in candidate_results
            if item.primary_score is not None
        }
        if len(successful_modes) > 1:
            warnings.append(
                "Candidates were evaluated with mixed modes "
                f"({', '.join(sorted(successful_modes))}). Evaluation mode is shown per candidate; "
                "fallback and LLM assessment are not presented as identical evidence paths."
            )
        if self.llm is not None and self.llm.disabled_reason:
            warnings.append(
                "The local LLM circuit was disabled after a technical failure; remaining LLM calls used deterministic fallback."
            )

        for candidate in candidate_results:
            if candidate.primary_score is None:
                candidate.eligibility = check_eligibility(
                    candidate=candidate, requirements=requirements, policy=eligibility_policy,
                )
        ranked = assign_ranks(candidate_results)
        return RankingReport(
            job_description_source=str(jd_path),
            jd_validation_mode=jd_mode,
            yake_candidates=yake_candidates,
            requirements=requirements,
            candidates=ranked,
            warnings=warnings,
            jd_diagnostics=jd_diagnostics,
            approved_aliases=[item.model_dump() for item in approved_aliases],
            approved_aliases_sha256=approved_alias_hash,
            jd_sha256=jd_source_sha256(jd_text),
            eligibility_policy_sha256=eligibility_policy_hash,
            eligibility_policy_reviewed_by=eligibility_policy.reviewed_by if eligibility_policy else None,
            eligibility_gate_names=[g.requirement for g in eligibility_policy.gates] if eligibility_policy else [],
            eligibility_gates=[g.model_dump() for g in eligibility_policy.gates] if eligibility_policy else [],
        )
