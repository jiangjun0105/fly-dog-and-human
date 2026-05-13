"""
Explore the male-cns:v0.9 connectome and generate an interactive HTML report.
Target SNN framework: Brian2 + GeNN (GPU-accelerated).

Usage:
    uv run python scripts/explore_connectome.py

Output:
    reports/connectome_exploration.html
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

from digital_drosophila.constants import NT_COLORS, NT_SIGN_MAP
from digital_drosophila.data import (
    connect,
    find_nt_column,
    load_connectivity,
    load_dataset_overview,
    load_vnc_neurons,
)
from wiki.metrics import compute_strategies

pio.templates.default = "plotly_dark"


# ---------------------------------------------------------------------------
# HTML report generation
# ---------------------------------------------------------------------------

def build_report(meta, all_rois, primary_rois, vnc_rois, vnc_df, nt_col, sample_df, adj, strategies):
    figures = []

    # --- 1. Dataset overview card ---
    figures.append(dataset_overview_html(meta, all_rois, primary_rois, vnc_rois, vnc_df))

    # --- 2. Superclass distribution ---
    if "superclass" in vnc_df.columns:
        sc = vnc_df["superclass"].value_counts()
        fig = go.Figure(go.Bar(
            x=sc.values,
            y=sc.index,
            orientation="h",
            marker_color=["#e74c3c" if "motor" in str(i) else "#3498db" if "intrinsic" in str(i) else "#2ecc71" if "sensory" in str(i) else "#95a5a6" for i in sc.index],
        ))
        fig.update_layout(title="VNC Neuron Superclass Distribution", xaxis_title="Count", yaxis_title="", height=max(300, len(sc) * 28), yaxis=dict(autorange="reversed"))
        figures.append(fig.to_html(full_html=False, include_plotlyjs=False))

    # --- 3. Cell type treemap ---
    if "type" in vnc_df.columns:
        type_counts = vnc_df["type"].value_counts().head(50)
        fig = go.Figure(go.Treemap(
            labels=type_counts.index.tolist(),
            parents=[""] * len(type_counts),
            values=type_counts.values.tolist(),
            textinfo="label+value",
        ))
        fig.update_layout(title=f"Top 50 Cell Types (of {vnc_df['type'].nunique()} unique)", height=500)
        figures.append(fig.to_html(full_html=False, include_plotlyjs=False))

    # --- 4. Neurotransmitter distribution ---
    if nt_col:
        nt_counts = vnc_df[nt_col].value_counts()
        colors = [NT_COLORS.get(nt, "#95a5a6") for nt in nt_counts.index]
        sign_labels = []
        for nt in nt_counts.index:
            s = NT_SIGN_MAP.get(str(nt).lower(), "?")
            sign_labels.append({1: "excitatory (+1)", -1: "inhibitory (-1)", None: "modulatory"}.get(s, "?"))
        fig = go.Figure(go.Bar(
            x=nt_counts.index.tolist(),
            y=nt_counts.values.tolist(),
            marker_color=colors,
            text=sign_labels,
            textposition="outside",
        ))
        missing = vnc_df[nt_col].isna().sum()
        fig.update_layout(
            title=f"Neurotransmitter Distribution ({nt_col}) — {missing} neurons missing ({100*missing/len(vnc_df):.1f}%)",
            xaxis_title="Neurotransmitter", yaxis_title="Count", height=400,
        )
        figures.append(fig.to_html(full_html=False, include_plotlyjs=False))

    # --- 5. Synapse count distributions ---
    fig = make_subplots(rows=1, cols=2, subplot_titles=["Output Synapses (pre)", "Input Synapses (post)"])
    for i, col in enumerate(["pre", "post"], 1):
        if col in vnc_df.columns:
            vals = vnc_df[col].clip(upper=vnc_df[col].quantile(0.99))
            fig.add_trace(go.Histogram(x=vals, nbinsx=60, name=col, marker_color="#3498db" if col == "pre" else "#e74c3c"), row=1, col=i)
            fig.add_vline(x=vnc_df[col].median(), line_dash="dash", line_color="black", annotation_text=f"median={vnc_df[col].median():.0f}", row=1, col=i)
    fig.update_layout(title="Synapse Count Distributions (clipped at 99th percentile)", height=350, showlegend=False)
    figures.append(fig.to_html(full_html=False, include_plotlyjs=False))

    # --- 6. Motor neuron detail ---
    if "superclass" in vnc_df.columns:
        motor = vnc_df[vnc_df["superclass"] == "vnc_motor"]
        if len(motor) > 0:
            figures.append(motor_neuron_detail_html(motor, nt_col))

    # --- 7. Adjacency matrix heatmap ---
    fig = go.Figure(go.Heatmap(
        z=np.log1p(adj),
        colorscale="Viridis",
        colorbar=dict(title="log(1+count)"),
    ))
    nonzero = np.count_nonzero(adj)
    total = adj.shape[0] ** 2
    fig.update_layout(
        title=f"Adjacency Matrix (top {adj.shape[0]} neurons) — {nonzero}/{total} edges ({100*nonzero/total:.2f}% fill)",
        xaxis_title="Post-synaptic", yaxis_title="Pre-synaptic", height=550, width=650,
    )
    figures.append(fig.to_html(full_html=False, include_plotlyjs=False))

    # --- 8. Weight distribution ---
    weights_nz = adj[adj > 0]
    fig = make_subplots(rows=1, cols=2, subplot_titles=["Raw Synapse Counts", "Log(1 + count)"])
    fig.add_trace(go.Histogram(x=weights_nz, nbinsx=60, marker_color="#3498db"), row=1, col=1)
    fig.add_trace(go.Histogram(x=np.log1p(weights_nz), nbinsx=60, marker_color="#e67e22"), row=1, col=2)
    fig.add_vline(x=np.median(weights_nz), line_dash="dash", line_color="red", annotation_text=f"median={np.median(weights_nz):.0f}", row=1, col=1)
    fig.update_layout(title=f"Synapse Weight Distribution — min={weights_nz.min():.0f}, max={weights_nz.max():.0f}, mean={weights_nz.mean():.1f}", height=350, showlegend=False)
    figures.append(fig.to_html(full_html=False, include_plotlyjs=False))

    # --- 9. Strategy comparison ---
    figures.append(strategy_comparison_html(strategies))

    return wrap_html(figures)


def _md_to_html(text):
    """Convert markdown links and lists in neuPrint descriptions to HTML."""
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank">\1</a>', text)
    lines = text.split("\n")
    html_lines = []
    in_list = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{stripped[2:]}</li>")
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            if stripped:
                html_lines.append(f"<p>{stripped}</p>")
    if in_list:
        html_lines.append("</ul>")
    return "\n".join(html_lines)


def dataset_overview_html(meta, all_rois, primary_rois, vnc_rois, vnc_df):
    motor_count = len(vnc_df[vnc_df.get("superclass", pd.Series()) == "vnc_motor"]) if "superclass" in vnc_df.columns else "?"
    desc_html = _md_to_html(meta.get("description", "N/A"))
    return f"""
    <div class="card">
        <h2>Dataset Overview: male-cns:v0.9</h2>
        <div class="description">{desc_html}</div>
        <div class="stat-grid">
            <div class="stat"><span class="stat-value">{meta.get('totalPreCount', 0):,}</span><span class="stat-label">Pre-synapses</span></div>
            <div class="stat"><span class="stat-value">{meta.get('totalPostCount', 0):,}</span><span class="stat-label">Post-synapses</span></div>
            <div class="stat"><span class="stat-value">{len(all_rois)}</span><span class="stat-label">ROIs ({len(primary_rois)} primary)</span></div>
            <div class="stat"><span class="stat-value">{len(vnc_df):,}</span><span class="stat-label">VNC Neurons</span></div>
            <div class="stat"><span class="stat-value">{motor_count}</span><span class="stat-label">Motor Neurons</span></div>
            <div class="stat"><span class="stat-value">{len(vnc_rois)}</span><span class="stat-label">VNC ROIs</span></div>
        </div>
        <details><summary>VNC-related ROIs ({len(vnc_rois)})</summary>
            <div class="roi-list">{" ".join(f'<span class="tag">{r}</span>' for r in vnc_rois)}</div>
        </details>
    </div>
    """


def motor_neuron_detail_html(motor_df, nt_col):
    parts = ['<div class="card"><h2>Motor Neurons (superclass=vnc_motor)</h2>']
    parts.append(f"<p><strong>{len(motor_df)}</strong> motor neurons, <strong>{motor_df['type'].nunique()}</strong> unique types</p>")

    if nt_col and nt_col in motor_df.columns:
        nt = motor_df[nt_col].value_counts()
        parts.append("<h3>Neurotransmitter breakdown</h3><ul>")
        for n, c in nt.items():
            sign = NT_SIGN_MAP.get(str(n).lower(), "?")
            parts.append(f"<li>{n}: {c} ({sign})</li>")
        parts.append("</ul>")

    if "subclass" in motor_df.columns:
        sc = motor_df["subclass"].value_counts()
        parts.append("<h3>Subclass (body part)</h3><ul>")
        for n, c in sc.items():
            parts.append(f"<li>{n}: {c}</li>")
        parts.append("</ul>")

    if "somaNeuromere" in motor_df.columns and motor_df["somaNeuromere"].notna().any():
        nm = motor_df["somaNeuromere"].value_counts()
        parts.append("<h3>Soma Neuromere (segment)</h3><ul>")
        for n, c in nm.items():
            parts.append(f"<li>{n}: {c}</li>")
        parts.append("</ul>")

    parts.append("</div>")
    return "\n".join(parts)


def strategy_comparison_html(strategies):
    n_strats = len(strategies)
    fig = make_subplots(
        rows=2, cols=n_strats,
        subplot_titles=[s["name"] for s in strategies] + [f"{s['name']} — vth" for s in strategies],
        vertical_spacing=0.12,
    )
    for i, s in enumerate(strategies, 1):
        w = s["weights"]
        nz = w[w != 0]
        fig.add_trace(go.Histogram(x=nz, nbinsx=50, name=f"Weights", marker_color="#3498db", showlegend=False), row=1, col=i)
        fig.add_vline(x=0, line_dash="dash", line_color="red", row=1, col=i)
        fig.add_trace(go.Histogram(x=s["vth"], nbinsx=30, name="vth", marker_color="#e74c3c", showlegend=False), row=2, col=i)

    fig.update_layout(
        title="Parameter Conversion Strategy Comparison",
        height=600,
    )
    for i in range(1, n_strats + 1):
        fig.update_xaxes(title_text="Weight value", row=1, col=i)
        fig.update_xaxes(title_text="Threshold (vth)", row=2, col=i)

    summary = "<div class='card'><h2>Strategy Comparison Summary</h2><table><tr><th>Strategy</th><th>Weight Range</th><th>vth Range</th><th>Scale Factor</th></tr>"
    for s in strategies:
        w = s["weights"]
        nz = w[w != 0]
        w_range = f"[{nz.min():.4f}, {nz.max():.4f}]" if len(nz) > 0 else "N/A"
        vth_range = f"[{s['vth'].min():.2f}, {s['vth'].max():.2f}]"
        scale = f"{s.get('scale', 'N/A')}"
        summary += f"<tr><td>{s['name']}</td><td>{w_range}</td><td>{vth_range}</td><td>{scale}</td></tr>"
    summary += """</table>
    <h3>Strategy Descriptions</h3>
    <dl>
        <dt><strong>A: Degree-Scaled Threshold</strong></dt>
        <dd>vth proportional to in-degree; raw synapse counts scaled globally. Preserves absolute connection strength.</dd>
        <dt><strong>B: Conductance-Normalized</strong></dt>
        <dd>Weights normalized per post-synaptic neuron (total input = 1.0); uniform vth. Simple but loses absolute strength.</dd>
        <dt><strong>C: Log-Scaled Weights</strong></dt>
        <dd>log(1 + count) compression; uniform vth. Handles heavy-tailed weight distribution naturally.</dd>
    </dl>
    </div>"""

    return summary + fig.to_html(full_html=False, include_plotlyjs=False)


def wrap_html(sections):
    body = "\n".join(sections)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Connectome Exploration: male-cns:v0.9 → Brian2 + GeNN</title>
    <script src="https://cdn.plot.ly/plotly-3.0.1.min.js"></script>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f1117; color: #e0e0e0; padding: 20px; max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #fff; margin: 20px 0; font-size: 1.8em; }}
        h2 {{ color: #fff; margin: 16px 0 8px; font-size: 1.3em; }}
        h3 {{ color: #ccc; margin: 12px 0 6px; font-size: 1.1em; }}
        .card {{ background: #1a1d27; border-radius: 8px; padding: 20px; margin: 16px 0; border: 1px solid #2a2d37; }}
        table {{ border-collapse: collapse; width: 100%; margin: 8px 0; }}
        td, th {{ padding: 6px 12px; border-bottom: 1px solid #2a2d37; text-align: left; }}
        th {{ color: #fff; background: #242730; }}
        details {{ margin: 8px 0; }}
        summary {{ cursor: pointer; color: #7aa2f7; }}
        pre {{ background: #242730; padding: 10px; border-radius: 4px; overflow-x: auto; font-size: 0.85em; color: #a0a0a0; }}
        dl {{ margin: 8px 0; }}
        dt {{ margin-top: 8px; }}
        dd {{ margin-left: 16px; color: #a0a0a0; }}
        ul {{ margin-left: 20px; }}
        li {{ margin: 2px 0; }}
        .stat-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin: 16px 0; }}
        .stat {{ background: #242730; border-radius: 6px; padding: 14px; text-align: center; }}
        .stat-value {{ display: block; font-size: 1.6em; font-weight: 700; color: #7aa2f7; }}
        .stat-label {{ display: block; font-size: 0.8em; color: #888; margin-top: 4px; }}
        .description {{ margin: 12px 0; line-height: 1.6; color: #b0b0b0; }}
        .description a {{ color: #7aa2f7; text-decoration: none; }}
        .description a:hover {{ text-decoration: underline; }}
        .roi-list {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }}
        .tag {{ background: #242730; border: 1px solid #3a3d47; border-radius: 4px; padding: 2px 8px; font-size: 0.82em; color: #a0a0a0; }}
        a {{ color: #7aa2f7; }}
        .js-plotly-plot .plotly {{ background: transparent !important; }}
    </style>
</head>
<body>
    <h1>Connectome Exploration: male-cns:v0.9 → Brian2 + GeNN SNN</h1>
    {body}
    <div class="card" style="margin-top: 32px; color: #666; font-size: 0.85em;">
        Generated by scripts/explore_connectome.py
    </div>
</body>
</html>"""


def main():
    print("Connecting to neuPrint...")
    connect()

    print("Fetching dataset overview...")
    meta, all_rois, primary_rois, vnc_rois = load_dataset_overview()

    print("Querying VNC neurons...")
    vnc_df, _ = load_vnc_neurons()
    nt_col = find_nt_column(vnc_df)
    print(f"  {len(vnc_df)} VNC neurons, NT column: {nt_col}")

    n = 100
    print(f"Fetching sample connectivity (top {n} neurons)...")
    sample_df = vnc_df.nlargest(n, "post").reset_index(drop=True)
    sample_ids = tuple(sample_df["bodyId"].tolist())
    adj = load_connectivity(sample_ids, n)

    print("Computing conversion strategies...")
    strategies = compute_strategies(adj, sample_df, nt_col)

    print("Building HTML report...")
    html = build_report(meta, all_rois, primary_rois, vnc_rois, vnc_df, nt_col, sample_df, adj, strategies)

    out_path = Path("reports/connectome_exploration.html")
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(html)
    print(f"Report written to {out_path}")


if __name__ == "__main__":
    main()
