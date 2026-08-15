---
id: 2026-08-15-brian2-minimal-network
title: "Build minimal Brian2 spiking network from 100-neuron connectome sample"
created: 2026-08-15T11:00
status: done
priority: high
type: task
suitability: auto_agent_ready
depends_on: []
related: []
satisfies: []
branch: ""
pr: ""
auto_agent_task_id: ""
---

# Build minimal Brian2 spiking network from 100-neuron connectome sample

## Context

This is the "skateboard" of Epic 1 (Brian2 Neural Network) — the thinnest vertical proving
we can go from pre-computed connectome data to a running spiking neural network simulation.
No biological fidelity yet (no sign constraints, no superclass partitioning) — just "data
in, spikes out."

Parent issue: `docs/issues/2026-08-15-brian2-minimal-network.md`

## Problem

We have pre-computed connectome data (`adj.npy`, `sample_neurons.csv`) but zero simulation
code. The data sits in `src/wiki/data/metrics/sample_100/` and is currently only used for
Streamlit visualization. The core research tool — a running spiking neural network from
real connectome topology — doesn't exist yet.

## Desired Behavior

1. A single script (`scripts/run_brian2_minimal.py`) loads the 100-neuron adjacency matrix
   and produces a Brian2 simulation with visible spiking activity
2. The script completes without error in under 60 seconds
3. Output includes a raster plot (spike times × neuron index) saved as PNG showing that
   neurons fire (not all silent, not all maxed out — mean firing rates roughly 1-50 Hz)

## Demo

Run `python scripts/run_brian2_minimal.py` → it loads `adj.npy` and `sample_neurons.csv`,
builds 100 LIF neurons connected by the adjacency matrix, simulates for 1 second, and
saves a raster plot PNG to `reports/`. Neurons fire (not all silent, not all saturated).

## Key Files

| File | Purpose |
|------|---------|
| [`src/wiki/data/metrics/sample_100/adj.npy`](../../src/wiki/data/metrics/sample_100/adj.npy) | 100×100 float32 adjacency matrix (synapse counts, 12.8% density, values 0-416) |
| [`src/wiki/data/metrics/sample_100/sample_neurons.csv`](../../src/wiki/data/metrics/sample_100/sample_neurons.csv) | Neuron metadata: bodyId, superclass, consensusNt, predictedNtConfidence (100 rows) |
| [`src/digital_drosophila/constants.py`](../../src/digital_drosophila/constants.py) | NT_SIGN_MAP (not used in this task but reference for future) |
| [`docs/neuroscience/02-lif-model-design.md`](../neuroscience/02-lif-model-design.md) | LIF equations reference: tau_m * dV/dt = -(V - V_rest) + R * I(t) |

## Suggested Approach

### 1. Add matplotlib dependency

Add `matplotlib>=3.9` to `pyproject.toml` dependencies and run `uv sync`.

### 2. Create the simulation script

`scripts/run_brian2_minimal.py`:

```python
import numpy as np
import pandas as pd
from brian2 import *

# Load data
adj = np.load("src/wiki/data/metrics/sample_100/adj.npy")
neurons_df = pd.read_csv("src/wiki/data/metrics/sample_100/sample_neurons.csv")

# LIF parameters (from doc 02)
tau_m = 10*ms
V_rest = -70*mV
V_th = -50*mV
V_reset = -70*mV
R = 100*Mohm
t_refract = 2*ms

# Create neuron group
eqs = '''
dv/dt = (-(v - V_rest) + R * I) / tau_m : volt (unless refractory)
I : amp
'''
G = NeuronGroup(100, eqs, threshold='v > V_th', reset='v = V_reset',
                refractory=t_refract, method='euler')
G.v = V_rest

# Create synapses from adjacency matrix
S = Synapses(G, G, 'w : volt', on_pre='v_post += w')
sources, targets = adj.nonzero()
S.connect(i=sources, j=targets)
# Scale synapse counts to voltage jumps (tunable)
scale = 0.1*mV
S.w = adj[sources, targets] * scale

# Poisson input to descending neurons (indices where superclass == 'descending_neuron')
descending_idx = neurons_df[neurons_df['superclass'] == 'descending_neuron'].index.tolist()
P = PoissonInput(G[descending_idx], 'v', N=50, rate=15*Hz, weight=1.5*mV)

# Monitor and run
M = SpikeMonitor(G)
run(1*second)

# Plot and save
import matplotlib.pyplot as plt
plt.figure(figsize=(12, 6))
plt.plot(M.t/ms, M.i, '.k', markersize=1)
plt.xlabel('Time (ms)')
plt.ylabel('Neuron index')
plt.title(f'Raster plot — {M.num_spikes} spikes from 100 LIF neurons')
plt.tight_layout()
os.makedirs('reports', exist_ok=True)
plt.savefig('reports/brian2_minimal_raster.png', dpi=150)
print(f"Done: {M.num_spikes} spikes in 1s from 100 neurons")
print(f"Mean rate: {M.num_spikes/100:.1f} Hz")
print(f"Saved: reports/brian2_minimal_raster.png")
```

### Key parameters to tune if needed

- `scale` (weight scale factor): start at 0.1*mV, increase if network is silent, decrease if seizure
- PoissonInput `rate` and `weight`: 15 Hz / 1.5 mV is a reasonable starting point
- PoissonInput `N` (number of virtual Poisson sources per neuron): 50

### Recommendation

Implement the script as above. If firing rates are outside 1-50 Hz, tune `scale` first
(it controls how strongly connected neurons drive each other).

## Implementation Approach

- **Artifact type:** Python script (`scripts/run_brian2_minimal.py`) + dependency update (`pyproject.toml`)
- **Extend existing:** No existing patterns — this is greenfield Brian2 code
- **Do not:** Use GeNN/GPU (CPU is fine for 100 neurons), add sign constraints (that's the next issue), over-engineer abstractions (this is a proof-of-concept)

## Acceptance Criteria

- [x] `matplotlib>=3.9` added to pyproject.toml and `uv sync` succeeds
- [x] `scripts/run_brian2_minimal.py` exists and runs without error
- [x] Script produces `reports/brian2_minimal_raster.png` showing a raster plot with visible spikes
- [x] Mean firing rate printed to stdout is between 1-50 Hz (no silence, no seizure)
- [x] Total runtime < 60 seconds

## Automated verification

### Test infrastructure

Real: Brian2 simulation (CPU mode)
Mocked: None
Shared fixture: Pre-computed data files in src/wiki/data/metrics/sample_100/

### Proving test chain

`python scripts/run_brian2_minimal.py` → loads adj.npy + sample_neurons.csv → constructs
Brian2 NeuronGroup + Synapses + PoissonInput → runs 1s simulation → saves raster PNG +
prints spike count and mean rate.

### Test scenarios

```
Scenario 1 (★ proving): Script produces spiking activity from connectome data
Infrastructure:
  Real: Brian2 2.10.1 (CPU), numpy, pandas, matplotlib
  Mocked: None
  Fixture: src/wiki/data/metrics/sample_100/adj.npy, sample_neurons.csv
Given: The pre-computed 100-neuron adjacency matrix and metadata exist
When: python scripts/run_brian2_minimal.py is executed
Then:
  - Exit code == 0
  - reports/brian2_minimal_raster.png exists and is a valid PNG (file size > 10KB)
  - stdout contains "Mean rate:" with a value between 1.0 and 50.0
  - stdout contains "spikes" with a count > 0
  - Wall-clock runtime < 60 seconds
```

### Running the tests locally

```bash
# Run the simulation script directly
python scripts/run_brian2_minimal.py

# Verify output
ls -la reports/brian2_minimal_raster.png
```

## Notes

- The 100-neuron sample has NO sensory neurons (49 descending, 18 intrinsic, 18 motor,
  15 ascending). Poisson input targets descending neurons instead (they anatomically
  receive input from the brain).
- Weight scale factor (0.1 mV per synapse) is a guess — may need tuning. The adjacency
  matrix has values up to 416 (synapse counts), so max weight would be 41.6 mV — enough
  to push a neuron from rest (-70) past threshold (-50) in one spike. That's probably too
  strong; may need to reduce to 0.01 mV.
- Brian2's `PoissonInput` is more efficient than creating a separate `PoissonGroup` +
  `Synapses` for external input — it's built for this use case.
