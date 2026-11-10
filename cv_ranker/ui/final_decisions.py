"""One candidate-scoped decision per frozen requirement with original citations.

Reconcile direct CV claims, original evidence and functionally equivalent work.
The input V4 report is immutable; this is the final user-facing coverage view.
"""
from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import Field

from cv_ranker.evidence_bridge import performed_functional_bridge as _performed_functional_bridge
from cv_ranker.schemas import RankingReport, StrictModel
from cv_ranker.ui.evidence_inspection import literal_mentions, resume_segments
from cv_ranker.ui.semantic_workflow import semantic_candidate_rows
from cv_ranker.text_utils import instruction_like_evidence, non_candidate_requirement_copy, phrase_present


FinalStatus = Literal["Found", "Transferable", "Not Found"]


class SourceJudgment(StrictModel):
    segment_id: str
    why: str = Field(min_length=8)
    highlight_terms: list[str] = Field(default_factory=list)


class FocusedJudgment(StrictModel):
    result: Literal["matched", "transferable", "not_evidenced", "uncertain"]
    explanation: str = Field(min_length=12)
    supporting_sources: list[SourceJudgment] = Field(default_factory=list)


class CompactFocusedJudgment(StrictModel):
    """Retry shape for smaller models that fail nested citation schemas."""
    result: Literal["matched", "transferable", "not_evidenced", "uncertain"]
    explanation: str = Field(min_length=12)
    source_ids: list[str] = Field(default_factory=list)


_JUDGE_PROMPT = """You are the final source-grounded CV-to-JD adjudicator.
The CV is self-reported: determine what it CLAIMS, not the candidate's true expertise.
Return exactly the supplied structured schema. Judge ONLY the specified frozen
JD requirement using the supplied exact CV source segments. Do not invent evidence.

Rules:
- Reconcile the PRIMARY and SEMANTIC views. Preserve the more favorable
  SOURCE-SUPPORTED outcome. Do not downgrade a credible direct claim simply
  because another model missed it, gave no citation, or wanted project proof.
- A positive named skill in a skills list is sufficient for an ordinary skill
  requirement, EVEN without a work example. Label it "self-reported skill".
  Separate qualifications, years, professional application and explicit JD
  constraints still require their own evidence. Learning-only is not a skill claim.
- Recognize unambiguous standard names and acronyms for the SAME item without
  requiring a second project mention. Never confuse unrelated named products.
- A demonstrated activity can establish an implicit field or capability even
  when the JD phrase is absent, but only when performed work logically ENTAILS
  the requirement. Explain that inference using the exact action and source ID
  across ALL professions, not a predetermined skill dictionary.
- Building a comparable completed workflow with a DIFFERENT specifically
  named tool is TRANSFERABLE, not direct named-tool experience. Cite the
  performed actions, not merely the denial or similarity of tool names.
- IMPORTANT DISTINCTION: "has not used Tool X" prevents a DIRECT Tool X match,
  but DOES NOT disqualify a TRANSFERABLE outcome supported by independent
  performed work with another approach. If the CV describes built functions
  that it explicitly compares to Tool X, report transferable, cite BOTH the
  comparison and the performed activity, and explain the named-tool gap.
- A use denial, introductory study, copied job-ad, and hypothetical examples
  cannot demonstrate professional use. Treat a denial carefully: "not professionally"
  does not prove the person never studied/used it, but cannot establish work use.
- "rather than X", "without X", and "has not used X" are not affirmative
  X claims, even if a segment otherwise describes strong experience.
- Do not conflate adjacent tasks: preparatory inputs, related diagnostics or
  neighboring duties do not prove an independently requested output or task.
  A demonstration does not establish operational deployment, and a named skill
  does not establish years of its use. Respect explicit JD qualifiers, AND/OR,
  experience duration, education, licenses and certifications.
- For academic qualifications, distinguish the DEGREE LEVEL from the FIELD.
  The same completed level and explicitly required field is direct. A completed
  degree in a different but genuinely related discipline may be TRANSFERABLE
  if the JD does not itself accept that alternative. A degree in an unrelated
  discipline is NOT transferable merely because both are bachelor's degrees.
  Interpret field relationships dynamically, without assuming all fields are
  adjacent or relying on a fixed list of majors. Cite the actual education
  claim, and explain exactly which curricula/disciplinary competencies overlap.
  A pending, denied or lower qualification cannot be transferred into a
  completed degree. Transferability is for reviewer judgment, never a point.
- "matched" only when an exact claim or a sufficiently described performance of
  the ACTUAL JD capability is grounded in supplied segment IDs. Include at least
  one supporting source ID and why it proves that particular decision. For each
  source, give 1-3 exact short `highlight_terms` copied verbatim from its text.
- "transferable" when related work is shown but a named tool/requirement is NOT
  established. "not_evidenced" means the supplied CV does not establish it, NOT
  that the person cannot do it. "uncertain" only for material ambiguity/conflict.
- Every result, including not_evidenced and uncertain, needs a CONCRETE reason:
  what was shown, what is missing, and why. Cite the closest relevant segments
  if they explain a gap; do not invent an absence of skill.
- Respect the older assessment when supported, but explicitly reject a false
  favorable decision if its sole passage is negative or proves a different task.
"""


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().casefold()


def _positive(hit: dict[str, str]) -> bool:
    return hit["Finding"] in {"Explicit CV skill claim", "Named in work/project account"}


def _safe_citation(quote: str, original: str) -> bool:
    if not quote or not original:
        return False
    return _norm(quote) in _norm(original)


def _source_highlight_from_reason(source_text: str, *reasons: str) -> list[str]:
    """Recover one real phrase from model reasoning if it omits highlights.

    This only searches exact phrases inside original CV text; it never invents
    an absent skill name or treats a shared word as additional competence.
    """
    for reason in reasons:
        words = re.findall(r"[\w+#.-]+", reason or "")
        for count in (5, 4, 3, 2, 1):
            for start in range(len(words) - count + 1):
                term = " ".join(words[start:start + count])
                if len(term) >= 3 and term.casefold() not in {"the", "and", "this", "skill", "work"} and re.search(
                        rf"(?<![\w+#&]){re.escape(term)}(?![\w+#&])", source_text, re.IGNORECASE):
                    return [term]
    return []


def _proposals(report: RankingReport, index: int, semantic: Any) -> dict[str, list[dict]]:
    if semantic is None:
        return {}
    try:
        rows = semantic_candidate_rows(report, semantic, report.candidates[index].candidate_name)
    except (ValueError, TypeError, KeyError):
        return {}
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["Requirement ID"], []).append(row)
    return grouped


def _evidence_items(requirement: Any, assessment: Any, proposals: list[dict],
                    original: dict[str, Any], mentions: list[dict],
                    judgment: FocusedJudgment | None,
                    functional_bridge: tuple[str, str, list[str]] | None = None) -> list[dict]:
    """Union every cited source and literal checkpoint; never truncate to top-k."""
    items: dict[str, dict] = {}

    def include(sid: str, section: str, content: str, origin: str, why: str,
                *, trustworthy: bool = True, terms: list[str] | None = None) -> None:
        existing = items.setdefault(sid, {
            "Segment": sid, "Section": section, "Text": content,
            "Sources": [], "Why": [], "Highlight terms": [],
            "Validated against CV": trustworthy,
        })
        if sid in original:
            existing["Section"] = original[sid].section
            existing["Text"] = original[sid].text
        # A bad citation from one path cannot invalidate a separately verified
        # original source from the other path.
        existing["Validated against CV"] = existing["Validated against CV"] or trustworthy
        if origin not in existing["Sources"]:
            existing["Sources"].append(origin)
        if why and why not in existing["Why"]:
            existing["Why"].append(why)
        for term in terms or []:
            if term and re.search(re.escape(term), existing["Text"], re.IGNORECASE) and term not in existing["Highlight terms"]:
                existing["Highlight terms"].append(term)

    if assessment:
        for citation in assessment.evidence_segments:
            src = original.get(citation.segment_id)
            verified = not original or (src is not None and _safe_citation(citation.text, src.text))
            include(citation.segment_id, citation.section, citation.text, "V4 primary citation",
                    "Original V4 assessor cited this passage (initial assessment, not necessarily the final decision). " + (assessment.reason or
                    f"Its recorded decision was {assessment.status.replace('_', ' ')}."),
                    trustworthy=verified, terms=[assessment.matched_term] if assessment.matched_term else [])
        if assessment.qualification_check is not None:
            for claim in assessment.qualification_check.claims:
                original_segment = original.get(claim.segment_id)
                if original_segment is not None:
                    include(claim.segment_id, original_segment.section, original_segment.text,
                            "Typed qualification claim",
                            f"CV reports a {claim.state} {claim.degree_level or 'unspecified'} "
                            f"qualification in {claim.field_of_study or 'an unspecified field'}. "
                            "This is a document claim, not independently verified education.",
                            trustworthy=_safe_citation(claim.quote, original_segment.text),
                            terms=[claim.field_of_study] if claim.field_of_study else [])

    for row in proposals:
        for citation in row["Citations"]:
            sid = citation["segment_id"]
            src = original.get(sid)
            verified = src is not None and _safe_citation(citation["text"], src.text)
            include(sid, src.section if src else "source not retained",
                    src.text if src else citation["text"], "AI relationship citation",
                    f"Earlier AI considered this for {row['Capability ID']} (provisional relationship, not the final verdict). {row['Explanation']}",
                    trustworthy=verified)

    for hit in mentions:
        include(hit["Segment"], hit["Section"], hit["Text"], "CV wording cross-check",
                f"{hit['Finding']}; detected term: {hit['Source term']}.", terms=[hit["Source term"]])

    if judgment:
        for reason in judgment.supporting_sources:
            if reason.segment_id in original:
                src = original[reason.segment_id]
                include(reason.segment_id, src.section, src.text, "Focused final verification",
                        reason.why, terms=(reason.highlight_terms or
                                           _source_highlight_from_reason(src.text, reason.why, judgment.explanation)))
    if functional_bridge:
        comparison_id, work_id, terms = functional_bridge
        for sid, why in (
            (comparison_id, "The applicant explicitly compares completed alternative-tool functions with the named requirement; this is a CV claim about functional overlap, not direct tool use."),
            (work_id, "The applicant describes performed work with an alternative approach; shared source wording: " + ", ".join(terms) + "."),
        ):
            source = original[sid]
            include(sid, source.section, source.text, "Source-backed functional transfer review",
                    why, terms=terms)
    return sorted(items.values(), key=lambda item: (
        int(item["Segment"][1:]) if re.fullmatch(r"S\d+", item["Segment"]) else 10**9,
        item["Segment"],
    ))


def _verifiable_semantic_sources(proposals: list[dict], sources: dict[str, Any]) -> dict[str, Any]:
    used = {}
    for row in proposals:
        if row["Relationship"] not in {"direct", "transferable", "related_only"}:
            continue
        if row.get("Citation audit") not in {"source_validated", "validated", "source validated"}:
            continue
        for citation in row["Citations"]:
            original = sources.get(citation["segment_id"])
            if original is not None and _safe_citation(citation["text"], original.text):
                used[citation["segment_id"]] = original
    return used


def _representative_negative_checkpoints(checkpoints: list[dict], limit: int = 4) -> list[dict]:
    """Keep a small, varied sample of searched evidence for nonmatches.

    The full source ledger remains available on tab 03. Prefer explicit
    mention/denial checks, then cover skills, performed work, and projects.
    """
    if len(checkpoints) <= limit:
        return checkpoints
    chosen: list[dict] = []
    chosen_ids: set[str] = set()

    def include(checkpoint: dict) -> None:
        if len(chosen) < limit and checkpoint["Segment"] not in chosen_ids:
            chosen.append(checkpoint)
            chosen_ids.add(checkpoint["Segment"])

    for item in checkpoints:
        if "CV wording cross-check" in item["Sources"]:
            include(item)
    for section_group in ({"skills", "inferred_skills"}, {"experience", "work_experience"},
                          {"projects"}, {"summary"}):
        for item in checkpoints:
            if item["Section"] in section_group:
                include(item)
                break
    for item in checkpoints:
        include(item)
    return chosen


def _judge_requirement(llm: Any, requirement: Any, assessment: Any,
                       proposals: list[dict], sources: dict[str, Any]) -> FocusedJudgment:
    previous = {
        "primary": {"status": assessment.status if assessment else "missing",
                    "reason": assessment.reason if assessment else ""},
        "semantic": [{"relationship": row["Relationship"],
                      "capability": row["Capability ID"],
                      "explanation": row["Explanation"]} for row in proposals],
    }
    payload = {
        "frozen_requirement": {
            "id": requirement.requirement_id, "name": requirement.name,
            "priority": requirement.priority, "exact_jd_text": requirement.jd_evidence,
            "type": requirement.constraint.kind, "operator": requirement.constraint.operator,
            "alternatives_or_components": requirement.constraint.options,
            "minimum_years": requirement.constraint.minimum_years,
        },
        "previous_views_for_independent_verification": previous,
        "exact_cv_segments": [
            {"segment_id": sid, "section": segment.section, "text": segment.text}
            for sid, segment in sources.items()
        ],
    }
    import json
    flat_suffix = ("\nResponse: output result, explanation and source_ids only. "
                   "Use source IDs from exact_cv_segments. The same evidence rules apply.")
    prompt = json.dumps(payload, ensure_ascii=False)
    fits = getattr(llm, "prompt_fits", None)
    if callable(fits):
        # This is a *request-only* source window, not a modification of the
        # saved complete ledger or the final union of evidence checkpoints.
        # Sources enter in relevant/cited-first order from _review_sources.
        while payload["exact_cv_segments"] and not fits(_JUDGE_PROMPT + flat_suffix, prompt):
            payload["exact_cv_segments"].pop()
            prompt = json.dumps(payload, ensure_ascii=False)
        if not payload["exact_cv_segments"] or not fits(_JUDGE_PROMPT + flat_suffix, prompt):
            raise ValueError("Focused source context exceeds configured model budget")

    def flat_judgment() -> FocusedJudgment:
        compact = llm.invoke_structured(
            system_prompt=_JUDGE_PROMPT + flat_suffix,
            user_prompt=prompt, schema=CompactFocusedJudgment)
        if isinstance(compact, FocusedJudgment):
            # Test doubles / already structured provider responses are valid.
            return compact
        compact = (compact if isinstance(compact, CompactFocusedJudgment)
                   else CompactFocusedJudgment.model_validate(compact))
        return FocusedJudgment(
            result=compact.result, explanation=compact.explanation,
            supporting_sources=[SourceJudgment(segment_id=sid,
                why=compact.explanation[:450]) for sid in compact.source_ids],
        )

    if getattr(llm, "prefer_flat_focused_judgment", False):
        # A flat response is sufficient to recover exact original source
        # checkpoints. It is materially more portable across cloud endpoints
        # than an array of nested objects with constrained subfields.
        response = flat_judgment()
    else:
        try:
            raw = llm.invoke_structured(system_prompt=_JUDGE_PROMPT,
                                        user_prompt=prompt, schema=FocusedJudgment)
            response = raw if isinstance(raw, FocusedJudgment) else FocusedJudgment.model_validate(raw)
        except (ValueError, RuntimeError):
            response = flat_judgment()
    ids = {item.segment_id for item in response.supporting_sources}
    if len(ids) != len(response.supporting_sources) or not ids.issubset(sources):
        raise ValueError("Focused judge cited missing or repeated source IDs")
    if response.result in {"matched", "transferable"} and not ids:
        raise ValueError("Focused judge proposed a positive result without source IDs")
    for citation in response.supporting_sources:
        text = sources[citation.segment_id].text
        if any(term.casefold() not in text.casefold() for term in citation.highlight_terms):
            raise ValueError("Focused judge invented a highlighted source phrase")
    if response.result == "transferable":
        if requirement.constraint.kind == "education":
            # A related course of study is a legitimate academic transfer
            # claim, not evidence of a performed work project. The LLM must
            # cite a real, completed degree claim at the requested level.
            claims = (assessment.qualification_check.claims
                      if assessment and assessment.qualification_check else [])
            eligible = {claim.segment_id for claim in claims
                        if claim.state == "claimed" and claim.field_of_study
                        and claim.degree_level == requirement.constraint.degree_level}
            if not ids.intersection(eligible):
                raise ValueError("Academic transfer did not cite a completed degree at the required level")
        else:
            # A negation or a self-declared transferable label alone proves no
            # transferred skill. Require at least one cited account of performed work.
            performed = re.compile(
                r"\b(?:built|trained|implemented|developed|designed|delivered|created|"
                r"integrated|deployed|operated|evaluated|orchestrated|automated|maintained)\b", re.I)
            if not any(sources[sid].section in {"experience", "projects", "work_experience", "summary"}
                       and performed.search(sources[sid].text) for sid in ids):
                raise ValueError("Transferable proposal did not cite performed candidate work")
    return response


def _needs_judge(requirement: Any, assessment: Any, rows: list[dict],
                 positive_mentions: list[dict], sources: dict[str, Any]) -> bool:
    if not sources:
        return False
    direct = any(row["Relationship"] == "direct" and any(
        c["segment_id"] in sources for c in row["Citations"]
    ) for row in rows)
    transferable = any(row["Relationship"] == "transferable" and any(
        c["segment_id"] in sources for c in row["Citations"]
    ) for row in rows)
    ordinary_skill = requirement.constraint.kind == "skill" and requirement.constraint.operator == "single"
    if ordinary_skill and positive_mentions:
        return False
    if transferable and not direct and (assessment is None or assessment.status != "matched"):
        # Audited, performed-function transfer evidence is itself an accepted
        # final relationship; an extra LLM roundtrip is not needed.
        return False
    if assessment is None:
        return True
    if assessment.status == "matched":
        # Two agreeing models can still mistakenly equate related functions.
        # Implicit work matches are worth an independent, focused source check.
        return not positive_mentions and (direct or transferable)
    # The earlier semantic pass can fail or return uncited uncertainty. That
    # must not erase implicit ML, applied skills or functionally transferable
    # work: independently inspect the original candidate source in that case.
    return direct or transferable or assessment.status != "matched"


def _review_sources(original: dict[str, Any], mentions: list[dict],
                    validated: dict[str, Any], primary: Any) -> dict[str, Any]:
    """Bound review context without depending on failed semantic retrieval.

    Preserve explicit wording, skill lists, and completed project/work actions.
    Selection is domain-neutral, unlike a handcrafted skill equivalence map.
    """
    included = set(validated)
    included.update(hit["Segment"] for hit in mentions)
    if primary:
        included.update(c.segment_id for c in primary.evidence_segments if c.segment_id in original)
    scored = []
    for sid, segment in original.items():
        if (segment.section in {"non_candidate", "metadata"} or
                instruction_like_evidence(segment.text) or
                non_candidate_requirement_copy(segment.text)):
            continue
        rank = (0 if sid in included else
                1 if segment.section in {"skills", "inferred_skills"} else
                2 if segment.section == "projects" else
                3 if segment.section in {"experience", "work_experience"} else 4)
        scored.append((rank, int(sid[1:]) if re.fullmatch(r"S\d+", sid) else 10**9, sid, segment))
    ordered = sorted(scored)
    # Always keep cited or explicit term sources, then inspect surrounding
    # capabilities from the actual CV. Normal short CVs fit entirely.
    selected = [x for x in ordered if x[0] == 0] + [x for x in ordered if x[0] != 0][:40]
    return {sid: segment for _, _, sid, segment in selected}


def reconcile_candidate(report: RankingReport, candidate_index: int,
                        ledger: list[dict], semantic: Any = None,
                        llm: Any = None, max_focused_checks: int = 16) -> dict:
    """Construct the sole end-user table and all source-level explanations.

    ``llm`` is optional: only audited, truly disputed/implicit requirements get
    focused model calls. On failures we preserve honest review states.
    """
    candidate = report.candidates[candidate_index]
    originals = {segment.segment_id: segment for segment in resume_segments(ledger)}
    segments = list(originals.values())
    assessed = {item.requirement_id: item for item in candidate.assessments}
    proposals_by_id = _proposals(report, candidate_index, semantic)
    result: list[dict] = []
    warnings: list[str] = []
    if candidate.errors:
        warnings.append(
            f"Initial candidate assessment had {len(candidate.errors)} citation/response notice(s). "
            "These refer to the earlier pass; inspect the consolidated source verdicts separately."
        )
    if semantic is not None:
        completed = semantic.get("complete", True) if isinstance(semantic, dict) else getattr(semantic, "complete", True)
        if not completed:
            warnings.append(
                "The optional semantic verification was incomplete. Locally verified source evidence "
                "remains visible, but this candidate's assessment is provisional pending review."
            )
    calls = 0

    for req in report.requirements:
        primary = assessed.get(req.requirement_id)
        rows = proposals_by_id.get(req.requirement_id, [])
        mentions = literal_mentions(req, segments)
        affirmations = [hit for hit in mentions if _positive(hit)]
        denials = [hit for hit in mentions if "Explicit negative statement" in hit["Finding"]]
        validated = _verifiable_semantic_sources(rows, originals)
        direct = any(row["Relationship"] == "direct" and any(
            c["segment_id"] in validated for c in row["Citations"]
        ) for row in rows)
        transferable = any(row["Relationship"] == "transferable" and any(
            c["segment_id"] in validated for c in row["Citations"]
        ) for row in rows)
        primary_matched = primary is not None and primary.status == "matched"
        primary_uncertain = primary is None or primary.status == "uncertain"
        experience_check = primary.experience_check if primary else None
        qualification_check = primary.qualification_check if primary else None
        comparable_degree = bool(
            qualification_check is not None and qualification_check.kind == "education"
            and qualification_check.outcome == "mismatch"
            and req.constraint.field_of_study and req.constraint.degree_level
            and any(claim.state == "claimed" and claim.field_of_study
                    and claim.degree_level == req.constraint.degree_level
                    for claim in qualification_check.claims)
        )
        simple_skill = req.constraint.kind == "skill" and req.constraint.operator == "single"
        positive_skill = simple_skill and bool(affirmations) and not denials
        # A previously positive model status cannot win over a direct use denial
        # without independent affirmative evidence for that same named item.
        if simple_skill and denials and not positive_skill:
            primary_matched = False
        judge: FocusedJudgment | None = None
        review_sources = _review_sources(originals, mentions, validated, primary)
        wanted = _needs_judge(req, primary, rows, affirmations if positive_skill else [], review_sources)
        if experience_check is not None:
            # The primary pipeline already enforces exact quantitative tenure
            # constraints. An LLM cannot waive the minimum duration.
            wanted = False
        elif qualification_check is not None:
            # A strict degree mismatch remains Not Found for direct credit.
            # For completed SAME-LEVEL degrees in different stated fields,
            # allow an independent domain-general LLM related-field judgment.
            # A purely unrelated major must stay Not Found; the model must
            # explain academic relevance and cite the original degree claim.
            wanted = comparable_degree
        if wanted and llm is not None and calls < max_focused_checks:
            calls += 1
            # Provide both primary AND shadow sources, not only one path.
            try:
                judge = _judge_requirement(llm, req, primary, rows, review_sources)
            except Exception as exc:
                from cv_ranker.llm import LLMError
                diagnostic = str(exc) if isinstance(exc, LLMError) else type(exc).__name__
                # Provider exceptions are deliberately sanitized upstream;
                # never expose prompt text, provider bodies, or credentials.
                warnings.append(f"{req.requirement_id}: focused check unavailable ({diagnostic[:220]}); only independently supported evidence is counted.")
        elif wanted and calls >= max_focused_checks:
            warnings.append(f"{req.requirement_id}: focused-check budget reached; review source evidence.")
        elif wanted and llm is None and (direct or transferable):
            warnings.append(f"{req.requirement_id}: focused verification was not run; implicit evidence requires review.")

        adjudicated = judge.result if judge else None
        # Source-level explicit denials take precedence over a model's unsupported
        # claim of exact tool usage; related work can still be transferable.
        if (adjudicated == "matched" and simple_skill and denials and not positive_skill):
            warnings.append(f"{req.requirement_id}: a focused model match conflicted with an explicit named-skill denial; direct credit was blocked.")
            adjudicated = "transferable" if transferable else "uncertain"
        needs_review = False
        if adjudicated == "matched":
            status: FinalStatus = "Found"
            explanation = judge.explanation
        elif adjudicated == "transferable":
            status = "Transferable"
            explanation = judge.explanation
        elif adjudicated == "not_evidenced":
            status = "Not Found"
            explanation = judge.explanation
        elif adjudicated == "uncertain":
            status = "Not Found"
            explanation = judge.explanation
            needs_review = True
        elif primary_matched:
            status = "Found"
            cited = [c.segment_id for c in primary.evidence_segments if c.segment_id in originals]
            explanation = (primary.reason or
                           ("The original assessment cites CV source " + ", ".join(cited) +
                            " as evidence for this requirement." if cited else
                            "The earlier model reported a match but provided no verifiable source."))
            if not cited:
                status = "Not Found"
                explanation = "The recorded match has no accepted source segment to inspect."
                needs_review = True
            elif wanted and judge is None:
                # A second-pass timeout/failed citation cannot demote credible
                # earlier source-backed evidence just by being unavailable.
                explanation += " The second pass did not establish a reason to override this sourced result."
        elif positive_skill:
            status = "Found"
            source_ids = ", ".join(hit["Segment"] for hit in affirmations)
            explanation = (f"The CV affirmatively lists or reports {req.name} in source {source_ids}. "
                           "A separate project example is not required for an ordinary stated skill.")
        elif transferable:
            status = "Transferable"
            proposal_reasons = [r["Explanation"] for r in rows if r["Relationship"] == "transferable"]
            explanation = ("Comparable work is evidenced, but direct experience with the named requirement is not established. "
                           + (proposal_reasons[0] if proposal_reasons else ""))
        elif direct:
            status = "Not Found"
            explanation = ("AI cited possible direct evidence where the primary assessment did not. "
                           "A focused verification has not established the capability, so direct credit was withheld.")
            needs_review = True
        elif primary_uncertain:
            status = "Not Found"
            explanation = (primary.reason if primary and primary.reason else
                           "The available CV statements do not establish this requirement conclusively; review is possible.")
            needs_review = True
        else:
            status = "Not Found"
            explanation = ("No affirmative named claim or sufficiently supported functional evidence was found "
                           "for this requirement. This is an evidence gap, not proof the candidate lacks the ability.")

        if experience_check is not None:
            # Strict numeric decisions override *all* favorable source/LLM
            # routes, including a second-pass proposed match.
            if experience_check.outcome == "sufficient":
                status = "Found"
                explanation = (f"The JD requires at least {experience_check.minimum_years:g} years. "
                               f"An explicitly scoped CV duration meets that minimum. {experience_check.explanation}")
                needs_review = False
            elif experience_check.outcome in {"insufficient", "ambiguous", "not_evidenced"}:
                status = "Not Found"
                stated = "; ".join(c.quote[:160] for c in experience_check.claims[:2])
                explanation = (f"The JD requires at least {experience_check.minimum_years:g} years. "
                               + (f"CV duration statement: {stated}. " if stated else "")
                               + experience_check.explanation)
                needs_review = experience_check.outcome != "insufficient"
        if qualification_check is not None:
            if qualification_check.outcome == "satisfied":
                status = "Found"
                needs_review = False
                explanation = qualification_check.explanation
            elif comparable_degree and adjudicated == "transferable":
                status = "Transferable"
                needs_review = True  # Related field requires supervisor review.
                explanation = (judge.explanation + " This is a related qualification for "
                               "human review, not a direct match or scoring point.")
            else:
                status = "Not Found"
                needs_review = qualification_check.outcome == "ambiguous" or (comparable_degree and judge is None)
                explanation = qualification_check.explanation
                if comparable_degree and judge is None:
                    explanation += " The different academic field has not been verified as transferable."

        # The applicant may *deny using* a named framework while explicitly
        # comparing successfully implemented functions to it. A model that
        # equates "not used the tool" with "no transferable work" is not the
        # final authority. This narrow document-backed override requires a
        # separate performed-work segment and grants NO required/preferred point.
        bridge = None
        if (status == "Not Found" and simple_skill and not positive_skill
                and experience_check is None and qualification_check is None):
            bridge = _performed_functional_bridge(req, originals)
            if bridge:
                comparison_id, work_id, shared_terms = bridge
                status = "Transferable"
                explanation = (
                    f"The CV describes completed alternative-tool work (source {work_id}) "
                    f"and explicitly compares overlapping functions with {req.name} "
                    f"(source {comparison_id}; shared wording: {', '.join(shared_terms)}). "
                    f"Direct use of {req.name} is not established. This is CV-reported "
                    "functional transfer for human review, not a direct skill match or score."
                )
                needs_review = True
        if status == "Transferable":
            # Transferability is always a supervisor judgment, never an exact
            # Found score, even when both AI passes agree on an analogy.
            needs_review = True
        elif status == "Not Found" and any(row["Review flags"] for row in rows):
            # If the relationship audit specifically flags a potentially
            # overlooked skill, do not call the nonmatch fully resolved.
            needs_review = True

        checkpoints = _evidence_items(req, primary, rows, originals, mentions, judge, bridge)
        applied = any(item["Section"] in {"experience", "projects", "work_experience"} and
                      ("V4 primary citation" in item["Sources"] or
                       "Focused final verification" in item["Sources"] or
                       (status == "Found" and "AI relationship citation" in item["Sources"]))
                      for item in checkpoints if item["Validated against CV"])
        listed = any(hit["Section"] in {"skills", "inferred_skills"} for hit in affirmations)
        if status == "Found":
            level = "Described in work/projects" if applied else (
                "Stated in skills" if listed or any(item["Section"] in {"skills", "inferred_skills"}
                for item in checkpoints if "V4 primary citation" in item["Sources"]) else
                "CV-reported capability")
        elif status == "Transferable":
            level = "Comparable function, different tool/requirement"
        else:
            level = "Evidence inconclusive" if needs_review else "Not established by this CV"

        result.append({
            "ID": req.requirement_id, "Requirement": req.name,
            "Priority": req.priority.title(), "Result": status,
            "Evidence level": level, "Why": explanation,
            "JD source": req.jd_evidence, "Kind": req.constraint.kind,
            "Checkpoints": checkpoints, "Focused check": bool(judge),
            "Display checkpoints": (_representative_negative_checkpoints(checkpoints)
                                    if status == "Not Found" else checkpoints),
            "Total checkpoints considered": len(checkpoints),
            "Review recommended": needs_review,
            "Primary diagnostic": {
                "status": primary.status if primary else "missing",
                "reason": primary.reason if primary else "",
            },
            "AI diagnostic": [
                {"relationship": row["Relationship"], "capability": row["Capability ID"],
                 "reason": row["Explanation"], "source_ids": row["Source IDs"],
                 "review_flags": row["Review flags"]} for row in rows
            ],
        })
    return {
        "Candidate": candidate.candidate_name,
        "Required matched": sum(row["Result"] == "Found" and row["Priority"] == "Required" for row in result),
        "Required total": sum(row["Priority"] == "Required" for row in result),
        "Preferred matched": sum(row["Result"] == "Found" and row["Priority"] == "Preferred" for row in result),
        "Preferred total": sum(row["Priority"] == "Preferred" for row in result),
        "Transferable": sum(row["Result"] == "Transferable" for row in result),
        "Criteria": result,
        "Notices": warnings,
        "Provisional": bool(warnings) or any(row["Review recommended"] for row in result),
    }
