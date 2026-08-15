# EPIC — PyGeNN GPU-Accelerated Training Loop

**EPIC — container, do not execute; work lives in child issues.**

**Parent:** epic-phase1-implementation
**Depends on:** epic4-learning-locomotion (reuses same learning rules)

## Motivation

The current training loop (Epic 4) uses Brian2 with numpy codegen on CPU. At ~118s per
2s-episode on the 100-neuron network, a 50-episode training run takes ~98 minutes. The
NVIDIA A10G GPU (23GB VRAM) sits idle at 0% utilization.

Brian2 was chosen for its flexibility with plasticity rules — arbitrary differential
equations, dynamic on_pre/on_post handlers, and future structural plasticity (synapse
creation/deletion). However, the current Phase 1 training uses **fixed topology with
weight-only updates** (STDP + homeostatic threshold adjustment between episodes). This
pattern is compatible with PyGeNN, which supports weight modification between timesteps.

**Key constraint:** This epic builds a *parallel fast-path* for the fixed-topology training
case. Brian2 remains the primary framework for future structural plasticity (Phase 2).

## Epic Demo

Run `python -m digital_drosophila learn train_gpu --episodes 50 --episode-length 2.0` →
- Trains on GPU using PyGeNN (same network, same learning rules)
- 10-50x faster than CPU (estimated ~5-10s per episode vs ~118s)
- Produces identical checkpoint format (weights.npz) compatible with evaluation tools
- Enables rapid iteration on hyperparameters and multi-seed experiments

## Architecture

```
                     ┌──────────────────────────────────┐
                     │  TrainingHarness (existing)       │
                     │  - Episode management             │
                     │  - Reward computation             │
                     │  - Homeostatic update (numpy)     │
                     │  - Synaptic decay (numpy)         │
                     │  - Checkpoint saving              │
                     └────────────┬─────────────────────┘
                                  │ calls
                     ┌────────────▼─────────────────────┐
                     │  NeuralBackend (protocol)         │
                     │  - build(adj, weights, thresholds)│
                     │  - run_episode(sensory_fn) → spikes│
                     │  - get_eligibility() → array      │
                     │  - set_weights(w)                 │
                     └────────────┬─────────────────────┘
                                  │
              ┌───────────────────┼───────────────────────┐
              │                                           │
   ┌──────────▼──────────┐                 ┌─────────────▼──────────┐
   │  Brian2Backend       │                 │  PyGeNNBackend          │
   │  (CPU, 100 neurons)  │                 │  (GPU, 100-15K neurons) │
   │  - numpy codegen     │                 │  - CUDA compilation     │
   │  - full flexibility  │                 │  - StaticPulse synapses │
   │  - ~118s/episode     │                 │  - ~5-10s/episode       │
   └──────────────────────┘                 └─────────────────────────┘
```

The between-episode plasticity updates (STDP weight change, homeostatic threshold,
synaptic decay) stay in numpy on CPU — they're O(n_synapses) and take milliseconds.
Only the expensive inner loop (neural simulation + body coupling) moves to GPU.

## Children (value-sliced)

1. **[Issue 6.1 — PyGeNN neural backend](2026-08-15-pygenn-backend.md)**: Build a
   `PyGeNNBackend` class that wraps the GPU-accelerated LIF network with STDP eligibility
   tracking. Must produce the same spike patterns and eligibility traces as the Brian2
   version (validated by comparing 1-episode outputs).

2. **[Issue 6.2 — GPU training loop integration](2026-08-15-gpu-training-integration.md)**:
   Wire `PyGeNNBackend` into the existing `TrainingHarness` via a backend protocol. Add
   `--backend gpu` flag to CLI. Verify that training produces comparable learning curves.

3. **[Issue 6.3 — Scale to full VNC](2026-08-15-gpu-full-vnc-training.md)** (stretch):
   Use the 15K-neuron VNC network (already working in `run_full_vnc()`) for training.
   This requires mapping the motor neuron indices and ascending neuron indices into the
   larger network. Potentially much richer learning dynamics.

## Dependency Spine

```
Issue 6.1 (PyGeNN backend) → Issue 6.2 (integration) → Issue 6.3 (scale up)
```

## Key Design Decisions

- **Weight updates between episodes, not during:** PyGeNN's `StaticPulse` synapse model
  doesn't support online weight changes. Instead, we accumulate spike timing correlations
  on GPU (via custom neuron variables tracking pre/post spike times), pull them to CPU
  after each episode, compute eligibility-based weight updates in numpy, then push new
  weights back to GPU. This matches the existing pattern in `TrainingHarness`.

- **Eligibility trace computation:** Two approaches:
  - (A) Record all spike times on GPU, compute eligibility on CPU post-episode
  - (B) Use GeNN's custom weight update model with `dApre/dt` and `dApost/dt` variables
  Option (B) is more faithful to the Brian2 implementation and keeps the computation on
  GPU. PyGeNN custom weight update models support this.

- **FlyGym stays on CPU:** MuJoCo doesn't benefit from GPU compute for single-body
  simulation. The coupling loop runs: GPU neural step → pull motor spikes → CPU body
  step → push sensory currents → GPU neural step. Latency per coupling step should be
  ~1ms (dominated by GPU kernel + PCIe transfer), so the 1000 steps per 2s episode
  should take ~1-2s total.

- **Checkpoint compatibility:** Same .npz format as Brian2 training. Trained weights
  can be evaluated with `TrainedController` regardless of which backend trained them.

## Technical Notes

### PyGeNN STDP Support

PyGeNN supports custom weight update models with pre/post spike event code:

```python
from pygenn import create_weight_update_model_class

stdp_model = create_weight_update_model_class(
    "stdp_eligibility",
    param_names=["tauSTDP", "tauElig"],
    var_name_types=[("g", "scalar"), ("Apre", "scalar"), ("Apost", "scalar"),
                    ("eligibility", "scalar")],
    sim_code="eligibility -= eligibility * (dt / tauElig);",
    pre_spike_code="""
        Apre += 1.0;
        eligibility += Apost;
        addToPost(g);
    """,
    post_spike_code="""
        Apost += 1.0;
        eligibility += Apre;
    """,
)
```

This runs entirely on GPU and produces per-synapse eligibility traces that can be
pulled to CPU for the reward-modulated weight update.

### Existing Infrastructure

- `simulate.py::run_full_vnc()` — Complete PyGeNN 15K-neuron VNC model (working)
- `training.py::TrainingHarness` — Episode management, reward, homeostasis (working)
- `/usr/local/cuda/bin/nvcc` — CUDA compiler available
- PyGeNN 5.4.0 installed and tested

### Performance Estimate

The existing `run_full_vnc()` simulates 15K neurons for 5s in ~30s wall-clock on the A10G
(~6x realtime). For the 100-neuron training network:
- Neural sim: <1s for 2s simulated (100 neurons is trivial on GPU)
- FlyGym coupling: ~2s (same as now — body simulation doesn't change)
- Total per episode: ~3-5s (vs 118s on CPU) — **25-40x speedup**

Even with the 15K network, we'd expect ~10-15s per episode.

## Success Criteria

1. GPU training produces forward-distance rewards within 10% of CPU training (same learning dynamics)
2. Per-episode wall time < 10s for 100-neuron network (>10x speedup over CPU)
3. Checkpoint files are interchangeable between backends
4. `learn experiment` with GPU backend completes in <30 minutes (vs ~3 hours on CPU)

## Open Questions

- Should we use GeNN's built-in `STDPAdditive` model or write a custom one for the
  three-factor (eligibility-gated) STDP? Custom is more faithful but more work.
- PCIe transfer overhead for pushing/pulling currents every 2ms — is this the bottleneck
  for the 100-neuron case? (Probably negligible given small data size.)
- For the 15K network, which motor neurons map to which legs? Need to extract this from
  the VNC connectome annotations.
