# Child 0b: Sensory Calibration — make an afferent able to spike

**Date:** 2026-08-17
**Status:** todo
**Parent:** [Epic: Sensorimotor Babbling — Level 1](2026-08-17-sensorimotor-babbling-level1.md)
**Type:** experiment + fix

## Problem

**As shipped, no proprioceptive afferent can ever fire.** `ProprioceptiveEncoder` defaults to
`gain_pa = 75.0`, so its maximum possible output at activation 1.0 is 75 pA. LIF rheobase is
**200 pA** (`V_th − V_rest = 20 mV` over `R_membrane = 100 MΩ`). 75 pA is **0.38× rheobase** —
below the current at which a neuron fires *at all*, regardless of how long it is applied.

The demo's "60.68 pA" readings were reported as evidence the encoder works. They are
sub-threshold currents, not firing. The old `SensoryEncoder` used **500 pA**
(`loop.py: sensory_gain=500e-12`); the new default came from doc 14's "50-100 pA" note, which
was never checked against rheobase.

Separately, **the force channel is dead.** The 2 `SNpp53` afferents (campaniform sensilla)
read ground reaction force, which is identically zero in the tethered world — the tarsus
clears the floor by 0.97 and the only contacts are Thorax↔Coxa self-collisions
(interpenetration, not weight-bearing).

This is the **mirror of the motor calibration we already did.** That one asked "how fast must
a motor neuron fire before the joint moves in time?" This one asks "how much movement is
needed before an afferent spikes, and what gain makes that happen?"

## Desired Behavior

- A gain configuration under which afferents fire in a useful **~40-100 Hz** band, verified
  by counting spikes on real LIF neurons — not by computing currents and asserting.
- `SNpp53` reads **tendon tension** (`d.actuator_force`) instead of ground reaction force.
- A documented **minimum detectable movement** — the sensory analogue of the motor
  firing-rate floor.

### Demo

Sweep gain × joint displacement, run real LIF neurons, print a table of resulting firing
rates. Show a named afferent going from 0 Hz to a rate in the target band as gain crosses
rheobase.

## Technical notes

**The switch to tendon force is a correction toward biology, not a workaround.** Campaniform
sensilla measure cuticle strain and muscle load, not ground contact. A tethered fly pulling
its tibia against an immovable tether fires its CS as strongly as one standing on the ground.
Independently confirmed in external review.

Starting arithmetic (position channel, tibia half-range 1.0115 rad), cross-checked against
*measured* muscle-driven movement:

| gain | movement needed to spike | reachable by muscle activation |
|------|--------------------------|-------------------------------|
| 75 pA | impossible (needs activation 2.67) | **never** |
| 300 pA | 0.674 rad | only at act ≥ 1.00 |
| 500 pA | 0.405 rad | act ≥ 0.40 |
| 800 pA | 0.253 rad | act ≥ 0.40 |
| 1000 pA | 0.202 rad | act ≥ 0.20 |

Analytic current → rate above rheobase (no noise): 220 pA → 38 Hz, 250 → 55, 300 → 77,
400 → 112, 500 → 141, 800 → 205. **Treat these as predictions to test, not answers** — the
200 pA rheobase assumes an isolated neuron, and synaptic input plus background noise may
lower the practical floor. That is precisely why this is an experiment rather than a
one-line default change.

Questions the sweep should settle:

1. **Per-modality gains, or one shared `gain_pa`?** Position rests near 0 while force sits
   tonically high — a single gain probably cannot serve both. Current defaults:
   `gain_pa = 75.0`, `max_velocity = 25.0`, `max_force = 120.0`.
2. **Is `max_velocity = 25.0` the right scale?** At 500 pA the velocity channel needs
   10 rad/s. Measured peak tibia velocity was ~21 rad/s — reachable, but only transiently.
3. **Does the position channel's unsigned `|angle − rest|` lose information STDP needs?**
   Flexion and extension currently produce identical current.

Other constraints:

- **Settle ~3000 steps before measuring.** At 500 steps the tibia is still drifting at
  −4 rad/s; measuring from an unsettled leg contaminates the baseline. (`dt = 0.1 ms`.)
- Encoder selects 41 afferents (45 matched, 4 `SApp23` excluded as ascending with zero motor
  connections). Laterality is **`rootSide`**, not `somaSide` — `somaSide` is NaN for all
  afferents because their somata sit in the leg periphery.

## Out of scope

Do not add synaptic delays or STDP bounding (Child 0a), and do not wire the body into the
training harness (Child 0c). Use whatever minimal physics setup is needed to produce joint
displacement for the sweep.
