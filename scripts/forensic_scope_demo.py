"""Reproducible, no-model provenance and scope regression examples."""
import json
from pathlib import Path

from cv_ranker.fallback import fallback_assessment
from cv_ranker.schemas import ValidatedRequirement
from cv_ranker.segments import segment_resume

SCENARIOS = [
    ('Split negative, first skill', 'Python', 'No experience with\nPython\nDjango', 'not_matched'),
    ('Split negative, next skill', 'Django', 'No experience with\nPython\nDjango', 'not_matched'),
    ('Split learning, first skill', 'Python', 'Currently learning\nPython\nDjango', 'uncertain'),
    ('Split learning, next skill', 'Django', 'Currently learning\nPython\nDjango', 'uncertain'),
    ('Copied job requirements', 'Python', 'We require\nSkills\nPython\nDjango', 'not_matched'),
    ('Copied nested requirements', 'Python', 'Requirements:\nTechnical Skills\nPython\nDjango', 'not_matched'),
    ('Genuine unheaded list', 'Python', 'Python\nDjango', 'matched'),
    ('Blank line ends negative list', 'Django', 'No experience with:\nPython\n\nDjango', 'matched'),
]


def main() -> int:
    rows = []
    for label, name, resume, expected in SCENARIOS:
        req = ValidatedRequirement(requirement_id='R001',name=name,
                                   priority='required',jd_evidence=name)
        result = fallback_assessment(req, resume)
        rows.append({
            'scenario': label, 'requirement': name,
            'expected': expected, 'predicted': result.status,
            'correct': result.status == expected,
            'evidence_ids': result.evidence_ids,
            'evidence': result.evidence,
            'segments': [
                {'id':seg.segment_id,'section':seg.section,'text':seg.text,
                 'physical_lines': list(seg.source_lines)}
                for seg in segment_resume(resume)
            ]
        })
    result = {'build':'evidence-scope-forensic-fix-2026-10-13',
              'type':'targeted-regression-demo-not-industrial-validation',
              'correct':sum(r['correct'] for r in rows),'total':len(rows),
              'rows':rows}
    out = Path('outputs/phase7f2_forensic_demo.json')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(f"Forensic source-scope checks: {result['correct']}/{result['total']}")
    print(f'Saved: {out}')
    return 0 if all(r['correct'] for r in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
