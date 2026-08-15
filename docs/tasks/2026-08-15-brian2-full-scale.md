---
id: 2026-08-15-brian2-full-scale
title: "Scale Brian2 network to full VNC connectome with burn-in validation"
created: 2026-08-15T12:00
status: done
priority: medium
type: task
suitability: needs_human
depends_on:
  - 2026-08-15-brian2-biological-constraints
related: []
satisfies: []
branch: ""
pr: ""
auto_agent_task_id: ""
---

# Scale Brian2 network to full VNC connectome with burn-in validation

## Context

Issues 1.1 and 1.2 proved the concept on 100 neurons. This task scales to the full VNC
connectome (~15,000-20,000 neurons) using the GeNN GPU backend, and implements the burn-in
protocol from the design docs. This is the "car" — the output Epic 3 (sensorimotor loop)
will connect to the body.

Parent issue: `docs/issues/2026-08-15-brian2-full-scale.md`

## Problem

100 neurons is a toy. The sensorimotor loop needs all 702 motor neurons and the full
connectivity to produce meaningful body control. Scaling 100× requires GPU acceleration
(GeNN) and careful validation that the network doesn't collapse or explode at scale.

## Desired Behavior

1. A script queries the full VNC connectome via neuPrint API (or loads from cache) and
   builds a Brian2/GeNN network with all VNC neurons (~15,000-20,000)
2. Uses GeNN backend for GPU acceleration on the A10G
3. Applies the same biological constraints from Issue 1.2 (sign-constrained weights,
   NT-based initialization) at full scale
4. Runs the burn-in protocol: Poisson input to sensory/descending neurons, waits for
   steady-state spontaneous activity
5. Validation passes: mean firing rates 1-30 Hz per superclass, no population goes
   silent, no runaway excitation
6. Performance: the 5-second burn-in completes in < 60 seconds wall-clock (≥80× realtime)

## Demo

Run `python -m digital_drosophila simulate full_vnc` → queries neuPrint (or cache), builds full
VNC network on GPU, runs 5-second burn-in, produces:
(1) population firing rate time-series (one line per superclass) showing convergence,
(2) subsampled raster plot,
(3) validation report with rates/E-I ratio.

## Key Files

| File | Purpose |
|------|---------|
| [`src/digital_drosophila/network.py`](../../src/digital_drosophila/network.py) | Network builder — extend with full-scale construction |
| [`src/digital_drosophila/simulate.py`](../../src/digital_drosophila/simulate.py) | Simulation runner — add `run_full_vnc()` mode |
| [`src/digital_drosophila/plotting.py`](../../src/digital_drosophila/plotting.py) | Visualization — extend for burn-in time-series plots |
| [`src/digital_drosophila/data.py`](../../src/digital_drosophila/data.py) | neuPrint API client: `load_vnc_neurons()`, `load_connectivity()` |
| [`src/digital_drosophila/constants.py`](../../src/digital_drosophila/constants.py) | NT_SIGN_MAP |
| [`docs/neuroscience/04-learning-normal.md`](../neuroscience/04-learning-normal.md) | Burn-in protocol specification |
| [`docs/neuroscience/02-lif-model-design.md`](../neuroscience/02-lif-model-design.md) | LIF parameters, neuromodulation stubs |

## Suggested Approach

### 1. Data acquisition

Use the existing data module which provides joblib-cached neuPrint queries:
```python
from digital_drosophila.data import connect, load_vnc_neurons, load_connectivity
connect()  # requires NEU_PRINT_API_KEY in .env
neurons_df = load_vnc_neurons()  # ~15k-20k neurons
connectivity = load_connectivity()  # sparse adjacency
```

### 2. Extend the package

Add a `run_full_vnc()` function in `src/digital_drosophila/simulate.py` that reuses:
- `network.create_neuron_group()` — same LIF parameters, just more neurons
- `network.create_synapses_constrained()` — same sign logic, full adjacency
- `network.create_poisson_drive()` — targeting sensory/descending neurons
- `plotting.plot_raster()` — subsampled for visibility at scale

Register it as a mode in `__main__.py` so `python -m digital_drosophila simulate full_vnc` works.

### 3. GeNN backend

```python
from brian2 import prefs
prefs.codegen.target = 'genn'  # requires nvcc on PATH
```

Potential blocker: `nvcc` is not currently on PATH. May need:
`export PATH=/usr/local/cuda/bin:$PATH` or install CUDA toolkit.

### 4. Scale considerations

- ~15k neurons × 12.75% density ≈ 28M synapses — large but GeNN handles this
- Memory: estimate ~2-4 GB GPU memory for the network state
- May need sparse connectivity representation rather than dense matrix

### 5. Burn-in protocol (from doc 04)

- Inject Poisson input to sensory neurons at biological rates (~10-20 Hz)
- Run until firing rates stabilize (check variance over sliding window)
- "Stable" = per-superclass rate variance < 10% over last 1s

### Recommendation

Start with a medium-scale test (~2000-3000 neurons: all motor neurons + direct
presynaptic partners) before attempting full 15k. This catches scaling issues early.

## Implementation Approach

- **Artifact type:** New mode in `src/digital_drosophila/simulate.py` (`run_full_vnc()`)
- **Extend existing:** Reuse `network.py` builders (create_neuron_group, create_synapses_constrained, etc.) at full scale
- **Do not:** Create standalone scripts in `scripts/`, skip the intermediate scale test, use CPU Brian2 at this scale

## Acceptance Criteria

- [ ] `python -m digital_drosophila simulate full_vnc` runs without error
- [ ] Loads full VNC data (from neuPrint cache or API)
- [ ] GeNN GPU backend is configured and working
- [ ] Network builds with all VNC neurons using `network.create_synapses_constrained()`
- [ ] 5-second burn-in runs to completion in < 60 seconds
- [ ] Per-superclass firing rates converge to 1-30 Hz
- [ ] No population goes silent or saturates
- [ ] Output includes validation report + plots (via `plotting.py`)

## Notes

- **Marked `needs_human`** because:
  - Requires `nvcc` on PATH (may need CUDA toolkit setup)
  - Requires neuPrint API token (in .env)
  - GeNN compilation can fail with unclear errors — needs interactive debugging
  - Scale factor tuning at 15k neurons is less predictable than 100
- Consider an intermediate milestone: ~2000 neurons (motor + presynaptic) as a stepping stone
- The neuPrint API token is in `.env` as `NEU_PRINT_API_KEY`
- joblib cache means second runs are fast (no API calls)
