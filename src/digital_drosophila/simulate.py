"""Simulation runner: configure, run, and collect results.

Provides high-level functions to run the minimal and constrained simulations,
computing firing rates and producing raster plots.

Also provides `run_full_vnc()` for GPU-accelerated full-scale VNC simulation
using PyGeNN 5.x directly (Brian2 does not support GeNN as a backend in v2.10+).
"""

import os
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
_DEFAULT_REPORTS_DIR = _PROJECT_ROOT / "reports"


def _resolve_reports_dir(output_dir=None):
    """Resolve the reports directory.

    Priority:
    1. Explicit *output_dir* argument (if provided).
    2. DIGITAL_DROSOPHILA_REPORTS_DIR environment variable.
    3. Computed default (_DEFAULT_REPORTS_DIR).
    """
    import os

    if output_dir is not None:
        return Path(output_dir)
    env_dir = os.environ.get("DIGITAL_DROSOPHILA_REPORTS_DIR")
    if env_dir:
        return Path(env_dir)
    return _DEFAULT_REPORTS_DIR


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


def run_minimal(output_dir=None):
    """Run the minimal (raw-weight) simulation.

    Loads connectome data, builds a 100-neuron LIF network with raw synapse-count
    weights, drives descending neurons with Poisson input, and produces a raster plot.

    Parameters
    ----------
    output_dir : str or Path, optional
        Directory to write output reports. Falls back to
        DIGITAL_DROSOPHILA_REPORTS_DIR env var, then the computed default.
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
    reports_dir = _resolve_reports_dir(output_dir)
    output_path = reports_dir / "brian2_minimal_raster.png"
    title = f"Raster plot — {M.num_spikes} spikes from {n} LIF neurons (1s)"
    plot_raster_minimal(M, title, output_path)


def run_constrained(output_dir=None):
    """Run the biologically-constrained simulation.

    Loads connectome data, builds a 100-neuron LIF network with sign-constrained
    weights (Dale's principle), background drive, and produces a color-coded
    raster plot with per-superclass firing rate statistics.

    Parameters
    ----------
    output_dir : str or Path, optional
        Directory to write output reports. Falls back to
        DIGITAL_DROSOPHILA_REPORTS_DIR env var, then the computed default.
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
    print(f"  ratio (E/I): {n_excitatory}/{n_inhibitory} = {n_excitatory/max(n_inhibitory, 1):.2f}")

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
    reports_dir = _resolve_reports_dir(output_dir)
    output_path = reports_dir / "brian2_constrained_raster.png"
    title = (
        f"Biologically-constrained raster — {M.num_spikes} spikes, "
        f"{n} LIF neurons (E:{n_excitatory}/I:{n_inhibitory}/U:{n_unclear})"
    )
    plot_raster(M, neurons_df, title, output_path)


def run_full_vnc(output_dir=None, n_neurons=15000):
    """Run the full-scale VNC simulation using PyGeNN GPU backend.

    Loads the VNC connectome (top N neurons by connectivity), builds a LIF
    network on GPU using PyGeNN 5.x, runs a 5-second burn-in with Poisson
    input to sensory/descending neurons, and validates per-superclass firing
    rates.

    Parameters
    ----------
    output_dir : str or Path, optional
        Directory to write output reports.
    n_neurons : int
        Number of neurons to include (sorted by total synapse count).
        Default 15000 covers the most connected VNC neurons (~58% of full
        connectome). Use None for all available (~25k).
    """
    # Ensure CUDA is on PATH
    cuda_bin = "/usr/local/cuda/bin"
    if cuda_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = cuda_bin + ":" + os.environ.get("PATH", "")

    from pygenn import GeNNModel
    from .data import connect, load_vnc_neurons, load_connectivity_sparse, find_nt_column
    from .constants import NT_SIGN_MAP
    from .plotting import plot_burnin_rates, plot_raster_subsampled

    reports_dir = _resolve_reports_dir(output_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    # ---- 1. Load VNC neuron data ----
    print("=" * 70)
    print("FULL VNC SIMULATION (PyGeNN GPU Backend)")
    print("=" * 70)
    print("\n[1/6] Loading VNC neuron data...")
    connect()
    neurons_df, _ = load_vnc_neurons()

    # Determine subset size
    total_available = len(neurons_df)
    if n_neurons is not None:
        n = min(n_neurons, total_available)
    else:
        n = total_available

    # Sort by pre+post synapse count (most connected first) for meaningful subset
    neurons_df = neurons_df.copy()
    neurons_df["total_synapses"] = neurons_df["pre"].fillna(0) + neurons_df["post"].fillna(0)
    neurons_df = neurons_df.sort_values("total_synapses", ascending=False).head(n)
    neurons_df = neurons_df.reset_index(drop=True)
    # Fill NaN superclass with "unknown" to avoid sort errors
    neurons_df["superclass"] = neurons_df["superclass"].fillna("unknown")

    print(f"  Selected {n} neurons (of {total_available} available)")
    print(f"  Superclass distribution:")
    for sc, count in neurons_df["superclass"].value_counts().items():
        print(f"    {sc}: {count}")

    # ---- 2. Load connectivity (sparse) ----
    print(f"\n[2/6] Loading sparse connectivity for {n} neurons...")
    body_ids = tuple(neurons_df["bodyId"].tolist())
    sources, targets, weights = load_connectivity_sparse(body_ids)
    n_synapses = len(sources)
    density = n_synapses / (n * n) * 100
    print(f"  {n_synapses:,} synapses (density: {density:.2f}%)")

    # ---- 3. Compute sign-constrained weights ----
    print("\n[3/6] Computing sign-constrained synaptic weights...")
    nt_col = find_nt_column(neurons_df)
    if nt_col is None:
        nt_col = "consensusNt"

    nt_series = neurons_df[nt_col].fillna("unclear")
    sign_vector = np.array([NT_SIGN_MAP.get(str(nt), 0) or 0 for nt in nt_series], dtype=np.float32)

    # Confidence (use predictedNtConfidence if available, else 1.0)
    if "predictedNtConfidence" in neurons_df.columns:
        confidence = neurons_df["predictedNtConfidence"].fillna(0.5).values.astype(np.float32)
    else:
        confidence = np.ones(n, dtype=np.float32)

    # Weight formula: log(1 + synapse_count) * sign * confidence * scale
    # Scale factor tuned for larger network (less background needed)
    scale = 0.15  # mV — smaller than 100-neuron (0.6) due to more real connectivity
    inh_attenuation = 0.5
    sign_per_synapse = sign_vector[sources]
    conf_per_synapse = confidence[sources]
    sign_scale = np.where(sign_per_synapse >= 0, 1.0, inh_attenuation)

    syn_weights = (
        np.log1p(weights) * sign_per_synapse * conf_per_synapse * sign_scale * scale
    ).astype(np.float32)

    n_exc = int((sign_vector == 1).sum())
    n_inh = int((sign_vector == -1).sum())
    n_unc = int((sign_vector == 0).sum())
    print(f"  E/I ratio: {n_exc} excitatory / {n_inh} inhibitory / {n_unc} unclear")
    print(f"  Weight stats: mean_exc={syn_weights[syn_weights>0].mean():.3f} mV, "
          f"mean_inh={syn_weights[syn_weights<0].mean():.3f} mV")

    # ---- 4. Build PyGeNN model ----
    print("\n[4/6] Building PyGeNN GPU model...")
    t_build_start = time.time()

    from pygenn import init_weight_update, init_postsynaptic, init_sparse_connectivity

    model = GeNNModel("float", "full_vnc")
    model.dt = 0.1  # 0.1 ms timestep

    # LIF parameters (matching network.py DEFAULT_LIF_PARAMS)
    # PyGeNN LIF: V' = ((Isyn + Ioffset) * Rmembrane + Vrest - V) * ExpTC
    # Rmembrane = TauM / C; ExpTC = exp(-dt/TauM)
    # Units: mV for voltage, ms for time, nA for current
    # With C=0.1nF, TauM=10ms: Rmembrane=100 MOhm
    # A synaptic weight g (nA) through ExpCurr(tau=5ms) at rate r Hz gives:
    #   mean Isyn = g * r * tau_syn_s (nA)
    #   steady-state dV = Isyn * Rmembrane (mV)
    lif_params = {
        "C": 0.1,         # nF (= tau_m / R_m = 10ms / 100MOhm)
        "TauM": 10.0,     # ms
        "Vrest": -70.0,   # mV
        "Vreset": -70.0,  # mV
        "Vthresh": -50.0, # mV
        "Ioffset": 0.0,   # nA
        "TauRefrac": 2.0, # ms
    }
    lif_init = {"V": -70.0, "RefracTime": 0.0}

    # Main neuron population
    pop = model.add_neuron_population("vnc", n, "LIF", lif_params, lif_init)
    pop.spike_recording_enabled = True

    # Convert weights from mV (Brian2 DeltaCurr convention) to nA for GeNN.
    # In Brian2: v_post += w (mV) instantaneously per spike.
    # In GeNN with ExpCurr(tau=5ms): steady-state dV = g * Rmembrane * tau_syn/1000
    #   per Hz of presynaptic rate. For a single spike, peak PSP ≈ g * 50 mV/nA.
    # But for network dynamics, what matters is the mean current contribution.
    # We want the *cumulative effect* of syn_weights (mV) to be preserved.
    # A DeltaCurr spike of w mV decays with tau_m=10ms.
    # An ExpCurr spike of g nA has PSP area = g * Rmembrane * tau_syn (mV*ms).
    # A DeltaCurr spike of w mV has PSP area = w * tau_m (mV*ms).
    # Equating: g * Rmembrane * tau_syn = w * tau_m
    # => g = w * tau_m / (Rmembrane * tau_syn) = w * 10 / (100 * 5) = w * 0.02
    tau_syn = 5.0  # ms - synaptic time constant
    rmembrane = 100.0  # MOhm (= TauM/C = 10/0.1)
    mV_to_nA = lif_params["TauM"] / (rmembrane * tau_syn)  # = 0.02
    syn_weights_nA = (syn_weights * mV_to_nA).astype(np.float32)

    print(f"  Network weight stats (nA): "
          f"mean_exc={syn_weights_nA[syn_weights_nA>0].mean():.5f}, "
          f"mean_inh={syn_weights_nA[syn_weights_nA<0].mean():.5f}")

    # StaticPulse with per-synapse weights + ExpCurr postsynaptic model
    syn_group = model.add_synapse_population(
        "vnc_syn", "SPARSE",
        pop, pop,
        init_weight_update("StaticPulse", {}, {"g": syn_weights_nA}),
        init_postsynaptic("ExpCurr", {"tau": tau_syn}),
    )
    syn_group.set_sparse_connections(
        sources.astype(np.uint32), targets.astype(np.uint32)
    )

    # Poisson input to sensory and descending neurons
    sensory_classes = {"vnc_sensory", "descending_neuron", "sensory_ascending",
                       "sensory_descending"}
    sensory_mask = neurons_df["superclass"].isin(sensory_classes).values
    n_sensory = int(sensory_mask.sum())

    # Poisson drive calibration for sensory/descending neurons:
    # These neurons receive external sensory input and should fire at ~10-20 Hz.
    # Additional to background, provide enough current to push above threshold.
    # Extra dV needed above background: ~4-5 mV -> extra Isyn = 0.04-0.05 nA
    # mean_Isyn = g * rate * tau_syn/1000
    # With rate=500Hz, tau=5ms: g = 0.05/(500*0.005) = 0.020 nA
    poisson_rate = 500.0  # Hz - high rate Poisson for smooth drive
    poisson_g = 0.020     # nA - extra ~5 mV above background for driven neurons

    if n_sensory > 0:
        sensory_idx = np.where(sensory_mask)[0].astype(np.uint32)
        poisson_pop = model.add_neuron_population(
            "poisson_input", n_sensory, "Poisson",
            {"rate": poisson_rate}, {"timeStepToSpike": 0.0}
        )

        poisson_syn = model.add_synapse_population(
            "poisson_syn", "SPARSE",
            poisson_pop, pop,
            init_weight_update("StaticPulseConstantWeight", {"g": poisson_g}),
            init_postsynaptic("ExpCurr", {"tau": tau_syn}),
            init_sparse_connectivity("OneToOne", {}),
        )
        print(f"  Poisson drive: {n_sensory} sources at {poisson_rate} Hz -> "
              f"sensory/descending neurons (g={poisson_g} nA)")

    # Background drive to all neurons
    # The VNC receives tonic input from the brain (descending) and sensory organs.
    # We model this as Poisson background bringing neurons into fluctuation-driven
    # regime: ~6 mV below threshold so recurrent + Poisson fluctuations trigger spikes.
    # Target: dV = 14 mV (bringing neurons from -70 to -56, i.e. 6 mV below -50 threshold)
    # This gives ~10-15 Hz mean rate when combined with recurrent excitation.
    fraction_present = n / total_available
    target_dV = 14.0  # mV - bring near threshold but not too close
    target_Isyn = target_dV / rmembrane  # 0.15 nA
    bg_rate = 1000.0  # Hz - high rate for smooth current (less variance)
    bg_g = target_Isyn / (bg_rate * tau_syn / 1000.0)  # nA per spike
    bg_mean_Isyn = bg_g * bg_rate * tau_syn / 1000.0
    print(f"  Network fraction: {fraction_present:.2%}")
    print(f"  Background target: dV={target_dV:.1f} mV -> Isyn={target_Isyn:.4f} nA")
    print(f"  Background: rate={bg_rate:.0f} Hz, g={bg_g:.5f} nA, "
          f"mean_Isyn={bg_mean_Isyn:.4f} nA (dV≈{bg_mean_Isyn*rmembrane:.1f} mV)")

    bg_pop = model.add_neuron_population(
        "background", n, "Poisson",
        {"rate": bg_rate}, {"timeStepToSpike": 0.0}
    )
    bg_syn = model.add_synapse_population(
        "bg_syn", "SPARSE",
        bg_pop, pop,
        init_weight_update("StaticPulseConstantWeight", {"g": bg_g}),
        init_postsynaptic("ExpCurr", {"tau": tau_syn}),
        init_sparse_connectivity("OneToOne", {}),
    )
    print(f"  Background drive: {n} sources at {bg_rate} Hz (g={bg_g:.4f} nA)")

    # Build and load model on GPU
    print("  Compiling GeNN model (nvcc)...")
    t_compile_start = time.time()
    model.build()
    t_compile_end = time.time()
    print(f"  Compilation took {t_compile_end - t_compile_start:.1f}s")

    # 5-second burn-in = 50000 timesteps at 0.1ms
    duration_ms = 5000.0
    n_timesteps = int(duration_ms / model.dt)
    model.load(num_recording_timesteps=n_timesteps)
    t_build_end = time.time()
    print(f"  Model built and loaded in {t_build_end - t_build_start:.1f}s total")

    # ---- 5. Run 5-second burn-in ----
    print(f"\n[5/6] Running 5-second burn-in ({n_timesteps} timesteps)...")
    t_sim_start = time.time()

    for step in range(n_timesteps):
        model.step_time()
        # Progress reporting every 1 second of simulation
        if (step + 1) % 10000 == 0:
            elapsed = time.time() - t_sim_start
            sim_time = (step + 1) * model.dt / 1000.0
            print(f"    {sim_time:.1f}s simulated ({elapsed:.1f}s wall-clock)")

    t_sim_end = time.time()
    sim_wallclock = t_sim_end - t_sim_start
    realtime_factor = duration_ms / 1000.0 / sim_wallclock
    print(f"  Simulation completed: {sim_wallclock:.1f}s wall-clock "
          f"({realtime_factor:.1f}x realtime)")

    # Pull spike recording data
    model.pull_recording_buffers_from_device()
    recording_data = pop.spike_recording_data[0]
    spike_times_ms = recording_data[0]   # in ms
    spike_ids = recording_data[1]        # neuron indices
    total_spikes = len(spike_times_ms)
    print(f"  Total spikes: {total_spikes:,}")
    print(f"  Mean firing rate: {total_spikes / n / (duration_ms / 1000.0):.1f} Hz")

    # ---- 6. Validation ----
    print("\n[6/6] Validating per-superclass firing rates...")

    # Compute per-superclass rates over full simulation
    superclasses = sorted(neurons_df["superclass"].unique())
    rates = {}
    for sc in superclasses:
        sc_idx = neurons_df[neurons_df["superclass"] == sc].index.values
        spikes_in_group = np.isin(spike_ids, sc_idx).sum()
        rate = spikes_in_group / (len(sc_idx) * (duration_ms / 1000.0))
        rates[sc] = rate

    print("\n  Per-superclass firing rates:")
    all_valid = True
    for sc in superclasses:
        rate = rates[sc]
        n_in_class = int((neurons_df["superclass"] == sc).sum())
        status = "OK" if 1.0 <= rate <= 30.0 else "OUT OF RANGE"
        if status != "OK":
            all_valid = False
        print(f"    {sc:30s}: {rate:6.1f} Hz ({n_in_class:5d} neurons) [{status}]")

    # Compute rate traces (per-superclass rates in 100ms bins)
    bin_width_ms = 100.0
    n_bins = int(duration_ms / bin_width_ms)
    time_bins = np.arange(n_bins) * bin_width_ms / 1000.0 + bin_width_ms / 2000.0
    rate_traces = {}

    for sc in superclasses:
        sc_idx = set(neurons_df[neurons_df["superclass"] == sc].index.values.tolist())
        n_in_class = len(sc_idx)
        trace = np.zeros(n_bins)
        if n_in_class > 0 and total_spikes > 0:
            sc_mask = np.array([int(sid) in sc_idx for sid in spike_ids])
            sc_times = spike_times_ms[sc_mask]
            for b in range(n_bins):
                t_start_b = b * bin_width_ms
                t_end_b = (b + 1) * bin_width_ms
                count = ((sc_times >= t_start_b) & (sc_times < t_end_b)).sum()
                trace[b] = count / (n_in_class * bin_width_ms / 1000.0)
        rate_traces[sc] = trace

    # Check stability: variance in last 1 second
    last_1s_bins = int(1000.0 / bin_width_ms)  # last 10 bins
    print("\n  Stability check (variance in last 1s):")
    for sc in superclasses:
        if rates[sc] > 0.1:
            last_rates = rate_traces[sc][-last_1s_bins:]
            mean_last = last_rates.mean()
            cv = last_rates.std() / max(mean_last, 0.01)
            stable = "STABLE" if cv < 0.3 else "UNSTABLE"
            print(f"    {sc:30s}: CV={cv:.3f} [{stable}]")

    # ---- Generate outputs ----
    print("\n  Generating plots...")

    # Plot 1: Firing rate time-series
    title_rates = f"VNC Burn-in: Per-superclass firing rates ({n} neurons, 5s)"
    plot_burnin_rates(
        time_bins, rate_traces, superclasses,
        title_rates, reports_dir / "full_vnc_burnin_rates.png"
    )

    # Plot 2: Subsampled raster
    superclass_labels = neurons_df["superclass"].values
    title_raster = f"VNC Raster (subsampled) — {total_spikes:,} spikes, {n} neurons"
    plot_raster_subsampled(
        spike_times_ms, spike_ids, n, title_raster,
        reports_dir / "full_vnc_raster.png",
        superclass_labels=superclass_labels,
    )

    # ---- Validation report ----
    report_path = reports_dir / "full_vnc_validation.txt"
    with open(report_path, "w") as f:
        f.write("=" * 70 + "\n")
        f.write("FULL VNC BURN-IN VALIDATION REPORT\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Neurons: {n}\n")
        f.write(f"Synapses: {n_synapses:,}\n")
        f.write(f"Duration: {duration_ms/1000:.1f}s\n")
        f.write(f"Wall-clock: {sim_wallclock:.1f}s ({realtime_factor:.1f}x realtime)\n")
        f.write(f"Total spikes: {total_spikes:,}\n")
        f.write(f"Mean firing rate: {total_spikes / n / (duration_ms/1000.0):.1f} Hz\n")
        f.write(f"E/I ratio: {n_exc}/{n_inh}/{n_unc} (exc/inh/unclear)\n\n")
        f.write("Per-superclass firing rates:\n")
        for sc in superclasses:
            rate = rates[sc]
            n_in_class = int((neurons_df["superclass"] == sc).sum())
            status = "OK" if 1.0 <= rate <= 30.0 else "OUT OF RANGE"
            f.write(f"  {sc:30s}: {rate:6.1f} Hz ({n_in_class:5d} neurons) [{status}]\n")
        f.write(f"\nOverall validation: {'PASS' if all_valid else 'FAIL'}\n")
        f.write(f"  All rates in [1, 30] Hz: {all_valid}\n")
    print(f"Saved: {report_path}")

    # Summary
    print("\n" + "=" * 70)
    print(f"RESULT: {'PASS' if all_valid else 'FAIL'}")
    print(f"  {n} neurons, {n_synapses:,} synapses")
    print(f"  5s burn-in completed in {sim_wallclock:.1f}s ({realtime_factor:.1f}x realtime)")
    print(f"  All rates in [1-30 Hz]: {all_valid}")
    print("=" * 70)
