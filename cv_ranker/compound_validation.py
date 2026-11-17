"""Source-backed validation of JD compound expressions.

Standalone named alternatives are checked literally. Descriptive work clauses
are judged semantically by the already-validated assessment, with additional
source and conjunction safeguards. No new AI request or inferred JD criterion.
"""
from __future__ import annotations

import re

from .decision_contract import DecisionRecord
from .schemas import (CompoundCheck, CompoundComponent, DecisionTransition, EvidenceCitation,
                      RequirementAssessment, ValidatedRequirement)
from .segments import segment_resume
from .text_utils import (classify_requirement_tone, instruction_like_evidence,
                         phrase_present, normalize_whitespace, non_candidate_requirement_copy,
                         has_candidate_action)
from .assessor import _positive_literal_segment_is_capability_evidence


SUPPORTED_SECTIONS = {"skills", "inferred_skills", "experience", "projects", "summary", "other"}
# A summary explicitly claiming completed delivery is still a candidate claim;
# summary-only aspirations are excluded by the performed-action guard below.
_WORK_SECTIONS = {"experience", "work_experience", "projects", "summary"}
_COMPLETED_WORK = re.compile(
    r"\b(?:built|developed|designed|delivered|created|implemented|deployed|"
    r"launched|released|shipped|shipping|maintained|operated|integrated|configured|produced|"
    r"automated|managed|trained|evaluated|tested)\b", re.I,
)
_NEGATED_WORK = re.compile(
    r"\b(?:never|not|no|without|haven't|hasn't|didn't|doesn't)\b"
    r".{0,48}\b(?:built|developed|designed|delivered|created|implemented|"
    r"deployed|launched|released|maintained|operated|integrated|configured|"
    r"produced|automated|managed|trained|evaluated|tested)\b", re.I,
)
_ILLUSTRATIVE_SCOPE = re.compile(r"\b(?:including|such as|for example)\b|\be\.g\.", re.I)
_SCOPE_JOINERS = frozenset({
    "a", "an", "and", "or", "of", "for", "to", "on", "in", "by", "with",
    "during", "while", "through", "within", "across", "the", "at", "as",
    "both", "including", "experience", "knowledge", "ability", "skills",
    "hands-on", "exposure", "familiarity", "proficiency", "skilled",
})


def _work_anchors(text: str) -> set[str]:
    """Conservative *lexical* anchors; never a synonym or skill mapping.

    The first six characters allow grammatical variants such as 'corrective'
    and 'corrections' to share a source anchor. The model remains responsible
    for semantic equivalence; these anchors can only refuse a vague match.
    """
    units = re.findall(r"[A-Za-z][A-Za-z0-9+#]*(?:-[A-Za-z0-9+#]+)*", text)
    # Keep the complete hyphenated name as well as its meaningful parts:
    # 'safe-start' contains 'safe', while 'air-jet' retains its exact name.
    tokens = units + [part for unit in units if '-' in unit for part in unit.split('-')]
    return {word[:6].casefold() for word in tokens
            if ((len(word) >= 4 or (2 <= len(word) <= 5 and word.isupper()))
                and word.casefold() not in _SCOPE_JOINERS)}


def _and_clauses_are_grounded(statement: str,
                              citations: list[EvidenceCitation]) -> bool:
    """Every explicit mandatory AND arm needs *some* literal work anchor.

    This is a necessary, not sufficient, condition for accepting the previously
    validated model verdict. OR alternatives within an arm remain alternatives.
    No interpretation of ambiguous AND/OR precedence is invented.
    """
    mandatory = re.split(r"\s+and\s+", statement, flags=re.I)
    if len(mandatory) < 2:
        return True
    cited_anchors = set().union(*(_work_anchors(source.text) for source in citations))
    return all(
        # One standalone gerund is a general activity, not a separate subject
        # that must literally be named in every source ('Monitoring and
        # reporting ...' can be evidenced by the same reporting activity).
        bool(re.fullmatch(r"\s*[A-Za-z]{5,}ing\s*", arm, re.I))
        # An illustrative item AFTER "including" cannot replace a separate
        # mandatory activity BEFORE it: "manage deployments, including APIs"
        # requires deployment evidence, not merely an API mention.
        or bool(_work_anchors(re.split(r"\b(?:including|such as|for example)\b",
                                       arm, maxsplit=1, flags=re.I)[0])
                .intersection(cited_anchors))
        for arm in mandatory
    )


def _descriptive_work_options(req: ValidatedRequirement) -> bool:
    """Do not apply exact-tool lookup to natural-language job duties.

    Named skill pairs such as 'Python and Django' retain strict literal checks.
    The heuristic is grammatical only and does not enumerate professions.
    """
    c = req.constraint
    if c.operator == "complex":
        return True  # Additional conjunction and performed-work gates apply.
    # A real, multi-part performed-work sentence can be expressed as two
    # independent verbal actions ("investigate flaky tests AND document root
    # causes"). Its exact English inflections need not be verbatim in a CV.
    # Standalone A-and-B named skills still take strict option validation.
    if (c.operator == "all_of" and
            c.kind in {"responsibility", "experience", "other"} and
            all(len(option.split()) >= 3 for option in c.options)):
        return True
    if c.operator not in {"all_of", "any_of"}:
        return False
    return any(re.search(r"\b(?:of|for|with|during|within|through|while|"
                         r"across|using|including|to|by)\b", option, re.I)
               for option in c.options)


def _illustrative_experience(req: ValidatedRequirement,
                             item: RequirementAssessment) -> RequirementAssessment | None:
    """Preserve verified work for broad experience JDs with example alternatives.

    The word 'including' often supplies acceptable examples, NOT a requirement
    to satisfy each comma/or alternative. Keep the frozen JD as one criterion.
    This exception does not apply to numeric tenure, qualifications or skills.
    It grants no direct match from a skills list or an unperformed assertion.
    """
    c = req.constraint
    examples = _ILLUSTRATIVE_SCOPE.search(req.jd_evidence)
    if not (c.kind == "experience" and c.minimum_years is None
            and c.operator == "complex" and examples):
        return None
    # Never override an independently mandatory 'A and B' scope; the only
    # exempt shape is ONE broad work clause followed by an illustrative OR
    # list. Mixed AND/OR beyond that remains review-only and unscored.
    before = req.jd_evidence[:examples.start()]
    after = req.jd_evidence[examples.end():]
    if (re.search(r"\b(?:and|or)\b", before, re.I)
            or re.search(r"\band\b", after, re.I)
            or not re.search(r"\bor\b", after, re.I)):
        return None
    if item.status != "matched":
        # The model has not claimed a match. Keep its citations and uncertainty
        # intact; running a complex Boolean checker cannot improve that claim.
        return item.model_copy(update={
            "review_recommended": item.review_recommended or item.status == "uncertain",
        })
    valid_work = any(
        citation.section in _WORK_SECTIONS
        and _COMPLETED_WORK.search(citation.text)
        and not _NEGATED_WORK.search(citation.text)
        and not instruction_like_evidence(citation.text)
        and not non_candidate_requirement_copy(citation.text)
        for citation in item.evidence_segments
    )
    if valid_work:
        # The main assessor already validated citations and semantic meaning.
        # Preserve the optional HR-review flag, but record this as an accepted
        # illustrated clause in the audit rather than a pipeline failure.
        return item.model_copy(update={
            "review_recommended": True,
            "compound_check": CompoundCheck(
                operator="complex", outcome="matched",
                explanation=("The JD gives illustrative alternatives to one "
                             "broad experience requirement. Completed cited "
                             "work supports the overall requirement; the "
                             "examples are not separate mandatory AND items."),
            ),
        })
    return None


def _semantic_nonatomic_clause(req: ValidatedRequirement,
                               item: RequirementAssessment) -> RequirementAssessment | None:
    """Do not erase a cited model verdict solely because an AND/OR is long.

    A structural rule can verify short standalone alternatives, but it cannot
    decide which work duties satisfy a non-atomic shared object. Only a positive
    model verdict backed by *performed* original work is retained, with HR
    review explicitly requested. Each AND arm requires a source lexical anchor.
    This never promotes a negative, tentative, education or license claim.
    """
    c = req.constraint
    text = req.jd_evidence
    if (not _descriptive_work_options(req) or item.status != "matched"
            or c.kind in {"education", "certification", "license", "eligibility"}
            or not item.evidence_segments or not item.evidence_ids):
        return None
    has_and = bool(re.search(r"\band\b", text, re.I))
    has_or = bool(re.search(r"\bor\b", text, re.I))
    if not (has_and or has_or):
        return None
    performed_sources = [source for source in item.evidence_segments if (
        source.section in _WORK_SECTIONS
        and has_candidate_action(source.text)
        and not _NEGATED_WORK.search(source.text)
        and not re.search(r"\b(?:never|without|not|no|only\s+learning|"
                          r"planning\s+to|plan\s+to|intend\s+to|future|"
                          r"hypothetical|tutorial|currently\s+learning)\b",
                          source.text, re.I)
        and not instruction_like_evidence(source.text)
        and not non_candidate_requirement_copy(source.text)
    )]
    if not performed_sources or not _and_clauses_are_grounded(text, performed_sources):
        return None
    return item.model_copy(update={
        "review_recommended": True,
        "compound_check": CompoundCheck(
            operator=c.operator, outcome="matched",
            explanation=("The source-validated model accepted performed work "
                         "for this descriptive JD clause, with original citations "
                         "and work anchors for each mandatory AND part. Semantic "
                         "equivalence remains a model judgment requiring HR review."),
        ),
    })


def _component(name: str, req: ValidatedRequirement, segments) -> CompoundComponent:
    positive = []
    negative = []
    uncertain = []
    atomic_req = req.model_copy(update={"name": name})
    for seg in segments:
        if (seg.section not in SUPPORTED_SECTIONS or instruction_like_evidence(seg.text)
                or non_candidate_requirement_copy(seg.text)):
            continue
        if not phrase_present(name, seg.text):
            continue
        tone = classify_requirement_tone(seg.text, name, name)
        cited = EvidenceCitation(segment_id=seg.segment_id, section=seg.section, text=seg.text)
        if tone == "negated":
            negative.append(cited)
        elif tone == "uncertain":
            uncertain.append(cited)
        elif tone == "positive" and _positive_literal_segment_is_capability_evidence(atomic_req, seg):
            positive.append(cited)
    if positive and negative:
        return CompoundComponent(name=name, status="uncertain", evidence=positive[:1]+negative[:1], reason="Contradictory positive and negative source claims")
    if positive:
        return CompoundComponent(name=name, status="matched", evidence=positive[:2], reason="Literal capability claim in CV")
    if uncertain:
        return CompoundComponent(name=name, status="uncertain", evidence=uncertain[:2], reason="Learning-only or qualified evidence")
    if negative:
        return CompoundComponent(name=name, status="not_matched", evidence=negative[:2], reason="Explicit negative claim")
    return CompoundComponent(name=name, status="not_matched", reason="No source-qualified literal evidence")


def evaluate_compound(req: ValidatedRequirement, resume_text: str) -> CompoundCheck | None:
    constraint = req.constraint
    if constraint.operator == "single":
        return None
    if constraint.operator == "complex":
        return CompoundCheck(operator="complex", outcome="needs_review", explanation="Mixed or non-atomic Boolean wording; no precedence or equivalents inferred")
    options = constraint.options
    if (constraint.kind not in {"skill", "other"} or
        not (2 <= len(options) <= 3) or
        any(not 1 <= len(opt.split()) <= 4 or re.search(
            r"\b(?:years?|experience|knowledge|proficiency|qualified|certified|" 
            r"certification|license|degree|must|should|can|ability|using|with|in)\b", opt, re.I
        ) for opt in options) or
        len({normalize_whitespace(opt).casefold() for opt in options}) != len(options)):
        return CompoundCheck(operator=constraint.operator, outcome="needs_review", explanation="Option types or syntax cannot be evaluated safely as standalone skills")
    # Ensure every option really appears in the quoted frozen JD. Fail closed.
    if not all(phrase_present(opt, req.jd_evidence) for opt in options):
        return CompoundCheck(operator=constraint.operator, outcome="needs_review", explanation="Compound alternatives not grounded in frozen JD source")
    segments = segment_resume(resume_text)
    components = [_component(option, req, segments) for option in options]
    statuses = [c.status for c in components]
    if constraint.operator == "all_of":
        outcome = "not_matched" if "not_matched" in statuses else ("uncertain" if "uncertain" in statuses else "matched")
    else:
        outcome = "matched" if "matched" in statuses else ("uncertain" if "uncertain" in statuses else "not_matched")
    return CompoundCheck(operator=constraint.operator, outcome=outcome, components=components,
                         explanation="Evaluated explicit JD alternatives independently using literal source claims; no synonym or transferable-skill credit")


def apply_compound_checks(*, requirements: list[ValidatedRequirement],
                          assessments: list[RequirementAssessment], resume_text: str
                          ) -> tuple[list[RequirementAssessment], list[str], bool]:
    by_id = {r.requirement_id: r for r in requirements}
    result = []
    notes = []
    changed = False
    for item in assessments:
        if item.assessment_state == "unverified":
            result.append(item)
            continue
        requirement = by_id[item.requirement_id]
        # A reviewed nested expression outranks both the descriptive gerund
        # shortcut and the short standalone Boolean parser. Every positive
        # needs source-bound facet adjudication against this approved tree.
        if (requirement.constraint.approved_expression is not None
                or requirement.constraint.approved_mandatory_parts
                or requirement.constraint.approved_alternative_groups) and item.status == "matched":
            check = CompoundCheck(operator=requirement.constraint.operator,
                                  outcome="needs_review",
                                  explanation="Approved JD condition tree requires full source-bound leaf verification")
            result.append(item.model_copy(update={
                "status": "uncertain", "assessment_state": "unverified",
                "unified_status": None, "compound_check": check,
                "current_decision": DecisionRecord(processing_state="pending",
                    explanation="Source-bound assessment of approved JD conditions is scheduled"),
                "review_recommended": True,
                "decision_trace": [*item.decision_trace, DecisionTransition(
                    stage="compound_review", from_status=item.unified_status or item.status,
                    to_status="Unverified", reason_code="jd_syntax_needs_review",
                    evidence_ids=list(item.evidence_ids))],
            }))
            changed = True
            continue
        illustrated = _illustrative_experience(requirement, item)
        if illustrated is not None:
            result.append(illustrated)
            if item.status == "uncertain":
                notes.append(
                    f"{item.requirement_id}: descriptive experience evidence remains "
                    "uncertain; human review is required."
                )
            continue
        nonatomic = _semantic_nonatomic_clause(requirement, item)
        if nonatomic is not None:
            result.append(nonatomic)
            continue
        # The specialist validators already verified numeric tenure and
        # degree/credential claims against their actual source lines. A
        # syntactic "or" in an experience JD must NOT wipe a sufficient
        # four-year check into Unknown after that stronger check has run.
        # Keep general non-numeric compound skills on this conservative path.
        if ((requirement.constraint.kind == 'experience' and item.experience_check is not None) or
                (requirement.constraint.kind in {'education', 'certification', 'license'}
                 and item.qualification_check is not None)):
            result.append(item)
            continue
        check = evaluate_compound(requirement, resume_text)
        if check is None:
            result.append(item)
            continue
        # The syntax review must not erase a PREVIOUSLY source-validated
        # relationship. Preserve only narrow, independently checkable cases:
        # (1) an ordinary knowledge skill explicitly claimed in an affirmative
        #     candidate source; the full frozen claim must appear there;
        # (2) completed, positively stated adjacent work, which can support
        #     an existing Transferable proposal but never direct Found credit.
        # Other complex clauses stay review-only until their JD conditions
        # have been approved; this is important for "both A and B" cases.
        if check.outcome == "needs_review":
            original_by_id = {s.segment_id: s for s in segment_resume(resume_text)}
            prior_source = bool(
                item.evidence_ids and item.evidence_segments and
                {s.segment_id for s in item.evidence_segments}.issuperset(item.evidence_ids)
                and all(sid in original_by_id for sid in item.evidence_ids)
            )
            cited = [s for s in item.evidence_segments if (
                s.segment_id in item.evidence_ids
                and s.segment_id in original_by_id
                and s.text == original_by_id[s.segment_id].text
                and s.section == original_by_id[s.segment_id].section
                and not instruction_like_evidence(s.text)
                and not non_candidate_requirement_copy(s.text)
            )]
            explicit_knowledge = (
                prior_source and item.status == "matched"
                and requirement.constraint.kind == "skill"
                and not re.search(r"\bboth\b", requirement.jd_evidence, re.I)
                and any(s.section in {"skills", "inferred_skills"}
                        and phrase_present(requirement.jd_evidence, s.text)
                        and classify_requirement_tone(s.text, requirement.name,
                                                      requirement.jd_evidence) == "positive"
                        and _positive_literal_segment_is_capability_evidence(
                            requirement, original_by_id[s.segment_id])
                        for s in cited)
            )
            completed_related_work = (
                prior_source and item.status != "matched"
                and item.unified_status == "Transferable"
                and any(s.section in _WORK_SECTIONS
                        and not _NEGATED_WORK.search(s.text)
                        for s in cited)
            )
            if explicit_knowledge or completed_related_work:
                result.append(item.model_copy(update={
                    "compound_check": check,
                    "review_recommended": True,
                    "decision_trace": [*item.decision_trace, DecisionTransition(
                        stage="compound_review", from_status=item.unified_status or item.status,
                        to_status=item.unified_status or item.status,
                        reason_code="syntax_review_not_candidate_failure",
                        evidence_ids=list(item.evidence_ids),
                    )] if not any(t.stage == "compound_review" and
                                 t.reason_code == "syntax_review_not_candidate_failure"
                                 for t in item.decision_trace) else list(item.decision_trace),
                }))
                notes.append(
                    f"{item.requirement_id}: ambiguous JD conjunction requires "
                    "review; previously accepted positive source relationship "
                    "has not been interpreted as a negative."
                )
                continue
        # Non-preserved positive claims are NOT accepted as verified Found.
        status = "uncertain" if check.outcome == "needs_review" else check.outcome
        citations = []
        seen = set()
        for component in check.components:
            for citation in component.evidence:
                if citation.segment_id not in seen:
                    citations.append(citation)
                    seen.add(citation.segment_id)
        # For an uncertain/matched check source data should be visible, but
        # never repeat the original compound claim as proof of each component.
        update = {"status": status, "compound_check": check, "matched_term": None}
        if check.outcome == "needs_review" and item.status == "matched":
            # A syntax-only parser cannot disprove the model's cited work.
            # Keep original citations for bounded semantic adjudication and
            # withhold BOTH positive credit and a verified negative until it
            # resolves. This is a JD-meaning/evaluation gap, not a CV deficit.
            update.update({
                "assessment_state": "unverified", "unified_status": None,
                "current_decision": DecisionRecord(processing_state="pending",
                    explanation="Compound condition requires independent source review"),
                "review_recommended": True,
                "reason": (
                    "The frozen JD combines conditions whose semantic scope "
                    "the structural parser could not resolve. The cited "
                    "passage remains a review lead; no direct or negative "
                    "candidate judgment was established by this syntax check."
                ),
            })
        if status != item.status and check.outcome != "needs_review":
            details = '; '.join(
                f'{component.name}: {component.status.replace("_", " ")} '
                f'({component.reason})' for component in check.components)
            scope = {
                'all_of': 'all explicitly required parts',
                'any_of': 'at least one explicit alternative',
                'complex': 'the combined conditions',
            }[check.operator]
            update['reason'] = (
                f'The frozen JD requires {scope}. '
                f'Source checks found: {details or check.explanation}. '
                f'Final decision: {"Found" if status == "matched" else "Not Found" if status == "not_matched" else "review needed"}.'
            )
        if citations:
            update.update({"evidence_ids": [c.segment_id for c in citations],
                           "evidence_segments": citations,
                           "evidence": " | ".join(c.text for c in citations)})
        elif item.evidence_segments:
            # A syntactic veto does not make already source-validated excerpts
            # disappear. Keep them as *reviewed, uncredited* evidence; the
            # final status still controls scoring.
            update.update({"evidence_ids": list(item.evidence_ids),
                           "evidence_segments": list(item.evidence_segments),
                           "evidence": item.evidence, "matched_term": None})
        else:
            update.update({"evidence_ids": [], "evidence_segments": [], "evidence": None, "matched_term": None})
        if status != item.status:
            update["decision_trace"] = [*item.decision_trace, DecisionTransition(
                stage="compound_validation", from_status=item.status,
                to_status=status,
                reason_code=("jd_syntax_needs_review" if check.outcome == "needs_review"
                             else "explicit_compound_source_check"),
                evidence_ids=list(item.evidence_ids),
            )]
        new_item = item.model_copy(update=update)
        if new_item.status != item.status:
            changed = True
            notes.append(f"{item.requirement_id}: compound {check.operator}: {item.status} -> {status}; source-verified options, no alias inference")
        result.append(new_item)
    return result, notes, changed
