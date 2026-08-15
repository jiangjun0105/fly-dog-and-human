from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .common import BenchmarkResult

# Standard color map for known controller types.
CONTROLLER_COLORS = {
    "biological": "tab:blue",
    "random": "tab:orange",
    "cpg": "tab:green",
    "zero": "tab:gray",
    "noise": "tab:red",
}


def _apply_style() -> None:
    """Apply publication-quality plot style with graceful fallback."""
    import matplotlib.pyplot as plt

    try:
        plt.style.use("seaborn-v0_8-whitegrid")
    except OSError:
        pass  # fall back to default style


def _controller_color(name: str, idx: int = 0):
    """Get color for a controller by name, falling back to tab10 cycle."""
    import matplotlib.pyplot as plt

    if name in CONTROLLER_COLORS:
        return CONTROLLER_COLORS[name]
    import matplotlib
    cmap = matplotlib.colormaps["tab10"]
    return cmap(idx % 10)


def _save_or_show(fig, output_path: str | Path | None) -> None:
    """Save figure to file or display (headless-safe)."""
    import matplotlib.pyplot as plt

    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
    else:
        try:
            plt.show()
        except Exception:
            plt.close(fig)


def plot_metric_comparison(
    results: Sequence[BenchmarkResult],
    metrics: list[str] | None = None,
    output_path: str | Path | None = None,
) -> None:
    """Bar chart comparing scalar metrics across multiple controllers.

    Produces grouped bars with error bars (one group per metric, one bar per
    controller).
    """
    import matplotlib.pyplot as plt
    import numpy as np

    _apply_style()

    if not results:
        return

    if metrics is None:
        metrics = list(results[0].scalar_metrics.keys())

    n_metrics = len(metrics)
    n_controllers = len(results)
    x = np.arange(n_metrics)
    width = 0.8 / max(n_controllers, 1)

    fig, ax = plt.subplots(figsize=(10, 6))

    for i, result in enumerate(results):
        means = [result.scalar_metrics.get(m, 0.0) for m in metrics]
        stds = [result.metric_stds.get(m, 0.0) for m in metrics]
        offset = (i - n_controllers / 2 + 0.5) * width
        color = _controller_color(result.controller_name, i)
        ax.bar(
            x + offset,
            means,
            width,
            yerr=stds,
            label=result.controller_name,
            capsize=3,
            color=color,
            edgecolor="white",
            linewidth=0.5,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(metrics, rotation=30, ha="right")
    ax.legend(
        loc="upper left",
        bbox_to_anchor=(1.02, 1),
        borderaxespad=0,
    )
    ax.set_title(results[0].benchmark_name)
    ax.set_ylabel("Value")

    _save_or_show(fig, output_path)


def plot_gait_ethogram(
    leg_contacts,
    dt: float,
    duration_s: float | None = None,
    title: str = "",
    output_path: str | Path | None = None,
) -> None:
    """Plot a gait ethogram showing stance/swing phases for 6 legs.

    Parameters
    ----------
    leg_contacts : array-like, shape (T, 6)
        Boolean array where True = stance (foot on ground).
        Column order: LF, LM, LH, RF, RM, RH.
    dt : float
        Simulation timestep in seconds.
    duration_s : float, optional
        Clip display to this many seconds. If None, show full trace.
    title : str
        Plot title.
    output_path : str or Path, optional
        If provided, save figure to this path.
    """
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.patches import Rectangle
    from matplotlib.collections import PatchCollection

    _apply_style()

    contacts = np.asarray(leg_contacts, dtype=bool)
    T = contacts.shape[0]
    time_axis = np.arange(T) * dt

    if duration_s is not None:
        n_samples = min(T, int(duration_s / dt))
        contacts = contacts[:n_samples]
        time_axis = time_axis[:n_samples]
        T = n_samples

    leg_labels = ["LF", "LM", "LH", "RF", "RM", "RH"]
    # Left legs in blue shades, right legs in red/orange shades
    leg_colors = [
        "#1f77b4",  # LF - dark blue
        "#4a9fd5",  # LM - medium blue
        "#7ec8e3",  # LH - light blue
        "#d62728",  # RF - red
        "#e57320",  # RM - orange
        "#f5a623",  # RH - light orange
    ]

    fig, ax = plt.subplots(figsize=(10, 4))

    bar_height = 0.7

    for leg_idx in range(6):
        # Find contiguous stance intervals
        contact_signal = contacts[:, leg_idx].astype(int)
        # Detect transitions
        diff = np.diff(contact_signal, prepend=0, append=0)
        starts = np.where(diff == 1)[0]
        ends = np.where(diff == -1)[0]

        patches = []
        for s, e in zip(starts, ends):
            t_start = s * dt
            t_end = e * dt
            rect = Rectangle(
                (t_start, leg_idx - bar_height / 2),
                t_end - t_start,
                bar_height,
            )
            patches.append(rect)

        if patches:
            collection = PatchCollection(
                patches,
                facecolor=leg_colors[leg_idx],
                edgecolor="none",
                alpha=0.85,
            )
            ax.add_collection(collection)

    ax.set_xlim(0, time_axis[-1])
    ax.set_ylim(-0.5, 5.5)
    ax.set_yticks(range(6))
    ax.set_yticklabels(leg_labels)
    ax.set_xlabel("Time (s)")
    ax.set_title(title if title else "Gait Ethogram")

    # Add light gridlines on x-axis only
    ax.grid(axis="x", alpha=0.3)
    ax.grid(axis="y", visible=False)

    # Add legend for stance
    from matplotlib.patches import Patch

    left_patch = Patch(facecolor="#1f77b4", label="Left stance")
    right_patch = Patch(facecolor="#d62728", label="Right stance")
    ax.legend(handles=[left_patch, right_patch], loc="upper right", fontsize=9)

    _save_or_show(fig, output_path)


def plot_trajectory_overlay(
    trajectories: dict,
    source_position=None,
    arena_bounds: tuple[float, float, float, float] | None = None,
    output_path: str | Path | None = None,
) -> None:
    """Plot overhead XY trajectories for multiple controllers.

    Parameters
    ----------
    trajectories : dict
        Mapping of controller_name -> (T, 2) position array.
    source_position : array-like, optional
        (x, y) position of odor source to mark with a star.
    arena_bounds : tuple, optional
        (x_min, x_max, y_min, y_max) for arena rectangle.
    output_path : str or Path, optional
        If provided, save figure to this path.
    """
    import matplotlib.pyplot as plt
    import numpy as np

    _apply_style()

    fig, ax = plt.subplots(figsize=(10, 6))

    for idx, (name, traj) in enumerate(trajectories.items()):
        traj = np.asarray(traj)
        color = _controller_color(name, idx)

        # Plot trajectory line
        ax.plot(
            traj[:, 0],
            traj[:, 1],
            color=color,
            linewidth=1.5,
            alpha=0.8,
            label=name,
        )
        # Start marker (circle)
        ax.plot(
            traj[0, 0],
            traj[0, 1],
            "o",
            color=color,
            markersize=8,
            markeredgecolor="white",
            markeredgewidth=1.0,
        )
        # End marker (triangle)
        ax.plot(
            traj[-1, 0],
            traj[-1, 1],
            "^",
            color=color,
            markersize=10,
            markeredgecolor="white",
            markeredgewidth=1.0,
        )

    # Odor source position
    if source_position is not None:
        src = np.asarray(source_position)
        ax.plot(
            src[0],
            src[1],
            "*",
            color="gold",
            markersize=18,
            markeredgecolor="black",
            markeredgewidth=0.8,
            label="Odor source",
            zorder=10,
        )

    # Arena bounds
    if arena_bounds is not None:
        x_min, x_max, y_min, y_max = arena_bounds
        from matplotlib.patches import Rectangle

        rect = Rectangle(
            (x_min, y_min),
            x_max - x_min,
            y_max - y_min,
            fill=False,
            edgecolor="black",
            linewidth=1.5,
            linestyle="--",
            label="Arena",
        )
        ax.add_patch(rect)

    ax.set_xlabel("X position")
    ax.set_ylabel("Y position")
    ax.set_title("Trajectory Overlay")
    ax.set_aspect("equal", adjustable="datalim")
    ax.legend(
        loc="upper left",
        bbox_to_anchor=(1.02, 1),
        borderaxespad=0,
    )

    _save_or_show(fig, output_path)


def plot_radar(
    results: Sequence[BenchmarkResult],
    metrics: list[str] | None = None,
    output_path: str | Path | None = None,
) -> None:
    """Spider/radar plot comparing controllers across normalized metrics.

    Each controller forms a polygon on the radar chart with one axis per
    metric, all normalized to [0, 1] across the set of results.

    Parameters
    ----------
    results : sequence of BenchmarkResult
        Results to compare.
    metrics : list of str, optional
        Metric names to plot. Defaults to all metrics in first result.
    output_path : str or Path, optional
        If provided, save figure to this path.
    """
    import matplotlib.pyplot as plt
    import numpy as np

    _apply_style()

    if not results:
        return

    if metrics is None:
        metrics = list(results[0].scalar_metrics.keys())

    n_metrics = len(metrics)
    if n_metrics < 3:
        # Radar plots need at least 3 axes to be meaningful
        return

    # Gather values and normalize to [0, 1]
    raw_values = []
    for result in results:
        vals = [result.scalar_metrics.get(m, 0.0) for m in metrics]
        raw_values.append(vals)
    raw_values = np.array(raw_values)  # shape: (n_controllers, n_metrics)

    # Normalize each metric column to [0, 1]
    mins = raw_values.min(axis=0)
    maxs = raw_values.max(axis=0)
    ranges = maxs - mins
    # Avoid division by zero for constant metrics
    ranges[ranges == 0] = 1.0
    normalized = (raw_values - mins) / ranges

    # Compute angle for each axis
    angles = np.linspace(0, 2 * np.pi, n_metrics, endpoint=False).tolist()
    # Close the polygon
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={"polar": True})

    for i, result in enumerate(results):
        values = normalized[i].tolist()
        values += values[:1]  # close polygon
        color = _controller_color(result.controller_name, i)

        ax.plot(
            angles,
            values,
            color=color,
            linewidth=2,
            label=result.controller_name,
        )
        ax.fill(
            angles,
            values,
            color=color,
            alpha=0.15,
        )

    # Set metric labels
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metrics, fontsize=9)

    # Radial ticks
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0.25", "0.5", "0.75", "1.0"], fontsize=7, alpha=0.6)

    ax.set_title(
        f"Radar: {results[0].benchmark_name}" if results else "Radar",
        y=1.08,
    )
    ax.legend(
        loc="upper right",
        bbox_to_anchor=(1.3, 1.1),
    )

    _save_or_show(fig, output_path)
