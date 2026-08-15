"""Baseline controllers for locomotion benchmarking.

Each controller implements a common protocol:
    reset() -> None
    step() -> None
    done -> bool
    get_metrics() -> dict[str, float]
    close() -> None

Controllers:
    BiologicalController — Connectome-derived Brian2 + FlyGym (wraps CoSimulation)
    RandomWeightController — Same topology, shuffled weight magnitudes within sign groups
    ZeroWeightController — All synaptic weights zeroed (Poisson drive only)
    CPGController — Scripted tripod gait via FlyGym (no neural network)
    NoiseController — Random actuator commands (null model)
"""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

import numpy as np

os.environ.setdefault("MUJOCO_GL", "egl")


@runtime_checkable
class Controller(Protocol):
    def reset(self) -> None: ...
    def step(self) -> None: ...
    @property
    def done(self) -> bool: ...
    def get_metrics(self) -> dict[str, float]: ...
    def close(self) -> None: ...


# ---------------------------------------------------------------------------
# BiologicalController
# ---------------------------------------------------------------------------


class BiologicalController:
    """Thin wrapper around CoSimulation using original connectome weights."""

    def __init__(self, episode_length_s: float = 2.0, **kwargs):
        from ..loop import CoSimulation

        self._sim = CoSimulation(episode_length_s=episode_length_s, **kwargs)

    def reset(self) -> None:
        self._sim.reset()

    def step(self) -> None:
        self._sim.step()

    @property
    def done(self) -> bool:
        return self._sim.done

    def get_metrics(self) -> dict[str, float]:
        return self._sim.get_metrics()

    def close(self) -> None:
        self._sim.close()


# ---------------------------------------------------------------------------
# RandomWeightController
# ---------------------------------------------------------------------------


class RandomWeightController:
    """Same network topology as biological but with shuffled weight magnitudes.

    Weights are shuffled WITHIN sign groups (excitatory among excitatory,
    inhibitory among inhibitory) to preserve Dale's principle while destroying
    specific wiring structure.
    """

    def __init__(self, episode_length_s: float = 2.0, seed: int = 42,
                 coupling_dt_ms: float = 2.0, motor_gain: float = 0.3,
                 sensory_gain: float = 500e-12):
        self.episode_length_s = episode_length_s
        self.coupling_dt_ms = coupling_dt_ms
        self.motor_gain = motor_gain
        self.sensory_gain = sensory_gain
        self._seed = seed
        self._elapsed_s = 0.0
        self._motor_rates_log: list[float] = []
        self._build()

    def _build(self) -> None:
        import brian2
        brian2.prefs.codegen.target = "numpy"
        from brian2 import Network, SpikeMonitor, Hz as brian_Hz, mV as brian_mV

        from ..network import (
            load_sample_data,
            create_neuron_group,
            create_synapses_constrained,
            create_poisson_drive,
            create_background_drive,
        )
        from ..locomotion import build_simulation, settle_simulation
        from ..sensory_encoder import SensoryEncoder
        from ..motor_adapter import SpikeRateDecoder, MotorMapping

        adj, neurons_df = load_sample_data()
        self._n_neurons = adj.shape[0]

        self._motor_neuron_indices = neurons_df[
            neurons_df["superclass"] == "vnc_motor"
        ].index.tolist()
        self._ascending_indices = neurons_df[
            neurons_df["superclass"] == "ascending_neuron"
        ].index.tolist()

        G = create_neuron_group(self._n_neurons)
        S, sources, targets, weights_raw, sign_vector = create_synapses_constrained(
            G, adj, neurons_df, scale=0.6, inh_attenuation=0.5,
        )

        # Shuffle weight magnitudes within sign groups
        rng = np.random.default_rng(self._seed)
        w_values = np.array(S.w / brian_mV)  # in mV units (float)
        exc_mask = w_values > 0
        inh_mask = w_values < 0

        exc_magnitudes = w_values[exc_mask].copy()
        inh_magnitudes = np.abs(w_values[inh_mask]).copy()

        rng.shuffle(exc_magnitudes)
        rng.shuffle(inh_magnitudes)

        w_values[exc_mask] = exc_magnitudes
        w_values[inh_mask] = -inh_magnitudes
        S.w = w_values * brian_mV

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
        self._flygym_steps_per_coupling = int(
            self.coupling_dt_ms / (flygym_dt_s * 1000)
        )

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

    def reset(self) -> None:
        from brian2 import ms as brian_ms, pA
        import mujoco

        self._net.restore("initial")
        self._data.qpos[:] = self._initial_qpos
        self._data.qvel[:] = self._initial_qvel
        self._data.ctrl[:] = self._neutral_ctrl
        mujoco.mj_forward(self._model, self._data)

        from ..motor_adapter import SpikeRateDecoder
        self.decoder = SpikeRateDecoder(
            self._motor_neuron_indices, window_ms=50.0, dt_ms=self.coupling_dt_ms,
        )

        self._G.I = 0 * pA
        self._net.run(500.0 * brian_ms)
        self._total_spikes_start = self._M.num_spikes

        self._elapsed_s = 0.0
        self._motor_rates_log = []
        self._episode_start_pos = self._data.qpos[0:3].copy()

        joint_angles = self._sim.get_joint_angles("nmf")
        body_vel = self._data.qvel[0:3].copy()
        self._sensory_currents = self.encoder.encode(joint_angles, body_vel)
        self._prev_spike_count = self._M.num_spikes

    def step(self) -> None:
        import brian2
        from brian2 import ms as brian_ms, pA
        from flygym.compose import ActuatorType

        self._G.I = 0 * pA
        for idx in self._ascending_indices:
            self._G.I[idx] = self._sensory_currents[idx] * brian2.amp

        self._net.run(self.coupling_dt_ms * brian_ms)

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
        mean_motor_rate = np.mean(list(rates.values())) if rates else 0.0
        self._motor_rates_log.append(mean_motor_rate)

        from ..motor_adapter import decode_spikes_to_positions
        action = decode_spikes_to_positions(
            rates, self._mapping, self._neutral_ctrl,
            baseline_hz=15.0, amplitude=self.motor_gain,
        )

        for _ in range(self._flygym_steps_per_coupling):
            self._sim.set_actuator_inputs("nmf", ActuatorType.POSITION, action)
            self._sim.step()

        joint_angles = self._sim.get_joint_angles("nmf")
        body_vel = self._data.qvel[0:3].copy()
        self._sensory_currents = self.encoder.encode(joint_angles, body_vel)
        self._elapsed_s += self.coupling_dt_ms / 1000.0

    @property
    def done(self) -> bool:
        return self._elapsed_s >= self.episode_length_s

    def get_metrics(self) -> dict[str, float]:
        current_pos = self._data.qpos[0:3].copy()
        displacement = current_pos - self._episode_start_pos
        return {
            "forward_distance_mm": float(displacement[0]),
            "mean_motor_rate_hz": float(np.mean(self._motor_rates_log))
            if self._motor_rates_log else 0.0,
        }

    def close(self) -> None:
        if hasattr(self, "_sim") and self._sim is not None:
            self._sim.close()
            self._sim = None


# ---------------------------------------------------------------------------
# ZeroWeightController
# ---------------------------------------------------------------------------


class ZeroWeightController:
    """Network with all synaptic weights set to zero.

    Neurons fire only from Poisson background drive — no recurrent or
    feedforward synaptic transmission.
    """

    def __init__(self, episode_length_s: float = 2.0,
                 coupling_dt_ms: float = 2.0, motor_gain: float = 0.3,
                 sensory_gain: float = 500e-12):
        self.episode_length_s = episode_length_s
        self.coupling_dt_ms = coupling_dt_ms
        self.motor_gain = motor_gain
        self.sensory_gain = sensory_gain
        self._elapsed_s = 0.0
        self._motor_rates_log: list[float] = []
        self._build()

    def _build(self) -> None:
        import brian2
        brian2.prefs.codegen.target = "numpy"
        from brian2 import Network, SpikeMonitor, Hz as brian_Hz, mV as brian_mV

        from ..network import (
            load_sample_data,
            create_neuron_group,
            create_synapses_constrained,
            create_poisson_drive,
            create_background_drive,
        )
        from ..locomotion import build_simulation, settle_simulation
        from ..sensory_encoder import SensoryEncoder
        from ..motor_adapter import SpikeRateDecoder, MotorMapping

        adj, neurons_df = load_sample_data()
        self._n_neurons = adj.shape[0]

        self._motor_neuron_indices = neurons_df[
            neurons_df["superclass"] == "vnc_motor"
        ].index.tolist()
        self._ascending_indices = neurons_df[
            neurons_df["superclass"] == "ascending_neuron"
        ].index.tolist()

        G = create_neuron_group(self._n_neurons)
        S, sources, targets, weights_raw, sign_vector = create_synapses_constrained(
            G, adj, neurons_df, scale=0.6, inh_attenuation=0.5,
        )

        # Zero all synaptic weights
        S.w = 0 * brian_mV

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
        self._flygym_steps_per_coupling = int(
            self.coupling_dt_ms / (flygym_dt_s * 1000)
        )

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

    def reset(self) -> None:
        from brian2 import ms as brian_ms, pA
        import mujoco

        self._net.restore("initial")
        self._data.qpos[:] = self._initial_qpos
        self._data.qvel[:] = self._initial_qvel
        self._data.ctrl[:] = self._neutral_ctrl
        mujoco.mj_forward(self._model, self._data)

        from ..motor_adapter import SpikeRateDecoder
        self.decoder = SpikeRateDecoder(
            self._motor_neuron_indices, window_ms=50.0, dt_ms=self.coupling_dt_ms,
        )

        self._G.I = 0 * pA
        self._net.run(500.0 * brian_ms)
        self._total_spikes_start = self._M.num_spikes

        self._elapsed_s = 0.0
        self._motor_rates_log = []
        self._episode_start_pos = self._data.qpos[0:3].copy()

        joint_angles = self._sim.get_joint_angles("nmf")
        body_vel = self._data.qvel[0:3].copy()
        self._sensory_currents = self.encoder.encode(joint_angles, body_vel)
        self._prev_spike_count = self._M.num_spikes

    def step(self) -> None:
        import brian2
        from brian2 import ms as brian_ms, pA
        from flygym.compose import ActuatorType

        self._G.I = 0 * pA
        for idx in self._ascending_indices:
            self._G.I[idx] = self._sensory_currents[idx] * brian2.amp

        self._net.run(self.coupling_dt_ms * brian_ms)

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
        mean_motor_rate = np.mean(list(rates.values())) if rates else 0.0
        self._motor_rates_log.append(mean_motor_rate)

        from ..motor_adapter import decode_spikes_to_positions
        action = decode_spikes_to_positions(
            rates, self._mapping, self._neutral_ctrl,
            baseline_hz=15.0, amplitude=self.motor_gain,
        )

        for _ in range(self._flygym_steps_per_coupling):
            self._sim.set_actuator_inputs("nmf", ActuatorType.POSITION, action)
            self._sim.step()

        joint_angles = self._sim.get_joint_angles("nmf")
        body_vel = self._data.qvel[0:3].copy()
        self._sensory_currents = self.encoder.encode(joint_angles, body_vel)
        self._elapsed_s += self.coupling_dt_ms / 1000.0

    @property
    def done(self) -> bool:
        return self._elapsed_s >= self.episode_length_s

    def get_metrics(self) -> dict[str, float]:
        current_pos = self._data.qpos[0:3].copy()
        displacement = current_pos - self._episode_start_pos
        return {
            "forward_distance_mm": float(displacement[0]),
            "mean_motor_rate_hz": float(np.mean(self._motor_rates_log))
            if self._motor_rates_log else 0.0,
        }

    def close(self) -> None:
        if hasattr(self, "_sim") and self._sim is not None:
            self._sim.close()
            self._sim = None


# ---------------------------------------------------------------------------
# CPGController
# ---------------------------------------------------------------------------


class CPGController:
    """Scripted tripod gait using FlyGym — no neural network.

    Applies sinusoidal CPG-like position commands to produce forward walking
    via the same tripod pattern used in locomotion.py.
    """

    def __init__(self, episode_length_s: float = 2.0, freq_hz: float = 8.0):
        self.episode_length_s = episode_length_s
        self.freq_hz = freq_hz
        self._elapsed_s = 0.0
        self._build()

    def _build(self) -> None:
        from ..locomotion import (
            build_simulation,
            settle_simulation,
            TRIPOD_PHASES,
            LEG_OFFSETS,
        )

        sim, fly, model, data, neutral_ctrl, actuator_names = build_simulation()
        settle_simulation(sim, n_steps=2000)

        self._sim = sim
        self._fly = fly
        self._model = model
        self._data = data
        self._neutral_ctrl = neutral_ctrl
        self._initial_qpos = data.qpos.copy()
        self._initial_qvel = data.qvel.copy()
        self._dt = model.opt.timestep
        self._tripod_phases = TRIPOD_PHASES
        self._leg_offsets = LEG_OFFSETS

        # Gait amplitudes (same as locomotion.run_tripod_gait)
        self._amp_coxa_pitch = 0.2
        self._amp_coxa_yaw = 0.3
        self._amp_femur = 0.4
        self._amp_tibia = 0.2

        # Steps per coupling-equivalent tick (use 2ms like neural controllers)
        self._coupling_dt_ms = 2.0
        self._physics_steps_per_tick = int(
            self._coupling_dt_ms / (self._dt * 1000)
        )

    def reset(self) -> None:
        import mujoco

        self._data.qpos[:] = self._initial_qpos
        self._data.qvel[:] = self._initial_qvel
        self._data.ctrl[:] = self._neutral_ctrl
        mujoco.mj_forward(self._model, self._data)

        self._elapsed_s = 0.0
        self._episode_start_pos = self._data.qpos[0:3].copy()

    def step(self) -> None:
        from flygym.compose import ActuatorType

        t = self._elapsed_s
        phase = 2 * np.pi * self.freq_hz * t
        action = self._neutral_ctrl.copy()

        for leg_name, leg_phase in self._tripod_phases.items():
            offset = self._leg_offsets[leg_name]
            p = phase + leg_phase
            action[offset + 0] += self._amp_coxa_pitch * np.sin(p)
            action[offset + 2] += self._amp_coxa_yaw * np.sin(p)
            action[offset + 3] += self._amp_femur * np.sin(p + np.pi / 2)
            action[offset + 5] += self._amp_tibia * np.sin(p - np.pi / 4)

        for _ in range(self._physics_steps_per_tick):
            self._sim.set_actuator_inputs("nmf", ActuatorType.POSITION, action)
            self._sim.step()

        self._elapsed_s += self._coupling_dt_ms / 1000.0

    @property
    def done(self) -> bool:
        return self._elapsed_s >= self.episode_length_s

    def get_metrics(self) -> dict[str, float]:
        current_pos = self._data.qpos[0:3].copy()
        displacement = current_pos - self._episode_start_pos
        return {
            "forward_distance_mm": float(displacement[0]),
            "mean_motor_rate_hz": 0.0,
        }

    def close(self) -> None:
        if hasattr(self, "_sim") and self._sim is not None:
            self._sim.close()
            self._sim = None


# ---------------------------------------------------------------------------
# NoiseController
# ---------------------------------------------------------------------------


class NoiseController:
    """Random actuator commands each step — null model baseline.

    Uses FlyGym body but applies uniform random actions around the neutral
    pose every coupling tick.
    """

    def __init__(self, episode_length_s: float = 2.0, seed: int = 0,
                 noise_amplitude: float = 0.3):
        self.episode_length_s = episode_length_s
        self._seed = seed
        self._noise_amplitude = noise_amplitude
        self._elapsed_s = 0.0
        self._rng = np.random.default_rng(seed)
        self._build()

    def _build(self) -> None:
        from ..locomotion import build_simulation, settle_simulation

        sim, fly, model, data, neutral_ctrl, actuator_names = build_simulation()
        settle_simulation(sim, n_steps=2000)

        self._sim = sim
        self._fly = fly
        self._model = model
        self._data = data
        self._neutral_ctrl = neutral_ctrl
        self._initial_qpos = data.qpos.copy()
        self._initial_qvel = data.qvel.copy()

        self._coupling_dt_ms = 2.0
        self._physics_steps_per_tick = int(
            self._coupling_dt_ms / (model.opt.timestep * 1000)
        )

    def reset(self) -> None:
        import mujoco

        self._data.qpos[:] = self._initial_qpos
        self._data.qvel[:] = self._initial_qvel
        self._data.ctrl[:] = self._neutral_ctrl
        mujoco.mj_forward(self._model, self._data)

        self._elapsed_s = 0.0
        self._rng = np.random.default_rng(self._seed)
        self._episode_start_pos = self._data.qpos[0:3].copy()

    def step(self) -> None:
        from flygym.compose import ActuatorType

        noise = self._rng.uniform(
            -self._noise_amplitude, self._noise_amplitude,
            size=self._neutral_ctrl.shape,
        )
        action = self._neutral_ctrl + noise

        for _ in range(self._physics_steps_per_tick):
            self._sim.set_actuator_inputs("nmf", ActuatorType.POSITION, action)
            self._sim.step()

        self._elapsed_s += self._coupling_dt_ms / 1000.0

    @property
    def done(self) -> bool:
        return self._elapsed_s >= self.episode_length_s

    def get_metrics(self) -> dict[str, float]:
        current_pos = self._data.qpos[0:3].copy()
        displacement = current_pos - self._episode_start_pos
        return {
            "forward_distance_mm": float(displacement[0]),
            "mean_motor_rate_hz": 0.0,
        }

    def close(self) -> None:
        if hasattr(self, "_sim") and self._sim is not None:
            self._sim.close()
            self._sim = None
