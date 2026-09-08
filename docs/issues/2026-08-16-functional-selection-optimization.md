# Epic: Functional Selection Optimization

EPIC — container issue, do not execute; work lives in child issues.

**Date:** 2026-08-16
**Status:** todo
**Context:** [ideas/2026-08-15-functional-neuron-selection.md](../ideas/2026-08-15-functional-neuron-selection.md)

## Summary

Expand the functional neuron selection from 1-hop/248-neuron to 2-3 hops, tune homeostatic
plasticity parameters, and run on GPU by default. Goal: achieve visible learning improvement
where STDP training measurably increases forward locomotion over episodes.

## Background

- 1-hop functional selection (248n) gives 1.49mm mean reward (1.4× over hub-neuron baseline)
- But STDP is fought by homeostatic plasticity — performance declines over training (2.15→1.13mm)
- Missing CPG pattern generators at 2 hops means network has no internal oscillator
- GPU backend (30× speedup) is available but not wired to functional training

## Capabilities (child issues)

1. **Tooling: GPU + configurable hops** (enabler)
   - Make functional training run on GPU by default
   - Make hop count a configurable parameter
   - Demo: `learn train_functional --hops 2` runs on GPU in ~8s/episode

2. **Hop count experiment: 2-hop vs 3-hop**
   - Build 2-hop and 3-hop networks (expect ~400-500n and ~600-800n)
   - Train both (50 episodes each) with existing algorithm
   - Compare learning curves — which topology enables STDP to improve locomotion?
   - Demo: comparison plot showing forward distance progression for 2-hop vs 3-hop

3. **Plasticity tuning: η=0 vs η=0.005**
   - Run on the winning topology from #2
   - Compare fully-off (η=0) vs half-strength (η=0.005) vs current (η=0.01, already known bad)
   - Demo: comparison plot + video of best-performing configuration

## Dependency spine

```
[1] Tooling (enabler)
 └──→ [2] Hop experiment
       └──→ [3] Plasticity experiment
```

## Success criteria

- At least one configuration shows forward distance *increasing* over 50 episodes
- Best configuration produces demo video showing visibly improved locomotion vs untrained baseline
- Total experiment wall time < 2 hours on GPU
