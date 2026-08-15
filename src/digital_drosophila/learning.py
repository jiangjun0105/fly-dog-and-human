"""Reward-modulated three-factor STDP for the sensorimotor loop.

Implements a LearningLoop that wraps Brian2 + FlyGym co-simulation with
three-factor plasticity: spike timing (STDP) + eligibility trace + reward signal.

The network learns from forward velocity reward to improve motor output over episodes.

Usage:
    python -m digital_drosophila learn stdp_basic --episodes 10
"""

import os
import time
from pathlib import Path

import numpy as np

# Reports directory
_PACKAGE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _PACKAGE_DIR.parent.parent
_DEFAULT_REPORTS_DIR = _PROJECT_ROOT / "reports"


class LearningLoop:
    """Episode-based learning loop with three-factor STDP plasticity.

    Three-factor STDP:
      Factor 1: Pre-post spike timing (causal STDP window, tau ~ 20ms)
      Factor 2: Eligibility trace (decaying memory of correlations, tau ~ 1s)
      Factor 3: Reward/dopamine signal (gates actual weight updates at episode end)

    Parameters
    ----------
    n_episodes : int
        Number of training episodes.
    episode_length_s : float
        Duration of each episode in seconds.
    coupling_dt_ms : float
        Coupling timestep between neural and body simulators in milliseconds.
    learning_rate : float
        Weight change scale per update (in mV units).
    tau_stdp_ms : float
        STDP time window in milliseconds.
    tau_eligibility_s : float
        Eligibility trace decay time constant in seconds.
    motor_gain : float
        Amplitude of motor neuron rate-to-position conversion.
    sensory_gain : float
        Gain for sensory encoding in Amperes.
    baseline_window : int
        Number of recent rewards to average for baseline subtraction.
    """

    def __init__(
        self,
        n_episodes=20,
        episode_length_s=1.0,
        coupling_dt_ms=2.0,
        learning_rate=0.001,
        tau_stdp_ms=20.0,
        tau_eligibility_s=1.0,
        motor_gain=0.3,
        sensory_gain=500e-12,
        baseline_window=5,
    ):
        self.n_episodes = n_episodes
        self.episode_length_s = episode_length_s
        self.coupling_dt_ms = coupling_dt_ms
        self.learning_rate = learning_rate
        self.tau_stdp_ms = tau_stdp_ms
        self.tau_eligibility_s = tau_eligibility_s
        self.motor_gain = motor_gain
        self.sensory_gain = sensory_gain
        self.baseline_window = baseline_window

        # Set env vars before importing heavy dependencies
        os.environ.setdefault("MUJOCO_GL", "egl")

        # Build the simulation
        self._build()

    def _build(self):
        """Build Brian2 network with STDP synapses and FlyGym body."""
        import brian2
        brian2.prefs.codegen.target = "numpy"

        from brian2 import (
            Network, SpikeMonitor, PoissonGroup, Synapses, NeuronGroup,
            Hz as brian_Hz, mV as brian_mV, ms as brian_ms, second as brian_second,
            pA,
        )

        from .network import (
            load_sample_data,
            create_neuron_group,
            create_poisson_drive,
            create_background_drive,
        )
        from .constants import NT_SIGN_MAP
        from .locomotion import build_simulation, settle_simulation
        from .sensory_encoder import SensoryEncoder
        from .motor_adapter import SpikeRateDecoder, MotorMapping

        # --- Load data ---
        adj, neurons_df = load_sample_data()
        self._n_neurons = adj.shape[0]
        self._neurons_df = neurons_df

        self._motor_neuron_indices = neurons_df[
            neurons_df["superclass"] == "vnc_motor"
        ].index.tolist()
        self._ascending_indices = neurons_df[
            neurons_df["superclass"] == "ascending_neuron"
        ].index.tolist()

        # --- Build sign vector ---
        nt_series = neurons_df["consensusNt"]
        confidence = neurons_df["predictedNtConfidence"].values
        self._sign_vector = np.array(
            [NT_SIGN_MAP.get(nt, 0) or 0 for nt in nt_series]
        )
        self._confidence = confidence

        # --- Build neuron group ---
        G = create_neuron_group(self._n_neurons)

        # --- Build STDP synapses (three-factor) ---
        # The synapse model includes eligibility trace for reward modulation
        stdp_model = '''
        w : volt
        dApre/dt = -Apre / tau_stdp : 1 (event-driven)
        dApost/dt = -Apost / tau_stdp : 1 (event-driven)
        deligibility/dt = -eligibility / tau_e : 1 (clock-driven)
        '''

        stdp_pre = '''
        v_post += w
        Apre += 1.0
        eligibility += Apost
        '''

        stdp_post = '''
        Apost += 1.0
        eligibility += Apre
        '''

        namespace = {
            'tau_stdp': self.tau_stdp_ms * brian_ms,
            'tau_e': self.tau_eligibility_s * brian_second,
        }

        S = Synapses(
            G, G,
            model=stdp_model,
            on_pre=stdp_pre,
            on_post=stdp_post,
            namespace=namespace,
        )

        # Connect based on adjacency matrix
        sources, targets = adj.nonzero()
        S.connect(i=sources, j=targets)

        # Set initial weights using sign-constrained formula
        inh_attenuation = 0.5
        scale = 0.6
        sign_scale = np.where(
            self._sign_vector[sources] >= 0, 1.0, inh_attenuation
        )
        weights_raw = (
            np.log1p(adj[sources, targets])
            * self._sign_vector[sources]
            * confidence[sources]
            * sign_scale
            * scale
        )
        S.w = weights_raw * brian_mV

        self._S = S
        self._sources = sources
        self._targets = targets
        self._initial_weights = weights_raw.copy()

        # --- Input drives ---
        PG, S_input, _ = create_poisson_drive(
            G, neurons_df, target_superclass="descending_neuron",
            n_sources=15, rate=10 * brian_Hz, weight=2.0 * brian_mV,
        )
        PG_bg, S_bg = create_background_drive(
            G, self._n_neurons, n_sources=50, rate=22 * brian_Hz, weight=1.3 * brian_mV,
        )
        M = SpikeMonitor(G)

        # Assemble network
        self._net = Network(G, S, PG, S_input, PG_bg, S_bg, M)
        self._G = G
        self._M = M

        # Store initial state for reset
        self._net.store("initial")

        # --- FlyGym body ---
        sim, fly, model, data, neutral_ctrl, actuator_names = build_simulation()
        settle_simulation(sim, n_steps=2000)

        self._sim = sim
        self._fly = fly
        self._model = model
        self._data = data
        self._neutral_ctrl = neutral_ctrl

        # Save initial body state
        self._initial_qpos = data.qpos.copy()
        self._initial_qvel = data.qvel.copy()

        # FlyGym physics steps per coupling step
        flygym_dt_s = model.opt.timestep
        self._flygym_steps_per_coupling = int(
            self.coupling_dt_ms / (flygym_dt_s * 1000)
        )

        # --- Adapters ---
        sensory_gain_pa = self.sensory_gain / 1e-12
        self._encoder = SensoryEncoder(
            self._ascending_indices, n_neurons=self._n_neurons, n_actuated=66,
            gain_pa=sensory_gain_pa, vel_gain_pa=sensory_gain_pa * 0.6,
        )
        self._decoder = SpikeRateDecoder(
            self._motor_neuron_indices, window_ms=50.0, dt_ms=self.coupling_dt_ms,
        )
        motor_map = MotorMapping(self._motor_neuron_indices)
        self._mapping = motor_map.get_mapping()

    def _reset_episode(self):
        """Reset network and body for a new episode."""
        import brian2
        from brian2 import ms as brian_ms, pA

        # Reset Brian2 network
        self._net.restore("initial")

        # Restore current learned weights (initial state has the original weights)
        from brian2 import mV as brian_mV
        self._S.w = self._current_weights * brian_mV

        # Reset body
        self._data.qpos[:] = self._initial_qpos
        self._data.qvel[:] = self._initial_qvel
        self._data.ctrl[:] = self._neutral_ctrl
        import mujoco
        mujoco.mj_forward(self._model, self._data)

        # Reset decoder
        from .motor_adapter import SpikeRateDecoder
        self._decoder = SpikeRateDecoder(
            self._motor_neuron_indices, window_ms=50.0, dt_ms=self.coupling_dt_ms,
        )

        # Run 500ms burn-in
        burn_in_ms = 500.0
        self._G.I = 0 * pA
        self._net.run(burn_in_ms * brian_ms)

        # Track spike count baseline
        self._prev_spike_count = self._M.num_spikes

        # Record start position
        self._episode_start_pos = self._data.qpos[0:3].copy()

        # Initialize sensory currents
        joint_angles = self._sim.get_joint_angles("nmf")
        body_vel = self._data.qvel[0:3].copy()
        self._sensory_currents = self._encoder.encode(joint_angles, body_vel)

    def _run_episode(self):
        """Run one episode of the closed-loop simulation."""
        import brian2
        from brian2 import ms as brian_ms, pA
        from flygym.compose import ActuatorType
        from .motor_adapter import decode_spikes_to_positions

        n_steps = int(self.episode_length_s * 1000 / self.coupling_dt_ms)

        for step in range(n_steps):
            # 1. Inject sensory currents
            self._G.I = 0 * pA
            for idx in self._ascending_indices:
                self._G.I[idx] = self._sensory_currents[idx] * brian2.amp

            # 2. Run Brian2
            self._net.run(self.coupling_dt_ms * brian_ms)

            # 3. Decode motor spikes
            current_spike_count = self._M.num_spikes
            if current_spike_count > self._prev_spike_count:
                new_spike_indices = np.array(self._M.i)[
                    self._prev_spike_count:current_spike_count
                ]
                motor_spike_set = (
                    set(new_spike_indices) & set(self._motor_neuron_indices)
                )
                self._decoder.update(motor_spike_set)
            else:
                self._decoder.update(set())
            self._prev_spike_count = current_spike_count

            rates = self._decoder.get_rates_hz()

            # 4. Convert to actuator positions and step body
            action = decode_spikes_to_positions(
                rates, self._mapping, self._neutral_ctrl,
                baseline_hz=15.0, amplitude=self.motor_gain,
            )

            for _ in range(self._flygym_steps_per_coupling):
                self._sim.set_actuator_inputs("nmf", ActuatorType.POSITION, action)
                self._sim.step()

            # 5. Read sensors
            joint_angles = self._sim.get_joint_angles("nmf")
            body_vel = self._data.qvel[0:3].copy()
            self._sensory_currents = self._encoder.encode(joint_angles, body_vel)

    def _compute_reward(self):
        """Compute reward from forward displacement."""
        current_pos = self._data.qpos[0:3].copy()
        displacement = current_pos - self._episode_start_pos
        # Reward = forward distance in mm
        return float(displacement[0])

    def _update_weights(self, reward, rewards_history):
        """Apply reward-modulated weight update using eligibility traces.

        Parameters
        ----------
        reward : float
            Reward for this episode (forward distance in mm).
        rewards_history : list of float
            All past rewards for baseline computation.
        """
        from brian2 import mV as brian_mV

        # Compute dopamine signal (reward prediction error)
        if len(rewards_history) >= 2:
            recent = rewards_history[-min(self.baseline_window, len(rewards_history)):]
            baseline = np.mean(recent)
        else:
            baseline = 0.0
        dopamine = reward - baseline

        # Read eligibility traces from synapses
        eligibility = np.array(self._S.eligibility[:])

        # Compute weight deltas
        dw = self.learning_rate * eligibility * dopamine

        # Apply update to current weights
        self._current_weights = self._current_weights + dw

        # Enforce sign constraint (Dale's principle)
        excitatory_mask = self._sign_vector[self._sources] > 0
        inhibitory_mask = self._sign_vector[self._sources] < 0

        # Excitatory weights must stay >= 0
        self._current_weights[excitatory_mask] = np.maximum(
            self._current_weights[excitatory_mask], 0.0
        )
        # Inhibitory weights must stay <= 0
        self._current_weights[inhibitory_mask] = np.minimum(
            self._current_weights[inhibitory_mask], 0.0
        )

        # Return stats
        return {
            "dopamine": dopamine,
            "mean_eligibility": float(np.mean(np.abs(eligibility))),
            "mean_abs_dw": float(np.mean(np.abs(dw))),
            "max_abs_dw": float(np.max(np.abs(dw))),
            "weight_mean": float(np.mean(self._current_weights)),
            "weight_std": float(np.std(self._current_weights)),
        }

    def train(self):
        """Run the full training loop over all episodes.

        Returns
        -------
        results : dict
            Keys: rewards, weight_stats, episode_times.
        """
        print("=" * 70)
        print("Three-Factor STDP Learning Loop")
        print(f"  Episodes: {self.n_episodes}")
        print(f"  Episode length: {self.episode_length_s}s")
        print(f"  Learning rate: {self.learning_rate} mV")
        print(f"  STDP tau: {self.tau_stdp_ms} ms")
        print(f"  Eligibility tau: {self.tau_eligibility_s} s")
        print("=" * 70)

        # Initialize current weights from initial weights
        self._current_weights = self._initial_weights.copy()

        rewards = []
        weight_stats = []
        episode_times = []

        t_total_start = time.time()

        for ep in range(self.n_episodes):
            print(f"\n--- Episode {ep + 1}/{self.n_episodes} ---")
            t_ep_start = time.time()

            # Reset and run episode
            self._reset_episode()
            self._run_episode()

            # Compute reward
            reward = self._compute_reward()
            rewards.append(reward)

            # Update weights
            stats = self._update_weights(reward, rewards)
            weight_stats.append(stats)

            t_ep = time.time() - t_ep_start
            episode_times.append(t_ep)

            # Print summary
            print(f"  Reward (forward distance): {reward:.6f} mm")
            print(f"  Dopamine signal: {stats['dopamine']:.6f}")
            print(f"  Mean |eligibility|: {stats['mean_eligibility']:.6f}")
            print(f"  Mean |dw|: {stats['mean_abs_dw']:.8f} mV")
            print(f"  Max |dw|: {stats['max_abs_dw']:.8f} mV")
            print(f"  Weight mean: {stats['weight_mean']:.6f} mV")
            print(f"  Weight std: {stats['weight_std']:.6f} mV")
            print(f"  Episode wall time: {t_ep:.1f}s")

            # Verify sign constraint
            exc_mask = self._sign_vector[self._sources] > 0
            inh_mask = self._sign_vector[self._sources] < 0
            n_exc_violations = np.sum(self._current_weights[exc_mask] < 0)
            n_inh_violations = np.sum(self._current_weights[inh_mask] > 0)
            if n_exc_violations > 0 or n_inh_violations > 0:
                print(f"  WARNING: Sign violations! exc={n_exc_violations}, "
                      f"inh={n_inh_violations}")
            else:
                print(f"  Sign constraint: OK (no violations)")

        total_time = time.time() - t_total_start

        # Final summary
        print(f"\n{'=' * 70}")
        print("TRAINING COMPLETE")
        print(f"{'=' * 70}")
        print(f"  Total episodes: {self.n_episodes}")
        print(f"  Total time: {total_time:.1f}s "
              f"(avg {total_time / self.n_episodes:.1f}s/episode)")
        print(f"\n  Per-episode rewards:")
        for i, r in enumerate(rewards):
            print(f"    Episode {i + 1}: {r:.6f} mm")
        print(f"\n  Reward stats:")
        print(f"    Mean: {np.mean(rewards):.6f} mm")
        print(f"    Std: {np.std(rewards):.6f} mm")
        print(f"    First half mean: {np.mean(rewards[:len(rewards)//2]):.6f} mm")
        print(f"    Second half mean: {np.mean(rewards[len(rewards)//2:]):.6f} mm")

        # Weight change from initial
        total_weight_change = np.sum(
            np.abs(self._current_weights - self._initial_weights)
        )
        print(f"\n  Total weight change from initial: {total_weight_change:.6f} mV")
        print(f"  Mean absolute weight: {np.mean(np.abs(self._current_weights)):.6f} mV")
        print(f"{'=' * 70}")

        return {
            "rewards": rewards,
            "weight_stats": weight_stats,
            "episode_times": episode_times,
            "final_weights": self._current_weights.copy(),
            "initial_weights": self._initial_weights.copy(),
        }

    def save_learning_curve(self, results, path=None):
        """Save learning curve visualization.

        Parameters
        ----------
        results : dict
            Output from train().
        path : str or Path, optional
            Output path. Defaults to reports/learning_curve.png.
        """
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        if path is None:
            path = _DEFAULT_REPORTS_DIR / "learning_curve.png"
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        rewards = results["rewards"]
        weight_stats = results["weight_stats"]
        n_eps = len(rewards)
        episodes = np.arange(1, n_eps + 1)

        fig, axes = plt.subplots(4, 1, figsize=(10, 12))

        # Panel 1: Rewards (forward distance)
        ax = axes[0]
        ax.plot(episodes, rewards, "o-", color="tab:blue", linewidth=1.5,
                markersize=5)
        # Running mean
        if n_eps >= 3:
            window = min(5, n_eps)
            running_mean = np.convolve(
                rewards, np.ones(window) / window, mode="valid"
            )
            rm_x = np.arange(window, n_eps + 1)
            ax.plot(rm_x, running_mean, "--", color="tab:red", linewidth=2,
                    label=f"{window}-episode running mean")
            ax.legend(fontsize=9)
        ax.set_ylabel("Forward Distance (mm)")
        ax.set_title("Three-Factor STDP Learning Curve")
        ax.grid(True, alpha=0.3)
        ax.axhline(0, color="gray", linestyle=":", alpha=0.5)

        # Panel 2: Weight change magnitude per episode
        ax = axes[1]
        dw_means = [s["mean_abs_dw"] for s in weight_stats]
        dw_maxes = [s["max_abs_dw"] for s in weight_stats]
        ax.plot(episodes, dw_means, "o-", color="tab:green", linewidth=1.5,
                markersize=4, label="Mean |dw|")
        ax.plot(episodes, dw_maxes, "s-", color="tab:orange", linewidth=1,
                markersize=3, alpha=0.7, label="Max |dw|")
        ax.set_ylabel("Weight Change (mV)")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)

        # Panel 3: Eligibility trace magnitude
        ax = axes[2]
        elig_means = [s["mean_eligibility"] for s in weight_stats]
        ax.plot(episodes, elig_means, "o-", color="tab:purple", linewidth=1.5,
                markersize=4)
        ax.set_ylabel("Mean |Eligibility|")
        ax.grid(True, alpha=0.3)

        # Panel 4: Dopamine signal
        ax = axes[3]
        dopamines = [s["dopamine"] for s in weight_stats]
        colors = ["tab:green" if d >= 0 else "tab:red" for d in dopamines]
        ax.bar(episodes, dopamines, color=colors, alpha=0.7)
        ax.axhline(0, color="gray", linestyle="-", alpha=0.5)
        ax.set_ylabel("Dopamine Signal")
        ax.set_xlabel("Episode")
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(str(path), dpi=150, bbox_inches="tight")
        plt.close()

        print(f"Learning curve saved: {path}")
        return path

    def close(self):
        """Clean up resources."""
        if hasattr(self, "_sim") and self._sim is not None:
            self._sim.close()
            self._sim = None


def run_stdp_basic(episodes=10):
    """Run the basic STDP learning demo.

    Parameters
    ----------
    episodes : int
        Number of training episodes.
    """
    print(f"\nStarting STDP basic learning with {episodes} episodes...\n")

    loop = LearningLoop(
        n_episodes=episodes,
        episode_length_s=1.0,
        coupling_dt_ms=2.0,
        learning_rate=0.001,
        tau_stdp_ms=20.0,
        tau_eligibility_s=1.0,
        motor_gain=0.3,
        sensory_gain=500e-12,
        baseline_window=5,
    )

    try:
        results = loop.train()
        path = loop.save_learning_curve(results)
        print(f"\nDone. Learning curve: {path}")
    finally:
        loop.close()
