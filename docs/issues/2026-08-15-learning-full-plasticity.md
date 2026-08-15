---
id: 2026-08-15-learning-full-plasticity
title: "Full Phase 1 plasticity suite + training harness"
created: 2026-08-15T14:30
status: open
priority: medium
type: feature
area:
reporter_side: engineering
need_verify: true
related_issues: ["2026-08-15-learning-stdp-reward"]
related_tasks: []
parent_epic: epic4-learning-locomotion
---

# Full Phase 1 plasticity suite + training harness

The bicycle for Epic 4: add homeostatic plasticity and synaptic decay alongside STDP,
plus a proper training harness with episode management and logging. The fly produces
recognizable forward movement.

## Current Behavior

(After Issue 4.1) Reward-modulated STDP works but alone isn't enough — network can
drift to silence or saturation over many episodes. No homeostatic regulation.

## What's Wrong

STDP alone can cause runaway excitation or activity death over long training. Need
homeostatic mechanisms to keep the network in a healthy operating regime while learning.

## Desired Behavior

- Homeostatic plasticity: `dV_th/dt = eta_homeo * (firing_rate - target_rate)`
  keeps per-neuron firing rates near target (prevents silence and seizure)
- Synaptic decay: `dw/dt = -lambda_decay * w` for inactive synapses (prunes unused)
- Training harness: episode reset, metric logging, checkpoint saving
- After training (50-100 episodes), the fly produces recognizable forward locomotion
  (moves forward without falling, even if gait is imperfect)

## Demo

Run `python -m digital_drosophila learn train --episodes 100` →
1. Trains for 100 episodes with full plasticity suite
2. Logs per-episode metrics to `reports/training_log.json`
3. Saves weight checkpoints every 10 episodes
4. Final episode: fly moves forward measurably
5. Before/after comparison: episode 1 (random twitching) vs episode 100 (directed movement)

## Notes

- Homeostatic plasticity parameters from doc 04: `eta_homeo` small enough that it
  doesn't fight STDP on short timescales, but prevents drift over episodes
- Synaptic decay: `lambda_decay` should be slow (timescale of minutes/hours of sim time)
- STF/STD (short-term facilitation/depression) from doc 05 should be included —
  they help CPG rhythm generation and are listed as Phase 1 in doc 08
- Episode structure: reset body to standing, run burn-in (500ms), then training (5-10s)
