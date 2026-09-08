# Hop Count Experiment: 2-hop vs 3-hop

**Date:** 2026-08-16
**Status:** todo
**Parent:** Epic: Functional Selection Optimization
**Depends on:** Tooling: GPU Default + Configurable Hops

## Problem

The 1-hop network (248 neurons) misses the CPG (Central Pattern Generator) interneurons
that create rhythmic alternating patterns. These oscillator neurons sit at 2 hops from
motor neurons. At 3 hops we'd also include descending command neurons from the brain.

Without internal oscillators, STDP has to *discover* rhythmic patterns from scratch.
With them, STDP only needs to *tune timing*, which is easier.

## Desired Behavior

Build and train two network configurations:
- **2-hop**: motor neurons + premotor + CPG layer (~400-500 neurons expected)
- **3-hop**: motor + premotor + CPG + descending command (~600-800 neurons expected)

Train each for 50 episodes (2s each) on GPU. Use current STDP algorithm with reduced
homeostatic plasticity (η=0.005 — half strength, to avoid the known issue of plasticity
fighting STDP while still preventing runaway).

### Demo

Comparison output showing:
- Neuron count and composition for each hop level
- Forward distance learning curve (per-episode reward over 50 episodes)
- Which topology shows improvement (increasing reward over time)

## Experimental design

| Config | Hops | η | Expected neurons | Expected time/ep |
|--------|------|---|-----------------|-----------------|
| A      | 2    | 0.005 | ~400-500   | ~8-10s (GPU)    |
| B      | 3    | 0.005 | ~600-800   | ~12-15s (GPU)   |

Both configurations:
- 50 episodes × 2s each
- Reward = forward displacement (mm)
- STDP with eligibility traces, reward modulation
- Synaptic decay λ=1e-4 (keep for now, tune in next issue)
- Checkpoints every 10 episodes

## Success criteria

- At least one configuration shows reward increasing over the 50 episodes
- Clear winner between 2-hop and 3-hop (or evidence they're equivalent)
- Results logged to `reports/hop_experiment_2hop.json` and `reports/hop_experiment_3hop.json`
