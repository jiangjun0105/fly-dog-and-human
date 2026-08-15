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


def plot_burnin_rates(time_bins, rate_traces, superclass_names, title, output_path):
    """Plot per-superclass firing rate time-series during burn-in.

    Parameters
    ----------
    time_bins : ndarray
        Time bin centers in seconds.
    rate_traces : dict
        Mapping of superclass name -> array of firing rates per time bin.
    superclass_names : list[str]
        Ordered superclass names.
    title : str
        Plot title.
    output_path : str or Path
        Where to save the figure.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(14, 6))
    for sc in superclass_names:
        if sc in rate_traces:
            color = SUPERCLASS_COLORS.get(sc, None)
            ax.plot(time_bins, rate_traces[sc], label=sc, color=color, linewidth=1.5)

    ax.axhline(1.0, color='gray', linestyle='--', alpha=0.5, label='_min (1 Hz)')
    ax.axhline(30.0, color='gray', linestyle='--', alpha=0.5, label='_max (30 Hz)')
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Firing rate (Hz)")
    ax.set_title(title)
    ax.legend(loc="upper right", fontsize=8)
    ax.set_ylim(bottom=0)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"Saved: {output_path}")


def plot_raster_subsampled(spike_times, spike_ids, n_neurons, title, output_path,
                           max_spikes=50000, superclass_labels=None):
    """Plot a subsampled raster for large-scale networks.

    Parameters
    ----------
    spike_times : ndarray
        Spike times in ms.
    spike_ids : ndarray
        Neuron indices for each spike.
    n_neurons : int
        Total number of neurons.
    title : str
        Plot title.
    output_path : str or Path
        Where to save the figure.
    max_spikes : int
        Maximum number of spikes to plot (subsampled).
    superclass_labels : ndarray, optional
        Per-neuron superclass string for coloring.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Subsample if needed
    n_spikes = len(spike_times)
    if n_spikes > max_spikes:
        idx = np.random.choice(n_spikes, max_spikes, replace=False)
        idx.sort()
        spike_times = spike_times[idx]
        spike_ids = spike_ids[idx]

    fig, ax = plt.subplots(figsize=(14, 8))
    if superclass_labels is not None:
        colors = [SUPERCLASS_COLORS.get(superclass_labels[int(i)], '#333333')
                  for i in spike_ids]
        ax.scatter(spike_times / 1000.0, spike_ids, c=colors, s=0.3, alpha=0.5)
        # Legend
        unique_sc = sorted(set(superclass_labels))
        legend_elements = [
            Patch(facecolor=SUPERCLASS_COLORS.get(sc, '#333333'), label=sc)
            for sc in unique_sc if sc in SUPERCLASS_COLORS
        ]
        ax.legend(handles=legend_elements, loc="upper right", fontsize=7)
    else:
        ax.scatter(spike_times / 1000.0, spike_ids, c='black', s=0.3, alpha=0.5)

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Neuron index")
    ax.set_title(title)
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
