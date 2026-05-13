"""
Cached data access for the male-cns:v0.9 connectome.

All neuPrint API results are transparently cached to data/cache/ via joblib.
First call hits the API; subsequent calls load from disk instantly.

Usage:
    from digital_drosophila.data import connect, load_dataset_overview, load_vnc_neurons, load_connectivity

To force a re-fetch, delete data/cache/ or the specific subdirectory.
"""

import os
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from joblib import Memory
from neuprint import (
    Client,
    NeuronCriteria,
    fetch_adjacencies,
    fetch_all_rois,
    fetch_meta,
    fetch_neurons,
    fetch_primary_rois,
    set_default_client,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CACHE_DIR = _PROJECT_ROOT / "data" / "cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

memory = Memory(_CACHE_DIR, verbose=0)

_client: Client | None = None


def connect() -> Client:
    global _client
    if _client is not None:
        return _client
    for env_path in [
        _PROJECT_ROOT / ".env",
        _PROJECT_ROOT.parent / ".env",
        Path("/home/ubuntu/Repos/.env"),
    ]:
        if env_path.exists():
            load_dotenv(env_path)
            break
    _client = Client(
        server="neuprint.janelia.org",
        dataset="male-cns:v0.9",
        token=os.environ["NEU_PRINT_API_KEY"],
    )
    set_default_client(_client)
    return _client


@memory.cache
def load_dataset_overview() -> tuple[dict, list[str], list[str], list[str]]:
    connect()
    meta = fetch_meta()
    all_rois = fetch_all_rois()
    primary_rois = fetch_primary_rois()
    vnc_rois = sorted(
        r for r in all_rois
        if any(x in r for x in ["VNC", "T1", "T2", "T3", "ANm", "Leg", "leg"])
    )
    return meta, all_rois, primary_rois, vnc_rois


@memory.cache
def load_vnc_neurons() -> tuple[pd.DataFrame, pd.DataFrame]:
    connect()
    criteria = NeuronCriteria(rois=["VNC"], min_pre=1, min_post=1)
    neurons_df, roi_counts = fetch_neurons(criteria)
    return neurons_df, roi_counts


@memory.cache
def load_connectivity(body_ids: tuple[int, ...], n: int) -> np.ndarray:
    connect()
    sample_ids = list(body_ids[:n])
    criteria = NeuronCriteria(bodyId=sample_ids)
    _, conn_df = fetch_adjacencies(criteria, criteria)

    agg = conn_df.groupby(["bodyId_pre", "bodyId_post"])["weight"].sum().reset_index()
    id_to_idx = {bid: i for i, bid in enumerate(sample_ids)}
    m = len(sample_ids)
    adj = np.zeros((m, m), dtype=np.float32)
    for _, row in agg.iterrows():
        pre, post, w = row["bodyId_pre"], row["bodyId_post"], row["weight"]
        if pre in id_to_idx and post in id_to_idx:
            adj[id_to_idx[pre], id_to_idx[post]] = w

    return adj


def find_nt_column(df: pd.DataFrame) -> str | None:
    for col in ["consensusNt", "predictedNt", "celltypePredictedNt"]:
        if col in df.columns and df[col].notna().any():
            return col
    return None
