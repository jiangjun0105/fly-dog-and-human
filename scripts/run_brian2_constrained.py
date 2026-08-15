"""Biologically-constrained Brian2 spiking network from 100-neuron connectome sample.

Extends the minimal LIF network with:
  - Sign-constrained weights from neurotransmitter type (Dale's principle)
  - Weight formula: w_ij = log(1 + synapse_count) * sign_i * confidence_i * scale
  - Color-coded raster plot by superclass
  - Per-superclass firing rate statistics
"""

import os
import sys
import time

import numpy as np
import pandas as pd
from brian2 import (
    Hz,
    Mohm,
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

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.digital_drosophila.constants import NT_SIGN_MAP

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
# E/I ratio from neurotransmitter types
# --------------------------------------------------------------------------
nt_series = neurons_df["consensusNt"]
confidence = neurons_df["predictedNtConfidence"].values

# Build sign vector: +1 (excitatory), -1 (inhibitory), 0 (unclear/modulatory)
# NT_SIGN_MAP maps: acetylcholine -> +1, gaba -> -1, glutamate -> -1, unclear -> None
sign_vector = np.array([NT_SIGN_MAP.get(nt, 0) or 0 for nt in nt_series])

n_excitatory = int((sign_vector == 1).sum())
n_inhibitory = int((sign_vector == -1).sum())
n_unclear = int((sign_vector == 0).sum())

print(f"\nE/I ratio:")
print(f"  excitatory: {n_excitatory} (acetylcholine, sign=+1)")
print(f"  inhibitory: {n_inhibitory} (gaba, sign=-1)")
print(f"  unclear: {n_unclear} (unclear NT, sign=0)")
print(f"  ratio (E/I): {n_excitatory}/{n_inhibitory} = {n_excitatory/n_inhibitory:.2f}")

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
# Create synapses with biologically-constrained weights
# --------------------------------------------------------------------------
S = Synapses(G, G, "w : volt", on_pre="v_post += w")
sources, targets = adj.nonzero()
S.connect(i=sources, j=targets)

# Weight formula: w_ij = log(1 + synapse_count) * sign_i * confidence_i * scale
# Sign comes from the PRESYNAPTIC neuron (Dale's principle)
scale = 0.6  # in mV units; will multiply by mV below
# Inhibitory attenuation factor: GABA-A reversal potential (-75mV) is close to
# V_rest (-70mV), so inhibitory PSPs are smaller than excitatory ones in conductance-
# based models. We approximate this by scaling inhibitory weights by 0.5.
inh_attenuation = 0.5
sign_scale = np.where(sign_vector[sources] >= 0, 1.0, inh_attenuation)
weights_raw = (
    np.log1p(adj[sources, targets])
    * sign_vector[sources]
    * confidence[sources]
    * sign_scale
    * scale
)
S.w = weights_raw * mV

# Print weight statistics
w_exc = weights_raw[weights_raw > 0]
w_inh = weights_raw[weights_raw < 0]
w_zero = weights_raw[weights_raw == 0]
print(f"\nWeight statistics (mV):")
print(f"  Excitatory: n={len(w_exc)}, mean={w_exc.mean():.2f}, max={w_exc.max():.2f}")
print(f"  Inhibitory: n={len(w_inh)}, mean={w_inh.mean():.2f}, min={w_inh.min():.2f}")
print(f"  Zero (unclear): n={len(w_zero)}")
print(f"  Total synapses: {len(sources)}")

# --------------------------------------------------------------------------
# External input: Poisson drive to descending neurons
# --------------------------------------------------------------------------
descending_idx = neurons_df[neurons_df["superclass"] == "descending_neuron"].index.tolist()
print(f"\nDriving {len(descending_idx)} descending neurons with Poisson input")

# External input: Descending neurons get targeted Poisson drive (they receive
# sensory/brain input in vivo). Other populations get background drive only.
N_poisson = 15  # Number of virtual Poisson sources per descending neuron
PG = PoissonGroup(N_poisson, rates=10 * Hz)
S_input = Synapses(PG, G, on_pre="v_post += 2.0*mV")
# Connect all Poisson sources to all descending neurons (all-to-all)
poisson_i = np.repeat(np.arange(N_poisson), len(descending_idx))
poisson_j = np.tile(descending_idx, N_poisson)
S_input.connect(i=poisson_i, j=poisson_j)

# Background input to all neurons (representing missing network context:
# the full VNC has ~14,000 neurons; this 100-neuron sample lacks many inputs).
# Without this, ascending and intrinsic neurons receive net inhibition from
# the recurrent network and remain silent.
N_bg = 50  # Number of background Poisson sources
PG_bg = PoissonGroup(N_bg, rates=20 * Hz)
S_bg = Synapses(PG_bg, G, on_pre="v_post += 1.2*mV")
# Connect to all neurons
bg_i = np.repeat(np.arange(N_bg), 100)
bg_j = np.tile(np.arange(100), N_bg)
S_bg.connect(i=bg_i, j=bg_j)
print(f"Background drive: {N_bg} sources at 20 Hz to all 100 neurons")

# --------------------------------------------------------------------------
# Monitor and run
# --------------------------------------------------------------------------
M = SpikeMonitor(G)

print("\nRunning simulation (1 second)...")
t_start = time.time()
run(1 * second)
t_elapsed = time.time() - t_start

print(f"Simulation completed in {t_elapsed:.1f}s")
print(f"Total spikes: {M.num_spikes}")
print(f"Mean rate (all neurons): {M.num_spikes / 100:.1f} Hz")

# --------------------------------------------------------------------------
# Per-superclass firing rate statistics
# --------------------------------------------------------------------------
print("\nPer-superclass firing rates:")
sim_duration = 1.0  # seconds
spike_indices = np.array(M.i)

superclass_rates = {}
for sc in sorted(neurons_df["superclass"].unique()):
    idx = neurons_df[neurons_df["superclass"] == sc].index.values
    spikes_in_group = np.isin(spike_indices, idx).sum()
    rate = spikes_in_group / (len(idx) * sim_duration)
    superclass_rates[sc] = rate
    print(f"  {sc}: {rate:.1f} Hz ({len(idx)} neurons, {spikes_in_group} spikes)")

# Check if rates are in biological range
all_in_range = all(1.0 <= r <= 30.0 for r in superclass_rates.values())
if all_in_range:
    print("\n  All superclass rates within biological range (1-30 Hz)")
else:
    print("\n  WARNING: Some rates outside 1-30 Hz range — consider tuning scale factor")

# --------------------------------------------------------------------------
# Color-coded raster plot by superclass
# --------------------------------------------------------------------------
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

superclass_colors = {
    "descending_neuron": "#e74c3c",
    "vnc_intrinsic": "#3498db",
    "vnc_motor": "#2ecc71",
    "ascending_neuron": "#9b59b6",
}

# Assign color to each spike based on the neuron's superclass
colors = [superclass_colors[neurons_df.iloc[int(i)]["superclass"]] for i in M.i]

fig, ax = plt.subplots(figsize=(12, 6))
ax.scatter(np.array(M.t / ms), np.array(M.i), c=colors, s=1, alpha=0.7)
ax.set_xlabel("Time (ms)")
ax.set_ylabel("Neuron index")
ax.set_title(
    f"Biologically-constrained raster — {M.num_spikes} spikes, "
    f"100 LIF neurons (E:{n_excitatory}/I:{n_inhibitory}/U:{n_unclear})"
)

# Add legend
from matplotlib.patches import Patch

legend_elements = [
    Patch(facecolor=color, label=f"{sc} ({len(neurons_df[neurons_df['superclass']==sc])})")
    for sc, color in superclass_colors.items()
]
ax.legend(handles=legend_elements, loc="upper right", fontsize=8)

plt.tight_layout()

os.makedirs("reports", exist_ok=True)
output_path = "reports/brian2_constrained_raster.png"
plt.savefig(output_path, dpi=150)
print(f"\nSaved: {output_path}")
