# Child 0c: Wire the Body — muscles drive physics, end-to-end conduction

**Date:** 2026-08-17 (revised 2026-08-18 after 0a/0b landed)
**Status:** todo
**Parent:** [Epic: Sensorimotor Babbling — Level 1](2026-08-17-sensorimotor-babbling-level1.md)
**Depends on:** [Child 0a](2026-08-17-babbling-child0a-neural-model.md), [Child 0b](2026-08-17-babbling-child0b-sensory-calibration.md)
**Type:** enabler + demo

## Problem

**The muscles are computed but drive nothing.** `functional_training` builds `NeuroMechFly`
(66 position servos), so `MuscleDecoder.muscle_activations()` produces 15 Hill-type muscle
activations that are then discarded — only the 66-DOF `decode()` path is wired. Nothing
outside the decoder's own demo calls `muscle_activations()`.

This makes Child 1 unmeasurable for a subtler reason than "the wrong body." A position servo
commands a joint angle directly, so there is no inertial lag, no force-rise time, and no
tendon. The entire 3.2-15.5 ms physics latency that the motor calibration measured — and
which the whole 20 ms loop-closure budget is built around — **only exists in the
musculoskeletal body.** Measuring Child 1 on `NeuroMechFly` would report timings from a
mechanism the experiment is not about.

This issue is also the **exit gate for Level 1**: it produces the first end-to-end
measurement that the chain conducts at all.

## Desired Behavior

Drive one LF muscle in the spiking network and show that a **named** proprioceptive afferent
spikes as a consequence, with the elapsed time printed.

No STDP, no weight change. This is the walking skeleton — every seam
(network → muscle → physics → afferent → spike) exercised once, end to end.

### Demo

```
motor pool <ids> driven at <rate> Hz
  → muscle <name> activation <value>
  → joint <name> moved <n> rad
  → afferent <bodyId/type> [modality] spiked at t = <n> ms
```

**Report time-to-first-spike broken out per modality** (position / velocity / force /
posture), not just the earliest spike overall. This is the quantity the old scale table
should have contained and didn't — it measured "time until the joint starts moving," which
is a strictly earlier event than "time until an afferent spikes," so the two were never
chainable.

**Primary hypothesis: the first afferent to spike is on a velocity channel.** 0b measured
that within a 50 ms burst, position needs activation 0.60 to spike at all (displacement must
integrate first) while velocity fires from 0.20 and reaches 60 Hz by 0.30. Physics agrees:
for a step force on a damped spring-mass, velocity peaks early and decays as displacement
asymptotes. **If a position afferent spikes first, that hypothesis is wrong and worth saying
so plainly** — it would mean the damped-spring reasoning does not describe this body.

**Exit gate:** if no afferent can be made to spike from motor stimulation, Level 1 is blocked
and Children 1-2 cannot be interpreted. Report this outcome as a result, not a failure —
it would be a real finding about the connectome and body model.

## Second deliverable: can the return volley fire anything?

**This was added after 0a proved that no single connectome synapse can fire a postsynaptic
cell.** The strongest weight anywhere in the VNC is 3.98 mV; a presynaptic neuron firing at
2× rheobase has an 8.93 ms ISI, so a single PSP must exceed
`20 mV · (1 − e^(−0.893)) = 11.8 mV` to reach threshold before the membrane leaks. Therefore
**propagation is a convergence phenomenon, not a hop-count phenomenon** — the same "one hop"
takes 12 ms at pool 60, 4.4 ms at pool 111, and 2.6 ms at pool 150.

A static connectome analysis (main agent, 2026-08-18) suggests the **direct** return path may
be too thin to conduct:

| return path | convergence | summed PSP if all fire at once |
|-------------|-------------|-------------------------------|
| afferent → MN (direct, 121 syn) | median **2** afferents/MN, max 7 | median 1.32 mV, max 8.36 mV |
| afferent → interneuron (1,339 relays) | — | median 1.08 mV, **max 17.65 mV** |

Against the ~11.8 mV single-shot bar, the direct path fails even at full blast, while **6
relays clear it** — the strongest being `IN23B024` (17.65 mV), then `INXXX007`, `IN09A022`,
`IN09A016`, `IN01B007`.

**Treat those numbers as a hypothesis to test, not a finding.** Two reasons they may be
pessimistic: (a) they are *single-shot* — one synchronous volley — whereas the protocol uses
sustained 30-50 ms bursts, and temporal summation across repeated volleys can cross threshold
where one volley cannot; (b) they were computed from the weight formula in a `network.py`
comment rather than the live code path, so they are order-of-magnitude only. **Recompute them
from the actual code path** rather than trusting this table.

Deliverable: does a returning afferent volley fire *anything* downstream, and if so, name the
relay neurons it went through and the convergence at each. If nothing fires on a single volley
but sustained bursting succeeds, that is a valuable result and should be reported explicitly —
it tells Child 1 that burst duration is load-bearing rather than a detail.

Why this belongs here rather than in Child 1: if Child 1 reports "no loop closure," we could
not distinguish real biology from a return path that was merely sub-threshold. Settling it now
makes Child 1's result interpretable either way.

## Third deliverable: where do the afferents actually rest in-network?

0b measured every firing rate on **isolated** LIF neurons and explicitly flagged that it never
ran the 41 afferents inside the full VNC. The connectome says those afferents receive **642
synapses (median 15 each, all 41 receive some), of which 66% are GABAergic** — presynaptic
inhibition of sensory afferents, a real and well-documented mechanism for sensory gain control.

So the practical firing threshold in-network may differ from the isolated 200 pA rheobase, and
given the GABA fraction the network's own input may push afferents **down** rather than up.
Measure the resting current/rate of the 41 afferents with full synaptic input present, and
report whether 0b's calibrated gains still land them in the 40-100 Hz band.

This bears on an open design question — whether afferents need a **tonic bias** (a standing
current holding them near threshold, as real proprioceptors have) — but **do not implement a
bias.** Just measure where they sit. The 66% GABAergic input means the operating point is
something the network sets dynamically, and hardcoding a constant would substitute a guess for
a mechanism we already have the wiring for. Report the measurement; the decision is the user's.

## Technical notes

- Apply the 15 muscle activations via `ActuatorType.MUSCLE`. Body is
  `MusculoskeletalFly()` + `MusculoskeletalWorld(fly)` — 14 joints (LF+RF), 15 muscles (all
  LF), **no free joint** → tethered by construction. `dt = 0.1 ms`.
- **`NeuroMechFly` and `MusculoskeletalFly` are not sub/supersets of each other** — different
  joint counts, actuator transmission types (`mjTRN_JOINT` vs `mjTRN_TENDON`), and even
  different ground geom names (`ground_plane` vs `floor`). Do not assume a shared interface;
  check.
- Muscle `ctrlrange = [0.0001, 1.0]` is **unipolar** — a muscle pulls, never pushes. Existing
  `motor_gain` / `baseline_hz` were tuned for bipolar joint offsets and need retuning.
  `baseline_hz = 15` is a hard deadband: 15 Hz produces exactly zero activation.
- **Weighted sum, never mean,** for pooling motor neurons onto a muscle
  (`w_i = size_i / mean(size)` from the connectome `size` column). A mean violates the size
  principle — silent neurons would *weaken* the muscle. This bug was already found and fixed
  once (1 of 8 neurons firing drove the joint **backwards** by −0.225 rad); do not
  reintroduce it.
- **Settle ~3000 steps before measuring.**
- **Use a pool, not a single neuron.** The earlier text said pool size "does not apply here"
  because this is a conduction test. That is now wrong: 0a proved a single synapse cannot fire
  a postsynaptic cell at any rate, so single-neuron drive tests a configuration that cannot
  propagate even in principle. Child 1 onward uses ~4-neuron pools at ~80 Hz; stay consistent
  with that unless you find a reason not to, and report the pool size with every latency.
- Use the gain values Child 0b established. Do not re-derive them.
- Timings will include Child 0a's synaptic delays, so the elapsed time here is directly
  comparable to the 20 ms STDP window — unlike every previous measurement.

## Reference measurements

### Physics (still valid)

Force rises in **0.2 ms** at every activation level; joint movement takes **3.2-15.5 ms**.
The lag is inertial (joint mass + damping 0.02 + stiffness 0.4), not charge accumulation.
Measured on `LFTibia_flex_93434`:

| activation | 0.05 | 0.10 | 0.20 | 0.40 | 0.70 | 1.00 |
|------------|------|------|------|------|------|------|
| t_move (ms) | 15.5 | 10.4 | 7.2 | 5.0 | 3.8 | 3.2 |

Rate → activation (16-neuron pool): 15 Hz → 0.000 (`baseline_hz = 15` is a hard deadband),
30 Hz → 0.081, 50 → 0.189, 80 → 0.351, 200 → 1.000.

### The old round-trip table is retired — do not use it

The previous version of this issue carried a `recruited × firing-rate → round-trip` table.
**It is withdrawn for two independent reasons**, both discovered after it was written:

1. **Its neural term was a flat 2 ms estimate.** 0a showed neural latency is a function of
   *convergence*, not hop count (12 ms at pool 60, 4.4 ms at pool 111, 2.6 ms at pool 150), so
   a single constant cannot stand in for it. Any "2-4 / 5-8 ms" figure is meaningless without
   stating the pool size.
2. **Its physics term measured the wrong event.** `t_move` is the time until the joint *starts*
   to move, but an afferent spikes only once movement is large or fast enough. These are
   different events separated by an unknown gap, so the two halves never chained. Every margin
   in that table was optimistic by an unmeasured amount.

**Regenerating it correctly is part of this issue.** The replacement should be indexed by
*convergent pool size* and report *time-to-first-afferent-spike per modality* — not `t_move`.

### Calibrated sensory gains (from 0b — use, do not re-derive)

`position 700, velocity 1200, force 1400, posture 2000` pA; `max_velocity = 25.0`,
`max_force = 150.0`. Rheobase measured at 200 pA (200 → 0.0 Hz, 201 → 18 Hz).

Three things 0b corrected that this issue depends on:

- **Position is now referenced to measured `SETTLED_LF_ANGLES`, not MJCF `springref`.**
  Referenced to `springref` the channel was **non-monotonic** (0.384 → 0.001 → 0.424 as the
  tibia swept through), emitting the same current at two different postures.
- **The old "ground reaction force" channel was a constant 116.2, not zero** — it summed any
  LF-involving contact, capturing Thorax↔Coxa interpenetration. Non-zero but unmodulated, so it
  looked alive while carrying no information. Now reads tendon tension (`d.actuator_force`):
  1.373 at rest → 76.7 under drive.
- **Position is unsigned.** Flexion +0.778 rad and extension −0.769 rad both produce exactly
  152 Hz — genuinely indistinguishable. Accepted for Level 1; blocks Level 2 agonist/antagonist
  work. Do not fix here.

### Neural model (from 0a — already in place)

Per-synapse delay 0.8-1.5 ms (seeded), wired into all six connectome-synapse sites and the GPU
path; measured +1.20 ms direct / +2.40 ms via one interneuron, identical on Brian2 and PyGeNN.
STDP soft-bounding active with `w_max` = 3.56 mV excitatory / 1.66 mV inhibitory.

**77 full-VNC synapses start above their own `w_max`** — real connectome outliers, not STDP
growth. They cannot grow and depress normally. Relevant if anything reports "synapses at the
ceiling."

## Scope

Test only the **52 of 64** LF motor neurons with a live DOF. Excludes 6 tarsus (FlyMimic
welds all 5 tarsus segments — no joint to move even in principle) and 6 long-tendon `ltm*`
(pooled into single-joint muscles, defeating their multi-joint function). Counting these 12
would measure FlyMimic's limitations rather than connectome biology. See
`docs/neuroscience/13-motor-neuron-muscle-mapping.md` §6.1.
