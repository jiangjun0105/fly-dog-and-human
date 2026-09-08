# Plasticity Tuning Experiment: η=0 vs η=0.005

**Date:** 2026-08-16
**Status:** todo
**Parent:** Epic: Functional Selection Optimization
**Depends on:** Hop Count Experiment (uses winning topology)

## Problem

Homeostatic plasticity (η=0.01) actively fights STDP learning. In the 1-hop experiment,
performance declined from 2.15mm to 1.13mm over 50 episodes — homeostasis raises thresholds
faster than reward reinforces useful synapses. The two mechanisms operate on different
timescales: homeostasis adapts every 2ms coupling step, while STDP only gets reward every
2 seconds.

## Desired Behavior

Using the winning topology from the hop experiment, run a plasticity parameter sweep:
- **η=0.0** — homeostatic plasticity fully disabled
- **η=0.005** — half the current strength

Compare against the hop experiment's result (which used η=0.005) to get the full picture.

### Demo

- Comparison plot: learning curves for η=0.0 vs η=0.005 (same topology)
- Video of best-performing configuration driving the fly body
- Clear answer: does removing homeostasis allow STDP to accumulate improvements?

## Experimental design

| Config | Hops | η     | λ (decay) | Expected behavior |
|--------|------|-------|-----------|-------------------|
| A      | best | 0.0   | 1e-4      | STDP unconstrained — risk of runaway excitation |
| B      | best | 0.005 | 1e-4      | Mild constraint — from hop experiment |

Both configurations:
- 50 episodes × 2s each, GPU backend
- Same STDP algorithm, same reward signal
- Checkpoints every 10 episodes
- Monitor firing rates (without homeostasis, may drift high/low)

## Risk: runaway excitation without homeostasis

With η=0, nothing prevents neurons from firing at 100+ Hz if STDP keeps strengthening
synapses. Monitor mean firing rate per episode. If it exceeds 80 Hz, the network is
unstable and needs at least minimal homeostasis. This is useful data either way.

## Success criteria

- One configuration shows forward distance *increasing* (not declining) over 50 episodes
- Generate demo video from best checkpoint showing improved locomotion
- Output: `reports/plasticity_eta0.json`, `reports/plasticity_eta005.json`
- Output: `reports/plasticity_best_demo.mp4`
