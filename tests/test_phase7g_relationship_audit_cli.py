import pytest
from scripts.phase7g_relationship_audit import audit_reports


def test_audit_realistic_exact_technology_is_flagged_without_changing_ranking():
    retrieval = {"schema_version":2, "scoring_unchanged":True,
        "requirements":[{"requirement_id":"R1", "name":"Git"}],
        "capability_search_plan":{"capabilities":[{"capability_id":"R1-C01", "parent_requirement_id":"R1", "description":"Git"}]},
        "candidates":[{"candidate_id":"abc", "candidate_name":"cv.txt", "direct_primary_score":75.0,
            "ranking_position":1, "hits_by_requirement":{"R1":[{"segment_id":"S1", "section":"experience",
                "original_text":"Used Git for version control."}]}}]}
    transfer = {"mode":"qwen_transferability_shadow_not_scoring", "scoring_unchanged":True,
        "candidates":[{"candidate_id":"abc", "candidate_name":"cv.txt", "original_primary_score":75.0,
            "original_rank":1, "status":"completed_provisional", "assessments":[{
                "requirement_id":"R1", "capability_id":"R1-C01", "relationship":"transferable",
                "citation_audit":"source_validated", "citations":[{"segment_id":"S1", "exact_quote":"Used Git for version control."}]
            }]}]}
    output = audit_reports(transfer, retrieval)
    assert output["flag_count"] == 1
    assert output["flag_types"] == {"possible_direct_mislabeled_transferable": 1}
    assert output["candidates"][0]["original_rank"] == 1
    transfer["candidates"][0]["assessments"][0]["citations"][0]["exact_quote"] = "I invented this"
    with pytest.raises(ValueError, match="Quotation"):
        audit_reports(transfer, retrieval)
