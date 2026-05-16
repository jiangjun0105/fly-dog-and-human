"""Neuroscience Reference — renders docs/neuroscience/*.md in the wiki."""

import re
from pathlib import Path

import streamlit as st

_DOCS_DIR = Path(__file__).resolve().parents[3] / "docs" / "neuroscience"

_CSS = """\
<style>
[data-testid="stMainBlockContainer"] .stMarkdown h1 {
    border-bottom: 2px solid rgba(128, 128, 128, 0.2);
    padding-bottom: 0.3em;
    margin-bottom: 0.8em;
}
[data-testid="stMainBlockContainer"] .stMarkdown h2 {
    margin-top: 1.8em;
    margin-bottom: 0.4em;
    border-bottom: 1px solid rgba(128, 128, 128, 0.1);
    padding-bottom: 0.2em;
}
[data-testid="stMainBlockContainer"] .stMarkdown h3 {
    margin-top: 1.4em;
}
[data-testid="stMainBlockContainer"] .stMarkdown code:not(pre code) {
    background: rgba(128, 128, 128, 0.1);
    padding: 0.15em 0.4em;
    border-radius: 4px;
    font-size: 0.9em;
}
[data-testid="stMainBlockContainer"] .stMarkdown blockquote {
    border-left: 3px solid #3498db;
    padding-left: 1em;
    color: rgba(128, 128, 128, 0.8);
}
[data-testid="stMainBlockContainer"] .stMarkdown table {
    width: 100%;
}
[data-testid="stMainBlockContainer"] .stMarkdown table th {
    background: rgba(128, 128, 128, 0.08);
}
[data-testid="stMainBlockContainer"] .stMarkdown hr {
    border: none;
    border-top: 1px solid rgba(128, 128, 128, 0.15);
    margin: 2em 0;
}
</style>
"""

_TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


@st.cache_data(ttl=300)
def _load_docs() -> list[tuple[str, str, str]]:
    """Return sorted list of (title, filename, content) for each .md file."""
    docs = []
    for path in sorted(_DOCS_DIR.glob("*.md")):
        text = path.read_text()
        match = _TITLE_RE.search(text)
        title = match.group(1) if match else path.stem.replace("-", " ").title()
        docs.append((title, path.name, text))
    return docs


def render():
    st.markdown(_CSS, unsafe_allow_html=True)

    docs = _load_docs()
    if not docs:
        st.warning(f"No markdown files found in `{_DOCS_DIR}`")
        return

    titles = [title for title, _, _ in docs]
    choice = st.sidebar.radio(
        "Reference Docs",
        range(len(titles)),
        format_func=lambda i: titles[i],
    )

    _, filename, content = docs[choice]

    st.markdown(content)
    st.caption(f"Source: `docs/neuroscience/{filename}`")
