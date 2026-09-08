# Idea: Sensorimotor Babbling for Developmental Loop Closure

**Status:** Exploring — Level 1 conduction resolved 2026-08-18 (see Resolution)
**Date:** 2026-08-17
**Motivation:** Reward-modulated STDP on the locomotor circuit doesn't produce behavior — it must simultaneously discover which pathways move the body AND coordinate them for locomotion

## The Problem

Current training asks the network to solve two problems at once:
1. Discover which connections correspond to real physical movements
2. Coordinate those movements into forward locomotion

Evidence this is too much:
- Full VNC + DNa02 stimulation → negative displacement (wiring present, weights untuned)
- Homeostatic plasticity fights STDP (performance declines across episodes)
- Only the small 6-hop subnet learned at all, and weakly

Biology separates these. Fetal motor development runs a **pre-goal phase**: random
twitches where the body's own physics teaches which motor command causes which sensation.
No reward, no supervision — the body is the teacher.

## Proposed Approach

**Three levels of loop closure, tested in order** (full concept in
`docs/neuroscience/12-sensorimotor-babbling.md`):

| Level | Loop origin | Question | Status |
|-------|-------------|----------|--------|
| **1** | motor neuron | which motor neuron controls which joint | **active** |
| 2 | intrinsic interneuron | which interneuron patterns produce which movements (CPG) | not started |
| 3 | descending neuron | which brain commands produce which whole-body sensations | not started |

Level 3 is the full arc — brain command → motor → body → sensory → back to the command
neuron. Level 1 is first because **its failure is the only interpretable one**: if a signal
cannot complete the shortest loop (one motor neuron, one joint, direct return), the longer
loops cannot work either. A Level 3 failure would leave us unable to distinguish a wrong
hypothesis from a circuit that is merely too deep.

*Constraint on Level 3:* the brain is not in our dataset (`cb_intrinsic` = 4 neurons). We
have the descending and ascending bundles at the VNC boundary but nothing computing between
them, so "back to the brain" can only mean "back to the descending neuron that issued the
command."

### Level 1 (what is being built now)

Pure two-factor STDP (no reward modulation) during random single-motor-neuron bursts on
the Left Front leg, using FlyMimic's Hill-type muscles as the body.

```
Motor neuron bursts (30-50ms)
  → muscle contracts (Hill-type)
  → joint moves (MuJoCo)
  → proprioceptive afferents fire (current injection)
  → return via direct synapse or 1 local interneuron
  → does the signal reach neurons presynaptic to the origin?
```

Then Phase 2 (existing reward-modulated STDP) optimizes over the established map rather
than discovering one from scratch.

**Phase 2 is deferred out of the Level 1 epic.** Babbling runs on tethered FlyMimic (LF
only, thorax pinned); locomotion requires NeuroMechFly (6 legs, free-floating). Tuning 1/6
of the circuit and then measuring whole-body displacement would make a null result
uninterpretable. Locomotion transfer becomes its own epic once Levels 1-2 land.

## Expected Outcome

Closed loops strengthen, open pathways don't. Subsequent goal-directed training converges
faster on a babbling-pretrained network.

## Trade-offs

- **LF leg only.** FlyMimic has muscles for one leg, so this validates the mechanism, not
  whole-body coordination.
- **Tethered.** No ground contact, so no load feedback — a real channel of proprioception
  is simply absent.
- **Slow to falsify.** If loop closure isn't detected we've spent the harness build to
  learn it.

## Execution Context

- **Network:** full VNC (25,635 neurons, 4.1M synapses) — **not** the 6-hop subnet.
  Only 2.7% (20/736) of the sensory→motor relay interneurons are in the 6-hop net, so
  that subnet cannot express the reflex loop. The 6-hop path is retired.
- **Body:** `MusculoskeletalFly()` + `MusculoskeletalWorld(fly)`. 15 muscle actuators
  (all LF), 14 joints (LF+RF), **no free joint** → tethered by construction.
  `dt = 0.1 ms`.
- **Motor scope:** 52 of 64 LF motor neurons. Excludes 6 tarsus (`Ta depressor/levator` —
  FlyMimic welds all 5 tarsus segments, no joint to move) and 6 `ltm*` long-tendon
  (multi-joint action collapsed into single-joint muscles).
- **Sensory scope:** 41 of 45 left-side ProLN afferents. Filter is
  `entryNerve == "ProLN"` + `class == "mechanosensory_proprioceptive"` + `rootSide == "L"`.
  Excludes 4 `SApp23` (ascending, zero motor connections).
- **Constraint — laterality is `rootSide`, not `somaSide`.** `somaSide` is NaN for all 65
  afferents (somata sit in the leg periphery). Using both sides would encode right-leg
  afferents from left-leg joint angles.
- **Decision — current injection, never Poisson spike generation.** Poisson destroys the
  precise spike timing STDP depends on, which is the entire mechanism under test.
- **Decision — sustained 30-50 ms bursts, not 5 ms pulses.** See anti-causality below.
- **Decision — weighted-sum muscle activation, never mean.** `w_i = size_i / mean(size)`
  from the connectome `size` column. A mean violates the size principle: silent neurons
  would weaken the muscle.
- **Settling requires ~3000 steps.** At 500 steps the tibia is still drifting at
  −4 rad/s. Measuring from an unsettled leg contaminates the baseline.

## Intermediate Findings

- 2026-08-17: **Loop closure is structurally present.** 134 direct monosynaptic
  sensory→motor synapses (22 afferents onto 46 of 64 motor neurons), plus 19,565 one-hop
  paths through 736 local interneurons reaching all 64. Key relays: IN21A004, IN13A006,
  IN19A005. → The loop exists in wiring; the question is whether STDP can detect it.

- 2026-08-17: **Sensory types are joint-specific.** SNpp39 sends 100% of its direct motor
  output to tibia motors; SNpp53 (campaniform sensilla) 78% to trochanter; SNppxx 59% to
  tibia. SNpp51 is broad (29/30/41% across tibia/troch/coxa). → Joint-specific encoding is
  justified by measured connectivity, not assumed.

- 2026-08-17: **STDP anti-causality is the sharpest trap.** Motor fires at t=0, sensory
  returns at t≈10ms → post-before-pre by 10ms → standard asymmetric STDP *depresses* the
  correct reflex arc. Naive babbling would systematically weaken exactly what it should
  strengthen, and would look like "no loop closure detected" rather than a sign error.
  Fix: sustained bursts so later motor spikes follow the sensory spike.

- 2026-08-17: **Latency is inertial, not accumulative.** Tendon force rises in **0.2 ms**
  at every activation level; joint movement takes **3.2-15.5 ms**. The lag is joint mass +
  damping (0.02) + stiffness (0.4), not charge building up.

- 2026-08-17: **There is a firing-rate floor for loop closure** (see scale analysis below).
  Below ~30 Hz with full recruitment the joint moves too slowly for feedback to return
  inside the 20 ms STDP window. This is a second false-negative trap: weak drive produces
  *no detectable loop*, not merely a small one.

- 2026-08-17: **The load channel is dead in the tethered world.** Tarsus tip clears the
  floor by 0.97 (lowest points are actually the *hind* tarsi). The only contacts are
  Thorax↔Coxa self-collisions with negative `dist` (interpenetration, ~39-42 N repulsion) —
  not weight-bearing. The 2 SNpp53 afferents need `d.actuator_force` (tendon tension,
  which is what campaniform sensilla actually sense) instead of ground reaction force.

## Scale Analysis: the babbling drive window

Round-trip (ms) = measured `t_move` + 2 ms neural estimate. `--` = no closure within the
20 ms STDP window. Measured on `LFTibia_flex_93434` (16-neuron pool):

| recruited | 30 Hz | 50 Hz | 80 Hz | 120 Hz | 200 Hz |
|-----------|-------|-------|-------|--------|--------|
| 1/16  | -- | -- | -- | -- | 13.8 |
| 2/16  | -- | -- | 14.6 | 11.5 | 8.9 |
| 4/16  | -- | 15.6 | 11.5 | 9.1 | 7.4 |
| 8/16  | -- | 12.0 | 9.1 | 7.7 | 6.2 |
| 12/16 | 16.1 | 10.8 | 8.3 | 6.8 | 5.6 |
| 16/16 | 14.3 | 9.5 | 7.5 | 6.3 | 5.2 |

**Implication for the protocol:** the loop only closes in the upper-right region. Single-
neuron babbling needs ~200 Hz to close at all; at 50 Hz it needs ≥4 neurons co-firing.

This is a **problem for the Level 1 premise**, which assumes stimulating *one* motor neuron
produces detectable feedback. One neuron at 200 Hz closes with 6 ms of margin — viable but
tight, and it depends on the 2 ms neural term being right.

Supporting measurements:

| activation | t_move (ms) | | rate (all 16) | activation |
|-----------|-------------|---|---------------|------------|
| 0.05 | 15.5 | | 15 Hz | 0.000 |
| 0.10 | 10.4 | | 20 Hz | 0.027 |
| 0.20 | 7.2  | | 30 Hz | 0.081 |
| 0.40 | 5.0  | | 50 Hz | 0.189 |
| 0.70 | 3.8  | | 80 Hz | 0.351 |
| 1.00 | 3.2  | | 200 Hz | 1.000 |

`baseline_hz = 15` is a hard deadband — 15 Hz produces exactly zero activation.

## Sensory Calibration — the open half

The motor side is calibrated (table above). The sensory side is not, and the arithmetic
already exposes a blocking defect.

**LIF rheobase is 200 pA** — `V_th - V_rest = 20 mV` over `R_membrane = 100 MΩ`. Below that
a neuron never fires regardless of duration. `ProprioceptiveEncoder` defaults to
`gain_pa = 75.0`, so its maximum possible output (activation = 1.0) is **0.38× rheobase**:
**no afferent can spike as configured.** The demo's "60.68 pA" figures are sub-threshold
currents, not firing rates. The old `SensoryEncoder` used **500 pA**
(`loop.py: sensory_gain=500e-12`); the new default came from doc 14's "50-100 pA" note,
which was never checked against rheobase.

Gain vs. movement required to spike (position channel, tibia half-range 1.0115 rad), and
whether measured muscle drive can produce it:

| gain | movement to spike | reachable by muscle activation |
|------|-------------------|-------------------------------|
| 75 pA | impossible (needs activation 2.67) | never |
| 300 pA | 0.674 rad | only at act ≥ 1.00 |
| 500 pA | 0.405 rad | act ≥ 0.40 |
| 800 pA | 0.253 rad | act ≥ 0.40 |
| 1000 pA | 0.202 rad | act ≥ 0.20 |

Current → firing rate above rheobase (analytic LIF, no noise):
220 pA → 38 Hz · 250 → 55 · 300 → 77 · 400 → 112 · 500 → 141 · 800 → 205.

**Experiment to run:** sweep `gain_pa` per modality × joint displacement, measuring actual
afferent firing on real LIF neurons. Deliverables: (a) a per-modality gain table landing
afferents in ~40-100 Hz, (b) minimum detectable movement — the sensory analogue of the
motor firing-rate floor.

Design questions it should settle:
1. Per-modality gains instead of one shared `gain_pa`? Position rests near 0 while force
   would sit tonically high — one gain cannot serve both.
2. Is `max_velocity = 25.0` the right scale? At 500 pA the velocity channel needs 10 rad/s;
   measured peak tibia velocity was ~21 rad/s — reachable, but only transiently.
3. Does the position channel's unsigned `|angle - rest|` lose information STDP needs?
   Flexion and extension currently produce identical current.

## Open Risks

1. **Neural delay was underestimated — revised to 2-4 ms direct, 5-8 ms via one
   interneuron** (~0.8-1.5 ms synaptic transmission + ~1-4 ms membrane integration per hop).
   The scale table above assumes 2 ms, so **its upper-right cells shrink**: at 6 ms, single-
   neuron/200 Hz becomes 19.8 ms — flush against the window. **And our network has no
   synaptic delay at all** (`network.py`: `on_pre="v_post += w"`), so measured round-trips
   will be optimistic by 1-3 ms per hop until per-synapse `delay` is added.
2. **Single-neuron babbling abandoned in favour of ~4-neuron pools at ~80 Hz** (11.5 ms
   physics → ~17.5 ms closure with margin). This is a correction *toward* biology — fetal
   twitches recruit synergies, not single cells — but it means Level 1 tests pool-level
   rather than cell-level credit assignment.
3. **STDP has no upper weight bound.** `functional_training.py` enforces only Dale's
   principle; magnitude is uncapped. A 30-50 ms burst pairs pre/post many times per episode,
   and with no reward term to oppose it, additive STDP will run away. Needs soft-bounding
   (`Δw ∝ (w_max − w)`) — a hard clip would pin synapses at `w_max` and destroy the graded
   differences Child 2 measures.
3. **Muscles are not yet driving physics.** `functional_training` builds `NeuroMechFly`
   (66 position servos), so `muscle_activations()` is computed but inert.
4. **SNpp51 cross-contamination.** It targets all three joint groups; specificity is
   assumed to come from timing alone. Untested.
5. ~~**Sensory gain is below rheobase**~~ — **RESOLVED 2026-08-17 (Child 0b).** Calibrated
   per-modality on measured LIF spike counts: position 700 pA, velocity 1200 pA, force
   1400 pA, posture 2000 pA. Rheobase confirmed at 200 pA (200 → 0.0 Hz, 201 → 18 Hz).
6. **The two floors overlap, but only through the velocity channel.** Measured: inside a
   50 ms burst the velocity channel fires from muscle activation 0.20 (20 Hz) and reaches
   60 Hz by 0.30, while the position channel emits its first in-burst spike only at 0.60 —
   displacement has to integrate before it crosses threshold, whereas velocity peaks at
   ~25 ms. The motor floor is activation 0.189 (≈50 Hz). So a single babbling drive at
   activation ≳0.2-0.3 satisfies both, **via velocity**. A protocol leaning on position
   for within-burst feedback needs ≥0.60 or a longer burst.

## Sensory Calibration — RESOLVED (Child 0b, 2026-08-17)

Reproduce: `python -m digital_drosophila loop sensory_calibration`

- **Per-modality gains are required**, not one shared value: the in-band gains span 2.9x
  (700-2000 pA). At a shared 700 pA the force and posture channels are silent.
- **Calibrate at the activation physics reaches, not at 1.0.** Only tibia position ever
  approaches activation 1.0; the others top out at 0.30-0.66 under the strongest
  single-muscle drive.
- **`max_velocity = 25.0` is right.** Peak single-joint speed measured 22.1 rad/s = 0.89 of
  full scale — no clipping, little waste. Lowering it would clip the strongest drivers.
- **Minimum detectable movement** at 700 pA: 0.356 rad (muscle activation 0.40) held, or
  0.506 rad (activation 0.60) counted within the burst.
- **The unsigned position channel is direction-blind** and measurably so: +0.778 rad
  flexion and −0.769 rad extension both give 152 Hz. Acceptable for Level 1, must be fixed
  for Level 2 agonist/antagonist credit assignment. Not fixed.
- **The position reference was wrong**, separately from the gain: MJCF `springref` is not
  the settled posture, and referencing it made activation *non-monotonic* (0.384 → 0.001 →
  0.424 as the tibia passes through springref). Now referenced to `SETTLED_LF_ANGLES`.
- **The force channel now reads tendon tension.** True LF↔floor ground reaction is exactly
  0.0000; the ~116 the old code read was constant Thorax↔Coxa interpenetration — not merely
  zero but *unmodulated*, carrying no information. Tendon load is 0.68/1.37/4.88 at rest
  (coxa/troch/tibia) and 15-336 under drive. It is **tonic but weak (activation
  0.005-0.033)**, staying sub-rheobase at rest — so the earlier "tonic 0.66, fires
  continuously, hurts STDP eligibility" concern does not apply.

## Resolution — Level 1 (2026-08-18)

**The loop conducts. It cannot answer Level 1's question.**

Multi-joint drive (coxa + trochanter + tibia, 3 muscles) fires all 41 afferents and wakes 7
neurons presynaptic to in-scope LF motor neurons. Single-muscle drive fires nothing in 8 of 8
conditions, despite the same motor rate and *larger* single-joint excursions — so the missing
variable was **afferent recruitment breadth**, not drive strength, latency, or gain. The
frozen-physics control is clean (0 afferent spikes with the leg immobilised), so the signal
travels through the body and not via the 34 motor->X->afferent shortcut paths.

Two measured properties nonetheless disqualify it (a third, timing, was withdrawn):

1. **Broadcast return path.** `IN21A004` contacts 46 of 64 LF motor neurons (72%). "Returned
   to a neuron presynaptic to the origin" is then near-guaranteed by anatomy for any origin,
   so Child 2 may have no meaningful control set.
2. **Inhibitory return.** `IN13A006` -18.24 mV (GABA), `IN21A006` -13.86 (glutamate),
   `IN13A002` -12.76 (GABA) against `IN21A004` +33.17. The loop diagram assumed excitation.
3. ~~Outside the plasticity window.~~ **Withdrawn 2026-08-18.** Closure at 35-49 ms was
   presented as too slow for a "20 ms STDP window", but `tau_stdp_ms = 20` sets eligibility
   *magnitude*, while `tau_eligibility_s = 1.0` (**1000 ms**) carries the credit. 35-49 ms is
   ~5% of that. Timing was never the barrier.

So the *physical* question (does a signal return?) is answered yes; the *scientific* question
(which motor neuron controls which joint?) is not answerable here — feedback reports that the
leg moved, not which muscle moved it.

**The hypothesis this idea was built on is not disproved — it is relocated.** Body-mediated
temporal correlation does happen; it just carries whole-leg rather than per-muscle information.
Level 2 (interneuron origin) is the better test, since "which interneuron *pattern* produces
which movement" is a question a broadcast return path can answer.

- **Lab entries:** [multi-muscle loop closure](../lab/2026-08-18-multi-muscle-loop-closure.md)
  · [single-muscle return limb fails](../lab/2026-08-18-babbling-child0-return-limb-fails.md)

## Related Documents

- `docs/neuroscience/12-sensorimotor-babbling.md` — the three-level concept
- `docs/neuroscience/13-motor-neuron-muscle-mapping.md` — motor→muscle→joint, §6.1 scope
- `docs/neuroscience/14-sensory-motor-loop-structure.md` — the measured return path
- `docs/issues/2026-08-17-sensorimotor-babbling-level1.md` — the Level 1 epic
