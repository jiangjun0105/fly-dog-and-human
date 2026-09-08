# Tooling: GPU Default + Configurable Hops

**Date:** 2026-08-16
**Status:** todo
**Parent:** Epic: Functional Selection Optimization
**Type:** enabler

## Problem

The functional training pipeline (`functional_training.py`) currently only supports the
Brian2 CPU backend, which takes ~117s per episode at 248 neurons. The GPU backend (PyGeNN)
is 30× faster and already works in the original `training.py`. Additionally, the hop count
in `functional_selection.py` is hardcoded to 1.

## Desired Behavior

- `functional_selection.py` accepts a `n_hops` parameter (default=2)
- `functional_training.py` uses GPU backend by default (fallback to CPU if unavailable)
- CLI: `python -m digital_drosophila learn train_functional --hops 2 --episodes 5` completes
  in under 1 minute (vs ~10 min on CPU)

### Demo

Run `python -m digital_drosophila learn train_functional --hops 2 --episodes 5` and see:
- GPU backend selected automatically
- ~8-10s per episode (not 117s)
- Training completes and saves checkpoint

## Technical notes

- The GPU integration pattern already exists in `training.py` (see `_build_gpu()`, `_run_episode_gpu()`)
- PyGeNN needs 180 pA tonic background current to replace Brian2's Poisson drive
- Sparse synapse vars use `.values` not `.view[:]`
- Reset via `model.timestep = 0`
- `functional_selection.py` should cache results per hop count (separate cache keys)
