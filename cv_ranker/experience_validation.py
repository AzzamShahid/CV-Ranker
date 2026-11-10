"""Phase 7B: document-grounded checks of explicit experience durations.

A conservative constraint evaluator, not a career-length calculator. Source
lines are assessed without embeddings, job dictionaries, or invented dates.
Only applicable to typed experience requirements with a numeric minimum.
"""
from __future__ import annotations

import re
from datetime import date
from itertools import combinations
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


class RoleTenureClaim(StrictModel):
    """A dated role plus its own following duties; work relevance is semantic."""
    role_segment_id: str
    duty_segment_ids: list[str] = Field(default_factory=list)
    raw_dates: str
    lower_years: float = Field(ge=0, le=100)
    start_month_index: int
    end_month_index: int


class ExperienceCheck(StrictModel):
    outcome: Literal["sufficient", "insufficient", "ambiguous", "not_evidenced", "not_applicable", "role_semantic"]
    minimum_years: float | None
    subject: str | None = None
    claims: list[DurationClaim] = Field(default_factory=list)
    role_tenure: list[RoleTenureClaim] = Field(default_factory=list)
    role_groups: list[list[RoleTenureClaim]] = Field(default_factory=list)
    explanation: str
    changed_status: bool = False


# Numbers have explicit year units; dates such as 2019-2022 are not parsed.
_NUMBER_WORDS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}
_YEAR_NUMBER = r"(?:\d{1,2}(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten)"
_DURATION = re.compile(
    rf"(?<![\w])(?P<low>{_YEAR_NUMBER})\s*"
    rf"(?:(?P<plus>\+)|\s*(?P<range>-|–|to)\s*(?P<high>{_YEAR_NUMBER}))?"
    r"\s*(?:years?|yrs?)\b", re.I,
)
_CONTRADICTION = re.compile(
    # Negation must govern the numeric work/experience claim. A clause such as
    # "4 years of professional nursing; no night shifts" still asserts tenure.
    r"\b(?:no|without|lack(?:s|ing)?)\s+"
    r"(?:(?:actual|paid|professional|relevant|practical|hands-on|direct)\s+){0,3}"
    r"(?:experience|work|employment|practice|service|years?)\b|"
    r"\b(?:never|not|don't|doesn't|didn't)\s+"
    r"(?:worked|employed|practiced|practised|served|held\s+a\s+job)\b",
    re.I,
)
_JD_COPY = re.compile(
    r"\b(?:requirements?:|minimum\s+requirements?|"
    r"candidates?\s+(?:must|should)|applicants?\s+(?:must|should)|"
    r"(?:years?|yrs?)\s+(?:of\s+)?(?:experience\s+)?required)\b", re.I,
)
_LEARNING = re.compile(
    # Bare 'learning' is a *domain word* in, e.g., '3 years of machine
    # learning/deep-learning research'. It is NOT evidence of studying or
    # limited ability. Classify learning-only duration by its actual grammar.
    r"\b(?:(?:currently|still|only|just)\s+learning|"
    r"learning\s+(?:about|to|from|via)|years?\s+of\s+learning|"
    r"studying|coursework|theoretical|basic\s+(?:exposure|knowledge)|"
    r"interested\s+in|plans?\s+to\s+learn|planning\s+to|familiarizing)\b", re.I,
)
# These patterns describe the relationship between a year count and a tenure
# claim, independent of industry. A work verb merely *somewhere in a line*
# cannot turn dataset coverage, ages or project timelines into employment.
_TENURE_BEFORE_DURATION = re.compile(
    r"\b(?:experience|employment|tenure|service|career|practice)\s*[:=\-]?\s*$|"
    r"\b(?:worked|working|employed|served|practiced|practised)\s+"
    r"(?:[\w-]+\s+){0,6}"
    r"(?:for|over|more\s+than|at\s+least)\s*$", re.I,
)
_TENURE_AFTER_DURATION = re.compile(
    r"^\s*(?:,?\s*(?:and\s+)?\d{1,2}\s*months?\b\s*)?"
    # Scope descriptors are ordinary resume tokens, including conjunctions
    # and punctuation within compound field names (e.g., quality/operations,
    # UI/UX, research & design). Dropping these tokens misclassifies a direct
    # statement of professional tenure as an unsupported dated-role guess.
    r"(?:of\s+(?:(?:[\w/&+-]+)\s+){0,5}"
    r"(?:experience|employment|service|practice|work|tenure)\b|"
    # E.g. '3 years of professional language research'. Research is work
    # tenure here because it is explicitly qualified as professional, not
    # because the CV's section happens to be named Experience.
    r"of\s+(?:professional|paid|full-time)\s+"
    r"(?:[\w/&+-]+\s+){0,5}"
    r"(?:research|operations|development|delivery|management|analysis)\b|"
    r"(?:professional\s+)?experience\b|"
    r"as\s+(?:an?\s+)?[\w-]+\b|"
    r"(?:working|employed|serving|practicing|practising)\b)", re.I,
)

_MONTH_NAMES = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5,
                "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10,
                "nov": 11, "dec": 12}
_MONTH_PATTERN = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
                  r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|"
                  r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)")
_ROLE_DATES = re.compile(
    rf"\b(?:(?P<start_month>{_MONTH_PATTERN})\.?\s+)?(?P<start_year>\d{{4}})\s*"
    rf"(?:-|–|—|to)\s*(?:(?P<end_month>{_MONTH_PATTERN})\.?\s+)?"
    r"(?P<end_year>\d{4}|present|current|ongoing)\b", re.I,
)
_ROLE_DUTY = re.compile(
    r"\b(?:built|developed|delivered|managed|trained|implemented|deployed|"
    r"created|designed|operated|maintained|led|supervised|performed|served|"
    r"conducted|integrated|evaluated|coordinated|provided|supported|"
    r"practiced|practised|worked|handled|architected|administered)\b", re.I,
)
_NEGATED_DUTY = re.compile(
    r"^\s*(?:(?:i|we)\s+)?(?:no|never|not|without|has\s+not|have\s+not|"
    r"did\s+not|haven't|hasn't|didn't)\b", re.I,
)


def _affirmative_duty(text: str) -> bool:
    return bool(_ROLE_DUTY.search(text) and not _NEGATED_DUTY.search(text)
                and not _CONTRADICTION.search(text)
                and not _LEARNING.search(text)
                and not _JD_COPY.search(text)
                and not instruction_like_evidence(text))


def related_experience_transfer_supported(row: RequirementAssessment) -> bool:
    """Only preserve the model's *unscored* overlap with real performed work.

    The numeric tenure/scope validator may veto Found. It must not erase a
    separately source-grounded finding that the person performed related
    work. No similarity score, title, dates, or aspiration establishes this.
    """
    return bool(row.unified_status == 'Transferable' and any(
        source.section in {'experience', 'projects', 'summary', 'work_experience'}
        and _affirmative_duty(source.text)
        for source in row.evidence_segments))


def _model_describes_related_work(reason: str) -> bool:
    """Recognize an *affirmative* reviewer-only overlap statement, not synonyms."""
    statement = (reason or '').casefold()
    if re.search(r'\b(?:unrelated|no\s+meaningful\s+overlap|does\s+not\s+overlap|'
                 r'not\s+(?:substantially\s+|meaningfully\s+)?related)\b', statement):
        return False
    return bool(re.search(r'\b(?:related|overlap(?:s|ping)?|transferable|adjacent)\b',
                          statement))


def _role_tenure(segments: list[ResumeSegment]) -> list[RoleTenureClaim]:
    """Derive conservative duration from a role header, never from a CV total.

    The period only establishes tenure IN THAT ROLE; the source-grounded LLM
    must independently assess the cited duties against the particular JD.
    Separate roles cannot silently lend each other their dates or duties.
    """
    headers: list[tuple[int, ResumeSegment, re.Match[str]]] = []
    for index, segment in enumerate(segments):
        if segment.section != "experience" or len(segment.text) > 230:
            continue
        match = _ROLE_DATES.search(segment.text)
        if match:
            headers.append((index, segment, match))
    claims: list[RoleTenureClaim] = []
    today = date.today()
    for position, (index, segment, match) in enumerate(headers):
        start_year = int(match.group("start_year"))
        # Bare YYYY - YYYY periods are bounded conservatively: start in
        # December and end in January unless the CV gives the months.
        start_month = (_MONTH_NAMES[match.group("start_month")[:3].casefold()]
                       if match.group("start_month") else 12)
        ending = match.group("end_year").casefold()
        if ending in {"present", "current", "ongoing"}:
            end_year, end_month = today.year, today.month
        else:
            end_year = int(ending)
            # A bare ending year does not establish an ending month: using
            # January is the conservative lower bound for dated work.
            end_month = (_MONTH_NAMES[match.group("end_month")[:3].casefold()]
                         if match.group("end_month") else 1)
        months = (end_year - start_year) * 12 + end_month - start_month
        if not 0 <= months <= 1200:
            continue
        next_index = (headers[position + 1][0] if position + 1 < len(headers)
                      else len(segments))
        duty_ids = []
        for duty in segments[index + 1:next_index]:
            if duty.section != "experience":
                break
            # The PDF sectioner may keep a later ALL-CAPS chapter heading
            # inside the Experience section. Its following paragraphs are
            # NOT automatically duties of the preceding dated employer.
            if (len(duty.text) < 110 and duty.text.isupper()
                    and not _ROLE_DATES.search(duty.text)):
                break
            if _affirmative_duty(duty.text):
                duty_ids.append(duty.segment_id)
        # Some text files/PDF parsers preserve the header and its first duty
        # in ONE original segment; its two physical lines may both be cited
        # by that single legitimate ID without fabricating a second source.
        if (len(segment.source_lines) >= 2
                and len(_ROLE_DATES.findall(segment.text)) == 1
                and any(_affirmative_duty(line)
                        for line in segment.source_lines[1:])):
            duty_ids.insert(0, segment.segment_id)
        if duty_ids:
            claims.append(RoleTenureClaim(
                role_segment_id=segment.segment_id,
                duty_segment_ids=duty_ids,
                raw_dates=match.group(0), lower_years=months / 12,
                start_month_index=start_year * 12 + start_month,
                end_month_index=end_year * 12 + end_month))
    return claims


def _role_months_without_double_counting(group: tuple[RoleTenureClaim, ...]) -> int:
    """Conservative union of employment intervals, not sum of overlapping jobs."""
    total = 0
    right = -1
    for role in sorted(group, key=lambda r: (r.start_month_index, r.end_month_index)):
        total += max(0, role.end_month_index - max(right, role.start_month_index))
        right = max(right, role.end_month_index)
    return total


def _qualifying_role_groups(roles: list[RoleTenureClaim], minimum: float
                            ) -> list[list[RoleTenureClaim]]:
    """Find small, source-citable candidate role sets for LLM scope judgment.

    Each role needs its OWN dated heading plus completed duty. Three roles
    require at most six original source citations. Dates are mere leads; no
    semantic match or point is produced by this calculation.
    """
    for count in range(1, min(3, len(roles)) + 1):
        groups = [list(group) for group in combinations(roles, count)
                  if _role_months_without_double_counting(group) >= minimum * 12]
        if groups:
            return groups[:5]
    return []


def _clauses(text: str) -> list[str]:
    """Splits conjunctive numeric statements, preserving 2.5 decimals."""
    return [s.strip() for s in re.split(r"(?<!\d)[.;](?!\d)|\n|,(?=\s)|\s+\band\b\s+(?=\d+(?:\.\d+)?\s*(?:\+|years?|yrs?))", text) if s.strip()]


def _duration_interval(clause: str, match: re.Match[str]) -> tuple[float, float | None]:
    lower = float(_NUMBER_WORDS.get(match.group('low').casefold(), match.group('low')))
    high = (float(_NUMBER_WORDS.get(match.group('high').casefold(), match.group('high')))
            if match.group('high') else None)
    before = clause[max(0, match.start()-25):match.start()].casefold()
    if match.group('range') and high is not None:
        return min(lower, high), max(lower, high)
    if match.group('plus') or re.search(r'(?:at\s+least|minimum(?:\s+of)?|over|more\s+than)\s*$', before):
        return lower, None
    if re.search(r'(?:up\s+to|less\s+than|under|fewer\s+than|at\s+most)\s*$', before):
        return 0.0, lower
    # Self-reported "2 years 4 months" is 2⅓ years, not 2 or 4. Only
    # accept an immediately adjacent month count; separate education/project
    # dates and standalone numbers must never inflate professional tenure.
    months = re.match(r"\s*(?:,?\s*(?:and\s+)?)?(\d{1,2})\s*months?\b",
                      clause[match.end():], re.I)
    if months and int(months.group(1)) < 12:
        lower += int(months.group(1)) / 12
    return lower, lower


# These are generic grammatical words, not a dictionary of occupations,
# degrees, tools, or skill equivalents. Relevant terms come from EACH JD.
_SCOPE_CONNECTORS = frozenset({
    'in', 'of', 'on', 'for', 'and', 'or', 'the', 'a', 'an', 'with', 'using',
    'develop', 'developing', 'developed', 'deliver', 'delivering', 'delivered',
    'building', 'built', 'working', 'work', 'relevant', 'professional',
    'experience', 'practical', 'minimum', 'at', 'least', 'powered',
    'related', 'including', 'such', 'as',
})
_GENERIC_WORK_NOUNS = frozenset({'software', 'system', 'systems', 'solutions',
                                 'application', 'applications', 'product', 'products'})


def _jd_scope_options(jd_statement: str) -> tuple[tuple[str, ...], ...]:
    """Extract source-word alternatives after 'experience' without aliases.

    This does not equate different technologies. It asks whether a *single
    physical duration claim* demonstrably concerns a JD-described work scope.
    """
    work = re.search(r"\bexperience\b\s+(.*)$", jd_statement, re.I)
    if not work or not work.group(1).strip():
        return ()
    detail = re.split(r"[.;]", work.group(1), maxsplit=1)[0]
    alternatives = re.split(r"\s*,\s*|\s+or\s+|\s*/\s*", detail, flags=re.I)
    result: list[tuple[str, ...]] = []
    for alternative in alternatives:
        tokens = tuple(word for word in re.findall(r"[a-z][a-z0-9]*", alternative.casefold())
                       if word not in _SCOPE_CONNECTORS)
        strong = tuple(token for token in tokens if token not in _GENERIC_WORK_NOUNS)
        if strong:
            result.append(strong)
        elif tokens:
            # "software development" is a real JD work scope, but broad
            # nouns should not need every marketing synonym in the CV.
            result.append((tokens[0],))
    return tuple(result)


def _jd_scope_applies(clause: str, alternatives: tuple[tuple[str, ...], ...]) -> bool:
    if not alternatives:
        return True
    source_tokens = set(re.findall(r"[a-z][a-z0-9]*", clause.casefold()))
    return any(all(term in source_tokens for term in alternative)
               for alternative in alternatives)


def _scope(clause: str, subject: str | None, section: str,
           jd_options: tuple[tuple[str, ...], ...] = (),
           duration_match: re.Match[str] | None = None) -> Literal['named_subject','general_experience','unscoped']:
    """Attribute numeric tenure only when its grammar explicitly binds subject.

    In particular, a title/skill printed next to "4 years of professional
    experience" is never sufficient. The model cannot create a connection
    between different physical lines by merging display segments.
    """
    # General career/work/overall experience is not subject-specific, even if
    # a technology or job title is mentioned elsewhere in the same clause.
    if subject:
        if len(clause) > 250 or not phrase_present(subject, clause):
            return 'unscoped'
        # An explicit subject inside a sentence about a different skill is not
        # enough; require a near-term grammatical relationship to years.
        term = re.escape(subject)
        years = rf"{_YEAR_NUMBER}\s*(?:\+|\s*(?:-|–|to)\s*{_YEAR_NUMBER})?\s*(?:years?|yrs?)"
        relationships = (
            rf"{years}\s+(?:of\s+)?(?:experience\s+)?(?:in|with|using|on|as)?\s*{term}\b",
            rf"{years}\s+of\s+(?:(?:relevant|professional|full-time|work)\s+)*{term}\s+(?:experience|work|development|practice)\b",
            rf"{years}\s+(?:of\s+)?(?:(?:relevant|professional|full-time|work)\s+)*experience\s+(?:with|in|using|on)\s+{term}\b",
            rf"{years}\s+as\s+(?:an?\s+)?{term}\b",
            rf"{term}\b\s+(?:experience\s*[:=-]?|for|using|with)\s*{years}\b",
        )
        if any(re.search(pattern, clause, re.I) for pattern in relationships):
            return 'named_subject'
        return 'unscoped'
    # The grammatical link must bind *this year count*, not a different
    # duration or a generic work verb elsewhere in the physical source line.
    # Sections are discovery hints: a PDF sectioner can leave unrelated
    # project coverage within the Experience section. Dated roles are handled
    # separately by _role_tenure.
    matched = duration_match or _DURATION.search(clause)
    if matched is None:
        return 'unscoped'
    before, after = clause[:matched.start()], clause[matched.end():]
    if ((_TENURE_BEFORE_DURATION.search(before) or
         _TENURE_AFTER_DURATION.search(after)) and
            _jd_scope_applies(clause, jd_options)):
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
    if c.origin == 'llm_suggestion':
        return ExperienceCheck(outcome='ambiguous', minimum_years=minimum, subject=c.subject,
                               explanation='The model-suggested JD requirement needs confirmation; no automatic credit.')
    review_semantics = c.operator != 'single' or c.requires_review
    jd_options = _jd_scope_options(requirement.jd_evidence) if not c.subject else ()
    # A source-defined OR is not a single literal skill called "A or B".
    # Evaluate each stated option as an alternative, using only tokens from
    # the frozen JD. No occupation-specific synonyms or broad inference.
    source_or_subject = bool(c.subject and re.search(r"\bor\b", c.subject, re.I)
                             and re.search(r"\bor\b", requirement.jd_evidence, re.I)
                             and not re.search(r"\band\b", requirement.jd_evidence, re.I))
    if source_or_subject:
        alternatives = re.split(r"\s+or\s+|\s*/\s*|\s*,\s*", c.subject, flags=re.I)
        source_options = tuple(
            tuple(word for word in re.findall(r"[a-z][a-z0-9]*", item.casefold())
                  if word not in _SCOPE_CONNECTORS)
            for item in alternatives
        )
        source_options = tuple(option for option in source_options if option)
        if len(source_options) >= 2:
            jd_options = source_options
        else:
            source_or_subject = False
    subject_for_scope = None if source_or_subject else c.subject
    segments = segments if segments is not None else segment_resume(resume_text)
    role_groups = _qualifying_role_groups(_role_tenure(segments), minimum)
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
                scoped = _scope(clause, subject_for_scope, segment.section, jd_options,
                                duration_match=match)
                if scoped == 'unscoped':
                    continue
                low, high = _duration_interval(clause, match)
                claims.append(DurationClaim(
                    segment_id=segment.segment_id, quote=clause[:500],
                    lower_years=low, upper_years=high, scope=scoped,
                    tone=_tone(clause, subject_for_scope),
                ))
    if not claims:
        if role_groups:
            return ExperienceCheck(outcome='role_semantic', minimum_years=minimum,
                                   subject=c.subject,
                                   role_tenure=list(role_groups[0]),
                                   role_groups=role_groups,
                                   explanation=(
                                       'One or more dated roles jointly meet the numeric minimum '
                                       'without double-counting overlapping dates, but the work '
                                       'scope must be established by model-cited duties within '
                                       'EVERY credited role; dates alone do not earn credit.'))
        if review_semantics:
            return ExperienceCheck(outcome='ambiguous', minimum_years=minimum,
                                   subject=c.subject, explanation=(
                                       'The JD includes a compound experience condition and the CV has no '
                                       'sufficiently scoped numeric statement; human review is required.'))
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
    if review_semantics and outcome == 'sufficient' and ((c.subject and not source_or_subject) or
            (c.operator == 'complex' and re.search(r'\band\b', requirement.jd_evidence, re.I)
             and not re.search(r'\bor\b', requirement.jd_evidence, re.I))):
        # Numeric years alone cannot prove the candidate met each alternative
        # or professional context in a compound condition.
        outcome = 'ambiguous'
        note = 'The year count reaches the threshold, but the JD work-scope alternatives still require review.'
    elif review_semantics and c.subject and outcome == 'insufficient':
        outcome = 'ambiguous'
        note = 'The work scope and numeric tenure need review; this clause alone does not establish all relevant years.'
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
        if row.assessment_state == "unverified":
            final.append(row)
            continue
        req = reqs[row.requirement_id]
        if req.constraint.kind != 'experience' or req.constraint.minimum_years is None:
            final.append(row)
            continue
        check = check_experience(req, resume_text, segments)
        status = row.status
        dated_heading_ids: list[str] = []
        if check.outcome == 'sufficient':
            # Existing positive classifications stay positive. Direct literal
            # quantitative evidence can rescue a false negative without an
            # LLM guessing anything about synonyms or transferable skills.
            status = 'matched'
        elif check.outcome == 'insufficient':
            status = 'not_matched'
        elif check.outcome == 'ambiguous':
            status = 'uncertain'
        elif check.outcome == 'role_semantic':
            # The model must have judged the actual completed duties relevant
            # and cited duties in EVERY role whose years are credited. Python
            # may then deterministically link those cited duties to their own
            # parsed dated headings. The dates alone never establish scope.
            cited = set(row.evidence_ids)
            credited = next((group for group in check.role_groups
                             if row.status == 'matched' and all(
                                 cited.intersection(role.duty_segment_ids)
                                 for role in group)), None)
            supported = credited is not None
            if credited:
                dated_heading_ids = [role.role_segment_id for role in credited
                                     if role.role_segment_id not in cited]
            status = ('matched' if supported else
                      'uncertain' if row.status == 'matched' else row.status)
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
        if dated_heading_ids and status == 'matched':
            # A source-ledger relationship, not another model inference:
            # include the missing original role dates with their cited duties.
            for sid in dated_heading_ids:
                if sid in source_by_id and sid not in ids:
                    ids.append(sid)
                    source = source_by_id[sid]
                    citations.append(EvidenceCitation(
                        segment_id=sid, section=source.section, text=source.text))
            evidence = ' '.join(c.text for c in citations)
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
        elif status != row.status and not citations:
            evidence = None
            ids = []
            citations = []
        # Preserve a *non-scoring* semantic overlap already evaluated by the
        # LLM when the numeric/scope contract prevents an exact match. The
        # original affirmative performed-work passage is mandatory. Merely
        # reaching the numeric career total, holding a title, or reproducing
        # the JD cannot establish even this reviewer-only transfer judgment.
        has_related_duty = any(
            seg.section in {'experience', 'projects', 'summary', 'work_experience'}
            and _affirmative_duty(seg.text) for seg in citations)
        transfer = bool(status != 'matched' and has_related_duty
                        and (row.unified_status == 'Transferable' or
                             (row.unified_status in {'Found', 'Not Found'}
                              and _model_describes_related_work(row.reason))))
        unified = 'Transferable' if transfer else row.unified_status
        reason = row.reason
        if transfer:
            reason = (
                'The cited CV describes completed professional work related to '
                'this JD, but its minimum duration in the specifically required '
                f'work scope is not established. {check.explanation} '
                'This is Transferable for HR review, not Found or numeric credit.'
            )
        elif status != row.status:
            reason = ('The cited experience does not establish the complete '
                      f'JD minimum: {check.explanation}')
        final.append(row.model_copy(update={
            'status': status, 'evidence': evidence, 'evidence_ids': ids,
            'evidence_segments': citations,
            'experience_check': check,
            'unified_status': unified, 'reason': reason,
            'review_recommended': row.review_recommended or check.outcome == 'role_semantic'
                                  or transfer,
        }))
    return final, warnings, changed
