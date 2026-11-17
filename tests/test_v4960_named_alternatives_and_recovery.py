"""Universal named-condition alternative and bounded recovery regressions.

These cases reproduce v4.9.59's erroneous treatment of ERP OR MES as
ERP AND MES. All candidate sources are fictional; no provider calls.
"""
import pytest

from cv_ranker.assessor import _missing_explicit_named_conditions, _validate_rows
from cv_ranker.schemas import (EvidenceCitation, LLMAssessmentItem,
    LLMCandidateAssessmentResponse, RequirementConstraint, ValidatedRequirement)
from cv_ranker.segments import ResumeSegment
from cv_ranker.unified import _source_repair_hits

JD = "Use of ERP or manufacturing execution systems (MES) for weaving production reporting."


def req(text=JD):
    return ValidatedRequirement(requirement_id="R015", name=text,
        jd_evidence=text, priority="required",
        constraint=RequirementConstraint(kind="responsibility", origin="source_rules"))


def validate(text, requirement=None, *, section="experience"):
    requirement = requirement or req()
    segment = ResumeSegment("S011", section, text)
    response = LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
        requirement_id="R015", status="matched", evidence_ids=["S011"],
        reason="The cited original candidate work covers the frozen requirement.")])
    valid, invalid, warnings, _ = _validate_rows(response=response,
        requirements=[requirement], resume_text=text, segments=[segment],
        semantic_grounded=True)
    return valid, invalid, warnings


@pytest.mark.parametrize("text", [
    "Used ERP dashboards for weaving production reports during every shift.",
    "Used MES dashboards for weaving production reporting during every shift.",
    "Used manufacturing execution systems for weaving production reporting.",
])
def test_one_explicit_or_alternative_is_enough_for_named_guard(text):
    valid, invalid, warnings = validate(text)
    assert not invalid, warnings
    assert valid["R015"].status == "matched"


def test_neither_named_alternative_must_not_receive_found():
    valid, invalid, warnings = validate(
        "Prepared weaving production reports by hand on paper shift sheets.")
    assert "R015" in invalid or valid["R015"].status != "matched", warnings


def test_explicit_and_requires_both_named_conditions():
    mandatory = req("Use ERP and MES for production reporting")
    valid, invalid, warnings = validate(
        "Used ERP dashboards for production reporting.", mandatory)
    assert "R015" in invalid or valid["R015"].status != "matched", warnings
    both, bad, notices = validate(
        "Used ERP and MES dashboards for production reporting.", mandatory)
    assert not bad, notices
    assert both["R015"].status == "matched"


def test_grouped_or_and_other_mandatory_named_condition():
    conditional = req("Use (ERP or MES) and SQL for operational reporting")
    for passage in ["Used ERP and SQL for operational reporting.",
                    "Used MES and SQL for operational reporting."]:
        valid, invalid, warnings = validate(passage, conditional)
        assert not invalid, warnings
        assert valid["R015"].status == "matched"
    valid, invalid, warnings = validate("Used ERP for operational reporting.", conditional)
    assert "R015" in invalid or valid["R015"].status != "matched", warnings


def test_a_recovery_attempt_prioritizes_new_original_named_alternative():
    requirement = req()
    originals = {
        "S011": ResumeSegment("S011", "experience", "Prepared manual shift reports and logged defects."),
        "S015": ResumeSegment("S015", "experience",
            "Used ERP dashboards to create weaving production reporting for supervisors."),
        "S005": ResumeSegment("S005", "summary", "Weaving shift supervisor with four years experience."),
    }
    hits, skipped = _source_repair_hits([requirement], originals,
        {"R015": ["S011", "S005"]},
        ["R015: cited CV source did not establish explicitly named JD condition(s): ERP or MES"],
        set(originals))
    assert "R015" not in skipped
    assert hits["R015"][0] == "S015"


def test_no_new_alternative_prevents_repeating_identical_evidence_only_correction():
    requirement = req()
    originals = {"S011": ResumeSegment("S011", "experience",
        "Prepared paper shift reports and logged machine defects.")}
    hits, skipped = _source_repair_hits([requirement], originals,
        {"R015": ["S011"]},
        ["R015: cited CV source did not establish explicitly named JD condition(s): ERP or MES"],
        set(originals))
    assert hits["R015"] == ["S011"]
    assert "R015" in skipped


def test_unrelated_tool_does_not_qualify_as_named_alternative():
    valid, invalid, warnings = validate(
        "Used SQL dashboards for weaving production reporting, without ERP or MES access.")
    assert "R015" in invalid or valid["R015"].status != "matched", warnings


def test_skills_inventory_alone_does_not_prove_duty_with_tool():
    valid, invalid, warnings = validate("Skills: ERP; shift coordination; loom inspection.",
                                       section="skills")
    assert "R015" in invalid or valid["R015"].status != "matched", warnings

@pytest.mark.parametrize("text", [
    "ERP or MES for manufacturing reporting",
    "ERP or manufacturing execution systems (MES) for weaving reporting",
])
def test_alternative_with_first_acronym_is_not_accidentally_omitted(text):
    requirement = req(text)
    from cv_ranker.assessor import _named_condition_groups
    groups = _named_condition_groups(requirement)
    assert [name for group in groups for name in group] == ["ERP", "MES"]


def test_spelled_out_negative_is_not_positive_acronym_proof():
    requirement = req()
    valid, invalid, warnings = validate(
        "No manufacturing execution systems experience; used manual weaving reports.", requirement)
    assert "R015" in invalid or valid["R015"].status != "matched", warnings


def test_contiguous_proper_name_is_a_single_named_condition():
    from cv_ranker.assessor import _named_condition_groups
    requirements = req("Operate Google Cloud or AWS for production analytics")
    assert _named_condition_groups(requirements) == [["Google Cloud", "AWS"]]

# These tests execute the shipping retrieval -> validation -> correction ->
# finalizer path with controlled JSON replies; the model is not mocked away
# downstream of its original citation or verdict.
class FlatEncoder:
    fingerprint = "v4960-conditional-source-regression"

    def embed_documents(self, texts):
        import numpy as np
        return np.ones((len(texts), 3), dtype=np.float32)

    def embed_queries(self, texts):
        import numpy as np
        return np.ones((len(texts), 3), dtype=np.float32)


class ConditionalModel:
    disabled_reason = None

    def __init__(self, *, scenario):
        from cv_ranker.config import Settings
        self.settings = Settings(llm_provider="ollama")
        self.scenario = scenario
        self.calls = 0
        self.packets = []

    def prompt_fits(self, system_prompt, user_prompt):
        return True

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        import json
        from cv_ranker.unified import UnifiedItem, UnifiedResponse
        self.calls += 1
        packet = json.loads(user_prompt)
        self.packets.append(packet)
        sources = {s["id"]: s["text"] for s in packet["sources"]}
        if schema.__name__ == "IndependentSemanticDecisionByID":
            if self.scenario == "related_only":
                return schema.model_validate({"R015": {
                    "decision": "transferable", "relation": "overlap",
                    "evidence_ids": ["S011"], "proof_excerpt": None,
                    "reason": "Candidate independently completed related reporting, but named system use is absent."}})
            return schema.model_validate({"R015": {
                "decision": "not_found", "relation": "absent",
                "evidence_ids": ["S011"], "proof_excerpt": None,
                "reason": "The original source does not establish a required named system or reporting use."}})
        if self.scenario == "recover_source" and self.calls == 1:
            assert "S011" in sources
            cited = "S011"  # intentionally wrong primary source
        else:
            cited = "S015" if "S015" in sources else "S011"
        return UnifiedResponse(assessments=[UnifiedItem(
            requirement_id="R015", decision="found", relation="direct",
            evidence_ids=[cited],
            reason="The source shows candidate use of the named reporting system.")])


def integrated_assessment(tmp_path, *, scenario, sources):
    from cv_ranker.unified import UnifiedEvidenceEngine
    provider = ConditionalModel(scenario=scenario)
    with UnifiedEvidenceEngine(provider.settings, provider,
                               encoder=FlatEncoder(),
                               cache_path=tmp_path / (scenario + ".sqlite"),
                               top_k=8) as engine:
        rows, metrics = engine.assess([req()], sources,
            "\n".join(seg.text for seg in sources), candidate_id="fictional-" + scenario)
    return rows[0], metrics, provider


def test_end_to_end_or_erp_found_no_unverified(tmp_path):
    sources = [ResumeSegment("S011", "experience",
        "Used ERP dashboards to prepare weaving production reports and shift summaries.")]
    result, metrics, provider = integrated_assessment(tmp_path, scenario="direct_erp", sources=sources)
    assert result.unified_status == "Found"
    assert result.assessment_state == "verified"
    assert metrics.unresolved_criteria == 0
    assert provider.calls == 1


def test_end_to_end_invalid_first_citation_changes_to_better_original_source(tmp_path):
    sources = [
        ResumeSegment("S011", "experience", "Prepared manual weaving shift reports for supervisors."),
        ResumeSegment("S015", "experience", "Used ERP dashboards to generate weaving production reports."),
    ]
    result, metrics, provider = integrated_assessment(
        tmp_path, scenario="recover_source", sources=sources)
    assert result.unified_status == "Found", (result.reason, metrics.public())
    assert result.assessment_state == "verified"
    assert metrics.unresolved_criteria == 0
    assert provider.calls == 2
    assert metrics.correction_calls == 1
    assert "S015" in {source["id"] for source in provider.packets[1]["sources"]}


def test_end_to_end_unsupported_found_is_finalized_as_unscored_negative(tmp_path):
    sources = [ResumeSegment("S011", "experience",
        "Operated weaving looms and prepared manual shift reports.")]
    result, metrics, provider = integrated_assessment(
        tmp_path, scenario="negative_only", sources=sources)
    assert result.unified_status == "Not Found", (result.reason, metrics.public())
    assert result.assessment_state == "verified"
    assert metrics.unresolved_criteria == 0
    assert provider.calls == 2  # primary + single independent review
    assert metrics.correction_calls == 0
    assert metrics.final_verification_calls == 1


def test_end_to_end_related_work_stays_transferable_not_direct_credit(tmp_path):
    sources = [ResumeSegment("S011", "experience",
        "Prepared manual weaving production reports and tracked shift output defects.")]
    result, metrics, provider = integrated_assessment(
        tmp_path, scenario="related_only", sources=sources)
    assert result.unified_status == "Transferable", (result.reason, metrics.public())
    assert result.status != "matched"
    assert result.assessment_state == "verified"
    assert metrics.unresolved_criteria == 0
    assert provider.calls == 2

@pytest.mark.parametrize("text", [
    "Used ERP dashboards to prepare weaving production reports during shifts.",
    "Used MES dashboards to prepare weaving production reports during shifts.",
])
def test_complete_postprocessing_retains_source_valid_direct_or_work(text):
    """Model -> source gate -> compound check -> finalizer -> score must agree."""
    from cv_ranker.compound_validation import apply_compound_checks
    from cv_ranker.pipeline import reconcile_final_assessments
    from cv_ranker.scoring import score_candidate
    from cv_ranker.segments import segment_resume
    requirement = req()
    requirement = requirement.model_copy(update={"constraint": RequirementConstraint(
        kind="responsibility", operator="complex", requires_review=True,
        origin="source_rules")})
    cv = "Professional Experience\n- " + text
    segments = segment_resume(cv)
    evidence = next(s for s in segments if "dashboards" in s.text)
    response = LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
        requirement_id="R015", status="matched", evidence_ids=[evidence.segment_id],
        reason="Original citation reports directly completed system-based weaving reporting.")])
    checked, invalid, errors, _ = _validate_rows(response=response,
        requirements=[requirement], resume_text=cv, segments=segments,
        semantic_grounded=True)
    assert not invalid, errors
    before = checked["R015"].model_copy(update={"unified_status": "Found"})
    compound, _, notices = apply_compound_checks(
        requirements=[requirement], assessments=[before], resume_text=cv)
    final = reconcile_final_assessments(requirements=[requirement], assessments=compound)
    assert final[0].unified_status == "Found", (notices, final[0].reason)
    assert final[0].evidence_ids == before.evidence_ids
    result = score_candidate(candidate_name="Fictional worker", requirements=[requirement],
        assessments=final, evaluation_mode="llm_assessed", errors=[])
    assert result.primary_score == 100.0

@pytest.mark.parametrize("sentence,shown,expected_missing", [
    ("ERP or MES", "Used ERP for operations.", []),
    ("ERP or MES", "Used MES for operations.", []),
    ("ERP or MES", "Used SQL for operations.", ["ERP or MES"]),
    ("ERP and MES", "Used ERP for operations.", ["MES"]),
    ("ERP and MES", "Used both ERP and MES for operations.", []),
])
def test_compact_named_and_or_has_correct_boolean_guard(sentence, shown, expected_missing):
    requirement = req(sentence)
    source = EvidenceCitation(segment_id="S011", section="experience", text=shown)
    assert _missing_explicit_named_conditions(requirement, [source]) == expected_missing

@pytest.mark.parametrize("description", [
    "Use ERP and/or MES for production reporting",
    "Use ERP and / or MES for production reporting",
])
def test_explicit_and_or_has_inclusive_alternative_semantics(description):
    requirement = req(description)
    for cited in ["Used ERP for production reporting.", "Used MES for production reporting."]:
        citation = EvidenceCitation(segment_id="S011", section="experience", text=cited)
        assert not _missing_explicit_named_conditions(requirement, [citation])
