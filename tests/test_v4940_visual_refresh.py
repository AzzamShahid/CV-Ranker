"""The supervisor visual refresh must keep source text safe and assessment state stable."""

from streamlit.testing.v1 import AppTest

from cv_ranker.build_info import (ASSESSMENT_PROTOCOL_VERSION, BUILD_ID,
                                  UI_RELEASE_VERSION)


def test_assessment_repair_has_a_new_protocol_identity():
    # The 4.9.40–4.9.42 styling revisions left the paid assessment identity
    # unchanged. This release changes how invalid grouped model rows are
    # reconciled, so old incomplete checkpoints must not mix with new results.
    assert UI_RELEASE_VERSION == "4.9.55"
    assert BUILD_ID == "phase7g-v4-9-55-calibrated-uncertainty-local-edit-2026-11-11"
    assert ASSESSMENT_PROTOCOL_VERSION == 41


def test_supervisor_cards_render_consistently_in_streamlit():
    def page():
        from cv_ranker.ui.dashboard import _insight_card, _section_title, _styles

        _styles()
        _section_title("Why this CV received its ranking", "A summary of verified evidence.")
        _insight_card("Candidate A", "Has four years of relevant delivery experience.",
                      label="Assessment summary", tag="Rank #1 · 89.50%")
        _insight_card("Why this decision", "Verified source citation supports the JD.",
                      label="Individual criterion explanation", tag="Found", tone="blue")

    app = AppTest.from_function(page).run(timeout=15)
    assert not app.exception
    markup = "\n".join(str(item.value) for item in app.markdown)
    assert "cv-hero" in markup  # global design language registered
    assert "cv-section" in markup
    assert "cv-insight" in markup
    assert "Why this CV received its ranking" in markup
    assert "Why this decision" in markup
    assert "Rank #1 · 89.50%" in markup


def test_untrusted_candidate_and_jd_copy_are_escaped(monkeypatch):
    from cv_ranker.ui import dashboard

    output = []
    monkeypatch.setattr(dashboard.st, "markdown", lambda value, **kwargs: output.append(value))
    dashboard._insight_card('<script>alert("x")</script>', "<img src=x>",
                            label="<h1>untrusted</h1>", tag="<b>Found</b>", tone="blue")
    dashboard._section_title("<script>heading</script>", "<i>subtitle</i>")
    dashboard._evidence_tile({"requirement": "<b>JD</b>", "why": "<svg/onload=bad>",
                              "earned_points": 3.5})
    markup = "\n".join(output)
    assert "&lt;script&gt;" in markup
    assert "&lt;img src=x&gt;" in markup
    assert "&lt;b&gt;JD&lt;/b&gt;" in markup
    assert "&lt;svg/onload=bad&gt;" in markup
    assert '<script>alert("x")</script>' not in markup
    assert "cv-mini-item" in markup
