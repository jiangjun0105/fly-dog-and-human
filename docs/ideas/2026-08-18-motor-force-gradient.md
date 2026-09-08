# Idea: Model the Motor Neuron Force-Per-Spike Gradient

**Status:** IMPLEMENTED AND TESTED (2026-08-18) — partially confirmed, and it
falsified its own premise. See "Outcome" below.
**Date:** 2026-08-18
**Motivation (as originally written, and wrong in part — see Outcome):** Our loop-closure
experiment only worked at 200 Hz sustained for 200 ms — a rate no *Drosophila* leg motor neuron
has ever been measured to reach. The likely cause is that our decoder omits the 1000×
force-per-spike gradient across motor neuron classes.

> **The premise did not survive.** The loop never *required* 200 Hz — that rate was pinned by
> the protocol and never swept. The legacy decode closes at 20 Hz. The decode was genuinely ~3×
> too weak and that is worth fixing, but it is not what produced the 200 Hz figure.

## Outcome (measured 2026-08-18)

Implemented in `muscle_decoder.py` (per-class force per spike, per-class rate
ceilings, `baseline_hz` retired) and measured by `check multi_muscle`
deliverables [5] and [6], with both decoders run in the same process against the
same settled body and seeded delays.

**Confirmed:**

- The Hill-type model *can* express the gradient — force is near-linear in
  activation over 4 decades, so this was testable as posed.
- The decode was systematically too weak. At a physiological 50 Hz the corrected
  decode reaches activation 0.76 against the legacy 0.25 (**3.0×**).
- The loop closes under genuinely biological drive: slow MNs tonic at **30 Hz**
  plus fast MNs firing **1 spike** closes in **35.9 ms**, 12 of 12
  class-specific conditions.
- At ≤80 Hz the corrected decode reaches **1.431 rad** against 1.446 rad for the
  legacy decode at 200 Hz — **0.99×**. So yes, the joint moves as far at
  physiological drive as it did at 200 Hz.

**Falsified — the premise this idea was built on:**

- **200 Hz was never actually required.** The legacy decode also closes at
  **20 Hz** given a 200 ms burst. The previous experiment did not measure that
  the loop *needs* 200 Hz; it fixed drive at 200 Hz and never swept rate (it said
  so: "minimum conducting rate not measured"). So the constant depressed
  activation, but the "200 Hz requirement" was an artefact of the *protocol*, not
  of the constant. **This is the third premise on this project to dissolve on
  measurement, and it is our own again.**
- **Closure latency has a floor force cannot lower.** The
  afferent→closure lag is **28.6 ms** at best and never goes below it, at any
  rate, under either decode. Force gain shortens only the mechanical half
  (drive→first afferent: 51 ms at 20 Hz down to 6.6 ms at 200 Hz). The residual
  is synaptic integration through the connectome. So closure latency floors at
  ~35 ms and the predicted "closure latency should drop from 35-49 ms" is
  **wrong** — 35 ms *is* the floor.

**Net:** the decoder defect was real and is fixed; the result it was supposed to
explain did not need explaining. Level 1's specificity problem (the broadcast
return path) is untouched, as this idea already predicted.

## The Problem

The multi-muscle experiment closed the sensorimotor loop, but only under drive that the
literature says is unphysiological:

| our drive | measured biology |
|-----------|------------------|
| 200 Hz sustained, 200 ms | slow MN: ~30 Hz at rest, ~100 Hz natural peak, **~150 Hz artificial ceiling** |
| all 52 MNs treated alike | fast MN: **1-few spikes**, silent at rest, force saturates by ~10 spikes |

**No measurement of a *Drosophila* leg motor neuron at or near 200 Hz appears to exist.**

### Where the 200 Hz came from — it was our own assumption

`docs/neuroscience/13-motor-neuron-muscle-mapping.md` §4 defines

```
activation = clip( sum(w_i * rate_i) / activation_scale, 0, 1 )
activation_scale = sum(w_i) * max_rate      with  max_rate ~ 200 Hz
```

That `max_rate ~ 200 Hz` was written unsourced. Normalising against a rate the neurons cannot
reach makes activation systematically too low, so producing movement requires drive that
compensates — which is exactly the 200 Hz we ended up needing. **The experiment did not
discover that the loop needs 200 Hz; it recovered our own normalisation constant.**

### The mechanism we are missing

Azevedo et al. 2020 (*eLife* 9:e56754) recorded identified femur/tibia-flexor MNs in the
*front leg* — our exact pool — and found three classes whose force per spike spans **three
orders of magnitude**:

| class | resting rate | operating range | force per spike |
|-------|--------------|-----------------|-----------------|
| slow | ~30 Hz | ~10-100 Hz (150 driven) | ~0.013 µN |
| intermediate | 0 (silent) | phasic, ~10 spikes | — |
| fast | 0 (silent) | **1-few spikes** | **~10 µN ≈ body weight** |

A single fast MN spike should move the tibia. In our model it contributes a fraction of an
activation unit.

**Our decoder has no class distinction at all.** It weights MNs by connectome `size`
(`w_i = size_i / mean(size)`), which spans only **14×** across the 64 LF MNs — and that weight
scales *drive*, not *force per spike*. So a 1000× biological gradient is represented as 14×, in
the wrong variable.

This is a plausible ~10-20× force deficit, which is the right order to explain the 200 Hz.

## Proposed Approach

1. **Classify the 52 in-scope LF motor neurons** into slow / intermediate / fast. Open question
   which connectome variable predicts class — `size` is the obvious candidate but is a volume
   proxy, and Azevedo's classes differ in `Rin` and resting potential, which the connectome does
   not carry. May require matching named types against the paper's identified cells.
2. **Give each class its own force-per-spike and rate range**, replacing the single shared
   `max_rate`. Fast MNs should saturate after ~10 spikes; slow MNs should be tonically active at
   ~30 Hz and integrate over rate.
3. **Re-derive `activation_scale`** from per-class maxima rather than a flat 200 Hz.
4. **Re-run the loop-closure measurements** and ask whether closure now occurs at
   physiological rates and inside the 20 ms STDP window.

## Expected Outcome

If the force deficit is the explanation, then at biologically plausible drive (slow MNs
~50-80 Hz, fast MNs a few spikes) the joint should move as fast as it currently does at 200 Hz —
and closure latency should drop from 35-49 ms. Note this is a desirable improvement, not a fix
for a blocking defect: 35-49 ms is already within the 1000 ms eligibility trace.

## What This Would and Would Not Rescue

**Would plausibly be fixed** — all three are downstream of force gain:

- "The ~4-neuron / 80 Hz protocol does not conduct" — it might, with correct force per spike
- "Closure takes 35-49 ms" — inflated because the joint accelerates too slowly (though 35-49 ms
  was never actually disqualifying — the eligibility trace is 1000 ms)

**Would NOT be fixed** — this is pure anatomy and independent of force:

- **The return path is a broadcast.** `IN21A004` (bodyId 800802) contacts 46 of 64 LF motor
  neurons. No change to muscle force alters the wiring.
- **The return is predominantly inhibitory.**
- **Closure needs multi-joint movement**, so feedback reports *that the leg moved* rather than
  *which muscle moved it*.

So Level 1's **specificity** problem stands regardless. Only its **timing and conduction**
findings are in question. This idea could restore Level 1's protocol to plausibility without
restoring its scientific question.

## Trade-offs

- **Class assignment may not be derivable from the connectome.** If `size` does not predict
  slow/fast, we would be imposing a hand-built mapping — defensible, but an assumption layered
  on the anatomy rather than read from it.
- **It invalidates prior timing measurements.** Every latency we have recorded would need
  regenerating, again.
- **The 10-20× deficit is an inference, not a measurement.** It follows from the omitted
  gradient; we have not shown that correcting it recovers 20 ms closure. It might reveal a
  second, unrelated bottleneck.
- **Risk of tuning to a desired answer.** We now *want* closure inside 20 ms, and a
  force-gain parameter is exactly the knob that could produce it. The per-class values must be
  fixed from the literature *before* re-running, not adjusted until the latency looks right.

## Open Questions

1. Which connectome variable, if any, predicts slow/intermediate/fast? Can Azevedo's identified
   cells be matched to MANC types by name?
2. Does FlyMimic's Hill-type muscle model even admit a 1000× per-spike gradient, or does its own
   force scaling clamp the range?
3. Is `baseline_hz = 15` defensible once slow MNs are known to idle at ~30 Hz? A deadband at 15
   would silence a tonically active class.
4. Should the fast-MN saturation (~10 spikes) be modelled as muscle-side fatigue rather than a
   neural property? Azevedo attributes it to fibre fatigue.

## Evidence Base

- **Azevedo, Dickinson, Gurung, Venkatasubramanian, Mann & Tuthill (2020).** "A size principle
  for recruitment of *Drosophila* leg motor neurons." *eLife* 9:e56754 (PMC7347388). Primary,
  in vivo whole-cell + EMG, front-leg femur/tibia flexor. **The directly relevant source.**
- **Hürkey et al. (2023).** *Nature* 618:118 (PMC10232364). Asynchronous flight power-muscle MNs
  fire **3-12 Hz** during tethered flight while the muscle oscillates at ~200 Hz — a caution
  against reading muscle frequency as neural rate.
- **Fayyazuddin & Dickinson (1996).** *J Neurosci* 16:5225. b1 steering MN, one spike per
  wingbeat ≈ 150 Hz — in *blowfly*, and a wing rather than leg system. The one insect MN
  plausibly sustaining ~200 Hz.
- **Harischandra et al. (2019).** *PLoS Comput Biol* (PMC6812852). Locust extensor tibiae
  characterised 1-50 Hz; tetanic fusion above ~20-25 Hz.

**Caveats on this evidence:** several Azevedo figures were read off axes rather than stated in
text (treat as ±20%). No walking-state firing-rate distribution for fly leg MNs was found — the
rates above come from tethered spontaneous movement plus current/opto injection. The classic
locust kick papers (Heitler & Burrows 1977; Heitler 1988; Newland & Kondoh 1997) were paywalled
and are unread.

## Related Documents

- [Lab: multi-muscle loop closure](../lab/2026-08-18-multi-muscle-loop-closure.md) — the result
  that raised this
- `docs/neuroscience/13-motor-neuron-muscle-mapping.md` §4 — where `max_rate ~ 200 Hz` lives
- [Idea: sensorimotor babbling](2026-08-17-sensorimotor-babbling.md) — the programme this affects
