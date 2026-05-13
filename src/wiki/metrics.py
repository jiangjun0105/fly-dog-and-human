"""
Pre-computed metrics for the male-cns:v0.9 connectome.

Two-tier caching:
  1. src/wiki/data/metrics/ — clean JSON + CSV + .npy files, committed to git.
                              The wiki and CI can run from these alone.
  2. data/cache/            — joblib opaque cache, gitignored.
                              Used as fallback when metrics/ doesn't exist yet.

Workflow:
  - First time:  load_metrics() computes via joblib, returns results.
  - Run `export_metrics()` (or `just export`) to write src/wiki/data/metrics/.
  - After that:  load_metrics() reads directly from src/wiki/data/metrics/.

Usage:
    from wiki.metrics import load_metrics
    m = load_metrics()
    m["dataset_stats"]["vnc_neuron_count"]
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.spatial.distance import squareform

from digital_drosophila.constants import (
    DEFAULT_SAMPLE_SIZE,
    NT_SIGN_LABELS,
    NT_SIGN_MAP,
    superclass_category,
)
from digital_drosophila.data import (
    find_nt_column,
    load_connectivity,
    load_dataset_overview,
    load_vnc_neurons,
    memory,
)

_WIKI_ROOT = Path(__file__).resolve().parent
METRICS_DIR = _WIKI_ROOT / "data" / "metrics"


@memory.cache
def compute_dataset_stats() -> dict:
    meta, all_rois, primary_rois, vnc_rois = load_dataset_overview()
    vnc_df, _ = load_vnc_neurons()
    motor_count = int((vnc_df["superclass"] == "vnc_motor").sum()) if "superclass" in vnc_df.columns else 0
    return {
        "description": meta.get("description", ""),
        "total_pre_count": meta.get("totalPreCount", 0),
        "total_post_count": meta.get("totalPostCount", 0),
        "roi_count": len(all_rois),
        "primary_roi_count": len(primary_rois),
        "vnc_neuron_count": len(vnc_df),
        "motor_neuron_count": motor_count,
        "vnc_roi_count": len(vnc_rois),
        "vnc_rois": vnc_rois,
    }


@memory.cache
def compute_superclass_distribution() -> pd.DataFrame:
    vnc_df, _ = load_vnc_neurons()
    if "superclass" not in vnc_df.columns:
        return pd.DataFrame(columns=["superclass", "count", "category"])
    sc = vnc_df["superclass"].value_counts().reset_index()
    sc.columns = ["superclass", "count"]
    sc["category"] = sc["superclass"].map(superclass_category)
    return sc


@memory.cache
def compute_cell_type_distribution() -> tuple[pd.DataFrame, int]:
    vnc_df, _ = load_vnc_neurons()
    if "type" not in vnc_df.columns:
        return pd.DataFrame(columns=["type", "count"]), 0
    counts = vnc_df["type"].value_counts().reset_index()
    counts.columns = ["type", "count"]
    return counts, int(vnc_df["type"].nunique())


@memory.cache
def compute_nt_distribution() -> dict:
    vnc_df, _ = load_vnc_neurons()
    nt_col = find_nt_column(vnc_df)
    if nt_col is None:
        return {"nt_col": None, "nt_counts": pd.DataFrame(), "missing_count": 0, "missing_pct": 0.0}

    nt_counts = vnc_df[nt_col].value_counts().reset_index()
    nt_counts.columns = ["neurotransmitter", "count"]
    nt_counts["sign"] = nt_counts["neurotransmitter"].map(
        lambda x: NT_SIGN_LABELS.get(NT_SIGN_MAP.get(str(x).lower()), "?")
    )
    missing = int(vnc_df[nt_col].isna().sum())
    return {
        "nt_col": nt_col,
        "nt_counts": nt_counts,
        "missing_count": missing,
        "missing_pct": 100.0 * missing / len(vnc_df) if len(vnc_df) > 0 else 0.0,
    }


@memory.cache
def compute_synapse_distributions() -> dict:
    vnc_df, _ = load_vnc_neurons()
    result = {}
    for col in ["pre", "post"]:
        if col not in vnc_df.columns:
            continue
        series = vnc_df[col]
        p99 = float(series.quantile(0.99))
        result[col] = {
            "values_clipped": series.clip(upper=p99).values,
            "median": float(series.median()),
        }
    return result


@memory.cache
def compute_motor_neuron_metrics() -> dict:
    vnc_df, _ = load_vnc_neurons()
    nt_col = find_nt_column(vnc_df)

    if "superclass" not in vnc_df.columns:
        return {"count": 0}

    motor = vnc_df[vnc_df["superclass"] == "vnc_motor"]
    if len(motor) == 0:
        return {"count": 0}

    result: dict = {
        "count": len(motor),
        "unique_types": int(motor["type"].nunique()),
    }

    if nt_col and nt_col in motor.columns:
        nt = motor[nt_col].value_counts().reset_index()
        nt.columns = ["NT", "Count"]
        nt["Sign"] = nt["NT"].map(
            lambda x: {1: "+1", -1: "-1", None: "mod"}.get(NT_SIGN_MAP.get(str(x).lower()), "?")
        )
        result["nt_breakdown"] = nt

    if "subclass" in motor.columns:
        sub = motor["subclass"].value_counts().reset_index()
        sub.columns = ["Subclass", "Count"]
        result["subclass_breakdown"] = sub

    if "somaNeuromere" in motor.columns and motor["somaNeuromere"].notna().any():
        soma = motor["somaNeuromere"].value_counts().reset_index()
        soma.columns = ["Neuromere", "Count"]
        result["neuromere_breakdown"] = soma

    return result


def _get_nt_signs(neurons_df: pd.DataFrame, nt_col: str | None, n: int) -> np.ndarray:
    if nt_col and nt_col in neurons_df.columns:
        signs = neurons_df[nt_col].head(n).map(
            lambda x: NT_SIGN_MAP.get(str(x).lower(), +1)
            if NT_SIGN_MAP.get(str(x).lower()) is not None
            else +1
        ).values.astype(float)
    else:
        signs = np.ones(n)
    return signs


def compute_strategies(adj: np.ndarray, neurons_df: pd.DataFrame, nt_col: str | None) -> list[dict]:
    n = adj.shape[0]
    nt_signs = _get_nt_signs(neurons_df, nt_col, n)
    in_degree = adj.sum(axis=0)

    baseline_vth = 10.0
    mean_in = in_degree[in_degree > 0].mean() if (in_degree > 0).any() else 1.0
    vth_a = np.maximum(baseline_vth * (in_degree / mean_in), 1.0)
    scale_a = (0.5 * vth_a.mean()) / max(in_degree.mean(), 1.0)
    weights_a = adj * nt_signs[:, np.newaxis] * scale_a

    vth_fixed = 10.0
    total_input = adj.sum(axis=0, keepdims=True)
    total_input = np.where(total_input == 0, 1.0, total_input)
    weights_b = (adj / total_input) * nt_signs[:, np.newaxis]

    log_w = np.log1p(adj)
    mean_log_input = log_w.sum(axis=0).mean()
    scale_c = (0.5 * vth_fixed) / max(mean_log_input, 1e-6)
    weights_c = log_w * nt_signs[:, np.newaxis] * scale_c

    return [
        {"name": "A: Degree-Scaled Threshold", "vth": vth_a, "weights": weights_a, "scale": scale_a},
        {"name": "B: Conductance-Normalized", "vth": np.full(n, vth_fixed), "weights": weights_b, "scale": None},
        {"name": "C: Log-Scaled Weights", "vth": np.full(n, vth_fixed), "weights": weights_c, "scale": scale_c},
    ]


@memory.cache
def compute_connectivity_metrics(sample_size: int = DEFAULT_SAMPLE_SIZE) -> dict:
    vnc_df, _ = load_vnc_neurons()
    nt_col = find_nt_column(vnc_df)

    sample_df = vnc_df.nlargest(sample_size, "post").reset_index(drop=True)
    sample_ids = tuple(sample_df["bodyId"].tolist())
    adj = load_connectivity(sample_ids, sample_size)

    nonzero = int(np.count_nonzero(adj))
    total = adj.shape[0] ** 2

    symmetric = adj + adj.T
    np.fill_diagonal(symmetric, 0)
    max_val = symmetric.max()
    if max_val > 0:
        dist = max_val - symmetric
        np.fill_diagonal(dist, 0)
        dist = np.maximum(dist, 0)
        condensed = squareform(dist, checks=False)
        Z = linkage(condensed, method="ward")
        cluster_order = leaves_list(Z)
    else:
        cluster_order = np.arange(adj.shape[0])

    weights_nz = adj[adj > 0]
    strategies = compute_strategies(adj, sample_df, nt_col)

    return {
        "adj": adj,
        "sample_df": sample_df,
        "nonzero": nonzero,
        "total": total,
        "fill_pct": 100.0 * nonzero / total if total > 0 else 0.0,
        "cluster_order": cluster_order,
        "weight_min": float(weights_nz.min()) if len(weights_nz) > 0 else 0.0,
        "weight_median": float(np.median(weights_nz)) if len(weights_nz) > 0 else 0.0,
        "weight_max": float(weights_nz.max()) if len(weights_nz) > 0 else 0.0,
        "weights_nz": weights_nz,
        "strategies": strategies,
    }


def _compute_all(sample_size: int = DEFAULT_SAMPLE_SIZE) -> dict:
    return {
        "dataset_stats": compute_dataset_stats(),
        "superclass": compute_superclass_distribution(),
        "cell_types": compute_cell_type_distribution(),
        "neurotransmitters": compute_nt_distribution(),
        "synapse_distributions": compute_synapse_distributions(),
        "motor_neurons": compute_motor_neuron_metrics(),
        "connectivity": compute_connectivity_metrics(sample_size),
    }


# ---------------------------------------------------------------------------
# Export to data/metrics/ (clean, git-tracked files)
# ---------------------------------------------------------------------------

def _metrics_dir(sample_size: int) -> Path:
    d = METRICS_DIR / f"sample_{sample_size}"
    return d


def export_metrics(sample_size: int = DEFAULT_SAMPLE_SIZE) -> Path:
    """Compute all metrics and write clean files to data/metrics/sample_<n>/."""
    m = _compute_all(sample_size)
    out = _metrics_dir(sample_size)
    out.mkdir(parents=True, exist_ok=True)

    # dataset_stats — JSON
    (out / "dataset_stats.json").write_text(json.dumps(m["dataset_stats"], indent=2, default=str))

    # superclass — CSV
    m["superclass"].to_csv(out / "superclass.csv", index=False)

    # cell_types — CSV + scalar
    ct_df, ct_unique = m["cell_types"]
    ct_df.to_csv(out / "cell_types.csv", index=False)
    (out / "cell_types_meta.json").write_text(json.dumps({"unique_count": ct_unique}))

    # neurotransmitters — CSV + scalars
    nt = m["neurotransmitters"]
    nt_meta = {"nt_col": nt["nt_col"], "missing_count": nt["missing_count"], "missing_pct": nt["missing_pct"]}
    (out / "nt_meta.json").write_text(json.dumps(nt_meta))
    if isinstance(nt["nt_counts"], pd.DataFrame) and not nt["nt_counts"].empty:
        nt["nt_counts"].to_csv(out / "nt_counts.csv", index=False)

    # synapse_distributions — npy + JSON
    syn = m["synapse_distributions"]
    syn_meta = {}
    for col in ["pre", "post"]:
        if col in syn:
            np.save(out / f"syn_{col}_clipped.npy", syn[col]["values_clipped"])
            syn_meta[col] = {"median": syn[col]["median"]}
    (out / "syn_meta.json").write_text(json.dumps(syn_meta))

    # motor_neurons — JSON + CSVs
    motor = m["motor_neurons"]
    motor_scalars = {k: v for k, v in motor.items() if not isinstance(v, pd.DataFrame)}
    (out / "motor_meta.json").write_text(json.dumps(motor_scalars))
    for key in ["nt_breakdown", "subclass_breakdown", "neuromere_breakdown"]:
        if key in motor:
            motor[key].to_csv(out / f"motor_{key}.csv", index=False)

    # connectivity — npy + JSON + strategy npy
    conn = m["connectivity"]
    np.save(out / "adj.npy", conn["adj"])
    np.save(out / "cluster_order.npy", conn["cluster_order"])
    np.save(out / "weights_nz.npy", conn["weights_nz"])
    conn["sample_df"].to_csv(out / "sample_neurons.csv", index=False)

    conn_meta = {
        "nonzero": conn["nonzero"],
        "total": conn["total"],
        "fill_pct": conn["fill_pct"],
        "weight_min": conn["weight_min"],
        "weight_median": conn["weight_median"],
        "weight_max": conn["weight_max"],
    }
    (out / "conn_meta.json").write_text(json.dumps(conn_meta))

    strategies = conn["strategies"]
    for i, s in enumerate(strategies):
        prefix = f"strategy_{i}"
        np.save(out / f"{prefix}_weights.npy", s["weights"])
        np.save(out / f"{prefix}_vth.npy", s["vth"])
        s_meta = {"name": s["name"], "scale": s["scale"]}
        (out / f"{prefix}_meta.json").write_text(json.dumps(s_meta, default=str))

    return out


# ---------------------------------------------------------------------------
# Load from data/metrics/ (fast, no computation)
# ---------------------------------------------------------------------------

def _load_exported(sample_size: int) -> dict | None:
    d = _metrics_dir(sample_size)
    if not (d / "dataset_stats.json").exists():
        return None

    m: dict = {}

    m["dataset_stats"] = json.loads((d / "dataset_stats.json").read_text())

    m["superclass"] = pd.read_csv(d / "superclass.csv") if (d / "superclass.csv").exists() else pd.DataFrame()

    if (d / "cell_types.csv").exists():
        ct_df = pd.read_csv(d / "cell_types.csv")
        ct_meta = json.loads((d / "cell_types_meta.json").read_text())
        m["cell_types"] = (ct_df, ct_meta["unique_count"])
    else:
        m["cell_types"] = (pd.DataFrame(), 0)

    nt_meta = json.loads((d / "nt_meta.json").read_text()) if (d / "nt_meta.json").exists() else {}
    nt_counts = pd.read_csv(d / "nt_counts.csv") if (d / "nt_counts.csv").exists() else pd.DataFrame()
    m["neurotransmitters"] = {**nt_meta, "nt_counts": nt_counts}

    syn_meta = json.loads((d / "syn_meta.json").read_text()) if (d / "syn_meta.json").exists() else {}
    syn = {}
    for col in ["pre", "post"]:
        npy = d / f"syn_{col}_clipped.npy"
        if npy.exists() and col in syn_meta:
            syn[col] = {"values_clipped": np.load(npy), "median": syn_meta[col]["median"]}
    m["synapse_distributions"] = syn

    motor_meta = json.loads((d / "motor_meta.json").read_text()) if (d / "motor_meta.json").exists() else {"count": 0}
    for key in ["nt_breakdown", "subclass_breakdown", "neuromere_breakdown"]:
        csv = d / f"motor_{key}.csv"
        if csv.exists():
            motor_meta[key] = pd.read_csv(csv)
    m["motor_neurons"] = motor_meta

    conn_meta = json.loads((d / "conn_meta.json").read_text())
    conn = {
        **conn_meta,
        "adj": np.load(d / "adj.npy"),
        "cluster_order": np.load(d / "cluster_order.npy"),
        "weights_nz": np.load(d / "weights_nz.npy"),
        "sample_df": pd.read_csv(d / "sample_neurons.csv"),
    }
    strategies = []
    for i in range(3):
        prefix = f"strategy_{i}"
        s_meta = json.loads((d / f"{prefix}_meta.json").read_text())
        s_meta["weights"] = np.load(d / f"{prefix}_weights.npy")
        s_meta["vth"] = np.load(d / f"{prefix}_vth.npy")
        strategies.append(s_meta)
    conn["strategies"] = strategies
    m["connectivity"] = conn

    return m


def load_connectivity_metrics(sample_size: int) -> dict:
    """Load connectivity metrics for a given sample size (exported or computed)."""
    exported = _load_exported(sample_size)
    if exported is not None:
        return exported["connectivity"]
    return compute_connectivity_metrics(sample_size)


def load_metrics(sample_size: int = DEFAULT_SAMPLE_SIZE) -> dict:
    """Load metrics from data/metrics/ if available, otherwise compute."""
    exported = _load_exported(sample_size)
    if exported is not None:
        return exported
    return _compute_all(sample_size)
