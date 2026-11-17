from pathlib import Path
from datetime import date
from .assessment_clock import assessment_date, frozen_assessment_date
import hashlib
import re

from .assessor import assess_resume
from .alias_approvals import apply_reviewed_aliases, load_approved_aliases
from .config import Settings
from .documents import DocumentError, extract_text
from .jd import validate_jd_requirements
from .jd_coverage import explicit_clause_coverage, coverage_warning
from .llm import LLMError, StructuredLLM
from .schemas import (CandidateResult, JDReviewDraft, RankingReport, RequirementAssessment,
                      ValidatedRequirement, DecisionTransition)
from .build_info import BUILD_ID
from .decision_contract import completed, incomplete, DecisionRecord
from .resume import candidate_resume_keys
from .source_snapshot import read_candidate_snapshot
from .scoring import assign_ranks, score_candidate
from .requirement_typing import add_requirement_types
from .experience_validation import (apply_experience_checks,
                                    related_experience_transfer_supported)
from .qualification_validation import apply_qualification_checks, related_degree_transfer_supported
from .compound_validation import apply_compound_checks, _NEGATED_WORK
from .eligibility import jd_source_sha256, load_eligibility_policy, check_eligibility
from .yake_extractor import extract_yake_candidates
from .segments import segment_resume
from .text_utils import has_candidate_action, instruction_like_evidence, non_candidate_requirement_copy


def reconcile_final_assessments(*, requirements: list[ValidatedRequirement],
                                assessments: list[RequirementAssessment],
                                source_segments: list | None = None,
                                ) -> list[RequirementAssessment]:
    """Only Found earns direct credit; preserve verified reviewer-only overlap.

    Typed source checks can veto a direct score without deleting evidence of
    *related* work or education. A denied, incomplete, unsourced or merely
    adjacent claim is never promoted from Not Found by this function.
    """
    by_requirement = {req.requirement_id: req for req in requirements}
    # Optional original source ledger binds a scored final row to the exact
    # candidate revision. Standalone legacy projections retain their prior
    # behavior, while the active unified supervisor path supplies this ledger.
    original_by_id = ({s.segment_id: s for s in source_segments}
                      if source_segments is not None else None)
    final = []
    for item in assessments:
        if original_by_id is not None and item.assessment_state == "verified":
            ids = item.evidence_ids
            cited = {c.segment_id: c for c in item.evidence_segments}
            # Every cited verdict, including Transferable and contextual
            # Not Found, must resolve to this candidate's ORIGINAL ledger.
            # A legitimate negative may have no citations; a positive may not.
            if (((item.status == "matched" or item.unified_status == "Transferable")
                  and not ids) or len(ids) != len(set(ids)) or
                    not set(ids).issubset(cited) or
                    any(sid not in original_by_id or
                        cited[sid].text != original_by_id[sid].text or
                        cited[sid].section != original_by_id[sid].section
                        for sid in cited)):
                final.append(item.model_copy(update={
                    "status":"uncertain", "unified_status":None,
                    "assessment_state":"unverified", "review_recommended":True,
                    "current_decision": incomplete("source_identity_invalid",
                        stage="source_identity_finalizer",
                        detail="Original candidate source ledger did not validate the cited positive evidence."),
                    "reason":"Direct candidate evidence could not be verified against the exact original CV source ledger.",
                    "decision_trace":[*item.decision_trace, DecisionTransition(
                        stage="source_identity_finalizer", from_status=item.unified_status or item.status,
                        to_status="Unverified", reason_code="original_source_identity_incomplete",
                        evidence_ids=list(ids))],
                }))
                continue
        if item.assessment_state == "unverified":
            # A parser's request for semantic evidence review is pending work,
            # not a failed provider call.  Keep any actual operation failure,
            # but never invent one merely because the review has not run yet.
            source_review_pending = (item.compound_check is not None and
                item.compound_check.outcome == "needs_review" and
                any(t.reason_code == "jd_syntax_needs_review"
                    for t in item.decision_trace))
            record = item.current_decision
            if record is None or record.processing_state == "completed":
                record = (DecisionRecord(processing_state="pending",
                    explanation="Source-bound semantic review is required for the frozen JD condition")
                    if source_review_pending else
                    incomplete("processing_error", stage="final_reconciliation",
                        detail="An assessment result is incomplete without a validated decision"))
            final.append(item.model_copy(update={
                "status": "uncertain", "unified_status": None,
                "review_recommended": True,
                "current_decision": record,
            }))
            continue
        if (item.compound_check is not None
                and item.compound_check.outcome == "needs_review"
                and item.status == "uncertain"
                and item.unified_status == "Found"):
            final.append(item.model_copy(update={
                "status": "uncertain", "unified_status": None,
                "assessment_state": "unverified", "review_recommended": True,
                "reason": "Source-bound review is needed to interpret the JD; no negative is established.",
                "current_decision": DecisionRecord(processing_state="pending",
                    explanation="Compound source review has not completed"),
            }))
            continue
        if item.status == "matched":
            verdict = "Found"
        else:
            requirement = by_requirement[item.requirement_id]
            related_education = bool(
                item.unified_status == 'Transferable'
                and related_degree_transfer_supported(
                    requirement, item.qualification_check, item.evidence_ids))
            related_experience = bool(item.experience_check is not None
                                      and related_experience_transfer_supported(item))
            blocked = (
                (item.experience_check is not None and not related_experience) or
                (item.qualification_check is not None and not related_education)
            )
            # A compound check decides *direct* eligibility for explicitly
            # verified mandatory options. It is not evidence that genuinely
            # related, completed work was absent. Preserve a preceding
            # source-backed Transferable relationship independently of the
            # syntax/option check, while requiring actual cited sources.
            has_cited_source = bool(
                item.evidence_ids and item.evidence_segments and
                {s.segment_id for s in item.evidence_segments}.issuperset(item.evidence_ids)
            )
            # A source ID alone is not proof of transferable FUNCTIONAL work.
            # It must survive the upstream source validator AND document
            # completed affirmative actions. Education and tenure continue
            # using their independent specialist support tests above.
            related_work = any(
                s.segment_id in item.evidence_ids
                and s.section in {"experience", "work_experience", "projects", "summary"}
                and not _NEGATED_WORK.search(s.text)
                and not instruction_like_evidence(s.text)
                and not non_candidate_requirement_copy(s.text)
                for s in item.evidence_segments
            )
            compound_relation_ok = (item.compound_check is None or related_work
                                    or related_experience or related_education)
            verdict = ("Transferable" if not blocked and has_cited_source and
                       compound_relation_ok and
                       item.unified_status == "Transferable" else "Not Found")
        trace = list(item.decision_trace)
        if verdict != item.unified_status:
            trace.append(DecisionTransition(
                stage="final_reconciliation",
                from_status=item.unified_status or item.status,
                to_status=verdict,
                reason_code=("source_backed_related_work" if verdict == "Transferable"
                             else "direct_source_eligibility" if verdict == "Found"
                             else "direct_or_related_not_established"),
                evidence_ids=list(item.evidence_ids),
            ))
        final.append(item.model_copy(update={
            "unified_status": verdict,
            "current_decision": completed(verdict, item.reason),
            "decision_trace": trace,
            "review_recommended": item.review_recommended or
                item.status == "uncertain" or verdict == "Transferable",
        }))
    return final


class CVRanker:
    def __init__(self, settings: Settings | None = None, use_llm: bool = True,
                 *, unified: bool = False, embedding_cache_path: str | Path | None = None,
                 embedding_encoder=None, progress_callback=None):
        self.settings = settings or Settings()
        self.use_llm = use_llm
        self.unified = unified
        self.embedding_cache_path = embedding_cache_path
        self.embedding_encoder = embedding_encoder
        self.progress_callback = progress_callback
        self.source_ledgers: dict[str, list] = {}
        self.unified_metrics: dict[str, dict] = {}
        self.request_metrics: dict[str, object] = {}
        self.llm: StructuredLLM | None = None
        self.startup_warnings: list[str] = []

        if use_llm:
            try:
                self.llm = StructuredLLM(self.settings)
            except LLMError as exc:
                self.startup_warnings.append(
                    f"LLM initialization failed; technical fallback mode active: {exc}"
                )
        if self.unified and self.use_llm and self.llm is None:
            raise LLMError("Unified semantic assessment requires the configured LLM; cannot silently use fallback")
        if self.llm is not None and callable(self.progress_callback):
            self.llm.progress_callback = self.progress_callback

    def _progress(self, message: str) -> None:
        if callable(self.progress_callback):
            self.progress_callback(message)

    def prepare_jd_review(self, jd_path: str | Path) -> JDReviewDraft:
        """Extract and type JD requirements without assessing a single CV."""
        jd_text = extract_text(jd_path)
        warnings = list(self.startup_warnings)
        try:
            yake_candidates = extract_yake_candidates(jd_text, self.settings)
        except Exception as exc:
            warnings.append(f"YAKE failed: {exc}. Structural fallback will be used.")
            yake_candidates = []
        diagnostics: list[dict] = []
        requirements, jd_mode, jd_warnings = validate_jd_requirements(
            jd_text=jd_text, candidates=yake_candidates, settings=self.settings,
            llm=self.llm if self.use_llm else None, diagnostics=diagnostics,
        )
        warnings.extend(jd_warnings)
        if not requirements:
            raise RuntimeError("No usable JD requirements were produced; ranking cannot proceed.")
        typing_diagnostics: list[dict] = []
        requirements = add_requirement_types(
            requirements, jd_text,
            llm=self.llm if self.use_llm else None,
            enable_llm=self.settings.llm_type_review and self.use_llm,
            diagnostics=typing_diagnostics,
        )
        if diagnostics and diagnostics[-1].get("stage") == "final_denominator":
            diagnostics[-1:-1] = typing_diagnostics
        else:
            diagnostics.extend(typing_diagnostics)
        clause_coverage = explicit_clause_coverage(jd_text, requirements)
        if diagnostics and diagnostics[-1].get("stage") == "final_denominator":
            diagnostics[-1:-1] = clause_coverage
        else:
            diagnostics.extend(clause_coverage)
        warning = coverage_warning(clause_coverage)
        if warning:
            warnings.append(warning)
        return JDReviewDraft(
            jd_sha256=jd_source_sha256(jd_text),
            yake_candidates=yake_candidates, requirements=requirements,
            jd_validation_mode=jd_mode, warnings=warnings, diagnostics=diagnostics,
        )

    def run(self, jd_path: str | Path, resume_paths: list[Path], *,
            resume_report: RankingReport | None = None,
            resume_candidates: dict[str, CandidateResult] | None = None,
            approved_jd: JDReviewDraft | None = None,
            as_of_date: date | None = None) -> RankingReport:
        """Freeze calendar time across every stage and subsequent Resume call.

        Caller-supplied date is for a *new* assessment. A resumed run cannot
        reinterpret Present positions on a different date or use a new date.
        """
        original_date = resume_report.assessment_as_of_date if resume_report else None
        # The new protocol cannot import a genuinely older build (checked
        # below), but manually constructed same-build reports from old clients
        # may omit this optional field. Use a new frozen date for that case,
        # never pretend that its old unchecked tenure was independently proven.
        frozen = date.fromisoformat(original_date) if original_date else (as_of_date or date.today())
        if type(frozen) is not date:
            raise TypeError("as_of_date must be a datetime.date")
        if original_date and as_of_date is not None and as_of_date != frozen:
            raise ValueError("Assessment date changed during Resume; start a fresh assessment")
        with frozen_assessment_date(frozen):
            report = self._run_with_frozen_date(
                jd_path, resume_paths, resume_report=resume_report,
                resume_candidates=resume_candidates, approved_jd=approved_jd)
            return report.model_copy(update={"assessment_as_of_date": frozen.isoformat()})

    def _run_with_frozen_date(self, jd_path: str | Path, resume_paths: list[Path], *,
            resume_report: RankingReport | None = None,
            resume_candidates: dict[str, CandidateResult] | None = None,
            approved_jd: JDReviewDraft | None = None) -> RankingReport:
        jd_path = Path(jd_path)
        jd_text = extract_text(jd_path)
        warnings = list(self.startup_warnings)
        if resume_report is not None:
            if (resume_report.build_id != BUILD_ID or
                    resume_report.jd_sha256 != jd_source_sha256(jd_text)):
                raise ValueError("Resume rejected: build or JD changed. Start a fresh assessment.")
            # Reuse the exact frozen, typed JD. Re-extracting it would spend
            # provider quota and could silently change the score denominator.
            yake_candidates = list(resume_report.yake_candidates)
            requirements = list(resume_report.requirements)
            jd_mode = resume_report.jd_validation_mode
            jd_diagnostics = list(resume_report.jd_diagnostics)
        elif approved_jd is not None:
            if not approved_jd.approved:
                raise ValueError("JD requirements require reviewer approval before CV assessment.")
            if approved_jd.jd_sha256 != jd_source_sha256(jd_text):
                raise ValueError("The job description changed after approval. Extract and review it again.")
            if (not approved_jd.requirements or
                    len(approved_jd.requirements) > self.settings.max_requirements or
                    len({r.requirement_id for r in approved_jd.requirements}) != len(approved_jd.requirements)):
                raise ValueError("Approved JD has missing, duplicate or excessive requirement IDs.")
            yake_candidates = list(approved_jd.yake_candidates)
            requirements = list(approved_jd.requirements)
            jd_mode = approved_jd.jd_validation_mode
            jd_diagnostics = list(approved_jd.diagnostics)
            warnings.extend(approved_jd.warnings)
        else:
            draft = self.prepare_jd_review(jd_path)
            yake_candidates = draft.yake_candidates
            requirements = draft.requirements
            jd_mode = draft.jd_validation_mode
            jd_diagnostics = draft.diagnostics
            warnings.extend(draft.warnings)

        # An extraction limit is a UI/resource guard, not authorization to
        # remove employer requirements from the score denominator. This also
        # protects CLI runs and previously saved approvals made under a
        # smaller cap; only a complete frozen JD can be ranked.
        if any("JD requirement cap:" in item or
               "configured maximum retained" in item
               for item in warnings):
            raise ValueError(
                "JD extraction was truncated by max_requirements. Raise the "
                "requirement limit and extract/reapprove the complete JD before "
                "ranking candidates.")

        if not requirements:
            raise RuntimeError("No usable JD requirements were produced; ranking cannot proceed.")
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
        if resume_report is not None and (
                approved_alias_hash != resume_report.approved_aliases_sha256 or
                eligibility_policy_hash != resume_report.eligibility_policy_sha256):
            raise ValueError("Resume rejected: HR approval or eligibility policy changed.")
        if eligibility_policy:
            warnings.append(
                f"HR selected {len(eligibility_policy.gates)} required eligibility gates; "
                "result concerns CV evidence, not identity, legal eligibility or credential authenticity."
            )
        candidate_results: list[CandidateResult] = []
        self.source_ledgers = {}
        self.source_keys = {}  # exact byte snapshot identities for UI recovery
        self.unified_metrics = {}
        self.request_metrics = {}
        reused_candidates = 0
        reassessed_candidates = 0
        retained_partial_candidates = 0
        engine = None
        # Never pre-read every candidate just to build resume identities: one
        # deleted or unreadable file must not abort the healthy input slots.
        # Duplicate basenames have ambiguous historical occurrence identity;
        # declining reuse is safer than inheriting another slot's score.
        from collections import Counter
        repeated_names = {name for name, n in Counter(p.name for p in resume_paths).items() if n > 1}
        key_occurrences: dict[str,int] = {}
        for resume_index, resume_path in enumerate(resume_paths):
            self._progress(f"CV {resume_index + 1}/{len(resume_paths)}: reading resume and preparing evidence")
            errors: list[str] = []
            cached = None
            try:
                resume_text, exact_snapshot_key = read_candidate_snapshot(resume_path)
                occurrence = key_occurrences.get(exact_snapshot_key, 0)
                key_occurrences[exact_snapshot_key] = occurrence + 1
                if occurrence:
                    exact_slot_key = hashlib.sha256(
                        f"{exact_snapshot_key}:{occurrence}".encode("utf-8")).hexdigest()
                else:
                    exact_slot_key = exact_snapshot_key
                self.source_keys[str(resume_path)] = exact_slot_key
                if (resume_report is not None and resume_candidates is not None
                        and resume_path.name not in repeated_names):
                    cached = resume_candidates.get(exact_slot_key)
            except DocumentError as exc:
                self._progress(f"CV {resume_index + 1}/{len(resume_paths)}: document extraction failed")
                candidate_results.append(
                    CandidateResult(
                        candidate_name=resume_path.name,
                        candidate_source=str(resume_path),
                        primary_score=None,
                        evaluation_mode="failed",
                        errors=["Candidate source unavailable or incomplete; no assessment or verified score. "
                            + str(exc)],
                    )
                )
                continue

            # A complete cached judgment is reusable only if every frozen
            # requirement was verified. Hash matching alone is insufficient.
            expected = {r.requirement_id for r in requirements}
            if cached is not None and cached.primary_score is not None and (
                    {a.requirement_id for a in cached.assessments} == expected
                    and len(cached.assessments) == len(requirements)
                    and all(a.assessment_state != "unverified" for a in cached.assessments)):
                if self.unified and self.use_llm:
                    self.source_ledgers[str(resume_path)] = segment_resume(resume_text)
                    self.unified_metrics[str(resume_path)] = {
                        "reused_completed_assessment": True, "llm_calls": 0,
                        "correction_calls": 0, "final_verification_calls": 0,
                    }
                candidate_results.append(cached.model_copy(update={
                    "candidate_name": resume_path.name,
                    "candidate_source": str(resume_path), "rank": None,
                }))
                reused_candidates += 1
                self._progress(f"CV {resume_index + 1}/{len(resume_paths)}: completed judgment reused from checkpoint")
                continue

            # Once a run's cloud circuit has opened, do not embed and attempt
            # every remaining CV merely to get the same 429 again.
            if self.unified and self.llm is not None and self.llm.disabled_reason:
                paused_reason = ("Assessment paused after OpenRouter HTTP 429: provider "
                                 "stopped accepting requests; resume after cooldown."
                                 if "429" in self.llm.disabled_reason else
                                 "Assessment paused: the selected AI provider is unavailable "
                                 "for this run. Resume after its cooldown.")
                fallback = CandidateResult(
                    candidate_name=resume_path.name,
                    candidate_source=str(resume_path), evaluation_mode="failed",
                    errors=[paused_reason],
                )
                if cached is not None and cached.primary_score is None and cached.assessments:
                    fallback = cached.model_copy(update={
                        "candidate_name": resume_path.name,
                        "candidate_source": str(resume_path), "rank": None,
                        "errors": list(cached.errors) + [
                            "Resume paused by the provider; previous verified evidence was retained."],
                    })
                    retained_partial_candidates += 1
                candidate_results.append(fallback)
                self._progress(f"CV {resume_index + 1}/{len(resume_paths)}: provider paused; saved evidence retained")
                continue

            reassessed_candidates += 1

            try:
                if self.unified and self.use_llm:
                    if engine is None:
                        from .unified import UnifiedEvidenceEngine
                        cache_path = self.embedding_cache_path or (
                            Path(__file__).resolve().parent.parent /
                            "outputs" / "unified_embedding_cache.db")
                        engine = UnifiedEvidenceEngine(
                            self.settings, self.llm, cache_path=cache_path,
                            encoder=self.embedding_encoder)
                        engine.progress_callback = self.progress_callback
                    segments = segment_resume(resume_text)
                    self.source_ledgers[str(resume_path)] = segments
                    cid = hashlib.sha256(
                        (str(resume_path.resolve()) + "|" + resume_text).encode("utf-8")
                    ).hexdigest()[:24]
                    # A partial checkpoint must not send already-verified JD
                    # rows back to the model. Evidence is bound to the exact
                    # CV bytes and frozen JD by the outer resume checkpoint.
                    original_by_id = {s.segment_id: s for s in segments}
                    verified_prior = {}
                    blocked_semantic_prior = {}
                    retryable_semantic_prior = {}
                    if cached is not None:
                        from .condition_review import semantic_review_signature
                        frozen_by_id = {r.requirement_id: r for r in requirements}
                        for item in cached.assessments:
                            if item.requirement_id not in expected:
                                continue
                            if any(original_by_id.get(c.segment_id) is None
                                   or original_by_id[c.segment_id].text != c.text
                                   for c in item.evidence_segments):
                                continue
                            if any(sid not in original_by_id for sid in item.evidence_ids):
                                continue
                            if item.assessment_state == "verified":
                                verified_prior[item.requirement_id] = item
                            elif (item.compound_check is not None
                                  and item.compound_check.outcome == "needs_review"
                                  and item.condition_review_attempt_signature is not None
                                  and item.condition_review_attempt_signature ==
                                  semantic_review_signature(
                                      frozen_by_id[item.requirement_id], resume_text, self.llm)):
                                # An explicitly rejected 429 may be retried
                                # after the ledger's bounded cooldown. Unknown
                                # delivery is NOT a retry license.
                                current = item.current_decision
                                if (current is not None and
                                        current.processing_state == "paused" and
                                        current.failure is not None and
                                        current.failure.code == "provider_rate_limit" and
                                        current.failure.retry_eligible):
                                    retryable_semantic_prior[item.requirement_id] = item
                                else:
                                    blocked_semantic_prior[item.requirement_id] = item
                    pending_requirements = [req for req in requirements
                                            if req.requirement_id not in verified_prior
                                            and req.requirement_id not in blocked_semantic_prior
                                            and req.requirement_id not in retryable_semantic_prior]
                    if pending_requirements:
                        if verified_prior:
                            updated, measured = engine.assess(
                                pending_requirements, segments, resume_text,
                                candidate_id=cid, context_requirements=requirements,
                                known_assessments=verified_prior)
                        else:
                            updated, measured = engine.assess(
                                pending_requirements, segments, resume_text,
                                candidate_id=cid)
                        new_by_id = {item.requirement_id: item for item in updated}
                        assessments = [verified_prior.get(req.requirement_id)
                                       or blocked_semantic_prior.get(req.requirement_id)
                                       or retryable_semantic_prior.get(req.requirement_id)
                                       or new_by_id[req.requirement_id]
                                       for req in requirements]
                    else:
                        # Earlier technical failure may have withheld a score
                        # despite all rows now being independently verified.
                        from .unified import UnifiedMetrics
                        measured = UnifiedMetrics()
                        assessments = [verified_prior.get(req.requirement_id)
                                       or blocked_semantic_prior.get(req.requirement_id)
                                       or retryable_semantic_prior[req.requirement_id]
                                       for req in requirements]
                    self.unified_metrics[str(resume_path)] = measured.public()
                    if blocked_semantic_prior:
                        self.unified_metrics[str(resume_path)]["reused_paused_semantic_review"] = (
                            len(blocked_semantic_prior))
                        errors.append(
                            f"{len(blocked_semantic_prior)} compound JD review(s) remain "
                            "incomplete with unchanged evidence; identical semantic "
                            "calls were not repeated on Resume.")
                    outstanding = int(getattr(
                        measured, "unresolved_criteria",
                        sum(a.assessment_state == "unverified" for a in assessments)))
                    self._progress(
                        f"CV {resume_index + 1}/{len(resume_paths)}: "
                        f"{len(requirements) - outstanding}/{len(requirements)} "
                        "requirements resolved; saving assessment checkpoint")
                    assessment_mode, assessment_warnings = "llm_assessed", measured.warnings
                else:
                    if self.use_llm and self.llm is None:
                        # Requested semantic assessment could not initialize.
                        # Never turn a provider/configuration failure into a
                        # completed Not Found through exact-word fallback.
                        assessments = [RequirementAssessment(
                            requirement_id=req.requirement_id,
                            status="uncertain", unified_status=None,
                            assessment_state="unverified", review_recommended=True,
                            current_decision=incomplete("provider_unavailable",
                                stage="model_initialization",
                                detail="The configured provider did not initialize."),
                            reason="The semantic assessment provider was unavailable; "
                                   "no candidate verdict was established.",
                        ) for req in requirements]
                        assessment_mode = "failed"
                        assessment_warnings = [
                            "Configured model failed to initialize; no candidate "
                            "negative is inferred from the provider failure."]
                    else:
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

                # Syntax-only Boolean parsing cannot establish a negative
                # judgment about the applicant. An independent, source-bound
                # semantic review may settle ONLY the affected requirements.
                # Missing/invalid provider replies retain technical Unverified
                # and the previous verified siblings, never an invented score.
                if self.use_llm and self.llm is not None:
                    from .condition_review import review_compound_uncertainty
                    assessments, review_stats = review_compound_uncertainty(
                        requirements=requirements, assessments=assessments,
                        resume_text=resume_text, llm=self.llm,
                        ledger_path=(self.embedding_cache_path or (
                            Path(__file__).resolve().parent.parent /
                            "outputs" / "unified_embedding_cache.db")).parent /
                            "semantic_operation_ledger.sqlite")
                    errors.extend(review_stats.notices)
                    if review_stats.attempted:
                        self.unified_metrics.setdefault(str(resume_path), {})
                        self.unified_metrics[str(resume_path)]["compound_review_calls"] = (
                            review_stats.attempted)
                        self.unified_metrics[str(resume_path)]["llm_calls"] = (
                            int(self.unified_metrics[str(resume_path)].get("llm_calls", 0))
                            + review_stats.attempted)
                    if review_stats.resolved:
                        assessment_mode = "mixed"
                    if review_stats.pending:
                        errors.append(
                            f"{review_stats.pending} JD compound condition review(s) "
                            "remain incomplete. Approve source-grounded mandatory parts "
                            "or provide genuinely new candidate evidence; no verified "
                            "negative was inferred from parser syntax alone.")

                # All *new* supervisor assessments, including legacy and
                # deterministic fallback, must pass the same canonical final
                # decision owner before scores, exports or UI can see them.
                # If the user configured no LLM and the JD still requires a
                # semantic condition review, the missing operation is explicit.
                if engine is None and self.llm is None:
                    outstanding = []
                    for row in assessments:
                        if (row.assessment_state == "unverified" and
                                row.compound_check is not None and
                                row.compound_check.outcome == "needs_review" and
                                (row.current_decision is None or
                                 row.current_decision.processing_state == "pending")):
                            row = row.model_copy(update={
                                "current_decision": incomplete("provider_unavailable",
                                    stage="compound_review",
                                    detail="This compound criterion requires semantic review; no model is configured")})
                        outstanding.append(row)
                    assessments = outstanding
                assessments = reconcile_final_assessments(
                    requirements=requirements, assessments=assessments,
                    source_segments=(segments if engine is not None else
                                     segment_resume(resume_text)))

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
                self._progress(f"CV {resume_index + 1}/{len(resume_paths)}: "
                               "unexpected local failure; preserving previous checkpoint")
                provider_status = (re.search(r"OpenRouter HTTP \d{3}", str(exc))
                                   if isinstance(exc, LLMError) else None)
                failure_kind = (provider_status.group(0) if provider_status
                                else type(exc).__name__)
                candidate_results.append(
                    CandidateResult(
                        candidate_name=resume_path.name,
                        candidate_source=str(resume_path),
                        primary_score=None,
                        evaluation_mode="failed",
                        # Exception messages from parser/provider dependencies
                        # may contain CV excerpts or response payloads.
                        errors=errors + [f"Unexpected candidate evaluation failure: {failure_kind}"],
                    )
                )

            # Never discard stronger, source-grounded partial findings merely
            # because a later resume attempt encountered a provider outage.
            current = candidate_results[-1]
            if cached is not None and cached.primary_score is None and cached.assessments and (
                    current.primary_score is None):
                old_verified = sum(a.assessment_state != "unverified" for a in cached.assessments)
                new_verified = sum(a.assessment_state != "unverified" for a in current.assessments)
                if old_verified > new_verified:
                    candidate_results[-1] = cached.model_copy(update={
                        "candidate_name": resume_path.name,
                        "candidate_source": str(resume_path), "rank": None,
                        "errors": list(cached.errors) + [
                            "Retry did not improve source coverage; previous partial evidence was retained.",
                            *[e for e in current.errors if "HTTP 429" in e],
                        ],
                    })
                    retained_partial_candidates += 1

            self._progress(
                f"CV {resume_index + 1}/{len(resume_paths)}: "
                + ("complete" if candidate_results[-1].primary_score is not None
                   else "incomplete; remaining decisions saved for focused recovery"))

        if engine is not None:
            engine.close()

        if self.llm is not None:
            self.request_metrics = {
                "provider": self.settings.llm_provider,
                "model": self.settings.model_name,
                "logical_model_calls": getattr(self.llm, "logical_calls", 0),
                "actual_model_request_attempts": getattr(self.llm, "http_attempts", 0),
                # Reuse occurs ONLY for identical successful, validated
                # prompts during the same unified assessment run. Never
                # confuse it with attempted HTTP calls or cached embeddings.
                "validated_identical_prompt_reuses": getattr(
                    self.llm, "reused_successful_calls", 0),
                "provider_reported_tokens": getattr(self.llm, "token_usage", {}),
                "unified_candidate_calls": sum(
                    int(v.get("llm_calls", 0)) for v in self.unified_metrics.values()),
                "resumed_frozen_jd": resume_report is not None,
                "reused_completed_candidates": reused_candidates,
                "reassessed_candidates": reassessed_candidates,
                "retained_previous_partial_candidates": retained_partial_candidates,
                "http_429_count": getattr(self.llm, "http_429_count", 0),
                "provider_retry_after_seconds": getattr(self.llm, "last_retry_after_seconds", None),
            }

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
            if self.unified:
                # Unified scoring deliberately does NOT substitute a different
                # assessor when provider calls fail. Calling this 'fallback'
                # concealed three unassessed CVs behind apparent zero scores.
                warning = ("The selected AI provider stopped accepting assessment "
                           "requests during this run. Later candidates may be "
                           "incomplete; no fallback score was assigned.")
                if self.settings.llm_provider == "openrouter":
                    warning += " " + str(self.llm.disabled_reason)[:300]
                warnings.append(warning)
            else:
                warnings.append(
                    "The configured AI provider was disabled after a technical failure; "
                    "remaining non-unified checks may use deterministic fallback."
                )

        for candidate in candidate_results:
            if candidate.primary_score is None:
                candidate.eligibility = check_eligibility(
                    candidate=candidate, requirements=requirements, policy=eligibility_policy,
                )
        ranked = assign_ranks(candidate_results)
        return RankingReport(
            job_description_source=str(jd_path),
            original_jd_text=jd_text,
            jd_validation_mode=jd_mode,
            yake_candidates=yake_candidates,
            requirements=requirements,
            jd_review_approved=bool(approved_jd is not None or
                                    (resume_report and resume_report.jd_review_approved)),
            jd_review_edited=bool((approved_jd and approved_jd.edited) or
                                  (resume_report and resume_report.jd_review_edited)),
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

    def plan_jd_capabilities(self, report: RankingReport):
        """Propose JD-grounded search queries; never changes frozen requirements or ranking.

        These LLM proposals REQUIRE review and must not be scored as evidence.
        """
        from .semantic.decomposition import create_shadow_search_plan
        if self.llm is None or not self.use_llm:
            raise ValueError("JD decomposition requires live Qwen; --no-llm is incompatible")
        return create_shadow_search_plan(report.requirements, self.llm)

    def run_semantic_shadow(
        self, report: RankingReport, *, cache_path: str | Path, encoder=None,
        top_k: int = 5, model: str | None = None,
        dimensions: int | None = None, capability_plan=None,
    ) -> dict:
        """Optional Phase 7G retrieval diagnostics; never changes a candidate score.

        Call after ``run`` so YAKE, Qwen JD freezing, segmentation, source
        validation and Python scoring follow their existing proven flow.
        """
        from .semantic import run_shadow_retrieval
        return run_shadow_retrieval(
            report, cache_path=cache_path, encoder=encoder, top_k=top_k,
            model=model or self.settings.embedding_model,
            base_url=self.settings.ollama_base_url,
            timeout=self.settings.embedding_timeout_seconds,
            batch_size=self.settings.embedding_batch_size,
            dimensions=dimensions, capability_plan=capability_plan,
        )


    def score_verified_functional_coverage(
        self, candidate: CandidateResult, requirements, plan, decisions, *, admissible_source_ids: set[str]
    ):
        """Optional read-only 7G functional-coverage report, NOT a rank update.

        The caller must first produce and independently verify JD-derived
        capability decisions and candidate-scoped source admissibility.
        Shadow retrieval alone must never be turned into assessments.
        """
        from .semantic.coverage_scoring import score_verified_capability_coverage
        return score_verified_capability_coverage(
            candidate=candidate, requirements=requirements, plan=plan,
            decisions=decisions, admissible_source_ids=admissible_source_ids,
        )

    def assess_transferability_shadow(self, report: RankingReport, retrieval: dict, *, batch_size: int = 3):
        """Read-only, source-audited Qwen judgments; not verified coverage or ranking."""
        from .semantic.transferability import assess_transferability_shadow
        if self.llm is None or not self.use_llm:
            raise ValueError("Transferability proposals require the live structured Qwen model")
        return assess_transferability_shadow(report, retrieval, self.llm, batch_size=batch_size)
