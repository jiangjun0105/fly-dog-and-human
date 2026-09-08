# The Loop Closes — But Only With Multi-Joint Movement, and It Broadcasts

**Date:** 2026-08-18
**Experiment:** Follow-up to the Child 0 exit-gate failure — test whether driving muscles
across several joint groups recruits enough afferent breadth to fire the return limb

## Summary

**The sensorimotor loop conducts.** Driving three muscles spanning coxa + trochanter + tibia
fires all 41 LF afferents, delivers the full 15.56 mV to relay `IN23B024`, and wakes **7
neurons presynaptic to in-scope LF motor neurons**. Single-muscle drive fires nothing, in 8 of
8 conditions.

The predicted mechanism was right: the bottleneck was **afferent recruitment breadth**, not
drive strength, latency, or gain.

**But the loop cannot do the job Level 1 wanted it for.** Three properties, all measured,
disqualify it from teaching *which motor neuron controls which joint*:

1. The return path is a **broadcast** — its strongest excitatory relay contacts 72% of all LF
   motor neurons. **This is the disqualifying one.**
2. It returns mostly as **inhibition**, not excitation

A third property — closure at **35-49 ms** — was originally listed here as disqualifying
("outside the 20 ms STDP window"). **That was wrong; see the correction below.** Our eligibility
trace is 1000 ms, so 35-49 ms is ~5% of its lifetime and well within reach.

## What We Did

Extended the `body_wiring.py` harness to sweep multi-muscle drive combinations, measuring
whether any neuron presynaptic to an in-scope LF motor neuron spikes — the actual definition of
loop closure.

Reproduce: `python -m digital_drosophila check multi_muscle` (`--quick` for 50 ms only).
Full VNC (25,635 neurons / 4,114,854 synapses), network and physics in lockstep at
`dt = 0.1 ms`, 3000-step settle, `data.act` restored between conditions.

Every verdict below is a `SpikeMonitor` count. Membrane-voltage figures are context only.

## What We Observed

### Breadth was the missing variable

| condition | mV to strongest relay | conditions that closed |
|-----------|----------------------|------------------------|
| 1 joint group | 7.46 | **0** |
| 2 joint groups | 12.09 | 1 |
| 3 joint groups | **15.56** | **7** |

Overall: **14 of 22** multi-muscle conditions closed; **0 of 8** single-muscle conditions did,
including 0c's tibia-flexor reference at both 50 and 200 ms.

**The controls are what make this convincing.** Single-muscle conditions reached the same motor
firing rate and produced *larger* single-joint excursions than the winning set (1.43 rad on the
trochanter vs 1.45 rad for the 3-group combination) — and still fired nothing downstream. The
difference is not how far the leg moved or how hard it was driven. It is **how many different
joints moved at once.**

Best condition — `3group:strongest x3` (coxa promotor_b + STT-trochanter extensor_b + tibia
extensor), 200 Hz, 200 ms burst:

- **41 of 41 afferents fire** (single-muscle best: 22)
- **15.56 of 15.56 mV** to `IN23B024` — all 16 of its afferent inputs fired
- **7 closers spiked**, first at 35.5 ms: `IN21A004`, `IN13A006`, `IN21A006`, `IN13A002`,
  `IN23B024`, `AN04B001`, and `Tergotr. MN` (an in-scope LF MN reached monosynaptically)

### The frozen-physics control is clean — the signal really travels through the body

Stimulating the motor pools with physics frozen produced **0 afferent spikes across all 30
frozen conditions**, while the motor pools themselves fired 20-2080 spikes each. Afferent
current stayed constant at a maximum of 12.8 pA, far below the 200 pA rheobase.

This closes the ambiguity left open by 0c. There are 34 relay neurons forming
motor→X→afferent paths reaching 27 of 41 afferents, and the encoder parks afferents near
threshold, so a neural shortcut could in principle have supplied the final few mV. **It does
not.** Every afferent spike is attributable to the body having moved.

Causal ordering also holds: first afferent spike 4.7-10.3 ms, first closure 35.5-48.9 ms, lag
+28.9 to +42.3 ms, **0 inversions**.

### Antagonist co-activation cancels

Breadth must be spread *across* groups, never piled onto one. Driving all 7 coxa muscles
together yields **0.37×** the excursion of the single strongest coxa muscle and fires *fewer*
afferents (9 vs 12). Trochanter 0.61×, tibia 0.78×.

Consequence: `broad: all 15 muscles` performs **worse** than the 3-muscle set. Muscles are
unipolar (a muscle pulls, never pushes), so co-activating opposing muscles fights itself.

Deliberately targeting `IN23B024`'s specific afferent inputs from the connectome worked, but
was **not better** than the naive 3-group set — same 15.56 mV, fewer closers, because the
greedily chosen muscles are weaker movers. Anatomical targeting lost to mechanical strength.

### The return path is a broadcast — this is the finding that matters

*(Computed from the connectome by the main agent, not part of the subagent's run.)*

How many of the 64 LF motor neurons does each closer contact?

| closer | LF MNs reached | share | neurotransmitter | effect |
|--------|----------------|-------|------------------|--------|
| `IN21A004` | **46** | **72%** | acetylcholine | excitatory |
| `IN21A006` | 39 | 61% | glutamate | inhibitory |
| `IN13A006` | 38 | 59% | GABA | inhibitory |
| `IN13A002` | 26 | 41% | GABA | inhibitory |
| `AN04B001` | 13 | 20% | acetylcholine | excitatory |
| `IN23B024` | 4 | 6% | acetylcholine | excitatory |

**The strongest excitatory closer reaches 72% of all LF motor neurons.** So "the signal
returned to a neuron presynaptic to the origin" is very nearly guaranteed by anatomy — it would
be true for almost any origin we could have picked.

**The 72% is one identified cell, not an artefact of pooling a type.** Six neurons share the
name `IN21A004` — one per side per thoracic segment, a serially repeating motif. Only the
left-T1 cell contacts left-front motor neurons; the other five contact **zero**:

| bodyId | soma side | segment | LF MNs contacted |
|--------|-----------|---------|------------------|
| **800802** | **L** | **T1** | **46 of 64** |
| 800549 | R | T1 | 0 |
| 801054 | L | T2 | 0 |
| 820881 | L | T3 | 0 |
| 800793 | R | T3 | 0 |
| 801665 | R | T2 | 0 |

That is exactly correct anatomically — T1 is the front-leg segment, L the left side — so the
figure is a property of one cell rather than a sum over six.

**And its profile is that of a global postural driver, not a specific relay.**
`superclass = vnc_intrinsic` (local to the VNC), `subclass = IR` (intersegmental),
**cholinergic/excitatory** at 0.96 confidence, with **1,874 outgoing and 5,793 incoming**
synapses (`synweight` 17,081) — roughly 50× the VNC median in-degree of 111. A large excitatory
local cell fanning out onto 72% of one leg's motor pool is wired to say "excite the whole leg,"
not "excite this muscle."

So the broadcast is not an accident of our stimulus. The return path's strongest excitatory
element is a cell that anatomically **cannot** carry per-muscle information.

This undercuts Child 2's design directly. Its hypothesis is that closed-loop pathway weights
increase *relative to matched control pathways*. If the return path contacts most of the
population, the "control" pathways are largely the same pathways, and there may be no
meaningful contrast to measure. **A positive Child 2 result would be difficult to distinguish
from an artefact of broadcast connectivity.**

### The signal returns as inhibition

Summed effect onto in-scope motor neurons: `IN13A006` −18.24 mV, `IN21A006` −13.86,
`IN13A002` −12.76, against `IN21A004` +33.17 and `AN04B001` +5.64. Neurotransmitters verified
independently in the table above (glutamate is inhibitory in *Drosophila*).

So the dominant returning message is *suppression*. That is architecturally reasonable for a
reflex — real proprioceptive feedback is heavily inhibitory, and it is consistent with the 68%
GABAergic input onto the afferents themselves. But every version of our loop diagram assumed an
excitatory arc that STDP would strengthen. Child 2 would be strengthening an **inhibitory**
return path, which is a different experiment from the one specified.

### Timing is outside the plasticity window

Closure latencies are **35-49 ms**, and the winning condition used a **200 ms** burst.

> **CORRECTION (2026-08-18): this was wrongly presented as disqualifying.** The original text
> read "against a 20 ms STDP window ... conduction is demonstrated; STDP-usable timing is not."
> That misread our own implementation.
>
> `tau_stdp_ms = 20` is the *pairing* time constant setting eligibility **magnitude** — not a
> deadline. The trace that carries credit forward is `tau_eligibility_s = 1.0`, i.e. **1000 ms**
> (`functional_training.py:89`, three-factor STDP since Epic 4.1). At 49 ms the loop closes
> within **5%** of the trace's lifetime.
>
> So **timing is not a barrier.** A 35-49 ms return is comfortably bridgeable by the mechanism
> already in the code, and the 200 ms burst is a *stimulus* duration, not a plasticity constraint.
>
> **What this does not rescue:** eligibility traces solve *temporal* credit assignment — when the
> credit arrives. They do nothing for *spatial* credit assignment, which is the actual blocker. A
> 1000 ms trace cannot indicate which of the 46 motor neurons downstream of `IN21A004` caused the
> movement; it only keeps the same undifferentiated signal available longer. **The broadcast is
> the disqualifying finding, and it stands.**

The minimum conducting rate was not measured (drive was fixed at 200 Hz nominal), so it remains
unknown whether any parameter set closes the loop *within* the window.

### One structural curiosity

`Tergotr. MN` counts as a closer because it is presynaptic to in-scope motor neurons — but its
output onto them sums to exactly **+0.00 mV** across 11 wired synapses, all with sign-0
neurotransmitter. Structurally presynaptic, electrically silent. A reminder that connectome
adjacency and functional connectivity are different things, which is the same lesson as the
convergence floor.

## What This Means

**Level 1's physical question is answered: yes, the loop conducts.** That was genuinely open —
the previous experiment showed the return limb firing nothing — and it is now settled with a
clean positive and a clean negative control.

**Level 1's scientific question is not answerable at this level.** It asks *which motor neuron
controls which joint*. But closure requires simultaneous 2-3 group movement, so the returning
signal reports *that the leg moved*, not *which muscle moved it*. Compounding that, the return
path reaches 41-72% of motor neurons, so it could not carry per-neuron specificity even if the
stimulus were specific.

This is a real result about how the circuit is built: **the proprioceptive return path in the
VNC is a broadcast, not a private line.** That is not a limitation of our model — it is what
the connectome says, and it is biologically sensible for a system whose job is postural
regulation of a whole leg rather than per-muscle bookkeeping.

**Implication for the programme.** The tension flagged in the previous lab entry is now
resolved, unfavourably: pool-level credit assignment was already a retreat from cell-level, and
this shows even pool-level is not available at Level 1. Level 2 (interneuron origin) is the
better target — interneurons sit in far higher-convergence positions, and "which interneuron
pattern produces which movement" is a question a broadcast return path *can* answer, because it
is asking about patterns rather than individual cells.

Child 2 should not run as written. Before it does, it needs (a) a control set that is genuinely
disjoint from the closing pathways, which may not exist, (b) a decision about strengthening an
inhibitory arc, and (c) an STDP rule with a depression term, which we still do not have.

## Threat to Validity — the 200 Hz drive is unphysiological, and it is our own artefact

*(Added 2026-08-18 after a literature check, post-hoc to the run above.)*

**The drive used here exceeds any measured *Drosophila* leg motor neuron firing rate.**

Azevedo et al. 2020 (*eLife* 9:e56754) recorded identified femur/tibia-flexor MNs in the
**front leg** — our exact pool. Slow MNs idle at ~30 Hz, peak ~100 Hz under natural
proprioceptive drive, and cap at **~150 Hz under direct current injection**. Intermediate and
fast MNs are silent at rest and fire **1-10 spikes**, with force saturating by ~10. No
measurement of a fly leg MN at or near 200 Hz was found in any condition.

So 200 Hz × 200 ms is beyond the artificial ceiling for a slow MN and off the map by more than
an order of magnitude for a fast one.

**Worse, the 200 Hz traces back to our own unsourced assumption.**
`13-motor-neuron-muscle-mapping.md` §4 sets `activation_scale = sum(w_i) * max_rate` with
`max_rate ~ 200 Hz`. Normalising against a rate the neurons cannot reach makes activation
systematically too low, so movement requires compensating drive. **This experiment did not
discover that the loop needs 200 Hz — it recovered our own normalisation constant.**

The likely mechanism: Azevedo found force per spike spans **three orders of magnitude** across
classes (fast ~10 µN/spike ≈ body weight; slow ~0.013 µN). Our decoder has **no class
distinction** — it weights MNs by connectome `size`, a **14×** spread, and that weight scales
*drive* rather than *force per spike*. A 1000× gradient represented as 14×, in the wrong
variable, is a plausible ~10-20× force deficit — the right order to explain the 200 Hz.

### What this invalidates, and what survives

**In question** — all downstream of force gain:

- "The ~4-neuron / 80 Hz protocol does not conduct" — it might, at correct force per spike
- "Closure takes 35-49 ms" — inflated, because the joint accelerates too slowly
- (The "timing is outside the window" concern is withdrawn outright — see the correction above.
  Faster closure would still be welcome, but it was never disqualifying.)

**Unaffected** — anatomy, independent of force:

- **The return path is a broadcast** (`IN21A004` bodyId 800802 → 46 of 64 LF MNs)
- **The return is predominantly inhibitory**
- **Closure requires multi-joint movement**, so feedback reports *that the leg moved*
- **The frozen-physics control** — 0 afferent spikes, so conduction really is body-mediated
- **Breadth beats drive strength** — single-muscle conditions failed at the *same* rate and
  *larger* excursions, a within-experiment comparison that a shared force error cannot explain

**So the headline finding stands and Level 1's specificity problem stands.** What is in doubt is
whether Level 1's protocol is as infeasible as the timing numbers suggest.

**This is an inference, not a measurement.** We have shown the model omits the gradient; we have
*not* shown that restoring it recovers 20 ms closure. Follow-up:
[Idea: motor force-per-spike gradient](../ideas/2026-08-18-motor-force-gradient.md).

> **CORRECTION (2026-08-18, after the follow-up ran): the first sentence of this
> section is wrong, and the error is ours a second time over.**
> [Lab: motor force classes](2026-08-18-motor-force-classes.md) measured the
> minimum conducting rate that this entry left unmeasured.
>
> **This experiment did not need 200 Hz. It closes at 20 Hz** — with a 200 ms burst
> and *the same decoder this entry used*. Drive was pinned at 200 Hz and rate was
> never swept, which this entry's own "Not Verified" section states. So "the drive
> used here exceeds any measured rate" is true and "the loop required it" is not:
> **the 200 Hz was a property of the protocol we chose, not a requirement the loop
> imposed.** The decoder defect was real and depressed activation 3-6× at
> physiological rates, but it is not what produced the 200 Hz figure.
>
> Corrected per-decoder minima (frozen control at every point, causal ordering
> enforced): legacy decode 100 Hz @ 50 ms / **20 Hz** @ 200 ms; per-class force
> decode 80 Hz @ 50 ms / **20 Hz** @ 200 ms.
>
> Also falsified: the expectation that closure latency would drop. The
> afferent→closure lag floors at **28.6 ms** across all 27 closing conditions under
> either decode, so **~35 ms is a synaptic floor** that no force-per-spike value can
> lower. Faster force compresses only the mechanical half (51.2 ms → 6.6 ms
> drive-to-first-afferent).
>
> **Unaffected:** every anatomical finding in this entry — the broadcast, the
> inhibitory return, the multi-joint requirement, the clean frozen control, and
> breadth beating drive strength.

## Corrections to Prior Documents

- **"Velocity closes the loop"** — holds for the tibia; the trochanter closes on force and one
  coxa driver on position. Modality ranking is joint-dependent.
- **"~4-neuron pools at ~80 Hz"** — already retired as non-conducting; this experiment confirms
  that even the conducting protocol needs 200 Hz and 200 ms, both far outside the original spec.
- **The loop diagram's implied excitatory return arc** — measured to be predominantly
  inhibitory.
- **"Closure must occur within the 20 ms STDP window"** — the framing was wrong, not just the
  number. `tau_stdp_ms = 20` sets eligibility magnitude; `tau_eligibility_s = 1.0` (1000 ms)
  carries the credit. 35-49 ms is well inside that. Retracted as a disqualifying criterion.
- **The single-shot PSP analysis was pessimistic in the right direction but wrong in detail** —
  it predicted the direct path could not conduct (correct) but the relay figures were ~13% high
  (17.65 vs 15.56 mV for IN23B024) because they used the weight formula from a code comment
  rather than the live path.

## Not Verified

- **Minimum conducting rate not measured.** Drive was fixed at 200 Hz nominal, so we do not
  know whether closure is achievable inside the 20 ms window at any setting. This is the single
  most useful follow-up.
- Peak depolarisation figures (18.56-21.67 mV) come from a `StateMonitor` and are context only.
- CPU Brian2 only; the GPU path was not exercised (0a showed the backends agree on delay).
- Whether the return path *discriminates between origins* at all — the natural test of the
  broadcast finding — was not run. It would settle whether Child 2 has a measurable contrast.

## Artifacts

- `src/digital_drosophila/body_wiring.py` — `measure_multi_muscle_drive`, `run_lockstep_multi`;
  CLI `check multi_muscle`
- Previous entry: [the return limb does not conduct](2026-08-18-babbling-child0-return-limb-fails.md)
- Epic: [Sensorimotor Babbling Level 1](../issues/2026-08-17-sensorimotor-babbling-level1.md)
- Idea doc: [2026-08-17-sensorimotor-babbling.md](../ideas/2026-08-17-sensorimotor-babbling.md)
