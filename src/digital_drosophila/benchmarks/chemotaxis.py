"""Chemotaxis benchmark: fly navigates toward an odor source using olfactory input.

Metrics computed:
    - final_distance_mm: Euclidean distance from source at end of episode
    - source_reached: 1.0 if fly came within arrival threshold of source
    - path_efficiency: straight-line progress / actual path length
    - progress_toward_source_mm: initial_distance - final_distance
    - path_length_mm: total distance traveled
    - upwind_bias: fraction of steps moving toward source

Usage:
    python -c "from digital_drosophila.benchmarks.chemotaxis import run_chemotaxis_benchmark; run_chemotaxis_benchmark()"
"""

from __future__ import annotations

import os

os.environ.setdefault("MUJOCO_GL", "egl")

import numpy as np


def _quat_to_yaw(quat: np.ndarray) -> float:
    """Extract yaw angle (rotation about Z) from a wxyz quaternion."""
    w, x, y, z = quat
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return float(np.arctan2(siny_cosp, cosy_cosp))


def compute_chemotaxis_metrics(
    positions: np.ndarray,
    source_position: np.ndarray,
    duration_s: float,
    arrival_threshold_mm: float = 1.0,
) -> dict[str, float]:
    """Compute chemotaxis metrics from recorded fly trajectory.

    Parameters
    ----------
    positions : ndarray, shape (T, 2)
        XY positions of the fly at each timestep in mm.
    source_position : ndarray, shape (2,)
        XY location of the odor source in mm.
    duration_s : float
        Total episode duration in seconds.
    arrival_threshold_mm : float
        Distance threshold for considering the source reached.

    Returns
    -------
    dict[str, float]
        Chemotaxis metric name -> value.
    """
    positions = np.asarray(positions, dtype=float)
    source_position = np.asarray(source_position, dtype=float)

    if len(positions) < 2:
        return {
            "final_distance_mm": float(np.linalg.norm(positions[0] - source_position)),
            "source_reached": 0.0,
            "path_efficiency": 0.0,
            "progress_toward_source_mm": 0.0,
            "path_length_mm": 0.0,
            "upwind_bias": 0.0,
        }

    # Distances from source at each timestep
    distances = np.linalg.norm(positions - source_position, axis=1)

    initial_distance = distances[0]
    final_distance = distances[-1]
    min_distance = float(np.min(distances))

    # Source arrival
    source_reached = 1.0 if min_distance < arrival_threshold_mm else 0.0

    # Progress toward source (positive = got closer)
    progress = initial_distance - final_distance

    # Path length: sum of step-wise displacements
    step_displacements = np.diff(positions, axis=0)
    step_lengths = np.linalg.norm(step_displacements, axis=1)
    path_length = float(np.sum(step_lengths))

    # Path efficiency: straight-line progress / actual path length
    if path_length > 1e-9:
        path_efficiency = max(0.0, progress) / path_length
    else:
        path_efficiency = 0.0

    # Upwind bias: fraction of steps where fly moves closer to source
    distance_changes = np.diff(distances)  # negative = approaching source
    n_approaching = int(np.sum(distance_changes < 0))
    upwind_bias = n_approaching / len(distance_changes) if len(distance_changes) > 0 else 0.0

    return {
        "final_distance_mm": float(final_distance),
        "source_reached": float(source_reached),
        "path_efficiency": float(path_efficiency),
        "progress_toward_source_mm": float(progress),
        "path_length_mm": float(path_length),
        "upwind_bias": float(upwind_bias),
    }


# ---------------------------------------------------------------------------
# ChemotaxisController — CoSimulation with olfactory reflexive turning
# ---------------------------------------------------------------------------


class ChemotaxisController:
    """Co-simulation with olfactory input driving reflexive turning bias.

    Uses the 'skateboard' approach: bilateral olfactory difference produces
    a turning bias on motor actuators, without requiring direct injection
    into Brian2 internals. This tests whether the fly CAN navigate toward
    an odor source with simple reflexive coupling.

    Parameters
    ----------
    arena : Arena
        Arena containing the concentration field.
    episode_length_s : float
        Duration of each episode in seconds.
    olfactory_gain : float
        Gain for converting bilateral difference to turning bias.
    """

    def __init__(self, arena, episode_length_s: float = 10.0,
                 olfactory_gain: float = 0.1):
        from ..arenas import Arena
        from ..olfaction import OlfactoryEncoder
        from ..loop import CoSimulation

        self._arena = arena
        self._olfactory_gain = olfactory_gain
        self._encoder = OlfactoryEncoder()
        self._sim = CoSimulation(episode_length_s=episode_length_s)
        self.positions: list[np.ndarray] = []

    def reset(self) -> None:
        self._sim.reset()
        self.positions.clear()
        # Record initial position
        pos_xy = self._sim._data.qpos[0:2].copy()
        self.positions.append(pos_xy)

    def step(self) -> None:
        # 1. Get fly position and heading from body state
        pos_xy = self._sim._data.qpos[0:2].copy()
        quat = self._sim._data.qpos[3:7]
        heading = _quat_to_yaw(quat)

        # 2. Encode olfactory input from concentration field
        result = self._encoder.encode(self._arena.field, pos_xy, heading)
        bilateral_diff = result["bilateral_difference"]

        # 3. Apply reflexive turning bias to actuators
        # bilateral_diff > 0 means stronger on left antenna -> turn right
        # bilateral_diff < 0 means stronger on right antenna -> turn left
        # We bias the coxa yaw joints to produce turning
        self._apply_olfactory_bias(bilateral_diff)

        # 4. Step the co-simulation
        self._sim.step()

        # 5. Record new position
        new_pos = self._sim._data.qpos[0:2].copy()
        self.positions.append(new_pos)

    def _apply_olfactory_bias(self, bilateral_diff: float) -> None:
        """Apply turning bias to motor commands via ctrl array.

        Modifies the neutral control offsets for coxa yaw joints to
        produce turning toward the stronger-concentration side.
        """
        # bilateral_diff > 0: left antenna stronger -> source is to the left
        # To turn left, we want to increase left-side yaw and decrease right-side
        # In the FlyGym NMF model, each leg has joints at specific offsets
        # Coxa yaw is typically offset +2 in the 11-DOF per-leg layout
        #
        # Convention: positive yaw = swing forward, so asymmetric yaw
        # produces turning. For left turn: bias right legs forward more.
        #
        # Simpler: directly bias the ctrl array with a small asymmetry
        turn_bias = bilateral_diff * self._olfactory_gain

        # Apply bias to the body ctrl: left legs get -bias, right legs get +bias
        # This creates a differential that turns the fly toward the source
        # FlyGym NMF has 6 legs x 11 joints = 66 actuators
        # Legs: LF, LM, LH (indices 0-32), RF, RM, RH (indices 33-65)
        # Coxa yaw is index 2 within each leg's 11 DOFs
        n_dof_per_leg = 11
        # Left legs (0, 1, 2): decrease yaw to turn left
        for leg_idx in range(3):
            coxa_yaw_idx = leg_idx * n_dof_per_leg + 2
            self._sim._data.ctrl[coxa_yaw_idx] -= turn_bias
        # Right legs (3, 4, 5): increase yaw to turn left
        for leg_idx in range(3, 6):
            coxa_yaw_idx = leg_idx * n_dof_per_leg + 2
            self._sim._data.ctrl[coxa_yaw_idx] += turn_bias

    @property
    def done(self) -> bool:
        return self._sim.done

    def get_metrics(self) -> dict[str, float]:
        """Return chemotaxis metrics for the completed episode."""
        source_pos = self._arena.field.source_position
        positions_array = np.array(self.positions)
        duration_s = self._sim._elapsed_s

        metrics = compute_chemotaxis_metrics(
            positions_array, source_pos, duration_s
        )

        # Also include the underlying CoSimulation metrics
        sim_metrics = self._sim.get_metrics()
        metrics["forward_distance_mm"] = sim_metrics["forward_distance_mm"]
        metrics["mean_motor_rate_hz"] = sim_metrics["mean_motor_rate_hz"]
        metrics["total_spikes"] = sim_metrics["total_spikes"]

        return metrics

    def close(self) -> None:
        self._sim.close()


# ---------------------------------------------------------------------------
# CPGChemotaxisController — CPG walking with olfactory turning (no SNN)
# ---------------------------------------------------------------------------


class CPGChemotaxisController:
    """CPG tripod gait with reflexive olfactory turning — no neural network.

    Uses the scripted tripod gait from CPGController but adds olfactory
    bilateral input to modulate turning.

    Parameters
    ----------
    arena : Arena
        Arena containing the concentration field.
    episode_length_s : float
        Duration of each episode in seconds.
    olfactory_gain : float
        Gain for converting bilateral difference to turning bias.
    freq_hz : float
        CPG frequency for tripod gait.
    """

    def __init__(self, arena, episode_length_s: float = 10.0,
                 olfactory_gain: float = 0.1, freq_hz: float = 8.0):
        from ..olfaction import OlfactoryEncoder
        from ..locomotion import (
            build_simulation,
            settle_simulation,
            TRIPOD_PHASES,
            LEG_OFFSETS,
        )

        self._arena = arena
        self._olfactory_gain = olfactory_gain
        self._encoder = OlfactoryEncoder()
        self.episode_length_s = episode_length_s
        self.freq_hz = freq_hz
        self._elapsed_s = 0.0
        self.positions: list[np.ndarray] = []

        # Build FlyGym simulation
        sim, fly, model, data, neutral_ctrl, actuator_names = build_simulation()
        settle_simulation(sim, n_steps=2000)

        self._sim = sim
        self._fly = fly
        self._model = model
        self._data = data
        self._neutral_ctrl = neutral_ctrl
        self._initial_qpos = data.qpos.copy()
        self._initial_qvel = data.qvel.copy()
        self._tripod_phases = TRIPOD_PHASES
        self._leg_offsets = LEG_OFFSETS

        # Gait amplitudes
        self._amp_coxa_pitch = 0.2
        self._amp_coxa_yaw = 0.3
        self._amp_femur = 0.4
        self._amp_tibia = 0.2

        # Coupling timing
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
        self.positions.clear()
        self.positions.append(self._data.qpos[0:2].copy())

    def step(self) -> None:
        from flygym.compose import ActuatorType

        # 1. Get fly position and heading
        pos_xy = self._data.qpos[0:2].copy()
        quat = self._data.qpos[3:7]
        heading = _quat_to_yaw(quat)

        # 2. Encode olfactory input
        result = self._encoder.encode(self._arena.field, pos_xy, heading)
        bilateral_diff = result["bilateral_difference"]
        turn_bias = bilateral_diff * self._olfactory_gain

        # 3. Compute CPG gait action
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

        # 4. Apply olfactory turning bias on top of CPG
        n_dof_per_leg = 11
        for leg_idx in range(3):  # Left legs
            coxa_yaw_idx = leg_idx * n_dof_per_leg + 2
            action[coxa_yaw_idx] -= turn_bias
        for leg_idx in range(3, 6):  # Right legs
            coxa_yaw_idx = leg_idx * n_dof_per_leg + 2
            action[coxa_yaw_idx] += turn_bias

        # 5. Step physics
        for _ in range(self._physics_steps_per_tick):
            self._sim.set_actuator_inputs("nmf", ActuatorType.POSITION, action)
            self._sim.step()

        self._elapsed_s += self._coupling_dt_ms / 1000.0
        self.positions.append(self._data.qpos[0:2].copy())

    @property
    def done(self) -> bool:
        return self._elapsed_s >= self.episode_length_s

    def get_metrics(self) -> dict[str, float]:
        source_pos = self._arena.field.source_position
        positions_array = np.array(self.positions)

        metrics = compute_chemotaxis_metrics(
            positions_array, source_pos, self._elapsed_s
        )
        metrics["forward_distance_mm"] = float(
            self._data.qpos[0] - self._initial_qpos[0]
        )
        metrics["mean_motor_rate_hz"] = 0.0
        metrics["total_spikes"] = 0.0
        return metrics

    def close(self) -> None:
        if hasattr(self, "_sim") and self._sim is not None:
            self._sim.close()
            self._sim = None


# ---------------------------------------------------------------------------
# NoiseChemotaxisController — random baseline (no olfaction)
# ---------------------------------------------------------------------------


class NoiseChemotaxisController:
    """Random actuator commands — null model baseline for chemotaxis.

    No olfactory input; just random actions. Tracks positions for metric
    computation.

    Parameters
    ----------
    arena : Arena
        Arena containing the concentration field (used only for metrics).
    episode_length_s : float
        Duration of each episode in seconds.
    seed : int
        Random seed.
    noise_amplitude : float
        Amplitude of random noise around neutral pose.
    """

    def __init__(self, arena, episode_length_s: float = 10.0,
                 seed: int = 0, noise_amplitude: float = 0.3):
        from ..locomotion import build_simulation, settle_simulation

        self._arena = arena
        self.episode_length_s = episode_length_s
        self._seed = seed
        self._noise_amplitude = noise_amplitude
        self._rng = np.random.default_rng(seed)
        self._elapsed_s = 0.0
        self.positions: list[np.ndarray] = []

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
        self.positions.clear()
        self.positions.append(self._data.qpos[0:2].copy())

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
        self.positions.append(self._data.qpos[0:2].copy())

    @property
    def done(self) -> bool:
        return self._elapsed_s >= self.episode_length_s

    def get_metrics(self) -> dict[str, float]:
        source_pos = self._arena.field.source_position
        positions_array = np.array(self.positions)

        metrics = compute_chemotaxis_metrics(
            positions_array, source_pos, self._elapsed_s
        )
        metrics["forward_distance_mm"] = float(
            self._data.qpos[0] - self._initial_qpos[0]
        )
        metrics["mean_motor_rate_hz"] = 0.0
        metrics["total_spikes"] = 0.0
        return metrics

    def close(self) -> None:
        if hasattr(self, "_sim") and self._sim is not None:
            self._sim.close()
            self._sim = None


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def run_chemotaxis_benchmark(n_episodes: int = 10, duration_s: float = 10.0) -> None:
    """Run chemotaxis benchmark with point source arena.

    Runs three controller types:
        1. ChemotaxisController (biological SNN + olfactory reflexive turning)
        2. CPGChemotaxisController (CPG gait + olfactory turning, no SNN)
        3. NoiseChemotaxisController (random baseline, no olfaction)

    Parameters
    ----------
    n_episodes : int
        Number of episodes per controller.
    duration_s : float
        Duration of each episode in seconds.
    """
    from ..arenas import Arena, PointSource
    from .common import BenchmarkRunner

    # Default arena: point source at (5, 0), fly starts near (0, 0)
    field = PointSource(position=(5.0, 0.0), sigma=2.0)
    arena = Arena("point_source", size_mm=(10.0, 10.0), concentration_field=field)

    controllers = [
        (
            "biological_olfactory",
            lambda: ChemotaxisController(
                arena, episode_length_s=duration_s, olfactory_gain=0.1
            ),
        ),
        (
            "cpg_olfactory",
            lambda: CPGChemotaxisController(
                arena, episode_length_s=duration_s, olfactory_gain=0.1
            ),
        ),
        (
            "noise_baseline",
            lambda: NoiseChemotaxisController(
                arena, episode_length_s=duration_s
            ),
        ),
    ]

    for name, factory in controllers:
        print(f"\n{'=' * 60}")
        print(f"Running chemotaxis benchmark: {name}")
        print(f"{'=' * 60}")

        runner = BenchmarkRunner(
            controller_factory=factory,
            controller_name=name,
        )
        result = runner.run("chemotaxis", n_episodes=n_episodes)
        print(result.summary_table())

        out_path = f"reports/benchmarks/chemotaxis_{name}.json"
        result.to_json(out_path)
        print(f"\nResults saved to {out_path}")
