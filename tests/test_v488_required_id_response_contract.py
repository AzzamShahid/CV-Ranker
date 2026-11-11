"""Provider-shaped batch tests; all role names are synthetic test fixtures."""
import json

import numpy as np

from cv_ranker.config import Settings
from cv_ranker.schemas import ValidatedRequirement
from cv_ranker.scoring import assign_ranks, score_candidate
from cv_ranker.segments import ResumeSegment
from cv_ranker.unified import UnifiedEvidenceEngine


class FlatEncoder:
    fingerprint = "id-keyed-across-departments"

    def embed_documents(self, texts):
        return np.tile(np.array([[1., 0.]], dtype=np.float32), (len(texts), 1))

    def embed_queries(self, texts):
        return np.tile(np.array([[1., 0.]], dtype=np.float32), (len(texts), 1))


class KeyedProvider:
    """Emulates schema-constrained OpenRouter/Ollama, not their judgment quality."""
    disabled_reason = None

    def __init__(self, *, bad_last_once=False):
        self.settings = Settings(llm_provider="ollama")
        self.calls = []
        self.bad_last_once = bad_last_once

    def prompt_fits(self, system_prompt, user_prompt):
        return True

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        data = json.loads(user_prompt)
        expected = [req["id"] for req in data["requirements"]]
        # The schema itself—not instructions in a prompt—must make every
        # supplied requirement a REQUIRED top-level field.
        assert schema.model_json_schema()["required"] == expected
        self.calls.append(expected)
        source_map = {source["id"]: source["text"] for source in data["sources"]}
        verdicts = {}
        for req in data["requirements"]:
            matching = [sid for sid, statement in source_map.items()
                        if req["name"] in statement]
            found = bool(matching)
            chosen = matching[:1]
            if (self.bad_last_once and len(expected) == 1
                    and len(self.calls) > 1):
                self.bad_last_once = False
            elif self.bad_last_once and req["id"] == "R018":
                chosen = ["NONEXISTENT"]
            verdicts[req["id"]] = {
                "decision": "found" if found else "not_found",
                "evidence_ids": chosen if found else [],
                "matched_term": None,
                "reason": ("Completed work in the source establishes this capability."
                           if found else "No completed candidate claim establishes this duty."),
            }
        return schema.model_validate(verdicts)


ROLE_NEUTRAL_DUTIES = [
    "clinical appointment scheduling", "monthly retail cash reconciliation",
    "warehouse inventory control", "industrial compliance inspection",
    "technical customer onboarding", "supplier invoice review",
    "construction project handover", "patient intake coordination",
    "school attendance reporting", "restaurant kitchen safety",
    "fleet route scheduling", "human resources induction",
    "marketing campaign tracking", "legal document indexing",
    "property maintenance coordination", "museum collection cataloguing",
    "emergency logistics planning", "production quality monitoring",
]


def test_five_fictional_candidates_have_18_resolved_criteria_without_id_loss(tmp_path):
    requirements = [ValidatedRequirement(
        requirement_id=f"R{index:03}", name=duty, priority="required",
        jd_evidence=duty) for index, duty in enumerate(ROLE_NEUTRAL_DUTIES, 1)]
    results = []
    total_calls = 0
    for present in (18, 14, 9, 4, 0):
        segments = [ResumeSegment(segment_id=f"S{index:03}", section="experience",
                                  text=f"Developed {duty} in a completed project.")
                    for index, duty in enumerate(ROLE_NEUTRAL_DUTIES[:present], 1)]
        segments.append(ResumeSegment(segment_id="S999", section="summary",
                                      text="Available for work in operations."))
        llm = KeyedProvider()
        with UnifiedEvidenceEngine(llm.settings, llm,
                                   cache_path=tmp_path / f"resume-{present}.db",
                                   encoder=FlatEncoder()) as engine:
            decisions, metrics = engine.assess(
                requirements, segments, "\n".join(s.text for s in segments),
                candidate_id=f"fictional-{present}")
        assert len(decisions) == 18
        assert metrics.unresolved_criteria == 0
        assert all(row.assessment_state == "verified" for row in decisions)
        assert sum(row.unified_status == "Found" for row in decisions) == present
        assert len(llm.calls) == 4  # 18 criteria, 5+5+5+3; no per-criterion calls.
        total_calls += len(llm.calls)
        results.append(score_candidate(
            candidate_name=f"Worker-{present}", requirements=requirements,
            assessments=decisions, evaluation_mode="llm_assessed", errors=[]))
    assert total_calls == 20
    assert [person.candidate_name for person in assign_ranks(results)] == [
        "Worker-18", "Worker-14", "Worker-9", "Worker-4", "Worker-0"]
    assert all(person.rank is not None for person in results)


def test_last_requirement_bad_citation_is_repaired_with_one_keyed_call(tmp_path):
    requirements = [ValidatedRequirement(
        requirement_id=f"R{index:03}", name=duty, priority="required",
        jd_evidence=duty) for index, duty in enumerate(ROLE_NEUTRAL_DUTIES, 1)]
    segments = [ResumeSegment(segment_id=f"S{index:03}", section="experience",
                              text=f"Developed {duty} in a completed project.")
                for index, duty in enumerate(ROLE_NEUTRAL_DUTIES, 1)]
    llm = KeyedProvider(bad_last_once=True)
    with UnifiedEvidenceEngine(llm.settings, llm,
                               cache_path=tmp_path / "correction.db",
                               encoder=FlatEncoder()) as engine:
        decisions, metrics = engine.assess(
            requirements, segments, "\n".join(s.text for s in segments),
            candidate_id="fictional-correction")
    assert metrics.correction_calls == 1
    assert len(llm.calls) == 5
    assert llm.calls[-1] == ["R018"]
    assert metrics.unresolved_criteria == 0
    assert len(decisions) == 18
    assert all(row.unified_status == "Found" for row in decisions)
