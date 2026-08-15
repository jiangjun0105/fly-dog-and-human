---
id: 2026-08-15-brian2-biological-constraints
title: "Add biological constraints to Brian2 network (signs, weights, superclasses)"
created: 2026-08-15T11:30
status: done
priority: high
type: task
suitability: auto_agent_ready
depends_on:
  - 2026-08-15-brian2-minimal-network
related: []
satisfies: []
branch: ""
pr: ""
auto_agent_task_id: ""
---

# Add biological constraints to Brian2 network (signs, weights, superclasses)

## Context

Issue 1.1 (skateboard) proved Brian2 works with our connectome data — 100 LIF neurons
fire with raw synapse counts as weights. Now we thicken it with biological fidelity:
neurotransmitter-based sign constraints, the proper weight initialization formula from
the design docs, and neuron partitioning by superclass.

Parent issue: `docs/issues/2026-08-15-brian2-biological-constraints.md`

## Problem

The current `scripts/run_brian2_minimal.py` treats all weights as positive and all
neurons identically. This doesn't respect biology: GABA neurons should inhibit (negative
weights), acetylcholine neurons should excite (positive weights), and "unclear" neurons
(12 motor neurons) should be near-zero. Neurons aren't differentiated by functional role.

## Desired Behavior

1. A new script `scripts/run_brian2_constrained.py` uses sign-constrained weights computed
   as: `w_ij = log(1 + synapse_count) × sign × confidence × scale`
2. Sign comes from `NT_SIGN_MAP` in `src/digital_drosophila/constants.py` applied to
   each presynaptic neuron's `consensusNt` column
3. "Unclear" NT neurons (sign=None, all 12 are motor neurons) get weights initialized
   near zero (sign=0 effectively)
4. Neurons are partitioned by superclass in the output (separate stats per group)
5. Raster plot is color-coded by superclass showing differentiated activity patterns
6. Mean firing rates per superclass are all in 1-30 Hz range (no silence, no seizure)
7. Script prints E/I ratio summary (65 excitatory / 23 inhibitory / 12 unclear in this sample)

## Demo

Run `python scripts/run_brian2_constrained.py` → output shows:
(1) neuron counts per superclass and E/I ratio,
(2) color-coded raster plot saved to `reports/brian2_constrained_raster.png`,
(3) mean firing rates per superclass (all 1-30 Hz).

## Key Files

| File | Purpose |
|------|---------|
| [`scripts/run_brian2_minimal.py`](../../scripts/run_brian2_minimal.py) | Starting point — copy and modify |
| [`src/digital_drosophila/constants.py`](../../src/digital_drosophila/constants.py) | `NT_SIGN_MAP`: acetylcholine→+1, gaba→-1, glutamate→-1, unclear→None |
| [`src/wiki/data/metrics/sample_100/adj.npy`](../../src/wiki/data/metrics/sample_100/adj.npy) | 100×100 adjacency matrix (synapse counts) |
| [`src/wiki/data/metrics/sample_100/sample_neurons.csv`](../../src/wiki/data/metrics/sample_100/sample_neurons.csv) | Neuron metadata with `consensusNt`, `predictedNtConfidence`, `superclass` |
| [`docs/neuroscience/02-lif-model-design.md`](../neuroscience/02-lif-model-design.md) | Weight formula, sign constraints, parameter table |

## Suggested Approach

Copy `run_brian2_minimal.py` → `run_brian2_constrained.py` and modify:

### 1. Weight initialization with signs

```python
from src.digital_drosophila.constants import NT_SIGN_MAP

# For each presynaptic neuron i, get its sign from consensusNt
nt_series = neurons_df['consensusNt']
confidence = neurons_df['predictedNtConfidence'].values

# Build sign vector: +1 (excitatory), -1 (inhibitory), 0 (unclear/modulatory)
sign_vector = np.array([NT_SIGN_MAP.get(nt, 0) or 0 for nt in nt_series])
# None → 0 for unclear/modulatory

# Weight formula: w_ij = log(1 + count) * sign_i * confidence_i * scale
# sign comes from the PRESYNAPTIC neuron (neuron i sends with its NT type)
sources, targets = adj.nonzero()
weights = np.log1p(adj[sources, targets]) * sign_vector[sources] * confidence[sources] * scale
```

### 2. Scale factor

Log-compressed weights are much smaller than raw counts (log(1+416) ≈ 6.0 vs 416).
Start with `scale = 2.0 * mV` (so max weight ≈ 6.0 × 1 × 0.97 × 2.0 = 11.6 mV).
Tune if rates are off.

### 3. Color-coded raster plot

```python
# Assign colors by superclass
superclass_colors = {
    'descending_neuron': '#e74c3c',
    'vnc_intrinsic': '#3498db',
    'vnc_motor': '#2ecc71',
    'ascending_neuron': '#9b59b6',
}
colors = [superclass_colors[neurons_df.iloc[i]['superclass']] for i in M.i]
plt.scatter(M.t/ms, M.i, c=colors, s=1)
```

### 4. Per-superclass firing rate stats

```python
for sc in neurons_df['superclass'].unique():
    idx = neurons_df[neurons_df['superclass'] == sc].index
    spikes_in_group = np.isin(np.array(M.i), idx).sum()
    rate = spikes_in_group / len(idx)
    print(f"  {sc}: {rate:.1f} Hz ({len(idx)} neurons)")
```

### Recommendation

Implement as above. The key decision (sign from presynaptic neuron) is per the design doc:
"the neurotransmitter identity provides the sign" — a neuron's outgoing connections all
have the same sign (Dale's principle).

## Implementation Approach

- **Artifact type:** New Python script (`scripts/run_brian2_constrained.py`)
- **Extend existing:** Copy from `run_brian2_minimal.py`, modify weight calculation and plotting
- **Do not:** Modify the original `run_brian2_minimal.py` (keep it as a reference/baseline), create separate NeuronGroups per superclass (one NeuronGroup with index-based analysis is sufficient for now), implement neuromodulation (stub only if trivial, otherwise skip)

## Acceptance Criteria

- [ ] `scripts/run_brian2_constrained.py` runs without error
- [ ] Weights use the formula: `log(1 + synapse_count) × sign × confidence × scale`
- [ ] Sign correctly applied from presynaptic neuron's `consensusNt` via `NT_SIGN_MAP`
- [ ] "Unclear" NT neurons contribute near-zero weights (sign=0)
- [ ] Output prints E/I ratio (65 excitatory / 23 inhibitory / 12 unclear)
- [ ] Output prints per-superclass firing rates, all between 1-30 Hz
- [ ] Raster plot saved to `reports/brian2_constrained_raster.png`, color-coded by superclass
- [ ] Plot shows visible differentiation between driven (descending) vs. emergent (intrinsic/motor) populations
- [ ] Runtime < 60 seconds

## Automated verification

### Test infrastructure

Real: Brian2 2.10.1 (CPU), numpy, pandas, matplotlib
Mocked: None
Shared fixture: src/wiki/data/metrics/sample_100/adj.npy, sample_neurons.csv

### Proving test chain

`python scripts/run_brian2_constrained.py` → loads data → computes signed weights →
builds network → runs 1s → saves color-coded raster + prints per-superclass rates.

### Test scenarios

```
Scenario 1 (★ proving): Biologically-constrained network fires with correct E/I balance
Infrastructure:
  Real: Brian2 (CPU), numpy, pandas, matplotlib
  Mocked: None
  Fixture: adj.npy, sample_neurons.csv, constants.py NT_SIGN_MAP
Given: The 100-neuron sample with 65 ACh (+1), 23 GABA (-1), 12 unclear (0)
When: python scripts/run_brian2_constrained.py is executed
Then:
  - Exit code == 0
  - stdout contains "excitatory: 65" and "inhibitory: 23" and "unclear: 12"
  - stdout shows per-superclass rates all between 1.0 and 30.0 Hz
  - reports/brian2_constrained_raster.png exists (file size > 10KB)
  - Runtime < 60 seconds
```

## Notes

- Data distribution: 65 acetylcholine (+1), 23 GABA (-1), 12 unclear (0). All "unclear" are motor neurons.
- No sensory neurons in this 100-neuron sample (4 superclasses: descending 49, intrinsic 18, motor 18, ascending 15)
- Poisson input remains on descending neurons (same as Issue 1.1)
- The `predictedNtConfidence` ranges 0.26-0.97 (mean 0.85) — this naturally down-weights uncertain classifications
- If inhibition is too strong and kills activity, reduce scale or increase Poisson drive
- Hard sign constraint (weights cannot cross zero) is structural in this implementation since we multiply by a fixed sign vector — no learning can flip it
