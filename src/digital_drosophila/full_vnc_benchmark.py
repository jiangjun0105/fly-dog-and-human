"""Full VNC network timing benchmark.

Loads ALL VNC neurons (~25,635) and their connectivity (~31M synapses),
builds a PyGeNN GPU network, hooks it to FlyGym, and runs exactly 1 episode
(2 seconds simulated). Reports timing breakdown and network stats.

With --with-homeostasis: runs N settling episodes (homeostatic threshold
updates only, no STDP/reward) until firing rates converge to ~25 Hz, then
runs 1 measured episode.

Usage
-----
    python -m digital_drosophila learn benchmark_full_vnc
    python -m digital_drosophila learn benchmark_full_vnc --with-homeostasis
or:
    python -c "from src.digital_drosophila.full_vnc_benchmark import run_benchmark; run_benchmark()"
    python -c "from src.digital_drosophila.full_vnc_benchmark import run_benchmark; run_benchmark(with_homeostasis=True)"
"""

import os
import subprocess
import time
from pathlib import Path

import numpy as np

_PACKAGE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _PACKAGE_DIR.parent.parent

# Leg nerve constants (same as functional_selection.py)
T1_NERVES = frozenset(["ProLN", "ProAN", "DProN", "VProN", "ADMN"])
T2_NERVES = frozenset(["MesoLN", "MesoAN"])
T3_NERVES = frozenset(["MetaLN"])
ALL_LEG_NERVES = T1_NERVES | T2_NERVES | T3_NERVES

# FlyGym leg name map (uppercase -> lowercase)
_LEG_NAME_MAP = {
    "LF": "lf", "RF": "rf",
    "LM": "lm", "RM": "rm",
    "LH": "lh", "RH": "rh",
}
# Primary DOFs: coxa-pitch (0), femur-pitch (3), tibia-pitch (5)
PRIMARY_DOFS = [0, 3, 5]


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


def _gpu_memory_mb() -> str:
    """Return GPU memory usage string via nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            parts = lines[0].split(", ")
            used_mb = int(parts[0].strip())
            total_mb = int(parts[1].strip())
            return f"{used_mb} MiB / {total_mb} MiB ({100*used_mb/total_mb:.1f}%)"
    except Exception:
        pass
    return "unavailable"


def run_benchmark(
    episode_length_s: float = 2.0,
    coupling_dt_ms: float = 2.0,
    with_homeostasis: bool = False,
    n_settling_episodes: int = 10,
    eta_homeo: float = 0.005,
    target_rate_hz: float = 25.0,
):
    """Run the full VNC benchmark.

    Parameters
    ----------
    episode_length_s : float
        Length of the simulated episode in seconds.
    coupling_dt_ms : float
        Neural-body coupling timestep in milliseconds.
    with_homeostasis : bool
        If True, run ``n_settling_episodes`` warm-up episodes with homeostatic
        threshold updates before the measured episode.
    n_settling_episodes : int
        Number of settling episodes when ``with_homeostasis=True``.
    eta_homeo : float
        Homeostatic learning rate (mV per Hz of rate error per episode).
    target_rate_hz : float
        Target mean firing rate in Hz.
    """
    os.environ.setdefault("MUJOCO_GL", "egl")

    print("=" * 70)
    print("Full VNC Network Benchmark")
    print(f"  Episode length:   {episode_length_s}s")
    print(f"  Coupling dt:      {coupling_dt_ms} ms")
    if with_homeostasis:
        print(f"  Homeostasis:      ON  (eta={eta_homeo}, target={target_rate_hz} Hz, "
              f"{n_settling_episodes} settling episodes)")
    else:
        print(f"  Homeostasis:      OFF")
    print("=" * 70)

    t_total_start = time.time()

    # ------------------------------------------------------------------
    # Step 1: Load all VNC neurons
    # ------------------------------------------------------------------
    print("\n[1/5] Loading all VNC neurons from neuPrint (cached)...")
    t0 = time.time()
    from .data import connect, load_vnc_neurons, load_connectivity_sparse
    connect()
    vnc_df, _ = load_vnc_neurons()
    body_ids = tuple(int(x) for x in vnc_df["bodyId"].tolist())
    n_neurons = len(body_ids)
    t_neurons = time.time() - t0
    print(f"  Loaded {n_neurons:,} VNC neurons in {t_neurons:.1f}s")

    # ------------------------------------------------------------------
    # Step 2: Load connectivity
    # ------------------------------------------------------------------
    print(f"\n[2/5] Loading connectivity for {n_neurons:,} neurons (cached)...")
    t0 = time.time()
    sources, targets, weights = load_connectivity_sparse(body_ids)
    n_synapses = len(sources)
    t_connectivity = time.time() - t0
    print(f"  Loaded {n_synapses:,} synapses in {t_connectivity:.1f}s")

    # ------------------------------------------------------------------
    # Step 3: Build motor and ascending neuron maps
    # ------------------------------------------------------------------
    print("\n[3/5] Building neuron role maps...")
    from .locomotion import LEG_OFFSETS

    bid_to_idx = {bid: i for i, bid in enumerate(body_ids)}

    # Motor neurons: superclass == 'vnc_motor', filtered to leg nerves
    motor_all = vnc_df[vnc_df["superclass"] == "vnc_motor"].copy()
    leg_motor = motor_all[motor_all["exitNerve"].isin(ALL_LEG_NERVES)].copy()
    leg_motor = leg_motor.copy()
    leg_motor["leg"] = leg_motor.apply(
        lambda row: _assign_leg(row["exitNerve"], row.get("somaSide", "L")),
        axis=1,
    )
    leg_motor = leg_motor.dropna(subset=["leg"])

    motor_neuron_indices = [
        bid_to_idx[int(bid)]
        for bid in leg_motor["bodyId"].values
        if int(bid) in bid_to_idx
    ]
    motor_leg_map = {
        int(bid): leg
        for bid, leg in zip(leg_motor["bodyId"].values, leg_motor["leg"].values)
        if int(bid) in bid_to_idx
    }

    # Ascending neurons
    ascending_mask = vnc_df["superclass"] == "ascending_neuron"
    ascending_bids = vnc_df[ascending_mask]["bodyId"].values
    ascending_indices = [
        bid_to_idx[int(bid)] for bid in ascending_bids if int(bid) in bid_to_idx
    ]

    # Descending neurons
    descending_mask = vnc_df["superclass"] == "descending_neuron"
    descending_bids = vnc_df[descending_mask]["bodyId"].values
    descending_indices = [
        bid_to_idx[int(bid)] for bid in descending_bids if int(bid) in bid_to_idx
    ]

    print(f"  Motor neurons:     {len(motor_neuron_indices):,}")
    print(f"  Ascending neurons: {len(ascending_indices):,}")
    print(f"  Descending neurons:{len(descending_indices):,}")

    # Build motor actuator map: network_index -> list of actuator indices
    motor_actuator_map: dict[int, list[int]] = {}
    for body_id, leg_abbrev in motor_leg_map.items():
        if body_id not in bid_to_idx:
            continue
        net_idx = bid_to_idx[body_id]
        leg_key = _LEG_NAME_MAP.get(leg_abbrev)
        if leg_key is None or leg_key not in LEG_OFFSETS:
            continue
        leg_offset = LEG_OFFSETS[leg_key]
        motor_actuator_map[net_idx] = [leg_offset + dof for dof in PRIMARY_DOFS]

    # Build weights from neurotransmitter types
    from .constants import NT_SIGN_MAP
    nt_col = None
    for col in ["consensusNt", "predictedNt", "celltypePredictedNt"]:
        if col in vnc_df.columns and vnc_df[col].notna().any():
            nt_col = col
            break

    if nt_col:
        nt_series = vnc_df[nt_col].fillna("unknown")
    else:
        nt_series = ["unknown"] * n_neurons

    # Map by position in body_ids
    sign_vector = np.array([
        NT_SIGN_MAP.get(nt, 0) or 0
        for nt in nt_series
    ], dtype=np.float32)

    conf_col = "predictedNtConfidence"
    if conf_col in vnc_df.columns:
        confidence = vnc_df[conf_col].fillna(0.5).values.astype(np.float32)
    else:
        confidence = np.full(n_neurons, 0.5, dtype=np.float32)

    inh_attenuation = 0.5
    scale = 0.6
    sign_scale = np.where(sign_vector[sources] >= 0, 1.0, inh_attenuation)
    weights_raw = (
        np.log1p(weights.astype(np.float32))
        * sign_vector[sources]
        * confidence[sources]
        * sign_scale
        * scale
    ).astype(np.float32)

    thresholds_mV = np.full(n_neurons, -50.0, dtype=np.float32)

    # ------------------------------------------------------------------
    # Step 4: Build PyGeNN GPU backend (CUDA compilation)
    # ------------------------------------------------------------------
    print(f"\n[4/5] Building PyGeNN GPU backend for {n_neurons:,} neurons, "
          f"{n_synapses:,} synapses...")
    print("  (CUDA compilation may take several minutes on first run)")
    print(f"  GPU memory BEFORE build: {_gpu_memory_mb()}")
    t0 = time.time()

    import scipy.sparse as sp
    from .gpu_backend import PyGeNNBackend

    adj_sparse = sp.coo_matrix(
        (np.ones(n_synapses, dtype=np.float32), (sources, targets)),
        shape=(n_neurons, n_neurons),
    )

    gpu_backend = PyGeNNBackend(
        adj_sparse,
        weights_raw,
        thresholds_mV,
        motor_neuron_indices,
        ascending_indices,
        dt_ms=0.1,
        coupling_dt_ms=coupling_dt_ms,
        tau_stdp_ms=20.0,
        tau_eligibility_ms=1000.0,
    )

    try:
        gpu_backend.build()
    except Exception as e:
        print(f"\n  ERROR during GPU build: {e}")
        print("\n  RESULT: GPU build failed — see error above.")
        print(f"  Network size: {n_neurons:,} neurons, {n_synapses:,} synapses")
        return

    t_build = time.time() - t0
    print(f"  GPU build + CUDA compile: {t_build:.1f}s")
    print(f"  GPU memory AFTER build:  {_gpu_memory_mb()}")

    # ------------------------------------------------------------------
    # Step 5: Build FlyGym body
    # ------------------------------------------------------------------
    print("\n[5/5] Building FlyGym body simulation...")
    t0 = time.time()
    from .locomotion import build_simulation, settle_simulation
    from .sensory_encoder import SensoryEncoder
    from .motor_adapter import SpikeRateDecoder

    sim, fly, model, data, neutral_ctrl, actuator_names = build_simulation()
    settle_simulation(sim, n_steps=2000)

    flygym_dt_s = model.opt.timestep
    flygym_steps_per_coupling = int(coupling_dt_ms / (flygym_dt_s * 1000))

    sensory_gain_pa = 500e-12 / 1e-12  # 500 pA as base unit
    encoder = SensoryEncoder(
        ascending_indices,
        n_neurons=n_neurons,
        n_actuated=66,
        gain_pa=sensory_gain_pa,
        vel_gain_pa=sensory_gain_pa * 0.6,
    )
    decoder = SpikeRateDecoder(
        motor_neuron_indices,
        window_ms=50.0,
        dt_ms=coupling_dt_ms,
    )

    t_body = time.time() - t0
    print(f"  FlyGym body built in {t_body:.1f}s")

    # ------------------------------------------------------------------
    # Shared setup: background currents and initial state
    # ------------------------------------------------------------------
    import mujoco
    from flygym.compose import ActuatorType

    # Background current: 180 pA for all, +30 pA for descending
    bg_current_pA = 180.0
    descending_extra_pA = 30.0
    gpu_bg_currents = np.full(n_neurons, bg_current_pA, dtype=np.float32)
    if descending_indices:
        gpu_bg_currents[descending_indices] += descending_extra_pA

    # Snapshot initial body state for resets
    initial_qpos = data.qpos.copy()
    initial_qvel = data.qvel.copy()

    motor_gain = 0.3
    baseline_hz = 15.0
    n_steps = int(episode_length_s * 1000 / coupling_dt_ms)

    # Working copy of thresholds — updated by homeostasis across episodes
    current_thresholds_mV = thresholds_mV.copy()

    def _reset_episode():
        """Reset GPU network and body for a new episode."""
        from .motor_adapter import SpikeRateDecoder as _SRD
        gpu_backend.reset(weights_raw, current_thresholds_mV)
        burn_in_steps = int(500.0 / coupling_dt_ms)
        for _ in range(burn_in_steps):
            gpu_backend.step(gpu_bg_currents)
        gpu_backend._spike_counts[:] = 0

        data.qpos[:] = initial_qpos
        data.qvel[:] = initial_qvel
        data.ctrl[:] = neutral_ctrl
        mujoco.mj_forward(model, data)

        dec = _SRD(motor_neuron_indices, window_ms=50.0, dt_ms=coupling_dt_ms)
        ep_start = data.qpos[0:3].copy()
        ja = sim.get_joint_angles("nmf")
        bv = data.qvel[0:3].copy()
        sc = encoder.encode(ja, bv)
        return dec, ep_start, sc

    def _run_one_episode(decoder_ep, sensory_currents_ep):
        """Run one episode step loop; return final sensory currents."""
        for _step in range(n_steps):
            sensory_pA = sensory_currents_ep * 1e12
            combined = sensory_pA + gpu_bg_currents
            motor_spikes = gpu_backend.step(combined)

            decoder_ep.update(motor_spikes)
            ep_rates = decoder_ep.get_rates_hz()

            action = neutral_ctrl.copy()
            actuator_offsets: dict[int, float] = {}
            actuator_counts: dict[int, int] = {}
            for net_idx, actuator_list in motor_actuator_map.items():
                rate = ep_rates.get(net_idx, 0.0)
                offset = float(np.clip(
                    (rate - baseline_hz) / max(baseline_hz, 1.0) * motor_gain,
                    -motor_gain, motor_gain,
                ))
                for act_idx in actuator_list:
                    actuator_offsets[act_idx] = actuator_offsets.get(act_idx, 0.0) + offset
                    actuator_counts[act_idx] = actuator_counts.get(act_idx, 0) + 1
            for act_idx, total_offset in actuator_offsets.items():
                action[act_idx] += total_offset / actuator_counts[act_idx]

            for _ in range(flygym_steps_per_coupling):
                sim.set_actuator_inputs("nmf", ActuatorType.POSITION, action)
                sim.step()

            ja = sim.get_joint_angles("nmf")
            bv = data.qvel[0:3].copy()
            sensory_currents_ep = encoder.encode(ja, bv)
        return sensory_currents_ep

    # ------------------------------------------------------------------
    # Homeostatic settling phase (optional)
    # ------------------------------------------------------------------
    t_settling = 0.0
    settling_rates_history = []

    if with_homeostasis:
        print(f"\n[Homeostasis] Running {n_settling_episodes} settling episodes "
              f"(eta={eta_homeo}, target={target_rate_hz} Hz)...")
        t_settle_start = time.time()

        for ep_i in range(n_settling_episodes):
            dec_ep, ep_start_pos_s, sc_ep = _reset_episode()
            _run_one_episode(dec_ep, sc_ep)

            # Compute mean firing rate for this episode
            spike_counts_ep = gpu_backend.get_spike_counts()
            rates_ep = spike_counts_ep.astype(float) / episode_length_s
            mean_rate_ep = float(np.mean(rates_ep))
            settling_rates_history.append(mean_rate_ep)

            # Homeostatic threshold update (clipped to [−70, −30] mV)
            rate_deviation = rates_ep - target_rate_hz
            current_thresholds_mV = np.clip(
                current_thresholds_mV + eta_homeo * rate_deviation,
                -70.0, -30.0,
            )

            th_mean = float(np.mean(current_thresholds_mV))
            th_std = float(np.std(current_thresholds_mV))
            print(f"  Settling ep {ep_i + 1}/{n_settling_episodes}: "
                  f"mean rate={mean_rate_ep:.1f} Hz  "
                  f"threshold mean={th_mean:.2f} mV  std={th_std:.3f} mV")

        t_settling = time.time() - t_settle_start
        print(f"  Settling complete in {t_settling:.1f}s  "
              f"(final mean rate={settling_rates_history[-1]:.1f} Hz)")

    # ------------------------------------------------------------------
    # Episode reset (burn-in) for the measured episode
    # ------------------------------------------------------------------
    print("\n[Episode] Resetting network (500ms burn-in)...")
    t0 = time.time()

    decoder, episode_start_pos, sensory_currents = _reset_episode()

    t_reset = time.time() - t0
    print(f"  Burn-in complete in {t_reset:.1f}s")

    # ------------------------------------------------------------------
    # Run 1 measured episode
    # ------------------------------------------------------------------
    print(f"\n[Episode] Running 1 episode ({episode_length_s}s simulated)...")

    t_episode_start = time.time()
    _run_one_episode(decoder, sensory_currents)
    t_episode = time.time() - t_episode_start

    # ------------------------------------------------------------------
    # Compute metrics
    # ------------------------------------------------------------------
    spike_counts = gpu_backend.get_spike_counts()
    mean_rate = float(np.mean(spike_counts) / episode_length_s)
    active_neurons = int(np.sum(spike_counts > 0))
    total_spikes = int(np.sum(spike_counts))

    current_pos = data.qpos[0:3].copy()
    forward_displacement_mm = float(current_pos[0] - episode_start_pos[0])

    gpu_mem_after = _gpu_memory_mb()

    t_total = time.time() - t_total_start

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("FULL VNC BENCHMARK RESULTS")
    if with_homeostasis:
        print("  (with homeostatic plasticity settling)")
    print("=" * 70)
    print(f"\n  Network:")
    print(f"    Total neurons:        {n_neurons:,}")
    print(f"    Total synapses:       {n_synapses:,}")
    print(f"    Motor neurons:        {len(motor_neuron_indices):,}")
    print(f"    Ascending neurons:    {len(ascending_indices):,}")
    print(f"    Descending neurons:   {len(descending_indices):,}")
    print(f"\n  Timing:")
    print(f"    Neuron load time:     {t_neurons:.1f}s")
    print(f"    Connectivity load:    {t_connectivity:.1f}s")
    print(f"    GPU build (CUDA):     {t_build:.1f}s")
    print(f"    FlyGym body build:    {t_body:.1f}s")
    if with_homeostasis:
        print(f"    Settling ({n_settling_episodes} eps):   {t_settling:.1f}s")
    print(f"    Burn-in (500ms):      {t_reset:.1f}s")
    print(f"    Episode wall time:    {t_episode:.1f}s  *** KEY NUMBER ***")
    print(f"    Total wall time:      {t_total:.1f}s")
    print(f"\n  Episode stats (measured episode):")
    print(f"    Simulated time:       {episode_length_s}s")
    print(f"    Real-time factor:     {episode_length_s / t_episode:.3f}x "
          f"({'faster' if episode_length_s / t_episode > 1 else 'slower'} than real-time)")
    print(f"    Total spikes:         {total_spikes:,}")
    print(f"    Active neurons:       {active_neurons:,} / {n_neurons:,} "
          f"({100*active_neurons/n_neurons:.1f}%)")
    print(f"    Mean firing rate:     {mean_rate:.2f} Hz")
    print(f"    Forward displacement: {forward_displacement_mm:.4f} mm")
    if with_homeostasis and settling_rates_history:
        print(f"\n  Homeostasis settling:")
        print(f"    Initial rate:         {settling_rates_history[0]:.1f} Hz")
        print(f"    Final rate:           {settling_rates_history[-1]:.1f} Hz")
        print(f"    Target rate:          {target_rate_hz:.1f} Hz")
        final_th_mean = float(np.mean(current_thresholds_mV))
        final_th_std = float(np.std(current_thresholds_mV))
        print(f"    Final threshold:      mean={final_th_mean:.2f} mV  "
              f"std={final_th_std:.3f} mV")
        print(f"    Rate convergence:     "
              f"{'YES' if abs(settling_rates_history[-1] - target_rate_hz) < 5 else 'NO'} "
              f"(|{settling_rates_history[-1]:.1f} - {target_rate_hz:.1f}| = "
              f"{abs(settling_rates_history[-1] - target_rate_hz):.1f} Hz)")
    print(f"\n  GPU memory after build: {gpu_mem_after}")
    print(f"\n  Projections:")
    print(f"    50 episodes:          {50 * t_episode:.0f}s "
          f"({50 * t_episode / 3600:.1f}h)")
    print(f"    100 episodes:         {100 * t_episode:.0f}s "
          f"({100 * t_episode / 3600:.1f}h)")
    print("=" * 70)

    # Cleanup
    try:
        gpu_backend.close()
        sim.close()
    except Exception:
        pass

    return {
        "n_neurons": n_neurons,
        "n_synapses": n_synapses,
        "t_build_s": t_build,
        "t_settling_s": t_settling,
        "t_episode_s": t_episode,
        "t_total_s": t_total,
        "mean_rate_hz": mean_rate,
        "active_neurons": active_neurons,
        "forward_displacement_mm": forward_displacement_mm,
        "gpu_memory": gpu_mem_after,
        "settling_rates_history": settling_rates_history,
        "final_thresholds_mV": current_thresholds_mV if with_homeostasis else None,
    }
