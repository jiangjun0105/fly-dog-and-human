# Epic: Sensorimotor Babbling — Level 1 (Motor Neuron Loop Closure)

**Date:** 2026-08-17
**Status:** in progress
**Type:** epic
**Motivation:** Test whether closed sensorimotor loops exist in the VNC connectome and whether pure STDP can strengthen them through body-mediated temporal correlation.

EPIC — container issue, do not execute; work lives in child issues.

## Problem

Our current training (reward-modulated STDP) asks the network to simultaneously discover which pathways correspond to real body movements AND coordinate those movements for locomotion. Evidence this is too hard:
- Full VNC with DNa02 stimulation produces negative displacement (untuned weights)
- Homeostatic plasticity fights STDP (performance declines over training)
- Only a small subnet (6-hop, 648 neurons) learns at all

Biological nervous systems solve this with a developmental phase: random motor babbling where the body's physics provides the teaching signal through temporal loop closure, before any goal-directed learning.

## Desired Outcome

Determine whether the VNC connectome contains functional sensorimotor loops that can be detected and strengthened through pure (non-reward-modulated) STDP, using the physics simulation as the body.

Specifically for Level 1 (motor neuron level):
1. **Conduct:** Does the chain physically work — motor neuron → muscle → joint → afferent spike?
2. **Detect:** Does the feedback return to neurons presynaptic to the origin, within 20 ms?
3. **Strengthen:** Does pure STDP during babbling preferentially strengthen closed loops over
   open pathways?

"Does it improve locomotion" was originally a fourth goal; it is deferred to its own epic
(see Child 3) because it cannot be measured on the tethered body babbling requires.

### This is Level 1 of 3

`docs/neuroscience/12-sensorimotor-babbling.md` defines three levels of loop closure:

| Level | Loop origin | Question |
|-------|-------------|----------|
| **1 (this epic)** | motor neuron | which motor neuron controls which joint |
| 2 | intrinsic interneuron | which interneuron patterns produce which movements (CPG) |
| 3 | descending neuron | which brain commands produce which whole-body sensations |

**Level 1 is first because its failure is the only interpretable one.** If a signal cannot
complete the shortest possible loop — one motor neuron, one joint, direct return — then
Levels 2 and 3 cannot work either. A Level 3 failure would be ambiguous: wrong hypothesis,
or merely too deep a circuit?

**Constraint on Level 3:** the brain is not in our dataset. `cb_intrinsic` has 4 neurons;
we have `descending_neuron` (1,305, brain output arriving) and `ascending_neuron` (1,843,
VNC output departing) but nothing that computes in between. "Back to the brain" can only
mean "back to the descending neuron that issued the command."

### The loop being tested

```
Motor neuron M fires (injected current, 30-50ms sustained burst)
    → joint J moves (MuJoCo physics, ~1-5ms)
    → sensory neuron S fires (local ProLN proprioceptive encoding)
    → direct, or via 1 local T1 interneuron (~1-2ms)
    → does signal reach neurons presynaptic to M? (loop closure)
```

Expected round-trip: 7-14 ms (within 20ms STDP window).

**The burst must be sustained, not a 5 ms pulse.** See
`docs/neuroscience/13-motor-neuron-muscle-mapping.md` §8.1 — a brief pulse
fires M entirely *before* feedback returns, so asymmetric STDP would
depress the correct reflex arcs and Child 1 would report a false negative.

## Capabilities (child issues)

> **Revised 2026-08-17** after building the transducers and measuring loop latency.
> The original Child 1-3 text was written before we had those numbers and specified a
> 5 ms pulse, a single physics timestep, and sensory *spike* injection — all three are
> now known to be wrong. Child 0 is new: it exists because two blockers currently make
> any loop measurement meaningless.

### Child 0: Mechanical Loop Closure — does the chain conduct at all?

**Demo:** Drive one LF muscle in the spiking network; show that a named proprioceptive
afferent spikes as a consequence, with the elapsed time printed.

No statistics, no STDP, no loop-back — just proof the chain physically conducts. This is
the walking skeleton: every seam (network → muscle → physics → afferent → spike) exercised
once, end to end.

**Split into three issues (2026-08-17)** — it grew to six items spanning the neural model,
the sensory encoder, and the physics harness. 0a and 0b are disjoint in files and run in
parallel; 0c depends on both.

| | scope | depends on |
|---|-------|------------|
| [**0a** — neural model](2026-08-17-babbling-child0a-neural-model.md) | per-synapse transmission delay; STDP soft-bounding | — |
| [**0b** — sensory calibration](2026-08-17-babbling-child0b-sensory-calibration.md) | gain sweep on real LIF neurons; SNpp53 → tendon force | — |
| [**0c** — wire the body](2026-08-17-babbling-child0c-wire-body.md) | `MusculoskeletalFly` into harness; retune `motor_gain`; run the exit-gate demo | 0a, 0b |

0a must land **before** 0c measures anything: without synaptic delays every round-trip is
optimistic by 1-3 ms per hop, and the exit-gate number is meaningless as a comparison
against the 20 ms window. 0c needs 0b's gain table because at the shipped 75 pA no afferent
can spike at all.

**Exit gate (0c):** if no afferent can be made to spike from motor stimulation, Level 1 is
blocked and Children 1-2 cannot be interpreted.

### Child 1: Loop Detection — does the signal return to origin?

**Demo:** For each of N tested motor neurons, show whether sensory feedback reaches a
neuron presynaptic to that motor neuron within 20 ms, as a loop-closure table with
measured timings.

- Stimulate a **pool of ~4 motor neurons at ~80 Hz** with a **sustained 30-50 ms burst**
  (not a single neuron, not a pulse). Rationale: a single neuron closes the loop only at
  ~200 Hz → 13.8 ms physics + ~6 ms realistic neural delay = 19.8 ms, flush against the
  window. A 4-neuron pool at 80 Hz moves the joint in 11.5 ms → closes ~17.5 ms. Pools are
  also the biologically faithful unit — fetal twitches recruit synergies, not single cells.
- Run physics **~50-150 steps** per measurement window (`dt = 0.1 ms`; joint movement
  takes 3-15 ms, so a single timestep shows nothing)
- Encode joint state as sensory **current** (not spikes — Poisson generation destroys the
  spike timing STDP depends on)
- Run the network forward 20 ms, record spike propagation
- Measure: which interneurons fire, and do any synapse back onto M?
- Repeat across the **52 testable** motor neurons (see Scope); report per-neuron

**Known structural baseline** (from `14-sensory-motor-loop-structure.md`): 134 direct
monosynaptic sensory→motor synapses and 19,565 one-hop paths via 736 interneurons already
exist in the connectome. Child 1 tests whether that wiring *conducts a timed signal*, not
whether it exists.

### Child 2: Babbling Training — does pure STDP strengthen closed loops?

**Demo:** After N babbling episodes, show that weights on the closed-loop pathways
identified in Child 1 increased relative to matched control pathways.

- Random motor neuron drawn from the 52, sustained burst, physics, sensory feedback, repeat
- **Pure two-factor STDP, no reward modulation**
- Track weights on Child 1's confirmed loop pathways vs control pathways
- 50-200 episodes
- Measure: loop vs non-loop weight change; does per-neuron specificity emerge, or does
  everything strengthen indiscriminately?
- **Watch the anti-causality sign.** If loop weights systematically *decrease*, suspect the
  burst is too short before concluding the hypothesis failed.

### Child 3: Motor Control Improvement — moved out of this epic

**Deferred.** Originally "run reward-modulated training, measure displacement vs a fresh
network." That cannot be evaluated here: babbling runs on **tethered FlyMimic** (LF only,
thorax pinned, no ground contact) while displacement requires **NeuroMechFly** (6 legs,
free-floating). Weights transfer — same VNC — but babbling would tune only LF-related
synapses and we would then test whole-body locomotion. A null result would be
uninterpretable: did babbling not help, or did we tune 1/6th of the circuit and measure all
of it?

Locomotion transfer becomes its own epic once Levels 1-2 land. This epic answers the
scientific question — *does body-mediated STDP strengthen real sensorimotor loops* — which
is fully answerable on the tethered body.

## Dependencies

```
Child 0a (neural model) ─┐
                         ├→ Child 0c (wire body, exit gate) → Child 1 (detection) → Child 2 (babbling)
Child 0b (sensory gain) ─┘
```

Child 0 is a hard prerequisite: until muscles drive physics and afferents can spike, both
later children would measure plumbing failures rather than biology. Child 1 then gates
Child 2 — if no loop closure is detectable at all, the hypothesis is falsified and we stop.

## Risks

1. **No loop closure detected:** The VNC may be too densely connected — everything propagates everywhere within 20ms, making timing-based discrimination impossible.
2. **STDP too slow:** 4.1M synapses may need thousands of babbling episodes to show measurable weight changes.
3. **Physics latency — RESOLVED, fits the window.** `dt = 0.1 ms`, and joint movement takes
   3.2-15.5 ms depending on activation (tendon force rises in 0.2 ms; the lag is inertial).
   Round-trip = 5.2-16.1 ms including a 2 ms neural estimate. **But it only fits above a
   firing-rate floor** — below ~30 Hz at full recruitment the loop does not close in 20 ms.
4. **Single-neuron babbling abandoned — now motor pools.** Resolved by switching to ~4-neuron
   pools at ~80 Hz (see Child 1). Level 1 therefore tests **pool-level**, not cell-level,
   credit assignment; cell-level specificity moves to Level 2.
5. **The neural delay was underestimated — now 2-4 ms direct, 5-8 ms via one interneuron.**
   Per-synapse transmission is ~0.8-1.5 ms plus ~1-4 ms membrane integration to threshold.
   **Worse: our network has no synaptic delay at all** — `network.py` uses
   `on_pre="v_post += w"` (instantaneous). Child 0 must add per-synapse `delay` or every
   measured round-trip will be optimistic by 1-3 ms per hop.
6. **STDP has no upper weight bound.** `functional_training.py` enforces only Dale's
   principle (excitatory ≥ 0, inhibitory ≤ 0); magnitude is uncapped. Sustained 30-50 ms
   bursts pair pre/post many times per episode, so additive STDP will run away with no reward
   term to oppose it. Needs soft-bounding (`Δw ∝ (w_max − w)`) before Child 2 — prefer soft
   over a hard clip, since clipping pins synapses at exactly `w_max` and destroys the graded
   differences Child 2 measures.
6. **Sensory gain is below rheobase** (75 pA vs 200 pA required). Blocks everything until
   Child 0 fixes it. Note the 200 pA figure assumes an isolated neuron — synaptic input and
   background noise may lower the practical floor, which is why it needs measuring rather
   than deriving.
7. **The two floors may not overlap.** Motor needs ≥30 Hz for a timely return; sensory needs
   ~0.4 rad of movement at 500 pA to fire at all. Both are individually satisfiable; whether
   one babbling drive satisfies both simultaneously is the core viability question.
8. **Sensory encoding too sparse:** only 41 afferents encode the leg, and 2 of those (SNpp53)
   are on a channel that is dead until switched to tendon force.

## Scope: which motor neurons are testable

**Test only the 52 of 64 LF motor neurons that have a live DOF.** Exclude:
- **6 tarsus** (`Ta depressor MN` ×4, `Ta levator MN` ×2) — FlyMimic welds
  all 5 tarsus segments, so these have no joint to move even in principle
- **6 long tendon** (`ltm MN`, `ltm1-tibia MN`, `ltm2-femur MN`) — pooled
  into single-joint muscles, which defeats their multi-joint function

See `docs/neuroscience/13-motor-neuron-muscle-mapping.md` §6.1. Counting
these 12 would measure FlyMimic's limitations, not connectome biology.

## Success Criteria

- [ ] **Child 0:** driving one LF muscle causes a named afferent to spike, with measured
      elapsed time — the chain physically conducts end to end
- [ ] **Child 1:** loop closure detected for ≥50% of the **52 testable** motor neurons
      (signal returns to a presynaptic partner of the origin within 20 ms)
- [ ] **Child 2:** closed-loop pathway weights increase by ≥10% relative to matched control
      pathways after babbling

Displacement is deliberately **not** a criterion here — see Child 3. This epic tests loop
closure and its strengthening, not locomotion.
