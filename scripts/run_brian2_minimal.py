"""Minimal Brian2 spiking neural network from 100-neuron connectome sample.

Loads the pre-computed adjacency matrix and neuron metadata, builds a
100-neuron LIF network with connectivity from the connectome, drives
descending neurons with Poisson input, and saves a raster plot.
"""

import os
import time

import numpy as np
import pandas as pd
from brian2 import (
    Mohm,
    Hz,
    NeuronGroup,
    PoissonGroup,
    Synapses,
    SpikeMonitor,
    mV,
    ms,
    second,
    run,
    prefs,
)

# Use runtime mode (CPU, no code generation overhead for small network)
prefs.codegen.target = "numpy"

# --------------------------------------------------------------------------
# Load data
# --------------------------------------------------------------------------
DATA_DIR = os.path.join("src", "wiki", "data", "metrics", "sample_100")
adj = np.load(os.path.join(DATA_DIR, "adj.npy"))
neurons_df = pd.read_csv(os.path.join(DATA_DIR, "sample_neurons.csv"))

print(f"Loaded {adj.shape[0]}-neuron adjacency matrix ({np.count_nonzero(adj)} synapses)")
print(f"Neuron superclass distribution: {dict(neurons_df['superclass'].value_counts())}")

# --------------------------------------------------------------------------
# LIF parameters (from docs/neuroscience/02-lif-model-design.md)
# --------------------------------------------------------------------------
tau_m = 10 * ms
V_rest = -70 * mV
V_th = -50 * mV
V_reset = -70 * mV
R_membrane = 100 * Mohm
t_refract = 2 * ms

# --------------------------------------------------------------------------
# Create neuron group
# --------------------------------------------------------------------------
eqs = """
dv/dt = (-(v - V_rest) + R_membrane * I) / tau_m : volt (unless refractory)
I : amp
"""
G = NeuronGroup(
    100,
    eqs,
    threshold="v > V_th",
    reset="v = V_reset",
    refractory=t_refract,
    method="euler",
)
G.v = V_rest

# --------------------------------------------------------------------------
# Create synapses from adjacency matrix
# --------------------------------------------------------------------------
S = Synapses(G, G, "w : volt", on_pre="v_post += w")
sources, targets = adj.nonzero()
S.connect(i=sources, j=targets)

# Scale synapse counts to voltage jumps.
# adj values range 0-416. With scale=0.1mV, max single-spike contribution
# would be 41.6mV which is too strong. Start with 0.02mV so max is ~8.3mV.
scale = 0.02 * mV
S.w = adj[sources, targets] * scale

print(f"Connected {len(sources)} synapses (scale={scale})")

# --------------------------------------------------------------------------
# External input: Poisson drive to descending neurons
# --------------------------------------------------------------------------
descending_idx = neurons_df[neurons_df["superclass"] == "descending_neuron"].index.tolist()
print(f"Driving {len(descending_idx)} descending neurons with Poisson input")

# PoissonInput requires contiguous subgroups; descending neurons are scattered.
# Use a PoissonGroup + Synapses to target specific neuron indices.
N_poisson = 50  # Number of virtual Poisson sources per descending neuron
PG = PoissonGroup(N_poisson, rates=30 * Hz)
S_input = Synapses(PG, G, on_pre="v_post += 2.0*mV")
# Connect all Poisson sources to all descending neurons (all-to-all)
poisson_i = np.repeat(np.arange(N_poisson), len(descending_idx))
poisson_j = np.tile(descending_idx, N_poisson)
S_input.connect(i=poisson_i, j=poisson_j)

# --------------------------------------------------------------------------
# Monitor and run
# --------------------------------------------------------------------------
M = SpikeMonitor(G)

print("Running simulation (1 second)...")
t_start = time.time()
run(1 * second)
t_elapsed = time.time() - t_start

print(f"Simulation completed in {t_elapsed:.1f}s")
print(f"Total spikes: {M.num_spikes}")
print(f"Mean rate: {M.num_spikes / 100:.1f} Hz")

# --------------------------------------------------------------------------
# Plot and save raster
# --------------------------------------------------------------------------
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.figure(figsize=(12, 6))
plt.plot(M.t / ms, M.i, ".k", markersize=1)
plt.xlabel("Time (ms)")
plt.ylabel("Neuron index")
plt.title(f"Raster plot — {M.num_spikes} spikes from 100 LIF neurons (1s)")
plt.tight_layout()

os.makedirs("reports", exist_ok=True)
output_path = "reports/brian2_minimal_raster.png"
plt.savefig(output_path, dpi=150)
print(f"Saved: {output_path}")
