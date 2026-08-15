"""Locomotion benchmark: compute walking metrics from CoSimulation episodes.

Metrics computed:
    - forward_speed_mm_per_s: net X displacement / duration
    - lateral_deviation_mm: RMS of Y position relative to start
    - speed_variability: CV of instantaneous speed
    - turn_bias_deg_per_s: net heading change / duration
    - energy_efficiency: forward distance / sum(|actuator_deltas|)
    - stance_stability: fraction of steps with >=3 legs grounded
    - fall_detected: 1.0 if thorax Z dropped below threshold

Usage:
    python -c "from digital_drosophila.benchmarks.locomotion import run_locomotion_benchmark; run_locomotion_benchmark()"
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


def compute_locomotion_metrics(trajectory: dict) -> dict[str, float]:
    """Compute locomotion metrics from recorded trajectory data.

    Parameters
    ----------
    trajectory : dict
        Must contain:
            positions: (T, 3) array of body CoM [x, y, z] in mm
            headings: (T,) array of yaw angles in radians
            actions: (T, N) array of actuator commands
            dt: float, timestep between samples in seconds
        Optional:
            leg_contacts: (T, 6) boolean array, True if leg has ground contact

    Returns
    -------
    dict[str, float]
        Locomotion metric name -> value.
    """
    positions = np.asarray(trajectory["positions"])
    headings = np.asarray(trajectory["headings"])
    actions = np.asarray(trajectory["actions"])
    dt = float(trajectory["dt"])
    leg_contacts = trajectory.get("leg_contacts")

    T = len(positions)
    if T < 2:
        return {
            "forward_speed_mm_per_s": 0.0,
            "lateral_deviation_mm": 0.0,
            "speed_variability": 0.0,
            "turn_bias_deg_per_s": 0.0,
            "energy_efficiency": 0.0,
            "stance_stability": 1.0,
            "fall_detected": 0.0,
        }

    duration_s = (T - 1) * dt

    # Forward speed: net X displacement / duration
    forward_displacement = positions[-1, 0] - positions[0, 0]
    forward_speed_mm_per_s = forward_displacement / duration_s

    # Lateral deviation: RMS of Y position relative to start
    y_deviations = positions[:, 1] - positions[0, 1]
    lateral_deviation_mm = float(np.sqrt(np.mean(y_deviations**2)))

    # Speed variability: CV of instantaneous speed
    displacements = np.diff(positions[:, :2], axis=0)
    inst_speeds = np.linalg.norm(displacements, axis=1) / dt
    mean_speed = np.mean(inst_speeds)
    if mean_speed > 1e-9:
        speed_variability = float(np.std(inst_speeds) / mean_speed)
    else:
        speed_variability = 0.0

    # Turn bias: net heading change / duration (in deg/s)
    net_heading_change = headings[-1] - headings[0]
    turn_bias_deg_per_s = float(np.degrees(net_heading_change) / duration_s)

    # Energy efficiency: forward distance / sum(|actuator_deltas|)
    actuator_deltas = np.diff(actions, axis=0)
    total_effort = float(np.sum(np.abs(actuator_deltas)))
    if total_effort > 1e-9:
        energy_efficiency = abs(forward_displacement) / total_effort
    else:
        energy_efficiency = 0.0

    # Stance stability: fraction of steps with >= 3 legs grounded
    if leg_contacts is not None:
        leg_contacts = np.asarray(leg_contacts)
        grounded_count = np.sum(leg_contacts, axis=1)
        stance_stability = float(np.mean(grounded_count >= 3))
    else:
        # Assume all legs grounded if data not available
        stance_stability = 1.0

    # Fall detection: thorax Z below threshold
    # Neutral standing Z is ~0.6 mm in the spawn config; a fall means Z < 0.3
    min_z = float(np.min(positions[:, 2]))
    fall_threshold = 0.3
    fall_detected = 1.0 if min_z < fall_threshold else 0.0

    metrics = {
        "forward_speed_mm_per_s": forward_speed_mm_per_s,
        "lateral_deviation_mm": lateral_deviation_mm,
        "speed_variability": speed_variability,
        "turn_bias_deg_per_s": turn_bias_deg_per_s,
        "energy_efficiency": energy_efficiency,
        "stance_stability": stance_stability,
        "fall_detected": fall_detected,
    }

    # Gait analysis if leg contacts available
    if leg_contacts is not None and len(leg_contacts) > 10:
        from .gait import analyze_gait

        gait_metrics = analyze_gait(np.asarray(leg_contacts), dt)
        metrics.update(gait_metrics)

    return metrics


class TrajectoryCollector:
    """Wraps a CoSimulation to collect per-step trajectory data for metrics."""

    def __init__(self, sim):
        """Wrap an existing CoSimulation instance.

        Parameters
        ----------
        sim : CoSimulation
            The co-simulation instance (already constructed).
        """
        self._sim = sim
        self.positions: list[np.ndarray] = []
        self.headings: list[float] = []
        self.actions: list[np.ndarray] = []
        self.leg_contacts: list[np.ndarray] = []

    def reset(self) -> None:
        self._sim.reset()
        self.positions.clear()
        self.headings.clear()
        self.actions.clear()
        self.leg_contacts.clear()
        self._record_state()

    def step(self) -> None:
        self._sim.step()
        self._record_state()

    def _record_state(self) -> None:
        data = self._sim._data
        # Body position (x, y, z)
        self.positions.append(data.qpos[0:3].copy())
        # Yaw from quaternion (wxyz format in MuJoCo)
        quat = data.qpos[3:7]
        self.headings.append(_quat_to_yaw(quat))
        # Current actuator commands
        self.actions.append(data.ctrl.copy())
        # Leg contacts: use sensordata if available (6 legs x 16-dim plugin)
        # Detect contact by checking if any force component is nonzero per leg
        try:
            sensor_data = data.sensordata
            n_legs = 6
            dim_per_leg = len(sensor_data) // n_legs if len(sensor_data) >= 6 else 0
            if dim_per_leg > 0:
                contacts = np.zeros(n_legs, dtype=bool)
                for i in range(n_legs):
                    leg_sensor = sensor_data[i * dim_per_leg:(i + 1) * dim_per_leg]
                    contacts[i] = np.any(np.abs(leg_sensor) > 1e-6)
                self.leg_contacts.append(contacts)
            else:
                self.leg_contacts.append(np.ones(6, dtype=bool))
        except (AttributeError, IndexError):
            self.leg_contacts.append(np.ones(6, dtype=bool))

    @property
    def done(self) -> bool:
        return self._sim.done

    def get_trajectory(self) -> dict:
        """Return trajectory data suitable for compute_locomotion_metrics."""
        return {
            "positions": np.array(self.positions),
            "headings": np.array(self.headings),
            "actions": np.array(self.actions),
            "dt": self._sim.coupling_dt_ms / 1000.0,
            "leg_contacts": np.array(self.leg_contacts) if self.leg_contacts else None,
        }

    def get_metrics(self) -> dict[str, float]:
        """Compute locomotion metrics from collected trajectory."""
        return compute_locomotion_metrics(self.get_trajectory())

    def close(self) -> None:
        self._sim.close()


class BiologicalController:
    """Adapts CoSimulation + TrajectoryCollector to the Controller protocol.

    Converts `done` property into a method as required by BenchmarkRunner.
    """

    def __init__(self, episode_length_s: float = 5.0):
        from ..loop import CoSimulation

        self._sim = CoSimulation(episode_length_s=episode_length_s)
        self._collector = TrajectoryCollector(self._sim)

    def reset(self) -> None:
        self._collector.reset()

    def step(self) -> None:
        self._collector.step()

    @property
    def done(self) -> bool:
        return self._collector.done

    def get_metrics(self) -> dict[str, float]:
        return self._collector.get_metrics()

    def close(self) -> None:
        self._collector.close()


def run_locomotion_benchmark(n_episodes: int = 10, duration_s: float = 5.0) -> None:
    """Run locomotion benchmark with multiple controllers and produce comparison.

    Parameters
    ----------
    n_episodes : int
        Number of episodes to run per controller.
    duration_s : float
        Duration of each episode in seconds.
    """
    from pathlib import Path

    from .baselines import CPGController, NoiseController
    from .common import BenchmarkRunner

    reports_dir = Path("reports/benchmarks")
    reports_dir.mkdir(parents=True, exist_ok=True)

    results = []

    print("=" * 60)
    print(f"Locomotion Benchmark — {n_episodes} episodes × {duration_s}s each")
    print("=" * 60)

    # CPG (fast, deterministic)
    print("\n[1/3] CPG Controller (scripted tripod)...")
    runner = BenchmarkRunner(
        controller_factory=lambda: CPGController(episode_length_s=duration_s),
        controller_name="cpg_tripod",
    )
    results.append(runner.run("locomotion", n_episodes=n_episodes))

    # Noise (fast, random)
    print("[2/3] Noise Controller (random actuators)...")
    runner = BenchmarkRunner(
        controller_factory=lambda: NoiseController(episode_length_s=duration_s),
        controller_name="noise",
    )
    results.append(runner.run("locomotion", n_episodes=n_episodes))

    # Biological (slow)
    print("[3/3] Biological Controller (connectome SNN)...")
    runner = BenchmarkRunner(
        controller_factory=lambda: BiologicalController(episode_length_s=duration_s),
        controller_name="biological",
    )
    results.append(runner.run("locomotion", n_episodes=n_episodes))

    # Print comparison
    print("\n" + "=" * 60)
    print("RESULTS COMPARISON")
    print("=" * 60)
    for r in results:
        print(f"\n{r.summary_table()}")
        r.to_json(reports_dir / f"locomotion_{r.controller_name}.json")

    # Generate comparison plot
    try:
        from .plotting import plot_metric_comparison

        plot_metric_comparison(results, output_path=reports_dir / "locomotion_comparison.png")
        print(f"\nComparison plot: {reports_dir / 'locomotion_comparison.png'}")
    except Exception as e:
        print(f"\nPlot generation failed: {e}")

    print(f"\nAll results saved to {reports_dir}/")
