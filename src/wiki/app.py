"""
Digital Drosophila — Connectome Explorer (UI)

Sidebar-routed multi-page app. Each page module exposes a `render()` function.

Usage:
    uv run streamlit run run_app.py
"""

import streamlit as st

from wiki.pages import data_analysis, strategies
from wiki.theme import setup_plotly_theme

PAGES = [
    st.Page(data_analysis.render, title="Data Analysis", icon=":material/analytics:", url_path="data-analysis"),
    st.Page(strategies.render, title="Parameter Strategies", icon=":material/tune:", url_path="strategies"),
]


def main():
    st.set_page_config(
        page_title="Digital Drosophila — Connectome Explorer",
        page_icon="\U0001fab0",
        layout="wide",
    )
    setup_plotly_theme()

    nav = st.navigation(PAGES)
    nav.run()
