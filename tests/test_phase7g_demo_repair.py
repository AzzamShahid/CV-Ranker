"""Independent regression for AI/ML demo semantics (no network or skill aliases)."""
from pathlib import Path

from cv_ranker.fallback import structural_hints
from cv_ranker.requirement_typing import classify_requirement
from cv_ranker.schemas import ValidatedRequirement
from cv_ranker.text_utils import extract_or_requirement, requirement_options, classify_requirement_tone
from cv_ranker.semantic.decomposition import (
    create_shadow_search_plan, DecompositionResponse, RequirementProposal,
    ProposedCapability,
)
from cv_ranker.semantic.transferability import (
    _validate_compact_response, CompactTransferabilityResponse, CompactCapabilityProposal,
)

ROOT = Path(__file__).resolve().parents[1]


def test_applied_ai_jd_sections_exclude_instructions_and_include_experience():
    jd = (ROOT / 'sample_data/applied_ai_jd.txt').read_text(encoding='utf-8')
    hints = structural_hints(jd)
    assert len(hints) == 17, [(h.priority, h.name) for h in hints]
    assert sum(h.priority == 'required' for h in hints) == 10
    assert sum(h.priority == 'preferred' for h in hints) == 7
    names = [h.name for h in hints]
    assert any('Minimum 3 years' in s for s in names)
    assert not any('HOW TO INTERPRET' in s or 'CORE RESPONSIBILITIES' in s for s in names)
    assert not any('The 3-year requirement' in s or 'OR: evidence' in s for s in names)


def test_or_annotation_is_not_an_extra_tool():
    original = 'TensorFlow or PyTorch (at least one)'
    assert extract_or_requirement(original) == 'TensorFlow or PyTorch'
    assert requirement_options(original) == ['TensorFlow', 'PyTorch']
    jd = f'REQUIRED SKILLS\n- {original}\n'
    req = ValidatedRequirement(requirement_id='R004', name='TensorFlow or PyTorch',
                               priority='required', jd_evidence=original)
    constraint = classify_requirement(req, jd)
    assert constraint.operator == 'any_of'
    assert constraint.options == ['TensorFlow', 'PyTorch']


def test_three_year_requirement_is_typed_and_not_silently_discarded():
    jd = (ROOT / 'sample_data/applied_ai_jd.txt').read_text(encoding='utf-8')
    hint = next(h for h in structural_hints(jd) if 'Minimum 3 years' in h.name)
    req = ValidatedRequirement(requirement_id='R001', name=hint.name,
                               priority=hint.priority, jd_evidence=hint.evidence)
    meta = classify_requirement(req, jd)
    assert meta.kind == 'experience' and meta.minimum_years == 3
    assert meta.requires_review  # Complex related-experience condition remains reviewable.


def test_shadow_command_uses_applied_ai_not_backend_demo():
    command = (ROOT / 'scripts/run_phase7g_shadow.cmd').read_text(encoding='utf-8').lower()
    assert 'applied_ai_jd.txt' in command and 'applied_ai_resumes' in command
    assert 'backend_jd.txt' not in command
    backend = (ROOT / 'scripts/run_phase7g_backend.cmd').read_text(encoding='utf-8').lower()
    assert 'backend_jd.txt' in backend


class FakeDecompositionLLM:
    def invoke_structured(self, **kwargs):
        return DecompositionResponse(requirements=[RequirementProposal(
            requirement_id='R001', capabilities=[
                ProposedCapability(description='LangChain', source_quote='LangChain', origin='explicit'),
                ProposedCapability(description='LLM orchestration pipelines', source_quote='LangChain', origin='search_hint'),
            ],
        )])


def test_redundant_model_child_is_not_counted_as_separate_obligation():
    req = ValidatedRequirement(requirement_id='R001', name='LangChain',
                               priority='required', jd_evidence='LangChain')
    plan = create_shadow_search_plan([req], FakeDecompositionLLM())
    assert plan.complete
    assert [(c.capability_id, c.origin) for c in plan.capabilities] == [
        ('R001', 'explicit'), ('R001-C01', 'search_hint'),
    ]


def test_semantic_direct_claim_from_explicit_denial_is_not_accepted():
    from cv_ranker.semantic.decomposition import SearchCapability
    cap = SearchCapability(parent_requirement_id='R001', capability_id='R001',
                           description='LangChain', source_quote='LangChain',
                           origin='explicit', provenance='source_preserved',
                           requires_human_review=False)
    text = 'No direct experience with LangChain; built Python retrieval workflows using other tools.'
    assert classify_requirement_tone(text, 'LangChain') == 'negated'
    reply = CompactTransferabilityResponse(capabilities=[CompactCapabilityProposal(
        capability_id='R001', relationship='direct', source_ids=['S001'],
        explanation='Mistaken direct credit',
    )])
    results, notices = _validate_compact_response('R001', [cap], {'S001': text}, reply,
                                                   requirement_name='LangChain')
    assert results[0].relationship == 'uncertain'
    assert results[0].citation_audit == 'source_validated'
    assert notices and 'denial' in notices[0]


def test_semantic_transferable_still_requires_verified_citation():
    from cv_ranker.semantic.decomposition import SearchCapability
    cap = SearchCapability(parent_requirement_id='R001', capability_id='R001',
                           description='LangChain', source_quote='LangChain',
                           origin='explicit', provenance='source_preserved',
                           requires_human_review=False)
    text = 'Built LLM routing and retrieval pipelines using a different orchestration framework.'
    reply = CompactTransferabilityResponse(capabilities=[CompactCapabilityProposal(
        capability_id='R001', relationship='transferable', source_ids=['S001'],
        explanation='Documented orchestration workflows, but not LangChain usage.',
    )])
    results, notices = _validate_compact_response('R001', [cap], {'S001': text}, reply,
                                                   requirement_name='LangChain')
    assert results[0].relationship == 'transferable' and not notices
    assert results[0].independent_semantic_verification is False


def test_ui_shows_all_relations_by_default():
    ui = (ROOT / 'cv_ranker/ui/dashboard.py').read_text(encoding='utf-8')
    assert '"Show AI proposals", ["All", "Transferable only"' in ui
    assert '"Why": r["Explanation"]' in ui
