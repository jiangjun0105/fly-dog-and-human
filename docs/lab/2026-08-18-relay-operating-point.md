# The 28.6 ms Synaptic Floor Was Our Own Silent Network

**Date:** 2026-08-18
**Experiment:** Test whether the afferent→closure lag floors at 28.6 ms because
relay interneurons were held at exactly `V_rest = −70 mV`, a state no VNC
interneuron occupies

## Summary

**The floor moves, and it was ours.** `run_lockstep_multi` zeroed `drive` for every
neuron outside the driven motor pool, so relay interneurons sat at exactly `V_rest`
and had to be pushed the whole 20 mV to threshold by the afferent volley alone. That
is the mechanism we published as the 28.6 ms floor. Giving the relays a
**sub-threshold operating point** — background current applied to the network minus
the driven pool and the afferents — collapses the lag from **+28.8 ms to +5.8 ms**,
a **5.0×** compression, with the frozen-physics control **silent at every usable
level** (0 closers, 0 afferent spikes, 0 downstream neurons).

**+5.8 ms lands inside the published 3-6 ms band** (Tuthill & Wilson 2016, cited in
Karashchuk et al. eLife 2025), which our own model previously missed by 5×.

**So "the return path is too thin to conduct" is weakened, and the 15.56-vs-20 mV
gap is partly an artefact of testing in an unnaturally silent network.** State it
plainly: the gap is real arithmetic about one volley, but the inference "therefore
~26 ms of integration is a structural property of the connectome" does not follow. It
was a property of the operating point we chose by omission.

**A usable window exists and it is wide.** 0-125 pA constant current (0-12.5 mV of
idling depolarisation) and 0-11 Hz Poisson. Above that the *recurrent network
ignites* — which is a second, separate confound from spontaneity, and it was the
easier one to have missed.

**Unaffected, as predicted:** the broadcast finding (`IN21A004` bodyId 800802 → 46 of
64 LF MNs) is pure anatomy. It does not depend on any operating point and is untouched.

## What We Did

Reproduce: `python -m digital_drosophila check background` (`--quick` for fewer
levels). Full VNC (25,635 neurons / 4,114,854 synapses), physics and network in
lockstep at `dt = 0.1 ms`, 3000-step settle, `data.act` restored between conditions,
force model ON, and the class-specific drive protocol that closes (slow MNs tonic
50 Hz, fast/intermediate 2 spikes then silent).

Background is applied to every neuron **except** the driven motor pool and the 41
afferents, so the changed variable is the relays' idling point and not the motor
drive or 0b's calibrated sensory gain. A **200 ms background settle** runs before
each stimulus with the motor drive off and the afferents held at their settled
resting current, so the relays are *at* their operating point rather than climbing
towards it; those spikes are excluded and `t = 0` is stimulus onset.

Both arms are run because they are not equivalent — constant current shifts the mean
only, Poisson (`create_background_drive`'s 1.3 mV per spike, 50 sources) shifts the
mean *and* adds variance.

**Every background level runs with the frozen-physics control.** A closure counts
only if the closer fired live, did **not** fire frozen, and fired **after** the first
afferent spike.

Every verdict is a `SpikeMonitor` count. The `idle dV` column is a `StateMonitor`
read and is the one voltage that is load-bearing here — it is the thing being
manipulated — so it is reported as measured, never as `dV = I·R`.

## The Baseline Reproduces the Published Number Exactly

This is the check that makes the rest a measurement rather than a new experiment.
At 0 pA — the condition every previous sweep ran — this harness returns
**closure 35.4 ms, lag +28.8 ms, 41/41 afferents, 1.173 rad, 6 closers**
(`IN21A004`, `IN13A006`, `IN21A006`, `Tergotr. MN`, `IN13A002`, `IN23B024`), against
the lab entry's slow50+fast2 row of **35.4 ms / 1.173 rad / 41 afferents**. Identical.
So the background is the one changed variable.

## The Sweep

`3group:strongest x3`, slow 50 Hz + fast 2 spikes, 200 ms burst, frozen control at
every point. `poolx` = driven-pool rate ÷ its rate at zero background. `share` =
closers as a fraction of the 1,980 neurons presynaptic to some in-scope LF MN.

| background | idle dV (mV) | net Hz | poolx | aff | closers | share | **frozen closers** | t_aff | t_close | **lag** | exc (rad) | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **0 pA** | +0.000 | 0.13 | 1.00 | 41/41 | 6 | 0.3% | **0** | 6.6 | 35.4 | **+28.8** | 1.173 | usable (baseline) |
| 25 pA | +2.500 | 0.13 | 1.00 | 41/41 | 12 | 0.6% | **0** | 6.6 | 31.0 | +24.4 | 1.173 | usable |
| 50 pA | +5.000 | 0.14 | 1.02 | 41/41 | 17 | 0.9% | **0** | 6.6 | 26.0 | +19.4 | 1.173 | usable |
| 75 pA | +7.500 | 0.15 | 1.02 | 41/41 | 37 | 1.9% | **0** | 6.6 | 21.2 | +14.6 | 1.173 | usable |
| 100 pA | +10.000 | 0.19 | 1.06 | 41/41 | 58 | 2.9% | **0** | 6.6 | 16.8 | +10.2 | 1.173 | usable |
| 115 pA | +11.500 | 0.20 | 1.00 | 41/41 | 86 | 4.3% | **0** | 6.6 | 12.6 | +6.0 | 1.173 | usable |
| **125 pA** | **+12.500** | 0.24 | 1.04 | 41/41 | 125 | 6.3% | **0** | 6.6 | **12.4** | **+5.8** | 1.173 | **usable — best** |
| 130 pA | +13.000 | 0.62 | **1.43** | 41/41 | 302 | 15.3% | 0 | 6.6 | 12.2 | +5.6 | 1.283 | CONFOUNDED (pool runaway) |
| 135 pA | +13.500 | 38.26 | **6.02** | 41/41 | 1242 | 62.7% | 0 | 6.6 | 12.2 | +5.6 | 1.423 | CONFOUNDED |
| 150 pA | +15.000 | 50.93 | **7.35** | 41/41 | 1417 | 71.6% | 0 | 6.6 | 8.2 | +1.6 | 1.446 | CONFOUNDED |
| 175 pA | +17.500 | 81.96 | **8.98** | 41/41 | 1685 | 85.1% | 0 | 6.6 | 7.6 | +1.0 | 1.446 | CONFOUNDED |
| 190 pA | +19.000 | 97.52 | **10.41** | 41/41 | 1760 | 88.9% | 0 | 6.6 | 7.5 | +0.9 | 1.446 | CONFOUNDED |
| poisson 5 Hz | +2.480 | 0.13 | 1.02 | 41/41 | 14 | 0.7% | **0** | 6.6 | 31.0 | +24.4 | 1.173 | usable |
| poisson 10 Hz | +5.767 | 0.16 | 1.00 | 41/41 | 62 | 3.1% | **0** | 6.6 | 17.0 | +10.4 | 1.173 | usable |
| poisson 11 Hz | +6.275 | 0.18 | 1.00 | 41/41 | 105 | 5.3% | **0** | 6.6 | 16.8 | +10.2 | 1.173 | usable |
| poisson 15 Hz | +9.535 | 12.93 | **2.43** | 41/41 | 1770 | 89.4% | 0 | 6.6 | 12.2 | +5.6 | 1.304 | CONFOUNDED |
| **poisson 20 Hz** | +12.440 | 35.17 | 5.22 | 41/41 | 1768 | 89.3% | **1952** | 6.6 | — | — | 1.446 | **CONTAMINATED** |
| poisson 22 Hz | +13.666 | 52.09 | 6.54 | 41/41 | 1850 | 93.4% | **1952** | 6.6 | — | — | 1.446 | CONTAMINATED |
| poisson 50 Hz | +9.926 | 164.31 | 10.39 | 41/41 | 1952 | 98.6% | **1952** | 6.7 | — | — | 1.446 | CONTAMINATED |
| poisson 100 Hz | +7.201 | 244.24 | 11.11 | 41/41 | 1952 | 98.6% | **1952** | 6.7 | — | — | 1.446 | CONTAMINATED |
| poisson 200 Hz | +6.066 | 316.61 | 11.91 | 41/41 | 1952 | 98.6% | **1952** | 5.1 | — | — | 1.446 | CONTAMINATED |

The arithmetic in the hypothesis checks out with one correction. At `R_membrane =
100 MΩ`, 1 pA does give 0.1 mV, and the measured `idle dV` matches the open-loop
prediction to 6 decimal places at every current level (50 pA → **+5.000000 mV**
measured). But the predicted ~50 pA / 15 mV-gap point does **not** produce
single-volley closure: at 50 pA the lag is +19.4 ms, not ~2.4 ms. It takes **125 pA**
(a 12.5 mV offset, 7.5 mV of gap) to reach the 3-6 ms band. The direction was right;
the magnitude needed 2.5× more background than predicted, because the relay that
actually closes first receives less than the headline 15.56 mV (see below).

**The feared inhibitory reversal did not happen.** 68% of the input onto the
afferents is GABAergic and deliverable 3 measured them resting net-inhibited
(−6.3 to −19.4 pA), so net suppression was a live possibility. Measured: the effect
is **monotone facilitation** across the whole clean window, and the afferents are
excluded from the background by construction so their operating point is unchanged
(41/41 fire at every level, `t_aff` pinned at 6.6 ms).

## The Two Confounds, Both Real, Both Found by Measuring

**1. Spontaneity — the control the brief demanded.** The frozen-physics control is
**perfectly clean through the entire usable window**: 0 closers, 0 downstream
neurons, 0 afferent spikes, network rate 0.0094 Hz (48 spikes over 200 ms across
25,635 neurons — the driven pool itself, which is what the frozen control is
supposed to show). It breaks abruptly and completely at **poisson 20 Hz**, where the
frozen network fires at 5.0 Hz and **1,952 of 1,980 possible closers (98.6%) fire
with the leg immobilised**. There is no graded false-positive region to trade off
against: the Poisson arm is either silent or saturated.

Note the ordering: `create_background_drive`'s own default of **22 Hz is above the
ignition point**, not below it. The background the training harness runs would make
this experiment uninterpretable.

**2. Recurrent pool runaway — a confound the brief did not ask for, and the one that
would have inflated the result.** The background is withheld from the driven pool,
but the pool is wired to 25,635 neurons that receive it. Above ~130 pA the pool's own
rate runs away: **34 Hz → 48 Hz at 130 pA → 203 Hz at 135 pA → 351 Hz at 190 pA**,
and the excursion grows with it (1.173 → 1.446 rad). Those rows are a *different
motor protocol* — closer to the retired 200 Hz drive — so their faster closure is
partly faster **movement**, which force gain was already known to buy. They are
excluded.

**Without this second check the headline would have been +0.9 ms**, i.e. we would
have reported near-instantaneous closure produced by a 10× motor-drive increase we
did not intend and would not have noticed. The usable answer is **+5.8 ms**, and it
is the honest one.

## What Actually Changes in the Circuit

The closers at 125 pA are not the same population as at 0 pA, and the identity of the
first one changes:

| background | first closer | t (ms) | its afferent PSP | its output onto in-scope MNs |
|---|---|---|---|---|
| 0 pA | `IN21A004` (800802) | 35.4 | 9.48 mV (9/9 aff) | +33.17 mV over 37 syn |
| 100 pA | `AN04B001` (519981) | 16.8 | 8.50 mV (10/10 aff) | +5.64 mV over 6 syn |
| 125 pA | `AN04B001` (519981) | 12.4 | 8.50 mV (10/10 aff) | +5.64 mV over 6 syn |

Two things worth recording. First, `IN23B024` — the 15.56 mV relay the whole
sub-threshold argument was built around — is **the slowest closer at every level**
(57.3 ms at 0 pA, 37.0 ms at 125 pA) and is never the one that closes the loop. The
relay with the largest single-volley PSP is not the relay that conducts; the ones
that do receive 4.75-9.48 mV. That is why 50 pA was not enough.

Second, the closer count grows 6 → 125 and the in-scope MNs reached
monosynaptically grow 1 → 13. So the background does not merely speed the same path
up; it **recruits more of the return path**, and `share` rising to 6.3% is still far
from the saturation regime (62-99%) where the criterion stops discriminating.

## Robustness

- **Settle sufficiency.** At 125 pA, `settle_ms` ∈ {100, 200, 400} gives identical
  results (idle dV 12.484 / 12.500 / 12.500 mV; closure **12.4 ms** in all three;
  125 closers; 0 frozen). The 200 ms default is enough.
- **Second drive protocol.** The cheapest closing protocol from the previous entry
  (slow 30 Hz + fast 1 spike) reproduces the effect: **35.9 → 12.5 ms**, lag
  **+29.3 → +5.9 ms**, 0 frozen closers, `poolx` 1.17, excursion flat at 0.987 rad.
  So the result is not specific to slow50+fast2.
- **Poisson seed sensitivity (3 seeds).** At 10-11 Hz the lag is +10.2/+10.4 ms in
  4 of 6 runs and +19.1 ms in 2 of 6, with idle dV spanning 5.77-9.57 mV and 0 frozen
  closers throughout. The Poisson arm is **noticeably seed-dependent** and the
  constant-current arm is not. Reported as such; the headline number is from the
  deterministic arm.

## What This Means

**The "return path is sub-threshold" claim is weakened, and the correction is ours.**
The 15.56-vs-20 mV arithmetic is right and it does mean one volley cannot fire that
relay from rest. What does not follow is that the ~26 ms of integration is structural.
It was measured with relays pinned at `V_rest` because we never gave them anything
else, and 12.5 mV of physiologically ordinary idling depolarisation — well
sub-threshold, frozen control silent — takes the lag to +5.8 ms, inside the published
band. **This is a fifth "empirical finding" on this project that turned out to be one
of our own unexamined choices read back as a measurement**, and of the same kind as
the 200 Hz: a parameter never swept, treated as a result.

**What survives, unchanged.** The broadcast is anatomy: `IN21A004` bodyId 800802
contacts 46 of 64 LF MNs regardless of operating point. The return is still
predominantly inhibitory (`IN13A009` −20.20 mV, `IN13A006` −18.24, `IN13A002` −12.76
against `IN21A004` +33.17, `IN04B013` +21.78). Closure still requires multi-joint
movement. The frozen control is still clean. **Level 1's specificity problem is
untouched** — indeed the background makes it slightly worse, since 125 closers carry
less origin information than 6.

**What this does not rescue.** Faster closure was never the blocker
(`tau_eligibility_s = 1.0` = 1000 ms), so 12.4 ms instead of 35.4 ms changes no
downstream conclusion about Child 2. The value of the result is that a *stated
mechanism* was wrong, not that a barrier was removed.

## Corrections to Prior Documents

- **"~35 ms is a synaptic floor that no force-per-spike value can lower"**
  ([motor force classes](2026-08-18-motor-force-classes.md)) — the *force* half is
  still right; force cannot lower it. But it is not a floor. **12.4 ms closure /
  +5.8 ms lag**, with the frozen control silent, on the same condition.
- **"The afferent→closure lag is 28.6 ms at best and never lower"** — true across the
  27 conditions run, all of which had zero background. Not a property of the connectome.
- **"~26 ms of that is synaptic integration ... a structural property"**
  ([multi-muscle](2026-08-18-multi-muscle-loop-closure.md)) — retracted as stated. It
  is integration, but the number is set by the relays' operating point, which was an
  unexamined default.
- **STATUS.md "A second bottleneck was found, and it is not force"** — the bottleneck
  is real but it is not anatomical. Needs rewriting.

## Not Verified

- **The background magnitude is not calibrated against any *Drosophila* measurement.**
  125 pA / 12.5 mV is where our model reaches the literature's latency, not a recorded
  VNC interneuron resting offset. The claim is "the silent-network assumption was
  wrong", **not** "12.5 mV is the correct value". No paper was consulted for a VNC
  interneuron `V_m` distribution; that is the obvious next check and it could move the
  usable window.
- **Uniform background is itself an unexamined choice** — the same class of error this
  entry is about. Real tonic drive is heterogeneous, and 68% GABAergic input onto the
  afferents suggests inhibitory cells may need a different level. Untested.
- **Only the excitatory sign was swept.** Negative background (net inhibition, which
  deliverable 3 measured on the afferents) was not tested.
- **The Poisson arm is seed-dependent** (see Robustness) and only 3 seeds were run at
  2 rates. The constant-current arm is deterministic and is what the headline uses.
- **The 130-190 pA rows are reported but excluded**, on a `poolx > 1.25` threshold
  that is a judgement call, not a measured cutoff. At 130 pA (`poolx` 1.43) the lag
  is +5.6 ms and the excursion has moved 9%; a stricter or looser threshold would
  move which rows count, though not the +5.8 ms headline.
- **Whether background changes anything about *training*** (STDP, `functional_training`
  already uses tonic background) was not measured.
- **CPU Brian2 only**; the GPU path was not exercised.
- **Nothing was rerun with the pre-existing sweeps**, so the interaction between
  background and the deliverable 4/5/6 tables is unmeasured — only the two protocols
  above were tested.

## Artifacts

- `src/digital_drosophila/body_wiring.py` — `measure_background_operating_point`,
  `_print_background_sweep`, `run_background`, `open_loop_gap_mV`,
  `BACKGROUND_LADDER_PA`, `BACKGROUND_POISSON_HZ`; `background_pa` /
  `background_poisson_hz` / `background_settle_ms` / `background_seed` in
  `run_lockstep_multi`; `pool_contaminated` and `closer_share` on every row
- CLI: `python -m digital_drosophila check background [--quick]`
- Previous entries: [motor force classes](2026-08-18-motor-force-classes.md) ·
  [multi-muscle loop closure](2026-08-18-multi-muscle-loop-closure.md)
