"""Parameter Conversion Strategies page — synapse-to-SNN parameter mapping."""

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from wiki.metrics import load_connectivity_metrics, load_metrics


def render():
    st.title("Parameter Conversion Strategies")
    st.caption("Mapping biological synapse counts to Brian2/GeNN spiking neuron parameters")

    conn = load_metrics()["connectivity"]

    sample_size = st.slider("Sample size (top neurons by input synapses)", 50, 200, 100, step=10)
    if sample_size != 100:
        conn = load_connectivity_metrics(sample_size)

    strategies = conn["strategies"]

    _render_summary_table(strategies)
    _render_strategy_details(strategies)


def _render_summary_table(strategies: list[dict]):
    st.header("Strategy Comparison")

    summary_rows = []
    for s in strategies:
        w = s["weights"]
        nz = w[w != 0]
        summary_rows.append({
            "Strategy": s["name"],
            "Weight Range": f"[{nz.min():.4f}, {nz.max():.4f}]" if len(nz) > 0 else "N/A",
            "vth Range": f"[{s['vth'].min():.2f}, {s['vth'].max():.2f}]",
            "Scale Factor": f"{float(s['scale']):.6f}" if s["scale"] is not None else "N/A",
        })
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)


def _render_strategy_details(strategies: list[dict]):
    st.header("Weight & Threshold Distributions")

    strat_cols = st.columns(3)
    for strat_col, s in zip(strat_cols, strategies):
        with strat_col:
            with st.container(border=True):
                st.markdown(f"**{s['name']}**")
                w = s["weights"]
                nz = w[w != 0]

                w_df = pd.DataFrame({"weight": nz})
                w_chart = (
                    alt.Chart(w_df)
                    .mark_bar(cornerRadiusEnd=3, color="#3498db")
                    .encode(
                        x=alt.X("weight:Q", bin=alt.Bin(maxbins=50), title="Weight value"),
                        y=alt.Y("count()", title="Count"),
                    )
                    .properties(height=200)
                )
                zero_rule = (
                    alt.Chart(pd.DataFrame({"x": [0]}))
                    .mark_rule(strokeDash=[6, 3], color="#e74c3c", strokeWidth=2)
                    .encode(x="x:Q")
                )
                st.altair_chart(w_chart + zero_rule, use_container_width=True)

                vth_df = pd.DataFrame({"vth": s["vth"]})
                vth_chart = (
                    alt.Chart(vth_df)
                    .mark_bar(cornerRadiusEnd=3, color="#e74c3c")
                    .encode(
                        x=alt.X("vth:Q", bin=alt.Bin(maxbins=30), title="Threshold (vth)"),
                        y=alt.Y("count()", title="Count"),
                    )
                    .properties(height=200)
                )
                st.altair_chart(vth_chart, use_container_width=True)
