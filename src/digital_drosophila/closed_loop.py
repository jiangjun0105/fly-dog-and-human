"""Closed-loop sensorimotor co-simulation: Brian2 + FlyGym bidirectional coupling.

Runs the full loop: spikes -> motor output -> body movement -> sensors -> currents -> spikes.

Usage:
    python -m digital_drosophila loop closed_loop
"""

import os
import time
from pathlib import Path

import numpy as np

# Reports directory
_PACKAGE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _PACKAGE_DIR.parent.parent
_DEFAULT_REPORTS_DIR = _PROJECT_ROOT / "reports"


def run_closed_loop():
    """Run the closed-loop sensorimotor co-simulation.

    Co-simulation architecture:
    1. Build Brian2 network with ascending + motor neurons
    2. Build FlyGym simulation
    3. In 2ms coupling steps:
       - Inject sensory currents into ascending neurons
       - Run Brian2 for 2ms
       - Decode motor neuron spikes
       - Convert to actuator positions
       - Step FlyGym for 2ms (20 physics steps)
       - Read sensors for next iteration
    4. At t=1.0s, apply perturbation (velocity impulse)
    5. Save traces and summary
    """
    print("=" * 70)
    print("Closed-Loop Sensorimotor Co-Simulation")
    print("  Brian2 spikes <-> FlyGym body (bidirectional coupling)")
    print("=" * 70)

    t_wall_start = time.time()

    # ------------------------------------------------------------------
    # Step 1: Build Brian2 network
    # ------------------------------------------------------------------
    print("\n[1/5] Building Brian2 network...")

    import brian2
    brian2.prefs.codegen.target = "numpy"

    from brian2 import Network, SpikeMonitor, Hz as brian_Hz, mV as brian_mV, ms, pA

    from .network import (
        load_sample_data,
        create_neuron_group,
        create_synapses_constrained,
        create_poisson_drive,
        create_background_drive,
    )

    adj, neurons_df = load_sample_data()
    n = adj.shape[0]

    # Identify neuron populations
    motor_neuron_indices = neurons_df[
        neurons_df["superclass"] == "vnc_motor"
    ].index.tolist()
    ascending_indices = neurons_df[
        neurons_df["superclass"] == "ascending_neuron"
    ].index.tolist()

    print(f"  Network: {n} neurons")
    print(f"  Motor neurons: {len(motor_neuron_indices)} (indices: {motor_neuron_indices})")
    print(f"  Ascending neurons: {len(ascending_indices)} (indices: {ascending_indices})")

    # Build Brian2 components
    G = create_neuron_group(n)
    S, sources, targets, weights_raw, sign_vector = create_synapses_constrained(
        G, adj, neurons_df, scale=0.6, inh_attenuation=0.5,
    )
    PG, S_input, descending_idx = create_poisson_drive(
        G, neurons_df, target_superclass="descending_neuron",
        n_sources=15, rate=10 * brian_Hz, weight=2.0 * brian_mV,
    )
    PG_bg, S_bg = create_background_drive(
        G, n, n_sources=50, rate=22 * brian_Hz, weight=1.3 * brian_mV,
    )
    M = SpikeMonitor(G)

    # Assemble into a Network for incremental run()
    net = Network(G, S, PG, S_input, PG_bg, S_bg, M)

    print(f"  Brian2 network assembled (incremental run mode)")

    # ------------------------------------------------------------------
    # Step 2: Build FlyGym simulation
    # ------------------------------------------------------------------
    print("\n[2/5] Building FlyGym simulation...")

    os.environ.setdefault("MUJOCO_GL", "egl")
    from .locomotion import build_simulation, settle_simulation
    from flygym.compose import ActuatorType

    sim, fly, model, data, neutral_ctrl, actuator_names = build_simulation()
    settle_simulation(sim, n_steps=2000)
    initial_pos = data.qpos[0:3].copy()
    print(f"  FlyGym built and settled. Initial position: {initial_pos}")

    # ------------------------------------------------------------------
    # Step 3: Set up encoder, decoder, mapping
    # ------------------------------------------------------------------
    print("\n[3/5] Setting up sensory encoder and motor decoder...")

    from .sensory_encoder import SensoryEncoder
    from .motor_adapter import SpikeRateDecoder, MotorMapping, decode_spikes_to_positions

    encoder = SensoryEncoder(
        ascending_indices, n_neurons=n, n_actuated=66,
        gain_pa=500.0, vel_gain_pa=300.0,
    )
    motor_map = MotorMapping(motor_neuron_indices)
    mapping = motor_map.get_mapping()
    decoder = SpikeRateDecoder(motor_neuron_indices, window_ms=50.0, dt_ms=2.0)

    print(f"  Sensory encoder: {encoder.n_ascending} ascending neurons")
    print(f"    {encoder.n_proprio} proprioceptive channels, {encoder.n_vel} velocity channels")
    print(f"  Motor decoder: {len(motor_neuron_indices)} motor neurons -> {len(mapping)} actuators")

    # ------------------------------------------------------------------
    # Step 4: Run co-simulation
    # ------------------------------------------------------------------
    print("\n[4/5] Running closed-loop co-simulation (2.0s)...")

    coupling_dt_ms = 2.0  # ms per coupling step
    sim_duration_s = 2.0
    n_steps = int(sim_duration_s * 1000 / coupling_dt_ms)
    perturbation_step = n_steps // 2  # at t=1.0s

    # FlyGym physics steps per coupling step
    flygym_dt_s = model.opt.timestep  # typically 0.0001s = 0.1ms
    flygym_steps_per_coupling = int(coupling_dt_ms / (flygym_dt_s * 1000))

    print(f"  Coupling dt: {coupling_dt_ms} ms")
    print(f"  Total steps: {n_steps} ({sim_duration_s}s)")
    print(f"  FlyGym sub-steps per coupling: {flygym_steps_per_coupling}")
    print(f"  Perturbation at step {perturbation_step} (t={perturbation_step * coupling_dt_ms / 1000:.1f}s)")

    # Recording arrays
    time_axis = np.zeros(n_steps)
    motor_rates_log = np.zeros(n_steps)
    sensory_mag_log = np.zeros(n_steps)
    body_pos_log = np.zeros((n_steps, 3))
    ascending_currents_log = np.zeros(n_steps)

    # Initialize sensory currents from current body state
    joint_angles = sim.get_joint_angles("nmf")
    body_vel = data.qvel[0:3].copy()
    sensory_currents = encoder.encode(joint_angles, body_vel)

    # Track spike counts for windowed decoding
    prev_spike_count = 0

    t0 = time.time()
    for step in range(n_steps):
        t_sim_ms = step * coupling_dt_ms
        time_axis[step] = t_sim_ms / 1000.0  # in seconds

        # --- 1. Inject sensory currents into ascending neurons ---
        # sensory_currents values are in Amperes (float); Brian2 G.I expects amp units
        # Reset all currents first, then set ascending neurons
        G.I = 0 * pA
        for idx in ascending_indices:
            G.I[idx] = sensory_currents[idx] * brian2.amp

        # --- 2. Run Brian2 for coupling_dt ---
        net.run(coupling_dt_ms * ms)

        # --- 3. Decode motor neuron spikes from this window ---
        # Get spikes that occurred in this window
        current_spike_count = M.num_spikes
        if current_spike_count > prev_spike_count:
            # Extract new spikes
            new_spike_indices = np.array(M.i)[prev_spike_count:current_spike_count]
            # Count which motor neurons spiked
            motor_spike_set = set(new_spike_indices) & set(motor_neuron_indices)
            decoder.update(motor_spike_set)
        else:
            decoder.update(set())
        prev_spike_count = current_spike_count

        rates = decoder.get_rates_hz()

        # --- 4. Convert to actuator positions ---
        action = decode_spikes_to_positions(
            rates, mapping, neutral_ctrl,
            baseline_hz=15.0, amplitude=0.3,
        )

        # --- 5. Step FlyGym for coupling_dt ---
        for _ in range(flygym_steps_per_coupling):
            sim.set_actuator_inputs("nmf", ActuatorType.POSITION, action)
            sim.step()

        # --- Perturbation at midpoint ---
        if step == perturbation_step:
            data.qvel[0] += 10.0  # forward push (mm/s)
            print(f"  ** Perturbation applied at t={t_sim_ms / 1000:.2f}s: "
                  f"qvel[0] += 10.0 mm/s")

        # --- 6. Read sensors for next iteration ---
        joint_angles = sim.get_joint_angles("nmf")
        body_vel = data.qvel[0:3].copy()
        sensory_currents = encoder.encode(joint_angles, body_vel)

        # --- Record ---
        mean_motor_rate = np.mean(list(rates.values())) if rates else 0.0
        motor_rates_log[step] = mean_motor_rate
        sensory_mag_log[step] = np.sum(np.abs(sensory_currents)) * 1e12  # in pA
        body_pos_log[step] = data.qpos[0:3].copy()
        ascending_currents_log[step] = np.mean(
            [sensory_currents[idx] for idx in ascending_indices]
        ) * 1e12  # in pA

        # Progress report every 250 steps
        if (step + 1) % 250 == 0:
            elapsed = time.time() - t0
            pct = (step + 1) / n_steps * 100
            print(f"  Step {step + 1}/{n_steps} ({pct:.0f}%) "
                  f"t={t_sim_ms / 1000:.2f}s | "
                  f"motor rate: {mean_motor_rate:.1f} Hz | "
                  f"sensory: {sensory_mag_log[step]:.1f} pA total | "
                  f"elapsed: {elapsed:.1f}s")

    t_sim_wall = time.time() - t0
    final_pos = data.qpos[0:3].copy()
    displacement = final_pos - initial_pos

    print(f"\n  Co-simulation completed in {t_sim_wall:.1f}s")
    print(f"  Total Brian2 spikes: {M.num_spikes}")

    # Check if runtime is acceptable
    if t_sim_wall > 120:
        print(f"  WARNING: Runtime ({t_sim_wall:.0f}s) exceeds 120s target")

    # ------------------------------------------------------------------
    # Step 5: Summary and visualization
    # ------------------------------------------------------------------
    print("\n[5/5] Summary and visualization...")

    # Summary stats
    print(f"\n  --- Results ---")
    print(f"  Simulation: {sim_duration_s}s in {n_steps} coupling steps")
    print(f"  Mean motor rate: {np.mean(motor_rates_log):.2f} Hz")
    print(f"  Mean sensory magnitude: {np.mean(sensory_mag_log):.1f} pA (total)")
    print(f"  Body displacement:")
    print(f"    Forward (x): {displacement[0]:.4f} mm")
    print(f"    Lateral (y): {displacement[1]:.4f} mm")
    print(f"    Vertical (z): {displacement[2]:.4f} mm")
    print(f"    Total: {np.linalg.norm(displacement):.4f} mm")

    # Check perturbation response
    pre_perturb = sensory_mag_log[:perturbation_step]
    post_perturb = sensory_mag_log[perturbation_step:min(perturbation_step + 50, n_steps)]
    if len(post_perturb) > 0 and np.mean(post_perturb) != np.mean(pre_perturb):
        ratio = np.mean(post_perturb) / max(np.mean(pre_perturb), 1e-10)
        print(f"\n  Perturbation response:")
        print(f"    Pre-perturbation mean sensory: {np.mean(pre_perturb):.2f} pA")
        print(f"    Post-perturbation mean sensory (50 steps): {np.mean(post_perturb):.2f} pA")
        print(f"    Ratio: {ratio:.2f}x")
    else:
        print(f"\n  Perturbation response: no measurable change (loop may be weakly coupled)")

    # Check neural activity is not constant
    rate_std = np.std(motor_rates_log)
    if rate_std > 0.1:
        print(f"  Motor rate variability (std): {rate_std:.2f} Hz - GOOD (not constant)")
    else:
        print(f"  Motor rate variability (std): {rate_std:.2f} Hz - activity is near-constant")

    # Save visualization
    reports_dir = _DEFAULT_REPORTS_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)
    outpath = reports_dir / "closed_loop_traces.png"

    _save_traces(
        time_axis, motor_rates_log, sensory_mag_log, body_pos_log,
        ascending_currents_log, perturbation_step, coupling_dt_ms, outpath,
    )
    print(f"\n  Visualization saved: {outpath}")

    # Cleanup
    sim.close()

    # Final summary
    total_wall = time.time() - t_wall_start
    print(f"\n" + "=" * 70)
    print("CLOSED-LOOP CO-SIMULATION COMPLETE")
    print("=" * 70)
    print(f"  Runtime: {total_wall:.1f}s total ({t_sim_wall:.1f}s co-simulation)")
    print(f"  Network: {n} neurons, {M.num_spikes} total spikes")
    print(f"  Motor neurons: {len(motor_neuron_indices)}, mean rate: {np.mean(motor_rates_log):.1f} Hz")
    print(f"  Ascending neurons: {len(ascending_indices)}, mean current: {np.mean(ascending_currents_log):.1f} pA")
    print(f"  Body displacement: {np.linalg.norm(displacement):.4f} mm")
    print(f"  Output: {outpath}")
    print("=" * 70)


def _save_traces(time_axis, motor_rates, sensory_mag, body_pos,
                 ascending_currents, perturb_step, coupling_dt_ms, outpath):
    """Save a multi-panel figure showing the closed-loop dynamics.

    Parameters
    ----------
    time_axis : ndarray
        Time in seconds for each coupling step.
    motor_rates : ndarray
        Mean motor neuron firing rates per step.
    sensory_mag : ndarray
        Total sensory current magnitude per step (pA).
    body_pos : ndarray
        Body position (n_steps, 3) in mm.
    ascending_currents : ndarray
        Mean ascending neuron current per step (pA).
    perturb_step : int
        Step index where perturbation was applied.
    coupling_dt_ms : float
        Coupling timestep in ms.
    outpath : Path
        Output file path.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
    perturb_time = perturb_step * coupling_dt_ms / 1000.0

    # Panel 1: Motor neuron firing rates
    ax = axes[0]
    ax.plot(time_axis, motor_rates, color="tab:red", linewidth=0.8)
    ax.axvline(perturb_time, color="gray", linestyle="--", alpha=0.7, label="Perturbation")
    ax.set_ylabel("Motor Rate (Hz)")
    ax.set_title("Closed-Loop Sensorimotor Co-Simulation")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.3)

    # Panel 2: Sensory input magnitude
    ax = axes[1]
    ax.plot(time_axis, sensory_mag, color="tab:blue", linewidth=0.8)
    ax.axvline(perturb_time, color="gray", linestyle="--", alpha=0.7)
    ax.set_ylabel("Sensory Input (pA total)")
    ax.grid(True, alpha=0.3)

    # Panel 3: Ascending neuron currents (mean)
    ax = axes[2]
    ax.plot(time_axis, ascending_currents, color="tab:green", linewidth=0.8)
    ax.axvline(perturb_time, color="gray", linestyle="--", alpha=0.7)
    ax.set_ylabel("Ascending Current (pA mean)")
    ax.grid(True, alpha=0.3)

    # Panel 4: Body position
    ax = axes[3]
    ax.plot(time_axis, body_pos[:, 0], label="Forward (x)", color="tab:blue", linewidth=0.8)
    ax.plot(time_axis, body_pos[:, 1], label="Lateral (y)", color="tab:orange", linewidth=0.8)
    ax.plot(time_axis, body_pos[:, 2], label="Vertical (z)", color="tab:green", linewidth=0.8)
    ax.axvline(perturb_time, color="gray", linestyle="--", alpha=0.7)
    ax.set_ylabel("Position (mm)")
    ax.set_xlabel("Time (s)")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(str(outpath), dpi=150, bbox_inches="tight")
    plt.close()
