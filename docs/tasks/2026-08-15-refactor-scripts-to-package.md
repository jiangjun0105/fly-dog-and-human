---
id: 2026-08-15-refactor-scripts-to-package
title: "Refactor Brian2 simulation scripts into digital_drosophila package modules"
created: 2026-08-15T13:00
status: open
priority: high
type: task
suitability: auto_agent_ready
depends_on: []
related:
  - 2026-08-15-brian2-minimal-network
  - 2026-08-15-brian2-biological-constraints
satisfies: []
branch: ""
pr: ""
auto_agent_task_id: ""
---

# Refactor Brian2 simulation scripts into digital_drosophila package modules

## Context

We have two working Brian2 simulation scripts (`scripts/run_brian2_minimal.py` and
`scripts/run_brian2_constrained.py`) that were created as rapid prototypes. They work
but duplicate code and don't belong in `scripts/` — that directory is for process
tooling (create-task.py, dispatch-task.py, etc.), not research code.

The project needs a maintainable package structure where simulation code lives in
`src/digital_drosophila/` and can be invoked via `python -m digital_drosophila.simulate`.

## Problem

- Two scripts with significant code duplication (LIF parameters, neuron group creation,
  Poisson input setup, plotting boilerplate)
- Research code mixed with process tooling in `scripts/`
- No reusable API — the full-scale task (Issue 1.3) would have to copy-paste again
- Can't import simulation components from other modules

## Desired Behavior

1. `python -m digital_drosophila.simulate minimal` runs the minimal (raw-weight) simulation
2. `python -m digital_drosophila.simulate constrained` runs the sign-constrained simulation
3. Both produce the same outputs as before (raster plots in `reports/`, firing rate stats on stdout)
4. The old scripts (`scripts/run_brian2_minimal.py`, `scripts/run_brian2_constrained.py`) are deleted
5. Shared logic is factored into reusable modules within `src/digital_drosophila/`

## Demo

```bash
python -m digital_drosophila.simulate constrained
```
→ prints E/I ratio, per-superclass firing rates (all 1-30 Hz), saves `reports/brian2_constrained_raster.png`

```bash
python -m digital_drosophila.simulate minimal
```
→ prints neuron stats, mean firing rate, saves `reports/brian2_minimal_raster.png`

## Key Files

| File | Purpose |
|------|---------|
| `scripts/run_brian2_minimal.py` | Source — the minimal simulation to refactor |
| `scripts/run_brian2_constrained.py` | Source — the constrained simulation to refactor |
| `src/digital_drosophila/constants.py` | Existing — NT_SIGN_MAP, already in the package |
| `src/digital_drosophila/data.py` | Existing — neuPrint data access |

## Suggested Approach

### Target structure

```
src/digital_drosophila/
├── __init__.py
├── __main__.py          # CLI entry: python -m digital_drosophila.simulate
├── constants.py         # existing (unchanged)
├── data.py              # existing (unchanged)
├── network.py           # Network builder: load data, create NeuronGroup, create Synapses
├── simulate.py          # Simulation runner: configure, run, collect results
└── plotting.py          # Raster plots, rate analysis, saving figures
```

### Module responsibilities

**`network.py`** — Build Brian2 networks from connectome data:
- `load_sample_data(data_dir) -> (adj, neurons_df)` — load adjacency + metadata
- `create_neuron_group(n, params=None) -> NeuronGroup` — LIF group with standard params
- `create_synapses_minimal(G, adj, scale) -> Synapses` — raw synapse-count weights
- `create_synapses_constrained(G, adj, neurons_df, scale, inh_attenuation) -> Synapses` — sign-constrained weights
- `create_poisson_drive(G, neurons_df, target_superclass, ...) -> (PoissonGroup, Synapses)` — targeted Poisson input
- `create_background_drive(G, n_sources, rate, weight) -> (PoissonGroup, Synapses)` — background input to all

**`simulate.py`** — Run simulations and collect results:
- `run_simulation(G, duration, monitors) -> SimResult` — run and return structured result
- `compute_firing_rates(spike_monitor, neurons_df, duration) -> dict` — per-superclass rates
- `validate_rates(rates, min_hz, max_hz) -> bool` — check biological range

**`plotting.py`** — Visualization:
- `plot_raster(spike_monitor, neurons_df, title, output_path)` — color-coded by superclass
- `plot_raster_minimal(spike_monitor, title, output_path)` — single-color raster

**`__main__.py`** — CLI dispatcher:
```python
"""Entry point: python -m digital_drosophila.simulate <mode>"""
import sys
from .simulate import run_minimal, run_constrained

modes = {"minimal": run_minimal, "constrained": run_constrained}

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "constrained"
    modes[mode]()
```

Wait — `python -m digital_drosophila.simulate` requires `simulate` to be a subpackage.
Better: make `__main__.py` in the `digital_drosophila` package itself:

`python -m digital_drosophila --mode constrained` or use a simple subcommand:
`python -m digital_drosophila simulate constrained`

Simplest: `python -m digital_drosophila.simulate` triggers `simulate/__init__.py` or
just put the entry in `src/digital_drosophila/__main__.py` with mode arg.

### Key constraints

- **Preserve exact behavior** — both modes must produce identical output (rates, plots) to the current scripts
- **No new dependencies** — only use what's already in pyproject.toml (brian2, numpy, pandas, matplotlib)
- **Delete the old scripts** — `scripts/run_brian2_minimal.py` and `scripts/run_brian2_constrained.py` are removed
- **DATA_DIR path** — currently relative `src/wiki/data/metrics/sample_100`. Use `Path(__file__).resolve()` to compute absolute paths so `python -m` works from any directory.
- **Brian2 prefs** — set `prefs.codegen.target = "numpy"` early, before any network creation
- **Do NOT touch** `scripts/create-task.py`, `scripts/dispatch-task.py`, etc. (process tooling stays)

## Implementation Approach

- **Artifact type:** New modules in `src/digital_drosophila/` + deletion of 2 scripts
- **Extend existing:** Build on the package that already has `constants.py` and `data.py`
- **Do not:** Create a separate package, add CLI framework dependencies (argparse is fine), change the simulation parameters or behavior

## Acceptance Criteria

- [ ] `python -m digital_drosophila simulate minimal` runs without error, produces raster plot and rate output
- [ ] `python -m digital_drosophila simulate constrained` runs without error, produces raster plot with correct E/I ratio and per-superclass rates in 1-30 Hz
- [ ] `scripts/run_brian2_minimal.py` is deleted
- [ ] `scripts/run_brian2_constrained.py` is deleted
- [ ] No code duplication between minimal and constrained modes (shared LIF params, neuron group creation, etc.)
- [ ] All paths use `Path(__file__).resolve()` — no fragile relative paths
- [ ] Existing tests (if any) still pass
- [ ] `from digital_drosophila.network import create_neuron_group` works as an importable API

## Notes

- The `explore_connectome.py` script in `scripts/` can stay for now — it's a one-off data exploration script, not part of the simulation pipeline. But if the agent wants to move it too, that's fine.
- The `src/wiki/` data directory is where the sample data lives — don't move that, just reference it properly.
- Brian2's `prefs.codegen.target` must be set before any Brian2 objects are created.
