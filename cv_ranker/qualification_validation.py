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
from .segments import ResumeSegment, segment_resume
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
    outcome: Literal['satisfied', 'mismatch', 'ambiguous', 'not_evidenced']
    explanation: str
    claims: list[QualificationClaim] = Field(default_factory=list)
    # A satisfied source claim is not proof that a credential is authentic.
    independently_verified: bool = False
    changed_status: bool = False


_DEGREE = re.compile(
    r"(?<!\w)(?P<label>ph\.?d\.?|doctorate|doctoral|master(?:'s)?(?:\s+of\s+(?:science|arts))?|"
    r"m\.?s\.?c?\.?|mba|bachelor(?:'s)?(?:\s+of\s+(?:science|arts))?|"
    r"b\.?s\.?c?\.?|b\.?tech\.?|associate(?:'s)?|diploma)"
    r"(?:\s+degree)?\b", re.I,
)
_CERT_WORD = re.compile(r'\b(?:certified|certification|certificate|credential)\b', re.I)
_LICENSE_WORD = re.compile(r'\b(?:licen[cs]e|licen[cs]ed|registration|registered)\b', re.I)
_PENDING = re.compile(
    r'\b(?:pursuing|in[ -]progress|ongoing|studying|currently\s+enrolled|'
    r'expected\s+(?:to\s+graduate|graduation|in\b)|working\s+toward(?:s)?|'
    r'preparing\s+for|planning\s+to|intend(?:ing)?\s+to|hope\s+to|aim(?:ing)?\s+to|'
    r'will\s+(?:earn|obtain|complete)|can\s+earn|training\s+(?:for|on|in)|coursework|'
    r'course\s+(?:on|in)|applied\s+for|application\s+pending|exam\s+pending|'
    r'not\s+yet\s+(?:obtained|completed|certified|licensed)|'
    r'certification\s+(?:course|program|training)|certificate\s+course|incomplete)\b', re.I,
)
_DENIED = re.compile(
    r'\b(?:no\b|never\b|without\b|not\s+(?:certified|licensed|qualified|completed|graduated)|'
    r'did\s+not\s+(?:complete|obtain)|failed\s+to\s+(?:obtain|complete)|dropped\s+out|'
    r'not\s+(?:valid|active|current)|no\s+longer\s+(?:valid|active|current))\b', re.I,
)
_EXPIRED = re.compile(r'\b(?:expired|revoked|suspended|lapsed|invalid|withdrawn|cancelled|canceled)\b', re.I)
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


def _state(text: str) -> Literal['claimed', 'pending', 'denied', 'expired']:
    if _EXPIRED.search(text):
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
        line = line.strip().lstrip('-•* ').strip()
        if not line or len(line) > 500:
            continue
        for seg in segments:
            if normalize_whitespace(line).casefold() in seg.text.casefold():
                candidates.append((line, seg))
                break
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
            if expected_level == level and (not expected_field or (field and _field_equal(expected_field, field))):
                compatible.append(claim)
    if not claims:
        return QualificationCheck(kind='education', outcome='not_evidenced',
                                  explanation='No explicit degree claim found in the CV.')
    if expected_level is None or c.operator != 'single':
        return QualificationCheck(kind='education', outcome='ambiguous', claims=claims,
                                  explanation='The JD degree level or alternative qualification rule needs review.')
    positives = [claim for claim in compatible if claim.state == 'claimed']
    if positives and any(x.state != 'claimed' for x in compatible):
        return QualificationCheck(kind='education', outcome='ambiguous', claims=claims,
                                  explanation='Compatible degree claims conflict with incomplete or negative claims.')
    if positives:
        return QualificationCheck(kind='education', outcome='satisfied', claims=claims,
                                  explanation='CV explicitly claims the required degree level and field; authenticity not checked.')
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
        requirement = by_id[row.requirement_id]
        check = check_qualification(requirement, resume_text, segments)
        if check is None:
            final.append(row)
            continue
        if check.outcome == 'satisfied':
            status = 'matched'
        elif check.outcome == 'mismatch':
            status = 'not_matched'
        elif check.outcome == 'ambiguous':
            status = 'uncertain'
        else:
            status = 'uncertain' if row.status == 'matched' else row.status
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
            selected = next((x for x in check.claims if x.state == 'claimed' and
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
        final.append(row.model_copy(update={
            'status': status, 'evidence': evidence, 'evidence_ids': ids,
            'evidence_segments': cited, 'qualification_check': check,
        }))
    return final, notes, changed
