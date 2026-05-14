"""Data Analysis page — connectome overview, distributions, and connectivity."""

import altair as alt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from digital_drosophila.constants import NT_COLORS
from wiki.metrics import load_connectivity_metrics, load_metrics_for_scope
from wiki.theme import ADJ_COLORSCALE, HEATMAP_LAYOUT, SUPERCLASS_COLORS

_SCOPE_LABELS = {
    "total": "Total Connectome",
    "vnc": "VNC",
    "brain": "Brain",
}


def render():
    st.title("Data Analysis: male-cns:v0.9")

    m_vnc = load_metrics_for_scope("vnc")
    stats = m_vnc["dataset_stats"]

    if stats.get("description"):
        st.caption(stats["description"])

    tab_total, tab_vnc, tab_brain = st.tabs(["Total", "VNC", "Brain"])

    with tab_total:
        _render_scope_tab(load_metrics_for_scope("total"), "total")
    with tab_vnc:
        _render_scope_tab(m_vnc, "vnc")
    with tab_brain:
        _render_scope_tab(load_metrics_for_scope("brain"), "brain")


def _render_scope_tab(m: dict, scope: str):
    label = _SCOPE_LABELS[scope]
    scope_stats = m["scope_stats"]

    st.header(f"{label} Overview")
    items = [
        ("Neurons", f"{scope_stats['neuron_count']:,}"),
        ("Pre-synapses", f"{scope_stats['pre_total']:,}"),
        ("Post-synapses", f"{scope_stats['post_total']:,}"),
    ]
    if scope_stats["motor_neuron_count"] > 0:
        items.append(("Motor Neurons", f"{scope_stats['motor_neuron_count']:,}"))

    cols = st.columns(len(items))
    for col, (col_label, value) in zip(cols, items):
        with col:
            with st.container(border=True):
                st.metric(col_label, value)

    _render_roi_distribution(m["roi_distribution"], scope)
    _render_superclass(m["superclass"], scope)
    _render_cell_types(m["cell_types"], scope)
    _render_neurotransmitters(m["neurotransmitters"])
    _render_synapse_distributions(m["synapse_distributions"])
    _render_motor_neurons(m["motor_neurons"])
    _render_connectivity(m["connectivity"], scope)


# ---------------------------------------------------------------------------
# ROI distribution
# ---------------------------------------------------------------------------

_ROI_EXACT = {
    # VNC regions
    "VNC": "VNC", "VNC-unspecified": "VNC", "ANm": "Abdomen",
    "LegNp(T1)(L)": "Legs", "LegNp(T1)(R)": "Legs",
    "LegNp(T2)(L)": "Legs", "LegNp(T2)(R)": "Legs",
    "LegNp(T3)(L)": "Legs", "LegNp(T3)(R)": "Legs",
    "NTct(UTct-T1)(L)": "Neck", "NTct(UTct-T1)(R)": "Neck",
    "WTct(UTct-T2)(L)": "Wings", "WTct(UTct-T2)(R)": "Wings",
    "HTct(UTct-T3)(L)": "Halteres", "HTct(UTct-T3)(R)": "Halteres",
    "mVAC(T1)(L)": "Association", "mVAC(T1)(R)": "Association",
    "mVAC(T2)(L)": "Association", "mVAC(T2)(R)": "Association",
    "mVAC(T3)(L)": "Association", "mVAC(T3)(R)": "Association",
    # Brain top-level
    "CentralBrain": "Central Brain", "CentralBrain-unspecified": "Central Brain",
    # Central complex
    "EB": "Central Complex", "FB": "Central Complex",
    "PB": "Central Complex", "NO": "Central Complex",
    "AB(L)": "Central Complex", "AB(R)": "Central Complex",
    # Olfactory
    "AL(L)": "Olfactory", "AL(R)": "Olfactory",
    "LH(L)": "Olfactory", "LH(R)": "Olfactory",
    # Mushroom body
    "CA(L)": "Mushroom Body", "CA(R)": "Mushroom Body",
    "PED(L)": "Mushroom Body", "PED(R)": "Mushroom Body",
    # Subesophageal
    "GNG": "Subesophageal",
    "SAD": "Subesophageal",
}

_ROI_PREFIX_MAP = [
    ("Optic", "Optic Lobe"),
    ("ME", "Optic Lobe"),
    ("LO", "Optic Lobe"),
    ("LA", "Optic Lobe"),
    ("AME", "Optic Lobe"),
    ("AVLP", "Visual Neuropil"),
    ("PVLP", "Visual Neuropil"),
    ("PLP", "Visual Neuropil"),
    ("AOTU", "Visual Neuropil"),
    ("WED", "Visual Neuropil"),
    ("GOR", "Visual Neuropil"),
    ("ICL", "Central Brain"),
    ("SMP", "Central Brain"),
    ("SLP", "Central Brain"),
    ("SIP", "Central Brain"),
    ("CRE", "Central Brain"),
    ("IB", "Central Brain"),
    ("ATL", "Central Brain"),
    ("LAL", "Central Brain"),
    ("BU", "Central Brain"),
    ("EPA", "Central Brain"),
    ("IPS", "Central Brain"),
    ("SCL", "Central Brain"),
    ("CAN", "Central Brain"),
    ("FLA", "Central Brain"),
    ("GA", "Central Brain"),
    ("ROB", "Central Brain"),
    ("RUB", "Central Brain"),
    ("PRW", "Central Brain"),
    ("a'L", "Mushroom Body"),
    ("aL", "Mushroom Body"),
    ("b'L", "Mushroom Body"),
    ("bL", "Mushroom Body"),
    ("gL", "Mushroom Body"),
    ("LegNp", "Legs"),
    ("mVAC", "Association"),
    ("SPS", "Subesophageal"),
    ("Ov", "Subesophageal"),
    ("AMMC", "Subesophageal"),
    ("VES", "Subesophageal"),
    ("IntTct", "Tract"),
    ("LTct", "Tract"),
    ("CV", "Tract"),
    ("CvN", "Nerve"),
    ("VProN", "Nerve"),
    ("ADMN", "Nerve"),
    ("PDMN", "Nerve"),
    ("DProN", "Nerve"),
    ("DMetaN", "Nerve"),
    ("MesoAN", "Nerve"),
    ("MesoLN", "Nerve"),
    ("MetaLN", "Nerve"),
    ("ProAN", "Nerve"),
    ("ProCN", "Nerve"),
    ("ProLN", "Nerve"),
    ("PrN", "Nerve"),
    ("AbN", "Nerve"),
]


def _classify_roi(name: str) -> str:
    if name in _ROI_EXACT:
        return _ROI_EXACT[name]
    for prefix, category in _ROI_PREFIX_MAP:
        if name.startswith(prefix):
            return category
    if "N" in name and any(c.isupper() for c in name[:3]):
        if name.endswith("N") or "Nerve" in name or name.startswith("Ab"):
            return "Nerve"
    return "Other"


_REGION_COLORS = {
    "domain": [
        "Optic Lobe", "Visual Neuropil", "Central Brain", "Central Complex",
        "Mushroom Body", "Olfactory", "Subesophageal",
        "VNC", "Legs", "Wings", "Neck", "Halteres", "Abdomen", "Association",
        "Tract", "Nerve", "Other",
    ],
    "range": [
        "#f1c40f", "#e67e22", "#3498db", "#8e44ad",
        "#e74c3c", "#2ecc71", "#1abc9c",
        "#7f8c8d", "#27ae60", "#2980b9", "#c0392b", "#9b59b6", "#d35400", "#16a085",
        "#95a5a6", "#7f8c8d", "#bdc3c7",
    ],
}

_VNC_ROI_CATEGORIES = {
    "VNC": ("Ventral Nerve Cord", "VNC", "Top-level region encompassing the entire ventral nerve cord"),
    "VNC-unspecified": ("VNC (unspecified)", "VNC", "Neurons in the VNC not assigned to a finer sub-region"),
    "ANm": ("Abdominal Neuromere (male)", "Abdomen", "Male-specific abdominal neuropil — genital/reproductive motor control"),
    "LegNp(T1)(L)": ("Leg Neuropil T1 Left", "Legs", "Front leg motor neuropil, left"),
    "LegNp(T1)(R)": ("Leg Neuropil T1 Right", "Legs", "Front leg motor neuropil, right"),
    "LegNp(T2)(L)": ("Leg Neuropil T2 Left", "Legs", "Middle leg motor neuropil, left"),
    "LegNp(T2)(R)": ("Leg Neuropil T2 Right", "Legs", "Middle leg motor neuropil, right"),
    "LegNp(T3)(L)": ("Leg Neuropil T3 Left", "Legs", "Hind leg motor neuropil, left"),
    "LegNp(T3)(R)": ("Leg Neuropil T3 Right", "Legs", "Hind leg motor neuropil, right"),
    "NTct(UTct-T1)(L)": ("Neck Tergal Tract T1 Left", "Neck", "Neck/prothoracic commissure tract, left"),
    "NTct(UTct-T1)(R)": ("Neck Tergal Tract T1 Right", "Neck", "Neck/prothoracic commissure tract, right"),
    "WTct(UTct-T2)(L)": ("Wing Tergal Tract T2 Left", "Wings", "Wing commissure tract, left"),
    "WTct(UTct-T2)(R)": ("Wing Tergal Tract T2 Right", "Wings", "Wing commissure tract, right"),
    "HTct(UTct-T3)(L)": ("Haltere Tergal Tract T3 Left", "Halteres", "Haltere (balance organ) commissure tract, left"),
    "HTct(UTct-T3)(R)": ("Haltere Tergal Tract T3 Right", "Halteres", "Haltere (balance organ) commissure tract, right"),
    "mVAC(T1)(L)": ("Medial VAC T1 Left", "Association", "Ventral association center in T1, left — interneuron integration"),
    "mVAC(T1)(R)": ("Medial VAC T1 Right", "Association", "Ventral association center in T1, right — interneuron integration"),
    "mVAC(T2)(L)": ("Medial VAC T2 Left", "Association", "Ventral association center in T2, left — interneuron integration"),
    "mVAC(T2)(R)": ("Medial VAC T2 Right", "Association", "Ventral association center in T2, right — interneuron integration"),
    "mVAC(T3)(L)": ("Medial VAC T3 Left", "Association", "Ventral association center in T3, left — interneuron integration"),
    "mVAC(T3)(R)": ("Medial VAC T3 Right", "Association", "Ventral association center in T3, right — interneuron integration"),
}

def _render_roi_distribution(roi_dist: pd.DataFrame, scope: str):
    if roi_dist.empty:
        return

    label = _SCOPE_LABELS[scope]
    st.header(f"{label} Regions")

    top_n = min(40, len(roi_dist))
    df = roi_dist.head(top_n).copy()
    df["region"] = df["roi"].map(_classify_roi)

    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("neuron_count:Q", title="Neuron Count"),
            y=alt.Y("roi:N", sort="-x", title=None),
            color=alt.Color(
                "region:N",
                scale=alt.Scale(**_REGION_COLORS),
                legend=alt.Legend(title="Region", orient="bottom"),
            ),
            tooltip=["roi", "neuron_count", "region"],
        )
        .properties(height=max(300, len(df) * 28))
    )
    st.altair_chart(chart, use_container_width=True)
    st.caption(
        f"Top {top_n} ROIs by neuron count. "
        "A neuron is counted in every ROI it has synapses in, so totals exceed the neuron count."
    )

    with st.expander("ROI Reference Table"):
        roi_table = _build_roi_reference_table(roi_dist.head(top_n), scope)
        st.dataframe(roi_table, hide_index=True, use_container_width=True)


_BRAIN_ROI_DESCRIPTIONS = {
    "Optic(R)": ("Optic Lobe Right", "Full right optic lobe — all visual neuropils"),
    "Optic(L)": ("Optic Lobe Left", "Full left optic lobe — all visual neuropils"),
    "Optic-unspecified(R)": ("Optic Lobe Right (unspecified)", "Optic lobe synapses not assigned to a specific neuropil layer"),
    "Optic-unspecified(L)": ("Optic Lobe Left (unspecified)", "Optic lobe synapses not assigned to a specific neuropil layer"),
    "CentralBrain": ("Central Brain", "All central brain neuropils combined"),
    "CentralBrain-unspecified": ("Central Brain (unspecified)", "Central brain synapses not assigned to a specific neuropil"),
    "ME(R)": ("Medulla Right", "Main visual processing neuropil — columnar retinotopic map"),
    "ME(L)": ("Medulla Left", "Main visual processing neuropil — columnar retinotopic map"),
    "LO(R)": ("Lobula Right", "Second-order visual neuropil — motion and feature detection"),
    "LO(L)": ("Lobula Left", "Second-order visual neuropil — motion and feature detection"),
    "LOP(R)": ("Lobula Plate Right", "Direction-selective motion processing"),
    "LOP(L)": ("Lobula Plate Left", "Direction-selective motion processing"),
    "LA(R)": ("Lamina Right", "First visual neuropil — photoreceptor terminals"),
    "LA(L)": ("Lamina Left", "First visual neuropil — photoreceptor terminals"),
    "AME(R)": ("Accessory Medulla Right", "Circadian clock neuropil"),
    "AME(L)": ("Accessory Medulla Left", "Circadian clock neuropil"),
    "AVLP(R)": ("Anterior Ventrolateral Protocerebrum Right", "Higher visual processing — object recognition"),
    "AVLP(L)": ("Anterior Ventrolateral Protocerebrum Left", "Higher visual processing — object recognition"),
    "PVLP(R)": ("Posterior Ventrolateral Protocerebrum Right", "Higher visual processing — looming detection"),
    "PVLP(L)": ("Posterior Ventrolateral Protocerebrum Left", "Higher visual processing — looming detection"),
    "PLP(R)": ("Posterolateral Protocerebrum Right", "Visual integration area"),
    "PLP(L)": ("Posterolateral Protocerebrum Left", "Visual integration area"),
    "WED(R)": ("Wedge Right", "Visual-motor integration"),
    "WED(L)": ("Wedge Left", "Visual-motor integration"),
    "AL(R)": ("Antennal Lobe Right", "Olfactory processing — glomerular map of odors"),
    "AL(L)": ("Antennal Lobe Left", "Olfactory processing — glomerular map of odors"),
    "LH(R)": ("Lateral Horn Right", "Innate olfactory responses"),
    "LH(L)": ("Lateral Horn Left", "Innate olfactory responses"),
    "CA(R)": ("Calyx Right", "Mushroom body input — olfactory projection neuron terminals"),
    "CA(L)": ("Calyx Left", "Mushroom body input — olfactory projection neuron terminals"),
    "PED(R)": ("Pedunculus Right", "Mushroom body stalk — Kenyon cell axon bundle"),
    "PED(L)": ("Pedunculus Left", "Mushroom body stalk — Kenyon cell axon bundle"),
    "EB": ("Ellipsoid Body", "Central complex — orientation, navigation, and motor planning"),
    "FB": ("Fan-shaped Body", "Central complex — sleep, arousal, locomotor control"),
    "PB": ("Protocerebral Bridge", "Central complex — heading direction representation"),
    "NO": ("Noduli", "Central complex — self-motion integration"),
    "AB(R)": ("Asymmetrical Body Right", "Central complex — lateralized navigation signals"),
    "AB(L)": ("Asymmetrical Body Left", "Central complex — lateralized navigation signals"),
    "GNG": ("Gnathal Ganglia", "Subesophageal zone — taste, feeding, proboscis control"),
    "SAD": ("Saddle", "Subesophageal zone — descending neuron convergence"),
    "SPS(R)": ("Superior Posterior Slope Right", "Premotor area — descending neuron dendrites"),
    "SPS(L)": ("Superior Posterior Slope Left", "Premotor area — descending neuron dendrites"),
    "IPS(R)": ("Inferior Posterior Slope Right", "Premotor area — descending neuron integration"),
    "IPS(L)": ("Inferior Posterior Slope Left", "Premotor area — descending neuron integration"),
    "LAL(R)": ("Lateral Accessory Lobe Right", "Premotor center — locomotion command integration"),
    "LAL(L)": ("Lateral Accessory Lobe Left", "Premotor center — locomotion command integration"),
    "CRE(R)": ("Crepine Right", "Central brain neuropil — multimodal integration"),
    "CRE(L)": ("Crepine Left", "Central brain neuropil — multimodal integration"),
    "SMP(R)": ("Superior Medial Protocerebrum Right", "Higher-order integration and decision-making"),
    "SMP(L)": ("Superior Medial Protocerebrum Left", "Higher-order integration and decision-making"),
    "SLP(R)": ("Superior Lateral Protocerebrum Right", "Multimodal sensory integration"),
    "SLP(L)": ("Superior Lateral Protocerebrum Left", "Multimodal sensory integration"),
    "SIP(R)": ("Superior Intermediate Protocerebrum Right", "Integration between SMP and SLP"),
    "SIP(L)": ("Superior Intermediate Protocerebrum Left", "Integration between SMP and SLP"),
    "ICL(R)": ("Inferior Clamp Right", "Central brain neuropil near mushroom body"),
    "ICL(L)": ("Inferior Clamp Left", "Central brain neuropil near mushroom body"),
    "SCL(R)": ("Superior Clamp Right", "Central brain neuropil near mushroom body"),
    "SCL(L)": ("Superior Clamp Left", "Central brain neuropil near mushroom body"),
    "IB": ("Inferior Bridge", "Central brain — connects left and right hemispheres"),
    "ATL(R)": ("Antler Right", "Central brain neuropil near central complex"),
    "ATL(L)": ("Antler Left", "Central brain neuropil near central complex"),
    "AMMC(R)": ("Antennal Mechanosensory and Motor Center Right", "Mechanosensory processing from antenna — hearing, wind, gravity"),
    "AMMC(L)": ("Antennal Mechanosensory and Motor Center Left", "Mechanosensory processing from antenna — hearing, wind, gravity"),
}


def _get_roi_description(roi: str) -> tuple[str, str]:
    if roi in _BRAIN_ROI_DESCRIPTIONS:
        return _BRAIN_ROI_DESCRIPTIONS[roi]
    if roi in _VNC_ROI_CATEGORIES:
        full_name, _, description = _VNC_ROI_CATEGORIES[roi]
        return full_name, description
    # Medulla layers
    if roi.startswith("ME_") and "layer" in roi:
        side = "Right" if "_R_" in roi else "Left"
        layer = roi.rsplit("_", 1)[-1]
        return f"Medulla {side} Layer {layer}", f"Columnar layer {layer} of the medulla — specific depth in the retinotopic map"
    return roi, ""


def _build_roi_reference_table(roi_dist: pd.DataFrame, scope: str) -> pd.DataFrame:
    rows = []
    for _, row in roi_dist.iterrows():
        roi = row["roi"]
        region = _classify_roi(roi)
        full_name, description = _get_roi_description(roi)
        rows.append({
            "ROI": roi,
            "Name": full_name,
            "Region": region,
            "Neuron Count": row["neuron_count"],
            "Description": description,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Superclass distribution
# ---------------------------------------------------------------------------

_SUPERCLASS_GUIDE_VNC = """\
Each neuron is assigned a **superclass** based on its projection pattern — where it sends and \
receives signals relative to the VNC:

| Superclass | Meaning |
|---|---|
| **vnc_intrinsic** | Local interneurons — connect within the VNC, don't project out. The backbone of local circuit computation |
| **vnc_sensory** | Sensory neurons — bring information in from the body (mechanoreceptors, proprioceptors) |
| **ascending_neuron** | Project up from VNC to brain — carry processed signals to higher centers |
| **descending_neuron** | Project down from brain to VNC — carry commands to motor circuits |
| **vnc_motor** | Motor neurons — project out of the CNS to muscles. The final output layer |
| **vnc_efferent** | Other efferents (e.g., neuromodulatory outputs) |
| **sensory_ascending** | Sensory neurons that also ascend to the brain |

The chart groups these into categories: **Motor**, **Intrinsic**, **Sensory**, and **Other**. \
`_tbc` suffixed classes are "to be confirmed" — the morphological trace was ambiguous.
"""

_SUPERCLASS_GUIDE_BRAIN = """\
Each neuron is assigned a **superclass** based on its projection pattern — where it sends and \
receives signals within the brain:

| Superclass | Meaning |
|---|---|
| **ol_intrinsic** | Optic lobe intrinsic neurons — local processing within the visual system (medulla, lobula, lobula plate) |
| **cb_intrinsic** | Central brain intrinsic neurons — local processing within the central brain (mushroom body, central complex, etc.) |
| **visual_projection** | Visual projection neurons — relay processed visual information from the optic lobe to central brain areas |
| **visual_centrifugal** | Centrifugal neurons — project back from central brain into the optic lobe, providing feedback to visual circuits |
| **ol_sensory** | Optic lobe sensory neurons — photoreceptors (R1–R8) and early visual processing |
| **cb_sensory** | Central brain sensory neurons — receive non-visual sensory input (olfactory, gustatory, mechanosensory) |
| **cb_motor** | Central brain motor neurons — motor output from the brain (proboscis, antenna, etc.) |
| **endocrine** | Neuroendocrine cells — release hormones into the hemolymph rather than synapsing onto neurons |

The chart groups these into categories: **Motor**, **Intrinsic**, **Sensory**, and **Other**.
"""

_SUPERCLASS_GUIDE_TOTAL = """\
Each neuron is assigned a **superclass** based on its projection pattern. The full connectome \
includes superclasses from both the brain and VNC:

**Brain superclasses:**

| Superclass | Meaning |
|---|---|
| **ol_intrinsic** | Optic lobe intrinsic neurons — local visual processing |
| **cb_intrinsic** | Central brain intrinsic neurons — local processing in mushroom body, central complex, etc. |
| **visual_projection** | Relay visual information from optic lobe to central brain |
| **visual_centrifugal** | Feedback from central brain back into the optic lobe |
| **ol_sensory** | Photoreceptors (R1–R8) and early visual processing |
| **cb_sensory** | Non-visual sensory input (olfactory, gustatory, mechanosensory) |
| **cb_motor** | Motor output from the brain (proboscis, antenna) |
| **endocrine** | Neuroendocrine cells — release hormones into the hemolymph |

**VNC superclasses:**

| Superclass | Meaning |
|---|---|
| **vnc_intrinsic** | Local interneurons within the VNC |
| **vnc_sensory** | Sensory neurons from the body (mechanoreceptors, proprioceptors) |
| **vnc_motor** | Motor neurons — project out of the CNS to muscles |
| **vnc_efferent** | Other efferents (e.g., neuromodulatory outputs) |

**Shared (cross-region) superclasses:**

| Superclass | Meaning |
|---|---|
| **ascending_neuron** | Project up from VNC to brain |
| **descending_neuron** | Project down from brain to VNC |
| **sensory_ascending** | Sensory neurons that also ascend to the brain |

The chart groups these into categories: **Motor**, **Intrinsic**, **Sensory**, and **Other**.
"""

_SUPERCLASS_GUIDES = {
    "vnc": _SUPERCLASS_GUIDE_VNC,
    "brain": _SUPERCLASS_GUIDE_BRAIN,
    "total": _SUPERCLASS_GUIDE_TOTAL,
}


def _render_superclass(sc_df: pd.DataFrame, scope: str):
    if sc_df.empty:
        return

    st.header("Neuron Superclass Distribution")
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

    with st.expander("What do these superclasses mean?"):
        st.markdown(_SUPERCLASS_GUIDES.get(scope, _SUPERCLASS_GUIDE_TOTAL))


# ---------------------------------------------------------------------------
# Cell types
# ---------------------------------------------------------------------------

_CELL_TYPE_NAMING_VNC = """\
Type names are **systematic** — the prefix encodes superclass and the suffix often encodes body region, \
so you can read functional identity directly from the name.

**Superclass prefixes:**

| Prefix | Meaning | Example |
|--------|---------|---------|
| **SN** | Sensory neuron | SNta29, SNch10 |
| **IN** | Intrinsic (local interneuron) | IN01B095 |
| **AN** | Ascending neuron | AN10B045 |
| **DN** | Descending neuron | DNa02, DNp103 |
| **MN** | Motor neuron | MNad02, MNwm36 |
| **Lg** | Leg-specific circuit neuron | LgLG1a, LgLG2 |
| **W**  | Wing-specific circuit neuron | WG1–WG4 |

**Body-region suffixes** (especially visible in motor and sensory types):

| Suffix | Body region |
|--------|-------------|
| **ad** | Abdomen |
| **fl** | Front leg |
| **ml** | Middle leg |
| **hl** | Hind leg |
| **wm** | Wing muscle |
| **nm** | Neck muscle |
| **hm** | Haltere muscle |
| **ta** | Tarsal (touch/mechanoreceptor) |
| **ch** | Chordotonal (proprioception) |

**Other patterns:** Bilateral pairs share the same type name with an L/R instance suffix \
(e.g., `DNa02_L` and `DNa02_R` are both type `DNa02`). Composite names like `SNta02,SNta09` indicate \
types that couldn't be confidently split. `XXX` in the name (e.g., `INXXX027`) means the type is \
provisional.
"""

_CELL_TYPE_NAMING_BRAIN = """\
Brain cell types follow the naming conventions established across multiple *Drosophila* connectome \
projects. Many names come from classical Golgi studies and have been carried forward:

**Optic lobe cell types** (the most abundant in the brain):

| Name pattern | Meaning | Example |
|---|---|---|
| **R1–R8** | Photoreceptor subtypes — the retinal input layer | R1-R6 (broadband), R7/R8 (color) |
| **L1–L5** | Lamina monopolar cells — first visual interneurons | L1, L2 (motion pathway), L5 |
| **Mi** | Medulla intrinsic neurons — process within the medulla | Mi1, Mi4, Mi9 |
| **Tm** | Transmedullary neurons — project from medulla to lobula/lobula plate | Tm1, Tm3, Tm9 |
| **T** | T-neurons — project across lobula/lobula plate layers | T2a, T3, T4a–T4d |
| **C** | Centrifugal neurons — feed back from deeper neuropils to medulla | C2, C3 |
| **Dm** | Distal medulla amacrine cells — wide-field lateral processing | Dm1, Dm8 |

**Central brain cell types:**

| Name pattern | Meaning | Example |
|---|---|---|
| **KC** | Kenyon cells — mushroom body intrinsic neurons (learning and memory) | KCab, KCg |
| **MBON** | Mushroom body output neurons — read out learned associations | MBON01, MBON-a1 |
| **DAN** | Dopaminergic neurons — encode reward/punishment signals to mushroom body | DAN-d1 |
| **PN** | Projection neurons — relay olfactory information from antennal lobe to mushroom body | PN-DC3 |
| **LN** | Local neurons — lateral inhibition within the antennal lobe | LN-glomerular |
| **FB\\_\\***, **EB\\_\\***, **PB\\_\\*** | Central complex neurons — navigation, orientation | EPG, PFN, hDelta |
| **DN** | Descending neurons — same prefix as VNC, brain-to-VNC commands | DNa02, DNp01 |

**Naming notes:** Unlike VNC types which are systematically prefixed, many brain types carry \
historical names. Bilateral pairs use L/R suffixes just like VNC types.
"""

_CELL_TYPE_NAMING_TOTAL = (
    "The full connectome combines VNC and brain naming conventions. "
    "See the **VNC** and **Brain** tabs for scope-specific guides.\n\n"
    "**VNC types** use systematic prefixes: `SN` (sensory), `IN` (intrinsic), `AN` (ascending), "
    "`DN` (descending), `MN` (motor), `Lg` (leg), `W` (wing).\n\n"
    "**Brain types** often carry historical names from classical Golgi studies: `R1–R8` "
    "(photoreceptors), `L1–L5` (lamina monopolars), `Tm` (transmedullary), `T` (T-neurons), "
    "`KC` (Kenyon cells), `MBON` (mushroom body output), `PN` (projection neurons)."
)

_CELL_TYPE_NAMING = {
    "vnc": _CELL_TYPE_NAMING_VNC,
    "brain": _CELL_TYPE_NAMING_BRAIN,
    "total": _CELL_TYPE_NAMING_TOTAL,
}


def _render_cell_types(cell_types: tuple[pd.DataFrame, int], scope: str):
    type_counts_df, unique_count = cell_types
    if type_counts_df.empty:
        return

    st.header("Top Cell Types")
    top_n = st.slider("Number of cell types to show", 10, 100, 50, key=f"cell_types_{scope}")
    sliced = type_counts_df.head(top_n)

    fig = go.Figure(go.Treemap(
        labels=sliced["type"].tolist(),
        parents=[""] * len(sliced),
        values=sliced["count"].tolist(),
        textinfo="label+value",
    ))
    fig.update_layout(
        title=f"Top {top_n} Cell Types (of {unique_count:,} unique)",
        height=500,
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("About cell types"):
        st.markdown(f"""\
Cell type is a finer morphological/genetic classification — **{unique_count:,} distinct types**. \
Neurons of the same cell type share the same shape, connectivity pattern, and (usually) neurotransmitter.

The treemap shows the most common types by neuron count. Use the slider to explore more of the long tail.
""")

    with st.expander("Cell type naming convention"):
        st.markdown(_CELL_TYPE_NAMING.get(scope, _CELL_TYPE_NAMING_TOTAL))


# ---------------------------------------------------------------------------
# Neurotransmitters
# ---------------------------------------------------------------------------

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

    with st.expander("Neurotransmitter guide"):
        st.markdown("""\
The neurotransmitter is the chemical released by the **sending (presynaptic) neuron** at all of its \
T-bar release sites. This follows **Dale's principle** — a neuron uses the same transmitter at every \
synapse — so a single NT assignment determines the sign of all outgoing connections from that neuron.

The sign labels above each bar show the synaptic effect. Note that *Drosophila* NT conventions \
differ from vertebrates:

| NT | Effect | Notes |
|---|---|---|
| **Acetylcholine** | Excitatory (+1) | The dominant excitatory transmitter in *Drosophila* (unlike vertebrates where glutamate fills this role) |
| **GABA** | Inhibitory (-1) | Same role as in vertebrates |
| **Glutamate** | Inhibitory (-1) | **Opposite of vertebrates** — inhibitory at central synapses in *Drosophila* |
| **Serotonin** | Modulatory | Neuromodulator |
| **Histamine** | Inhibitory (-1) | Used by photoreceptors |
| **Dopamine** | Modulatory | Neuromodulator involved in learning and motivation |
| **Octopamine** | Modulatory | Invertebrate analog of norepinephrine |
| **Unclear** | Unknown | Couldn't be confidently assigned by the automated classifier |

**Motor neuron quirk:** 672 of 702 motor neurons have "unclear" NT assignment. Motor neurons at the \
neuromuscular junction use glutamate as an *excitatory* transmitter (like vertebrates), which conflicts \
with the CNS convention where glutamate is inhibitory — so the classifier flags them as ambiguous.
""")

    with st.expander("How NT identity is determined"):
        st.markdown("""\
NT assignments are **not direct biochemical measurements** — they are machine-learning predictions \
from EM image features (synapse morphology, vesicle shape and size). The dataset provides a \
three-stage prediction pipeline:

1. **`predictedNt`** — a per-neuron classifier based on that individual neuron's EM features. \
Comes with a confidence score; median ~0.94, but some neurons score as low as 0.25.
2. **`celltypePredictedNt`** — an aggregated prediction across all neurons of the same cell type. \
This smooths out noisy individual predictions.
3. **`consensusNt`** — the final call combining both. This is the column used in the chart above.

All three columns agree for ~94% of neurons. The remaining ~6% disagreement is concentrated in \
low-confidence neurons and motor neurons (see motor neuron quirk above).
""")


# ---------------------------------------------------------------------------
# Synapse distributions
# ---------------------------------------------------------------------------

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

    with st.expander("Reading these histograms"):
        st.markdown("""\
**Pre-synaptic** (output) counts show how many synapses each neuron *sends*; \
**post-synaptic** (input) counts show how many it *receives*. Values are clipped at the 99th \
percentile to keep the long tail from compressing the bulk of the distribution. \
The yellow dashed line marks the median.

Most neurons have relatively few synapses, producing the heavy right skew typical of \
connectome degree distributions.
""")


# ---------------------------------------------------------------------------
# Motor neurons
# ---------------------------------------------------------------------------

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

    with st.expander("Motor neuron breakdowns"):
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


# ---------------------------------------------------------------------------
# Connectivity
# ---------------------------------------------------------------------------

def _render_connectivity(conn: dict, scope: str):
    st.header("Connectivity Analysis")

    sample_size = st.slider(
        "Sample size (top neurons by input synapses)", 50, 200, 100, step=10,
        key=f"conn_sample_{scope}",
    )
    if sample_size != 100:
        conn = load_connectivity_metrics(sample_size, scope)

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

    with st.expander("Reading the adjacency matrices"):
        st.markdown(f"""\
Each heatmap is an N x N matrix where row *i*, column *j* is the synapse count from neuron *i* \
(pre-synaptic) to neuron *j* (post-synaptic). Colors are log-scaled — log(1 + weight) — so weak \
connections remain visible alongside the strong ones.

- **Raw** — neurons are sorted by total input synapse count (the same order as the sample slider). \
Structure here reflects the degree distribution: high-input neurons cluster at one end.
- **Clustered** — neurons are reordered by Ward-linkage hierarchical clustering on the symmetric \
connection matrix (A + A^T). This groups neurons that connect to similar partners, revealing \
functional modules — blocks along the diagonal are groups of neurons that preferentially wire to each other.

The matrix is sparse ({conn['fill_pct']:.2f}% fill) — most neuron pairs have zero direct synapses, \
which is typical for real neural circuits.
""")

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

    with st.expander("What does weight mean?"):
        st.markdown("""\
A **synapse weight** is the total number of individual synaptic connections from one neuron to another. \
A weight of 5 means neuron A makes 5 separate synapses onto neuron B — more synapses generally means \
a stronger influence.

- **Raw Synapse Counts** — the direct counts. The distribution is heavily right-skewed: most \
connections are weak (1-3 synapses), but a few are very strong (hundreds). The red dashed line marks the median.
- **Log-Transformed** — log(1 + count) compresses the long tail, making it easier to see the shape \
of the distribution. This is the same transform used in the heatmap color scale.

For the spiking neural network, these raw counts are the starting point that gets converted into \
model parameters (see the Parameter Strategies page).
""")
