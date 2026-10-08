from pathlib import Path

from .assessor import assess_resume
from .config import Settings
from .documents import DocumentError, extract_text
from .jd import validate_jd_requirements
from .llm import LLMError, StructuredLLM
from .schemas import CandidateResult, RankingReport
from .scoring import assign_ranks, score_candidate
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

        requirements, jd_mode, jd_warnings = validate_jd_requirements(
            jd_text=jd_text,
            candidates=yake_candidates,
            settings=self.settings,
            llm=self.llm if self.use_llm else None,
        )
        warnings.extend(jd_warnings)

        if not requirements:
            raise RuntimeError("No usable JD requirements were produced; ranking cannot proceed.")

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
                )
                errors.extend(assessment_warnings)

                candidate_results.append(
                    score_candidate(
                        candidate_name=resume_path.name,
                        candidate_source=str(resume_path),
                        requirements=requirements,
                        assessments=assessments,
                        evaluation_mode=assessment_mode,
                        errors=errors,
                    )
                )
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

        ranked = assign_ranks(candidate_results)
        return RankingReport(
            job_description_source=str(jd_path),
            jd_validation_mode=jd_mode,
            yake_candidates=yake_candidates,
            requirements=requirements,
            candidates=ranked,
            warnings=warnings,
        )
