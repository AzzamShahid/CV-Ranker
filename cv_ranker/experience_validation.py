"""Phase 7B: document-grounded checks of explicit experience durations.

A conservative constraint evaluator, not a career-length calculator. Source
lines are assessed without embeddings, job dictionaries, or invented dates.
Only applicable to typed experience requirements with a numeric minimum.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import Field

from .schemas import EvidenceCitation, RequirementAssessment, StrictModel, ValidatedRequirement
from .segments import ResumeSegment, segment_resume
from .text_utils import instruction_like_evidence, phrase_present, classify_requirement_tone, requirement_tones_in_source


class DurationClaim(StrictModel):
    segment_id: str
    quote: str
    lower_years: float = Field(ge=0, le=100)
    upper_years: float | None = Field(default=None, ge=0, le=100)
    scope: Literal["named_subject", "general_experience", "unscoped"]
    tone: Literal["positive", "negated", "uncertain"]


class ExperienceCheck(StrictModel):
    outcome: Literal["sufficient", "insufficient", "ambiguous", "not_evidenced", "not_applicable"]
    minimum_years: float | None
    subject: str | None = None
    claims: list[DurationClaim] = Field(default_factory=list)
    explanation: str
    changed_status: bool = False


# Numbers have explicit year units; dates such as 2019-2022 are not parsed.
_DURATION = re.compile(
    r"(?<!\d)(?P<low>\d{1,2}(?:\.\d+)?)\s*"
    r"(?:(?P<plus>\+)|\s*(?P<range>-|–|to)\s*(?P<high>\d{1,2}(?:\.\d+)?))?"
    r"\s*(?:years?|yrs?)\b", re.I,
)
_CONTRADICTION = re.compile(
    r"\b(?:no|never|without|lack(?:s|ing)?|not|don't|doesn't|didn't)\b", re.I,
)
_JD_COPY = re.compile(
    r"\b(?:requirements?:|minimum\s+requirements?|"
    r"candidates?\s+(?:must|should)|applicants?\s+(?:must|should)|"
    r"(?:years?|yrs?)\s+(?:of\s+)?(?:experience\s+)?required)\b", re.I,
)
_LEARNING = re.compile(
    r"\b(?:learning|studying|coursework|theoretical|basic\s+(?:exposure|knowledge)|"
    r"interested\s+in|plan(?:ning)?\s+to|familiarizing)\b", re.I,
)
_EXPERIENCE_WORDS = re.compile(
    r"\b(?:experience|experienced|professional|worked|working|work|employee|employed|"
    r"practiced|practising|using|used|developer|engineer|officer|manager|analyst|"
    r"handled|managing|led|supervised|role|career|service)\b", re.I,
)


def _clauses(text: str) -> list[str]:
    """Splits conjunctive numeric statements, preserving 2.5 decimals."""
    return [s.strip() for s in re.split(r"(?<!\d)[.;](?!\d)|\n|,(?=\s)|\s+\band\b\s+(?=\d+(?:\.\d+)?\s*(?:\+|years?|yrs?))", text) if s.strip()]


def _duration_interval(clause: str, match: re.Match[str]) -> tuple[float, float | None]:
    lower = float(match.group('low'))
    high = float(match.group('high')) if match.group('high') else None
    before = clause[max(0, match.start()-25):match.start()].casefold()
    if match.group('range') and high is not None:
        return min(lower, high), max(lower, high)
    if match.group('plus') or re.search(r'(?:at\s+least|minimum(?:\s+of)?|over|more\s+than)\s*$', before):
        return lower, None
    if re.search(r'(?:up\s+to|less\s+than|under|fewer\s+than|at\s+most)\s*$', before):
        return 0.0, lower
    return lower, lower


def _scope(clause: str, subject: str | None, section: str) -> Literal['named_subject','general_experience','unscoped']:
    """Attribute numeric tenure only when its grammar explicitly binds subject.

    In particular, a title/skill printed next to "4 years of professional
    experience" is never sufficient. The model cannot create a connection
    between different physical lines by merging display segments.
    """
    # General career/work/overall experience is not subject-specific, even if
    # a technology or job title is mentioned elsewhere in the same clause.
    if re.search(r"(?i)\b\d+(?:\.\d+)?\s*\+?\s*(?:years?|yrs?)\s+of\s+"
                 r"(?:total|overall|general|professional|work|career|employment)\s+"
                 r"(?:work\s+)?experience\b", clause):
        return 'unscoped' if subject else 'general_experience'
    if subject:
        if len(clause) > 250 or not phrase_present(subject, clause):
            return 'unscoped'
        # An explicit subject inside a sentence about a different skill is not
        # enough; require a near-term grammatical relationship to years.
        term = re.escape(subject)
        years = r"\d{1,2}(?:\.\d+)?\s*(?:\+|\s*(?:-|–|to)\s*\d{1,2}(?:\.\d+)?)?\s*(?:years?|yrs?)"
        relationships = (
            rf"{years}\s+(?:of\s+)?(?:experience\s+)?(?:in|with|using|on|as)?\s*{term}\b",
            rf"{years}\s+of\s+{term}\s+(?:experience|work|development|practice)\b",
            rf"{years}\s+(?:of\s+)?experience\s+(?:with|in|using|on)\s+{term}\b",
            rf"{years}\s+as\s+(?:an?\s+)?{term}\b",
            rf"{term}\b\s+(?:experience\s*[:=-]?|for|using|with)\s*{years}\b",
        )
        if any(re.search(pattern, clause, re.I) for pattern in relationships):
            return 'named_subject'
        return 'unscoped'
    if _EXPERIENCE_WORDS.search(clause) or section == 'experience':
        return 'general_experience'
    return 'unscoped'


def _source_duration_clauses(source_lines: tuple[str, ...]) -> list[str]:
    """Rejoin only obviously incomplete PDF wraps containing a duration.

    A preceding standalone competency NEVER binds to years on the next line.
    Numeric source scopes are based on physical clauses, not display joins.
    """
    units: list[str] = []
    for line in source_lines:
        value = line.strip()
        if not value:
            continue
        previous = units[-1] if units else ''
        wrapped_years = bool(_DURATION.search(previous))
        incomplete = bool(re.search(r"(?i)\b(?:of|in|with|using|as|for|on)\s*$", previous))
        next_finishes_experience = bool(re.fullmatch(r"(?i)experience\s*\.?", value))
        if wrapped_years and (incomplete or next_finishes_experience):
            units[-1] = previous + ' ' + value
        else:
            units.append(value)
    return [clause for unit in units for clause in _clauses(unit)]


def _tone(clause: str, subject: str | None) -> Literal['positive','negated','uncertain']:
    if subject:
        scoped = classify_requirement_tone(clause, subject, subject)
        if scoped in {'uncertain','negated'}:
            return scoped
    if _CONTRADICTION.search(clause):
        return 'negated'
    if _LEARNING.search(clause):
        return 'uncertain'
    return 'positive'


def check_experience(
    requirement: ValidatedRequirement, resume_text: str,
    segments: list[ResumeSegment] | None = None,
) -> ExperienceCheck:
    """Test explicit numeric intervals against a typed JD minimum.

    `sufficient` requires an affirmatively scoped claim with a lower bound
    meeting the threshold and no contrary/limited same-subject claims.
    `insufficient` requires a finite upper bound below the threshold.
    Open-ended lower bounds (e.g. 2+ vs 5) are `ambiguous`, not `insufficient`.
    """
    c = requirement.constraint
    if c.kind != 'experience' or c.minimum_years is None:
        return ExperienceCheck(outcome='not_applicable', minimum_years=None,
                               explanation='No typed numeric experience constraint to enforce.')
    minimum = c.minimum_years
    if c.operator != 'single' or c.requires_review or c.origin == 'llm_suggestion':
        return ExperienceCheck(outcome='ambiguous', minimum_years=minimum, subject=c.subject,
                               explanation='The JD requirement itself needs confirmation; no automatic credit.')
    segments = segments if segments is not None else segment_resume(resume_text)
    claims: list[DurationClaim] = []
    standalone_subject = bool(c.subject and any(
        raw.strip().casefold() == c.subject.casefold() for raw in resume_text.splitlines()
    ))
    for segment in segments:
        if segment.section in {'education','certifications','achievements','metadata','non_candidate'} or instruction_like_evidence(segment.text):
            continue
        # Never infer a numeric relationship across physical lines joined for
        # readable LLM evidence. Preserve a single PDF-wrapped phrase only if
        # the prior physical line ends in an incomplete grammatical connector.
        source_lines = segment.source_lines or (segment.text,)
        for clause in _source_duration_clauses(source_lines):
            # Resume segmentation may merge a standalone skills line with the
            # next line. Do not treat "Python\n6 years total experience" as
            # six *Python* years merely because the segmenter joined them.
            if standalone_subject and c.subject and re.match(
                rf"^{re.escape(c.subject)}\s+\d+(?:\.\d+)?\s*(?:\+|years?|yrs?)", clause, re.I
            ):
                clause = clause[len(c.subject):].strip()
            for match in _DURATION.finditer(clause):
                if _JD_COPY.search(clause):
                    continue  # A copied job posting is not candidate experience.
                scoped = _scope(clause, c.subject, segment.section)
                if scoped == 'unscoped':
                    continue
                low, high = _duration_interval(clause, match)
                claims.append(DurationClaim(
                    segment_id=segment.segment_id, quote=clause[:500],
                    lower_years=low, upper_years=high, scope=scoped,
                    tone=_tone(clause, c.subject),
                ))
    if not claims:
        if c.subject:
            tones = requirement_tones_in_source(resume_text, c.subject)
            if 'negated' in tones and 'positive' not in tones:
                return ExperienceCheck(outcome='insufficient', minimum_years=minimum,
                                       subject=c.subject,
                                       explanation='The resume explicitly denies experience with the required subject.')
            if 'uncertain' in tones:
                return ExperienceCheck(outcome='ambiguous', minimum_years=minimum,
                                       subject=c.subject,
                                       explanation='The subject is mentioned only as learning/limited exposure, not quantified experience.')
        if c.subject:
            positive_subject = any(
                phrase_present(c.subject, seg.text)
                and classify_requirement_tone(seg.text, c.subject, c.subject) == 'positive'
                and not instruction_like_evidence(seg.text)
                and not _JD_COPY.search(seg.text)
                for seg in segments if seg.section not in {'education', 'certifications', 'metadata', 'non_candidate'}
            )
            # A clearly OTHER-subject claim (e.g. "4 years of sales
            # experience" for Procurement) is NOT an unspecified duration.
            # Distinguish it from "4 years of professional experience", where
            # role-related tenure genuinely remains ambiguous.
            generic_years = re.compile(
                r"(?i)\b\d+(?:\.\d+)?\s*\+?\s*(?:years?|yrs?)\s+"
                r"(?:of\s+)?(?:total\s+|overall\s+|general\s+|professional\s+|"
                r"work\s+|career\s+|employment\s+){0,3}"
                r"(?:work\s+)?(?:experience|employment|service|career)\b"
            )
            unscoped_years = any(
                not _JD_COPY.search(seg.text) and not instruction_like_evidence(seg.text)
                and any(generic_years.search(line) or re.fullmatch(
                    r"(?i)\s*\d+(?:\.\d+)?\s*\+?\s*(?:years?|yrs?)\s*\.?\s*", line
                ) for line in (seg.source_lines or (seg.text,)))
                for seg in segments if seg.section not in {'metadata', 'non_candidate'}
            )
            # A resume's target-role metadata is NOT experience proof, but
            # together with unscoped career years it is a reason for review.
            # Never automatically grant subject-specific years from a title.
            titled_subject = any(
                seg.section == 'metadata' and phrase_present(c.subject, seg.text)
                for seg in segments
            )
            if (positive_subject or titled_subject) and unscoped_years:
                return ExperienceCheck(outcome='ambiguous', minimum_years=minimum,
                                       subject=c.subject,
                                       explanation='The CV mentions the subject and an unscoped career duration separately; years cannot be attributed to the subject.')
        return ExperienceCheck(outcome='not_evidenced', minimum_years=minimum,
                               subject=c.subject, explanation='No explicit, appropriately scoped duration with valid year units was found.')
    if c.subject:
        source_tones = requirement_tones_in_source(resume_text, c.subject)
        if 'positive' in source_tones and ('negated' in source_tones or 'uncertain' in source_tones):
            return ExperienceCheck(outcome='ambiguous', minimum_years=minimum,
                                   subject=c.subject, claims=claims,
                                   explanation='Contradictory/learning-only and affirmative subject claims require review.')
        if 'negated' in source_tones and not any(x.tone == 'positive' for x in claims):
            return ExperienceCheck(outcome='ambiguous', minimum_years=minimum,
                                   subject=c.subject, claims=claims,
                                   explanation='Explicitly negated relevant experience needs human clarification.')
    positive = [x for x in claims if x.tone == 'positive']
    if len(positive) != len(claims):
        return ExperienceCheck(outcome='ambiguous', minimum_years=minimum,
                               subject=c.subject, claims=claims,
                               explanation='Negated, learning-only, or conflicting experience statements require review.')
    sufficient = [x for x in positive if x.lower_years >= minimum]
    inadequate = [x for x in positive if x.upper_years is not None and x.upper_years < minimum]
    if sufficient and inadequate:
        outcome = 'ambiguous'
        note = 'Different explicit experience durations conflict; manual clarification required.'
    elif sufficient:
        outcome = 'sufficient'
        note = 'Explicit subject-scoped years meet the JD minimum (unverified CV claim).'
    elif len(inadequate) == len(positive):
        outcome = 'insufficient'
        note = 'All explicit upper bounds are below the JD minimum.'
    else:
        outcome = 'ambiguous'
        note = 'Duration range or lower bound does not establish whether the minimum is met.'
    return ExperienceCheck(outcome=outcome, minimum_years=minimum,
                           subject=c.subject, claims=claims, explanation=note)


def apply_experience_checks(*, requirements: list[ValidatedRequirement],
                            assessments: list[RequirementAssessment],
                            resume_text: str) -> tuple[list[RequirementAssessment], list[str], bool]:
    """Gate unsupported LLM matches and attach reviewable numeric provenance.

    A missing source duration never becomes a verified `matched`. Clear
    positive experience can credit even a model negative ONLY when directly
    quantified and verbatim subject-scoped (no semantic substitution).
    """
    reqs = {r.requirement_id: r for r in requirements}
    segments = segment_resume(resume_text)
    source_by_id = {s.segment_id: s for s in segments}
    changed = False
    warnings: list[str] = []
    final: list[RequirementAssessment] = []
    for row in assessments:
        req = reqs[row.requirement_id]
        if req.constraint.kind != 'experience' or req.constraint.minimum_years is None:
            final.append(row)
            continue
        check = check_experience(req, resume_text, segments)
        status = row.status
        if check.outcome == 'sufficient':
            # Existing positive classifications stay positive. Direct literal
            # quantitative evidence can rescue a false negative without an
            # LLM guessing anything about synonyms or transferable skills.
            status = 'matched'
        elif check.outcome == 'insufficient':
            status = 'not_matched'
        elif check.outcome == 'ambiguous':
            status = 'uncertain'
        elif check.outcome == 'not_evidenced' and row.status in {'matched', 'uncertain'}:
            # Model confidence cannot turn an explicitly unrelated career
            # history into evidence of subject-specific tenure. Retain review
            # only if the CV actually mentions the target competency outside
            # a target-job title or copied requirements. The absence of a
            # numeric duration for a *claimed* competency still needs review.
            has_subject_claim = bool(check.subject) and any(
                seg.section not in {'education', 'certifications', 'metadata', 'non_candidate'}
                and phrase_present(check.subject, seg.text)
                and classify_requirement_tone(seg.text, check.subject, check.subject) == 'positive'
                and not instruction_like_evidence(seg.text)
                and not _JD_COPY.search(seg.text)
                for seg in segments
            )
            status = 'uncertain' if has_subject_claim else 'not_matched'
        if status != row.status:
            changed = True
            warnings.append(f'{req.requirement_id}: experience {check.outcome}; '
                            f'{row.status} -> {status}. {check.explanation}')
        check = check.model_copy(update={'changed_status': status != row.status})
        evidence = row.evidence
        ids = list(row.evidence_ids)
        citations = list(row.evidence_segments)
        # Always cite the actual numeric claim when a numeric decision changes.
        # Do not carry a wrong Qwen citation across the validation boundary.
        if check.claims:
            supporting = (next((x for x in check.claims if x.tone == 'positive'
                                and x.lower_years >= check.minimum_years), None)
                          if check.outcome == 'sufficient' else None)
            supporting = supporting or check.claims[0]
            segment = source_by_id[supporting.segment_id]
            evidence = segment.text
            ids = [segment.segment_id]
            citations = [EvidenceCitation(segment_id=segment.segment_id, section=segment.section, text=segment.text)]
        elif status != row.status:
            evidence = None
            ids = []
            citations = []
        final.append(row.model_copy(update={
            'status': status, 'evidence': evidence, 'evidence_ids': ids,
            'evidence_segments': citations,
            'experience_check': check,
        }))
    return final, warnings, changed
