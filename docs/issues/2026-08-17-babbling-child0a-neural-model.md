# Child 0a: Fix the Neural Model — synaptic delay + bounded STDP

**Date:** 2026-08-17
**Status:** todo
**Parent:** [Epic: Sensorimotor Babbling — Level 1](2026-08-17-sensorimotor-babbling-level1.md)
**Type:** enabler

## Problem

Two defects in the spiking model make Level 1 unmeasurable, and neither is visible from the
outside — the simulation runs happily and produces plausible-looking numbers.

**1. Transmission is instantaneous.** `network.py` builds every synapse as:

```python
S = Synapses(G, G, "w : volt", on_pre="v_post += w")
```

A presynaptic spike raises `v_post` in the same timestep. Real *Drosophila* chemical
synapses cost ~0.8-1.5 ms each. Only the membrane-integration term (~1-4 ms) is currently
modelled, so **every round-trip we measure is optimistic by 1-3 ms per hop.** Child 1's
entire result is a latency comparison against a 20 ms window, so this is not a rounding
error — it is the difference between "loop closes" and "loop closes on paper."

**2. STDP has no upper weight bound.** `functional_training.py` enforces only Dale's
principle:

```python
self._current_weights[exc_mask] = np.maximum(self._current_weights[exc_mask], 0.0)
self._current_weights[inh_mask] = np.minimum(self._current_weights[inh_mask], 0.0)
```

Sign is constrained; magnitude is not. This is survivable under reward modulation, where the
reward term changes sign and opposes growth. Child 2 runs **unmodulated** STDP with sustained
30-50 ms bursts, which pair pre/post dozens of times per episode with nothing pushing back.
Additive STDP will run away.

## Desired Behavior

- Synapses carry a per-synapse transmission `delay` in the 0.8-1.5 ms range.
- STDP potentiation is **soft-bounded**: `Δw ∝ (w_max − w)`, so growth saturates smoothly.
- Dale's principle still holds after bounding (excitatory ≥ 0, inhibitory ≤ 0).
- The measured neural propagation term is reported and checked against the
  **2-4 ms direct / 5-8 ms via one interneuron** expectation.

### Demo

Stimulate a neuron, record a downstream spike, print the elapsed time. Show that it is
1-3 ms longer per hop than before the change, and that the increase matches the configured
delay rather than appearing from somewhere else.

Then run a burst long enough to saturate a synapse and show the weight approaching `w_max`
asymptotically instead of crossing it.

## Technical notes

- Prefer **soft-bounding over a hard clip.** A clip pins a whole population of synapses at
  exactly `w_max`, which destroys the graded weight differences Child 2 is trying to measure.
  That is the entire dependent variable of the next experiment.
- `DEFAULT_LIF_PARAMS`: `tau_m = 10 ms`, `V_rest = -70 mV`, `V_th = -50 mV`,
  `V_reset = -70 mV`, `R_membrane = 100 MΩ`, `t_refract = 2 ms`.
- Rheobase is therefore **200 pA** (`20 mV / 100 MΩ`) — below this a neuron never fires at
  any duration. Useful as a sanity check when interpreting propagation failures.
- Delay should be settable, not hardcoded — the 0.8-1.5 ms figure is a literature estimate,
  and Child 1 may need to test sensitivity to it.
- Both the GPU (PyGeNN) and CPU (Brian2) paths need the delay, or timings will silently
  disagree between backends.
- `w_max` needs a defensible value, not a round number. Derive it from the existing weight
  distribution in the full VNC connectome rather than picking one.

## Out of scope

Do not wire up the musculoskeletal body or touch the sensory encoder — those are Child 0b
and 0c. This issue is the neural model only.
