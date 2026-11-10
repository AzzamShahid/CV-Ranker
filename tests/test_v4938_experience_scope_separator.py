"""Direct professional tenure can include punctuation in its work-scope terms."""

from pathlib import Path

import pytest

from cv_ranker.documents import extract_text
from cv_ranker.experience_validation import apply_experience_checks, check_experience
from cv_ranker.pipeline import reconcile_final_assessments
from cv_ranker.requirement_typing import classify_requirement
from cv_ranker.schemas import RequirementAssessment, RequirementConstraint, ValidatedRequirement
from cv_ranker.segments import segment_resume


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _requirement(jd: str, minimum: int = 3, *, complex_scope: bool = False):
    return ValidatedRequirement(
        requirement_id="R001", name=jd, priority="required", jd_evidence=jd,
        constraint=RequirementConstraint(
            kind="experience", minimum_years=minimum,
            operator="complex" if complex_scope else "single",
            requires_review=complex_scope,
        ),
    )


def test_bilal_pdf_explicit_ai_ml_delivery_is_quantified_experience():
    """The specific observed regression, using real PDF source segment boundaries."""
    pdf = PROJECT_ROOT / "sample_data/applied_ai_documents/pdf/02_bilal_direct_fullstack.pdf"
    text = extract_text(pdf)
    segments = segment_resume(text)
    jd = ("Minimum 3 years of relevant professional experience developing or "
          "delivering AI, machine-learning, deep-learning, or LLM-powered software.")
    supervisor_jd = (PROJECT_ROOT / "sample_data/applied_ai_supervisor_jd.txt").read_text()
    req = _requirement(jd, complex_scope=True)
    classified = classify_requirement(req, supervisor_jd)
    assert classified.kind == "experience"
    assert classified.operator == "complex" and classified.subject is None
    req = req.model_copy(update={"constraint": classified})

    verdict = check_experience(req, text, segments)
    assert verdict.outcome == "sufficient", verdict.model_dump()
    assert any(abs(c.lower_years - (4 + 5 / 12)) < 0.001
               and "professional AI/ML delivery" in c.quote for c in verdict.claims)

    # A false initial LLM negative must not override the source-ledger proof.
    initial = RequirementAssessment(
        requirement_id="R001", status="not_matched", unified_status="Not Found",
        reason="The minimum was not established.",
    )
    checked, _, changed = apply_experience_checks(
        requirements=[req], assessments=[initial], resume_text=text)
    final = reconcile_final_assessments(requirements=[req], assessments=checked)
    assert changed
    assert final[0].status == "matched"
    assert final[0].unified_status == "Found"
    assert final[0].evidence_ids
    assert any("professional AI/ML delivery" in citation.text
               for citation in final[0].evidence_segments)


@pytest.mark.parametrize("profession, wording", [
    ("quality", "3 years 6 months of professional quality/operations delivery"),
    ("manufacturing", "3 years 8 months of professional manufacturing & quality management"),
    ("finance", "4 years of professional finance-compliance analysis"),
])
def test_professional_scope_with_punctuation_is_domain_neutral(profession, wording):
    jd = f"At least 3 years of relevant professional experience in {profession}."
    text = f"SUMMARY\nI have {wording}.\n"
    verdict = check_experience(_requirement(jd), text, segment_resume(text))
    assert verdict.outcome == "sufficient", verdict.model_dump()


@pytest.mark.parametrize("text", [
    "Managed an archive covering four years of manufacturing/quality records.",
    "Worked with four years of finance-compliance records for analysis.",
    "Designed a model on four years of retail/sales data and reported accuracy.",
])
def test_slashed_data_coverage_is_not_professional_tenure(text):
    jd = "Minimum 3 years of professional experience."
    verdict = check_experience(_requirement(jd), f"EXPERIENCE\n{text}\n",
                               segment_resume(f"EXPERIENCE\n{text}\n"))
    assert verdict.outcome != "sufficient", verdict.model_dump()

