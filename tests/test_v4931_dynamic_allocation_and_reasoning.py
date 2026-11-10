"""Regression contract: editable frozen-JD weights and evidence-based Why views."""
import io
import json
from math import nan
from zipfile import ZipFile

import pytest

from cv_ranker.ranking_reasoning import candidate_reasoning, comparative_reasoning
from cv_ranker.report_bundle import complete_results_zip
from cv_ranker.schemas import (CandidateResult, RankingReport, RequirementAssessment,
                               RequirementConstraint, ValidatedRequirement)
from cv_ranker.ui_support import final_leaderboard_rows
from cv_ranker.weighted_scoring import (
    ScoreWeights, allocation_bucket, even_requirement_shares,
    rebalance_requirement_share, weighted_candidate, weighted_leaderboard,
)


def req(rid, name=None, kind="skill", priority="required", minimum_years=None):
    return ValidatedRequirement(
        requirement_id=rid, name=name or rid, priority=priority, jd_evidence=name or rid,
        constraint=RequirementConstraint(kind=kind, minimum_years=minimum_years))


def cv(name, statuses, *, incomplete=False):
    return CandidateResult(
        candidate_name=name, candidate_source=f"uploaded://{name}.txt",
        primary_score=None if incomplete else 50,
        evaluation_mode="failed" if incomplete else "llm_assessed",
        assessments=[RequirementAssessment(
            requirement_id=rid,
            status="matched" if value == "Found" else "not_matched",
            unified_status="Unverified" if incomplete else value,
            assessment_state="unverified" if incomplete else "verified",
            reason=f"Recorded requirement reasoning: {rid} is {value}")
            for rid, value in statuses.items()],
    )


def snapshot(requirements, candidates):
    return RankingReport(job_description_source="JD", original_jd_text="Approved JD",
                         jd_validation_mode="llm_validated", yake_candidates=[],
                         requirements=requirements, candidates=candidates)


def customized(requirements, changed_id, new_percentage, **categories):
    shares = even_requirement_shares(requirements)
    shares = rebalance_requirement_share(requirements, shares, changed_id, new_percentage)
    return ScoreWeights(**categories, requirement_shares=tuple(sorted(shares.items())))


def detailed(requirements, statuses, *, missing_why=False, conflicting=False, invalid_citation=False):
    rows = []
    for requirement in requirements:
        status = statuses[requirement.requirement_id]
        rows.append({
            "ID": requirement.requirement_id,
            "Result": "Not Found" if conflicting and status == "Found" else status,
            "Why": "" if missing_why else f"CV stated {requirement.name} in source S001",
            "Checkpoints": [{"Segment": "S001", "Text": "CV stated " + requirement.name,
                             "Validated against CV": not invalid_citation}],
        })
    return {"Criteria": rows}


def test_equal_share_defaults_do_not_change_existing_scores():
    r = [req("tenure", kind="experience", minimum_years=3), req("degree", kind="education"),
         req("python"), req("api", priority="preferred"), req("cloud", priority="preferred")]
    person = cv("Old score", {"tenure": "Found", "degree": "Found", "python": "Found",
                              "api": "Found", "cloud": "Not Found"})
    report = snapshot(r, [person])
    before = weighted_candidate(report, person, ScoreWeights())["score"]
    even = ScoreWeights(requirement_shares=tuple(even_requirement_shares(r).items()))
    after = weighted_candidate(report, person, even)["score"]
    assert before == after == 73.33


def test_single_python_share_25_percent_of_jd_80_percent_earns_20_points():
    r = ([req("tenure", kind="experience", minimum_years=3), req("degree", kind="education")]
         + [req("python")] + [req(f"other_{i}", priority="preferred") for i in range(15)])
    statuses = {row.requirement_id: "Not Found" for row in r}
    statuses.update({"tenure": "Found", "degree": "Found", "python": "Found"})
    person = cv("Engineer", statuses)
    report = snapshot(r, [person])
    original = weighted_candidate(report, person, ScoreWeights())
    edited = weighted_candidate(report, person, customized(r, "python", 25))
    assert original["score"] == 25.0  # 10 + 10 + (80 / 16)
    assert edited["score"] == 40.0  # 10 + 10 + (80 * 25%)
    python = next(v for v in edited["requirement_contributions"] if v["requirement_id"] == "python")
    assert python["share_of_category"] == 25
    assert python["possible_points"] == python["earned_points"] == 20
    assert sum(v["share_of_category"] for v in edited["requirement_contributions"]
               if v["category"] == "jd") == pytest.approx(100)


def test_rebalancing_only_affects_its_own_bucket_and_preserves_total():
    r = [req("xp1", kind="experience", minimum_years=3),
         req("xp2", kind="experience", minimum_years=5),
         req("degree1", kind="education"), req("degree2", kind="education"),
         req("R1"), req("P1", priority="preferred"), req("P2", priority="preferred")]
    before = even_requirement_shares(r)
    after = rebalance_requirement_share(r, before, "P1", 80)
    assert after["P1"] == 80
    assert after["xp1"] == before["xp1"] == 50
    assert after["degree1"] == before["degree1"] == 50
    assert after["R1"] + after["P1"] + after["P2"] == pytest.approx(100)
    assert allocation_bucket(r[5]) == allocation_bucket(r[4]) == "jd"
    assert sum(after[row.requirement_id] for row in r if allocation_bucket(row) == "experience") == 100


def test_all_three_categories_have_independent_editable_requirement_shares():
    r = [req("xp1", kind="experience", minimum_years=3),
         req("xp2", kind="experience", minimum_years=5),
         req("deg1", kind="education"), req("deg2", kind="education"),
         req("R1"), req("P1", priority="preferred")]
    shares = even_requirement_shares(r)
    for rid, pct in (("xp1", 80), ("deg1", 25), ("R1", 30)):
        shares = rebalance_requirement_share(r, shares, rid, pct)
    weights = ScoreWeights(experience=20, education=30, jd=50,
                           requirement_shares=tuple(sorted(shares.items())))
    statuses = {row.requirement_id: ("Found" if row.requirement_id in {"xp1", "deg1", "R1"}
                                     else "Not Found") for row in r}
    person = cv("A", statuses)
    result = weighted_candidate(snapshot(r, [person]), person, weights)
    assert result["score"] == 38.5  # 20*.80 + 30*.25 + 50*.30
    points = {row["requirement_id"]: row["earned_points"]
              for row in result["requirement_contributions"]}
    assert (points["xp1"], points["deg1"], points["R1"]) == (16, 7.5, 15)


def test_zero_peer_allocations_can_be_reintroduced_and_singleton_is_fixed():
    r = [req("R1"), req("R2"), req("R3"), req("degree", kind="education")]
    shares = rebalance_requirement_share(r, even_requirement_shares(r), "R1", 100)
    assert shares["R2"] == shares["R3"] == 0
    recovered = rebalance_requirement_share(r, shares, "R1", 10)
    assert recovered["R1"] == 10
    assert recovered["R2"] == recovered["R3"] == 45
    with pytest.raises(ValueError, match="one requirement"):
        rebalance_requirement_share(r, recovered, "degree", 25)


@pytest.mark.parametrize("value", [nan, float("inf"), -1, 101, True])
def test_bad_per_requirement_input_is_rejected(value):
    r = [req("R1"), req("R2")]
    with pytest.raises(ValueError):
        rebalance_requirement_share(r, even_requirement_shares(r), "R1", value)


def test_bad_id_missing_coverage_or_category_total_is_rejected():
    r = [req("R1"), req("P1", priority="preferred")]
    person = cv("A", {"R1": "Found", "P1": "Found"})
    report = snapshot(r, [person])
    with pytest.raises(ValueError, match="precisely"):
        weighted_candidate(report, person, ScoreWeights(requirement_shares=(("R1", 100),)))
    with pytest.raises(ValueError, match="total 100"):
        weighted_candidate(report, person, ScoreWeights(requirement_shares=(("R1", 70), ("P1", 20))))
    with pytest.raises(ValueError, match="total 100"):
        weighted_candidate(report, person, ScoreWeights(requirement_shares=(("R1", 70), ("P1", 30.01))))
    with pytest.raises(ValueError, match="unique"):
        ScoreWeights(requirement_shares=(("R1", 50), ("R1", 50)))


def test_required_preferred_split_stays_visual_only_with_custom_allocations():
    r = [req("R1"), req("P1", priority="preferred")]
    person = cv("A", {"R1": "Not Found", "P1": "Found"})
    report = snapshot(r, [person])
    combined = customized(r, "P1", 90)
    split = ScoreWeights(split_jd=True, requirement_shares=combined.requirement_shares)
    assert weighted_candidate(report, person, combined)["score"] == 90
    assert weighted_candidate(report, person, split)["score"] == 90


def test_comparative_reasoning_reorders_and_cites_only_frozen_criteria():
    r = [req("R1", "Python"), req("P1", "Docker", priority="preferred")]
    people = [cv("First", {"R1": "Found", "P1": "Not Found"}),
              cv("Second", {"R1": "Not Found", "P1": "Found"})]
    report = snapshot(r, people)
    finals = {"0": detailed(r, {"R1": "Found", "P1": "Not Found"}),
              "1": detailed(r, {"R1": "Not Found", "P1": "Found"})}
    before = comparative_reasoning(report, ScoreWeights(), finals)
    assert len(before["top_candidate_indices"]) == 2
    weights = customized(r, "R1", 90)
    after = comparative_reasoning(report, weights, finals)
    assert after["top_candidate_indices"] == [0]
    assert after["comparisons"][0]["score_gap"] == 80
    assert after["comparisons"][0]["top_candidate_advantages"][0]["requirement"] == "Python"
    assert after["comparisons"][0]["top_candidate_advantages"][0]["validated_segment_ids"] == ["S001"]
    assert people[0].primary_score == people[1].primary_score == 50  # no mutation


def test_missing_or_conflicting_why_is_locally_repaired_without_score_changes():
    r = [req("R1", "Python")]
    person = cv("A", {"R1": "Found"})
    report = snapshot(r, [person])
    wrong = {"0": detailed(r, {"R1": "Found"}, missing_why=True, conflicting=True,
                           invalid_citation=True)}
    result = candidate_reasoning(report, 0, ScoreWeights(), wrong)
    assert result["weighted_score"] == 100
    assert result["criteria"][0]["decision"] == "Found"
    assert result["criteria"][0]["validated_segment_ids"] == []
    assert "validated assessment records" in result["criteria"][0]["why"]
    assert result["audit"]["external_reasoning_requests"] == 0
    assert len(result["audit"]["repairs"]) == 1
    assert person.assessments[0].status == "matched"
    assert wrong["0"]["Criteria"][0]["Result"] == "Not Found"  # source not mutated


def test_reasoning_rechecks_exact_original_cv_ledger_not_just_claimed_validity():
    r = [req("R1", "Python")]
    report = snapshot(r, [cv("A", {"R1": "Found"})])
    final = {"0": detailed(r, {"R1": "Found"})}
    correct = {"0": [{"segment_id": "S001", "text": "CV stated Python"}]}
    checked = candidate_reasoning(report, 0, ScoreWeights(), final, correct)
    assert checked["criteria"][0]["validated_segment_ids"] == ["S001"]
    assert checked["audit"]["status"] == "structurally_valid"

    altered = {"0": [{"segment_id": "S001", "text": "Different source passage"}]}
    repaired = candidate_reasoning(report, 0, ScoreWeights(), final, altered)
    assert repaired["criteria"][0]["validated_segment_ids"] == []
    assert any("altered" in issue for issue in repaired["audit"]["repairs"][0]["issues"])
    assert repaired["weighted_score"] == 100


def test_incomplete_candidates_remain_unranked_and_why_is_provisional():
    r = [req("R1")]
    report = snapshot(r, [cv("A", {"R1": "Found"}),
                          cv("Failed", {"R1": "Not Found"}, incomplete=True)])
    rows = comparative_reasoning(report, ScoreWeights())
    assert rows["top_candidate_indices"] == [0]
    failed = next(x for x in rows["candidates"] if x["candidate"] == "Failed")
    assert failed["weighted_score"] is None and failed["rank"] is None
    assert failed["audit"]["status"] == "incomplete"


def test_legacy_review_metadata_tracks_original_index_even_after_backend_sort():
    r = [req("R1")]
    report = snapshot(r, [cv("Low", {"R1": "Not Found"}),
                          cv("High", {"R1": "Found"})])
    report.candidates[0].primary_score = 10
    report.candidates[1].primary_score = 90
    rows = final_leaderboard_rows(report)
    assert [(row["Candidate"], row["Candidate index"]) for row in rows] == [("High", 1), ("Low", 0)]


def test_complete_export_includes_weight_shares_contributions_candidate_and_comparative_why():
    r = [req("R1"), req("P1", priority="preferred")]
    report = snapshot(r, [cv("A", {"R1": "Found", "P1": "Not Found"}),
                          cv("B", {"R1": "Not Found", "P1": "Found"})])
    weights = customized(r, "R1", 75)
    finals = {"0": detailed(r, {"R1": "Found", "P1": "Not Found"}),
              "1": detailed(r, {"R1": "Not Found", "P1": "Found"})}
    with ZipFile(io.BytesIO(complete_results_zip(report, weights, final_results=finals))) as z:
        assert z.testzip() is None
        allocation = json.loads(z.read("weighted_requirement_allocations.json"))
        overall = json.loads(z.read("overall_ranking_reasoning.json"))
        one = json.loads(z.read("candidates/candidate_001_results.json"))
        assert allocation[0]["contributions"][0]["possible_points"] == 75
        assert overall["top_candidate_indices"] == [0]
        assert one["candidate_ranking_why"]["rank"] == 1
        assert one["why"][0]["reason"].startswith("CV stated")


def test_actual_streamlit_editor_rebalances_after_one_requirement_is_changed():
    from streamlit.testing.v1 import AppTest

    def editor_page():
        import streamlit as st
        from cv_ranker.schemas import ValidatedRequirement
        from cv_ranker.ui.dashboard import _weightage_panel

        approved = [ValidatedRequirement(requirement_id=rid, name=rid,
                                         priority="required" if rid == "Python" else "preferred",
                                         jd_evidence=rid)
                    for rid in ("Python", "Docker", "Node", "Cloud")]
        _weightage_panel(approved)
        st.write("Allocation editor ready")

    app = AppTest.from_function(editor_page).run(timeout=20)
    assert not app.exception
    digest, amounts = next(iter(app.session_state["cv_requirement_allocations"].items()))
    assert amounts["Python"] == 25.0
    widget = next(item for item in app.number_input if item.key.endswith("_Python"))
    app = widget.set_value(40.0).run(timeout=20)
    assert not app.exception
    amounts = app.session_state["cv_requirement_allocations"][digest]
    assert amounts["Python"] == 40.0
    assert sum(amounts.values()) == pytest.approx(100.0)
    assert all(amounts[item] == 20.0 for item in ("Docker", "Node", "Cloud"))


@pytest.mark.parametrize("review_case", ["complete", "first_withheld", "all_withheld"])
def test_actual_streamlit_ranking_and_individual_why_render_with_two_candidates(review_case):
    from streamlit.testing.v1 import AppTest

    def results_page():
        import streamlit as st
        from cv_ranker.schemas import (CandidateResult, RequirementAssessment, RankingReport,
                                       ValidatedRequirement)
        from cv_ranker.ui.dashboard import _candidate_evidence, _ranking

        requirements = [ValidatedRequirement(requirement_id="R1", name="Python",
                                             priority="required", jd_evidence="Python"),
                        ValidatedRequirement(requirement_id="R2", name="Testing",
                                             priority="required", jd_evidence="Testing"),
                        ValidatedRequirement(requirement_id="P1", name="Docker",
                                             priority="preferred", jd_evidence="Docker")]
        candidates = []
        results = {}
        review_case = st.session_state.get("test_review_case", "complete")
        for index, name in enumerate(("Ada", "Ben")):
            statuses = ({"R1": "Found", "R2": "Not Found", "P1": "Not Found"}
                        if index == 0 else {"R1": "Not Found", "R2": "Found", "P1": "Found"})
            incomplete = (review_case == "all_withheld" or
                          (review_case == "first_withheld" and index == 0))
            if incomplete:
                statuses["P1"] = "Unverified"
            found_required = sum(statuses[rid] == "Found" for rid in ("R1", "R2"))
            found_preferred = int(statuses["P1"] == "Found")
            candidates.append(CandidateResult(
                candidate_name=name, primary_score=None if incomplete else 50,
                matched_required=found_required, total_required=2,
                matched_preferred=found_preferred, total_preferred=1,
                evaluation_mode="failed" if incomplete else "llm_assessed",
                assessments=[RequirementAssessment(
                    requirement_id=rid, status=("matched" if status == "Found" else
                                                "uncertain" if status == "Unverified" else "not_matched"),
                    unified_status=status, reason="Reviewed " + rid,
                    assessment_state="unverified" if status == "Unverified" else "verified")
                    for rid, status in statuses.items()],
            ))
            results[str(index)] = {
                "Required matched": found_required, "Required total": 2,
                "Preferred matched": found_preferred, "Preferred total": 1,
                "Transferable": 0, "Unverified": int(incomplete), "Provisional": incomplete,
                "Notices": [], "Criteria": [{
                    "ID": rid, "Requirement": rid, "Priority": "Required" if rid == "R1" else "Preferred",
                    "Result": status, "Why": "Reviewed " + rid,
                    "Checkpoints": [], "Review recommended": False,
                    "Evidence level": "Source assessment", "JD source": rid,
                    "Kind": "skill"} for rid, status in statuses.items()]}
        report = RankingReport(job_description_source="JD", jd_validation_mode="llm_validated",
                               requirements=requirements, yake_candidates=[], candidates=candidates)
        st.session_state["cv_final_results"] = results
        _ranking(report)
        _candidate_evidence(report)

    app = AppTest.from_function(results_page)
    app.session_state["test_review_case"] = review_case
    app = app.run(timeout=20)
    assert not app.exception
    text = " ".join(item.value for item in app.markdown)
    assert ("Why no ranking is available" if review_case == "all_withheld"
            else "Why this candidate ranks first") in text
    assert "Why this CV received its ranking" in text
    assert "Candidate leaderboard" in text
    if review_case != "complete":
        content = " ".join(str(item.value) for item in app.get("info"))
        assert "Assessment incomplete" in content or "points withheld" in text


def test_step_labels_are_sequential_and_extraction_is_step_two():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "cv_ranker/ui/dashboard.py").read_text(encoding="utf-8")
    for number in range(1, 7):
        assert f"Step {number} · " in source
    form = source.split("def _run_form(", 1)[1].split("@st.fragment", 1)[0]
    assert form.index("Step 1 · Upload documents") < form.index("Step 2 · Extract JD requirements")
    assert form.index("Step 2 · Extract JD requirements") < form.index("Extract JD requirements for review")
    assert "**2 · Candidate resumes**" not in form
