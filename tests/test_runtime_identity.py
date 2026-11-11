from cv_ranker.build_info import ASSESSMENT_PROTOCOL, ASSESSMENT_PROTOCOL_VERSION, BUILD_ID
from cv_ranker.runtime_check import assert_runtime_current
from cv_ranker.schemas import RankingReport


def test_runtime_protocol_is_segment_ids():
    info = assert_runtime_current()
    assert info["build_id"] == BUILD_ID
    assert info["assessment_protocol"] == ASSESSMENT_PROTOCOL == "segment_ids_semantic_llm"
    assert info["assessment_protocol_version"] == str(ASSESSMENT_PROTOCOL_VERSION) == "41"


def test_report_serializes_build_identity():
    report = RankingReport(
        job_description_source="jd",
        jd_validation_mode="test",
        yake_candidates=[],
        requirements=[],
        candidates=[],
    )
    dumped = report.model_dump()
    assert dumped["build_id"] == BUILD_ID
