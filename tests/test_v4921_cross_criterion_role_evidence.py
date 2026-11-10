"""Cross-criterion source recall and dated-role scope remain source-grounded."""
import json
from pathlib import Path

import numpy as np
import pytest

from cv_ranker.config import Settings
from cv_ranker.compound_validation import evaluate_compound
from cv_ranker.experience_validation import apply_experience_checks
from cv_ranker.schemas import (EvidenceCitation, RequirementAssessment,
                               RequirementConstraint, ValidatedRequirement)
from cv_ranker.segments import ResumeSegment, segment_resume
from cv_ranker.requirement_typing import classify_requirement
from cv_ranker.unified import (
    UnifiedEvidenceEngine, _completed_work_recall_leads,
    _needs_independent_overlap_review, _shared_found_duty_leads,
)


def _req(rid, text, kind, minimum=None):
    return ValidatedRequirement(
        requirement_id=rid, priority="required" if minimum else "preferred",
        name=text, jd_evidence=text, constraint=RequirementConstraint(
            kind=kind, minimum_years=minimum, origin="source_rules",
            requires_review=False))


R001 = _req("R001", "Minimum 3 years of relevant professional experience "
            "developing or delivering AI, machine-learning, deep-learning, or "
            "LLM-powered software.", "experience", 3)
R011 = _req("R011", "AI application development", "skill")
R018 = _req("R018", "Experience building production-oriented AI products, "
            "including deployable AI applications, APIs, containerized services, "
            "or cloud-ready solutions.", "experience")
CV_PATH = Path(__file__).resolve().parents[1] / "sample_data/applied_ai_resumes/06_rida_medical_imaging.txt"


class FlatEncoder:
    fingerprint = "v4921-role-recall"

    def embed_documents(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)

    def embed_queries(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)


class RecheckingProvider:
    disabled_reason = None

    def __init__(self):
        self.settings = Settings(llm_provider="ollama")
        self.prompts = []

    def prompt_fits(self, *_):
        return True

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        payload = json.loads(user_prompt)
        self.prompts.append(payload)
        sources = {item["id"]: item["text"] for item in payload["sources"]}
        result = {}
        for req in payload["requirements"]:
            rid = req["id"]
            if "second, independent" in system_prompt:
                assert rid in {"R001", "R018"}
                ids = (["S011", "S014"] if rid == "R001" else ["S014"])
                assert all(sid in sources for sid in ids)
                result[rid] = {
                    "decision": "found", "relation": "entailed",
                    "evidence_ids": ids,
                    "proof_excerpt": "Implemented a Python inference API",
                    "reason": ("A dated professional role and its actual implemented "
                               "inference service establish the requested professional work."),
                }
            elif rid == "R011":
                assert "S014" in sources
                result[rid] = {
                    "decision": "found", "relation": "entailed",
                    "evidence_ids": ["S014"], "matched_term": None,
                    "reason": "The completed inference API is AI application development.",
                }
            elif rid == "R018":
                # Reproduce a source-valid but overly conservative model
                # opinion: even a real completed API was called transferable.
                assert "S014" in sources
                result[rid] = {
                    "decision": "transferable", "relation": "overlap",
                    "evidence_ids": ["S014"], "matched_term": None,
                    "reason": "A completed inference API was built but research context is emphasized.",
                }
            else:
                result[rid] = {
                    "decision": "not_found", "relation": "absent",
                    "evidence_ids": [], "matched_term": None,
                    "reason": "A summary alone does not verify duties in the dated role.",
                }
        return schema.model_validate(result)


def test_work_delivery_recall_finds_own_duty_without_hardcoded_domain():
    segments = segment_resume(CV_PATH.read_text(encoding="utf-8"))
    originals = {s.segment_id: s for s in segments}
    leads = _completed_work_recall_leads(R018, originals, set(originals))
    assert leads
    assert "inference API" in originals[leads[0]].text
    assert originals[leads[0]].section == "experience"


def test_relevant_peer_found_evidence_can_be_reused_as_review_input_only():
    source = ResumeSegment("S014", "experience", "Implemented an inference API for clinicians.")
    accepted = RequirementAssessment(
        requirement_id="R011", status="matched", unified_status="Found",
        evidence_ids=["S014"], evidence_segments=[EvidenceCitation(
            segment_id="S014", section=source.section, text=source.text)])
    assert _shared_found_duty_leads(
        R018, {"R011": accepted}, [R011, R018], {"S014": source}) == ["S014"]
    assert _shared_found_duty_leads(
        R018, {"R011": accepted.model_copy(update={"unified_status": "Transferable"})},
        [R011, R018], {"S014": source}) == []


def test_one_independent_recheck_resolves_two_overlapping_role_criteria(tmp_path):
    cv = CV_PATH.read_text(encoding="utf-8")
    segments = segment_resume(cv)
    provider = RecheckingProvider()
    with UnifiedEvidenceEngine(
            provider.settings, provider, encoder=FlatEncoder(), top_k=25,
            cache_path=tmp_path / "role.sqlite") as engine:
        decisions, metrics = engine.assess(
            [R001, R011, R018], segments, cv, candidate_id="candidate-role")
    assert len(provider.prompts) == 2
    assert metrics.final_verification_calls == 1
    priorities = {item["id"]: item["priority_segments"]
                  for item in provider.prompts[0]["requirements"]}
    # A date heading AND original job-duty evidence outrank summaries.
    assert "S011" in priorities["R001"][:3]
    assert any(sid in priorities["R001"][:3] for sid in ("S012", "S014"))
    assert "S014" in priorities["R018"][:3]
    second = {r["id"]: r["priority_segments"]
              for r in provider.prompts[1]["requirements"]}
    assert "S014" in second["R018"]
    assert "S011" in second["R001"]
    by_id = {item.requirement_id: item for item in decisions}
    assert by_id["R018"].unified_status == "Found"
    assert by_id["R011"].unified_status == "Found"
    checked, _, _ = apply_experience_checks(
        requirements=[R001, R011, R018], assessments=decisions, resume_text=cv)
    checked_by_id = {row.requirement_id: row for row in checked}
    assert checked_by_id["R001"].status == "matched"
    assert "S011" in checked_by_id["R001"].evidence_ids
    assert "S014" in checked_by_id["R001"].evidence_ids


def test_unrelated_role_duties_are_never_automatically_credited():
    cv = ("Experience\nSupport Assistant | Example Org | Jan 2022 - Oct 2026\n"
          "- Managed desktop inventory tickets and replaced cables.")
    originals = {s.segment_id: s for s in segment_resume(cv)}
    assert not _completed_work_recall_leads(R018, originals, set(originals))
    row = RequirementAssessment(requirement_id="R001", status="not_matched",
                                unified_status="Not Found", reason="No relevant software duty established.")
    assert _needs_independent_overlap_review(R001, row, originals, cv)
    # A review trigger does not independently grant Found or experience years.
    checked, _, _ = apply_experience_checks(
        requirements=[R001], assessments=[row], resume_text=cv)
    assert checked[0].status != "matched"


def test_experience_schema_distinguishes_numeric_tenure_from_performed_scope():
    assert R001.constraint.experience_mode == "tenure"
    assert R018.constraint.experience_mode == "qualitative"
    assert R018.constraint.minimum_years is None
    assert R018.priority == "preferred"
    with pytest.raises(ValueError, match="experience_mode"):
        RequirementConstraint(kind="experience", experience_mode="tenure")
    with pytest.raises(ValueError, match="experience_mode"):
        RequirementConstraint(kind="skill", experience_mode="qualitative")


def test_preferred_skills_section_does_not_erase_qualitative_work_scope():
    text = "Preferred Skills:\nExperience building deployable APIs or cloud-ready solutions."
    row = _req("R018", "Experience building deployable APIs or cloud-ready solutions.", "experience")
    typed = classify_requirement(row, text)
    assert typed.kind == "experience"
    assert typed.experience_mode == "qualitative"
    assert typed.minimum_years is None


@pytest.mark.parametrize("only_skill", ["TensorFlow", "PyTorch"])
def test_explicit_or_skills_require_only_one_positive_capability(only_skill):
    text = "Required Skills:\nTensorFlow or PyTorch"
    base = _req("R006", "TensorFlow or PyTorch", "skill")
    typed = classify_requirement(base, text)
    assert typed.operator == "any_of"
    assert typed.options == ["TensorFlow", "PyTorch"]
    row = base.model_copy(update={"constraint": typed})
    result = evaluate_compound(row, f"Skills\n{only_skill}")
    assert result is not None and result.outcome == "matched"
