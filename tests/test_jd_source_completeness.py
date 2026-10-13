"""Phase 0/1: source-grounded denominator and JD diagnostic regressions."""
import json
from pathlib import Path

import pytest

from cv_ranker.config import Settings
from cv_ranker.jd import validate_jd_requirements
from cv_ranker.fallback import structural_hints
from cv_ranker.schemas import JDRequirement, JDValidationResponse


class FixedJDLLM:
    def __init__(self, rows):
        self.rows = rows
        self.calls = 0

    def invoke_structured(self, **kwargs):
        self.calls += 1
        if self.calls > 1:
            raise AssertionError("Omission recovery should not require another LLM call")
        return JDValidationResponse(requirements=self.rows)


def jd_for(scenario):
    lines = ["Benchmark Role", "", "Required Skills:"]
    lines.extend(f"- {r['name']}" for r in scenario['requirements'] if r['priority'] == 'required')
    preferred = [r for r in scenario['requirements'] if r['priority'] == 'preferred']
    if preferred:
        lines += ["", "Preferred Skills:"] + [f"- {r['name']}" for r in preferred]
    return "\n".join(lines) + "\n"


CASES = json.loads((Path(__file__).resolve().parents[1] / 'evaluation' / 'benchmark_cases.json').read_text(encoding='utf-8'))['scenarios']


@pytest.mark.parametrize('scenario', CASES, ids=[s['id'] for s in CASES])
def test_partial_llm_cannot_lose_any_of_the_21_explicit_benchmark_requirements(scenario):
    text = jd_for(scenario)
    selected = scenario['requirements'][0]
    llm = FixedJDLLM([JDRequirement(name=selected['name'], priority=selected['priority'], evidence=selected['name'])])
    diagnostic = []
    reqs, mode, warnings = validate_jd_requirements(
        jd_text=text, candidates=[], settings=Settings(max_requirements=50), llm=llm,
        diagnostics=diagnostic,
    )
    expected = sorted(scenario['requirements'], key=lambda x: x['priority'] != 'required')
    assert [(r.name, r.priority) for r in reqs] == [(r['name'], r['priority']) for r in expected]
    assert mode == 'fallback_structural_after_llm'
    assert llm.calls == 1
    assert any('source completeness' in warning for warning in warnings)
    source_rows = [r for r in diagnostic if r['stage'] == 'explicit_source']
    assert len(source_rows) == len(expected)
    assert sum(r['status'] == 'restored_from_explicit_source' for r in source_rows) == len(expected) - 1
    assert diagnostic[-1]['stage'] == 'final_denominator'
    assert diagnostic[-1]['source_restored'] == len(expected) - 1


def test_full_valid_llm_set_is_still_llm_validated_and_trace_has_no_recovery():
    text = 'Required Skills:\n- Python\n- Docker\nPreferred Skills:\n- AWS\n'
    rows = [JDRequirement(name=n, evidence=n, priority=p) for n,p in [('Python','required'),('Docker','required'),('AWS','preferred')]]
    diag=[]
    reqs, mode, warnings = validate_jd_requirements(jd_text=text,candidates=[],settings=Settings(),llm=FixedJDLLM(rows), diagnostics=diag)
    assert mode == 'llm_validated' and not warnings
    assert [r.name for r in reqs] == ['Python','Docker','AWS']
    assert sum(d['status'] == 'kept_model_source_match' for d in diag if d['stage']=='explicit_source') == 3


def test_unrelated_renamed_model_proposal_is_frozen_as_actual_source_and_logged():
    jd = 'Required Skills:\n- Python\n- Docker\n'
    diag=[]
    rows=[JDRequirement(name='Kubernetes',priority='required',evidence='Python')]
    reqs,mode,_=validate_jd_requirements(jd_text=jd,candidates=[],settings=Settings(),llm=FixedJDLLM(rows),diagnostics=diag)
    assert [r.name for r in reqs] == ['Python','Docker']
    assert mode == 'fallback_structural_after_llm'
    renamed=[x for x in diag if x.get('reason') == 'source_quote_replaced_model_name']
    assert renamed and renamed[0]['proposed_name']=='Kubernetes' and renamed[0]['frozen_name']=='Python'


def test_benefit_or_bulleted_responsibility_not_promoted_to_requirement():
    jd = 'Required Skills:\n- Python\n- Build internal APIs\n- Competitive salary\n\nBenefits:\n- Flexible hours\n'
    assert [h.name for h in structural_hints(jd)] == ['Python']
    # Qwen is not allowed to promote a benefit just because it quotes its text.
    class RetryJDLLM(FixedJDLLM):
        def invoke_structured(self, **kwargs):
            if self.calls:
                self.calls += 1
                return JDValidationResponse(requirements=[])
            return super().invoke_structured(**kwargs)

    llm=RetryJDLLM([
        JDRequirement(name='Python',priority='required',evidence='Python'),
        JDRequirement(name='Flexible hours',priority='required',evidence='Flexible hours'),
    ])
    reqs,mode,warnings=validate_jd_requirements(jd_text=jd,candidates=[],settings=Settings(),llm=llm)
    assert [r.name for r in reqs] == ['Python']
    assert mode == 'llm_validated'
    assert warnings and 'source-grounded' in warnings[0]


def test_configured_cap_is_diagnostic_not_silent_loss():
    jd='Required Skills:\nPython\nDocker\nPostgreSQL\n'
    rows=[JDRequirement(name=n,evidence=n,priority='required') for n in ('Python','Docker','PostgreSQL')]
    diag=[]
    reqs,mode,warnings=validate_jd_requirements(jd_text=jd,candidates=[],settings=Settings(max_requirements=2),llm=FixedJDLLM(rows),diagnostics=diag)
    assert [r.name for r in reqs] == ['Python','Docker']
    assert any('configured maximum' in w for w in warnings)
    assert diag[-1]['capped'] == 1


def test_pipeline_report_keeps_jd_diagnostics_and_complete_denominator(tmp_path, monkeypatch):
    """The report (not merely the low-level JD helper) must expose recovery."""
    import cv_ranker.pipeline as pipeline_module
    from cv_ranker.pipeline import CVRanker
    from cv_ranker.schemas import LLMCandidateAssessmentResponse, LLMAssessmentItem

    class FakePipelineModel:
        def __init__(self, settings):
            self.settings = settings
            self.disabled_reason = None
            self.jd_calls = 0

        def prompt_fits(self, *args):
            return True

        def invoke_structured(self, *, schema, user_prompt, system_prompt):
            if schema is JDValidationResponse:
                self.jd_calls += 1
                return JDValidationResponse(requirements=[
                    JDRequirement(name='Python', priority='required', evidence='Python')
                ])
            import re
            ids = re.findall(r'(?m)^(R\d{3})\s*\|', user_prompt)
            return LLMCandidateAssessmentResponse(assessments=[
                LLMAssessmentItem(requirement_id=rid, status='not_matched', evidence_ids=[])
                for rid in ids
            ])

    monkeypatch.setattr(pipeline_module, 'StructuredLLM', FakePipelineModel)
    jd_path = tmp_path / 'jd.txt'
    cv_path = tmp_path / 'resume.txt'
    jd_path.write_text('Required Skills:\n- Python\n- Django\n- PostgreSQL\nPreferred Skills:\n- AWS\n', encoding='utf-8')
    cv_path.write_text('Candidate with work on project management and team communication.', encoding='utf-8')
    report = CVRanker(Settings(), use_llm=True).run(jd_path, [cv_path])
    assert [r.name for r in report.requirements] == ['Python','Django','PostgreSQL','AWS']
    assert report.jd_validation_mode == 'fallback_structural_after_llm'
    assert [r['name'] for r in report.jd_diagnostics if r.get('status')=='restored_from_explicit_source'] == ['Django','PostgreSQL','AWS']
    assert report.jd_diagnostics[-1]['source_restored'] == 3
    assert len(report.candidates[0].assessments) == 4
    assert 'jd_diagnostics' in report.model_dump()


def test_explicit_nonrequirement_section_cannot_grant_a_skill():
    jd = 'Required Skills:\n- Python\n\nBenefits:\n- Machine Learning training\n\nPreferred Qualifications:\n- Docker\n'
    # The fake model incorrectly elevates text found only in the Benefits section.
    class CorrectedModel(FixedJDLLM):
        def invoke_structured(self, **kwargs):
            if self.calls:
                self.calls += 1
                return JDValidationResponse(requirements=[])
            return super().invoke_structured(**kwargs)
    llm = CorrectedModel([
        JDRequirement(name='Python', priority='required', evidence='Python'),
        JDRequirement(name='Machine Learning', priority='required', evidence='Machine Learning training'),
        JDRequirement(name='Docker', priority='preferred', evidence='Docker'),
    ])
    diag=[]
    frozen,mode,_=validate_jd_requirements(jd_text=jd,candidates=[],settings=Settings(),llm=llm,diagnostics=diag)
    assert [(r.name,r.priority) for r in frozen] == [('Python','required'),('Docker','preferred')]
    assert any(x.get('reason') == 'source_is_benefit_or_role_action_or_excluded_section' for x in diag)


def test_benchmark_reports_jd_source_recovery_instead_of_missing_requirements(monkeypatch):
    import cv_ranker.pipeline as pipeline_module
    from cv_ranker.schemas import LLMAssessmentItem, LLMCandidateAssessmentResponse
    from evaluation.evaluate_benchmark import _pipeline_rows

    class FakeModel:
        def __init__(self, settings):
            self.settings = settings
            self.disabled_reason = None

        def prompt_fits(self, *args):
            return True

        def invoke_structured(self, *, schema, system_prompt, user_prompt):
            if schema is JDValidationResponse:
                # Deliberately incomplete Qwen JD extraction: only one of seven.
                return JDValidationResponse(requirements=[
                    JDRequirement(name='Python', priority='required', evidence='Python')
                ])
            import re
            ids = re.findall(r'(?m)^(R\d{3})\s*\|', user_prompt)
            return LLMCandidateAssessmentResponse(assessments=[
                LLMAssessmentItem(requirement_id=rid, status='not_matched', evidence_ids=[])
                for rid in ids
            ])

    monkeypatch.setattr(pipeline_module, 'StructuredLLM', FakeModel)
    rows = _pipeline_rows(CASES[0], 'fake')
    assert len(rows) == 7
    assert all(row.predicted != 'missing_requirement' for row in rows)
    assert sum(row.jd_source_resolution == 'restored_from_explicit_source' for row in rows) == 6
    assert all(row.evaluation_mode.startswith('jd:fallback_structural_after_llm;cv:') for row in rows)
