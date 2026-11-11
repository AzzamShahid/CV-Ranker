"""Reliance palette is configuration-only and leaves security/scoring intact."""

from pathlib import Path
import tomllib

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


def test_reliance_palette_does_not_enable_static_server_or_change_upload_limits():
    config = tomllib.loads((ROOT / '.streamlit/config.toml').read_text())
    assert config['theme']['base'] == 'light'
    assert config['theme']['light']['primaryColor'] == '#12613C'
    assert config['theme']['light']['backgroundColor'] == '#FAFCF9'
    assert config['theme']['light']['sidebar']['primaryColor'] == '#12613C'
    assert config['theme']['dark']['backgroundColor'] == '#111D17'
    assert config['theme']['dark']['textColor'] == '#EDF7EF'
    assert config['theme']['dark']['sidebar']['textColor'] == '#EDF7EF'
    assert config['server']['enableStaticServing'] is False
    assert config['server']['enableCORS'] is True
    assert config['server']['enableXsrfProtection'] is True
    assert config['server']['address'] == '127.0.0.1'


def test_supervisor_branding_is_presentation_only_and_safely_escaped():
    def page():
        from cv_ranker.ui.dashboard import _styles, _section_title
        _styles()
        _section_title('Evidence for <script>unsafe()</script>', 'Original source text')

    app = AppTest.from_function(page).run(timeout=15)
    assert not app.exception
    html = '\n'.join(str(item.value) for item in app.markdown)
    assert '--cv-ink:#183025' in html
    assert 'Evidence for &lt;script&gt;unsafe()&lt;/script&gt;' in html
    assert '<script>unsafe()</script>' not in html


def test_theme_does_not_change_jd_scoring_module():
    # The scoring module does not import presentation or theme configuration.
    from cv_ranker import weighted_scoring
    import inspect

    source = inspect.getsource(weighted_scoring)
    assert 'streamlit' not in source.casefold()
    assert '#176B46' not in source
