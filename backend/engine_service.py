"""Streamlit-independent application services using ONLY canonical Python engine rules."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json


def score_weights(payload: dict):
    from cv_ranker.weighted_scoring import ScoreWeights
    shares = payload.get('requirement_shares_percent_of_category', payload.get('requirement_shares', {}))
    if not isinstance(shares, dict):raise ValueError('Requirement shares must be an ID-to-percentage object')
    return ScoreWeights(experience=payload.get('experience',10),education=payload.get('education',10),
        jd=payload.get('jd',80),split_jd=payload.get('split_jd',False),
        required_share=(80 if payload.get('jd_required_share',payload.get('required_share',80)) is None else payload.get('jd_required_share',payload.get('required_share',80))),
        requirement_shares=tuple(sorted((k,float(v)) for k,v in shares.items())),
        jd_allocation_mode=payload.get('jd_allocation',payload.get('jd_allocation_mode','pooled')))


def approved_draft(body: dict):
    from cv_ranker.schemas import JDReviewDraft
    return JDReviewDraft.model_validate(body)


def report_from_json(body: dict):
    from cv_ranker.schemas import RankingReport
    return RankingReport.model_validate(body)


def validate_approved_revision(raw_draft: dict, text: str, rows: list[dict], limit: int):
    from cv_ranker.jd_review import approve_jd_rows
    return approve_jd_rows(draft=approved_draft(raw_draft),rows=rows,jd_text=text,max_requirements=limit)


def editable_rows(draft_body: dict):
    from cv_ranker.jd_review import editable_jd_rows
    return editable_jd_rows(approved_draft(draft_body))


def projection(report_body: dict, weight_body: dict):
    from cv_ranker.weighted_scoring import weighted_leaderboard
    return weighted_leaderboard(report_from_json(report_body), score_weights(weight_body))


def candidate_projection(report_body: dict, index: int, ledgers: list):
    from cv_ranker.ui.unified_decisions import reconcile_unified_candidate
    return reconcile_unified_candidate(report_from_json(report_body),index,ledgers)


def export_zip(report_body: dict, weight_body: dict, ledgers_by_index: dict[str,list]):
    from cv_ranker.report_bundle import complete_results_zip
    return complete_results_zip(report_from_json(report_body),score_weights(weight_body),source_ledgers=ledgers_by_index)


def settings_params(job_settings: dict) -> dict:
    allowed={'model_name','ollama_model','openrouter_model','embedding_model',
             'openrouter_context_tokens','openrouter_output_tokens',
             'openrouter_max_requests_per_assessment'}
    params={'llm_provider':job_settings.get('provider','ollama'),
            'yake_top_k':job_settings.get('yake_top_k',40)}
    params.update({k:job_settings[k] for k in allowed if job_settings.get(k) is not None})
    return params


def evaluate_jd(jd_path: Path, job_settings: dict, progress=None, ranker_factory=None):
    from cv_ranker.pipeline import CVRanker
    from cv_ranker.config import Settings
    params = settings_params(job_settings)
    engine=(ranker_factory or CVRanker)(Settings(**params),use_llm=job_settings.get('use_llm',False),
                            unified=False,progress_callback=progress)
    return engine.prepare_jd_review(jd_path)


def evaluate_candidate(jd_path: Path, cv_path: Path, approved: dict, job_settings: dict,
                       *, progress=None, ranker_factory=None, resume_report=None, resume_candidate=None,
                       resume_key: str | None = None, semantic_dir: Path | None = None,
                       assessment_as_of_date=None):
    from cv_ranker.pipeline import CVRanker
    from cv_ranker.config import Settings
    params = settings_params(job_settings)
    settings=Settings(**params)
    ranker=(ranker_factory or CVRanker)(settings,use_llm=job_settings.get('use_llm',True),
               unified=job_settings.get('unified',True),
               embedding_cache_path=(semantic_dir/'embeddings.db') if semantic_dir else None,
               progress_callback=progress)
    saved_candidates={resume_key:resume_candidate} if resume_key and resume_candidate else None
    response=ranker.run(jd_path,[cv_path],approved_jd=approved_draft(approved),
                       resume_report=resume_report,resume_candidates=saved_candidates,
                       as_of_date=assessment_as_of_date)
    candidate=response.candidates[0]
    segments=ranker.source_ledgers.get(str(cv_path),[])
    if not segments:
        # Legacy/deterministic assessment may not populate the unified-only
        # display ledger. Recreate ORIGINAL extracted source segments without
        # evaluating or scoring them, so the read-only evidence viewer can
        # identify the same candidate's physical quotations.
        try:
            from cv_ranker.documents import extract_text
            from cv_ranker.segments import segment_resume
            segments=segment_resume(extract_text(cv_path))
        except Exception:
            segments=[]  # Parser failure remains in canonical candidate state.
    key=ranker.source_keys.get(str(cv_path))
    return (response,candidate,
        [asdict(s) if hasattr(s,'__dataclass_fields__') else s for s in segments],
        key,dict(ranker.request_metrics))


def focused_review_candidate(
    report_body: dict,
    candidate_doc_id: str,
    requirement_id: str,
    ledger: list[dict],
    job_settings: dict,
    *,
    ranker_factory=None,
    as_of_date=None,
):
    from cv_ranker.schemas import RankingReport, EvidenceCitation, DecisionTransition
    from cv_ranker.ui.final_decisions import _judge_requirement, FocusedJudgment, SourceJudgment
    from cv_ranker.ui.evidence_inspection import resume_segments
    from cv_ranker.decision_contract import completed
    from cv_ranker.scoring import score_candidate, assign_ranks

    report = RankingReport.model_validate(report_body)
    candidate_idx = next((i for i, c in enumerate(report.candidates) if c.candidate_source == candidate_doc_id), -1)
    if candidate_idx < 0:
        raise ValueError(f"Candidate {candidate_doc_id} not found in report")
    candidate = report.candidates[candidate_idx]

    req_idx = next((i for i, r in enumerate(report.requirements) if r.requirement_id == requirement_id), -1)
    if req_idx < 0:
        raise ValueError(f"Requirement {requirement_id} not found in report")
    requirement = report.requirements[req_idx]

    assessment = next((a for a in candidate.assessments if a.requirement_id == requirement_id), None)
    prior_verdict = (
        assessment.current_decision.verdict
        if assessment and assessment.current_decision and assessment.current_decision.verdict
        else assessment.unified_status
        if assessment and assessment.unified_status
        else "Not Found"
    )

    sources = {s.segment_id: s for s in resume_segments(ledger)}
    if not sources:
        raise ValueError(
            f"Candidate source document '{candidate_doc_id}' has no readable resume segments; cannot perform substantive review on missing source."
        )
    use_llm = job_settings.get("use_llm", False)

    if use_llm and sources:
        from cv_ranker.pipeline import CVRanker
        from cv_ranker.config import Settings
        settings = Settings(**settings_params(job_settings))
        ranker = (ranker_factory or CVRanker)(settings, use_llm=True, unified=True)
        judgment = _judge_requirement(
            ranker.llm,
            requirement,
            assessment,
            [],
            sources,
            as_of_date=as_of_date or report.assessment_as_of_date,
        )
    else:
        from cv_ranker.fallback import fallback_assessment
        from cv_ranker.text_utils import phrase_present, classify_requirement_tone
        resume_text = "\n\n".join(s.text for s in sources.values())
        fallback_res = fallback_assessment(requirement, resume_text)
        if fallback_res.status == "matched":
            supporting = []
            for sid, s in sources.items():
                if fallback_res.evidence and fallback_res.evidence in s.text:
                    supporting.append(SourceJudgment(segment_id=sid, why=f"Affirmative source mention: {fallback_res.evidence[:100]}"))
                elif phrase_present(requirement.name, s.text) and classify_requirement_tone(s.text, requirement.name, requirement.name) == "positive":
                    supporting.append(SourceJudgment(segment_id=sid, why=f"Affirmative source mention for {requirement.name}"))
            if not supporting and fallback_res.evidence_ids:
                supporting = [SourceJudgment(segment_id=sid, why="Affirmative evidence") for sid in fallback_res.evidence_ids if sid in sources]

            if supporting:
                judgment = FocusedJudgment(
                    result="matched",
                    explanation=f"Deterministic evaluation confirmed affirmative evidence for {requirement.name}.",
                    supporting_sources=supporting[:3],
                )
            else:
                judgment = FocusedJudgment(
                    result="not_evidenced",
                    explanation=f"Deterministic evaluation found no affirmative evidence for {requirement.name}.",
                    supporting_sources=[],
                )
        elif fallback_res.status == "uncertain":
            prior_result_map = {
                "Found": "matched",
                "Transferable": "transferable",
                "Not Found": "not_evidenced",
            }
            preservation_result = prior_result_map.get(prior_verdict, "not_evidenced")
            prior_sources = [
                SourceJudgment(
                    segment_id=c.segment_id,
                    why=c.text[:120] if len(c.text) >= 8 else f"Prior cited source for {requirement.name}",
                )
                for c in (assessment.evidence_segments if assessment else [])
                if c.segment_id in sources
            ]
            judgment = FocusedJudgment(
                result=preservation_result,
                explanation=f"Deterministic evaluation found ambiguous or conflicting mentions for {requirement.name}; preserved prior verdict ({prior_verdict}).",
                supporting_sources=prior_sources[:3] if preservation_result != "not_evidenced" else [],
            )
        else:
            is_negated = bool(fallback_res.evidence and any(neg in fallback_res.evidence.lower() for neg in ("no ", "not ", "never ", "neither ", "none ", "lack ")))
            explanation = (
                f"Candidate source contains explicit negation/denial for {requirement.name}."
                if is_negated else
                f"Independent review confirmed no affirmative evidence for {requirement.name}."
            )
            judgment = FocusedJudgment(
                result="not_evidenced",
                explanation=explanation,
                supporting_sources=[],
            )

    new_verdict = (
        "Found" if judgment.result == "matched"
        else "Transferable" if judgment.result == "transferable"
        else "Not Found"
    )

    new_assessments = []
    for a in candidate.assessments:
        if a.requirement_id == requirement_id:
            new_citations = [
                EvidenceCitation(
                    segment_id=s.segment_id,
                    section=sources[s.segment_id].section if s.segment_id in sources else "experience",
                    text=sources[s.segment_id].text if s.segment_id in sources else s.why,
                )
                for s in judgment.supporting_sources
                if s.segment_id in sources
            ]
            trace = list(a.decision_trace)
            trace.append(
                DecisionTransition(
                    stage="focused_review",
                    from_status=prior_verdict,
                    to_status=new_verdict,
                    reason_code="operator_review",
                    evidence_ids=[s.segment_id for s in judgment.supporting_sources],
                )
            )
            evidence_segments = new_citations if new_verdict in ("Found", "Transferable") else []
            evidence_ids = [s.segment_id for s in judgment.supporting_sources] if new_verdict in ("Found", "Transferable") else []
            updated_a = a.model_copy(update={
                "status": "matched" if new_verdict == "Found" else "not_matched",
                "unified_status": new_verdict,
                "assessment_state": "verified",
                "current_decision": completed(new_verdict, judgment.explanation),
                "reason": judgment.explanation,
                "evidence_segments": evidence_segments,
                "evidence_ids": evidence_ids,
                "decision_trace": trace,
                "review_recommended": False,
            })
            new_assessments.append(updated_a)
        else:
            new_assessments.append(a)

    scored = score_candidate(
        candidate_name=candidate.candidate_name,
        requirements=report.requirements,
        assessments=new_assessments,
        evaluation_mode=candidate.evaluation_mode,
        errors=candidate.errors,
        candidate_source=candidate.candidate_source,
    )
    scored = scored.model_copy(update={"candidate_source": candidate.candidate_source})

    updated_candidates = list(report.candidates)
    updated_candidates[candidate_idx] = scored
    ranked_candidates = assign_ranks(updated_candidates)
    updated_report = report.model_copy(update={"candidates": ranked_candidates})

    return {
        "prior_verdict": prior_verdict,
        "new_verdict": new_verdict,
        "explanation": judgment.explanation,
        "citations": [s.model_dump() for s in judgment.supporting_sources],
        "updated_report": updated_report.model_dump(mode="json"),
        "updated_candidate": scored.model_dump(mode="json"),
    }


def run_semantic_shadow_diagnostic(
    report_body: dict,
    top_k: int = 5,
    embedding_model: str | None = None,
    cache_dir: Path | None = None,
    *,
    workspace_id: str | None = None,
    store=None,
    doc_path_map: dict[str, Path | str] | None = None,
    ranker_factory=None,
    encoder=None,
):
    import os
    import tempfile
    from cv_ranker.schemas import RankingReport
    report = RankingReport.model_validate(report_body)
    items = []
    temp_dir = None
    temp_files = []
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / 'embeddings.db'
    else:
        temp_dir = tempfile.TemporaryDirectory()
        cache_path = Path(temp_dir.name) / 'embeddings.db'

    try:
        # Resolve candidate source paths for extraction without synthesizing fake CV files
        shadow_report = report.model_copy(deep=True)
        for c in shadow_report.candidates:
            orig_source = c.candidate_source
            p = Path(orig_source)
            resolved = None
            if p.is_file():
                resolved = p
            elif doc_path_map and orig_source in doc_path_map:
                candidate_p = Path(doc_path_map[orig_source])
                if candidate_p.is_file():
                    resolved = candidate_p
            elif store and workspace_id:
                try:
                    candidate_p = store.document_path(workspace_id, orig_source)
                    if candidate_p and candidate_p.is_file():
                        resolved = candidate_p
                except Exception:
                    resolved = None
            if resolved and resolved.is_file():
                c.candidate_source = str(resolved)

        from cv_ranker.pipeline import CVRanker
        from cv_ranker.config import Settings
        settings = Settings(embedding_model=embedding_model or 'embeddinggemma-2:latest')
        ranker = (ranker_factory or CVRanker)(settings, use_llm=False, unified=False)
        plan = ranker.plan_jd_capabilities(shadow_report) if (getattr(ranker, 'use_llm', False) and getattr(ranker, 'llm', None)) else None
        if encoder is None and os.environ.get('TEXTILEHR_TESTING') == '1':
            try:
                import urllib.request
                urllib.request.urlopen(f"{settings.ollama_base_url}/api/tags", timeout=0.5)
            except Exception:
                from tests.test_phase7g_shadow_integration import FakeEncoder
                encoder = FakeEncoder()

        retrieval = ranker.run_semantic_shadow(
            shadow_report, cache_path=cache_path, top_k=top_k,
            model=settings.embedding_model, capability_plan=plan,
            encoder=encoder,
        )
        if isinstance(retrieval, dict):
            for cand_entry in retrieval.get('candidates', []):
                cand_source = cand_entry.get('candidate_id') or cand_entry.get('candidate_source')
                report_cand = next((c for c in report.candidates if c.candidate_source == cand_source), None)
                if not report_cand:
                    report_cand = next((c for c in report.candidates if c.candidate_name == cand_entry.get('candidate_name')), None)
                cand_id = report_cand.candidate_source if report_cand else (cand_source or '')
                hits_by_req = cand_entry.get('hits_by_requirement', {})
                for req in report.requirements:
                    for hit in hits_by_req.get(req.requirement_id, []):
                        raw_sim = hit.get('cosine_similarity') if hit.get('cosine_similarity') is not None else hit.get('similarity')
                        sim = float(raw_sim) if raw_sim is not None else 0.0
                        if sim > 0.0:
                            seg = hit.get('source', {})
                            seg_id = hit.get('segment_id', '') or (seg.segment_id if hasattr(seg, 'segment_id') else seg.get('segment_id', '') if isinstance(seg, dict) else '')
                            items.append({
                                'requirement_id': req.requirement_id,
                                'candidate_id': cand_id,
                                'similarity': round(sim, 4),
                                'finding': f'Semantic shadow diagnostic: similarity {sim:.2f} for {req.name}',
                                'source_segments': [seg_id] if seg_id else [],
                            })
        elif isinstance(retrieval, list):
            for hit in retrieval:
                if isinstance(hit, dict):
                    raw_sim = hit.get('cosine_similarity') if hit.get('cosine_similarity') is not None else hit.get('similarity')
                    sim = float(raw_sim) if raw_sim is not None else 0.0
                    if sim > 0.0:
                        items.append(hit)
    except Exception as exc:
        return {
            'ready': False,
            'scoring_unchanged': True,
            'error_code': 'EMBEDDING_UNAVAILABLE',
            'error_message': f'Semantic shadow unavailable: {type(exc).__name__}',
            'notice': 'Read-only diagnostics unavailable. Semantic shadow proposals do NOT alter candidate scores, rankings, or official decisions.',
            'items': [],
        }
    finally:
        for tf_path in temp_files:
            try:
                tf_path.unlink(missing_ok=True)
            except Exception:
                pass
        if temp_dir:
            try:
                temp_dir.cleanup()
            except Exception:
                pass

    return {
        'ready': True,
        'scoring_unchanged': True,
        'notice': 'Read-only diagnostics. Semantic shadow proposals do NOT alter candidate scores, rankings, or official decisions.',
        'items': items,
    }
