"""Functional training harness: biologically-mapped locomotor network + STDP.

Builds on the existing TrainingHarness but replaces:
  1. 100-hub-neuron sample -> functionally-selected locomotor circuit
     (48 motor neurons + 200 premotor interneurons = 248 neurons)
  2. Round-robin motor mapping -> biological exitNerve-based mapping
     (each motor neuron is mapped to its anatomically correct leg)

The training loop (STDP + homeostatic plasticity + synaptic decay) is
identical to training.py.

Usage
-----
    python -m digital_drosophila learn train_functional [--episodes 50]
"""

import json
import os
import time
from pathlib import Path

import numpy as np

_PACKAGE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _PACKAGE_DIR.parent.parent
_DEFAULT_REPORTS_DIR = _PROJECT_ROOT / "reports"


class FunctionalTrainingHarness:
    """Training harness using biologically-mapped locomotor circuit.

    Identical training algorithm to TrainingHarness (STDP + homeostatic
    plasticity + synaptic decay), but uses:
      - Functionally-selected neurons (motor + premotor from connectome)
      - Biological motor mapping (exitNerve → leg)
      - Per-leg actuator pooling (motor neurons targeting the same leg
        contribute to a per-leg average rate)

    Parameters
    ----------
    n_episodes : int
    episode_length_s : float
    coupling_dt_ms : float
    learning_rate : float
    tau_stdp_ms : float
    tau_eligibility_s : float
    motor_gain : float
    sensory_gain : float
    baseline_window : int
    eta_homeo : float
    target_rate : float
    lambda_decay : float
    eligibility_decay_threshold : float
    checkpoint_interval : int
    random_seed : int
    force_rebuild : bool
        If True, re-query neuPrint even if a cached snapshot exists.
    n_hops : int
        Number of upstream hops for neuron selection (default 2).
    backend : str
        Neural simulator backend: "gpu" (PyGeNN, default) or "cpu" (Brian2).
        Falls back to "cpu" automatically if GPU is unavailable.
    reward_mode : str
        Reward delivery mode: "episodic" (default, single reward at episode
        end) or "continuous" (reward at every coupling step based on
        instantaneous forward velocity, weight updates batched every
        ``continuous_update_interval`` steps).
    continuous_update_interval : int
        For continuous reward mode: how many coupling steps between weight
        updates (default 50, i.e. every 100 ms at 2 ms/step).
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
        random_seed=42,
        force_rebuild=False,
        n_hops=2,
        backend="gpu",
        reward_mode="episodic",
        continuous_update_interval=50,
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
        self.random_seed = random_seed
        self.force_rebuild = force_rebuild
        self.n_hops = n_hops
        if reward_mode not in ("episodic", "continuous"):
            raise ValueError(
                f"reward_mode must be 'episodic' or 'continuous', got {reward_mode!r}"
            )
        self.reward_mode = reward_mode
        self.continuous_update_interval = continuous_update_interval

        # Resolve backend — fall back to cpu if GPU unavailable
        if backend == "gpu":
            try:
                import pygenn  # noqa: F401
                self._backend_type = "gpu"
            except ImportError:
                print("[FunctionalTrainingHarness] pygenn not available, "
                      "falling back to CPU (Brian2)")
                self._backend_type = "cpu"
        else:
            self._backend_type = "cpu"

        os.environ.setdefault("MUJOCO_GL", "egl")
        if self._backend_type == "gpu":
            self._build_gpu()
        else:
            self._build()

    def _build(self):
        """Build functional network + Brian2 + FlyGym."""
        import brian2
        brian2.prefs.codegen.target = "numpy"

        from brian2 import (
            Network, SpikeMonitor, PoissonGroup, Synapses, NeuronGroup,
            Hz as brian_Hz, mV as brian_mV, ms as brian_ms,
            second as brian_second, Mohm as brian_Mohm, pA,
        )
        from .network import DEFAULT_LIF_PARAMS
        from .constants import NT_SIGN_MAP
        from .locomotion import build_simulation, settle_simulation
        from .sensory_encoder import SensoryEncoder
        from .motor_adapter import SpikeRateDecoder
        from .functional_selection import get_or_build_network, build_motor_actuator_map

        # ------------------------------------------------------------------
        # Load functional network
        # ------------------------------------------------------------------
        print(f"[build] Loading functional locomotor network ({self.n_hops} hop(s))...")
        (self._body_ids, self._meta_df, self._motor_leg_map,
         sources_coo, targets_coo, weights_coo) = get_or_build_network(
            force_rebuild=self.force_rebuild,
            n_hops=self.n_hops,
        )

        self._n_neurons = len(self._body_ids)
        bid_to_idx = {int(bid): i for i, bid in enumerate(self._body_ids)}

        # Motor neuron network indices
        self._motor_neuron_indices = [
            bid_to_idx[int(bid)]
            for bid in self._motor_leg_map.keys()
            if int(bid) in bid_to_idx
        ]

        # Ascending neuron network indices
        self._ascending_indices = self._meta_df[
            self._meta_df["superclass"] == "ascending_neuron"
        ].index.tolist()
        # Re-map ascending indices to position in body_ids list
        ascending_bids = self._meta_df[
            self._meta_df["superclass"] == "ascending_neuron"
        ]["bodyId"].values
        self._ascending_indices = [
            bid_to_idx[int(bid)]
            for bid in ascending_bids
            if int(bid) in bid_to_idx
        ]

        # Descending neuron indices (for targeted Poisson drive)
        descending_bids = self._meta_df[
            self._meta_df["superclass"] == "descending_neuron"
        ]["bodyId"].values
        self._descending_indices = [
            bid_to_idx[int(bid)]
            for bid in descending_bids
            if int(bid) in bid_to_idx
        ]

        print(f"[build] Network: {self._n_neurons} neurons "
              f"({len(self._motor_neuron_indices)} motor, "
              f"{len(self._ascending_indices)} ascending, "
              f"{len(self._descending_indices)} descending)")

        # ------------------------------------------------------------------
        # Build sign vector from neurotransmitter types
        # ------------------------------------------------------------------
        nt_series = self._meta_df["consensusNt"].fillna("unknown")
        confidence = self._meta_df["predictedNtConfidence"].fillna(0.5).values
        self._sign_vector = np.array(
            [NT_SIGN_MAP.get(nt, 0) or 0 for nt in nt_series]
        )
        self._confidence = confidence

        # ------------------------------------------------------------------
        # Build NeuronGroup with adaptive threshold
        # ------------------------------------------------------------------
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
        G.V_th_adapt = -50 * brian_mV
        self._thresholds_mV = np.full(self._n_neurons, -50.0)

        # ------------------------------------------------------------------
        # Build STDP synapses
        # ------------------------------------------------------------------
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

        S = Synapses(G, G, model=stdp_model, on_pre=stdp_pre, on_post=stdp_post,
                     namespace=syn_namespace)

        # Connect using COO sparse adjacency
        S.connect(i=sources_coo, j=targets_coo)

        # Set initial weights using sign-constrained formula
        inh_attenuation = 0.5
        scale = 0.6
        sign_scale = np.where(
            self._sign_vector[sources_coo] >= 0, 1.0, inh_attenuation
        )
        weights_raw = (
            np.log1p(weights_coo)
            * self._sign_vector[sources_coo]
            * confidence[sources_coo]
            * sign_scale
            * scale
        )
        S.w = weights_raw * brian_mV

        self._S = S
        self._sources = sources_coo
        self._targets = targets_coo
        self._initial_weights = weights_raw.copy()

        # ------------------------------------------------------------------
        # Input drives
        # ------------------------------------------------------------------
        # Drive descending neurons (top-down command signal)
        n_desc = len(self._descending_indices)
        if n_desc > 0:
            n_pg = min(15, n_desc)
            PG_desc = PoissonGroup(n_pg, rates=10 * brian_Hz)
            S_desc = Synapses(PG_desc, G, on_pre="v_post += 2.0*mV")
            pg_i = np.repeat(np.arange(n_pg), n_desc)
            pg_j = np.tile(self._descending_indices, n_pg)
            S_desc.connect(i=pg_i, j=pg_j)
            self._PG_desc = PG_desc
            self._S_desc = S_desc
        else:
            self._PG_desc = None
            self._S_desc = None

        # Background drive (compensates for missing network context)
        PG_bg = PoissonGroup(50, rates=22 * brian_Hz)
        S_bg = Synapses(PG_bg, G, on_pre="v_post += 1.3*mV")
        bg_i = np.repeat(np.arange(50), self._n_neurons)
        bg_j = np.tile(np.arange(self._n_neurons), 50)
        S_bg.connect(i=bg_i, j=bg_j)
        self._PG_bg = PG_bg
        self._S_bg = S_bg

        M = SpikeMonitor(G)

        # Assemble network
        net_objects = [G, S, PG_bg, S_bg, M]
        if self._PG_desc is not None:
            net_objects.extend([self._PG_desc, self._S_desc])
        self._net = Network(*net_objects)
        self._G = G
        self._M = M
        self._net.store("initial")

        # ------------------------------------------------------------------
        # FlyGym body
        # ------------------------------------------------------------------
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

        # ------------------------------------------------------------------
        # Adapters
        # ------------------------------------------------------------------
        sensory_gain_pa = self.sensory_gain / 1e-12
        self._encoder = SensoryEncoder(
            self._ascending_indices,
            n_neurons=self._n_neurons,
            n_actuated=66,
            gain_pa=sensory_gain_pa,
            vel_gain_pa=sensory_gain_pa * 0.6,
        )
        self._decoder = SpikeRateDecoder(
            self._motor_neuron_indices,
            window_ms=50.0,
            dt_ms=self.coupling_dt_ms,
        )

        # Biological motor mapping: network_index -> list of actuator indices
        self._motor_actuator_map = build_motor_actuator_map(
            self._motor_leg_map, self._body_ids
        )

        print(f"[build] Motor actuator map: {len(self._motor_actuator_map)} neurons "
              f"each driving up to 3 actuators")

        print("[build] Done.")

    def _build_gpu(self):
        """Build functional network + PyGeNN GPU backend + FlyGym."""
        import scipy.sparse as sp

        from .constants import NT_SIGN_MAP
        from .locomotion import build_simulation, settle_simulation
        from .sensory_encoder import SensoryEncoder
        from .motor_adapter import SpikeRateDecoder
        from .functional_selection import get_or_build_network, build_motor_actuator_map
        from .gpu_backend import PyGeNNBackend

        # ------------------------------------------------------------------
        # Load functional network
        # ------------------------------------------------------------------
        print(f"[build_gpu] Loading functional locomotor network ({self.n_hops} hop(s))...")
        (self._body_ids, self._meta_df, self._motor_leg_map,
         sources_coo, targets_coo, weights_coo) = get_or_build_network(
            force_rebuild=self.force_rebuild,
            n_hops=self.n_hops,
        )

        self._n_neurons = len(self._body_ids)
        bid_to_idx = {int(bid): i for i, bid in enumerate(self._body_ids)}

        # Motor neuron network indices
        self._motor_neuron_indices = [
            bid_to_idx[int(bid)]
            for bid in self._motor_leg_map.keys()
            if int(bid) in bid_to_idx
        ]

        # Ascending neuron network indices
        ascending_bids = self._meta_df[
            self._meta_df["superclass"] == "ascending_neuron"
        ]["bodyId"].values
        self._ascending_indices = [
            bid_to_idx[int(bid)]
            for bid in ascending_bids
            if int(bid) in bid_to_idx
        ]

        # Descending neuron indices (for extra background current)
        descending_bids = self._meta_df[
            self._meta_df["superclass"] == "descending_neuron"
        ]["bodyId"].values
        self._descending_indices = [
            bid_to_idx[int(bid)]
            for bid in descending_bids
            if int(bid) in bid_to_idx
        ]

        print(f"[build_gpu] Network: {self._n_neurons} neurons "
              f"({len(self._motor_neuron_indices)} motor, "
              f"{len(self._ascending_indices)} ascending, "
              f"{len(self._descending_indices)} descending)")

        # ------------------------------------------------------------------
        # Build sign vector from neurotransmitter types
        # ------------------------------------------------------------------
        nt_series = self._meta_df["consensusNt"].fillna("unknown")
        confidence = self._meta_df["predictedNtConfidence"].fillna(0.5).values
        self._sign_vector = np.array(
            [NT_SIGN_MAP.get(nt, 0) or 0 for nt in nt_series]
        )
        self._confidence = confidence

        self._sources = sources_coo
        self._targets = targets_coo

        # ------------------------------------------------------------------
        # Compute initial weights (same formula as CPU path)
        # ------------------------------------------------------------------
        inh_attenuation = 0.5
        scale = 0.6
        sign_scale = np.where(
            self._sign_vector[sources_coo] >= 0, 1.0, inh_attenuation
        )
        weights_raw = (
            np.log1p(weights_coo)
            * self._sign_vector[sources_coo]
            * confidence[sources_coo]
            * sign_scale
            * scale
        )

        self._initial_weights = weights_raw.copy()
        self._thresholds_mV = np.full(self._n_neurons, -50.0)

        # ------------------------------------------------------------------
        # Build PyGeNN backend
        # ------------------------------------------------------------------
        adj_sparse = sp.coo_matrix(
            (np.ones(len(sources_coo)), (sources_coo, targets_coo)),
            shape=(self._n_neurons, self._n_neurons),
        )

        print("[build_gpu] Building PyGeNN GPU backend (CUDA compilation)...")
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
        print("[build_gpu] PyGeNN backend ready.")

        # ------------------------------------------------------------------
        # FlyGym body
        # ------------------------------------------------------------------
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

        # ------------------------------------------------------------------
        # Adapters
        # ------------------------------------------------------------------
        sensory_gain_pa = self.sensory_gain / 1e-12
        self._encoder = SensoryEncoder(
            self._ascending_indices,
            n_neurons=self._n_neurons,
            n_actuated=66,
            gain_pa=sensory_gain_pa,
            vel_gain_pa=sensory_gain_pa * 0.6,
        )
        self._decoder = SpikeRateDecoder(
            self._motor_neuron_indices,
            window_ms=50.0,
            dt_ms=self.coupling_dt_ms,
        )

        # Biological motor mapping: network_index -> list of actuator indices
        self._motor_actuator_map = build_motor_actuator_map(
            self._motor_leg_map, self._body_ids
        )

        print(f"[build_gpu] Motor actuator map: {len(self._motor_actuator_map)} neurons "
              f"each driving up to 3 actuators")
        print("[build_gpu] Done.")

    def _decode_biological(self, rates_hz: dict[int, float]) -> np.ndarray:
        """Convert motor neuron spike rates to actuator positions using biological mapping.

        Each motor neuron contributes to specific actuators on its leg.
        Multiple motor neurons targeting the same actuator have their offsets
        averaged.

        Parameters
        ----------
        rates_hz : dict[int, float]
            Network index → firing rate (Hz) for each motor neuron.

        Returns
        -------
        action : ndarray (66,)
            Actuator position commands.
        """
        action = self._neutral_ctrl.copy()
        # Accumulate offsets per actuator
        actuator_offsets = {}
        actuator_counts = {}

        baseline_hz = 15.0
        amplitude = self.motor_gain

        for net_idx, actuator_list in self._motor_actuator_map.items():
            rate = rates_hz.get(net_idx, 0.0)
            offset = (rate - baseline_hz) / max(baseline_hz, 1.0) * amplitude
            offset = float(np.clip(offset, -amplitude, amplitude))
            for act_idx in actuator_list:
                actuator_offsets[act_idx] = actuator_offsets.get(act_idx, 0.0) + offset
                actuator_counts[act_idx] = actuator_counts.get(act_idx, 0) + 1

        # Average contributions and apply
        for act_idx, total_offset in actuator_offsets.items():
            count = actuator_counts[act_idx]
            action[act_idx] += total_offset / count

        return action

    def _reset_episode(self):
        """Reset network and body for a new episode."""
        if self._backend_type == "gpu":
            return self._reset_episode_gpu()

        import brian2
        from brian2 import ms as brian_ms, mV as brian_mV, pA
        from .motor_adapter import SpikeRateDecoder

        # Restore Brian2 network to initial state, then apply current weights
        self._net.restore("initial")
        self._S.w = self._current_weights * brian_mV
        self._G.V_th_adapt = self._thresholds_mV * brian_mV

        # Reset body
        self._data.qpos[:] = self._initial_qpos
        self._data.qvel[:] = self._initial_qvel
        self._data.ctrl[:] = self._neutral_ctrl
        import mujoco
        mujoco.mj_forward(self._model, self._data)

        # Reset decoder
        self._decoder = SpikeRateDecoder(
            self._motor_neuron_indices,
            window_ms=50.0,
            dt_ms=self.coupling_dt_ms,
        )

        # Burn-in (500ms, no sensory input)
        self._G.I = 0 * pA
        self._net.run(500.0 * brian_ms)

        self._prev_spike_count = self._M.num_spikes

        # Record per-neuron spike counts at episode start
        if self._M.num_spikes > 0:
            spike_indices = np.array(self._M.i[:])
            self._episode_spike_start = np.bincount(
                spike_indices, minlength=self._n_neurons
            ).astype(float)
        else:
            self._episode_spike_start = np.zeros(self._n_neurons)

        self._episode_start_pos = self._data.qpos[0:3].copy()

        joint_angles = self._sim.get_joint_angles("nmf")
        body_vel = self._data.qvel[0:3].copy()
        self._sensory_currents = self._encoder.encode(joint_angles, body_vel)

    def _reset_episode_gpu(self):
        """Reset GPU backend and body for a new episode."""
        import mujoco
        from .motor_adapter import SpikeRateDecoder

        # Reset GPU backend with current weights and thresholds
        self._gpu_backend.reset(self._current_weights, self._thresholds_mV)

        # Build background tonic current:
        # 180 pA for all neurons, +30 pA for descending neurons.
        bg_current_pA = 180.0
        descending_extra_pA = 30.0
        self._gpu_bg_currents = np.full(self._n_neurons, bg_current_pA, dtype=np.float32)
        self._gpu_bg_currents[self._descending_indices] += descending_extra_pA

        # Run burn-in on GPU (250 coupling steps = 500ms at 2ms/step)
        burn_in_steps = int(500.0 / self.coupling_dt_ms)
        for _ in range(burn_in_steps):
            self._gpu_backend.step(self._gpu_bg_currents)

        # Reset spike counts after burn-in
        self._gpu_backend._spike_counts[:] = 0

        # Reset body
        self._data.qpos[:] = self._initial_qpos
        self._data.qvel[:] = self._initial_qvel
        self._data.ctrl[:] = self._neutral_ctrl
        mujoco.mj_forward(self._model, self._data)

        # Reset decoder
        self._decoder = SpikeRateDecoder(
            self._motor_neuron_indices,
            window_ms=50.0,
            dt_ms=self.coupling_dt_ms,
        )

        self._episode_start_pos = self._data.qpos[0:3].copy()

        joint_angles = self._sim.get_joint_angles("nmf")
        body_vel = self._data.qvel[0:3].copy()
        self._sensory_currents = self._encoder.encode(joint_angles, body_vel)

    def _run_episode(self):
        """Run one closed-loop episode."""
        if self._backend_type == "gpu":
            if self.reward_mode == "continuous":
                return self._run_episode_gpu_continuous()
            return self._run_episode_gpu()

        import brian2
        from brian2 import ms as brian_ms, pA
        from flygym.compose import ActuatorType

        n_steps = int(self.episode_length_s * 1000 / self.coupling_dt_ms)

        for _step in range(n_steps):
            # 1. Inject sensory currents into ascending neurons
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

            # 4. Biological motor decoding
            action = self._decode_biological(rates)

            for _ in range(self._flygym_steps_per_coupling):
                self._sim.set_actuator_inputs("nmf", ActuatorType.POSITION, action)
                self._sim.step()

            # 5. Read sensors
            joint_angles = self._sim.get_joint_angles("nmf")
            body_vel = self._data.qvel[0:3].copy()
            self._sensory_currents = self._encoder.encode(joint_angles, body_vel)

    def _run_episode_gpu(self):
        """Run one closed-loop episode using the GPU backend."""
        from flygym.compose import ActuatorType

        n_steps = int(self.episode_length_s * 1000 / self.coupling_dt_ms)

        for _step in range(n_steps):
            # 1. Step GPU neural simulation with sensory + background currents
            # Sensory currents from encoder are in Amps; convert to pA (×1e12)
            sensory_pA = self._sensory_currents * 1e12
            combined_currents = sensory_pA + self._gpu_bg_currents
            motor_spikes = self._gpu_backend.step(combined_currents)

            # 2. Decode motor spikes
            self._decoder.update(motor_spikes)
            rates = self._decoder.get_rates_hz()

            # 3. Biological motor decoding
            action = self._decode_biological(rates)

            for _ in range(self._flygym_steps_per_coupling):
                self._sim.set_actuator_inputs("nmf", ActuatorType.POSITION, action)
                self._sim.step()

            # 4. Read sensors
            joint_angles = self._sim.get_joint_angles("nmf")
            body_vel = self._data.qvel[0:3].copy()
            self._sensory_currents = self._encoder.encode(joint_angles, body_vel)

    def _run_episode_gpu_continuous(self):
        """Run one closed-loop episode with continuous per-step reward and weight updates.

        Instead of accumulating eligibility traces for a single end-of-episode
        weight update, this method updates weights every
        ``continuous_update_interval`` coupling steps using the instantaneous
        forward displacement as a reward signal.  The effective per-step
        learning rate is scaled down by ``continuous_update_interval`` so that
        the total weight change per episode remains comparable to episodic mode.

        Side-effects
        ------------
        - ``self._current_weights`` is modified in-place throughout the episode.
        - ``self._reward_baseline`` is maintained as an exponential moving
          average across steps (initialised on first use).
        - ``self._episode_total_displacement`` records the total forward
          displacement for logging.
        """
        from flygym.compose import ActuatorType

        n_steps = int(self.episode_length_s * 1000 / self.coupling_dt_ms)

        # Initialise running reward baseline (EMA) on first episode
        if not hasattr(self, "_reward_baseline"):
            self._reward_baseline = 0.0

        # Effective lr per update batch: divide by interval so total update
        # magnitude stays comparable to a single episodic update.
        # Also divide by 10 extra for safety (many more total updates than
        # episodic: n_steps / interval updates per episode).
        n_batches_per_episode = max(1, n_steps // self.continuous_update_interval)
        effective_lr = self.learning_rate / n_batches_per_episode

        # Track position for per-step reward
        prev_x = float(self._data.qpos[0])
        accumulated_dw = np.zeros_like(self._current_weights)
        steps_since_update = 0
        total_displacement = 0.0

        for _step in range(n_steps):
            # 1. Step GPU neural simulation
            sensory_pA = self._sensory_currents * 1e12
            combined_currents = sensory_pA + self._gpu_bg_currents
            motor_spikes = self._gpu_backend.step(combined_currents)

            # 2. Decode motor spikes
            self._decoder.update(motor_spikes)
            rates = self._decoder.get_rates_hz()

            # 3. Biological motor decoding
            action = self._decode_biological(rates)

            for _ in range(self._flygym_steps_per_coupling):
                self._sim.set_actuator_inputs("nmf", ActuatorType.POSITION, action)
                self._sim.step()

            # 4. Read sensors
            joint_angles = self._sim.get_joint_angles("nmf")
            body_vel = self._data.qvel[0:3].copy()
            self._sensory_currents = self._encoder.encode(joint_angles, body_vel)

            # 5. Compute instantaneous reward (forward displacement this step)
            current_x = float(self._data.qpos[0])
            instant_reward = current_x - prev_x
            prev_x = current_x
            total_displacement += instant_reward

            # 6. Accumulate weighted eligibility contribution
            # Pull eligibility every step — it is updated each coupling step
            # by the STDP rule, so pulling it here captures the current trace.
            eligibility = self._gpu_backend.get_eligibility()
            reward_error = instant_reward - self._reward_baseline
            accumulated_dw += effective_lr * eligibility * reward_error

            # Update EMA baseline
            self._reward_baseline = (
                0.99 * self._reward_baseline + 0.01 * instant_reward
            )

            steps_since_update += 1

            # 7. Batch weight update every continuous_update_interval steps
            if steps_since_update >= self.continuous_update_interval:
                self._current_weights = self._current_weights + accumulated_dw

                # Enforce Dale's principle
                exc_mask = self._sign_vector[self._sources] > 0
                inh_mask = self._sign_vector[self._sources] < 0
                self._current_weights[exc_mask] = np.maximum(
                    self._current_weights[exc_mask], 0.0
                )
                self._current_weights[inh_mask] = np.minimum(
                    self._current_weights[inh_mask], 0.0
                )

                # Apply updated weights to GPU backend for next batch
                # (convert mV -> nA as PyGeNN uses nA internally)
                weights_nA = (
                    self._current_weights * self._gpu_backend._MV_TO_NA
                ).astype(np.float32)
                self._gpu_backend._syn.vars["g"].values = weights_nA
                self._gpu_backend._syn.vars["g"].push_to_device()

                accumulated_dw[:] = 0.0
                steps_since_update = 0

        # Flush any remaining accumulated updates
        if steps_since_update > 0 and np.any(accumulated_dw != 0):
            self._current_weights = self._current_weights + accumulated_dw
            exc_mask = self._sign_vector[self._sources] > 0
            inh_mask = self._sign_vector[self._sources] < 0
            self._current_weights[exc_mask] = np.maximum(
                self._current_weights[exc_mask], 0.0
            )
            self._current_weights[inh_mask] = np.minimum(
                self._current_weights[inh_mask], 0.0
            )

        # Store for reporting
        self._episode_total_displacement = total_displacement

    def _compute_firing_rates(self) -> np.ndarray:
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
        return episode_spikes / self.episode_length_s

    def _compute_reward(self) -> float:
        current_pos = self._data.qpos[0:3].copy()
        return float(current_pos[0] - self._episode_start_pos[0])

    def _update_weights(self, reward: float, rewards_history: list[float]) -> dict:
        if len(rewards_history) >= 2:
            recent = rewards_history[-min(self.baseline_window, len(rewards_history)):]
            baseline = float(np.mean(recent))
        else:
            baseline = 0.0
        dopamine = reward - baseline

        if self._backend_type == "gpu":
            eligibility = self._gpu_backend.get_eligibility()
        else:
            eligibility = np.array(self._S.eligibility[:])
        dw = self.learning_rate * eligibility * dopamine
        self._current_weights = self._current_weights + dw

        # Enforce Dale's principle
        exc_mask = self._sign_vector[self._sources] > 0
        inh_mask = self._sign_vector[self._sources] < 0
        self._current_weights[exc_mask] = np.maximum(
            self._current_weights[exc_mask], 0.0
        )
        self._current_weights[inh_mask] = np.minimum(
            self._current_weights[inh_mask], 0.0
        )

        return {
            "dopamine": dopamine,
            "mean_eligibility": float(np.mean(np.abs(eligibility))),
            "mean_abs_dw": float(np.mean(np.abs(dw))),
            "max_abs_dw": float(np.max(np.abs(dw))),
            "weight_mean": float(np.mean(self._current_weights)),
            "weight_std": float(np.std(self._current_weights)),
        }

    def _apply_homeostatic_plasticity(self, firing_rates: np.ndarray) -> dict:
        rate_deviation = firing_rates - self.target_rate
        delta_th = self.eta_homeo * rate_deviation
        self._thresholds_mV = np.clip(
            self._thresholds_mV + delta_th, -70.0, -30.0
        )
        return {
            "threshold_mean": float(np.mean(self._thresholds_mV)),
            "threshold_std": float(np.std(self._thresholds_mV)),
            "threshold_min": float(np.min(self._thresholds_mV)),
            "threshold_max": float(np.max(self._thresholds_mV)),
            "mean_rate_deviation": float(np.mean(np.abs(rate_deviation))),
            "neurons_above_target": int(np.sum(firing_rates > self.target_rate)),
            "neurons_below_target": int(np.sum(firing_rates < self.target_rate)),
        }

    def _apply_synaptic_decay(self) -> dict:
        if self._backend_type == "gpu":
            eligibility = self._gpu_backend.get_eligibility()
        else:
            eligibility = np.array(self._S.eligibility[:])
        inactive_mask = np.abs(eligibility) < self.eligibility_decay_threshold
        self._current_weights[inactive_mask] *= (1.0 - self.lambda_decay)

        exc_mask = self._sign_vector[self._sources] > 0
        inh_mask = self._sign_vector[self._sources] < 0
        self._current_weights[exc_mask] = np.maximum(
            self._current_weights[exc_mask], 0.0
        )
        self._current_weights[inh_mask] = np.minimum(
            self._current_weights[inh_mask], 0.0
        )

        n_decayed = int(np.sum(inactive_mask))
        n_total = len(self._current_weights)
        return {
            "n_decayed": n_decayed,
            "n_total": n_total,
            "fraction_decayed": float(n_decayed / n_total) if n_total > 0 else 0.0,
            "mean_abs_weight_after": float(np.mean(np.abs(self._current_weights))),
        }

    def _save_checkpoint(self, episode: int, checkpoint_dir: Path) -> Path:
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        path = checkpoint_dir / f"functional_weights_ep{episode:04d}.npz"
        np.savez_compressed(
            path,
            weights=self._current_weights,
            thresholds=self._thresholds_mV,
            body_ids=np.array(self._body_ids, dtype=np.int64),
            episode=episode,
        )
        return path

    def train(self, checkpoint_dir=None) -> dict:
        """Run the full training loop.

        Returns
        -------
        dict
            Keys: rewards, weight_stats, homeostatic_stats, decay_stats,
            firing_rates, episode_times, final_weights, final_thresholds.
        """
        print("=" * 70)
        print("Functional Training Harness: Biological Locomotor Circuit")
        print(f"  Backend: {self._backend_type.upper()}")
        print(f"  Reward mode: {self.reward_mode.upper()}")
        print(f"  Hops: {self.n_hops}")
        print(f"  Neurons: {self._n_neurons} "
              f"({len(self._motor_neuron_indices)} motor + "
              f"{len(self._ascending_indices)} ascending + premotor)")
        print(f"  Connections: {len(self._sources)}")
        print(f"  Episodes: {self.n_episodes}")
        print(f"  Episode length: {self.episode_length_s}s")
        print(f"  Learning rate: {self.learning_rate} mV")
        if self.reward_mode == "continuous":
            print(f"  Continuous update interval: {self.continuous_update_interval} steps "
                  f"(every {self.continuous_update_interval * self.coupling_dt_ms:.0f} ms)")
        print(f"  STDP tau: {self.tau_stdp_ms} ms")
        print(f"  Homeostatic eta: {self.eta_homeo} mV/Hz")
        print(f"  Target rate: {self.target_rate} Hz")
        print("=" * 70)

        if checkpoint_dir is None:
            checkpoint_dir = _DEFAULT_REPORTS_DIR / "checkpoints_functional"
        checkpoint_dir = Path(checkpoint_dir)
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

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

            self._reset_episode()
            self._run_episode()

            # In continuous mode, total displacement is tracked inside
            # _run_episode_gpu_continuous(); weight update already done.
            if self.reward_mode == "continuous":
                reward = float(getattr(self, "_episode_total_displacement", 0.0))
                # Build a minimal weight stats dict for logging
                w_stats = {
                    "dopamine": float(getattr(self, "_reward_baseline", 0.0)),
                    "mean_eligibility": float("nan"),
                    "mean_abs_dw": float("nan"),
                    "max_abs_dw": float("nan"),
                    "weight_mean": float(np.mean(self._current_weights)),
                    "weight_std": float(np.std(self._current_weights)),
                }
            else:
                reward = self._compute_reward()
                w_stats = self._update_weights(reward, rewards)

            rewards.append(reward)

            firing_rates = self._compute_firing_rates()
            mean_rate = float(np.mean(firing_rates))
            firing_rates_list.append(mean_rate)

            weight_stats_list.append(w_stats)

            h_stats = self._apply_homeostatic_plasticity(firing_rates)
            homeostatic_stats_list.append(h_stats)

            d_stats = self._apply_synaptic_decay()
            decay_stats_list.append(d_stats)

            t_ep = time.time() - t_ep_start
            episode_times.append(t_ep)

            print(f"  Reward (forward distance): {reward:.4f} mm")
            print(f"  Mean firing rate: {mean_rate:.1f} Hz "
                  f"(target: {self.target_rate} Hz)")
            if self.reward_mode == "continuous":
                print(f"  Reward baseline (EMA): {w_stats['dopamine']:.6f}")
            else:
                print(f"  Dopamine signal: {w_stats['dopamine']:.4f}")
            print(f"  Threshold: mean={h_stats['threshold_mean']:.2f} mV, "
                  f"std={h_stats['threshold_std']:.3f} mV")
            print(f"  Episode wall time: {t_ep:.1f}s")

            if ep_num % self.checkpoint_interval == 0 or ep_num == self.n_episodes:
                ckpt_path = self._save_checkpoint(ep_num, checkpoint_dir)
                print(f"  Checkpoint saved: {ckpt_path.name}")

        total_time = time.time() - t_total_start

        print(f"\n{'=' * 70}")
        print("FUNCTIONAL TRAINING COMPLETE")
        print(f"{'=' * 70}")
        print(f"  Total episodes: {self.n_episodes}")
        print(f"  Total time: {total_time:.1f}s "
              f"(avg {total_time / self.n_episodes:.1f}s/episode)")
        print(f"\n  Reward stats:")
        print(f"    Mean: {np.mean(rewards):.4f} mm")
        print(f"    Std: {np.std(rewards):.4f} mm")
        print(f"    First half mean: {np.mean(rewards[:len(rewards)//2]):.4f} mm")
        print(f"    Second half mean: {np.mean(rewards[len(rewards)//2:]):.4f} mm")
        print(f"    Best episode: {np.max(rewards):.4f} mm")
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
            "n_neurons": self._n_neurons,
            "n_motor": len(self._motor_neuron_indices),
            "n_connections": len(self._sources),
        }

    def save_results(self, results: dict, path=None) -> Path:
        if path is None:
            path = _DEFAULT_REPORTS_DIR / "functional_training_log.json"
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        log = {
            "config": {
                "n_neurons": self._n_neurons,
                "n_motor": len(self._motor_neuron_indices),
                "n_connections": len(self._sources),
                "n_episodes": self.n_episodes,
                "episode_length_s": self.episode_length_s,
                "learning_rate": self.learning_rate,
                "tau_stdp_ms": self.tau_stdp_ms,
                "tau_eligibility_s": self.tau_eligibility_s,
                "motor_gain": self.motor_gain,
                "sensory_gain": self.sensory_gain,
                "eta_homeo": self.eta_homeo,
                "target_rate": self.target_rate,
                "lambda_decay": self.lambda_decay,
                "reward_mode": self.reward_mode,
                "continuous_update_interval": self.continuous_update_interval,
                "mode": "functional_biological",
            },
            "episodes": [],
        }

        for i in range(len(results["rewards"])):
            log["episodes"].append({
                "episode": i + 1,
                "reward": results["rewards"][i],
                "mean_firing_rate": results["firing_rates"][i],
                "wall_time_s": results["episode_times"][i],
                "weight_stats": results["weight_stats"][i],
                "homeostatic_stats": results["homeostatic_stats"][i],
                "decay_stats": results["decay_stats"][i],
            })

        rw = results["rewards"]
        log["summary"] = {
            "total_episodes": len(rw),
            "total_wall_time_s": sum(results["episode_times"]),
            "reward_mean": float(np.mean(rw)),
            "reward_std": float(np.std(rw)),
            "reward_first_half_mean": float(np.mean(rw[:len(rw)//2])),
            "reward_second_half_mean": float(np.mean(rw[len(rw)//2:])),
            "reward_best": float(np.max(rw)),
        }

        with open(path, "w") as f:
            json.dump(log, f, indent=2)
        print(f"Training log saved: {path}")
        return path

    def close(self):
        if hasattr(self, "_gpu_backend") and self._gpu_backend is not None:
            self._gpu_backend.close()
            self._gpu_backend = None
        if hasattr(self, "_sim") and self._sim is not None:
            self._sim.close()
            self._sim = None


class FunctionalTrainedController:
    """Controller using trained functional network weights.

    Conforms to the Controller protocol: reset(), step(), done, get_metrics(), close().
    """

    # Maps neuron count -> n_hops for auto-detection
    _NEURON_COUNT_TO_HOPS = {248: 1, 398: 2, 498: 3}

    def __init__(self, checkpoint_path, episode_length_s=5.0, n_hops=None):
        import numpy as np

        self._checkpoint_path = Path(checkpoint_path)
        self._episode_length_s = episode_length_s

        ckpt = np.load(self._checkpoint_path, allow_pickle=True)
        self._trained_weights = ckpt["weights"]
        self._trained_thresholds = ckpt["thresholds"]

        # body_ids may be stored in checkpoint; otherwise load from snapshot
        if "body_ids" in ckpt:
            self._ckpt_body_ids = list(ckpt["body_ids"].astype(int))
        else:
            self._ckpt_body_ids = None

        # Auto-detect n_hops from checkpoint body_ids length if not provided
        if n_hops is None:
            n_neurons = len(self._trained_thresholds)
            n_hops = self._NEURON_COUNT_TO_HOPS.get(n_neurons, 1)
            print(f"[FunctionalTrainedController] Auto-detected n_hops={n_hops} "
                  f"from checkpoint size ({n_neurons} neurons)")
        self._n_hops = n_hops

        self._build()

    def _build(self):
        import brian2
        brian2.prefs.codegen.target = "numpy"

        from brian2 import (
            Network, SpikeMonitor, PoissonGroup, Synapses, NeuronGroup,
            Hz as brian_Hz, mV as brian_mV, ms as brian_ms,
            Mohm as brian_Mohm, pA,
        )
        from .network import DEFAULT_LIF_PARAMS
        from .constants import NT_SIGN_MAP
        from .locomotion import build_simulation, settle_simulation
        from .sensory_encoder import SensoryEncoder
        from .motor_adapter import SpikeRateDecoder
        from .functional_selection import (
            load_network_snapshot, build_motor_actuator_map
        )

        # Load network snapshot matching the training hop count
        (body_ids, meta_df, motor_leg_map,
         sources_coo, targets_coo, weights_coo) = load_network_snapshot(
            n_hops=self._n_hops
        )

        self._body_ids = body_ids
        self._meta_df = meta_df
        self._motor_leg_map = motor_leg_map
        self._n_neurons = len(body_ids)

        bid_to_idx = {int(bid): i for i, bid in enumerate(body_ids)}

        self._motor_neuron_indices = [
            bid_to_idx[int(bid)]
            for bid in motor_leg_map.keys()
            if int(bid) in bid_to_idx
        ]

        ascending_bids = meta_df[
            meta_df["superclass"] == "ascending_neuron"
        ]["bodyId"].values
        self._ascending_indices = [
            bid_to_idx[int(bid)] for bid in ascending_bids if int(bid) in bid_to_idx
        ]

        descending_bids = meta_df[
            meta_df["superclass"] == "descending_neuron"
        ]["bodyId"].values
        self._descending_indices = [
            bid_to_idx[int(bid)] for bid in descending_bids if int(bid) in bid_to_idx
        ]

        # NeuronGroup with trained thresholds
        params = DEFAULT_LIF_PARAMS
        eqs = """
        dv/dt = (-(v - V_rest) + R_membrane * I) / tau_m : volt (unless refractory)
        I : amp
        V_th_adapt : volt
        """
        namespace = {
            "tau_m": params["tau_m"],
            "V_rest": params["V_rest"],
            "V_reset": params["V_reset"],
            "R_membrane": params["R_membrane"],
        }
        G = NeuronGroup(
            self._n_neurons, eqs,
            threshold="v > V_th_adapt",
            reset="v = V_reset",
            refractory=params["t_refract"],
            method="euler",
            namespace=namespace,
        )
        G.v = params["V_rest"]
        G.V_th_adapt = self._trained_thresholds * brian_mV

        # Synapses with trained weights (inference only, no STDP)
        S = Synapses(G, G, "w : volt", on_pre="v_post += w")
        S.connect(i=sources_coo, j=targets_coo)
        S.w = self._trained_weights * brian_mV

        # Input drives
        if self._descending_indices:
            n_pg = min(15, len(self._descending_indices))
            PG_desc = PoissonGroup(n_pg, rates=10 * brian_Hz)
            S_desc = Synapses(PG_desc, G, on_pre="v_post += 2.0*mV")
            pg_i = np.repeat(np.arange(n_pg), len(self._descending_indices))
            pg_j = np.tile(self._descending_indices, n_pg)
            S_desc.connect(i=pg_i, j=pg_j)
        else:
            PG_desc = S_desc = None

        PG_bg = PoissonGroup(50, rates=22 * brian_Hz)
        S_bg = Synapses(PG_bg, G, on_pre="v_post += 1.3*mV")
        bg_i = np.repeat(np.arange(50), self._n_neurons)
        bg_j = np.tile(np.arange(self._n_neurons), 50)
        S_bg.connect(i=bg_i, j=bg_j)

        M = SpikeMonitor(G)
        net_objects = [G, S, PG_bg, S_bg, M]
        if PG_desc is not None:
            net_objects.extend([PG_desc, S_desc])

        self._net = Network(*net_objects)
        self._G = G
        self._M = M
        self._net.store("initial")

        # FlyGym
        sim, fly, model, data, neutral_ctrl, _ = build_simulation()
        settle_simulation(sim, n_steps=2000)

        self._sim = sim
        self._model = model
        self._data = data
        self._neutral_ctrl = neutral_ctrl
        self._initial_qpos = data.qpos.copy()
        self._initial_qvel = data.qvel.copy()

        flygym_dt_s = model.opt.timestep
        self._coupling_dt_ms = 2.0
        self._flygym_steps_per_coupling = int(2.0 / (flygym_dt_s * 1000))

        # Adapters
        sensory_gain_pa = 500e-12 / 1e-12
        self._encoder = SensoryEncoder(
            self._ascending_indices, n_neurons=self._n_neurons, n_actuated=66,
            gain_pa=sensory_gain_pa, vel_gain_pa=sensory_gain_pa * 0.6,
        )
        self._decoder = SpikeRateDecoder(
            self._motor_neuron_indices, window_ms=50.0, dt_ms=self._coupling_dt_ms,
        )
        self._motor_actuator_map = build_motor_actuator_map(motor_leg_map, body_ids)

        self._motor_gain = 0.3
        self._n_steps_total = int(
            self._episode_length_s * 1000 / self._coupling_dt_ms
        )
        self._step_count = 0
        self._prev_spike_count = 0
        self._positions = []
        self._headings = []
        self._actions = []

    def _decode_biological(self, rates_hz):
        action = self._neutral_ctrl.copy()
        actuator_offsets = {}
        actuator_counts = {}
        baseline_hz = 15.0
        amplitude = self._motor_gain

        for net_idx, actuator_list in self._motor_actuator_map.items():
            rate = rates_hz.get(net_idx, 0.0)
            offset = float(np.clip(
                (rate - baseline_hz) / max(baseline_hz, 1.0) * amplitude,
                -amplitude, amplitude
            ))
            for act_idx in actuator_list:
                actuator_offsets[act_idx] = actuator_offsets.get(act_idx, 0.0) + offset
                actuator_counts[act_idx] = actuator_counts.get(act_idx, 0) + 1

        for act_idx, total_offset in actuator_offsets.items():
            action[act_idx] += total_offset / actuator_counts[act_idx]
        return action

    def reset(self):
        import brian2
        from brian2 import ms as brian_ms, mV as brian_mV, pA
        import mujoco
        from .motor_adapter import SpikeRateDecoder

        self._net.restore("initial")
        self._G.V_th_adapt[:] = self._trained_thresholds * brian_mV

        self._data.qpos[:] = self._initial_qpos
        self._data.qvel[:] = self._initial_qvel
        self._data.ctrl[:] = self._neutral_ctrl
        mujoco.mj_forward(self._model, self._data)

        self._decoder = SpikeRateDecoder(
            self._motor_neuron_indices, window_ms=50.0, dt_ms=self._coupling_dt_ms,
        )

        self._G.I = 0 * pA
        self._net.run(500 * brian_ms)
        self._prev_spike_count = self._M.num_spikes
        self._step_count = 0
        self._positions = []
        self._headings = []
        self._actions = []

        joint_angles = self._sim.get_joint_angles("nmf")
        body_vel = self._data.qvel[0:3].copy()
        self._sensory_currents = self._encoder.encode(joint_angles, body_vel)
        self._record_state()

    def step(self):
        import brian2
        from brian2 import ms as brian_ms, pA
        from flygym.compose import ActuatorType

        self._G.I = 0 * pA
        for idx in self._ascending_indices:
            self._G.I[idx] = self._sensory_currents[idx] * brian2.amp

        self._net.run(self._coupling_dt_ms * brian_ms)

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
        action = self._decode_biological(rates)

        for _ in range(self._flygym_steps_per_coupling):
            self._sim.set_actuator_inputs("nmf", ActuatorType.POSITION, action)
            self._sim.step()

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
    def done(self) -> bool:
        return self._step_count >= self._n_steps_total

    def get_metrics(self) -> dict:
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


def run_functional_training(
    episodes=50,
    episode_length=2.0,
    force_rebuild=False,
    n_hops=2,
    backend="gpu",
    eta_homeo=0.01,
    reward_mode="episodic",
    learning_rate=0.001,
):
    """Run functional training (biological locomotor circuit + STDP).

    Parameters
    ----------
    episodes : int
    episode_length : float
    force_rebuild : bool
        Re-query neuPrint even if cached.
    n_hops : int
        Number of upstream hops for neuron selection (default 2).
    backend : str
        Neural simulator backend: "gpu" (default) or "cpu".
    eta_homeo : float
        Homeostatic plasticity learning rate (default 0.01).
    reward_mode : str
        "episodic" (default) or "continuous".
    learning_rate : float
        STDP weight update learning rate (default 0.001).
    """
    print(f"\nStarting functional training "
          f"({episodes} episodes, {episode_length}s each, "
          f"{n_hops} hop(s), {backend.upper()} backend, "
          f"reward_mode={reward_mode}, "
          f"eta_homeo={eta_homeo}, lr={learning_rate})...\n")

    harness = FunctionalTrainingHarness(
        n_episodes=episodes,
        episode_length_s=episode_length,
        coupling_dt_ms=2.0,
        learning_rate=learning_rate,
        tau_stdp_ms=20.0,
        tau_eligibility_s=1.0,
        motor_gain=0.3,
        sensory_gain=500e-12,
        baseline_window=5,
        eta_homeo=eta_homeo,
        target_rate=25.0,
        lambda_decay=0.001,
        eligibility_decay_threshold=0.01,
        checkpoint_interval=10,
        force_rebuild=force_rebuild,
        n_hops=n_hops,
        backend=backend,
        reward_mode=reward_mode,
    )

    suffix = f"_functional_{n_hops}hop"
    if harness._backend_type == "gpu":
        suffix += "_gpu"
    if reward_mode == "continuous":
        suffix += "_continuous"
    log_path = _DEFAULT_REPORTS_DIR / f"functional_training_log{suffix}.json"
    checkpoint_dir = _DEFAULT_REPORTS_DIR / f"checkpoints_functional{suffix}"

    try:
        results = harness.train(checkpoint_dir=checkpoint_dir)
        harness.save_results(results, path=log_path)
        print(f"\nDone. Training log: {log_path}")
        return results
    finally:
        harness.close()
