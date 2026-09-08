# The Force Gradient Was Real, the 200 Hz Requirement Was Not

**Date:** 2026-08-18
**Experiment:** Test whether a defective decoder — an unsourced `max_rate = 200 Hz`
and no motor-neuron force classes — explains why our sensorimotor loop only closed
at 200 Hz sustained for 200 ms

## Summary

Two defects were found, fixed, and measured. Only one of them mattered, and the
result they were supposed to explain **turned out not to need explaining.**

**Confirmed.** The decode really was systematically too weak, by ~3× at
physiological rates. And the loop closes under drive shaped like real biology:
slow motor neurons tonic at **30 Hz** plus fast motor neurons firing **1 spike**
closes the loop in **35.9 ms**, in 12 of 12 class-specific conditions. At ≤80 Hz
the corrected decode produces **1.431 rad** of movement against **1.446 rad** for
the legacy decode at 200 Hz — **0.99×**. So the answer to the question as posed is
yes: at biologically plausible drive the joint moves as far as it did at 200 Hz,
and the loop still closes.

**Falsified — and it was our own artefact again.** The legacy decode *also* closes
at **20 Hz** with a 200 ms burst. The previous experiment never measured the
minimum conducting rate; it pinned drive at 200 Hz and said so in its own "Not
Verified" section. So **the 200 Hz was a property of the protocol we chose, not a
requirement the loop imposed.** The constant did depress activation, but the
inference "the loop needs 200 Hz, and the reason is the constant" was wrong in
both halves.

**Second bottleneck found, and it is not force.** The afferent→closure lag is
**28.6 ms at best and never lower**, under any drive rate and either decode. Force
gain compresses only the *mechanical* half of the latency (drive→first afferent:
51.2 ms at 20 Hz → 6.6 ms at 200 Hz). The remainder is synaptic integration
through the connectome. **Closure latency floors at ~35 ms**, so the predicted
"latency should drop from 35-49 ms" is wrong — 35 ms *is* the floor.

## What We Did

Reproduce: `python -m digital_drosophila check multi_muscle` (deliverables [5] and
[6]) and `check body_wiring`. Full VNC (25,635 neurons / 4,114,854 synapses),
network and physics in lockstep at `dt = 0.1 ms`, 3000-step settle, `data.act`
restored between conditions, frozen-physics control at every point.

**Both decoders run in the same process**, against the same settled body, the same
seeded per-synapse delays and the same network — `MuscleDecoder(force_model=False)`
reproduces the legacy decode exactly. So the before/after is one changed variable,
not a comparison against a remembered number.

Every verdict is a `SpikeMonitor` count. Voltages are context only.

## The Guard Against Tuning Worked, and Was Needed

Force gain is exactly the dial that could manufacture the desired answer. All
per-class constants were fixed from Azevedo et al. 2020 and written into the code
**before** any loop test ran, and none was changed afterwards.

One of them is checkable against a second, independent number in the same paper,
which is worth recording because it came out right: the twitch summation ratio
`x = 0.6` was derived *only* from "the force produced by two spikes was ~1.6X the
force produced by a single spike" (`F(2)/F(1) = 1 + x`). That value then predicts
`F(10)/F_sat = 0.994` — reproducing the separately stated "force-per-spike curves
saturated at ~10 spikes". Two readings of the paper, one parameter, consistent. The
demo prints the measured ratio as **1.600**.

## Class Assignment Is an Assumption, and Is Labelled as One

No principled assignment exists. Three routes were checked and all three fail:

1. **`size` cannot carry the gradient by magnitude.** Azevedo's classes are a
   *within-muscle* distinction. Our Ti flexor pool spans **2.1×** in `size` across
   5 neurons; Ti extensor 1.4× across 2. A 2.1× spread cannot encode 1000×. (The
   14× figure in the older docs is the spread across all 64 LF MNs of *different*
   muscles — a different quantity.)
2. **`synweight` is no better as a *class* variable.** It spans more (122× within
   the trochanter-flexor DOF pool) but counts synapses, not contractile capacity,
   and it correlates strongly with `size` anyway — Spearman **ρ = 0.83**,
   p = 4e-17 over the 64 LF MNs (measured) — so it would largely reproduce the same
   ordering while being harder to defend.
3. **Azevedo's cells cannot be joined to MANC types.** His classes are Gal4 lines
   (fast R81A07, intermediate R22A08, slow R35C09). MANC `type` for all 64 LF MNs
   names only the *muscle*, and every finer-identity column is empty for this
   population — `flywireType`, `hemibrainType`, `synonyms`, `class`, `supertype`
   all NaN; `mancType` merely repeats `type`. **There is no join key.**

So the fallback uses **rank, not magnitude**: class by `size` rank within each
`(leg, type)` pool, with Azevedo's anatomical pool proportions (1 fast : 3.5
intermediate : rest slow, of ~15) applied as fractions. The defence is that the
size principle predicts recruitment order tracks size — Azevedo's fast cell has
"an exceptionally large soma", his slow cell "the smallest cell body, dendrites,
and axon" — even where the connectome's dynamic range understates the force ratio.

Verified, not assumed: **0 of 140 pools** are non-monotone in `size`, and every
pool gets exactly one fast neuron.

## The Hill-Type Model Does Admit the Gradient

This was a possible show-stopper — a 1000× per-spike range is untestable if the
muscle model clamps it. It does not. Driving `LFTibia_flex_93434` alone from the
settled posture:

| ctrl | peak \|actuator force\| | excursion (rad) |
|------|------------------------|-----------------|
| 1e-4 | 0.007 | 0.0006 |
| 1e-2 | 1.36 | 0.009 |
| 1e-1 | 13.6 | 0.093 |
| 0.5 | 68.1 | 0.435 |
| 1.0 | 136.2 | 0.704 |

A 2×10⁴ force span over the usable `ctrl` range, near-linear, and `forcelimited`
is `False` on all 15 actuators. Excursion saturates well before force does, but
that is joint-limit mechanics, not a clamp on the range.

## The Size Principle Still Holds

Checked explicitly rather than argued, because it broke once before (a mean-based
decode drove a joint backwards by −0.225 rad when 1 of 8 neurons fired). Over
**all 15 muscle pools in both recruitment orders** — largest-first and
smallest-first, since a pool-mean bug hides in one order only:

- monotonicity violations: **0**
- additions leaving activation unchanged in an unsaturated pool: **0**
- pool members producing zero activation alone: **0**
- fully silent network: activation exactly **0.000000000**, joint offset exactly
  **0.000000000 rad**

## What We Measured

### Minimum conducting rate — the number the last experiment could not report

`3group:strongest x3`, frozen control at every point, causal ordering enforced:

| decoder | burst | min Hz that closes | closure latency | peak excursion |
|---------|-------|--------------------|-----------------|----------------|
| legacy | 50 ms | 100 | 49.0 ms | 0.671 rad |
| legacy | 200 ms | **20** | 127.3 ms | 1.160 rad |
| force | 50 ms | **80** | 44.0 ms | 0.753 rad |
| force | 200 ms | **20** | 87.7 ms | 1.411 rad |

**Both decoders close at 20 Hz.** The corrected decode helps at the short burst
(100 → 80 Hz) and moves the leg substantially further everywhere, but it does not
change the minimum rate at 200 ms, because the legacy decode was already
sufficient there. Nobody had looked.

### Same-rate comparison — what the decode change actually buys

| burst | Hz | legacy act | force act | legacy exc | force exc | legacy closes | force closes |
|-------|----|-----------|-----------|-----------|-----------|---------------|--------------|
| 50 | 30 | 0.091 | 0.581 | 0.114 | 0.273 | no | no |
| 50 | 50 | 0.253 | 0.763 | 0.357 | 0.539 | no | no |
| 50 | 80 | 0.438 | 0.892 | 0.565 | 0.753 | no | **YES** |
| 50 | 100 | 0.578 | 0.928 | 0.671 | 0.834 | YES | YES |
| 200 | 50 | 0.508 | 0.917 | 1.238 | 1.422 | YES | YES |

The activation gain at physiological rates is **3.0× at 50 Hz**, **5.7× at 30 Hz**,
and falls below 1 at 200 Hz — which is the signature of the defect. The legacy
decode was normalised so that only ~200 Hz produced full activation.

### The class-specific protocol — the question in its literal form

Every earlier sweep drove all neurons at one uniform rate for the whole burst, a
protocol no motor pool runs. Here slow MNs are tonic and fast/intermediate MNs get
N spikes and then go **silent** (current withdrawn after `N / 200 Hz`; spike counts
verified from the `SpikeMonitor`, not assumed from the window):

| slow Hz | fast spikes | fast spk measured | slow spk | excursion | afferents | t_close | closes |
|---------|-------------|-------------------|----------|-----------|-----------|---------|--------|
| 30 | 1 | 4 | 32 | 0.987 rad | 41/41 | 35.9 ms | YES |
| 30 | 2 | 8 | 32 | 1.173 rad | 41/41 | 35.4 ms | YES |
| 50 | 2 | 8 | 46 | 1.173 rad | 41/41 | 35.4 ms | YES |
| 80 | 10 | 44 | 70 | 1.444 rad | 41/41 | 35.2 ms | YES |

**12 of 12 closed.** The cheapest protocol — 30 Hz tonic plus a single fast spike —
is *below* the 50-80 Hz the question asked about. Under the legacy decode the same
1-spike protocol does **not** close at either burst length, so this is where the
decode fix is load-bearing.

### Where the latency actually goes — the second bottleneck

Splitting closure into the half force can move and the half it cannot:

| decoder | Hz | t_first_afferent | t_closure | lag |
|---------|----|------------------|-----------|-----|
| force | 20 | 51.2 ms | 87.7 ms | +36.5 |
| force | 50 | 22.2 ms | 56.8 ms | +34.6 |
| force | 80 | 14.4 ms | 44.0 ms | +29.6 |
| force | 200 | 6.6 ms | 35.2 ms | +28.6 |
| legacy | 200 | 6.6 ms | 35.5 ms | +28.9 |

The mechanical half compresses **7.8×** with drive. The lag **does not go below
28.6 ms** in any of the 27 closing conditions, under either decode. That residual
is synaptic integration through the connectome, and **no force-per-spike value can
reduce it.** This is a genuine second bottleneck, and it means closure latency has
a floor at ~35 ms that this hypothesis cannot lower.

Not disqualifying — `tau_eligibility_s = 1.0` is 1000 ms, so 35 ms is 3.5% of the
trace — but the idea's prediction that latency would *drop* is falsified.

### `check body_wiring` still passes

Velocity is still the first modality to spike (12.9 ms, pool 8 @ 200 Hz), and it is
still joint-dependent — position wins on the trochanter. Unchanged by the decode.

## What This Means

**The decoder defect was real.** `max_rate = 200 Hz` was unsourced, unreachable and
divided into activation, making it 3-6× too low at physiological rates; and the
decoder had no force classes at all. Both are now fixed, with per-class force per
spike, per-class rate ceilings, and `baseline_hz = 15` retired (it silenced a
tonically active class at one end and deleted three quarters of a single fast spike
at the other).

**But the finding it was supposed to explain was never a finding.** "The loop needs
200 Hz" was the drive we happened to pick, and the same protocol closes at 20 Hz
with the *old* decoder. Two "empirical findings" on this project had already turned
out to be our own constants read back to us; this is a third, and of a slightly
different kind — not a constant misread as a measurement, but a *never-swept
parameter* misread as a requirement. The lesson generalises: **the previous entry
flagged "minimum conducting rate not measured" in its own Not Verified section, and
the inference was drawn anyway.**

**A second bottleneck exists and it is anatomical.** The 28.6 ms synaptic floor is
independent of force, of rate and of decode. Anything that wants faster closure has
to change the wiring or the neuron model, not the muscle.

**Level 1's specificity problem is untouched**, exactly as the idea predicted. The
return path is still a broadcast (`IN21A004` → 46 of 64 LF MNs), still predominantly
inhibitory, and closure still requires multi-joint movement — all three are anatomy
and all three survive.

## Corrections to Prior Documents

- **`13-motor-neuron-muscle-mapping.md` §4** — rewritten. §4.1 is the per-class
  force model, §4.2 states the class assignment as a labelled assumption with the
  three failed alternatives, §4.3 keeps the superseded flat-`max_rate` decode
  because every pre-2026-08-18 measurement used it, §4.4 records the Hill-type
  linearity measurement.
- **"The multi-muscle experiment needed 200 Hz"** — retracted. It *used* 200 Hz.
  The minimum was 20 Hz all along, under the same decode.
- **"Closure takes 35-49 ms, inflated because the joint accelerates too slowly"** —
  half right. The joint did accelerate too slowly, but 35 ms is a synaptic floor and
  not inflated by it.
- **"The ~4-neuron / 80 Hz protocol does not conduct"** — still in question but for
  a different reason: 8 in-scope MNs at 80 Hz now conduct at a 50 ms burst. The
  original 4-neuron single-muscle version remains untested under the new decode.
- **`baseline_hz = 15`** — retired, not merely questioned.

## Not Verified

- **The class assignment is an assumption and cannot be validated against this
  data.** If Azevedo's Gal4 lines are ever mapped to MANC bodyIds, every per-class
  number downstream should be re-derived. Nothing here shows the assignment is
  *correct*, only that it is monotone, proportioned from the paper, and labelled.
- **`fusion_tau = 40 ms` is a cross-species import** — locust extensor tibiae
  (Harischandra et al. 2019), not *Drosophila*. It is not load-bearing (the phasic
  classes have saturated; the slow class is a few percent of pool maximum) but it is
  not a fly number.
- **The slow-MN 0.013 µN/spike figure was read off an axis**, not stated in text.
  Treat as ±20%. Azevedo's text says only "<0.1 µN".
- **Azevedo states no rate ceiling for the phasic classes** — only a spike count.
  The 250 Hz used for them is a modelling choice, defensible because their force
  function has already saturated there (moving it changes maximum force by <1%), but
  it is not a measured rate.
- **20 Hz is the LIF's floor**, not a biological one: with `t_refract = 2 ms` the
  cell jumps from silent (201 pA) to 20 Hz (202 pA). Whether the loop would close
  below 20 Hz cannot be asked of this neuron model.
- **CPU Brian2 only**; the GPU path was not exercised.
- Whether the corrected decode changes anything about *training* (STDP,
  `functional_training`) was not measured. Those callers now pick up the force model
  by default, and every latency and behaviour number recorded before today used the
  legacy decode.

## Artifacts

- `src/digital_drosophila/muscle_decoder.py` — `FORCE_PER_SPIKE_UN`,
  `CLASS_MAX_RATE_HZ`, `CLASS_BASELINE_HZ`, `class_force_un`,
  `assign_force_classes`, `MuscleDecoder(force_model=...)`, `class_summary`
- `src/digital_drosophila/body_wiring.py` — `verify_size_principle`,
  `measure_rate_threshold`, `measure_class_protocol`, per-class drive gating in
  `run_lockstep_multi`, extended `DRIVE_PA_FOR_HZ`
- Previous entry: [multi-muscle loop closure](2026-08-18-multi-muscle-loop-closure.md)
- Idea: [motor force-per-spike gradient](../ideas/2026-08-18-motor-force-gradient.md)
