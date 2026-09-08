# L3 Child A: Outbound Exit Gate — can a descending command drive the leg?

**Date:** 2026-08-19
**Status:** todo
**Parent:** [Idea: full loop / descending command](../ideas/2026-08-19-full-loop-descending-command.md)
**Type:** experiment (exit gate)

## Problem

We are moving from Level 1 (motor-neuron origin) to Level 3 (descending-command origin). The
return path is measurably strong — 65,788 ascending→DN synapses, median summed PSP 28.0 mV
against a 20 mV threshold, 841 of 1,305 DNs clearing it on ascending input alone.

**The bottleneck is the outbound half.** Measured for `DNa02` (2 cells):

| stage | measurement |
|-------|-------------|
| DNa02 → motor, direct | 97 synapses |
| DNa02 → 1 hop | 918 targets; summed PSP **median 0.83, max 4.32 mV** — **0 of 918 reach 20 mV** |
| DNa02 → X → LF motor | 1,685 synapses reaching **64 of 64** LF MNs; median 16.9, **max 115.7 mV**, 30 ≥ 20 |

Hop 2 is strong and the return is strong. **Hop 1 is weak**: 2 cells cannot fire anything on a
single volley. This is the same convergence floor found at Level 1, now on the outbound side.

Until this is resolved, no Level 3 loop measurement is meaningful.

## Desired Behavior

Stimulate a descending command and show that **named LF motor neurons spike**, with elapsed time
printed. This is the Level 3 analogue of Child 0c's exit gate.

### Demo

```
DN set <names/bodyIds> driven at <rate> Hz for <duration> ms
  → relay <name> spiked at t = <n> ms  (convergence <n> neurons, <n> mV)
  → LF motor neuron <name> spiked at t = <n> ms
  → <n> of 52 in-scope LF MNs fired
```

**Exit gate:** if no LF motor neuron can be made to fire from descending stimulation, Level 3 is
blocked and the full-loop experiment cannot be interpreted. Report that as a result, not a
failure — it would be a real finding about descending control in this connectome.

## The three candidate resolutions — distinguishing them IS the experiment

1. **Temporal summation.** DNa02 firing at sustained high rate. Bounded by **×5.52** (refractory
   ceiling), so 4.32 mV → ~23.8 mV at maximum rate. Barely viable, and only for the single
   strongest target. Test it, but do not expect it to carry the result alone.
2. **Background operating point.** The Level 1 lesson: relay neurons pinned at `V_rest` need the
   full 20 mV, which inflated our latency 5×. **Set a background operating point before the first
   measurement, not after.** Usable window measured at Level 1: **0-125 pA constant (0-12.5 mV
   idle) or 0-11 Hz Poisson**; above that, relays fire spontaneously. Note
   `create_background_drive`'s own 22 Hz default is **above** the spontaneity ceiling — do not use
   it unexamined.
3. **DN co-activation** — the most likely answer. Real walking recruits many descending neurons,
   not one. This mirrors Level 1's multi-muscle correction exactly: there the fix was multi-source
   drive, here it should be too.

## DNa02 is probably the wrong stimulus — check before committing to it

We have used `DNa02` throughout the project as "the known walking command," and it is the obvious
starting point. But ranked by summed outbound PSP onto interneurons that reach LF motor neurons,
**DNa02's two cells rank 537th and 66th of 1,279 DNs.** The strongest are:

> **CORRECTED 2026-08-19 — the original table here was wrong and is replaced.** It ranked DNs by
> `log1p(synapse_count) * 0.6`, omitting the `sign` and `confidence` factors the live formula
> applies (`network.py:447`). That is sign-blind, so it ranked *inhibitory* and *electrically
> silent* neurons as the strongest drivers. Of the five originally listed: DNg74_a scored −212.7
> (rank 1279 of 1279, i.e. the strongest **suppressor**), DNd03 −108.9, DNg108 −178.2, while DNg34
> and DNge149 both score **exactly 0.0** — unclear/modulatory neurotransmitter means `sign = 0`
> and they transmit nothing in our model. Do not use the old list.

Ranked with the **live formula** (`log1p(count) * sign * confidence * inh_attenuation * scale`),
summed onto interneurons that reach LF motor neurons:

| DN | bodyId | summed PSP (signed) | note |
|----|--------|--------------------|------|
| DNg100 | 10056 | **+406.3 mV** | strongest excitatory driver |
| pIP1 | 10030 | +296.3 | |
| DNg37 | 10506 | +294.6 | |
| DNg101 | 11527 | +283.9 | |
| DNge073 | 11737 | +279.7 | |
| aSP22 | 10090 | +278.8 | |

**Verify these too.** They come from my reimplementation of the formula, not from the code path
itself — recompute inside the harness where the weights are actually built.

So there is a real tension to resolve rather than paper over: **DNa02 is the behaviourally
identified walking command, but anatomically it is a weak driver of front-leg motor neurons.**

Report both. Test DNa02 because it is the biologically meaningful command, *and* test a strong-DN
set (from the corrected table) because it establishes whether the outbound path can conduct at all.
If DNa02 fails where DNg100 succeeds, that is an interesting result about our model, the connectome,
or the assumption that DNa02 drives front legs — say which you think it is, and why.

Also worth checking: DNa02's own 537th/66th ranking was computed with the same flawed shortcut, so
**recompute DNa02's rank under the live formula too.** It may be better or worse than stated.

**Lesson worth carrying:** the first version of this ranking was computed from the formula as
written in a `network.py` *comment* rather than the code, and dropping `sign`/`confidence` inverted
it. Connectome adjacency is not drive — a strong anatomical connection can be inhibitory or, if the
neurotransmitter prediction is unclear, electrically silent (`sign = 0`). Always carry sign.

## Constraints

- **Settle ~3000 physics steps before measuring** (`dt = 0.1 ms`). We have corrupted a measurement
  this way before.
- **Restore `data.act` between conditions**, not just `qpos`/`qvel` — muscle activation has its
  own 0.1/0.4 ms dynamics.
- **Frozen-physics control at every condition** — pin `qpos`/`qvel`/`act` so nothing can move,
  with all neural drive unchanged. Anything that fires in both conditions did not hear from the
  body. This control caught a real ambiguity at Level 1 and is non-negotiable.
- **Scope: 52 of 64 LF motor neurons** (excludes 6 tarsus — FlyMimic welds all 5 tarsus segments —
  and 6 `ltm*` long-tendon).
- Body is `MusculoskeletalFly` + `MusculoskeletalWorld` (tethered, 15 LF Hill-type muscles).
- The force model is now **on by default** in `MuscleDecoder` (per-class force per spike). Use it.
- Reuse `body_wiring.py` — it already has the lockstep loop, the frozen-physics mode, the
  background sweep, and the settle assertions. Do not rebuild them.

## Gotchas that have burned us

- In `connectivity.npz`, `sources`/`targets` are **row indices into meta.csv, NOT bodyIds**, and
  `weights` is synapse *counts* (1-1032), not mV. Mixing these up returns zero results silently
  rather than erroring.
- A type name can cover **several cells across sides and segments** — `IN21A004` has 6 cells and
  only the left-T1 one contacts left-front motor neurons; the other five contact zero. Resolve by
  bodyId, and report per-cell rather than per-type.
- `DNa02` has 2 cells with different bodyIds (10360, 523769). Do not pool them silently.

## Verification standard

Every number from a real run — `SpikeMonitor` counts, not computed predictions. This project had a
failure of exactly that kind: a demo printed "60.68 pA" as evidence the encoder worked, when
60.68 pA is 0.38× rheobase and nothing could ever have fired. **A current is not a spike.**

**Five "findings" on this project turned out to be our own unexamined defaults** read back as
properties of the fly: an unsourced `max_rate = 200 Hz`; "the 20 ms STDP window"; a never-swept
protocol rate; a latency called disqualifying against a non-deadline; and relay neurons pinned at
`V_rest` with no background. Before reporting any number as a property of the biology, ask whether
it is instead a property of a value we chose. **Finding a sixth would be a good outcome.**

## Report

Which DN sets conduct and which do not, with per-cell detail. First-spike latency per stage
(DN → relay → motor neuron). How many of the 52 in-scope LF MNs fire. Which of the three
resolutions (summation / background / co-activation) was necessary — and whether any single one
sufficed. The frozen-physics control result for every condition. Anything you could not verify,
flagged rather than smoothed over.
