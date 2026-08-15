"""Episode-based co-simulation harness: wraps Brian2 + FlyGym into a reusable API.

Provides the CoSimulation class with reset/step/get_metrics/close methods,
designed to serve as the training environment for Epic 4 (learning).

Usage:
    python -m digital_drosophila loop episode_demo

    from digital_drosophila.loop import CoSimulation

    sim = CoSimulation(episode_length_s=2.0)
    for ep in range(3):
        sim.reset()
        while not sim.done:
            sim.step()
        print(f"Episode {ep}: {sim.get_metrics()}")
    sim.close()
"""

import os
import time
from pathlib import Path

import numpy as np

# Reports directory
_PACKAGE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _PACKAGE_DIR.parent.parent
_DEFAULT_REPORTS_DIR = _PROJECT_ROOT / "reports"


class CoSimulation:
    """Episode-based co-simulation harness coupling Brian2 SNN with FlyGym body.

    Parameters
    ----------
    episode_length_s : float
        Duration of each episode in seconds.
    coupling_dt_ms : float
        Coupling timestep between neural and body simulators in milliseconds.
    motor_gain : float
        Amplitude of motor neuron rate-to-position conversion (radians).
    sensory_gain : float
        Gain for sensory encoding in Amperes (converted to pA for SensoryEncoder).
    """

    def __init__(self, episode_length_s=2.0, coupling_dt_ms=2.0,
                 motor_gain=0.3, sensory_gain=500e-12):
        self.episode_length_s = episode_length_s
        self.coupling_dt_ms = coupling_dt_ms
        self.motor_gain = motor_gain
        self.sensory_gain = sensory_gain

        # Set env vars before importing heavy dependencies
        os.environ.setdefault("MUJOCO_GL", "egl")

        # State
        self._elapsed_s = 0.0
        self._metrics_log = []
        self._motor_rates_log = []
        self._sensory_mag_log = []
        self._body_pos_log = []
        self._total_spikes_start = 0

        # Build everything
        self._build()

    def _build(self):
        """Build both simulators and all adapters."""
        import brian2
        brian2.prefs.codegen.target = "numpy"

        from brian2 import Network, SpikeMonitor, Hz as brian_Hz, mV as brian_mV

        from .network import (
            load_sample_data,
            create_neuron_group,
            create_synapses_constrained,
            create_poisson_drive,
            create_background_drive,
        )
        from .locomotion import build_simulation, settle_simulation
        from .sensory_encoder import SensoryEncoder
        from .motor_adapter import SpikeRateDecoder, MotorMapping

        # --- Brian2 network ---
        adj, neurons_df = load_sample_data()
        self._n_neurons = adj.shape[0]

        self._motor_neuron_indices = neurons_df[
            neurons_df["superclass"] == "vnc_motor"
        ].index.tolist()
        self._ascending_indices = neurons_df[
            neurons_df["superclass"] == "ascending_neuron"
        ].index.tolist()

        G = create_neuron_group(self._n_neurons)
        S, _, _, _, _ = create_synapses_constrained(
            G, adj, neurons_df, scale=0.6, inh_attenuation=0.5,
        )
        PG, S_input, _ = create_poisson_drive(
            G, neurons_df, target_superclass="descending_neuron",
            n_sources=15, rate=10 * brian_Hz, weight=2.0 * brian_mV,
        )
        PG_bg, S_bg = create_background_drive(
            G, self._n_neurons, n_sources=50, rate=22 * brian_Hz, weight=1.3 * brian_mV,
        )
        M = SpikeMonitor(G)

        self._net = Network(G, S, PG, S_input, PG_bg, S_bg, M)
        self._G = G
        self._M = M

        # Store initial state for fast reset
        self._net.store("initial")

        # --- FlyGym body ---
        sim, fly, model, data, neutral_ctrl, actuator_names = build_simulation()
        settle_simulation(sim, n_steps=2000)

        self._sim = sim
        self._fly = fly
        self._model = model
        self._data = data
        self._neutral_ctrl = neutral_ctrl

        # Save initial body state for reset
        self._initial_qpos = data.qpos.copy()
        self._initial_qvel = data.qvel.copy()

        # FlyGym physics steps per coupling step
        flygym_dt_s = model.opt.timestep
        self._flygym_steps_per_coupling = int(
            self.coupling_dt_ms / (flygym_dt_s * 1000)
        )

        # --- Adapters ---
        # Convert sensory_gain from Amperes to pA for SensoryEncoder
        sensory_gain_pa = self.sensory_gain / 1e-12
        self.encoder = SensoryEncoder(
            self._ascending_indices, n_neurons=self._n_neurons, n_actuated=66,
            gain_pa=sensory_gain_pa, vel_gain_pa=sensory_gain_pa * 0.6,
        )
        self.decoder = SpikeRateDecoder(
            self._motor_neuron_indices, window_ms=50.0, dt_ms=self.coupling_dt_ms,
        )
        motor_map = MotorMapping(self._motor_neuron_indices)
        self._mapping = motor_map.get_mapping()

        self._built = True

    def reset(self):
        """Reset body to standing pose and run 500ms neural burn-in.

        After reset, elapsed time is 0 and the simulation is ready for step().
        """
        from brian2 import ms as brian_ms, pA

        # Reset Brian2 network to initial state
        self._net.restore("initial")

        # Reset body to initial settled pose
        self._data.qpos[:] = self._initial_qpos
        self._data.qvel[:] = self._initial_qvel
        self._data.ctrl[:] = self._neutral_ctrl
        import mujoco
        mujoco.mj_forward(self._model, self._data)

        # Reset decoder
        from .motor_adapter import SpikeRateDecoder
        self.decoder = SpikeRateDecoder(
            self._motor_neuron_indices, window_ms=50.0, dt_ms=self.coupling_dt_ms,
        )

        # Run 500ms neural burn-in (no body coupling)
        burn_in_ms = 500.0
        self._G.I = 0 * pA
        self._net.run(burn_in_ms * brian_ms)

        # Record starting spike count (for episode spike counting)
        self._total_spikes_start = self._M.num_spikes

        # Reset state tracking
        self._elapsed_s = 0.0
        self._metrics_log = []
        self._motor_rates_log = []
        self._sensory_mag_log = []
        self._body_pos_log = []

        # Record initial position for displacement calculation
        self._episode_start_pos = self._data.qpos[0:3].copy()

        # Initialize sensory currents from current body state
        joint_angles = self._sim.get_joint_angles("nmf")
        body_vel = self._data.qvel[0:3].copy()
        self._sensory_currents = self.encoder.encode(joint_angles, body_vel)

        # Track prev spike count for windowed decoding
        self._prev_spike_count = self._M.num_spikes

    def step(self):
        """Advance one coupling step (coupling_dt_ms).

        Returns
        -------
        done : bool
            True when elapsed time >= episode_length_s.
        """
        import brian2
        from brian2 import ms as brian_ms, pA
        from flygym.compose import ActuatorType

        # 1. Inject sensory currents into ascending neurons
        self._G.I = 0 * pA
        for idx in self._ascending_indices:
            self._G.I[idx] = self._sensory_currents[idx] * brian2.amp

        # 2. Run Brian2 for coupling_dt
        self._net.run(self.coupling_dt_ms * brian_ms)

        # 3. Decode motor neuron spikes from this window
        current_spike_count = self._M.num_spikes
        if current_spike_count > self._prev_spike_count:
            new_spike_indices = np.array(self._M.i)[
                self._prev_spike_count:current_spike_count
            ]
            motor_spike_set = set(new_spike_indices) & set(self._motor_neuron_indices)
            self.decoder.update(motor_spike_set)
        else:
            self.decoder.update(set())
        self._prev_spike_count = current_spike_count

        rates = self.decoder.get_rates_hz()

        # 4. Convert to actuator positions and step FlyGym
        from .motor_adapter import decode_spikes_to_positions

        action = decode_spikes_to_positions(
            rates, self._mapping, self._neutral_ctrl,
            baseline_hz=15.0, amplitude=self.motor_gain,
        )

        for _ in range(self._flygym_steps_per_coupling):
            self._sim.set_actuator_inputs("nmf", ActuatorType.POSITION, action)
            self._sim.step()

        # 5. Read sensors for next iteration
        joint_angles = self._sim.get_joint_angles("nmf")
        body_vel = self._data.qvel[0:3].copy()
        self._sensory_currents = self.encoder.encode(joint_angles, body_vel)

        # 6. Log metrics
        mean_motor_rate = np.mean(list(rates.values())) if rates else 0.0
        sensory_mag = np.sum(np.abs(self._sensory_currents)) * 1e12  # pA
        body_pos = self._data.qpos[0:3].copy()

        self._motor_rates_log.append(mean_motor_rate)
        self._sensory_mag_log.append(sensory_mag)
        self._body_pos_log.append(body_pos)

        self._elapsed_s += self.coupling_dt_ms / 1000.0
        return self.done

    @property
    def done(self) -> bool:
        """True when elapsed time >= episode_length_s."""
        return self._elapsed_s >= self.episode_length_s

    def get_metrics(self) -> dict:
        """Return episode metrics.

        Returns
        -------
        dict
            Keys: forward_distance_mm, mean_motor_rate_hz, mean_sensory_input_pa,
            total_spikes, episode_duration_s.
        """
        current_pos = self._data.qpos[0:3].copy()
        displacement = current_pos - self._episode_start_pos

        total_episode_spikes = self._M.num_spikes - self._total_spikes_start

        return {
            "forward_distance_mm": float(displacement[0]),
            "mean_motor_rate_hz": float(np.mean(self._motor_rates_log))
            if self._motor_rates_log else 0.0,
            "mean_sensory_input_pa": float(np.mean(self._sensory_mag_log))
            if self._sensory_mag_log else 0.0,
            "total_spikes": int(total_episode_spikes),
            "episode_duration_s": self._elapsed_s,
        }

    def save_episode_summary(self, path):
        """Save episode traces and frame strip visualization.

        Parameters
        ----------
        path : str or Path
            Output file path for the PNG.
        """
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        n_steps = len(self._motor_rates_log)
        if n_steps == 0:
            return

        time_axis = np.linspace(0, self._elapsed_s, n_steps)
        motor_rates = np.array(self._motor_rates_log)
        sensory_mag = np.array(self._sensory_mag_log)
        body_pos = np.array(self._body_pos_log)

        fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True)

        # Panel 1: Motor neuron firing rates
        ax = axes[0]
        ax.plot(time_axis, motor_rates, color="tab:red", linewidth=0.8)
        ax.set_ylabel("Motor Rate (Hz)")
        ax.set_title("Episode Co-Simulation Traces")
        ax.grid(True, alpha=0.3)

        # Panel 2: Sensory input magnitude
        ax = axes[1]
        ax.plot(time_axis, sensory_mag, color="tab:blue", linewidth=0.8)
        ax.set_ylabel("Sensory Input (pA total)")
        ax.grid(True, alpha=0.3)

        # Panel 3: Body position
        ax = axes[2]
        ax.plot(time_axis, body_pos[:, 0], label="Forward (x)",
                color="tab:blue", linewidth=0.8)
        ax.plot(time_axis, body_pos[:, 1], label="Lateral (y)",
                color="tab:orange", linewidth=0.8)
        ax.plot(time_axis, body_pos[:, 2], label="Vertical (z)",
                color="tab:green", linewidth=0.8)
        ax.set_ylabel("Position (mm)")
        ax.set_xlabel("Time (s)")
        ax.legend(loc="upper left", fontsize=8)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(str(path), dpi=150, bbox_inches="tight")
        plt.close()

    def close(self):
        """Clean up resources (FlyGym simulation)."""
        if hasattr(self, "_sim") and self._sim is not None:
            self._sim.close()
            self._sim = None


def run_episode_demo():
    """Run 3 episodes and print metrics for each, demonstrating the harness API.

    Saves a summary visualization to reports/episode_demo.png.
    """
    print("=" * 70)
    print("Episode Demo: CoSimulation harness with 3 episodes")
    print("=" * 70)

    t_start = time.time()

    sim = CoSimulation(episode_length_s=2.0, coupling_dt_ms=2.0,
                       motor_gain=0.3, sensory_gain=500e-12)

    all_metrics = []
    for ep in range(3):
        print(f"\n--- Episode {ep + 1}/3 ---")
        t_ep_start = time.time()

        sim.reset()

        step_count = 0
        while not sim.done:
            sim.step()
            step_count += 1
            if step_count % 250 == 0:
                elapsed_ep = time.time() - t_ep_start
                print(f"  Step {step_count}, "
                      f"t={sim._elapsed_s:.2f}s, "
                      f"wall={elapsed_ep:.1f}s")

        metrics = sim.get_metrics()
        all_metrics.append(metrics)
        t_ep = time.time() - t_ep_start

        print(f"  Episode {ep + 1} completed in {t_ep:.1f}s")
        print(f"    Forward distance: {metrics['forward_distance_mm']:.4f} mm")
        print(f"    Mean motor rate:  {metrics['mean_motor_rate_hz']:.2f} Hz")
        print(f"    Mean sensory:     {metrics['mean_sensory_input_pa']:.1f} pA")
        print(f"    Total spikes:     {metrics['total_spikes']}")
        print(f"    Duration:         {metrics['episode_duration_s']:.2f} s")

    # Save last episode summary
    reports_dir = _DEFAULT_REPORTS_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)
    outpath = reports_dir / "episode_demo.png"
    sim.save_episode_summary(outpath)
    print(f"\n  Visualization saved: {outpath}")

    sim.close()

    # Check episodes are different (stochastic)
    print("\n--- Stochasticity Check ---")
    distances = [m["forward_distance_mm"] for m in all_metrics]
    spikes = [m["total_spikes"] for m in all_metrics]
    print(f"  Forward distances: {[f'{d:.4f}' for d in distances]}")
    print(f"  Total spikes:      {spikes}")

    if len(set(spikes)) > 1 or len(set(f"{d:.6f}" for d in distances)) > 1:
        print("  PASS: Episodes show stochastic variation")
    else:
        print("  NOTE: Episodes appear identical (may need more variation)")

    total_time = time.time() - t_start
    print(f"\n{'=' * 70}")
    print(f"EPISODE DEMO COMPLETE")
    print(f"  Total runtime: {total_time:.1f}s")
    print(f"  Output: {outpath}")
    print(f"{'=' * 70}")
