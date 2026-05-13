"""Plotly template and chart styling for the wiki."""

import plotly.graph_objects as go
import plotly.io as pio

COLORWAY = [
    "#3498db", "#e74c3c", "#2ecc71", "#f39c12",
    "#9b59b6", "#1abc9c", "#e67e22", "#95a5a6",
]

SUPERCLASS_COLORS = {
    "domain": ["Motor", "Intrinsic", "Sensory", "Other"],
    "range": ["#e74c3c", "#3498db", "#2ecc71", "#95a5a6"],
}

ADJ_COLORSCALE = [
    [0.0, "rgba(0,0,0,0)"],
    [0.01, "#0d1b2a"],
    [0.15, "#1b3a4b"],
    [0.35, "#1b4965"],
    [0.55, "#3e8098"],
    [0.75, "#62b6cb"],
    [1.0, "#bee9e8"],
]

HEATMAP_LAYOUT = dict(
    xaxis_title="Post-synaptic",
    yaxis_title="Pre-synaptic",
    height=550,
    yaxis=dict(autorange="reversed"),
)


def setup_plotly_theme():
    template = go.layout.Template(
        layout=go.Layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Source Sans Pro, sans-serif", size=13),
            xaxis=dict(gridcolor="rgba(128,128,128,0.15)", zeroline=False),
            yaxis=dict(gridcolor="rgba(128,128,128,0.15)", zeroline=False),
            colorway=COLORWAY,
            margin=dict(l=40, r=20, t=40, b=40),
        )
    )
    pio.templates["connectome"] = template
    pio.templates.default = "connectome"
