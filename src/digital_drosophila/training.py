"""Extended training harness with homeostatic plasticity and synaptic decay.

Builds on the three-factor STDP in learning.py, adding:
  1. Adaptive threshold (homeostatic plasticity): per-neuron threshold adjustment
     based on measured firing rate vs target rate.
  2. Synaptic decay: use-it-or-lose-it pruning of inactive synapses.
  3. Checkpoint saving and structured training log output.

Usage:
    python -m digital_drosophila learn train [--episodes 50] [--episode-length 2.0]
"""

import json
import os
import time
from pathlib import Path

import numpy as np

# Reports directory
_PACKAGE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _PACKAGE_DIR.parent.parent
_DEFAULT_REPORTS_DIR = _PROJECT_ROOT / "reports"


class TrainingHarness:
    """Episode-based training with homeostatic plasticity and synaptic decay.

    Extends the three-factor STDP approach (eligibility trace + reward modulation)
    with two stability mechanisms:

      - Adaptive threshold: adjusts per-neuron firing threshold to keep each neuron
        near a target firing rate, preventing silence or seizure-like activity.
      - Synaptic decay: slowly decays inactive synapses (low eligibility trace),
        implementing use-it-or-lose-it pruning.

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
    eta_homeo : float
        Homeostatic threshold adjustment rate (mV per Hz deviation per episode).
    target_rate : float
        Target firing rate in Hz for homeostatic regulation.
    lambda_decay : float
        Synaptic decay rate per episode for inactive synapses.
    eligibility_decay_threshold : float
        Synapses with eligibility trace magnitude below this are considered
        inactive and subject to decay.
    checkpoint_interval : int
        Save weight checkpoint every N episodes.
    """

    def __init__(
        self,
        n_episodes=50,
        episode_length_s=2.0,
        coupling_dt_ms=2.0,
        learning_rate=0.001,
        tau_stdp_ms=20.0,
        tau_eligibility_s=1.0,
        motor_gain=0.3,
        sensory_gain=500e-12,
        baseline_window=5,
        eta_homeo=0.01,
        target_rate=25.0,
        lambda_decay=0.001,
        eligibility_decay_threshold=0.01,
        checkpoint_interval=10,
        topology="biological",
        random_seed=42,
        backend="cpu",
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
        self.eta_homeo = eta_homeo
        self.target_rate = target_rate
        self.lambda_decay = lambda_decay
        self.eligibility_decay_threshold = eligibility_decay_threshold
        self.checkpoint_interval = checkpoint_interval
        self.topology = topology
        self.random_seed = random_seed
        self._backend_type = backend

        # Set env vars before importing heavy dependencies
        os.environ.setdefault("MUJOCO_GL", "egl")

        # Build the simulation
        if backend == "gpu":
            self._build_gpu()
        else:
            self._build()

    def _build(self):
        """Build Brian2 network with adaptive-threshold neurons and STDP synapses."""
        import brian2
        brian2.prefs.codegen.target = "numpy"

        from brian2 import (
            Network, SpikeMonitor, PoissonGroup, Synapses, NeuronGroup,
            Hz as brian_Hz, mV as brian_mV, ms as brian_ms, second as brian_second,
            Mohm as brian_Mohm, pA,
        )

        from .network import (
            load_sample_data,
            create_poisson_drive,
            create_background_drive,
            DEFAULT_LIF_PARAMS,
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

        # --- Build neuron group with adaptive threshold ---
        # Modified LIF model: V_th_adapt is a per-neuron variable instead of
        # a namespace constant. This allows homeostatic plasticity to raise/lower
        # each neuron's threshold independently.
        params = DEFAULT_LIF_PARAMS
        tau_m = params["tau_m"]
        V_rest = params["V_rest"]
        V_reset = params["V_reset"]
        R_membrane = params["R_membrane"]
        t_refract = params["t_refract"]

        eqs = """
        dv/dt = (-(v - V_rest) + R_membrane * I) / tau_m : volt (unless refractory)
        I : amp
        V_th_adapt : volt
        """

        namespace = {
            "tau_m": tau_m,
            "V_rest": V_rest,
            "V_reset": V_reset,
            "R_membrane": R_membrane,
        }

        G = NeuronGroup(
            self._n_neurons,
            eqs,
            threshold="v > V_th_adapt",
            reset="v = V_reset",
            refractory=t_refract,
            method="euler",
            namespace=namespace,
        )
        G.v = V_rest
        # Initialize adaptive threshold to default -50 mV
        G.V_th_adapt = -50 * brian_mV

        # Store initial threshold values (in mV, unitless for numpy manipulation)
        self._thresholds_mV = np.full(self._n_neurons, -50.0)

        # --- Build STDP synapses (three-factor) ---
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

        syn_namespace = {
            'tau_stdp': self.tau_stdp_ms * brian_ms,
            'tau_e': self.tau_eligibility_s * brian_second,
        }

        S = Synapses(
            G, G,
            model=stdp_model,
            on_pre=stdp_pre,
            on_post=stdp_post,
            namespace=syn_namespace,
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

        # For random topology: shuffle weight magnitudes within sign groups
        if self.topology == "random":
            rng = np.random.default_rng(self.random_seed)
            exc_mask = weights_raw > 0
            inh_mask = weights_raw < 0
            exc_vals = weights_raw[exc_mask].copy()
            inh_vals = weights_raw[inh_mask].copy()
            rng.shuffle(exc_vals)
            rng.shuffle(inh_vals)
            weights_raw[exc_mask] = exc_vals
            weights_raw[inh_mask] = inh_vals

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

    def _build_gpu(self):
        """Build PyGeNN GPU backend and FlyGym body (no Brian2)."""
        import scipy.sparse as sp

        from .network import load_sample_data, DEFAULT_LIF_PARAMS
        from .constants import NT_SIGN_MAP
        from .locomotion import build_simulation, settle_simulation
        from .sensory_encoder import SensoryEncoder
        from .motor_adapter import SpikeRateDecoder, MotorMapping
        from .gpu_backend import PyGeNNBackend

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

        # --- Compute weights (same logic as Brian2 path) ---
        sources, targets = adj.nonzero()
        self._sources = sources
        self._targets = targets

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

        if self.topology == "random":
            rng = np.random.default_rng(self.random_seed)
            exc_mask = weights_raw > 0
            inh_mask = weights_raw < 0
            exc_vals = weights_raw[exc_mask].copy()
            inh_vals = weights_raw[inh_mask].copy()
            rng.shuffle(exc_vals)
            rng.shuffle(inh_vals)
            weights_raw[exc_mask] = exc_vals
            weights_raw[inh_mask] = inh_vals

        self._initial_weights = weights_raw.copy()
        self._thresholds_mV = np.full(self._n_neurons, -50.0)

        # --- Build PyGeNN backend ---
        # Convert adjacency to sparse for backend
        adj_sparse = sp.coo_matrix(
            (np.ones(len(sources)), (sources, targets)),
            shape=(self._n_neurons, self._n_neurons),
        )

        print("Building PyGeNN GPU backend (CUDA compilation)...")
        self._gpu_backend = PyGeNNBackend(
            adj_sparse,
            weights_raw,
            self._thresholds_mV,
            self._motor_neuron_indices,
            self._ascending_indices,
            dt_ms=0.1,
            coupling_dt_ms=self.coupling_dt_ms,
            tau_stdp_ms=self.tau_stdp_ms,
            tau_eligibility_ms=self.tau_eligibility_s * 1000.0,
        )
        self._gpu_backend.build()
        print("PyGeNN backend ready.")

        # --- FlyGym body (same as CPU path) ---
        sim, fly, model, data, neutral_ctrl, actuator_names = build_simulation()
        settle_simulation(sim, n_steps=2000)

        self._sim = sim
        self._fly = fly
        self._model = model
        self._data = data
        self._neutral_ctrl = neutral_ctrl

        self._initial_qpos = data.qpos.copy()
        self._initial_qvel = data.qvel.copy()

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
        if self._backend_type == "gpu":
            return self._reset_episode_gpu()

        import brian2
        from brian2 import ms as brian_ms, mV as brian_mV, pA

        # Reset Brian2 network
        self._net.restore("initial")

        # Restore current learned weights (initial state has the original weights)
        self._S.w = self._current_weights * brian_mV

        # Restore adaptive thresholds
        self._G.V_th_adapt = self._thresholds_mV * brian_mV

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

        # Track spike count baseline (for counting new spikes this episode)
        self._prev_spike_count = self._M.num_spikes

        # Record per-neuron spike counts at episode start for firing rate measurement
        if self._M.num_spikes > 0:
            spike_indices = np.array(self._M.i[:])
            self._episode_spike_start = np.bincount(
                spike_indices, minlength=self._n_neurons
            ).astype(float)
        else:
            self._episode_spike_start = np.zeros(self._n_neurons)

        # Record start position
        self._episode_start_pos = self._data.qpos[0:3].copy()

        # Initialize sensory currents
        joint_angles = self._sim.get_joint_angles("nmf")
        body_vel = self._data.qvel[0:3].copy()
        self._sensory_currents = self._encoder.encode(joint_angles, body_vel)

    def _reset_episode_gpu(self):
        """Reset GPU backend and body for a new episode."""
        import mujoco
        from .motor_adapter import SpikeRateDecoder

        # Reset GPU backend with current weights and thresholds
        self._gpu_backend.reset(self._current_weights, self._thresholds_mV)

        # Compute background tonic current matching the Brian2 Poisson drives.
        # Brian2 uses stochastic Poisson input; tonic current needs to be higher
        # to compensate for the missing fluctuation-driven firing.
        # Target: bring neurons to ~2mV below threshold so recurrent + sensory
        # input can push them over. V_th=-50, V_rest=-70, need ~18mV drive.
        # I = dV / R_membrane = 18mV / 100MOhm = 0.18 nA = 180 pA
        # Descending neurons get extra 30 pA drive.
        bg_current_pA = 180.0
        descending_extra_pA = 30.0
        self._gpu_bg_currents = np.full(self._n_neurons, bg_current_pA, dtype=np.float32)
        descending_mask = self._neurons_df["superclass"] == "descending_neuron"
        descending_idx = self._neurons_df[descending_mask].index.tolist()
        self._gpu_bg_currents[descending_idx] += descending_extra_pA

        # Run burn-in on GPU (250 coupling steps = 500ms)
        burn_in_steps = int(500.0 / self.coupling_dt_ms)
        for _ in range(burn_in_steps):
            self._gpu_backend.step(self._gpu_bg_currents)

        # Reset spike counts after burn-in (don't count burn-in spikes)
        self._gpu_backend._spike_counts[:] = 0

        # Reset body
        self._data.qpos[:] = self._initial_qpos
        self._data.qvel[:] = self._initial_qvel
        self._data.ctrl[:] = self._neutral_ctrl
        mujoco.mj_forward(self._model, self._data)

        # Reset decoder
        self._decoder = SpikeRateDecoder(
            self._motor_neuron_indices, window_ms=50.0, dt_ms=self.coupling_dt_ms,
        )

        # Record start position
        self._episode_start_pos = self._data.qpos[0:3].copy()

        # Initialize sensory currents
        joint_angles = self._sim.get_joint_angles("nmf")
        body_vel = self._data.qvel[0:3].copy()
        self._sensory_currents = self._encoder.encode(joint_angles, body_vel)

    def _run_episode(self):
        """Run one episode of the closed-loop simulation."""
        if self._backend_type == "gpu":
            return self._run_episode_gpu()

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

    def _run_episode_gpu(self):
        """Run one episode using GPU backend for neural simulation."""
        from flygym.compose import ActuatorType
        from .motor_adapter import decode_spikes_to_positions

        n_steps = int(self.episode_length_s * 1000 / self.coupling_dt_ms)

        for step in range(n_steps):
            # 1. Step GPU neural simulation with sensory + background currents
            # Sensory currents are in Amps (from encoder), convert to pA
            sensory_pA = self._sensory_currents * 1e12
            combined_currents = sensory_pA + self._gpu_bg_currents
            motor_spikes = self._gpu_backend.step(combined_currents)

            # 2. Decode motor spikes
            self._decoder.update(motor_spikes)
            rates = self._decoder.get_rates_hz()

            # 3. Convert to actuator positions and step body
            action = decode_spikes_to_positions(
                rates, self._mapping, self._neutral_ctrl,
                baseline_hz=15.0, amplitude=self.motor_gain,
            )

            for _ in range(self._flygym_steps_per_coupling):
                self._sim.set_actuator_inputs("nmf", ActuatorType.POSITION, action)
                self._sim.step()

            # 4. Read sensors
            joint_angles = self._sim.get_joint_angles("nmf")
            body_vel = self._data.qvel[0:3].copy()
            self._sensory_currents = self._encoder.encode(joint_angles, body_vel)

    def _compute_firing_rates(self):
        """Compute per-neuron firing rate (Hz) during this episode."""
        if self._backend_type == "gpu":
            counts = self._gpu_backend.get_spike_counts().astype(float)
            return counts / self.episode_length_s

        if self._M.num_spikes > 0:
            spike_indices = np.array(self._M.i[:])
            spike_counts = np.bincount(
                spike_indices, minlength=self._n_neurons
            ).astype(float)
        else:
            spike_counts = np.zeros(self._n_neurons)

        episode_spikes = np.maximum(spike_counts - self._episode_spike_start, 0)
        rates = episode_spikes / self.episode_length_s
        return rates

    def _compute_reward(self):
        """Compute reward from forward displacement."""
        current_pos = self._data.qpos[0:3].copy()
        displacement = current_pos - self._episode_start_pos
        # Reward = forward distance in mm
        return float(displacement[0])

    def _update_weights(self, reward, rewards_history):
        """Apply reward-modulated weight update using eligibility traces."""
        # Compute dopamine signal (reward prediction error)
        if len(rewards_history) >= 2:
            recent = rewards_history[-min(self.baseline_window, len(rewards_history)):]
            baseline = np.mean(recent)
        else:
            baseline = 0.0
        dopamine = reward - baseline

        # Read eligibility traces from backend
        if self._backend_type == "gpu":
            eligibility = self._gpu_backend.get_eligibility()
        else:
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

    def _apply_homeostatic_plasticity(self, firing_rates):
        """Adjust per-neuron thresholds based on measured firing rates.

        Neurons firing above target_rate get a higher threshold (harder to fire).
        Neurons firing below target_rate get a lower threshold (easier to fire).

        Parameters
        ----------
        firing_rates : ndarray
            Per-neuron firing rates in Hz for the most recent episode.

        Returns
        -------
        stats : dict
            Threshold adjustment statistics.
        """
        # Compute deviation from target rate
        rate_deviation = firing_rates - self.target_rate

        # Update thresholds: positive deviation -> raise threshold
        delta_th = self.eta_homeo * rate_deviation
        self._thresholds_mV = self._thresholds_mV + delta_th

        # Clamp thresholds to reasonable range: [-70, -30] mV
        # (V_rest is -70 mV; anything above -30 mV means the neuron is effectively dead)
        self._thresholds_mV = np.clip(self._thresholds_mV, -70.0, -30.0)

        return {
            "threshold_mean": float(np.mean(self._thresholds_mV)),
            "threshold_std": float(np.std(self._thresholds_mV)),
            "threshold_min": float(np.min(self._thresholds_mV)),
            "threshold_max": float(np.max(self._thresholds_mV)),
            "mean_rate_deviation": float(np.mean(np.abs(rate_deviation))),
            "neurons_above_target": int(np.sum(firing_rates > self.target_rate)),
            "neurons_below_target": int(np.sum(firing_rates < self.target_rate)),
        }

    def _apply_synaptic_decay(self):
        """Decay inactive synapses (those with low eligibility trace).

        Only synapses whose absolute eligibility trace is below the decay threshold
        are decayed. Active synapses (high eligibility) are preserved.

        Returns
        -------
        stats : dict
            Decay statistics.
        """
        # Read current eligibility traces
        if self._backend_type == "gpu":
            eligibility = self._gpu_backend.get_eligibility()
        else:
            eligibility = np.array(self._S.eligibility[:])

        # Identify inactive synapses (low eligibility)
        inactive_mask = np.abs(eligibility) < self.eligibility_decay_threshold

        # Apply decay only to inactive synapses
        decay_factor = 1.0 - self.lambda_decay
        self._current_weights[inactive_mask] *= decay_factor

        # Enforce sign constraint after decay (decay toward zero, so this
        # should already be satisfied, but enforce for safety)
        excitatory_mask = self._sign_vector[self._sources] > 0
        inhibitory_mask = self._sign_vector[self._sources] < 0
        self._current_weights[excitatory_mask] = np.maximum(
            self._current_weights[excitatory_mask], 0.0
        )
        self._current_weights[inhibitory_mask] = np.minimum(
            self._current_weights[inhibitory_mask], 0.0
        )

        n_decayed = int(np.sum(inactive_mask))
        n_total = len(self._current_weights)

        return {
            "n_decayed": n_decayed,
            "n_total": n_total,
            "fraction_decayed": float(n_decayed / n_total) if n_total > 0 else 0.0,
            "mean_abs_weight_after": float(np.mean(np.abs(self._current_weights))),
        }

    def _save_checkpoint(self, episode, checkpoint_dir):
        """Save weight checkpoint to disk.

        Parameters
        ----------
        episode : int
            Current episode number (1-based).
        checkpoint_dir : Path
            Directory for checkpoint files.
        """
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = checkpoint_dir / f"weights_ep{episode:04d}.npz"
        np.savez_compressed(
            checkpoint_path,
            weights=self._current_weights,
            thresholds=self._thresholds_mV,
            episode=episode,
        )
        return checkpoint_path

    def train(self, checkpoint_dir=None):
        """Run the full training loop with homeostatic plasticity and synaptic decay.

        Parameters
        ----------
        checkpoint_dir : Path or str, optional
            Directory for weight checkpoints. Defaults to reports/checkpoints/.

        Returns
        -------
        results : dict
            Keys: rewards, weight_stats, homeostatic_stats, decay_stats,
            firing_rates, episode_times, final_weights, final_thresholds.
        """
        print("=" * 70)
        print("Training Harness: STDP + Homeostatic Plasticity + Synaptic Decay")
        print(f"  Backend: {self._backend_type.upper()}")
        print(f"  Topology: {self.topology}")
        print(f"  Episodes: {self.n_episodes}")
        print(f"  Episode length: {self.episode_length_s}s")
        print(f"  Learning rate: {self.learning_rate} mV")
        print(f"  STDP tau: {self.tau_stdp_ms} ms")
        print(f"  Eligibility tau: {self.tau_eligibility_s} s")
        print(f"  Homeostatic eta: {self.eta_homeo} mV/Hz")
        print(f"  Target rate: {self.target_rate} Hz")
        print(f"  Synaptic decay lambda: {self.lambda_decay}")
        print(f"  Checkpoint interval: every {self.checkpoint_interval} episodes")
        print("=" * 70)

        # Prepare output directories
        if checkpoint_dir is None:
            checkpoint_dir = _DEFAULT_REPORTS_DIR / "checkpoints"
        checkpoint_dir = Path(checkpoint_dir)
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Initialize current weights from initial weights
        self._current_weights = self._initial_weights.copy()

        rewards = []
        weight_stats_list = []
        homeostatic_stats_list = []
        decay_stats_list = []
        firing_rates_list = []
        episode_times = []

        t_total_start = time.time()

        for ep in range(self.n_episodes):
            ep_num = ep + 1
            print(f"\n--- Episode {ep_num}/{self.n_episodes} ---")
            t_ep_start = time.time()

            # Reset and run episode
            self._reset_episode()
            self._run_episode()

            # Compute reward
            reward = self._compute_reward()
            rewards.append(reward)

            # Compute per-neuron firing rates
            firing_rates = self._compute_firing_rates()
            mean_rate = float(np.mean(firing_rates))
            firing_rates_list.append(mean_rate)

            # Update weights via reward-modulated STDP
            w_stats = self._update_weights(reward, rewards)
            weight_stats_list.append(w_stats)

            # Apply homeostatic plasticity (between episodes)
            h_stats = self._apply_homeostatic_plasticity(firing_rates)
            homeostatic_stats_list.append(h_stats)

            # Apply synaptic decay (between episodes)
            d_stats = self._apply_synaptic_decay()
            decay_stats_list.append(d_stats)

            t_ep = time.time() - t_ep_start
            episode_times.append(t_ep)

            # Print episode summary
            print(f"  Reward (forward distance): {reward:.6f} mm")
            print(f"  Mean firing rate: {mean_rate:.1f} Hz "
                  f"(target: {self.target_rate} Hz)")
            print(f"  Dopamine signal: {w_stats['dopamine']:.6f}")
            print(f"  Threshold: mean={h_stats['threshold_mean']:.2f} mV, "
                  f"std={h_stats['threshold_std']:.3f} mV")
            print(f"  Neurons above/below target: "
                  f"{h_stats['neurons_above_target']}/{h_stats['neurons_below_target']}")
            print(f"  Synapses decayed: {d_stats['n_decayed']}/{d_stats['n_total']} "
                  f"({d_stats['fraction_decayed']:.1%})")
            print(f"  Weight: mean={w_stats['weight_mean']:.6f}, "
                  f"std={w_stats['weight_std']:.6f} mV")
            print(f"  Episode wall time: {t_ep:.1f}s")

            # Verify sign constraint
            exc_mask = self._sign_vector[self._sources] > 0
            inh_mask = self._sign_vector[self._sources] < 0
            n_exc_violations = np.sum(self._current_weights[exc_mask] < 0)
            n_inh_violations = np.sum(self._current_weights[inh_mask] > 0)
            if n_exc_violations > 0 or n_inh_violations > 0:
                print(f"  WARNING: Sign violations! exc={n_exc_violations}, "
                      f"inh={n_inh_violations}")

            # Save checkpoint periodically
            if ep_num % self.checkpoint_interval == 0 or ep_num == self.n_episodes:
                ckpt_path = self._save_checkpoint(ep_num, checkpoint_dir)
                print(f"  Checkpoint saved: {ckpt_path.name}")

        total_time = time.time() - t_total_start

        # Final summary
        print(f"\n{'=' * 70}")
        print("TRAINING COMPLETE")
        print(f"{'=' * 70}")
        print(f"  Total episodes: {self.n_episodes}")
        print(f"  Total time: {total_time:.1f}s "
              f"(avg {total_time / self.n_episodes:.1f}s/episode)")
        print(f"\n  Reward stats:")
        print(f"    Mean: {np.mean(rewards):.6f} mm")
        print(f"    Std: {np.std(rewards):.6f} mm")
        print(f"    First half mean: {np.mean(rewards[:len(rewards)//2]):.6f} mm")
        print(f"    Second half mean: {np.mean(rewards[len(rewards)//2:]):.6f} mm")
        print(f"\n  Final threshold stats:")
        print(f"    Mean: {np.mean(self._thresholds_mV):.2f} mV")
        print(f"    Std: {np.std(self._thresholds_mV):.3f} mV")
        print(f"    Range: [{np.min(self._thresholds_mV):.2f}, "
              f"{np.max(self._thresholds_mV):.2f}] mV")
        print(f"\n  Weight change from initial: "
              f"{np.sum(np.abs(self._current_weights - self._initial_weights)):.6f} mV")
        print(f"  Mean absolute weight: "
              f"{np.mean(np.abs(self._current_weights)):.6f} mV")
        print(f"{'=' * 70}")

        return {
            "rewards": rewards,
            "weight_stats": weight_stats_list,
            "homeostatic_stats": homeostatic_stats_list,
            "decay_stats": decay_stats_list,
            "firing_rates": firing_rates_list,
            "episode_times": episode_times,
            "final_weights": self._current_weights.copy(),
            "final_thresholds": self._thresholds_mV.copy(),
            "initial_weights": self._initial_weights.copy(),
        }

    def save_results(self, results, path=None):
        """Save training log to JSON.

        Parameters
        ----------
        results : dict
            Output from train().
        path : str or Path, optional
            Output path. Defaults to reports/training_log.json.

        Returns
        -------
        path : Path
            Path to the saved log file.
        """
        if path is None:
            path = _DEFAULT_REPORTS_DIR / "training_log.json"
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Build serializable log
        log = {
            "config": {
                "n_episodes": self.n_episodes,
                "episode_length_s": self.episode_length_s,
                "coupling_dt_ms": self.coupling_dt_ms,
                "learning_rate": self.learning_rate,
                "tau_stdp_ms": self.tau_stdp_ms,
                "tau_eligibility_s": self.tau_eligibility_s,
                "motor_gain": self.motor_gain,
                "sensory_gain": self.sensory_gain,
                "eta_homeo": self.eta_homeo,
                "target_rate": self.target_rate,
                "lambda_decay": self.lambda_decay,
                "eligibility_decay_threshold": self.eligibility_decay_threshold,
                "topology": self.topology,
                "random_seed": self.random_seed,
            },
            "episodes": [],
        }

        for i in range(len(results["rewards"])):
            episode_entry = {
                "episode": i + 1,
                "reward": results["rewards"][i],
                "mean_firing_rate": results["firing_rates"][i],
                "wall_time_s": results["episode_times"][i],
                "weight_stats": results["weight_stats"][i],
                "homeostatic_stats": results["homeostatic_stats"][i],
                "decay_stats": results["decay_stats"][i],
            }
            log["episodes"].append(episode_entry)

        # Summary statistics
        rewards = results["rewards"]
        log["summary"] = {
            "total_episodes": len(rewards),
            "total_wall_time_s": sum(results["episode_times"]),
            "reward_mean": float(np.mean(rewards)),
            "reward_std": float(np.std(rewards)),
            "reward_first_half_mean": float(np.mean(rewards[:len(rewards)//2])),
            "reward_second_half_mean": float(np.mean(rewards[len(rewards)//2:])),
            "final_threshold_mean": float(np.mean(results["final_thresholds"])),
            "final_threshold_std": float(np.std(results["final_thresholds"])),
            "final_weight_mean": float(np.mean(results["final_weights"])),
            "final_weight_std": float(np.std(results["final_weights"])),
        }

        with open(path, "w") as f:
            json.dump(log, f, indent=2)

        print(f"Training log saved: {path}")
        return path

    def close(self):
        """Clean up resources."""
        if hasattr(self, "_gpu_backend") and self._gpu_backend is not None:
            self._gpu_backend.close()
            self._gpu_backend = None
        if hasattr(self, "_sim") and self._sim is not None:
            self._sim.close()
            self._sim = None


class TrainedController:
    """Controller that uses trained weights from a checkpoint file.

    Conforms to the Controller protocol used by BenchmarkRunner:
    reset(), step(), done (property), get_metrics(), close().
    """

    def __init__(self, checkpoint_path, episode_length_s=5.0):
        """Create a controller using trained weights.

        Parameters
        ----------
        checkpoint_path : str or Path
            Path to .npz checkpoint (with 'weights' and 'thresholds' arrays).
        episode_length_s : float
            Episode duration for evaluation.
        """
        self._checkpoint_path = Path(checkpoint_path)
        self._episode_length_s = episode_length_s

        # Load checkpoint
        ckpt = np.load(self._checkpoint_path)
        self._trained_weights = ckpt["weights"]
        self._trained_thresholds = ckpt["thresholds"]

        self._build()

    def _build(self):
        """Build co-simulation with trained weights and adaptive thresholds."""
        import brian2
        brian2.prefs.codegen.target = "numpy"

        from brian2 import (
            Network, SpikeMonitor, NeuronGroup,
            Hz as brian_Hz, mV as brian_mV, ms as brian_ms,
            Mohm as brian_Mohm, pA,
        )

        from .network import (
            load_sample_data,
            create_poisson_drive,
            create_background_drive,
            DEFAULT_LIF_PARAMS,
        )
        from .constants import NT_SIGN_MAP
        from .locomotion import build_simulation, settle_simulation
        from .sensory_encoder import SensoryEncoder
        from .motor_adapter import SpikeRateDecoder, MotorMapping

        # Load data
        adj, neurons_df = load_sample_data()
        self._n_neurons = adj.shape[0]

        self._motor_neuron_indices = neurons_df[
            neurons_df["superclass"] == "vnc_motor"
        ].index.tolist()
        self._ascending_indices = neurons_df[
            neurons_df["superclass"] == "ascending_neuron"
        ].index.tolist()

        # Build neuron group with adaptive threshold
        params = DEFAULT_LIF_PARAMS
        tau_m = params["tau_m"]
        V_rest = params["V_rest"]
        V_reset = params["V_reset"]
        R_membrane = params["R_membrane"]
        t_refract = params["t_refract"]

        eqs = """
        dv/dt = (-(v - V_rest) + R_membrane * I) / tau_m : volt (unless refractory)
        I : amp
        V_th_adapt : volt
        """

        namespace = {
            "tau_m": tau_m,
            "V_rest": V_rest,
            "V_reset": V_reset,
            "R_membrane": R_membrane,
        }

        G = NeuronGroup(
            self._n_neurons,
            eqs,
            threshold="v > V_th_adapt",
            reset="v = V_reset",
            refractory=t_refract,
            method="euler",
            namespace=namespace,
        )
        G.v = V_rest
        G.V_th_adapt = self._trained_thresholds * brian_mV

        # Build synapses with trained weights (no STDP needed for inference)
        from brian2 import Synapses
        S = Synapses(G, G, "w : volt", on_pre="v_post += w")
        sources, targets = adj.nonzero()
        S.connect(i=sources, j=targets)
        S.w = self._trained_weights * brian_mV

        # Input drives
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
        self._net.store("initial")

        # FlyGym body
        sim, fly, model, data, neutral_ctrl, actuator_names = build_simulation()
        settle_simulation(sim, n_steps=2000)

        self._sim = sim
        self._fly = fly
        self._model = model
        self._data = data
        self._neutral_ctrl = neutral_ctrl
        self._initial_qpos = data.qpos.copy()
        self._initial_qvel = data.qvel.copy()

        flygym_dt_s = model.opt.timestep
        self._flygym_steps_per_coupling = int(2.0 / (flygym_dt_s * 1000))
        self._coupling_dt_ms = 2.0

        # Adapters
        sensory_gain_pa = 500e-12 / 1e-12
        self._encoder = SensoryEncoder(
            self._ascending_indices, n_neurons=self._n_neurons, n_actuated=66,
            gain_pa=sensory_gain_pa, vel_gain_pa=sensory_gain_pa * 0.6,
        )
        self._decoder = SpikeRateDecoder(
            self._motor_neuron_indices, window_ms=50.0, dt_ms=2.0,
        )
        motor_map = MotorMapping(self._motor_neuron_indices)
        self._mapping = motor_map.get_mapping()

        # Episode tracking
        self._n_steps_total = int(self._episode_length_s * 1000 / self._coupling_dt_ms)
        self._step_count = 0
        self._prev_spike_count = 0

        # Trajectory collection
        self._positions = []
        self._headings = []
        self._actions = []

    def reset(self):
        from brian2 import ms as brian_ms, mV as brian_mV, pA
        import mujoco

        self._net.restore("initial")
        self._G.V_th_adapt[:] = self._trained_thresholds * brian_mV

        self._data.qpos[:] = self._initial_qpos
        self._data.qvel[:] = self._initial_qvel
        self._data.ctrl[:] = self._neutral_ctrl
        mujoco.mj_forward(self._model, self._data)

        from .motor_adapter import SpikeRateDecoder
        self._decoder = SpikeRateDecoder(
            self._motor_neuron_indices, window_ms=50.0, dt_ms=2.0,
        )

        # Burn-in
        self._G.I = 0 * pA
        self._net.run(500 * brian_ms)
        self._prev_spike_count = self._M.num_spikes

        self._step_count = 0
        self._positions = []
        self._headings = []
        self._actions = []

        # Initial sensory
        joint_angles = self._sim.get_joint_angles("nmf")
        body_vel = self._data.qvel[0:3].copy()
        self._sensory_currents = self._encoder.encode(joint_angles, body_vel)

        self._record_state()

    def step(self):
        import brian2
        from brian2 import ms as brian_ms, pA
        from flygym.compose import ActuatorType
        from .motor_adapter import decode_spikes_to_positions

        # Inject sensory
        self._G.I = 0 * pA
        for idx in self._ascending_indices:
            self._G.I[idx] = self._sensory_currents[idx] * brian2.amp

        # Run neural
        self._net.run(self._coupling_dt_ms * brian_ms)

        # Decode spikes
        current_spike_count = self._M.num_spikes
        if current_spike_count > self._prev_spike_count:
            new_spike_indices = np.array(self._M.i)[
                self._prev_spike_count:current_spike_count
            ]
            motor_spike_set = set(new_spike_indices) & set(self._motor_neuron_indices)
            self._decoder.update(motor_spike_set)
        else:
            self._decoder.update(set())
        self._prev_spike_count = current_spike_count

        rates = self._decoder.get_rates_hz()

        # Motor output
        action = decode_spikes_to_positions(
            rates, self._mapping, self._neutral_ctrl,
            baseline_hz=15.0, amplitude=0.3,
        )

        for _ in range(self._flygym_steps_per_coupling):
            self._sim.set_actuator_inputs("nmf", ActuatorType.POSITION, action)
            self._sim.step()

        # Sensory feedback
        joint_angles = self._sim.get_joint_angles("nmf")
        body_vel = self._data.qvel[0:3].copy()
        self._sensory_currents = self._encoder.encode(joint_angles, body_vel)

        self._step_count += 1
        self._record_state()

    def _record_state(self):
        self._positions.append(self._data.qpos[0:3].copy())
        quat = self._data.qpos[3:7]
        w, x, y, z = quat
        siny_cosp = 2.0 * (w * z + x * y)
        cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
        self._headings.append(float(np.arctan2(siny_cosp, cosy_cosp)))
        self._actions.append(self._data.ctrl.copy())

    @property
    def done(self):
        return self._step_count >= self._n_steps_total

    def get_metrics(self):
        from .benchmarks.locomotion import compute_locomotion_metrics
        trajectory = {
            "positions": np.array(self._positions),
            "headings": np.array(self._headings),
            "actions": np.array(self._actions),
            "dt": self._coupling_dt_ms / 1000.0,
            "leg_contacts": None,
        }
        return compute_locomotion_metrics(trajectory)

    def close(self):
        if hasattr(self, "_sim") and self._sim is not None:
            self._sim.close()
            self._sim = None


def run_training(episodes=50, episode_length=2.0, topology="biological", backend="cpu"):
    """Run the training harness with homeostatic plasticity and synaptic decay.

    Parameters
    ----------
    episodes : int
        Number of training episodes.
    episode_length : float
        Episode length in seconds.
    topology : str
        "biological" (connectome-derived) or "random" (shuffled weights).
    backend : str
        "cpu" (Brian2) or "gpu" (PyGeNN).
    """
    print(f"\nStarting training harness ({topology} topology, {backend.upper()} backend) "
          f"with {episodes} episodes ({episode_length}s each)...\n")

    harness = TrainingHarness(
        n_episodes=episodes,
        episode_length_s=episode_length,
        coupling_dt_ms=2.0,
        learning_rate=0.001,
        tau_stdp_ms=20.0,
        tau_eligibility_s=1.0,
        motor_gain=0.3,
        sensory_gain=500e-12,
        baseline_window=5,
        eta_homeo=0.01,
        target_rate=25.0,
        lambda_decay=0.001,
        eligibility_decay_threshold=0.01,
        checkpoint_interval=10,
        topology=topology,
        backend=backend,
    )

    # Use topology/backend-specific output paths
    suffix = f"_{topology}" if topology != "biological" else ""
    if backend == "gpu":
        suffix += "_gpu"
    log_path = _DEFAULT_REPORTS_DIR / f"training_log{suffix}.json"
    checkpoint_dir = _DEFAULT_REPORTS_DIR / f"checkpoints{suffix}"

    try:
        results = harness.train(checkpoint_dir=checkpoint_dir)
        harness.save_results(results, path=log_path)
        print(f"\nDone. Training log: {log_path}")
    finally:
        harness.close()


def run_evaluation(checkpoint_path, episodes=3, duration=5.0):
    """Evaluate a trained checkpoint against the untrained baseline.

    Parameters
    ----------
    checkpoint_path : str
        Path to .npz checkpoint.
    episodes : int
        Number of evaluation episodes.
    duration : float
        Episode duration in seconds.
    """
    from .benchmarks.common import BenchmarkRunner
    from .benchmarks.locomotion import BiologicalController

    checkpoint_path = Path(checkpoint_path)
    if not checkpoint_path.exists():
        print(f"Checkpoint not found: {checkpoint_path}")
        return

    print(f"\nEvaluating checkpoint: {checkpoint_path.name}")
    print(f"  Episodes: {episodes}, Duration: {duration}s\n")

    # Run untrained baseline
    print("--- Untrained (connectome weights) ---")
    runner = BenchmarkRunner(
        controller_factory=lambda: BiologicalController(episode_length_s=duration),
        controller_name="untrained",
    )
    untrained_result = runner.run("locomotion", n_episodes=episodes)

    # Run trained controller
    print("\n--- Trained (after STDP + homeostasis) ---")
    runner = BenchmarkRunner(
        controller_factory=lambda: TrainedController(
            checkpoint_path, episode_length_s=duration
        ),
        controller_name="trained",
    )
    trained_result = runner.run("locomotion", n_episodes=episodes)

    # Comparison
    print("\n" + "=" * 60)
    print("BEFORE vs AFTER TRAINING")
    print("=" * 60)
    key_metrics = [
        "forward_speed_mm_per_s",
        "lateral_deviation_mm",
        "energy_efficiency",
        "turn_bias_deg_per_s",
    ]
    for metric in key_metrics:
        before = untrained_result.metrics_mean.get(metric, 0)
        after = trained_result.metrics_mean.get(metric, 0)
        change = after - before
        sign = "+" if change >= 0 else ""
        print(f"  {metric}: {before:.4f} -> {after:.4f} ({sign}{change:.4f})")
    print("=" * 60)


def run_experiment(episodes=50, episode_length=2.0):
    """Run the bio-vs-random topology comparison experiment (Epic 4.3).

    Trains both biological and random-topology networks for the same number of
    episodes, then compares their learning curves and final performance.

    Parameters
    ----------
    episodes : int
        Number of training episodes per condition.
    episode_length : float
        Episode length in seconds.
    """
    print("\n" + "=" * 70)
    print("EXPERIMENT: Biological vs Random Topology Learning")
    print(f"  Episodes per condition: {episodes}")
    print(f"  Episode length: {episode_length}s")
    print("=" * 70)

    results = {}

    for topology in ("biological", "random"):
        print(f"\n{'#' * 70}")
        print(f"# CONDITION: {topology.upper()} TOPOLOGY")
        print(f"{'#' * 70}")

        harness = TrainingHarness(
            n_episodes=episodes,
            episode_length_s=episode_length,
            coupling_dt_ms=2.0,
            learning_rate=0.001,
            tau_stdp_ms=20.0,
            tau_eligibility_s=1.0,
            motor_gain=0.3,
            sensory_gain=500e-12,
            baseline_window=5,
            eta_homeo=0.01,
            target_rate=25.0,
            lambda_decay=0.001,
            eligibility_decay_threshold=0.01,
            checkpoint_interval=10,
            topology=topology,
        )

        suffix = f"_{topology}" if topology != "biological" else ""
        log_path = _DEFAULT_REPORTS_DIR / f"training_log{suffix}.json"
        checkpoint_dir = _DEFAULT_REPORTS_DIR / f"checkpoints{suffix}"

        try:
            result = harness.train(checkpoint_dir=checkpoint_dir)
            harness.save_results(result, path=log_path)
            results[topology] = result
        finally:
            harness.close()

    # Compare learning curves
    print("\n" + "=" * 70)
    print("EXPERIMENT RESULTS: Biological vs Random Topology")
    print("=" * 70)

    bio_rewards = results["biological"]["rewards"]
    rand_rewards = results["random"]["rewards"]

    print(f"\n  Biological topology:")
    print(f"    Mean reward: {np.mean(bio_rewards):.6f} mm")
    print(f"    First half: {np.mean(bio_rewards[:len(bio_rewards)//2]):.6f} mm")
    print(f"    Second half: {np.mean(bio_rewards[len(bio_rewards)//2:]):.6f} mm")
    print(f"    Final 5 episodes: {np.mean(bio_rewards[-5:]):.6f} mm")

    print(f"\n  Random topology:")
    print(f"    Mean reward: {np.mean(rand_rewards):.6f} mm")
    print(f"    First half: {np.mean(rand_rewards[:len(rand_rewards)//2]):.6f} mm")
    print(f"    Second half: {np.mean(rand_rewards[len(rand_rewards)//2:]):.6f} mm")
    print(f"    Final 5 episodes: {np.mean(rand_rewards[-5:]):.6f} mm")

    # Learning speed comparison
    bio_improvement = (
        np.mean(bio_rewards[len(bio_rewards)//2:])
        - np.mean(bio_rewards[:len(bio_rewards)//2])
    )
    rand_improvement = (
        np.mean(rand_rewards[len(rand_rewards)//2:])
        - np.mean(rand_rewards[:len(rand_rewards)//2])
    )

    print(f"\n  Improvement (2nd half - 1st half):")
    print(f"    Biological: {bio_improvement:+.6f} mm")
    print(f"    Random: {rand_improvement:+.6f} mm")

    if bio_improvement > rand_improvement:
        print(f"\n  >> Biological topology shows FASTER learning")
    elif rand_improvement > bio_improvement:
        print(f"\n  >> Random topology shows faster learning (unexpected)")
    else:
        print(f"\n  >> No significant difference in learning speed")

    print("=" * 70)

    # Save comparison results
    comparison = {
        "biological": {
            "rewards": bio_rewards,
            "mean_reward": float(np.mean(bio_rewards)),
            "improvement": float(bio_improvement),
        },
        "random": {
            "rewards": rand_rewards,
            "mean_reward": float(np.mean(rand_rewards)),
            "improvement": float(rand_improvement),
        },
        "config": {
            "episodes": episodes,
            "episode_length_s": episode_length,
        },
    }

    comparison_path = _DEFAULT_REPORTS_DIR / "experiment_comparison.json"
    comparison_path.parent.mkdir(parents=True, exist_ok=True)
    with open(comparison_path, "w") as f:
        json.dump(comparison, f, indent=2)
    print(f"\nComparison saved: {comparison_path}")


def plot_training_log(log_path=None, output_path=None):
    """Generate learning curve plot from a training log JSON.

    Parameters
    ----------
    log_path : str or Path, optional
        Path to training_log.json. Defaults to reports/training_log.json.
    output_path : str or Path, optional
        Output image path. Defaults to reports/learning_curve.png.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if log_path is None:
        log_path = _DEFAULT_REPORTS_DIR / "training_log.json"
    log_path = Path(log_path)

    if output_path is None:
        output_path = log_path.parent / (log_path.stem + "_curve.png")
    output_path = Path(output_path)

    with open(log_path) as f:
        log = json.load(f)

    episodes_data = log["episodes"]
    n_eps = len(episodes_data)
    ep_nums = np.arange(1, n_eps + 1)

    rewards = [e["reward"] for e in episodes_data]
    firing_rates = [e["mean_firing_rate"] for e in episodes_data]
    th_means = [e["homeostatic_stats"]["threshold_mean"] for e in episodes_data]
    th_stds = [e["homeostatic_stats"]["threshold_std"] for e in episodes_data]

    fig, axes = plt.subplots(4, 1, figsize=(10, 12))

    # Panel 1: Reward
    ax = axes[0]
    ax.plot(ep_nums, rewards, "o-", color="tab:blue", linewidth=1.5, markersize=4)
    if n_eps >= 5:
        window = min(5, n_eps)
        rm = np.convolve(rewards, np.ones(window) / window, mode="valid")
        ax.plot(np.arange(window, n_eps + 1), rm, "--", color="tab:red",
                linewidth=2, label=f"{window}-ep running mean")
        ax.legend(fontsize=9)
    ax.set_ylabel("Forward Distance (mm)")
    ax.set_title(f"Training: {log['config'].get('topology', 'biological')} topology")
    ax.grid(True, alpha=0.3)
    ax.axhline(0, color="gray", linestyle=":", alpha=0.5)

    # Panel 2: Firing rate
    ax = axes[1]
    ax.plot(ep_nums, firing_rates, "o-", color="tab:green", linewidth=1.5, markersize=4)
    ax.axhline(log["config"]["target_rate"], color="tab:red", linestyle="--",
               linewidth=1, label=f"target ({log['config']['target_rate']} Hz)")
    ax.set_ylabel("Mean Firing Rate (Hz)")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # Panel 3: Threshold adaptation
    ax = axes[2]
    th_means_arr = np.array(th_means)
    th_stds_arr = np.array(th_stds)
    ax.plot(ep_nums, th_means_arr, "o-", color="tab:purple", linewidth=1.5, markersize=4)
    ax.fill_between(ep_nums, th_means_arr - th_stds_arr, th_means_arr + th_stds_arr,
                    color="tab:purple", alpha=0.2)
    ax.set_ylabel("Threshold Mean ± Std (mV)")
    ax.grid(True, alpha=0.3)

    # Panel 4: Weight stats
    ax = axes[3]
    w_means = [e["weight_stats"]["weight_mean"] for e in episodes_data]
    w_stds = [e["weight_stats"]["weight_std"] for e in episodes_data]
    ax.plot(ep_nums, w_means, "o-", color="tab:orange", linewidth=1.5, markersize=4,
            label="Weight mean")
    ax.plot(ep_nums, w_stds, "s-", color="tab:cyan", linewidth=1, markersize=3,
            alpha=0.7, label="Weight std")
    ax.set_ylabel("Weight (mV)")
    ax.set_xlabel("Episode")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Learning curve plot saved: {output_path}")
    return output_path
