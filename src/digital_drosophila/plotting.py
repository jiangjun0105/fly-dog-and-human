"""Visualization: raster plots, rate analysis, and figure saving.

All plotting uses the 'Agg' backend for headless environments.
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
import numpy as np  # noqa: E402

# Default color scheme for superclasses
SUPERCLASS_COLORS = {
    "descending_neuron": "#e74c3c",
    "vnc_intrinsic": "#3498db",
    "vnc_motor": "#2ecc71",
    "ascending_neuron": "#9b59b6",
}


def plot_raster_minimal(spike_monitor, title, output_path):
    """Plot a single-color raster and save to file.

    Parameters
    ----------
    spike_monitor : SpikeMonitor
        Brian2 SpikeMonitor with recorded spikes.
    title : str
        Plot title.
    output_path : str or Path
        Where to save the figure.
    """
    from brian2 import ms as brian_ms

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(12, 6))
    plt.plot(np.array(spike_monitor.t / brian_ms), np.array(spike_monitor.i),
             ".k", markersize=1)
    plt.xlabel("Time (ms)")
    plt.ylabel("Neuron index")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"Saved: {output_path}")


def plot_raster(spike_monitor, neurons_df, title, output_path, colors=None):
    """Plot a color-coded raster by superclass and save to file.

    Parameters
    ----------
    spike_monitor : SpikeMonitor
        Brian2 SpikeMonitor with recorded spikes.
    neurons_df : DataFrame
        Neuron metadata with 'superclass' column.
    title : str
        Plot title.
    output_path : str or Path
        Where to save the figure.
    colors : dict, optional
        Mapping of superclass -> color hex. Defaults to SUPERCLASS_COLORS.
    """
    from brian2 import ms as brian_ms

    if colors is None:
        colors = SUPERCLASS_COLORS

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Assign color to each spike based on neuron superclass
    spike_colors = [colors.get(neurons_df.iloc[int(i)]["superclass"], "#333333")
                    for i in spike_monitor.i]

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.scatter(np.array(spike_monitor.t / brian_ms), np.array(spike_monitor.i),
               c=spike_colors, s=1, alpha=0.7)
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Neuron index")
    ax.set_title(title)

    # Add legend
    legend_elements = [
        Patch(facecolor=color,
              label=f"{sc} ({len(neurons_df[neurons_df['superclass']==sc])})")
        for sc, color in colors.items()
    ]
    ax.legend(handles=legend_elements, loc="upper right", fontsize=8)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"Saved: {output_path}")
