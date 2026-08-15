---
id: 2026-08-15-learning-stdp-reward
title: "Reward-modulated STDP on the closed sensorimotor loop"
created: 2026-08-15T14:30
status: open
priority: medium
type: feature
area:
reporter_side: engineering
need_verify: true
related_issues: ["2026-08-15-sensorimotor-harness"]
related_tasks: []
parent_epic: epic4-learning-locomotion
---

# Reward-modulated STDP on the closed sensorimotor loop

The skateboard for Epic 4: implement three-factor STDP (pre-post timing × eligibility
trace × dopamine/reward signal) and show that the network can improve its behavior
over episodes, even crudely.

## Current Behavior

(After Epic 3) The closed loop runs: the fly twitches randomly driven by network
activity. Synaptic weights are fixed — no learning occurs.

## What's Wrong

Without plasticity, the network can't adapt its output to produce useful behavior.
The fly twitches randomly forever.

## Desired Behavior

- Three-factor STDP implemented in Brian2 Synapses:
  - Factor 1: Pre-post spike timing (causal window ~20ms from doc 04)
  - Factor 2: Eligibility trace (tau ~1-5s, decaying record of "what changed")
  - Factor 3: Dopamine/reward gate (broadcast signal modulates weight updates)
- Reward signal: forward velocity extracted from MuJoCo body state
- Running multiple episodes shows ANY improvement in forward distance
- Weight changes are bounded (hard sign constraint still holds from Epic 1)

## Demo

Run `python -m digital_drosophila learn stdp_test --episodes 20` →
1. Runs 20 episodes of 5s each with reward-modulated STDP active
2. Prints per-episode forward distance showing trend (ideally improving)
3. Plots learning curve: forward distance vs. episode number
4. Even if improvement is small/noisy, the mechanism demonstrably works
   (weights change in response to reward)

## Notes

- Three-factor STDP from `docs/neuroscience/04-learning-normal.md`:
  - `dw/dt = eta * eligibility * dopamine_signal`
  - `d(eligibility)/dt = -eligibility/tau_e + STDP_window(t_pre, t_post)`
  - `dopamine_signal = reward - baseline` (broadcast to all plastic synapses)
- Hard sign constraint: excitatory weights stay ≥0, inhibitory stay ≤0
- Start with all synapses plastic; later restrict to specific pathways
- Don't need locomotion — just measurable improvement over random baseline
- tau_eligibility = 1-5s means reward can be delayed (not immediate)
