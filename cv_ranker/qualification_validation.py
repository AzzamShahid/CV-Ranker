"""Phase 7C: conservative, source-cited CV qualification claim validation.

This module verifies what the CV *states*, not credential authenticity. It has
no occupation catalogue, semantic skill aliases, provider lookup or database.
The employer's frozen JD remains the source of the requirement definition.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import Field

from .schemas import EvidenceCitation, RequirementAssessment, StrictModel, ValidatedRequirement
from .segments import ResumeSegment, _clean, segment_resume
from .text_utils import instruction_like_evidence, normalize_whitespace, phrase_present


class QualificationClaim(StrictModel):
    segment_id: str
    quote: str
    state: Literal['claimed', 'pending', 'denied', 'expired']
    degree_level: str | None = None
    field_of_study: str | None = None
    credential_name: str | None = None


class QualificationCheck(StrictModel):
    kind: Literal['education', 'certification', 'license']
    outcome: Literal['satisfied', 'mismatch', 'ambiguous', 'not_evidenced', 'field_semantic']
    explanation: str
    claims: list[QualificationClaim] = Field(default_factory=list)
    # A satisfied source claim is not proof that a credential is authentic.
    independently_verified: bool = False
    changed_status: bool = False


_DEGREE = re.compile(
    r"(?<!\w)(?P<label>ph\.?d\.?|doctorate|doctoral|master(?:'s)?(?:\s+of\s+(?:science|arts))?|"
    r"m\.?s\.?c?\.?|mba|bachelor(?:'s)?(?:\s+of\s+(?:science|arts))?|"
    # 'Research Associate' and 'Sales Associate' are JOB TITLES, not degrees.
    # An associate credential needs an explicit degree-bearing phrase.
    r"b\.?s\.?c?\.?|b\.?tech\.?|associate(?:'s)?\s+(?:degree|of\s+(?:arts|science))|diploma)"
    r"(?:\s+degree)?\b", re.I,
)
_CERT_WORD = re.compile(r'\b(?:certified|certification|certificate|credential)\b', re.I)
_LICENSE_WORD = re.compile(r'\b(?:licen[cs]e|licen[cs]ed|registration|registered)\b', re.I)
_PENDING = re.compile(
    r'\b(?:pursuing|in[ -]progress|ongoing|studying|currently\s+enrolled|'
    r'expected\s+(?:to\s+graduate|graduation|in\b|'
    r'(?:bachelor|master|doctorate|ph\.?d\.?|b\.?s\.?c?\.?|m\.?s\.?c?\.?|mba)\b)|'
    r'working\s+toward(?:s)?|'
    r'preparing\s+for|planning\s+to|intend(?:ing)?\s+to|hope\s+to|aim(?:ing)?\s+to|'
    r'will\s+(?:earn|obtain|complete)|can\s+earn|training\s+(?:for|on|in)|coursework|'
    r'course\s+(?:on|in)|applied\s+for|application\s+pending|exam\s+pending|'
    r'not\s+yet\s+(?:obtained|completed|certified|licensed)|'
    r'certification\s+(?:course|program|training)|certificate\s+course|incomplete)\b', re.I,
)
_DENIED = re.compile(
    r'\b(?:no\s+(?!restrictions?\b|limitations?\b|issues?\b)'
    r'(?:\w+(?:[\x27\u2019]s)?\s+){0,2}(?:degree|diploma|'
    r'qualification|certificate|certification|credential|license|licence|registration)|'
    r'never\s+(?:obtained|completed|graduated|qualified|certified|licensed|held)|'
    r'without\s+(?:an?\s+)?(?:degree|diploma|qualification|certificate|'
    r'certification|credential|license|licence)|'
    r'not\s+(?:certified|licensed|qualified|completed|graduated)|'
    r'did\s+not\s+(?:complete|obtain)|failed\s+to\s+(?:obtain|complete)|dropped\s+out|'
    r'not\s+(?:valid|active|current)|no\s+longer\s+(?:valid|active|current))\b', re.I,
)
_EXPIRED = re.compile(r'\b(?:expired|revoked|suspended|lapsed|invalid|withdrawn|cancelled|canceled)\b', re.I)
_NOT_EXPIRED = re.compile(
    r'\b(?:never|not|has\s+not|have\s+not|hasn\x27t|haven\x27t)\s+'
    r'(?:(?:been|become)\s+)?'
    r'(?:expired|revoked|suspended|lapsed|withdrawn|cancelled|canceled)\b', re.I,
)
_EXPIRY_UNVERIFIED = re.compile(r'\b(?:expires?|expir(?:y|ation)|valid\s+until|valid\s+through)\b', re.I)
_VALID = re.compile(r'\b(?:valid|active|current|in\s+good\s+standing)\b', re.I)
_JD_COPY = re.compile(r'\b(?:job\s+(?:requirements?|description|posting)|requirement(?:s)?|required|must\s+have|applicants?\s+must|candidates?\s+must)\b', re.I)
_STOP_FIELD = re.compile(
    r'\s+(?:at\b|from\b|graduated\b|completed\b|awarded\b|in\s+progress\b|'
    r'expected\b|currently\b|with\b|and\b|or\b|\d{4}\b)', re.I,
)


def _level(token: str) -> str | None:
    t = re.sub(r'[^a-z]', '', token.casefold())
    if t.startswith(('phd', 'doctor')):
        return 'doctorate'
    if t.startswith(('master', 'msc', 'mba')) or t == 'ms':
        return 'master'
    if t.startswith(('bachelor', 'bsc', 'btech')) or t == 'bs':
        return 'bachelor'
    if t.startswith('associate'):
        return 'associate'
    if t.startswith('diploma'):
        return 'diploma'
    return None


_ACADEMIC_RANK = {'associate': 1, 'bachelor': 2, 'master': 3, 'doctorate': 4}


def _degree_level_can_overlap(*, required: str | None, claimed: str | None) -> bool:
    """Level eligibility for *unscored* semantic review, not JD satisfaction.

    A completed higher academic award may be academically relevant to an
    exact-major lower-degree requirement, but it does not prove possession of
    that lower degree. Diploma equivalence is deliberately not inferred.
    Whether the subject areas actually overlap is left to the model/human.
    """
    return bool(required and claimed and (
        (required == claimed) or
        (required in _ACADEMIC_RANK and claimed in _ACADEMIC_RANK and
         _ACADEMIC_RANK[claimed] > _ACADEMIC_RANK[required])
    ))


def _state(text: str) -> Literal['claimed', 'pending', 'denied', 'expired']:
    if _EXPIRED.search(text) and not _NOT_EXPIRED.search(text):
        return 'expired'
    if _DENIED.search(text):
        return 'denied'
    if _PENDING.search(text) or _EXPIRY_UNVERIFIED.search(text):
        return 'pending'
    return 'claimed'


def _subject_key(text: str) -> str:
    return ' '.join(re.findall(r'[a-z0-9]+', text.casefold()))


def _field_equal(expected: str, observed: str) -> bool:
    a, b = _subject_key(expected), _subject_key(observed)
    if not a or not b:
        return False
    if a == b:
        return True
    # Initialisms only when mechanically exact, not semantic synonyms.
    if len(a.split()) >= 2 and ''.join(x[0] for x in a.split()) == b:
        return True
    if len(b.split()) >= 2 and ''.join(x[0] for x in b.split()) == a:
        return True
    return False


def _jd_requests_field_category(requirement: ValidatedRequirement) -> bool:
    """Recognize a *grammatical* family/related-field policy, not occupations.

    A family like 'computing programs' is a category; it is not the exact
    credential name the candidate should reproduce. Which subject belongs to
    that category remains for the source-grounded model/human, not a Python
    whitelist of degree disciplines.
    """
    text = requirement.jd_evidence.casefold()
    field = (requirement.constraint.field_of_study or '').casefold()
    return bool(
        re.search(r'\b(?:programs|programmes|fields|disciplines|majors|areas|specializations)\b', field)
        # Indefinite singular wording names a kind of programme, rather than
        # requiring those category words verbatim on the applicant's degree.
        # A definite named major (e.g. "Computer Science") remains exact.
        # Do not keep a catalogue of fields or award credit by this grammar.
        or re.fullmatch(
            r'(?:a|an|any|some)\s+(?:[\w-]+\s+){0,5}'
            r'(?:program|programme|field|discipline|major|area|specialization)',
            field.strip(), re.I)
        or re.search(r'\b(?:related|equivalent|similar)\s+'
                     r'(?:fields?|disciplines?|degrees?|programs?|programmes?|areas?)\b', text)
        or re.search(r'\bor\s+(?:a\s+|an\s+)?(?:closely\s+|directly\s+)?'
                     r'(?:related|equivalent)\b', text)
    )


def _degree_field(text: str, match: re.Match[str]) -> str | None:
    tail = text[match.end():].lstrip('.')
    field = re.match(r'\s+(?:(?:degree\s+)?in\s+|of\s+)([A-Za-z][A-Za-z0-9 &/.-]{0,75})', tail, re.I)
    if field is None:
        # In an education section, 'BSc Computer Science' is a named degree,
        # not a claim about unrelated previous work.
        field = re.match(r'\s+([A-Za-z][A-Za-z0-9 &/.-]{0,75})', tail)
    if field is None:
        return None
    value = re.split(r'[,;()]', field.group(1), maxsplit=1)[0]
    value = _STOP_FIELD.split(value, 1)[0].strip(' .-')
    if not value or value.casefold() in {'degree', 'science', 'arts', 'from', 'in'}:
        return None
    return value


def _line_claims(resume_text: str, segments: list[ResumeSegment]):
    """Original CV physical lines plus a mapped source ID, never fabricated lines."""
    candidates: list[tuple[str, ResumeSegment]] = []
    for line in resume_text.splitlines():
        # Use exactly the same PDF bullet normalization as the source ledger.
        # Otherwise \\uf0b7-prefixed degrees vanish while unrelated physical
        # lines prevent the joined-source fallback from activating.
        line = _clean(line)
        if not line or len(line) > 500:
            continue
        for seg in segments:
            if normalize_whitespace(line).casefold() in seg.text.casefold():
                candidates.append((line, seg))
                break
    # A physical PDF wrap can split "Bachelor of Science in" from its field.
    # The source ledger already preserves the original consecutive lines; add
    # that one grammatically incomplete phrase as a source-grounded candidate
    # without concatenating arbitrary independent education statements.
    for seg in segments:
        if seg.section not in {"education", "certifications"}:
            continue
        physical = [_clean(line) for line in seg.source_lines if _clean(line)]
        for previous, following in zip(physical, physical[1:]):
            if (_DEGREE.search(previous) and
                (re.search(r"\b(?:in|of)\s*$", previous, re.I)
                 or _DEGREE.fullmatch(previous)) and
                not re.search(r"[.!?]\s*$", previous)):
                candidates.append((previous + " " + following, seg))
    # PDF-wrapped statements need a joined-source fallback, but never join
    # separate physical lines to infer a qualification that is not present.
    if not candidates:
        candidates = [(seg.text, seg) for seg in segments if len(seg.text) <= 300]
    return [(line, seg) for line, seg in candidates
            if not instruction_like_evidence(line) and not _JD_COPY.search(line)]


def _education(requirement: ValidatedRequirement, lines) -> QualificationCheck:
    c = requirement.constraint
    expected_level = c.degree_level
    expected_field = c.field_of_study
    claims: list[QualificationClaim] = []
    compatible: list[QualificationClaim] = []
    broad_category = bool(expected_field and _jd_requests_field_category(requirement))
    same_level: list[QualificationClaim] = []
    for line, seg in lines:
        for m in _DEGREE.finditer(line):
            level = _level(m.group('label'))
            if level is None:
                continue
            # Bare BS/MS in a Skills section can mean a tool or abbreviation.
            # Require an explicit 'in <field>' outside Education for these forms.
            compact = re.sub(r'[^a-z]', '', m.group('label').casefold())
            if compact in {'bs', 'ms'} and seg.section != 'education' and not re.match(
                r'\s+(?:degree\s+)?in\s+\w+', line[m.end():], re.I
            ):
                continue
            field = _degree_field(line, m)
            claim = QualificationClaim(segment_id=seg.segment_id, quote=line,
                                       state=_state(line), degree_level=level,
                                       field_of_study=field)
            claims.append(claim)
            if expected_level == level:
                same_level.append(claim)
            if expected_level == level and (not expected_field or (field and _field_equal(expected_field, field))):
                compatible.append(claim)
    if not claims:
        return QualificationCheck(kind='education', outcome='not_evidenced',
                                  explanation='No explicit degree claim found in the CV.')
    if expected_level is None or (c.operator != 'single' and not broad_category):
        return QualificationCheck(kind='education', outcome='ambiguous', claims=claims,
                                  explanation='The JD degree level or alternative qualification rule needs review.')
    positives = [claim for claim in compatible if claim.state == 'claimed']
    if positives and any(x.state != 'claimed' for x in compatible):
        return QualificationCheck(kind='education', outcome='ambiguous', claims=claims,
                                  explanation='Compatible degree claims conflict with incomplete or negative claims.')
    if positives:
        return QualificationCheck(kind='education', outcome='satisfied', claims=claims,
                                  explanation='CV explicitly claims the required degree level and field; authenticity not checked.')
    if broad_category and same_level:
        if any(x.state != 'claimed' for x in same_level):
            return QualificationCheck(kind='education', outcome='ambiguous', claims=claims,
                                      explanation='Incomplete, denied or conflicting degree claims require review.')
        if any(x.field_of_study for x in same_level):
            return QualificationCheck(kind='education', outcome='field_semantic', claims=claims,
                                      explanation='The JD describes a family of degree fields. '
                                      'The claimed level is established; the field relationship '
                                      'must be determined from the JD and cited CV by the model '
                                      'or a human, not an exact-string equality test.')
    if compatible and any(x.state == 'pending' for x in compatible):
        return QualificationCheck(kind='education', outcome='ambiguous', claims=claims,
                                  explanation='Degree is described as in progress or expected, not completed.')
    if compatible and any(x.state in {'denied', 'expired'} for x in compatible):
        return QualificationCheck(kind='education', outcome='mismatch', claims=claims,
                                  explanation='Resume explicitly denies completion of the required degree.')
    # CV may claim a different degree. Higher-level degree substitution is an
    # employer policy decision, not an unrequested automatic equivalence.
    if expected_field and any(x.degree_level != expected_level and x.field_of_study and
                              _field_equal(expected_field, x.field_of_study) for x in claims):
        return QualificationCheck(kind='education', outcome='ambiguous', claims=claims,
                                  explanation='Different degree level in same field; employer equivalence policy required.')
    if any(x.degree_level == expected_level and x.field_of_study is None for x in claims):
        return QualificationCheck(kind='education', outcome='ambiguous', claims=claims,
                                  explanation='Degree level stated, but required academic field not established.')
    return QualificationCheck(kind='education', outcome='mismatch', claims=claims,
                              explanation='Explicit degree claims do not establish the requested level and field.')


def _cert_subject(jd: str) -> tuple[str, bool]:
    cleaned = re.sub(r'^(?:valid|required|current|active)\s+', '', jd.strip(), flags=re.I)
    # Specific credential name wins; never replace with a different certificate
    # just because the same provider appears.
    if re.search(r'\bcertified\b', cleaned, re.I):
        return cleaned, False
    m = re.fullmatch(r'(?:certification|certificate|credential)\s+(?:in|for|of)\s+(.+)', cleaned, re.I)
    if m:
        return m.group(1).strip(), True
    m = re.fullmatch(r'(.+?)\s+(?:certification|certificate|credential)', cleaned, re.I)
    if m:
        return m.group(1).strip(), True
    return '', True


def _certificate(requirement: ValidatedRequirement, lines) -> QualificationCheck:
    subject, generic = _cert_subject(requirement.name)
    claims: list[QualificationClaim] = []
    matches: list[QualificationClaim] = []
    for line, seg in lines:
        if seg.section != 'certifications' and not _CERT_WORD.search(line):
            continue
        # Training statements that mention certification are NOT certificates.
        state = _state(line)
        claim = QualificationClaim(segment_id=seg.segment_id, quote=line,
                                   state=state, credential_name=line)
        claims.append(claim)
        if subject and phrase_present(subject, line):
            if not generic:
                matches.append(claim)
            elif (_CERT_WORD.search(line) or
                  (seg.section == 'certifications' and _subject_key(line) != _subject_key(subject))):
                matches.append(claim)
    if not claims:
        return QualificationCheck(kind='certification', outcome='not_evidenced',
                                  explanation='No credential claim found in the CV.')
    if not subject or requirement.constraint.operator != 'single':
        return QualificationCheck(kind='certification', outcome='ambiguous', claims=claims,
                                  explanation='JD certificate identity/alternatives are underspecified.')
    if any(x.state == 'claimed' for x in matches) and any(x.state != 'claimed' for x in matches):
        return QualificationCheck(kind='certification', outcome='ambiguous', claims=claims,
                                  explanation='Credential statements conflict with pending/expired/negative evidence.')
    if any(x.state == 'claimed' for x in matches):
        return QualificationCheck(kind='certification', outcome='satisfied', claims=claims,
                                  explanation='CV claims the named credential; issuing authority has not verified it.')
    if any(x.state == 'pending' for x in matches):
        return QualificationCheck(kind='certification', outcome='ambiguous', claims=claims,
                                  explanation='Training or pending credential is not evidence of a completed certificate.')
    if matches:
        return QualificationCheck(kind='certification', outcome='mismatch', claims=claims,
                                  explanation='Named credential is denied, expired, or revoked in the CV.')
    return QualificationCheck(kind='certification', outcome='mismatch', claims=claims,
                              explanation='CV credential names do not establish the required certificate.')


def _license_subject(jd: str) -> tuple[str, bool]:
    cleaned = re.sub(r'\b(?:valid|active|current|required)\b', '', jd, flags=re.I).strip()
    valid_required = bool(re.search(r'\b(?:valid|active|current)\b', jd, re.I))
    return normalize_whitespace(cleaned), valid_required


def _license(requirement: ValidatedRequirement, lines) -> QualificationCheck:
    subject, needs_valid = _license_subject(requirement.name)
    claims: list[QualificationClaim] = []
    relevant: list[QualificationClaim] = []
    for line, seg in lines:
        # A job title such as 'Licensed Nurse' is not a license document
        # claim. Require an actual license/licence or registration noun.
        if not re.search(r'\b(?:licen[cs]e|registration)\b', line, re.I):
            continue
        state = _state(line)
        claim = QualificationClaim(segment_id=seg.segment_id, quote=line,
                                   state=state, credential_name=line)
        claims.append(claim)
        if subject and phrase_present(subject, line):
            relevant.append(claim)
    if not claims:
        return QualificationCheck(kind='license', outcome='not_evidenced',
                                  explanation='No direct license/registration claim found.')
    if not subject or requirement.constraint.operator != 'single':
        return QualificationCheck(kind='license', outcome='ambiguous', claims=claims,
                                  explanation='JD license scope/alternatives need reviewer confirmation.')
    if not relevant:
        return QualificationCheck(kind='license', outcome='mismatch', claims=claims,
                                  explanation='CV license claims do not name the required license.')
    if any(x.state == 'claimed' for x in relevant) and any(x.state != 'claimed' for x in relevant):
        return QualificationCheck(kind='license', outcome='ambiguous', claims=claims,
                                  explanation='Conflicting license status claims need review.')
    if any(x.state in {'expired', 'denied'} for x in relevant):
        return QualificationCheck(kind='license', outcome='mismatch', claims=claims,
                                  explanation='CV reports that the required license is expired, denied, or invalid.')
    if any(x.state == 'pending' for x in relevant):
        return QualificationCheck(kind='license', outcome='ambiguous', claims=claims,
                                  explanation='License is pending/in progress, not a current credential.')
    if needs_valid and not any(_VALID.search(x.quote) for x in relevant):
        return QualificationCheck(kind='license', outcome='ambiguous', claims=claims,
                                  explanation='JD requires a valid license but the CV does not claim current validity.')
    return QualificationCheck(kind='license', outcome='satisfied', claims=claims,
                              explanation='CV claims the named license and required validity, but authority verification is pending.')


def check_qualification(requirement: ValidatedRequirement, resume_text: str,
                        segments: list[ResumeSegment] | None = None) -> QualificationCheck | None:
    kind = requirement.constraint.kind
    if kind not in {'education', 'certification', 'license'}:
        return None
    segments = segments if segments is not None else segment_resume(resume_text)
    lines = _line_claims(resume_text, segments)
    if kind == 'education':
        return _education(requirement, lines)
    if kind == 'certification':
        return _certificate(requirement, lines)
    return _license(requirement, lines)


def related_degree_transfer_supported(requirement: ValidatedRequirement,
                                      check: QualificationCheck | None,
                                      evidence_ids: list[str]) -> bool:
    """Source-proof gate for a *model-decided*, unscored related-major review.

    No subject taxonomy or alias map lives here. The model decides whether
    the alternative degree is related; Python verifies its cited completion
    and that its academic level is not below the requested one. Crucially, a
    higher degree never satisfies an unrequested bachelor's degree in Python.
    """
    return bool(check and check.kind == 'education'
                and check.outcome in {'mismatch', 'ambiguous'}
                and any(x.state == 'claimed'
                        and _degree_level_can_overlap(
                            required=requirement.constraint.degree_level,
                            claimed=x.degree_level)
                        and x.field_of_study
                        and x.segment_id in evidence_ids
                        for x in check.claims))


def _model_describes_related_qualification(
    reason: str, requirement: ValidatedRequirement, check: QualificationCheck
) -> bool:
    """A reviewer-only bridge for contradictory model label and explanation.

    This is NOT a table of academic synonyms and can NEVER award Found.
    Qualification level/completion and the cited original source are still
    required by related_degree_transfer_supported(). A model explicitly
    calling a field unrelated must not be interpreted as transferability.
    """
    description = normalize_whitespace(reason).casefold()
    if re.search(r'\b(?:unrelated|not\s+(?:at\s+all\s+|closely\s+|meaningfully\s+)?'
                 r'(?:related|similar|equivalent)|no\s+meaningful\s+overlap)\b',
                 description):
        return False
    relationship_stated = bool(re.search(
        r'\b(?:closely\s+|substantially\s+|meaningfully\s+|directly\s+|'
        r'highly\s+)?(?:related|similar|adjacent|overlapping)\b|'
        r'\btransferable\b', description))
    # A generic response saying "some alternative has overlap" cannot prove
    # that *this* specific original credential is related to *this* JD field.
    # This fallback is used only when the model's structured label disagrees
    # with its explanation. Require the explanation to name both source and
    # requested fields, without maintaining any profession/degree mapping.
    expected = requirement.constraint.field_of_study
    if not relationship_stated or not expected or not phrase_present(expected, description):
        return False
    return any(claim.field_of_study and claim.state == 'claimed' and
               phrase_present(claim.field_of_study, description)
               for claim in check.claims)


def apply_qualification_checks(*, requirements: list[ValidatedRequirement],
                               assessments: list[RequirementAssessment],
                               resume_text: str) -> tuple[list[RequirementAssessment], list[str], bool]:
    """Post-assessment claim validation; never changes frozen criteria or scorer."""
    by_id = {r.requirement_id: r for r in requirements}
    segments = segment_resume(resume_text)
    by_segment = {s.segment_id: s for s in segments}
    final: list[RequirementAssessment] = []
    notes: list[str] = []
    changed = False
    for row in assessments:
        if row.assessment_state == "unverified":
            final.append(row)
            continue
        requirement = by_id[row.requirement_id]
        check = check_qualification(requirement, resume_text, segments)
        if check is None:
            final.append(row)
            continue
        if check.outcome == 'satisfied':
            status = 'matched'
        elif check.outcome == 'mismatch':
            status = 'not_matched'
        elif check.outcome == 'field_semantic':
            # Never automatically award a degree from an inclusive label.
            # Allow an already source-grounded positive model decision only
            # when it actually cited an affirmative degree of that level.
            valid_degree_ids = {x.segment_id for x in check.claims
                                if x.state == 'claimed'
                                and x.degree_level == requirement.constraint.degree_level
                                and x.field_of_study}
            status = (row.status if row.status != 'matched' or
                      valid_degree_ids.intersection(row.evidence_ids)
                      else 'uncertain')
        elif check.outcome == 'ambiguous':
            status = 'uncertain'
        else:
            status = 'uncertain' if row.status == 'matched' else row.status
        # A different completed degree does not satisfy an EXACT academic
        # major, but the independent semantic assessment may have found
        # credible overlap. Keep that *unscored* reviewer finding separate
        # from the immutable qualification/score decision. Do not let an
        # incomplete, denied, lower-level, or uncited degree pass this gate.
        # The LLM can identify a closely related completed qualification in
        # prose while incorrectly choosing Found (or Not Found). Preserve the
        # source-backed *relationship* as unscored Transferable rather than
        # letting the exact-field validator replace it with blanket absence.
        # This cannot convert the different academic field to an exact match.
        related_claim = bool(row.unified_status == 'Transferable'
                             or _model_describes_related_qualification(
                                 row.reason, requirement, check))
        preserves_transfer = bool(related_claim and
                                  related_degree_transfer_supported(
                                      requirement, check, row.evidence_ids)
                                  and status != 'matched')
        final_unified = row.unified_status
        if check.outcome in {'mismatch', 'ambiguous', 'not_evidenced'} and (
                row.unified_status == 'Transferable' and not preserves_transfer):
            final_unified = 'Not Found'
        is_changed = status != row.status
        if is_changed:
            changed = True
            notes.append(f'{row.requirement_id}: {check.kind} {check.outcome}; '
                         f'{row.status} -> {status}. {check.explanation}')
        check = check.model_copy(update={'changed_status': is_changed})
        # When a validator changes a model decision, cite its actual source.
        # Do not repeat a model citation that failed this verification.
        evidence = row.evidence
        ids = list(row.evidence_ids)
        cited = list(row.evidence_segments)
        if check.claims:
            selected = (next((x for x in check.claims
                              if preserves_transfer and x.segment_id in row.evidence_ids
                              and x.state == 'claimed' and x.field_of_study
                              and _degree_level_can_overlap(
                                  required=requirement.constraint.degree_level,
                                  claimed=x.degree_level)), None))
            selected = selected or next((x for x in check.claims if x.state == 'claimed' and
                             ((check.kind == 'education' and requirement.constraint.degree_level == x.degree_level
                               and (not requirement.constraint.field_of_study or
                                    (x.field_of_study and _field_equal(requirement.constraint.field_of_study, x.field_of_study))))
                              or (check.kind != 'education' and
                                  phrase_present(_cert_subject(requirement.name)[0] if check.kind == 'certification'
                                                 else _license_subject(requirement.name)[0], x.quote)))), None)
            selected = selected or check.claims[0]
            seg = by_segment[selected.segment_id]
            evidence, ids = seg.text, [seg.segment_id]
            cited = [EvidenceCitation(segment_id=seg.segment_id, section=seg.section, text=seg.text)]
        elif is_changed:
            evidence, ids, cited = None, [], []
        reason = row.reason
        if preserves_transfer:
            supported_degree = next((x for x in check.claims
                                     if x.state == 'claimed' and x.field_of_study
                                     and x.segment_id in row.evidence_ids
                                     and _degree_level_can_overlap(
                                         required=requirement.constraint.degree_level,
                                         claimed=x.degree_level)), None)
            if supported_degree:
                reason = (f"The CV reports a completed {supported_degree.degree_level or 'academic'} "
                          f"degree in {supported_degree.field_of_study}. The cited qualification "
                          "is related to the requested field but does not establish the "
                          "exact named degree; Transferable is for HR review and earns "
                          "no direct requirement point.")
        elif is_changed and status != 'matched':
            reason = (f"The reported qualification does not establish the exact JD "
                      f"condition: {check.explanation}")
        final.append(row.model_copy(update={
            'status': status, 'evidence': evidence, 'evidence_ids': ids,
            'evidence_segments': cited, 'qualification_check': check,
            'reason': reason,
            'unified_status': 'Transferable' if preserves_transfer else final_unified,
            'review_recommended': (row.review_recommended or preserves_transfer
                                   or check.outcome == 'field_semantic'),
        }))
    return final, notes, changed
