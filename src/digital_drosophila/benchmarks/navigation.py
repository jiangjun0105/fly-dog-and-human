"""Navigation benchmark: open-field exploration metrics from XY trajectory.

Metrics computed:
    - area_explored: fraction of grid cells visited (0-1)
    - path_tortuosity: total_path_length / net_displacement
    - mean_speed_mm_per_s: total path length / duration
    - boundary_contacts: number of times fly hit arena boundary
    - max_displacement_mm: furthest point from start
    - exploration_rate: new cells visited per second

Usage:
    python -c "from digital_drosophila.benchmarks.navigation import run_navigation_benchmark; run_navigation_benchmark()"
"""

from __future__ import annotations

import os

os.environ.setdefault("MUJOCO_GL", "egl")

import numpy as np


def compute_navigation_metrics(
    positions: np.ndarray,
    arena_size_mm: tuple[float, float],
    duration_s: float,
    grid_cell_mm: float = 0.5,
) -> dict[str, float]:
    """Compute navigation metrics from XY trajectory.

    Parameters
    ----------
    positions : (T, 2) array of XY positions in mm
    arena_size_mm : (width, height) of arena
    duration_s : episode duration in seconds
    grid_cell_mm : size of each exploration grid cell

    Returns
    -------
    dict with navigation metric name -> value
    """
    positions = np.asarray(positions)
    T = len(positions)

    if T < 2:
        return {
            "area_explored": 0.0,
            "path_tortuosity": 1.0,
            "mean_speed_mm_per_s": 0.0,
            "boundary_contacts": 0.0,
            "max_displacement_mm": 0.0,
            "exploration_rate": 0.0,
        }

    # Path length and displacement
    deltas = np.diff(positions, axis=0)
    step_lengths = np.linalg.norm(deltas, axis=1)
    total_path_length = float(np.sum(step_lengths))
    net_displacement = float(np.linalg.norm(positions[-1] - positions[0]))

    # Tortuosity: total_path / net_displacement (minimum 1.0 for straight line)
    if net_displacement > 1e-9:
        path_tortuosity = total_path_length / net_displacement
    else:
        path_tortuosity = float("inf") if total_path_length > 1e-9 else 1.0

    # Mean speed
    mean_speed_mm_per_s = total_path_length / duration_s

    # Max displacement from start
    displacements_from_start = np.linalg.norm(positions - positions[0], axis=1)
    max_displacement_mm = float(np.max(displacements_from_start))

    # Area explored: discretize into grid cells
    w, h = arena_size_mm
    n_cols = max(1, int(np.ceil(w / grid_cell_mm)))
    n_rows = max(1, int(np.ceil(h / grid_cell_mm)))
    total_cells = n_cols * n_rows

    # Map positions to grid indices (center arena at origin)
    grid_x = np.floor((positions[:, 0] + w / 2) / grid_cell_mm).astype(int)
    grid_y = np.floor((positions[:, 1] + h / 2) / grid_cell_mm).astype(int)

    # Clamp to valid range
    grid_x = np.clip(grid_x, 0, n_cols - 1)
    grid_y = np.clip(grid_y, 0, n_rows - 1)

    # Count unique cells visited
    cell_ids = grid_y * n_cols + grid_x
    unique_cells = len(np.unique(cell_ids))
    area_explored = unique_cells / total_cells

    # Exploration rate: unique cells per second
    exploration_rate = unique_cells / duration_s

    # Boundary contacts: count transitions from inside to outside arena boundary
    half_w, half_h = w / 2, h / 2
    outside = (
        (np.abs(positions[:, 0]) >= half_w)
        | (np.abs(positions[:, 1]) >= half_h)
    )
    # Count rising edges (transitions from inside to outside)
    boundary_contacts = int(np.sum(np.diff(outside.astype(int)) > 0))

    return {
        "area_explored": float(area_explored),
        "path_tortuosity": float(path_tortuosity),
        "mean_speed_mm_per_s": float(mean_speed_mm_per_s),
        "boundary_contacts": float(boundary_contacts),
        "max_displacement_mm": float(max_displacement_mm),
        "exploration_rate": float(exploration_rate),
    }


class NavigationController:
    """Wraps any base controller for navigation benchmarking.

    Tracks XY positions each step and detects virtual boundary contacts.
    """

    def __init__(
        self,
        base_controller,
        arena_size_mm: tuple[float, float] = (10.0, 10.0),
        coupling_dt_ms: float = 2.0,
    ):
        self._ctrl = base_controller
        self._arena_size = arena_size_mm
        self._coupling_dt_ms = coupling_dt_ms
        self.positions: list[np.ndarray] = []

    def reset(self) -> None:
        self._ctrl.reset()
        self.positions.clear()
        self._record_position()

    def step(self) -> None:
        self._ctrl.step()
        self._record_position()

    def _record_position(self) -> None:
        # Access body XY from MuJoCo qpos (first 2 elements)
        data = self._ctrl._data
        self.positions.append(data.qpos[0:2].copy())

    @property
    def done(self) -> bool:
        return self._ctrl.done

    def get_metrics(self) -> dict[str, float]:
        positions = np.array(self.positions)
        duration_s = len(positions) * (self._coupling_dt_ms / 1000.0)
        return compute_navigation_metrics(
            positions, self._arena_size, duration_s=duration_s
        )

    def close(self) -> None:
        self._ctrl.close()


def run_navigation_benchmark(n_episodes: int = 5, duration_s: float = 5.0) -> None:
    """Run open-field exploration benchmark with CPG and noise controllers.

    Parameters
    ----------
    n_episodes : int
        Number of episodes per controller.
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
    print(f"Navigation Benchmark — {n_episodes} episodes × {duration_s}s each")
    print("=" * 60)

    # CPG controller
    print("\n[1/2] CPG Controller (scripted tripod)...")
    runner = BenchmarkRunner(
        controller_factory=lambda: NavigationController(
            CPGController(episode_length_s=duration_s),
            arena_size_mm=(10.0, 10.0),
        ),
        controller_name="cpg_tripod",
    )
    results.append(runner.run("navigation", n_episodes=n_episodes))

    # Noise controller
    print("[2/2] Noise Controller (random actuators)...")
    runner = BenchmarkRunner(
        controller_factory=lambda: NavigationController(
            NoiseController(episode_length_s=duration_s),
            arena_size_mm=(10.0, 10.0),
        ),
        controller_name="noise",
    )
    results.append(runner.run("navigation", n_episodes=n_episodes))

    # Print comparison
    print("\n" + "=" * 60)
    print("RESULTS COMPARISON")
    print("=" * 60)
    for r in results:
        print(f"\n{r.summary_table()}")
        r.to_json(reports_dir / f"navigation_{r.controller_name}.json")

    # Generate comparison plot
    try:
        from .plotting import plot_metric_comparison

        plot_metric_comparison(
            results, output_path=reports_dir / "navigation_comparison.png"
        )
        print(f"\nComparison plot: {reports_dir / 'navigation_comparison.png'}")
    except Exception as e:
        print(f"\nPlot generation failed: {e}")

    print(f"\nAll results saved to {reports_dir}/")
