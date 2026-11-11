"""No silent frozen-JD omissions and no four-ID second-look blind spot.

The scenarios are synthetic and require no live API, Ollama, or cloud credit.
Semantic decisions still belong to the cited, independently checked model.
"""

import numpy as np
import pytest

from cv_ranker.config import Settings
from cv_ranker.fallback import structural_hints
from cv_ranker.jd import validate_jd_requirements
from cv_ranker.schemas import (EvidenceCitation, RequirementAssessment,
                               RequirementConstraint, ValidatedRequirement)
from cv_ranker.segments import ResumeSegment
from cv_ranker.unified import (UnifiedEvidenceEngine,
                               _needs_independent_overlap_review)


def test_nested_domain_sections_keep_all_tech_requirements_and_priorities():
    jd = """Required Qualifications:
- Four years professional experience with backend systems
Backend:
- Python
- Django
Cloud Services: Terraform, AWS

Preferred Qualifications:
Frontend:
- TypeScript

Benefits:
- Flexible working hours
"""
    source = structural_hints(jd)
    names = [(r.name, r.priority) for r in source]
    assert names == [
        ("Four years professional experience with backend systems", "required"),
        ("Python", "required"), ("Django", "required"),
        ("Terraform", "required"), ("AWS", "required"),
        ("TypeScript", "preferred"),
    ]


def test_large_explicit_jd_no_longer_truncates_at_old_30_default():
    jd = "Required Capabilities:\n" + "\n".join(
        f"- Independent capability {i:03d}" for i in range(1, 46))
    reqs, _, warnings = validate_jd_requirements(
        jd_text=jd, candidates=[], settings=Settings(), llm=None)
    assert len(reqs) == 45
    assert reqs[-1].name == "Independent capability 045"
    assert not any("cap:" in w or "configured maximum" in w for w in warnings)


def test_cli_cannot_rank_against_a_truncated_employer_jd(tmp_path):
    from cv_ranker.pipeline import CVRanker
    jd = tmp_path / "jd.txt"
    jd.write_text("Required Skills:\n- Python\n- Redis\n- Kotlin\n", encoding="utf-8")
    cv = tmp_path / "candidate.txt"
    cv.write_text("Technical Skills\nPython\n", encoding="utf-8")
    with pytest.raises(ValueError, match="JD extraction was truncated"):
        CVRanker(settings=Settings(max_requirements=2), use_llm=False).run(jd, [cv])


class EqualEncoder:
    fingerprint = "all-seven-sources-exact-original"

    def embed_documents(self, texts):
        return np.ones((len(texts), 5), dtype=np.float32)

    def embed_queries(self, texts):
        return np.ones((len(texts), 5), dtype=np.float32)


class FirstPassMissesNamedSkills:
    disabled_reason = None

    def __init__(self):
        self.settings = Settings(llm_provider="ollama")
        self.calls = []
        self.final_ids = []

    def prompt_fits(self, *_):
        return True

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        ids = list(schema.model_fields)
        self.calls.append(tuple(ids))
        if "second, independent" in system_prompt:
            self.final_ids.extend(ids)
            return schema.model_validate({rid: {
                "decision": "not_found", "relation": "absent",
                "evidence_ids": [f"S{int(rid[1:]):03d}"],
                "proof_excerpt": None,
                "reason": "The adjacent skill entry does not establish the exact composite JD capability.",
            } for rid in ids})
        return schema.model_validate({rid: {
            "decision": "not_found", "relation": "absent",
            "evidence_ids": [],
            "reason": "The first model overlooked the reported skill inventory.",
        } for rid in ids})


def test_last_optional_skill_is_not_skipped_by_four_id_review_cap(tmp_path):
    names = ["Python concurrency", "Docker orchestration", "Kotlin coroutines",
             "Redis clustering", "PostgreSQL replication", "Firebase authentication",
             "Terraform governance"]
    adjacent = ["Python scripting", "Docker images", "Kotlin mobile APIs",
                "Redis caching", "PostgreSQL queries", "Firebase storage",
                "Terraform provisioning"]
    requirements = [ValidatedRequirement(
        requirement_id=f"R{i:03d}", name=name, priority="preferred",
        jd_evidence=name,
        constraint=RequirementConstraint(kind="skill", operator="single", origin="source_rules"))
        for i, name in enumerate(names, 1)]
    sources = [ResumeSegment(f"S{i:03d}", "skills", name)
               for i, name in enumerate(adjacent, 1)]
    model = FirstPassMissesNamedSkills()
    with UnifiedEvidenceEngine(
        model.settings, model, encoder=EqualEncoder(), top_k=8,
        cache_path=tmp_path / "cache.sqlite") as engine:
        assessments, metrics = engine.assess(
            requirements, sources, "\n".join(adjacent), candidate_id="candidate")
    assert sorted(model.final_ids) == [r.requirement_id for r in requirements], (
        model.calls, [(r.requirement_id, r.unified_status, r.reason) for r in assessments], metrics.public())
    assert len(model.final_ids) == len(set(model.final_ids)) == 7
    assert metrics.final_verification_calls == 2
    assert all(row.unified_status == "Not Found" for row in assessments)
    assert assessments[-1].evidence_ids == ["S007"]
    assert all(row.assessment_state == "verified" for row in assessments)


def test_cited_completed_alternative_gets_unscored_transferable_review():
    req = ValidatedRequirement(
        requirement_id="R001", name="LangChain", priority="required",
        jd_evidence="LangChain",
        constraint=RequirementConstraint(kind="skill", operator="single", origin="source_rules"))
    source = ResumeSegment("S008", "projects",
                           "Built retrieval and orchestration pipelines with Haystack.")
    row = RequirementAssessment(
        requirement_id="R001", status="not_matched", unified_status="Not Found",
        evidence_ids=["S008"], evidence_segments=[EvidenceCitation(
            segment_id="S008", section="projects", text=source.text)],
        reason="The candidate used an alternative framework, but not the named LangChain tool.")
    assert _needs_independent_overlap_review(
        req, row, {"S008": source}, source.text)
    # The recall gate does not grant Found or Transferable by itself.
    assert row.unified_status == "Not Found"
