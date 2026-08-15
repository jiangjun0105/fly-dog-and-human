---
id: 2026-08-15-pygenn-backend
title: "PyGeNN neural backend with STDP eligibility tracking"
created: 2026-08-15T19:40
status: done
priority: high
type: feature
area: gpu
reporter_side: engineering
need_verify: true
related_issues: []
related_tasks: []
parent_epic: epic6-pygenn-gpu-training
---

# PyGeNN neural backend with STDP eligibility tracking

Build a GPU-accelerated neural simulation backend that produces the same outputs
as the Brian2 version: motor neuron spikes and per-synapse eligibility traces.

## Current Behavior

Training uses Brian2 with numpy codegen on CPU. The 100-neuron network takes ~118s
per 2s-episode. The A10G GPU is idle.

## Desired Behavior

A `PyGeNNBackend` class that:
1. Builds a LIF network from the same adjacency matrix and weight array
2. Accepts injected sensory currents each coupling step
3. Returns motor neuron spike counts per coupling step
4. Tracks per-synapse eligibility traces (STDP pre/post × exponential decay)
5. Allows weight and threshold updates between episodes

## Implementation Plan

### 1. LIF neuron model on PyGeNN

Use the same parameters as `network.py::DEFAULT_LIF_PARAMS`:
- tau_m = 10ms, V_rest = -70mV, V_th = -50mV (adaptive), V_reset = -70mV
- t_refract = 2ms, R_membrane = 100 MOhm

PyGeNN LIF with adaptive threshold:
```python
lif_params = {"C": 0.1, "TauM": 10.0, "Vrest": -70.0, "Vreset": -70.0,
              "Vthresh": -50.0, "Ioffset": 0.0, "TauRefrac": 2.0}
```

For per-neuron adaptive threshold, use a custom neuron model that adds a `Vth` variable.

### 2. STDP eligibility synapse model

Custom weight update model with:
- `Apre`, `Apost`: STDP traces (tau = 20ms)
- `eligibility`: accumulated correlation (tau = 1s)
- `g`: synaptic weight (static during episode, updated between)

The eligibility trace accumulates spike-timing correlations on GPU. After an episode,
pull `eligibility[:]` to CPU for reward-modulated weight update.

### 3. Sensory current injection

Each coupling step (2ms), set external current for ascending neurons:
```python
pop.extra_global_params["Iext"].view[:] = sensory_currents
```

### 4. Motor spike readout

After each coupling step, pull spike recording and count motor neuron spikes for
the rate decoder.

### 5. Validation

Run 1 episode with identical initial conditions on both Brian2 and PyGeNN backends.
Compare:
- Total spike count (should be within 10% — stochastic, not exact)
- Per-neuron mean firing rate (within 20%)
- Eligibility trace magnitudes (same order of magnitude)
- Forward distance reward (same sign, similar magnitude)

## Demo

```python
from digital_drosophila.gpu_backend import PyGeNNBackend

backend = PyGeNNBackend(adj, weights, thresholds, motor_indices, ascending_indices)
backend.reset()
for step in range(n_steps):
    backend.inject_current(sensory_currents)
    backend.step(dt_ms=2.0)
    motor_spikes = backend.get_motor_spikes()
eligibility = backend.get_eligibility()
backend.set_weights(new_weights)
```

## Notes

- The existing `run_full_vnc()` in simulate.py has working PyGeNN infrastructure
  for LIF + sparse connectivity + Poisson input. Reuse that pattern.
- Weight conversion: Brian2 uses DeltaCurr (v += w mV), PyGeNN uses conductance-based.
  Need the same mV_to_nA conversion from simulate.py (factor = 0.02).
- CUDA compilation takes ~30s on first build. Subsequent runs reuse cached kernels.
- For 100 neurons, GPU overhead may dominate. The real win is at 15K neurons.
  But even at 100, eliminating the Brian2 Python overhead (which is the real
  bottleneck, not computation) should give a significant speedup.
