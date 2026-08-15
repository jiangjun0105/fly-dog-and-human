---
id: 2026-08-15-learning-experiment
title: "Controlled experiment: biological vs random topology"
created: 2026-08-15T14:30
status: open
priority: medium
type: feature
area:
reporter_side: engineering
need_verify: true
related_issues: ["2026-08-15-learning-full-plasticity"]
related_tasks: []
parent_epic: epic4-learning-locomotion
---

# Controlled experiment: biological vs random topology

The car for Epic 4 and the research culmination: run the same learning experiment
on biological connectivity vs. a random-topology control network. This answers the
core hypothesis: does biological form accelerate functional learning?

## Current Behavior

(After Issue 4.2) The biological network learns locomotion. But we don't know if the
biological topology is actually helping — maybe any network with the same parameters
would learn just as well.

## What's Wrong

Without a control, we can't attribute learning success to the biological connectivity
structure. The research question remains unanswered.

## Desired Behavior

- Generate a random-topology control: same neuron count, same degree distribution,
  same E/I ratio, but randomly wired (destroying biological specificity)
- Run identical training on both networks (same learning rules, same parameters,
  same number of episodes)
- Statistical comparison over N runs (≥5 seeds each) on:
  - Learning speed (episodes to threshold performance)
  - Final performance (forward distance after training)
  - Gait stability (leg coordination metrics)
- Clear result: biological topology learns faster/better, OR it doesn't (both are
  interesting scientific findings)

## Demo

Run `python -m digital_drosophila experiment topology_comparison --seeds 5` →
1. Trains 5 biological-topology networks and 5 random-topology networks
2. Each for 100 episodes
3. Produces: learning curves with confidence bands (bio vs random), statistical test,
   before/after videos for best run of each condition
4. Saves full results to `reports/topology_experiment/`

## Notes

- Random network generation: preserve degree distribution (same in/out degree per
  neuron), randomize targets. This controls for network density while disrupting specificity.
- Keep sign constraints in random network too (same E/I ratio) — only topology changes
- Statistical test: Mann-Whitney U or permutation test on final forward distance
- This is the experiment that justifies the whole project — worth doing carefully
- Budget GPU time for this (5 seeds × 2 conditions × 100 episodes × 5-10s each)
- Gait analysis: extract leg phase relationships from joint angle time series,
  compare to tripod/tetrapod gait patterns known in Drosophila
