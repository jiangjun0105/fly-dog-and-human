"""Simulation runner: configure, run, and collect results.

Provides high-level functions to run the minimal and constrained simulations,
computing firing rates and producing raster plots.
"""

import time
from pathlib import Path

import numpy as np
from brian2 import SpikeMonitor, run, second, Hz, mV, prefs

from .network import (
    load_sample_data,
    create_neuron_group,
    create_synapses_minimal,
    create_synapses_constrained,
    create_poisson_drive,
    create_background_drive,
)
from .plotting import plot_raster_minimal, plot_raster

# Reports directory (project root / reports)
_PACKAGE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _PACKAGE_DIR.parent.parent  # src/ -> project root
_REPORTS_DIR = _PROJECT_ROOT / "reports"


def compute_firing_rates(spike_monitor, neurons_df, duration_s=1.0):
    """Compute per-superclass firing rates.

    Parameters
    ----------
    spike_monitor : SpikeMonitor
        Brian2 SpikeMonitor with recorded spikes.
    neurons_df : DataFrame
        Neuron metadata with 'superclass' column.
    duration_s : float
        Simulation duration in seconds.

    Returns
    -------
    rates : dict
        Mapping of superclass name -> mean firing rate in Hz.
    """
    spike_indices = np.array(spike_monitor.i)
    rates = {}
    for sc in sorted(neurons_df["superclass"].unique()):
        idx = neurons_df[neurons_df["superclass"] == sc].index.values
        spikes_in_group = np.isin(spike_indices, idx).sum()
        rate = spikes_in_group / (len(idx) * duration_s)
        rates[sc] = rate
    return rates


def validate_rates(rates, min_hz=1.0, max_hz=30.0):
    """Check if all firing rates are within biological range.

    Parameters
    ----------
    rates : dict
        Mapping of superclass -> firing rate in Hz.
    min_hz : float
        Minimum acceptable rate.
    max_hz : float
        Maximum acceptable rate.

    Returns
    -------
    bool
        True if all rates are within [min_hz, max_hz].
    """
    return all(min_hz <= r <= max_hz for r in rates.values())


def run_minimal():
    """Run the minimal (raw-weight) simulation.

    Loads connectome data, builds a 100-neuron LIF network with raw synapse-count
    weights, drives descending neurons with Poisson input, and produces a raster plot.
    """
    # Ensure numpy codegen is set before any Brian2 objects are created
    prefs.codegen.target = "numpy"

    # Load data
    adj, neurons_df = load_sample_data()
    n = adj.shape[0]

    print(f"Loaded {n}-neuron adjacency matrix ({np.count_nonzero(adj)} synapses)")
    print(f"Neuron superclass distribution: {dict(neurons_df['superclass'].value_counts())}")

    # Create neuron group
    G = create_neuron_group(n)

    # Create synapses
    S, sources, targets = create_synapses_minimal(G, adj, scale=0.02)
    print(f"Connected {len(sources)} synapses (scale=0.02 mV)")

    # External input: Poisson drive to descending neurons
    PG, S_input, descending_idx = create_poisson_drive(
        G, neurons_df, target_superclass="descending_neuron",
        n_sources=50, rate=30 * Hz, weight=2.0 * mV,
    )
    print(f"Driving {len(descending_idx)} descending neurons with Poisson input")

    # Monitor and run
    M = SpikeMonitor(G)

    print("Running simulation (1 second)...")
    t_start = time.time()
    run(1 * second)
    t_elapsed = time.time() - t_start

    print(f"Simulation completed in {t_elapsed:.1f}s")
    print(f"Total spikes: {M.num_spikes}")
    print(f"Mean rate: {M.num_spikes / n:.1f} Hz")

    # Plot raster
    output_path = _REPORTS_DIR / "brian2_minimal_raster.png"
    title = f"Raster plot — {M.num_spikes} spikes from {n} LIF neurons (1s)"
    plot_raster_minimal(M, title, output_path)


def run_constrained():
    """Run the biologically-constrained simulation.

    Loads connectome data, builds a 100-neuron LIF network with sign-constrained
    weights (Dale's principle), background drive, and produces a color-coded
    raster plot with per-superclass firing rate statistics.
    """
    # Ensure numpy codegen is set before any Brian2 objects are created
    prefs.codegen.target = "numpy"

    # Load data
    adj, neurons_df = load_sample_data()
    n = adj.shape[0]

    print(f"Loaded {n}-neuron adjacency matrix ({np.count_nonzero(adj)} synapses)")
    print(f"Neuron superclass distribution: {dict(neurons_df['superclass'].value_counts())}")

    # E/I ratio from neurotransmitter types
    from .constants import NT_SIGN_MAP
    nt_series = neurons_df["consensusNt"]
    sign_vector_check = np.array([NT_SIGN_MAP.get(nt, 0) or 0 for nt in nt_series])

    n_excitatory = int((sign_vector_check == 1).sum())
    n_inhibitory = int((sign_vector_check == -1).sum())
    n_unclear = int((sign_vector_check == 0).sum())

    print(f"\nE/I ratio:")
    print(f"  excitatory: {n_excitatory} (acetylcholine, sign=+1)")
    print(f"  inhibitory: {n_inhibitory} (gaba, sign=-1)")
    print(f"  unclear: {n_unclear} (unclear NT, sign=0)")
    print(f"  ratio (E/I): {n_excitatory}/{n_inhibitory} = {n_excitatory/n_inhibitory:.2f}")

    # Create neuron group
    G = create_neuron_group(n)

    # Create sign-constrained synapses
    S, sources, targets, weights_raw, sign_vector = create_synapses_constrained(
        G, adj, neurons_df, scale=0.6, inh_attenuation=0.5,
    )

    # Print weight statistics
    w_exc = weights_raw[weights_raw > 0]
    w_inh = weights_raw[weights_raw < 0]
    w_zero = weights_raw[weights_raw == 0]
    print(f"\nWeight statistics (mV):")
    print(f"  Excitatory: n={len(w_exc)}, mean={w_exc.mean():.2f}, max={w_exc.max():.2f}")
    print(f"  Inhibitory: n={len(w_inh)}, mean={w_inh.mean():.2f}, min={w_inh.min():.2f}")
    print(f"  Zero (unclear): n={len(w_zero)}")
    print(f"  Total synapses: {len(sources)}")

    # External input: Poisson drive to descending neurons
    PG, S_input, descending_idx = create_poisson_drive(
        G, neurons_df, target_superclass="descending_neuron",
        n_sources=15, rate=10 * Hz, weight=2.0 * mV,
    )
    print(f"\nDriving {len(descending_idx)} descending neurons with Poisson input")

    # Background input to all neurons
    PG_bg, S_bg = create_background_drive(G, n, n_sources=50, rate=22 * Hz, weight=1.3 * mV)
    print(f"Background drive: 50 sources at 22 Hz to all {n} neurons")

    # Monitor and run
    M = SpikeMonitor(G)

    print("\nRunning simulation (1 second)...")
    t_start = time.time()
    run(1 * second)
    t_elapsed = time.time() - t_start

    print(f"Simulation completed in {t_elapsed:.1f}s")
    print(f"Total spikes: {M.num_spikes}")
    print(f"Mean rate (all neurons): {M.num_spikes / n:.1f} Hz")

    # Per-superclass firing rate statistics
    print("\nPer-superclass firing rates:")
    rates = compute_firing_rates(M, neurons_df, duration_s=1.0)
    for sc, rate in rates.items():
        idx = neurons_df[neurons_df["superclass"] == sc].index.values
        spikes_in_group = np.isin(np.array(M.i), idx).sum()
        print(f"  {sc}: {rate:.1f} Hz ({len(idx)} neurons, {spikes_in_group} spikes)")

    if validate_rates(rates):
        print("\n  All superclass rates within biological range (1-30 Hz)")
    else:
        print("\n  WARNING: Some rates outside 1-30 Hz range — consider tuning scale factor")

    # Color-coded raster plot
    output_path = _REPORTS_DIR / "brian2_constrained_raster.png"
    title = (
        f"Biologically-constrained raster — {M.num_spikes} spikes, "
        f"{n} LIF neurons (E:{n_excitatory}/I:{n_inhibitory}/U:{n_unclear})"
    )
    plot_raster(M, neurons_df, title, output_path)
