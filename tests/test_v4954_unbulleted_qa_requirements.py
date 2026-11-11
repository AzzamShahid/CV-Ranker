"""A JD's explicit unbulleted requirements may not disappear during extraction.

These tests run offline, without external LLM or embedding dependencies.
"""

from cv_ranker.config import Settings
from cv_ranker.fallback import structural_hints
from cv_ranker.jd import validate_jd_requirements
from cv_ranker.schemas import JDRequirement, JDValidationResponse


QA_JD = """QA Automation Engineer
Quality Engineering · Orchardline Payments · Remote, Pakistan
The team and the work
Our merchants use a browser dashboard and a payments API. Refunds, partial captures and delayed callbacks
make the failure cases more interesting than the happy path. You will join two quality engineers supporting three
delivery teams. The developers own unit tests and the quality team owns cross-service regression coverage.
Your first quarter
The first release you will support changes how duplicate refunds are surfaced. Work with support to reconstruct a
real sequence, reproduce it in a sandbox and agree on what the customer should see. Before the quarter ends, the
release owner should be able to distinguish a product regression from an unstable test using the artifacts from a
single run.
How you will work
Your work includes exploratory sessions with product managers and reviewing failure evidence after releases. We
value a small, dependable suite more than an impressive count of cases. Explain what a test protects, what data it
relies on and who can investigate when it fails.
Delivery constraints
Our release review follows money movement from the merchant's first request to the final ledger entry. A green
browser test by itself cannot tell us whether a duplicate callback posted twice. For the first assignment, the sandbox
team will provide masked event sequences and allow you to inject delays. We expect a concise statement of the
uncovered risks and a release recommendation with evidence. On high-volume days, the support team also needs
a reliable way to reproduce the customer's account state.
Required qualifications and capabilities
At least 3 years of full-time professional experience in professional software testing.
Completed bachelor's degree in Computer Science or Software Engineering.
Automate browser regression coverage with Playwright.
Write automated HTTP API tests for error paths.
Integrate automated regression tests into a CI pipeline.
Diagnose and repair flaky tests.
Design reproducible test data for independent test runs.
Preferred experience
Measure application load behavior using k6.
Test accessibility using a screen reader.
Write actionable defect reports with isolation steps.
"""


EXPECTED_REQUIRED = [
    "At least 3 years of full-time professional experience in professional software testing.",
    "Completed bachelor's degree in Computer Science or Software Engineering.",
    "Automate browser regression coverage with Playwright.",
    "Write automated HTTP API tests for error paths.",
    "Integrate automated regression tests into a CI pipeline.",
    "Diagnose and repair flaky tests.",
    "Design reproducible test data for independent test runs.",
]
EXPECTED_PREFERRED = [
    "Measure application load behavior using k6.",
    "Test accessibility using a screen reader.",
    "Write actionable defect reports with isolation steps.",
]


def test_exact_qa_jd_source_produces_all_ten_with_correct_priorities():
    rows = structural_hints(QA_JD)
    assert [(r.name, r.priority) for r in rows] == (
        [(name, "required") for name in EXPECTED_REQUIRED]
        + [(name, "preferred") for name in EXPECTED_PREFERRED]
    )


def test_partial_qa_llm_output_cannot_drop_ci_or_reproducible_test_data():
    class PartialLLM:
        calls = 0

        def invoke_structured(self, **kwargs):
            self.calls += 1
            # Reproduce the observed eight-result model response.
            names = [name for name in EXPECTED_REQUIRED + EXPECTED_PREFERRED
                     if "CI pipeline" not in name and "test data" not in name]
            return JDValidationResponse(requirements=[
                JDRequirement(
                    name=name,
                    evidence=name,
                    priority="required" if name in EXPECTED_REQUIRED else "preferred",
                ) for name in names
            ])

    model = PartialLLM()
    diagnostics = []
    requirements, mode, warnings = validate_jd_requirements(
        jd_text=QA_JD,
        candidates=[],
        settings=Settings(),
        llm=model,
        diagnostics=diagnostics,
    )
    assert [(r.name, r.priority) for r in requirements] == (
        [(name, "required") for name in EXPECTED_REQUIRED]
        + [(name, "preferred") for name in EXPECTED_PREFERRED]
    )
    assert mode == "fallback_structural_after_llm"
    assert model.calls == 1
    assert any("source completeness" in warning for warning in warnings)
    assert [row["name"] for row in diagnostics
            if row.get("status") == "restored_from_explicit_source"] == [
                "Integrate automated regression tests into a CI pipeline.",
                "Design reproducible test data for independent test runs.",
            ]


def test_unbulleted_section_with_blank_lines_stays_scoped_but_prose_does_not():
    jd = """How the company works
We build services that process many events.

Required qualifications and capabilities:

Automate browser coverage for regressions.

Design independent test datasets.

Preferred experience

Measure operational load with a test tool.

Benefits:
Competitive salary and flexible hours.
"""
    assert [(r.name, r.priority) for r in structural_hints(jd)] == [
        ("Automate browser coverage for regressions.", "required"),
        ("Design independent test datasets.", "required"),
        ("Measure operational load with a test tool.", "preferred"),
    ]
