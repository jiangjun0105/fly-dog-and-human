"""Functional neuron selection: biologically-mapped motor and premotor neurons.

Selects a tractable (200-600 neuron) subset of the VNC connectome that forms
a genuine locomotor circuit, instead of the 100-hub-neuron sample used
previously.

Strategy
--------
1. Start with leg motor neurons (superclass=='vnc_motor', leg-nerve exitNerve).
2. Map each motor neuron to a FlyGym leg (LF/RF/LM/RM/LH/RH) via exitNerve +
   somaSide.
3. Take the top N motor neurons per leg by postsynaptic synapse count.
4. Trace n_hops upstream via fetch_adjacencies to find the strongest premotor
   interneurons (by total weight onto the motor pool).
   - Hop 1: top 200 presynaptic partners of the 48 motor neurons
   - Hop 2: top 150 presynaptic partners of the hop-1 neurons (~400 total)
   - Hop 3: top 100 presynaptic partners of the hop-2 neurons (~500-600 total)
5. Keep unique neurons across all hops.

The returned adjacency data is sparse COO (load_connectivity_sparse).

Usage
-----
    from digital_drosophila.functional_selection import select_locomotor_network

    body_ids, meta_df, motor_leg_map, sources, targets, weights = (
        select_locomotor_network(n_hops=2)
    )
"""

from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Leg nerves by FlyGym leg segment
T1_NERVES = frozenset(["ProLN", "ProAN", "DProN", "VProN", "ADMN"])
T2_NERVES = frozenset(["MesoLN", "MesoAN"])
T3_NERVES = frozenset(["MetaLN"])
ALL_LEG_NERVES = T1_NERVES | T2_NERVES | T3_NERVES

# Number of motor neurons to select per leg (both sides combined before split)
MOTOR_TOP_N_PER_LEG = 8

# Number of strongest premotor neurons to include per hop
# Hop 1: top 200, Hop 2: top 150, Hop 3: top 100
PREMOTOR_TOP_N = 200
PREMOTOR_TOP_N_PER_HOP = [200, 150, 100]

_PACKAGE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _PACKAGE_DIR.parent.parent
_CACHE_DIR = _PROJECT_ROOT / "data" / "cache"


def _assign_leg(exit_nerve: str, soma_side: str) -> str | None:
    """Map (exitNerve, somaSide) to FlyGym leg abbreviation."""
    if exit_nerve in T1_NERVES:
        segment = "F"
    elif exit_nerve in T2_NERVES:
        segment = "M"
    elif exit_nerve in T3_NERVES:
        segment = "H"
    else:
        return None
    side = "L" if soma_side == "L" else "R"
    return side + segment


def select_locomotor_network(
    motor_top_n: int = MOTOR_TOP_N_PER_LEG,
    premotor_top_n: int = PREMOTOR_TOP_N,
    n_hops: int = 1,
) -> tuple[
    list[int],           # ordered body IDs
    pd.DataFrame,        # neuron metadata
    dict[int, str],      # motor_body_id -> leg abbrev (e.g. 'LF')
    np.ndarray,          # COO sources (int32)
    np.ndarray,          # COO targets (int32)
    np.ndarray,          # COO weights (float32)
]:
    """Select a biologically-mapped locomotor network from the connectome.

    Parameters
    ----------
    motor_top_n : int
        Number of top motor neurons per leg to include (selected by postsynaptic
        synapse count).
    premotor_top_n : int
        Number of strongest premotor interneurons to include for hop 1 (selected
        by total summed weight onto the chosen motor pool). For hops 2+, the
        counts are taken from PREMOTOR_TOP_N_PER_HOP.
    n_hops : int
        Number of upstream hops to trace from motor neurons (default 1).
        - Hop 1: top 200 presynaptic partners of the 48 motor neurons
        - Hop 2: top 150 presynaptic partners of the hop-1 neurons
        - Hop 3: top 100 presynaptic partners of the hop-2 neurons
        Neurons already selected are excluded at each hop (no duplicates).

    Returns
    -------
    body_ids : list[int]
        Ordered list of body IDs for the network (motor first, then premotor).
    meta_df : DataFrame
        Neuron metadata with columns: bodyId, superclass, exitNerve, somaSide,
        leg (FlyGym abbreviation), post, consensusNt, predictedNtConfidence.
    motor_leg_map : dict[int, str]
        Maps motor neuron body ID → FlyGym leg abbreviation ('LF', 'RF', ...).
    sources, targets, weights : ndarray
        Sparse COO adjacency arrays (indices into body_ids ordering).
    """
    from .data import connect, load_vnc_neurons, load_connectivity_sparse
    from neuprint import fetch_adjacencies, NeuronCriteria

    connect()
    neurons_df, _ = load_vnc_neurons()

    # ------------------------------------------------------------------
    # Step 1: identify and map leg motor neurons
    # ------------------------------------------------------------------
    motor_all = neurons_df[neurons_df["superclass"] == "vnc_motor"].copy()
    leg_motor = motor_all[motor_all["exitNerve"].isin(ALL_LEG_NERVES)].copy()

    leg_motor["leg"] = leg_motor.apply(
        lambda row: _assign_leg(row["exitNerve"], row["somaSide"]),
        axis=1,
    )
    leg_motor = leg_motor.dropna(subset=["leg"])

    # ------------------------------------------------------------------
    # Step 2: select top motor neurons per leg
    # ------------------------------------------------------------------
    selected_motor_parts = []
    for leg in ["LF", "RF", "LM", "RM", "LH", "RH"]:
        subset = leg_motor[leg_motor["leg"] == leg]
        top = subset.nlargest(motor_top_n, "post")
        selected_motor_parts.append(top)

    motor_df = pd.concat(selected_motor_parts).drop_duplicates(subset="bodyId")
    motor_ids = list(motor_df["bodyId"].values)
    motor_id_set = set(motor_ids)

    print(f"[functional_selection] Selected {len(motor_ids)} motor neurons "
          f"({motor_top_n} per leg × 6 legs)")

    # ------------------------------------------------------------------
    # Step 3: multi-hop upstream tracing
    # ------------------------------------------------------------------
    # Per-hop top-N counts: use PREMOTOR_TOP_N_PER_HOP list, falling back
    # to [premotor_top_n] for hop 1 and halving each subsequent hop.
    hop_top_ns = list(PREMOTOR_TOP_N_PER_HOP)
    # Patch hop 1 count in case premotor_top_n was customised
    hop_top_ns[0] = premotor_top_n

    # Track all selected neurons (motor + premotor added each hop)
    all_selected_ids = list(motor_ids)
    all_selected_set = set(motor_ids)
    vnc_id_set = set(neurons_df["bodyId"].values)

    # The "frontier" neurons whose upstream partners we query each hop
    frontier_ids = motor_ids

    for hop in range(1, n_hops + 1):
        top_n = hop_top_ns[hop - 1] if hop - 1 < len(hop_top_ns) else 50
        print(f"[functional_selection] Hop {hop}: fetching upstream of "
              f"{len(frontier_ids)} neurons (top {top_n})...")

        _, conn_df = fetch_adjacencies(None, NeuronCriteria(bodyId=frontier_ids))

        if conn_df.empty:
            print(f"[functional_selection] Hop {hop}: no connections found, stopping.")
            break

        # Sum weight per presynaptic neuron across all frontier targets
        agg = (
            conn_df.groupby("bodyId_pre")["weight"]
            .sum()
            .reset_index()
            .sort_values("weight", ascending=False)
        )
        # Exclude neurons already selected (no duplicates)
        agg = agg[~agg["bodyId_pre"].isin(all_selected_set)]

        # Filter to neurons present in the VNC dataset (ensures metadata)
        agg = agg[agg["bodyId_pre"].isin(vnc_id_set)]

        new_premotor = list(agg.head(top_n)["bodyId_pre"].values)

        print(f"[functional_selection] Hop {hop}: added {len(new_premotor)} neurons")

        all_selected_ids.extend(new_premotor)
        all_selected_set.update(new_premotor)

        # The newly added neurons become the frontier for the next hop
        frontier_ids = new_premotor

        if not frontier_ids:
            break

    premotor_ids = [bid for bid in all_selected_ids if bid not in motor_id_set]
    print(f"[functional_selection] Total premotor neurons across all hops: "
          f"{len(premotor_ids)}")

    # ------------------------------------------------------------------
    # Step 4: assemble final network
    # ------------------------------------------------------------------
    all_body_ids = motor_ids + premotor_ids

    # Build metadata DataFrame for the full network
    meta_df = neurons_df[neurons_df["bodyId"].isin(all_body_ids)].copy()
    # Add leg column (NaN for non-motor)
    leg_series = leg_motor.set_index("bodyId")["leg"]
    meta_df = meta_df.copy()
    meta_df["leg"] = meta_df["bodyId"].map(leg_series)

    # Ensure consistent ordering: motor first, then premotor
    body_id_order = {bid: i for i, bid in enumerate(all_body_ids)}
    meta_df = meta_df.sort_values(
        "bodyId", key=lambda s: s.map(body_id_order)
    ).reset_index(drop=True)

    # Motor leg map: bodyId -> leg abbreviation
    motor_leg_map: dict[int, str] = dict(
        zip(motor_df["bodyId"].values, motor_df["leg"].values)
    )

    print(f"[functional_selection] Total network: {len(all_body_ids)} neurons")
    print(f"  Motor neurons:   {len(motor_ids)}")
    print(f"  Premotor neurons:{len(premotor_ids)} ({n_hops} hop(s))")

    # ------------------------------------------------------------------
    # Step 5: load sparse connectivity
    # ------------------------------------------------------------------
    print("[functional_selection] Loading sparse connectivity matrix...")
    sources, targets, weights = load_connectivity_sparse(tuple(all_body_ids))

    print(f"[functional_selection] Done. {len(sources)} connections loaded.")

    return all_body_ids, meta_df, motor_leg_map, sources, targets, weights


def build_motor_actuator_map(
    motor_leg_map: dict[int, str],
    body_ids: list[int],
) -> dict[int, list[int]]:
    """Build motor neuron index → list of actuator indices mapping.

    Each motor neuron is mapped to the primary actuators of its corresponding
    FlyGym leg: coxa-pitch (0), femur-pitch (3), and tibia-pitch (5).

    Parameters
    ----------
    motor_leg_map : dict[int, str]
        Maps motor neuron body ID → FlyGym leg abbreviation.
    body_ids : list[int]
        Ordered list of all body IDs in the network.

    Returns
    -------
    dict[int, list[int]]
        Maps network index (position in body_ids) → list of FlyGym actuator indices.
    """
    from .locomotion import LEG_OFFSETS

    # FlyGym LEG_OFFSETS uses lowercase leg names
    _LEG_NAME_MAP = {
        "LF": "lf",
        "RF": "rf",
        "LM": "lm",
        "RM": "rm",
        "LH": "lh",
        "RH": "rh",
    }
    # Primary DOFs for locomotion: coxa-pitch, femur-pitch, tibia-pitch
    PRIMARY_DOFS = [0, 3, 5]

    bid_to_idx = {bid: i for i, bid in enumerate(body_ids)}
    index_to_actuators: dict[int, list[int]] = {}

    for body_id, leg_abbrev in motor_leg_map.items():
        if body_id not in bid_to_idx:
            continue
        net_idx = bid_to_idx[body_id]
        leg_key = _LEG_NAME_MAP.get(leg_abbrev)
        if leg_key is None or leg_key not in LEG_OFFSETS:
            continue
        leg_offset = LEG_OFFSETS[leg_key]
        actuator_indices = [leg_offset + dof for dof in PRIMARY_DOFS]
        index_to_actuators[net_idx] = actuator_indices

    return index_to_actuators


def save_network_snapshot(
    body_ids: list[int],
    meta_df: pd.DataFrame,
    motor_leg_map: dict[int, str],
    sources: np.ndarray,
    targets: np.ndarray,
    weights: np.ndarray,
    output_dir: Path | None = None,
) -> Path:
    """Save network arrays and metadata to disk for offline use.

    Parameters
    ----------
    output_dir : Path, optional
        Directory to write files. Defaults to data/cache/functional_network/.

    Returns
    -------
    Path
        The output directory.
    """
    if output_dir is None:
        output_dir = _CACHE_DIR / "functional_network"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save COO connectivity
    np.savez_compressed(
        output_dir / "connectivity.npz",
        sources=sources,
        targets=targets,
        weights=weights,
    )

    # Save body IDs
    np.save(output_dir / "body_ids.npy", np.array(body_ids, dtype=np.int64))

    # Save metadata
    meta_df.to_csv(output_dir / "meta.csv", index=False)

    # Save motor leg map as CSV
    motor_map_df = pd.DataFrame([
        {"bodyId": bid, "leg": leg}
        for bid, leg in motor_leg_map.items()
    ])
    motor_map_df.to_csv(output_dir / "motor_leg_map.csv", index=False)

    print(f"[functional_selection] Network snapshot saved to {output_dir}")
    return output_dir


def load_network_snapshot(
    snapshot_dir: Path | None = None,
    n_hops: int = 1,
) -> tuple[list[int], pd.DataFrame, dict[int, str], np.ndarray, np.ndarray, np.ndarray]:
    """Load a previously saved network snapshot from disk (bypasses neuPrint).

    Parameters
    ----------
    snapshot_dir : Path, optional
        Directory containing connectivity.npz, body_ids.npy, meta.csv,
        motor_leg_map.csv. If None, defaults based on n_hops.
    n_hops : int
        Number of hops used to build the snapshot (used to select the correct
        default directory when snapshot_dir is None).

    Returns
    -------
    Same as select_locomotor_network().
    """
    if snapshot_dir is None:
        snapshot_dir = _snapshot_dir_for_hops(n_hops)
    snapshot_dir = Path(snapshot_dir)

    body_ids = list(np.load(snapshot_dir / "body_ids.npy").astype(int))
    meta_df = pd.read_csv(snapshot_dir / "meta.csv")
    motor_map_df = pd.read_csv(snapshot_dir / "motor_leg_map.csv")
    motor_leg_map = dict(zip(
        motor_map_df["bodyId"].astype(int).values,
        motor_map_df["leg"].values,
    ))

    conn = np.load(snapshot_dir / "connectivity.npz")
    sources = conn["sources"]
    targets = conn["targets"]
    weights = conn["weights"]

    return body_ids, meta_df, motor_leg_map, sources, targets, weights


def _snapshot_dir_for_hops(n_hops: int) -> Path:
    """Return the snapshot directory for a given hop count.

    n_hops=1 maps to the legacy ``functional_network`` directory so that
    existing 1-hop caches continue to work without migration.
    n_hops>1 maps to ``functional_network_<n_hops>hop``.
    """
    if n_hops == 1:
        return _CACHE_DIR / "functional_network"
    return _CACHE_DIR / f"functional_network_{n_hops}hop"


def get_or_build_network(
    motor_top_n: int = MOTOR_TOP_N_PER_LEG,
    premotor_top_n: int = PREMOTOR_TOP_N,
    force_rebuild: bool = False,
    n_hops: int = 1,
) -> tuple[list[int], pd.DataFrame, dict[int, str], np.ndarray, np.ndarray, np.ndarray]:
    """Return cached network snapshot, building it if necessary.

    On first call (or when force_rebuild=True), queries neuPrint and writes
    a snapshot. Subsequent calls load from disk instantly.

    Parameters
    ----------
    motor_top_n : int
        Top motor neurons per leg.
    premotor_top_n : int
        Top premotor neurons for hop 1.
    force_rebuild : bool
        Re-query neuPrint even if a cached snapshot exists.
    n_hops : int
        Number of upstream hops to include (1, 2, or 3).
    """
    snapshot_dir = _snapshot_dir_for_hops(n_hops)
    snap_file = snapshot_dir / "body_ids.npy"

    if not force_rebuild and snap_file.exists():
        print(f"[functional_selection] Loading cached network snapshot "
              f"({n_hops} hop(s)) from {snapshot_dir.name}...")
        return load_network_snapshot(snapshot_dir, n_hops=n_hops)

    result = select_locomotor_network(motor_top_n, premotor_top_n, n_hops=n_hops)
    body_ids, meta_df, motor_leg_map, sources, targets, weights = result
    save_network_snapshot(body_ids, meta_df, motor_leg_map, sources, targets, weights,
                          output_dir=snapshot_dir)
    return result
