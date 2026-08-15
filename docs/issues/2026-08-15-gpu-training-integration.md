---
id: 2026-08-15-gpu-training-integration
title: "Integrate PyGeNN backend into training harness"
created: 2026-08-15T19:40
status: done
priority: high
type: feature
area: gpu
reporter_side: engineering
need_verify: true
related_issues: ["2026-08-15-pygenn-backend"]
related_tasks: []
parent_epic: epic6-pygenn-gpu-training
---

# Integrate PyGeNN backend into training harness

Wire the PyGeNN GPU backend into the existing `TrainingHarness` so that training
can run on either CPU (Brian2) or GPU (PyGeNN) with a simple flag.

## Current Behavior

`TrainingHarness` directly constructs Brian2 objects in `_build()`. The neural
simulation is tightly coupled to Brian2.

## Desired Behavior

- `TrainingHarness` accepts a `backend="cpu"` or `backend="gpu"` parameter
- `backend="cpu"` uses the existing Brian2 code path (unchanged)
- `backend="gpu"` uses `PyGeNNBackend` for neural simulation
- Both produce the same checkpoint format and training log

## Implementation Plan

### 1. Extract neural interface

The `_build()`, `_reset_episode()`, and `_run_episode()` methods mix neural setup
with body setup. Refactor so that:
- Body setup (FlyGym, sensory encoder, motor decoder) stays in `TrainingHarness`
- Neural simulation is delegated to a backend object

### 2. Backend protocol

```python
class NeuralBackend(Protocol):
    def build(self, adj, weights, thresholds, motor_indices, ascending_indices): ...
    def reset(self, weights, thresholds): ...
    def step(self, sensory_currents, dt_ms) -> set[int]: ...  # returns motor spike indices
    def get_eligibility(self) -> np.ndarray: ...
    def get_spike_counts(self) -> np.ndarray: ...  # per-neuron counts this episode
    def close(self): ...
```

### 3. CLI integration

```
python -m digital_drosophila learn train_gpu [--episodes 50] [--episode-length 2.0]
```

Or add `--backend gpu|cpu` to the existing `train` command.

### 4. Validation

Run 10 episodes with both backends from the same initial weights. Compare:
- Learning curves (reward per episode) — should have same trend
- Final weight distributions — same magnitude and sign pattern
- Wall time per episode — GPU should be >10x faster

## Notes

- The body simulation (FlyGym/MuJoCo) is unchanged — it stays on CPU
- The coupling loop (inject sensory → step neural → decode motor → step body)
  has the same structure regardless of backend
- Between-episode updates (homeostatic plasticity, synaptic decay, STDP weight
  change) stay in numpy — they operate on the weight array, not on the simulator
- First PyGeNN build compiles CUDA kernels (~30s). Cache on disk for subsequent runs.
