"""Native two-mode theme, robust provenance, and domain-neutral contracts."""

import re
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

from cv_ranker.unified import FINAL_ADJUDICATION_PROMPT, UNIFIED_PROMPT


ROOT = Path(__file__).resolve().parents[1]


def _rgb(hex_color):
    return [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]


def _luminance(hex_color):
    def linear(value):
        return value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4
    r, g, b = map(linear, _rgb(hex_color))
    return .2126 * r + .7152 * g + .0722 * b


def _contrast(a, b):
    x, y = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (x + .05) / (y + .05)


@pytest.mark.parametrize('mode', ['light', 'dark'])
def test_native_streamlit_theme_has_accessible_reading_contrast(mode):
    theme = tomllib.loads((ROOT / '.streamlit/config.toml').read_text())['theme'][mode]
    for region in (theme, theme['sidebar']):
        assert _contrast(region['textColor'], region['backgroundColor']) >= 7.0
        assert _contrast(region['primaryColor'], region['backgroundColor']) >= 3.0


@pytest.mark.parametrize('mode,ink,card', [
    ('light', '#183025', '#EFF5EF'),
    ('dark', '#EDF7EF', '#1B2D23'),
])
def test_custom_result_cards_follow_selected_streamlit_theme(monkeypatch, mode, ink, card):
    import cv_ranker.ui.dashboard as dashboard

    fragments = []
    monkeypatch.setattr(dashboard.st, 'context',
                        SimpleNamespace(theme=SimpleNamespace(type=mode)))
    monkeypatch.setattr(dashboard.st, 'markdown',
                        lambda html, **kwargs: fragments.append(html))
    dashboard._styles()
    assert len(fragments) == 1
    assert f'--cv-ink:{ink}' in fragments[0]
    assert f'--cv-card:{card}' in fragments[0]
    assert '--cv-bg:' in fragments[0]
    assert 'var(--text-color)' not in fragments[0]
    assert _contrast(ink, card) >= 7.0


@pytest.mark.parametrize('mode,bg,ink', [
    ('light', '#12613C', '#FFFFFF'),
    ('dark', '#6FDEAA', '#092017'),
])
def test_all_primary_buttons_get_explicit_high_contrast_palette(monkeypatch, mode, bg, ink):
    import cv_ranker.ui.dashboard as dashboard

    fragments = []
    monkeypatch.setattr(dashboard.st, 'context',
                        SimpleNamespace(theme=SimpleNamespace(type=mode)))
    monkeypatch.setattr(dashboard.st, 'markdown',
                        lambda html, **kwargs: fragments.append(html))
    dashboard._styles()
    css = fragments[0]
    assert f'--cv-button-bg:{bg}' in css
    assert f'--cv-button-ink:{ink}' in css
    assert 'color:var(--cv-button-ink) !important' in css
    assert '[data-testid="stDownloadButton"] button[kind="primary"]' in css
    assert '[data-testid="stButton"] button[kind] :is(p,span)' in css
    assert 'color:inherit !important' in css
    assert _contrast(bg, ink) >= 7.0


def test_prompts_describe_general_lifecycle_and_provenance_without_software_dictionary():
    for prompt in (UNIFIED_PROMPT, FINAL_ADJUDICATION_PROMPT):
        assert 'frozen' in prompt.casefold()
        assert 'source' in prompt.casefold()
        assert 'transferable' in prompt.casefold()
        assert 'job title' in prompt.casefold()
        assert 'deploying' in prompt.casefold()
        assert '15–45 words' in prompt
        # Prompts derive specialties from the JD rather than privileging a
        # fixed vendor, programming language or cloud provider.
        for vendor in ('aws', 'azure', 'docker', 'kubernetes', 'react', 'java'):
            assert not re.search(rf'\b{vendor}\b', prompt, flags=re.IGNORECASE)
