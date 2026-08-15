"""Motor output adapter: decode Brian2 motor neuron spikes to FlyGym actuator positions.

Bridges the spiking neural network (Epic 1) with the biomechanical body (Epic 2)
in an open-loop configuration: run Brian2, collect spikes, replay against FlyGym.

Usage:
    python -m digital_drosophila loop motor_test
"""

import os
import time
from collections import deque
from pathlib import Path

import numpy as np

# Reports directory
_PACKAGE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _PACKAGE_DIR.parent.parent
_DEFAULT_REPORTS_DIR = _PROJECT_ROOT / "reports"


# ---------------------------------------------------------------------------
# Spike Rate Decoder
# ---------------------------------------------------------------------------


class SpikeRateDecoder:
    """Decode spike trains into continuous rate signals using a sliding window.

    Parameters
    ----------
    neuron_indices : list of int
        Indices of neurons to track.
    window_ms : float
        Sliding window duration in milliseconds.
    dt_ms : float
        Simulation timestep in milliseconds (Brian2 default: 0.1 ms).
    """

    def __init__(self, neuron_indices, window_ms=50.0, dt_ms=0.1):
        self.neuron_indices = list(neuron_indices)
        self.window_ms = window_ms
        self.dt_ms = dt_ms
        self.window_size = int(window_ms / dt_ms)
        # Each buffer stores 1/0 per timestep (spiked or not)
        self.spike_buffer = {
            idx: deque(maxlen=self.window_size) for idx in self.neuron_indices
        }

    def update(self, spike_indices):
        """Record which neurons spiked at this timestep.

        Parameters
        ----------
        spike_indices : set or array-like
            Neuron indices that spiked at the current timestep.
        """
        spike_set = set(spike_indices)
        for idx in self.neuron_indices:
            self.spike_buffer[idx].append(1 if idx in spike_set else 0)

    def get_rates_hz(self):
        """Get instantaneous firing rates in Hz for each tracked neuron.

        Returns
        -------
        dict
            Mapping of neuron_index -> firing rate in Hz.
        """
        rates = {}
        for idx in self.neuron_indices:
            buf = self.spike_buffer[idx]
            if len(buf) == 0:
                rates[idx] = 0.0
            else:
                # Count spikes in window, convert to Hz
                spike_count = sum(buf)
                window_duration_s = len(buf) * self.dt_ms / 1000.0
                rates[idx] = spike_count / window_duration_s
        return rates


# ---------------------------------------------------------------------------
# Motor Mapping
# ---------------------------------------------------------------------------


class MotorMapping:
    """Maps motor neuron indices to FlyGym actuator indices.

    Uses a coarse round-robin assignment: 18 motor neurons distributed
    across 6 legs x 3 primary DOFs (coxa-pitch, femur-pitch, tibia-pitch).

    Parameters
    ----------
    motor_neuron_indices : list of int
        Indices of motor neurons in the Brian2 network.
    """

    def __init__(self, motor_neuron_indices):
        from .locomotion import LEG_OFFSETS, LEG_NAMES

        self.motor_neuron_indices = list(motor_neuron_indices)
        # Primary DOFs per leg: coxa-pitch (0), femur-pitch (3), tibia-pitch (5)
        primary_dofs = [0, 3, 5]

        self.mapping = {}  # motor_neuron_idx -> actuator_idx
        for i, mn_idx in enumerate(self.motor_neuron_indices):
            leg_idx = i % 6
            dof = primary_dofs[(i // 6) % 3]
            actuator_idx = LEG_OFFSETS[LEG_NAMES[leg_idx]] + dof
            self.mapping[mn_idx] = actuator_idx

    def get_mapping(self):
        """Return the motor neuron -> actuator index mapping dict."""
        return self.mapping.copy()


# ---------------------------------------------------------------------------
# Spike-to-position conversion
# ---------------------------------------------------------------------------


def decode_spikes_to_positions(rates_hz, mapping, neutral_ctrl,
                               baseline_hz=15.0, amplitude=0.3):
    """Convert motor neuron firing rates to actuator position commands.

    Parameters
    ----------
    rates_hz : dict
        Motor neuron index -> firing rate in Hz.
    mapping : dict
        Motor neuron index -> actuator index.
    neutral_ctrl : ndarray
        Neutral standing pose (66,) control vector.
    baseline_hz : float
        Baseline firing rate (zero offset).
    amplitude : float
        Maximum position offset in radians.

    Returns
    -------
    action : ndarray
        Actuator position commands (66,).
    """
    action = neutral_ctrl.copy()
    for mn_idx, actuator_idx in mapping.items():
        rate = rates_hz.get(mn_idx, 0.0)
        # Normalize around baseline: (rate - baseline) / baseline * amplitude
        offset = (rate - baseline_hz) / max(baseline_hz, 1.0) * amplitude
        # Clamp to [-amplitude, +amplitude]
        offset = np.clip(offset, -amplitude, amplitude)
        action[actuator_idx] += offset
    return action


# ---------------------------------------------------------------------------
# Main entry point: run_motor_test
# ---------------------------------------------------------------------------


def run_motor_test():
    """Run the open-loop motor test: Brian2 spikes drive FlyGym body.

    Two-pass approach:
    1. Run Brian2 constrained simulation for 2 seconds, collect all spikes.
    2. Replay spikes against FlyGym: decode motor neuron activity in 2ms chunks,
       convert to actuator positions, step FlyGym.
    """
    print("=" * 70)
    print("Motor Output Adapter: Brian2 spikes -> FlyGym actuator positions")
    print("=" * 70)

    # ------------------------------------------------------------------
    # PASS 1: Run Brian2 constrained simulation
    # ------------------------------------------------------------------
    print("\n[1/4] Running Brian2 constrained simulation (2 seconds)...")
    t0 = time.time()

    from brian2 import SpikeMonitor, run, second, Hz as brian_Hz, mV as brian_mV, prefs, ms

    # MUST set codegen target before creating any Brian2 objects
    prefs.codegen.target = "numpy"

    from .network import (
        load_sample_data,
        create_neuron_group,
        create_synapses_constrained,
        create_poisson_drive,
        create_background_drive,
    )

    # Load data and identify motor neurons
    adj, neurons_df = load_sample_data()
    n = adj.shape[0]
    motor_neuron_indices = neurons_df[
        neurons_df["superclass"] == "vnc_motor"
    ].index.tolist()

    print(f"  Loaded {n}-neuron network with {len(motor_neuron_indices)} motor neurons")
    print(f"  Motor neuron indices: {motor_neuron_indices}")

    # Build network (same as run_constrained)
    G = create_neuron_group(n)
    S, sources, targets, weights_raw, sign_vector = create_synapses_constrained(
        G, adj, neurons_df, scale=0.6, inh_attenuation=0.5,
    )
    PG, S_input, descending_idx = create_poisson_drive(
        G, neurons_df, target_superclass="descending_neuron",
        n_sources=15, rate=10 * brian_Hz, weight=2.0 * brian_mV,
    )
    PG_bg, S_bg = create_background_drive(G, n, n_sources=50, rate=22 * brian_Hz, weight=1.3 * brian_mV)

    # Monitor all spikes
    M = SpikeMonitor(G)

    # Run for 2 seconds
    sim_duration = 2.0
    run(sim_duration * second)
    t_brian2 = time.time() - t0

    # Extract spike data
    spike_times_ms = np.array(M.t / ms)  # in milliseconds
    spike_indices = np.array(M.i)
    total_spikes = len(spike_times_ms)

    # Motor neuron spike stats
    motor_mask = np.isin(spike_indices, motor_neuron_indices)
    motor_spikes = motor_mask.sum()
    motor_rate = motor_spikes / (len(motor_neuron_indices) * sim_duration)

    print(f"  Brian2 simulation completed in {t_brian2:.1f}s")
    print(f"  Total spikes: {total_spikes}")
    print(f"  Motor neuron spikes: {motor_spikes} "
          f"(mean rate: {motor_rate:.1f} Hz)")

    # ------------------------------------------------------------------
    # PASS 2: Replay spikes against FlyGym
    # ------------------------------------------------------------------
    print("\n[2/4] Setting up FlyGym simulation...")

    # Import FlyGym (MUJOCO_GL already set at module level via locomotion.py)
    os.environ.setdefault("MUJOCO_GL", "egl")
    from .locomotion import build_simulation, settle_simulation, LEG_OFFSETS, LEG_NAMES
    from flygym.compose import ActuatorType

    t0 = time.time()
    sim, fly, model, data, neutral_ctrl, actuator_names = build_simulation()
    settle_simulation(sim, n_steps=2000)
    initial_pos = data.qpos[0:3].copy()
    print(f"  FlyGym built and settled in {time.time() - t0:.1f}s")
    print(f"  Initial position: {initial_pos}")

    # Set up motor mapping and decoder
    motor_map = MotorMapping(motor_neuron_indices)
    mapping = motor_map.get_mapping()
    decoder = SpikeRateDecoder(motor_neuron_indices, window_ms=50.0, dt_ms=0.1)

    print(f"\n  Motor neuron -> Actuator mapping:")
    for mn_idx, act_idx in sorted(mapping.items()):
        leg_idx = act_idx // 11
        dof_idx = act_idx % 11
        from .locomotion import LEG_DOF_NAMES
        print(f"    MN[{mn_idx:2d}] -> actuator[{act_idx:2d}] "
              f"({LEG_NAMES[leg_idx]} {LEG_DOF_NAMES[dof_idx]})")

    # Replay: step through simulation in 2ms chunks
    print("\n[3/4] Replaying spikes against FlyGym body...")
    t0 = time.time()

    chunk_ms = 2.0  # decode window per FlyGym step
    brian2_dt_ms = 0.1
    n_chunks = int(sim_duration * 1000 / chunk_ms)  # 1000 chunks for 2s

    # Pre-bin spikes by timestep for efficient lookup
    # Each Brian2 timestep is 0.1ms, so for each chunk of 2ms we need 20 timesteps
    steps_per_chunk = int(chunk_ms / brian2_dt_ms)

    # Collect frames for visualization
    import mujoco
    renderer = mujoco.Renderer(model, height=360, width=480)
    frame_interval = n_chunks // 6
    frames = []

    # Track positions over time
    positions = []

    for chunk_idx in range(n_chunks):
        t_start_ms = chunk_idx * chunk_ms
        t_end_ms = (chunk_idx + 1) * chunk_ms

        # Find spikes in this time window
        mask = (spike_times_ms >= t_start_ms) & (spike_times_ms < t_end_ms)
        chunk_spike_indices = spike_indices[mask]
        chunk_spike_times = spike_times_ms[mask]

        # Update decoder with each timestep in this chunk
        # Group spikes by their timestep within the chunk
        for step in range(steps_per_chunk):
            step_t_start = t_start_ms + step * brian2_dt_ms
            step_t_end = step_t_start + brian2_dt_ms
            step_mask = (chunk_spike_times >= step_t_start) & (chunk_spike_times < step_t_end)
            step_spikes = chunk_spike_indices[step_mask]
            decoder.update(step_spikes)

        # Decode rates and compute actuator positions
        rates = decoder.get_rates_hz()
        action = decode_spikes_to_positions(
            rates, mapping, neutral_ctrl,
            baseline_hz=15.0, amplitude=0.3
        )

        # Step FlyGym
        sim.set_actuator_inputs("nmf", ActuatorType.POSITION, action)
        sim.step()

        # Record position
        positions.append(data.qpos[0:3].copy())

        # Capture frames
        if chunk_idx % frame_interval == 0 and len(frames) < 6:
            renderer.update_scene(data, camera="nmf/trackcam")
            frames.append(renderer.render().copy())

    renderer.close()
    t_replay = time.time() - t0

    final_pos = data.qpos[0:3].copy()
    displacement = final_pos - initial_pos
    positions = np.array(positions)

    print(f"  Replay completed in {t_replay:.1f}s ({n_chunks} FlyGym steps)")
    print(f"\n  Displacement stats:")
    print(f"    Forward (x): {displacement[0]:.3f} mm")
    print(f"    Lateral (y): {displacement[1]:.3f} mm")
    print(f"    Vertical (z): {displacement[2]:.3f} mm")
    print(f"    Total: {np.linalg.norm(displacement):.3f} mm")

    # Check non-zero displacement
    total_disp = np.linalg.norm(displacement)
    if total_disp > 0.001:
        print(f"\n  SUCCESS: Fly moved {total_disp:.3f} mm driven by neural activity")
    else:
        print(f"\n  WARNING: Very small displacement ({total_disp:.6f} mm)")

    # ------------------------------------------------------------------
    # Control test: no spikes -> no movement
    # ------------------------------------------------------------------
    print("\n  Control test (no spikes)...")
    sim2, fly2, model2, data2, neutral_ctrl2, _ = build_simulation()
    settle_simulation(sim2, n_steps=2000)
    ctrl_initial = data2.qpos[0:3].copy()

    # Run same number of steps with neutral control only
    for _ in range(n_chunks):
        sim2.set_actuator_inputs("nmf", ActuatorType.POSITION, neutral_ctrl2)
        sim2.step()

    ctrl_final = data2.qpos[0:3].copy()
    ctrl_disp = np.linalg.norm(ctrl_final - ctrl_initial)
    sim2.close()
    print(f"    Control displacement: {ctrl_disp:.6f} mm")
    print(f"    Neural-driven displacement: {total_disp:.3f} mm")
    if total_disp > ctrl_disp * 2:
        print(f"    PASS: Neural activity produces significantly more movement")
    else:
        print(f"    NOTE: Neural-driven displacement is small relative to control drift")

    # ------------------------------------------------------------------
    # Visualization
    # ------------------------------------------------------------------
    print("\n[4/4] Saving visualization...")
    reports_dir = _DEFAULT_REPORTS_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)
    outpath = reports_dir / "motor_test_strip.png"

    if frames:
        _save_motor_test_strip(frames, positions, outpath, sim_duration)
        print(f"  Saved: {outpath}")
    else:
        print("  WARNING: No frames captured")

    # Cleanup
    sim.close()

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Brian2: {n} neurons, {sim_duration}s, {total_spikes} total spikes")
    print(f"  Motor neurons: {len(motor_neuron_indices)}, mean rate: {motor_rate:.1f} Hz")
    print(f"  FlyGym: {n_chunks} steps at {chunk_ms}ms interval")
    print(f"  Displacement: forward={displacement[0]:.3f} mm, "
          f"lateral={displacement[1]:.3f} mm, vertical={displacement[2]:.3f} mm")
    print(f"  Total displacement: {total_disp:.3f} mm")
    print(f"  Runtime: Brian2={t_brian2:.1f}s, FlyGym replay={t_replay:.1f}s")
    print(f"  Visualization: {outpath}")
    print("=" * 70)


def _save_motor_test_strip(frames, positions, outpath, duration_s):
    """Save a visualization strip showing fly movement and trajectory.

    Parameters
    ----------
    frames : list of ndarray
        Rendered frames from the simulation.
    positions : ndarray
        Body positions over time (n_steps, 3).
    outpath : Path
        Output file path.
    duration_s : float
        Total simulation duration in seconds.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n_frames = len(frames)
    fig, axes = plt.subplots(2, n_frames, figsize=(4 * n_frames, 6),
                             gridspec_kw={"height_ratios": [2, 1]})

    if n_frames == 1:
        axes = axes.reshape(2, 1)

    # Top row: rendered frames
    for i in range(n_frames):
        ax = axes[0, i]
        ax.imshow(frames[i])
        t = i * duration_s / n_frames
        ax.set_title(f"t={t:.2f}s", fontsize=10)
        ax.axis("off")

    # Bottom row: XY trajectory in a single wide panel
    # Merge bottom axes into one
    for i in range(n_frames):
        axes[1, i].remove()

    ax_traj = fig.add_subplot(2, 1, 2)
    time_axis = np.linspace(0, duration_s, len(positions))
    ax_traj.plot(time_axis, positions[:, 0], label="Forward (x)", color="tab:blue")
    ax_traj.plot(time_axis, positions[:, 1], label="Lateral (y)", color="tab:orange")
    ax_traj.plot(time_axis, positions[:, 2], label="Vertical (z)", color="tab:green")
    ax_traj.set_xlabel("Time (s)")
    ax_traj.set_ylabel("Position (mm)")
    ax_traj.set_title("Body position over time (neurally driven)")
    ax_traj.legend(loc="upper left", fontsize=8)
    ax_traj.grid(True, alpha=0.3)

    plt.suptitle("Motor Test: Brian2 spikes -> FlyGym actuator positions",
                 fontsize=12, y=0.98)
    plt.tight_layout()
    plt.savefig(str(outpath), dpi=150, bbox_inches="tight")
    plt.close()
