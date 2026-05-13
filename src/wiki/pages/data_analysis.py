"""Data Analysis page — connectome overview, distributions, and connectivity."""

import altair as alt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from digital_drosophila.constants import NT_COLORS
from wiki.metrics import load_connectivity_metrics, load_metrics
from wiki.theme import ADJ_COLORSCALE, HEATMAP_LAYOUT, SUPERCLASS_COLORS


def render():
    st.title("Data Analysis: male-cns:v0.9")

    m = load_metrics()

    _render_dataset_overview(m["dataset_stats"])
    _render_superclass(m["superclass"])
    _render_cell_types(m["cell_types"])
    _render_neurotransmitters(m["neurotransmitters"])
    _render_synapse_distributions(m["synapse_distributions"])
    _render_motor_neurons(m["motor_neurons"])
    _render_connectivity(m["connectivity"])


def _render_dataset_overview(stats: dict):
    st.header("Dataset Overview")

    if stats.get("description"):
        st.caption(stats["description"])

    items = [
        ("Pre-synapses", f"{stats['total_pre_count']:,}"),
        ("Post-synapses", f"{stats['total_post_count']:,}"),
        (f"ROIs ({stats['primary_roi_count']} primary)", f"{stats['roi_count']}"),
        ("VNC Neurons", f"{stats['vnc_neuron_count']:,}"),
        ("Motor Neurons", f"{stats['motor_neuron_count']:,}"),
        ("VNC ROIs", f"{stats['vnc_roi_count']}"),
    ]
    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        with col:
            with st.container(border=True):
                st.metric(label, value)

    with st.expander(f"VNC-related ROIs ({stats['vnc_roi_count']})"):
        st.write(", ".join(stats["vnc_rois"]))


def _render_superclass(sc_df: pd.DataFrame):
    if sc_df.empty:
        return

    st.header("VNC Neuron Superclass Distribution")
    chart = (
        alt.Chart(sc_df)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("count:Q", title="Count"),
            y=alt.Y("superclass:N", sort="-x", title=None),
            color=alt.Color(
                "category:N",
                scale=alt.Scale(**SUPERCLASS_COLORS),
                legend=alt.Legend(title="Category", orient="bottom"),
            ),
            tooltip=["superclass", "count", "category"],
        )
        .properties(height=max(300, len(sc_df) * 28))
    )
    st.altair_chart(chart, use_container_width=True)


def _render_cell_types(cell_types: tuple[pd.DataFrame, int]):
    type_counts_df, unique_count = cell_types
    if type_counts_df.empty:
        return

    st.header("Top Cell Types")
    top_n = st.slider("Number of cell types to show", 10, 100, 50)
    sliced = type_counts_df.head(top_n)

    fig = go.Figure(go.Treemap(
        labels=sliced["type"].tolist(),
        parents=[""] * len(sliced),
        values=sliced["count"].tolist(),
        textinfo="label+value",
    ))
    fig.update_layout(
        title=f"Top {top_n} Cell Types (of {unique_count} unique)",
        height=500,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_neurotransmitters(nt_data: dict):
    nt_col = nt_data.get("nt_col")
    if not nt_col:
        return

    st.header("Neurotransmitter Distribution")
    st.caption(
        f"Column: {nt_col} — {nt_data['missing_count']} neurons missing ({nt_data['missing_pct']:.1f}%)"
    )

    nt_counts = nt_data["nt_counts"]
    nt_domain = nt_counts["neurotransmitter"].tolist()
    nt_range = [NT_COLORS.get(nt, "#95a5a6") for nt in nt_domain]

    bars = (
        alt.Chart(nt_counts)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("neurotransmitter:N", sort="-y", title="Neurotransmitter", axis=alt.Axis(labelAngle=-30)),
            y=alt.Y("count:Q", title="Count"),
            color=alt.Color(
                "neurotransmitter:N",
                scale=alt.Scale(domain=nt_domain, range=nt_range),
                legend=None,
            ),
            tooltip=["neurotransmitter", "count", "sign"],
        )
    )
    text = bars.mark_text(dy=-10, fontSize=11).encode(text="sign:N")
    st.altair_chart((bars + text).properties(height=400), use_container_width=True)


def _render_synapse_distributions(syn: dict):
    st.header("Synapse Count Distributions")
    configs = [
        ("pre", "#3498db", "Output Synapses (pre)"),
        ("post", "#e74c3c", "Input Synapses (post)"),
    ]
    syn_cols = st.columns(2)
    for col_widget, (col_name, color, label) in zip(syn_cols, configs):
        if col_name not in syn:
            continue
        data = syn[col_name]
        with col_widget:
            hist_df = pd.DataFrame({col_name: data["values_clipped"]})
            median_val = data["median"]

            base = alt.Chart(hist_df).mark_bar(cornerRadiusEnd=3, color=color).encode(
                x=alt.X(f"{col_name}:Q", bin=alt.Bin(maxbins=60), title=label),
                y=alt.Y("count()", title="Count"),
                tooltip=[alt.Tooltip(f"{col_name}:Q", bin=alt.Bin(maxbins=60), title=label), "count()"],
            )
            rule = (
                alt.Chart(pd.DataFrame({"median": [median_val]}))
                .mark_rule(strokeDash=[6, 3], color="#ffc107", strokeWidth=2)
                .encode(x="median:Q")
            )
            text = (
                alt.Chart(pd.DataFrame({"median": [median_val], "label": [f"median = {median_val:.0f}"]}))
                .mark_text(align="left", dx=5, dy=-10, fontSize=12, color="#ffc107")
                .encode(x="median:Q", text="label:N")
            )
            st.altair_chart((base + rule + text).properties(height=300), use_container_width=True)


def _render_motor_neurons(motor: dict):
    if motor.get("count", 0) == 0:
        return

    st.header("Motor Neurons")
    mcol1, mcol2 = st.columns(2)
    with mcol1:
        with st.container(border=True):
            st.metric("Motor Neurons", f"{motor['count']:,}")
    with mcol2:
        with st.container(border=True):
            st.metric("Unique Types", f"{motor['unique_types']:,}")

    detail_cols = st.columns(3)
    if "nt_breakdown" in motor:
        with detail_cols[0]:
            with st.container(border=True):
                st.subheader("Neurotransmitter")
                st.dataframe(motor["nt_breakdown"], hide_index=True, use_container_width=True)
    if "subclass_breakdown" in motor:
        with detail_cols[1]:
            with st.container(border=True):
                st.subheader("Subclass (body part)")
                st.dataframe(motor["subclass_breakdown"], hide_index=True, use_container_width=True)
    if "neuromere_breakdown" in motor:
        with detail_cols[2]:
            with st.container(border=True):
                st.subheader("Soma Neuromere")
                st.dataframe(motor["neuromere_breakdown"], hide_index=True, use_container_width=True)


def _render_connectivity(conn: dict):
    st.header("Connectivity Analysis")

    sample_size = st.slider("Sample size (top neurons by input synapses)", 50, 200, 100, step=10)
    if sample_size != 100:
        conn = load_connectivity_metrics(sample_size)

    adj = conn["adj"]
    cluster_order = conn["cluster_order"]

    st.subheader("Adjacency Matrix")
    st.caption(f"{conn['nonzero']:,}/{conn['total']:,} edges ({conn['fill_pct']:.2f}% fill)")

    adj_clustered = adj[np.ix_(cluster_order, cluster_order)]
    hm_left, hm_right = st.columns(2)
    with hm_left:
        st.markdown("**Raw** (by input count)")
        fig = go.Figure(go.Heatmap(
            z=np.log1p(adj),
            colorscale=ADJ_COLORSCALE,
            colorbar=dict(title="log(1+w)", len=0.6),
            hovertemplate="pre: %{y}<br>post: %{x}<br>log(1+w): %{z:.2f}<extra></extra>",
        ))
        fig.update_layout(**HEATMAP_LAYOUT)
        st.plotly_chart(fig, use_container_width=True)
    with hm_right:
        st.markdown("**Clustered** (Ward linkage)")
        fig = go.Figure(go.Heatmap(
            z=np.log1p(adj_clustered),
            colorscale=ADJ_COLORSCALE,
            colorbar=dict(title="log(1+w)", len=0.6),
            hovertemplate="pre: %{y}<br>post: %{x}<br>log(1+w): %{z:.2f}<extra></extra>",
        ))
        fig.update_layout(**HEATMAP_LAYOUT)
        st.plotly_chart(fig, use_container_width=True)

    weights_nz = conn["weights_nz"]
    st.subheader("Synapse Weight Distribution")

    wdist_cols = st.columns(3)
    with wdist_cols[0]:
        with st.container(border=True):
            st.metric("Min", f"{conn['weight_min']:.0f}")
    with wdist_cols[1]:
        with st.container(border=True):
            st.metric("Median", f"{conn['weight_median']:.0f}")
    with wdist_cols[2]:
        with st.container(border=True):
            st.metric("Max", f"{conn['weight_max']:.0f}")

    wdist_chart_cols = st.columns(2)
    with wdist_chart_cols[0]:
        raw_df = pd.DataFrame({"weight": weights_nz})
        raw_chart = (
            alt.Chart(raw_df)
            .mark_bar(cornerRadiusEnd=3, color="#3498db")
            .encode(
                x=alt.X("weight:Q", bin=alt.Bin(maxbins=60), title="Raw Synapse Count"),
                y=alt.Y("count()", title="Count"),
                tooltip=[alt.Tooltip("weight:Q", bin=alt.Bin(maxbins=60)), "count()"],
            )
            .properties(height=300, title="Raw Synapse Counts")
        )
        raw_rule = (
            alt.Chart(pd.DataFrame({"m": [conn["weight_median"]]}))
            .mark_rule(strokeDash=[6, 3], color="#e74c3c", strokeWidth=2)
            .encode(x="m:Q")
        )
        st.altair_chart(raw_chart + raw_rule, use_container_width=True)
    with wdist_chart_cols[1]:
        log_df = pd.DataFrame({"log_weight": np.log1p(weights_nz)})
        log_chart = (
            alt.Chart(log_df)
            .mark_bar(cornerRadiusEnd=3, color="#e67e22")
            .encode(
                x=alt.X("log_weight:Q", bin=alt.Bin(maxbins=60), title="log(1 + count)"),
                y=alt.Y("count()", title="Count"),
                tooltip=[alt.Tooltip("log_weight:Q", bin=alt.Bin(maxbins=60)), "count()"],
            )
            .properties(height=300, title="Log-Transformed")
        )
        st.altair_chart(log_chart, use_container_width=True)
