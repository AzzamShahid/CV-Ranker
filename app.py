"""CV Ranker supervisor-ready Streamlit entry point.

Keep application presentation separate from the tested ranking engine.
Launch on Windows with ``run_ui.cmd``.
"""

import streamlit as st

st.set_page_config(
    page_title="TextileHR AI | Reliance Weaving Mills",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

from cv_ranker.ui.dashboard import render_app  # noqa: E402

render_app()
