# Idea: Test the Full Loop (Level 3) Directly, Skipping Level 2

**Status:** Proposed
**Date:** 2026-08-19
**Motivation:** Every Level 1 failure came from the loop being *too small*. The connectome's convergence structure suggests the full descending-command loop is the regime the circuit is actually built for — and the return path onto descending neurons is measurably strong where Level 1's was not.

## The Problem With the Ladder

`12-sensorimotor-babbling.md` defines three levels and argues for testing them in order:

| Level | origin | question |
|-------|--------|----------|
| 1 | motor neuron | which motor neuron controls which joint |
| 2 | intrinsic interneuron | which interneuron pattern produces which movement |
| 3 | descending neuron | which brain command produces which whole-body sensation |

The stated rationale: **"Level 1 is first because its failure is the only interpretable one."**
That reasoning was sound but rested on an assumption that turned out to be false — that the
shortest loop is the *easiest* one.

**It is the hardest.** Every Level 1 obstacle was a consequence of being small:

| Level 1 finding | why it is a smallness problem |
|-----------------|-------------------------------|
| One synapse cannot fire a cell (max weight 3.98 mV vs 11.8 mV needed) | short loops have the least convergence available |
| Single-muscle drive recruits too few afferents to close (0 of 8 conditions) | the multi-joint stimulus that *does* work is what a descending command naturally produces |
| Return relay `IN21A004` contacts 46 of 64 LF motor neurons (72%) | too coarse for per-neuron attribution — **but the correct grain for a whole-body command** |

That last row is the inversion. The broadcast fan-out that **disqualified** Level 1 is
**appropriate semantics** for Level 3: a "walk" command *should* reach most of a leg's motor
pool. We spent Child 0 testing the one regime this circuit is not built for.

## The Blocker We Assumed Was There Is Not

Our documents repeatedly state that Level 3 is constrained because "the brain is not in our
dataset" (`cb_intrinsic` has **4 neurons**). True — and **irrelevant**, because the loop does
not need to leave the VNC.

Measured from `connectivity.npz` (2026-08-19):

- **65,788 ascending → descending synapses**, reaching **all 1,305** descending neurons.
- Convergence per DN: **median 33 ascending neurons, max 321**.
- Summed PSP onto one DN: **median 28.0 mV, p90 110.6, max 394.5** — against a 20 mV threshold.
- **841 of 1,305 DNs** receive more than threshold from their ascending input *alone*.

Compare the two return paths directly:

| return path | convergence | summed PSP | clears 20 mV? |
|-------------|-------------|-----------|---------------|
| Level 1: afferent → relay | up to 16 | max **15.56 mV** | **never** |
| Level 3: ascending → DN | median 33, max 321 | **median 28.0 mV** | **841 of 1,305** |

The *median* descending neuron is better connected for return than Level 1's *best* relay was.

**And `DNa02` — the known walking command we have already used — receives 58-59 ascending
neurons delivering ~68-70 mV.** That is 3.4× threshold, on the exact neuron we would stimulate.

## The Real Bottleneck Is Outbound, Not Return

This is the finding that should shape the experiment. Measured for `DNa02` (2 cells):

| stage | measurement |
|-------|-------------|
| DNa02 → motor, direct | 97 synapses |
| DNa02 → 1 hop | 918 target neurons; summed PSP onto one target **median 0.83, max 4.32 mV** — **0 targets reach 20 mV** |
| DNa02 → X → LF motor | 1,685 synapses reaching **64 of 64** LF MNs; summed PSP onto one MN median 16.9, **max 115.7 mV**, 30 MNs ≥ 20 |

So the second hop is strong and the return is strong, but **the first hop is weak**: DNa02 is
only 2 cells, and 2 cells cannot fire anything on a single volley (max 4.32 mV against 20).

This is the *same* convergence floor found at Level 1, now on the outbound side. It has three
possible resolutions, and distinguishing them is the first experiment:

1. **Temporal summation** — DNa02 firing at a sustained high rate. Bounded by ×5.52 (refractory
   ceiling), so 4.32 mV → ~23.8 mV at maximum rate. Just barely viable, and only for the
   strongest target.
2. **Background operating point** — the effect we just measured at Level 1. With relays parked
   sub-threshold, a 4.32 mV input may suffice. At ~125 pA background (12.5 mV idle) the gap to
   threshold is 7.5 mV, which 4.32 mV does *not* close alone but two volleys would.
3. **Co-activation** — real walking recruits many descending neurons, not DNa02 alone. If DNa02
   in isolation cannot drive the circuit, that is biologically expected rather than a defect.

**Resolution 3 is the biologically faithful one and mirrors Level 1's lesson exactly** — there,
the fix was multi-muscle rather than single-muscle drive; here it would be multi-DN rather than
single-DN drive. Same correction, one level up.

## Proposed Approach

1. **Verify the outbound half conducts** — stimulate DNa02 (and, if it fails alone, a small
   co-activated DN set) and measure whether LF motor neurons fire. This is the Level 3 analogue
   of Child 0c's exit gate, and it must include a background operating point from the outset.
2. **Verify the full loop** — does motor firing → muscle → joint → afferent → ascending →
   *back to DNa02* complete? Report per-stage latency, with a frozen-physics control at every
   step.
3. **Only then consider plasticity.** Child 2's design problems (no depression term, no
   unmodulated two-factor mode, no disjoint control set) are unresolved and should not gate
   the conduction question.

## Why Skip Level 2

Level 2 is intermediate on every axis, and **its interpretability problem is the same as Level
3's**: a failure could mean wrong hypothesis, wrong cluster, or too-deep circuit. So it does not
buy the diagnostic clarity the ladder was designed to provide. If we are accepting that
ambiguity, accept it at the level that answers the question we care about.

Level 2 also inherits a blocker Level 3 partly avoids: the **unsigned position channel**
(flexion +0.778 rad and extension −0.769 rad both produce *exactly* 152 Hz). Level 2 asks about
agonist/antagonist coordination, which that encoding cannot express. A whole-body command loop
is less dependent on per-joint direction — though see Trade-offs.

## Expected Outcome

The full loop closes, at a latency dominated by hop count and convergence rather than by
physics. If it does, we will have shown that the VNC connectome supports body-mediated temporal
correlation at the command level — which is the original scientific question, and the one Level
1 turned out to be unable to answer.

## Trade-offs

- **A Level 3 failure is genuinely ambiguous** — wrong hypothesis, or a circuit too deep? This
  is precisely what the ladder was built to avoid, and we are giving it up deliberately.
  Mitigation: we now have instruments we lacked at the start — the frozen-physics control,
  per-modality afferent timing, convergence arithmetic, a calibrated encoder, and a working
  conduction harness. All transfer directly.
- **More stages means more places to hide a self-inflicted artefact.** Five of those have
  already been found on this project. The background operating point must be set *before* the
  first measurement, not discovered afterwards.
- **The unsigned position channel is still unfixed.** Less blocking here than at Level 2, but
  it means the loop cannot distinguish flexion from extension anywhere.
- **DNa02 alone may not be the right stimulus.** If co-activation is required, "which command
  produced which sensation" becomes coarser — the same dilution that happened to Level 1 when
  we moved from single-muscle to multi-muscle drive. Worth stating in advance rather than
  discovering it as a disappointment.
- **PSP figures here use the weight formula from a `network.py` comment**, so they are
  order-of-magnitude. Recompute from the live code path before relying on them.

## Open Questions

1. Can DNa02 alone drive the circuit, or is DN co-activation required? Which minimal set works?
2. What background operating point do the *outbound* relay neurons need? Level 1 measured this
   for the return path only.
3. Does the loop close back to the *originating* DN, or only to other DNs? With 65,788
   ascending→DN synapses the return may be as broadcast as Level 1's was — **the specificity
   question does not disappear by moving up a level, it just changes scale.**
4. Ascending neurons are the return path here, yet `12-sensorimotor-babbling.md` corrected an
   earlier claim that ascending neurons carry the *Level 1* return path. Both can be true —
   local reflex is not ascending; command-level return is — but the distinction should be
   written down explicitly to avoid re-confusing it.

## Related Documents

- `docs/neuroscience/12-sensorimotor-babbling.md` — the three-level concept
- [Lab: multi-muscle loop closure](../lab/2026-08-18-multi-muscle-loop-closure.md) — the broadcast finding
- [Lab: relay operating point](../lab/2026-08-18-relay-operating-point.md) — background is load-bearing
- [Idea: sensorimotor babbling](2026-08-17-sensorimotor-babbling.md) — the Level 1 programme
