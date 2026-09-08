# STDP Training Produces No Visible Behavior Change

**Date:** 2026-08-15
**Experiment:** 50-episode training with homeostatic plasticity and synaptic decay

## What We Did

Ran full training pipeline: 100-neuron spiking network (Brian2) driving FlyGym body
through 50 episodes × 2s each. Reward = forward displacement. Three-factor STDP with
eligibility traces gates weight updates based on reward prediction error.

Also ran 10-episode GPU training (same setup, PyGeNN backend) — same outcome.

## What We Observed

- Forward distance: 1.03mm (first half) vs 1.05mm (second half) — no improvement
- The fly twitches randomly in both trained and untrained videos
- Homeostatic plasticity works correctly (firing rates converge to 25 Hz target)
- Synaptic decay correctly prunes inactive synapses
- Weights change (~26 mV total change) but not in a functionally meaningful direction

## Why It Didn't Work

**1. Wrong neurons.** The 100-neuron sample is selected by connectivity rank (top 100 by
input synapse count). This gives us hub neurons, not the locomotor circuit. Composition:
49 descending, 18 motor, 18 intrinsic, 15 ascending. The CPG premotor interneurons that
create alternating gait patterns are mid-connectivity neurons that didn't make the cut.

**2. Impossible credit assignment.** With 1275 synapses all active, a single scalar reward
delivered after 2 seconds, and eligibility traces decaying over 1s, the system can't
identify which synapses caused forward movement. The signal-to-noise ratio is too low.

**3. Motor mapping is arbitrary.** 18 motor neurons assigned to legs via round-robin
(`motor_neuron[i] → leg[i % 6]`). In reality, specific motor neurons innervate specific
muscles — this mapping is available in the connectome data (exitNerve column) but we
didn't use it.

**4. No structure in the sensory→motor pathway.** The 100 random hubs don't form the
feedforward pathway that exists in the real VNC (sensory → interneuron → premotor → motor).
Without this structure, there's no gradient for STDP to follow.

## What This Means

The learning rule isn't wrong — it's applied to the wrong substrate. STDP can fine-tune
a network that's *already close* to a solution (has the right connectivity structure),
but it can't discover coordinated locomotion from connectivity hubs with arbitrary
motor mapping.

## Next Steps

Select neurons by functional role instead of connectivity rank. Trace backward from
identified motor neurons (using exitNerve and superclass annotations) to find the
actual locomotor circuit. See `ideas/2026-08-15-functional-neuron-selection.md`.
