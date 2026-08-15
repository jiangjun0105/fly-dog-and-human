---
id: 2026-08-15-brian2-biological-constraints
title: "Add biological constraints to Brian2 network (signs, weights, superclasses)"
created: 2026-08-15T10:01
status: open
priority: high
type: feature
area:
reporter_side: engineering
need_verify: true
related_issues: ["2026-08-15-brian2-minimal-network"]
related_tasks: []
parent_epic: epic1-brian2-network
---

# Add biological constraints to Brian2 network (signs, weights, superclasses)

Thicken the minimal network with biological fidelity: neurotransmitter-based sign
constraints, proper weight initialization formula, and neuron partitioning by superclass.
Still on 100 neurons — proving the biology is correct before scaling.

## Current Behavior

(After Issue 1) A minimal Brian2 network fires with raw synapse counts as weights and
no sign constraints. All neurons are treated identically.

## What's Wrong

The network doesn't respect biology: inhibitory neurons (GABA, glutamate) should have
negative weights, excitatory (acetylcholine) should have positive weights. Neurons
aren't differentiated by role (sensory vs. motor vs. intrinsic). Weight magnitudes
don't follow the design doc formula.

## Desired Behavior

- The network uses sign-constrained weights: `w_ij = log(1 + synapse_count) × sign × confidence × scale`
  with sign from `NT_SIGN_MAP` in `constants.py`
- Neurons are partitioned into NeuronGroups by superclass (sensory, intrinsic, motor,
  ascending, descending) with group-appropriate parameters
- Hard sign constraint enforced: weights cannot cross zero during any future learning
- Poisson input targets only sensory neurons (not all neurons)
- The network still fires with biologically plausible rates (1-30 Hz mean, no runaway)

## Demo

Run `python scripts/run_brian2_constrained.py` → loads the same 100-neuron sample but now:
(1) prints a summary showing neuron counts per superclass and excitatory/inhibitory ratio,
(2) produces a raster plot color-coded by superclass,
(3) prints mean firing rates per superclass (all in 1-30 Hz range).
The plot visually shows different activity patterns for sensory (driven) vs. intrinsic
(emergent) vs. motor (output) populations.

## Notes

- Sign mapping: acetylcholine → +1, GABA → -1, glutamate → -1, serotonin/dopamine → modulatory (skip or +1 for now)
- "Unclear" NT neurons (most motor neurons are glutamatergic/unclear): initialize near zero per doc 02
- Confidence weighting from `consensusNt` prediction confidence in the dataset
- Scale factor will need tuning — start with 1.0 and adjust if rates are wrong
- Neuromodulation parameters: stub them (define the variables) but don't activate (arousal = baseline)
- Reference: `docs/neuroscience/02-lif-model-design.md` §Parameter Decision Table
