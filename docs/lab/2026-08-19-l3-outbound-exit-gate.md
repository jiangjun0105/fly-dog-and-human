# The Descending Command Conducts — But DNa02 Does Not, and Co-activation Is the Only Physiological Route

**Date:** 2026-08-19
**Experiment:** Level 3 outbound exit gate — does a descending command make named LF
motor neurons spike?
**Issue:** [L3 Child A: outbound exit gate](../issues/2026-08-19-l3-outbound-exit-gate.md)

## Summary

**The exit gate PASSES, and Level 3 is not blocked.** A descending command fires up to
**50 of the 52 in-scope LF motor neurons**, first spike **1.6 ms** after stimulus onset
at best, with **all four controls clean**. But every part of that sentence needs a
qualifier, and one of them is a retraction of a figure in the spec.

**DNa02 does not conduct at any physiological rate.** At 50 Hz — inside Azevedo's
measured range — DNa02 fires **0 of 52** LF MNs at 0, 75, 100, 115 and 125 pA
background. It only conducts at **500 Hz**, which is this LIF's refractory ceiling and
**3.3× above any recorded *Drosophila* rate**. So "the known walking command drives the
front leg" is not something this model reproduces.

**DN co-activation is the resolution, and it is the only one that works at a
physiological rate.** Twelve cells (6 DN types) at **50 Hz** fire **29/52 at 100 pA and
50/52 at 115-125 pA**. That is the same multi-source correction that rescued Level 1,
one level up, exactly as predicted.

**Neither summation nor background sufficed alone, and neither was strictly
necessary** — the honest answer is that **two of the three are always required**, in any
of three combinations. See the table below.

**The spec's strong-DN ranking is wrong, and the error is the unsigned formula.** The
spec's top-6 (`DNg34`, `DNg74_a`, `DNge149`, `DNg100`, `DNd03`, `DNd02`) ranks 1-7 of
1,279 on the `network.py`-comment formula `log1p(count) * 0.6`. On the **live weight
path** those same cells rank **856th, 1227th, 856th, 2nd, 1220th, 856th** of 855-1218 —
i.e. four of the six are at or below the bottom of the ranking. Recomputed live, the
strongest are **DNg101 (11527 L, 181.6 mV)**, DNg100 (10056 R, 167.3), aSP22 (10090 L,
158.3), DNge073 (11737 R, 156.5), pIP1 (10030 L, 147.5), DNg37 (10506 R, 146.5).

The spec explicitly warned about this ("recompute from the live code path"), and the
recomputation changes the answer rather than refining it.

## What We Did

Reproduce: `python -m digital_drosophila check l3_outbound` (`--quick` for fewer points).

Full VNC (25,635 neurons / 4,114,854 synapses), Brian2 and MuJoCo in lockstep at
`dt = 0.1 ms`, 3000-step body settle, 200 ms background settle, `data.act` restored
between conditions, force model ON, all 15 muscles decoded.

**The stimulus is not the motor pool.** This is the structural difference from every
earlier sweep in `body_wiring.py`: current is injected into **descending neurons only**,
and the 52 in-scope LF motor neurons receive **zero injected current**. They are the
*readout* and have to be fired through 4.1M connectome synapses. They still decode to
the muscles, so the body still moves.

Every number is a `SpikeMonitor` count. Three axes are swept independently so "which
resolution was necessary" is a measurement: DN rate (50 / 200 / 500 Hz), background
(0 / 75 / 125 pA), and DN set size (1 / 2 / 11 / 12 cells).

### The background operating point was set before the first measurement

Per the Level 1 correction. The usable window measured there — 0-125 pA constant — is
what the ladder spans, and `create_background_drive`'s own 22 Hz Poisson default was not
used (it is above the L1-measured spontaneity ceiling).

### Four controls at every condition, and three of them are here because the first pass produced a false positive

| control | what it is | what it caught |
|---------|-----------|----------------|
| **frozen physics** | `qpos`/`qvel`/`act` pinned, all neural drive unchanged | asserted **0 afferent spikes** in all 63 conditions, so no sensory current existed to contaminate the readout |
| **no-stimulus** | same background, DN drive off | **0/52 MNs at every background level**, so no motor spike is spontaneous |
| **cut projection** | the same DNs driven with their **own outgoing synapses zeroed** — they fire but deliver nothing | **0/52 MNs and 0 relays in every one of the 63 conditions.** This is the control that makes the positive rows mean something |
| **sham DN** | matched stimulus onto 2 DNs (`DNg110`/20923, `DNp72`/21031) with **0 mV** live-path projection onto LF-reaching relays but 121-126 mV elsewhere | **0/52 MNs at all 9 rate × background settings** |

The first pass had only frozen + no-stimulus, and read as a clean pass at 125 pA in
conditions where the DN's projection could not plausibly be responsible. The **cut**
control is what settles it: with the projection removed, the identical stimulus at the
identical background fires **nothing**. The **sham** rules out the amplitude.

## The Sweep

`attr` = MNs firing live, minus the no-stimulus control, minus the cut control.
`x_sum` = steady-state PSP multiplier at that rate (×5.52 is the refractory ceiling).

| DN set | cells | rate | bg | relays | MN | cut | sham | attr | t_DN | t_relay | t_MN | exc (rad) |
|--------|------:|-----:|---:|-------:|---:|----:|-----:|-----:|-----:|--------:|-----:|----------:|
| **DNa02 both** | 2 | 50 | 0 | 0 | 0/52 | 0 | 0 | **0** | 18.0 | — | — | 0.001 |
| DNa02 both | 2 | 200 | 0 | 0 | 0/52 | 0 | 0 | **0** | 3.0 | — | — | 0.001 |
| DNa02 both | 2 | 500 | 0 | 1 | 0/52 | 0 | 0 | **0** | 0.0 | 25.4 | — | 0.001 |
| DNa02 both | 2 | 50 | 75 | 0 | 0/52 | 0 | 0 | **0** | 18.0 | — | — | 0.001 |
| DNa02 both | 2 | 200 | 75 | 0 | 0/52 | 0 | 0 | **0** | 3.0 | — | — | 0.001 |
| DNa02 both | 2 | 500 | 75 | 198 | 2/52 | 0 | 0 | **2** | 0.0 | 9.4 | 23.7 | 0.126 |
| DNa02 both | 2 | 50 | 125 | 0 | 0/52 | 0 | 0 | **0** | 18.0 | — | — | 0.001 |
| DNa02 both | 2 | 200 | 125 | 9 | 0/52 | 0 | 0 | **0** | 3.0 | 14.4 | — | 0.001 |
| DNa02 both | 2 | 500 | 125 | 853 | 49/52 | 0 | 0 | **49** | 0.0 | 5.0 | 9.5 | 1.563 |
| DNa02/523769 L | 1 | 500 | 75 | 108 | 4/52 | 0 | 0 | **4** | 0.0 | 13.1 | 33.5 | 0.055 |
| DNa02/523769 L | 1 | 500 | 125 | 442 | 49/52 | 0 | 0 | **49** | 0.0 | 5.1 | 9.5 | 1.562 |
| DNa02/10360 R | 1 | 500 | 75 | 51 | 0/52 | 0 | 0 | **0** | 0.0 | 15.0 | — | 0.001 |
| DNa02/10360 R | 1 | 500 | 125 | 442 | 50/52 | 0 | 0 | **50** | 0.0 | 6.9 | 12.0 | 1.560 |
| **DNg101 (top1 live)** | 2 | 500 | 0 | 60 | 2/52 | 0 | 0 | **2** | 0.0 | 13.6 | 30.3 | 0.387 |
| DNg101 | 2 | 500 | 75 | 379 | 35/52 | 0 | 0 | **35** | 0.0 | 5.6 | 10.5 | 1.224 |
| DNg101 | 2 | 200 | 125 | 651 | 50/52 | 0 | 0 | **50** | 3.0 | 9.6 | 15.7 | 1.560 |
| DNg101 | 2 | 500 | 125 | 753 | 50/52 | 0 | 0 | **50** | 0.0 | 3.1 | **6.1** | 1.565 |
| **top6 live co-activation** | 12 | 200 | 0 | 207 | 3/52 | 0 | 0 | **3** | 3.0 | 9.4 | 15.7 | 0.467 |
| top6 live co-activation | 12 | 500 | 0 | 2498 | 39/52 | 0 | 0 | **39** | 0.0 | 3.3 | 4.9 | 1.219 |
| **top6 live co-activation** | 12 | **50** | **100** | 1229 | 29/52 | 0 | 0 | **29** | 18.0 | 19.2 | 20.6 | 1.190 |
| **top6 live co-activation** | 12 | **50** | **115** | 4500 | 50/52 | 0 | 0 | **50** | 18.0 | 19.2 | 20.5 | 1.561 |
| **top6 live co-activation** | 12 | **50** | **125** | 4702 | 50/52 | 0 | 0 | **50** | 18.0 | 19.1 | 19.6 | 1.558 |
| top6 live co-activation | 12 | 200 | 125 | 4820 | 50/52 | 0 | 0 | **50** | 3.0 | 4.1 | 4.6 | 1.566 |
| top6 live co-activation | 12 | 500 | 125 | 5031 | 50/52 | 0 | 0 | **50** | 0.0 | **1.1** | **1.6** | 1.563 |
| spec strong-DN set | 11 | 500 | 0 | 7 | 0/52 | 0 | 0 | **0** | 0.0 | 21.0 | — | 0.001 |
| spec strong-DN set | 11 | 500 | 75 | 419 | 3/52 | 0 | 0 | **3** | 0.0 | 7.0 | 87.8 | 0.036 |
| spec strong-DN set | 11 | 200 | 125 | 6270 | 49/52 | 0 | 0 | **49** | 3.0 | 14.0 | 27.2 | 1.558 |
| **sham (2 cells, 0 mV onto LF relays)** | 2 | 500 | 125 | 128 | **0/52** | 0 | — | **0** | 0.0 | 7.1 | — | 0.001 |

Full 63-condition table: `python -m digital_drosophila check l3_outbound`.
**20 of 54 real conditions conduct. 0 of 9 sham conditions do. 0 of 63 cut conditions do.**

## Per-stage Latency

Read off the `SpikeMonitor`, from stimulus onset. The `t_DN` column is set entirely by
the injected current's own f-I curve (18.0 ms at 50 Hz = the first ISI at 238.8 pA,
3.0 ms at 200 Hz, 0.0 ms at 500 Hz), so it is a property of the stimulus, not the
circuit. The two circuit terms are DN→relay and relay→MN:

| condition | DN→relay | relay→MN | total DN→MN |
|-----------|---------:|---------:|------------:|
| top6, 500 Hz, 125 pA | **1.1 ms** | **0.5 ms** | **1.6 ms** |
| top6, 200 Hz, 125 pA | 1.1 | 0.5 | 1.6 |
| DNg101, 500 Hz, 125 pA | 3.1 | 3.0 | 6.1 |
| DNa02 both, 500 Hz, 125 pA | 5.0 | 4.5 | 9.5 |
| top6, 50 Hz, 125 pA | 1.1 | 0.5 | 1.6 |
| DNa02 both, 500 Hz, 75 pA | 9.4 | 14.3 | 23.7 |
| DNg101, 500 Hz, 0 pA | 13.6 | 16.7 | 30.3 |

**Both circuit terms are ~1-5 ms when the path conducts well and inflate to 14-17 ms as
the operating point drops.** This is the same relationship the Level 1 background result
found on the return path, now on the outbound side: latency tracks the operating point,
not hop count.

## Which of the Three Resolutions Was Necessary?

The spec asked which was necessary and whether any single one sufficed. Both questions
have clean answers and they are not the ones the spec expected:

**No single resolution sufficed.** At the minimum of each axis with the other two also
minimal, nothing conducts:

| all three minimal | DN rate 50 Hz, bg 0 pA, 2 cells | **0/52** |

**Any two of the three sufficed:**

| combination | example | result |
|-------------|---------|--------|
| summation + background | DNa02 both, 500 Hz, 125 pA | 49/52 |
| summation + co-activation | top6, 500 Hz, 0 pA | 39/52 |
| **background + co-activation** | **top6, 50 Hz, 115 pA** | **50/52** |

**Only the third combination is physiological.** 500 Hz is above the LIF's own 500 Hz
saturation and 3.3× Azevedo's 150 Hz direct-injection ceiling for a leg MN; there is no
measurement of a *Drosophila* DN firing anywhere near it. So the arithmetically
available routes are three and the biologically available route is **one: background +
co-activation**.

**Resolution 3 was the prediction and it is the one that holds.** The idea doc called
co-activation "the most likely answer ... this mirrors Level 1's multi-muscle correction
exactly." It does.

## DNa02 Is the Wrong Stimulus, and We Think It Is the Front-leg Assumption

The tension the spec asked us to report rather than resolve quietly:

**DNa02 fails at every physiological rate, where DNg101 and the top6 set succeed.** Per
cell, on the live weight path:

| cell | side | summed excitatory PSP onto LF-reaching excitatory relays | live-path rank | conducts at 50 Hz? |
|------|------|--------------------------------------------------------:|---------------:|:------------------:|
| DNa02/523769 | L | 71.0 mV | 52 of 855 | **no** |
| DNa02/10360 | R | 23.8 mV | 324 of 855 | **no** |
| DNg101/11527 | L | 181.6 mV | **1** | no (yes at 200 Hz + 125 pA) |
| DNg100/10056 | R | 167.3 mV | 2 | — |
| top6 set (12 cells) | — | — | — | **yes, 50/52 at 115 pA** |

**The two DNa02 cells are not equivalent and were never pooled.** 523769 (L) delivers
**3.0× more** than 10360 (R) onto LF-reaching relays, reaches **52/52** in-scope MNs at
two hops against 10360's **44/52**, and has 12 direct synapses onto in-scope MNs (16.00
mV) where 10360 has **zero**. At 500 Hz / 75 pA the L cell conducts (4/52) and the R
cell does not (0/52). Consistent with 523769 L being the ipsilateral cell for a
**left**-front leg.

**Which explanation do we favour?** Of the three the spec offers — our model, the
connectome, or the assumption that DNa02 drives front legs — **we favour the third, with
a caveat about the second.**

Reasons:

1. **The connectome is internally consistent.** DNa02's left cell reaches 52/52 in-scope
   LF MNs at two hops with max 29.1 mV, and its side asymmetry is anatomically correct.
   It is not disconnected from the front leg; it is *weakly* connected to the
   *excitatory relays* that reach it.
2. **DNa02's published role is steering, not stepping.** It is characterised as a
   turning/heading command that biases an ongoing gait, and in the real animal it acts
   on a walking VNC. A cell whose job is to bias a running CPG would not be expected to
   *initiate* a motor pool from silence, which is what this experiment asks it to do.
   Our stimulus is the wrong question for that cell, not a wrong answer about it.
3. **The caveat on the model.** We cannot rule the model out, because our sign
   assignment is load-bearing here and it is coarse. `NT_SIGN_MAP` gives glutamate −1
   (defensible in *Drosophila*) and gives **weight exactly 0** to dopamine, serotonin,
   octopamine and `unclear` — which is why four of the spec's six "strongest" DNs
   collapse to 0 mV on the live path. `DNge149`, `DNg34` and `DNd02` are all
   `consensusNt = unclear`. That is a modelling choice with a big effect on this
   ranking, and it is not a measurement.

So: **DNa02 is very likely a real walking command that our experiment is asking the
wrong question of**, and the DN ranking we replaced it with is itself sensitive to a
sign convention we chose.

## The Frozen-physics Control at Every Condition

**0 afferent spikes in all 63 conditions**, asserted (`run_lockstep_multi` raises if the
frozen afferent current moves by more than 1e-9 pA). So no sensory current was generated
and nothing in the readout could have arrived by the sensory route.

**At Level 3 outbound the frozen control does not partition the way it did at Level 1**,
and this is worth stating because it is easy to mis-read. The outbound path is purely
neural, so freezing the body cannot block a DN → relay → MN projection — the frozen
control *should* fire motor neurons, and it does (0-50, tracking the live count). Its job
here is the assertion above plus one residual: MNs firing live but **not** frozen and not
in either negative control number **0, 1 or 5** across the sweep, i.e. **at most 5 of 50
motor neurons needed the body to have moved.** The outbound half is ~90-100% feed-forward
neural, as expected.

## Candidate Artefact #6, Tested and Not Confirmed

The spec asked us to look for a sixth self-inflicted artefact. We found a candidate and
it did not survive testing, which is the honest outcome.

**The candidate:** Level 1's background sweep withheld the background from its *driven
motor pool*, so "the usable window is 0-125 pA" was measured with the motor neurons
pinned at `V_rest`. At Level 3 the motor pool is the *readout*, and we left it inside the
background — which at 125 pA holds every motor neuron **12.5 mV** depolarised, so it needs
7.5 mV rather than 20 mV from the descending volley. Inheriting a convention from a sweep
with the opposite roles is exactly the shape of the previous five artefacts.

**Measured both ways, DNa02 at 500 Hz, nothing else changed:**

| background | motor pool in background | motor pool at `V_rest` (L1's convention) |
|-----------:|-------------------------:|----------------------------------------:|
| 75 pA | 2/52 MNs, 23.7 ms | **0/52** |
| 125 pA | 49/52 MNs, 9.5 ms | **44/52**, 13.4 ms |

**Not an artefact.** With the readout held at `V_rest` the command still fires **44 of
52** motor neurons at 125 pA. The convention is worth ~5 motor neurons and ~4 ms, not the
result. Reproduce: `measure_l3_background_convention` in `body_wiring.py`.

At 75 pA it *is* the whole result (2 vs 0), so the convention is load-bearing for the
marginal rows and not for the headline. Both numbers are reported.

## What This Means

**Level 3 is not blocked and the full-loop experiment can proceed.** The outbound half
conducts, with a physiological route (co-activation + background at 50 Hz), a clean cut
control, a silent sham and a silent no-stimulus control.

**But the specificity problem did not go away, it only changed scale — as the idea doc's
Open Question 3 anticipated.** The conducting conditions fire **50 of 52** motor neurons.
Two different DN sets at the same operating point produce sets of motor neurons with
Jaccard overlap up to **1.000**. The Level 1 finding was "the *return* path is a
broadcast"; the Level 3 finding is that **the outbound path is a broadcast too**, at
least in the regime where it conducts at all. A command that fires 96% of a leg's motor
pool says "move the leg", not "move this muscle" — which the idea doc argued is *correct
semantics* for a whole-body command, and it is, but it means the full-loop experiment
should be designed to ask a pattern-level question and not a per-cell one.

**Latency is not a barrier anywhere.** DN → MN is 1.6 ms at best and 30.3 ms at worst,
against a 1000 ms eligibility trace.

## Not Verified

- **Nothing here is calibrated against a recorded DN firing rate.** The 500 Hz arm exists
  only to bound temporal summation and is unphysiological by construction. We did not find
  a *Drosophila* DN rate measurement to bound the 50 Hz arm against either — 50 Hz is the
  LIF's convenient low point, not a measured DNa02 rate. **This is the most likely place a
  seventh artefact is hiding.**
- **The 115 pA threshold for the physiological route is a 3-point measurement**
  (100 → 29/52, 115 → 50/52, 125 → 50/52). The cliff between 100 and 115 pA is not
  resolved and the 0-75 pA region was not run at 50 Hz for the top6 set.
- **The `NT_SIGN_MAP` zero-weight policy is a modelling choice that drives the DN ranking,
  and it is not tested here.** 3 of the spec's 6 strong-DN types are `consensusNt =
  unclear` and therefore contribute **exactly 0 mV on every synapse** in our model — a
  zero sign deletes rather than attenuates. If `unclear` is in fact excitatory (the 56%
  majority class), `DNg34`, `DNge149` and `DNd02` move from the bottom of the ranking to
  near the top and the "DNa02 is a weak driver" conclusion may not survive. **This is
  exactly what `src/digital_drosophila/sign_policy.py` (`check sign_policy`, in progress
  concurrently) sweeps** — arms A=0 / B=+1 / C=−1 — and it explicitly includes the L3 DN
  ranking. **The L3 numbers in this entry are all policy-A (the shipped default) and
  should be re-read against that sweep's result before the DN ranking is treated as
  settled.**
- **Only 6 DN sets were tested** out of 1,305 DNs. "Co-activation works" is demonstrated
  for one 12-cell set chosen by live-path rank; the **minimal** conducting set was not
  found, and the DN-count ladder (2/4/8/16/32/64) was computed statically but not run.
- **Specificity was measured on 3 conditions, not systematically.** The Jaccard figures
  above come from the 50 Hz margin run; a proper origin-discrimination test (does the
  motor pattern differ between DN sets?) is a separate experiment and is the one that
  matters for the full loop.
- **The return half is entirely unmeasured here.** This is the outbound gate only.
  Afferents fire (38/41 in the conducting conditions) and 0-5 MNs needed the body, but
  whether the signal returns to the *originating DN* is the next experiment.
- **CPU Brian2 only**; the GPU path was not exercised.
- **Poisson background was not run at Level 3** — only the deterministic constant-current
  arm, which is the one L1 found seed-independent.
- **One seed.** Synaptic delays are drawn once per network build and the whole sweep uses
  that draw. Level 1 found the constant-current arm deterministic, so this is expected to
  be stable, but it was not checked here.

## Corrections to Prior Documents

- **The L3 spec's and idea doc's strong-DN table (`DNg34` 486.3 mV, `DNg74_a` 480.3,
  `DNge149` 474.6, ...) is retracted.** It used the unsigned formula from a `network.py`
  comment. On the live weight path **3 of those 6 types deliver exactly 0 mV** onto
  LF-reaching excitatory relays (`DNg34`, `DNge149`, `DNd02` — all `consensusNt =
  unclear`, hence sign 0), **2 are net inhibitory** (`DNg74_a` −107.2/−60.5 mV GABA,
  `DNd03` −58.8/−39.6 mV glutamate), and **only `DNg100` is genuinely strong**
  (10056 R, +167.3 mV, rank 2 live-path). Live-path top6: DNg101/11527,
  DNg100/10056, aSP22/10090, DNge073/11737, pIP1/10030, DNg37/10506. Measured
  consequence: the spec's set fires **0/52** at 500 Hz / 0 pA where the live-path set
  fires **39/52**.
- **The spec's "DNa02 ranks 537th and 66th of 1,279"** — the *conclusion* (DNa02 is a weak
  driver) holds, the numbers do not. Live path: **324th and 52nd of 855** DNs with any
  positive projection.
- **"DNa02 → 1 hop: 918 targets, median 0.83, max 4.32 mV, 0 of 918 reach 20 mV"** —
  reproduced almost exactly on the live path: **918 targets, median 0.79, max 4.09 mV, 0
  of 918**. The hop-1 arithmetic was right.
- **"DNa02 → X → LF motor reaches 64 of 64 LF MNs, median 16.9, max 115.7"** — on the live
  path and restricted to the 52 in-scope MNs: **52/52, median 7.73, max 42.34 mV**. Right
  in kind, ~2.7× high in magnitude.
- **The refractory summation ceiling ×5.52 is confirmed by measurement**, not just
  arithmetic: an isolated LIF saturates at 500 Hz and 1/(1−e^(−0.2)) = 5.517. The
  `DRIVE_PA_FOR_HZ` ladder was extended to 250/300/400/500 Hz by the same 1 s spike-count
  method used for the existing entries.

## Artifacts

- `src/digital_drosophila/body_wiring.py` — `measure_l3_outbound`,
  `measure_l3_background_convention`, `dn_cells`, `dn_outbound_arithmetic`,
  `default_dn_sets`, `_l3_row`, `_print_l3_outbound`, `summation_factor`,
  `net_data_sources`, `L3_BACKGROUND_LADDER_PA`, `L3_DN_RATES_HZ`; new
  `drive_idx_pa` / `drive_idx_until_ms` / `cut_source_idx` /
  `background_excludes_pool` arguments on `run_lockstep_multi`; `DRIVE_PA_FOR_HZ`
  extended to 500 Hz
- CLI: `python -m digital_drosophila check l3_outbound [--quick]`
- Previous entries: [relay operating point](2026-08-18-relay-operating-point.md) ·
  [multi-muscle loop closure](2026-08-18-multi-muscle-loop-closure.md)
- **Load-bearing dependency:** `src/digital_drosophila/sign_policy.py`
  (`check sign_policy`) sweeps the `unclear` NT sign that this entry's DN ranking rests
  on. Every L3 figure here is policy A (`unclear` = 0).
- Idea: [full loop / descending command](../ideas/2026-08-19-full-loop-descending-command.md)
