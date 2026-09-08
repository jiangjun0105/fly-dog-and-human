# The Mechanical Chain Conducts; the Return Limb Does Not

**Date:** 2026-08-18
**Experiment:** Child 0 of the Level 1 babbling epic — fix the neural model (0a), calibrate
the sensory encoder (0b), wire the musculoskeletal body and run the exit gate (0c)

## Summary

Motor pool → muscle → joint → **afferent spike** now works end to end, named and timed. The
return limb — afferent → interneuron → a neuron presynaptic to the origin motor neuron —
**does not fire under any physically reachable drive.**

The reason is measured rather than inferred, and it is not what any of our documents
predicted. It is **not** latency, **not** firing rate, and **not** sensory calibration. It is
**afferent recruitment breadth**: the interneurons capable of relaying the signal integrate
across all three joint groups, and a single-joint movement can only ever recruit about a
quarter of any one relay's inputs.

## What We Did

Three issues, two run in parallel, one after:

- **0a** — added per-synapse transmission delay and STDP soft-bounding
- **0b** — calibrated the proprioceptive encoder against real LIF spike counts
- **0c** — wired `MusculoskeletalFly` into the harness and ran the exit gate

Reproduce: `python -m digital_drosophila check neural_model`,
`... loop sensory_calibration`, `... check body_wiring`.

All on the full VNC (25,635 neurons / 4,114,854 synapses) with the network and physics in
lockstep at `dt = 0.1 ms` (one Brian2 step, one `mj_step`, re-encode).

## What We Observed

### The convergence floor: one neuron cannot signal to one neuron

**The single most consequential result, and it was not something we set out to test.**

A LIF cell fires only if charge arrives before the membrane leaks it. For a presynaptic
neuron at 2× rheobase (ISI 8.93 ms), one PSP must exceed
`20 mV · (1 − e^(−0.893)) = 11.8 mV`. **The largest weight anywhere in the connectome is
3.98 mV.** So no single connectome synapse can fire a postsynaptic cell at any presynaptic
rate — propagation is inherently a population phenomenon.

Latency is therefore a function of *convergence*, not hop count:

| converging neurons | latency, one hop |
|--------------------|------------------|
| 60 | 12 ms |
| 111 (median in-degree) | 4.4 ms |
| 150 | 2.6 ms |

A 4.6× spread across the same single hop. This retires our per-hop budget ("2-4 ms direct,
5-8 ms via one interneuron") as ill-defined, and with it the whole
`recruited × rate → round-trip` scale table.

Rate cannot substitute for numbers. Accumulation from repeated spikes converges to
`w/(1 − e^(−ISI/τ))`, capped at **×5.52** by the 2 ms refractory period. The strongest
synapse in the connectome, driven at the physiological maximum, reaches 21.96 mV — barely
threshold. The median excitatory synapse tops out at 3.52 mV and **can never** get there.

### The neural model was optimistic in two ways, both now fixed

Per-synapse delay (0.8-1.5 ms, seeded) is live on both backends, costing **+1.20 ms direct /
+2.40 ms via one interneuron**, identical on Brian2 and PyGeNN. Every timing measured before
today is optimistic by 1-3 ms per hop.

STDP soft-bounding is live, with `w_max` derived from the connectome rather than chosen:
`log|w|` is near-Gaussian (skew 0.14), so `exp(μ+3σ)` per polarity gives **3.56 mV
excitatory / 1.66 mV inhibitory**. Split by polarity because inhibition carries an extra 0.5
attenuation; one shared ceiling would let inhibition grow to 2× anything real. Over
400 × 40 ms unmodulated bursts: 0.600 → 3.55996 mV, **zero crossings**, increments decaying
geometrically. The same input under the old additive rule reached **78.5 mV = 22× w_max** —
the runaway was real, not hypothetical.

### Sensory calibration: three defects, only one of which we knew about

The known one: `gain_pa = 75.0` against a **measured** rheobase of 200 pA (200 pA → 0.0 Hz,
201 pA → 18 Hz). Nothing could ever have fired. Calibrated gains are now **position 700,
velocity 1200, force 1400, posture 2000 pA** — per-modality, because the channels never reach
comparable activations (position peaks 0.77, force 0.51, posture 0.30).

Two we did not know about:

- **The "dead" ground-reaction channel was not zero — it was a constant 116.2.** True
  LF↔floor contact is exactly 0.0, but the code summed *any* LF-involving contact, capturing
  Thorax↔Coxa interpenetration. Worse than dead: non-zero but unmodulated, so it looked alive
  while carrying no information. Now reads tendon tension (`d.actuator_force`): 1.373 at rest
  → 76.7 under drive.
- **The position channel was non-monotonic.** Referenced to MJCF `springref` (which is not the
  settled posture), activation ran 0.384 → 0.001 → 0.424 as the tibia swept through — the same
  current at two different postures, independent of any gain error. Now referenced to measured
  `SETTLED_LF_ANGLES`.

Position remains **unsigned**: flexion +0.778 rad and extension −0.769 rad produce *exactly*
152 Hz. Acceptable for Level 1 ("did this MN move this joint"); blocks Level 2
agonist/antagonist assignment.

### Velocity leads — but only on the tibia

Within a 50 ms burst, position must wait for displacement to integrate while velocity peaks
early. On the tibia flexor: **velocity 11.6 ms → position 35.0 → posture 37.5; force never.**

**The ranking is joint-dependent, which none of our documents anticipated.** On
`LFF_trochanter_extensor`, **force fires first (17.3 ms) and velocity never fires at all**
(peaks 13 pA against 200 pA rheobase). On `LFF_sterno-tergo-trochanter_extensor_b`, position
wins. The trochanter is slow, heavily loaded, and the only group with force afferents.
Child 1 babbles all three groups, so "velocity is first" is a tibia fact, not a general one.

### The planned protocol is below the conduction floor

**The ~4-neuron / 80 Hz protocol specified in every one of our documents does not conduct.**
Activation 0.162, velocity peak 135 pA against 200 pA rheobase, **zero afferent spikes**.

| condition | outcome |
|-----------|---------|
| 4 neurons @ 80 Hz | **no afferent spike** |
| 2 neurons @ 200 Hz | first spike 27.1 ms |
| 14 neurons @ 80 Hz | first spike 31.7 ms |
| any pool @ 30 or 50 Hz | **nothing conducts** |

Observed latencies span 6.7-48.3 ms.

> **Correction (2026-08-18):** this originally read "mostly outside the 20 ms STDP window,"
> implying latencies above 20 ms could not be learned. That misread our own implementation —
> `tau_stdp_ms = 20` sets eligibility *magnitude*, while `tau_eligibility_s = 1.0` (**1000 ms**)
> carries the credit forward. Latencies in this range are weaker, not excluded.

### The return limb: the exit gate fails

Recomputed from the live code path (the static estimates in the issue were optimistic):

| return path | convergence | summed PSP if all fire at once |
|-------------|-------------|-------------------------------|
| afferent → MN (direct) | median 3, max 7 afferents/MN | median 1.70, max **7.97** mV |
| afferent → interneuron (1,339 relays) | up to 16 | median 1.02, max **15.56** mV |

Against the ~11.8 mV single-shot bar, only **5 targets** clear it and **nothing reaches
20 mV**. Forcing all 41 afferents to spike in one synchronous volley fires **nothing** (best
relay 14.95 of 20 mV).

**Sustained bursting does succeed where a single volley cannot** — 80 Hz forced drive fires 1
relay; 200 Hz fires 13, of which **5 are presynaptic to in-scope LF motor neurons**:
`IN23B024`, `IN21A004`, `IN13A002`, `IN13B010`, `IN13A006`. So burst duration is load-bearing,
exactly as suspected.

**But physics never delivers that drive.** The best physically reachable condition fires only
**22 of 41 afferents**, delivering **4.63 of 15.56 mV** to the strongest relay. **Zero
downstream neurons fire.**

### Why: the relays are multi-joint integrators

The gap is not rate and not gain — it is *which* afferents fire. Every top relay draws from
all three joint groups, and no single group supplies more than ~47% of its input:

| relay | total | coxa | tibia | trochanter | largest share |
|-------|-------|------|-------|------------|---------------|
| IN23B024 | 17.65 mV (16 aff) | 4.28 (5) | 5.14 (4) | 8.22 (7) | 47% |
| INXXX007 | 14.40 mV (10 aff) | 4.36 (3) | 4.64 (4) | 5.41 (3) | 38% |
| IN09A022 | 14.38 mV (14 aff) | 4.54 (5) | 4.06 (3) | 5.78 (6) | 40% |
| IN09A016 | 13.92 mV (12 aff) | 4.40 (3) | 4.46 (5) | 5.06 (4) | 36% |
| IN01B007 | 11.82 mV (8 aff)  | 4.76 (3) | 3.51 (3) | 3.55 (2) | 40% |

(Proportions computed with the weight formula from a `network.py` comment; absolute values run
~13% high against the live path — 17.65 vs 15.56 for IN23B024 — but the *shares* are the
point.)

A single-joint movement recruits ~4 of any relay's ~16 inputs, which is why the best real
condition delivered 4.63 mV. **This is a one-group share of a three-group requirement.**

### The afferents rest net-inhibited — the tonic-bias question is settled

The 41 LF afferents receive 642 synapses (median 15 each), **68.1% GABAergic**, 72.3%
inhibitory by sign; **36 of 41 are net-inhibitory**. Driving the network but not the afferents
leaves all 41 **silent**, with an offset of **−0.63 to −1.94 mV (−6.3 to −19.4 pA)**, worst
single afferent −64.7 pA.

We had been considering adding a **tonic excitatory bias** to hold afferents near threshold,
by analogy with real proprioceptors. The measurement says the network's own effect is to push
them **down**. A hardcoded excitatory bias would have been fighting the connectome's own gain
control. Not implemented; 0b's calibrated gains need +2-9% to compensate (worst case +8-31%,
position most exposed).

## What This Means

**Level 1 as specified cannot close.** Not because the wiring is absent — 134 direct synapses
and 19,565 one-hop paths are real — but because a single-joint twitch cannot recruit enough
afferent breadth to fire the relays that would carry the signal home. This is the distinction
we added to doc 12 this morning, now demonstrated: *structural presence does not imply
conduction*.

Child 1 would have reported "no loop closure." That result would have been uninterpretable.
It is now interpretable, and the diagnosis names its own candidate fix.

**The fix, if there is one: multi-muscle, multi-joint twitches.** If relays require input
across joint groups, single-muscle babbling is the wrong stimulus. Driving several muscles
across the coxa/trochanter/tibia groups simultaneously would recruit across groups.

This is *also* what real spontaneous twitches do — fetal motor activity recruits synergies
spanning multiple joints, not isolated muscles. Like the earlier single-neuron → pool
correction, it is a **correction toward biology**, not a workaround for a simulation limit.
That is now the second time this experiment has pushed us from an artificially clean stimulus
toward a messier and more biological one.

**Unresolved tension.** Level 1's question is "which motor neuron controls which joint." If
closure requires simultaneous multi-joint movement, the answer may be unavailable at this
level — the feedback would report *that the leg moved*, not *which muscle moved it*. Testing
multi-muscle drive is cheap and worth doing; but if it works, Level 1 is answering a coarser
question than we set out to ask, and that should be stated rather than glossed.

## Corrections to Prior Documents

- **Retired the `recruited × rate → round-trip` scale table.** Two independent faults: a flat
  2 ms neural term (latency depends on convergence, not hop count) and a physics term
  measuring the wrong event (`t_move` = joint *starts* moving, which is strictly earlier than
  an afferent spiking). The two halves never chained; every margin was optimistic by an
  unmeasured amount.
- **"2-4 ms direct / 5-8 ms via one interneuron"** — withdrawn as ill-defined without a stated
  pool size.
- **"~4-neuron pools at ~80 Hz"** — measured not to conduct. Every document carrying this
  protocol needs revision.
- **"Ground reaction force is identically zero"** — it was a constant 116.2 from
  Thorax↔Coxa interpenetration.
- **"Velocity closes the loop"** — true for the tibia only; the trochanter closes on force.
- **The anti-causality trap does not exist in our implementation.** Our rule is additive in
  both directions (pre-spike adds `Apost`, post-spike adds `Apre`, both positive); nothing
  decrements. The trap presumes an asymmetric rule with a depression term. The sustained-burst
  protocol may still be right — temporal summation is now known to be load-bearing — but not
  for the reason originally given. Blocks Child 2 only.

## Method Notes

- 77 full-VNC synapses *start* above their own `w_max` (real distribution outliers). They
  cannot grow and depress normally — but "synapses at the ceiling" in a future experiment
  would be initial values, not STDP growth.
- Brian2 rounds `delay/dt` half-*up* in SI seconds; `np.rint` rounds half-to-even. At the
  1.15 ms range midpoint that is 12 steps vs 11 — a silent 0.1 ms/hop divergence between
  backends, caught only because delay agreement was asserted across 11 values.
- Poisson input/background synapses deliberately carry **no** delay: they are virtual sources
  for drive originating outside the modelled population, not identified presynaptic neurons.
- `data.act` must be restored between conditions, not just `qpos`/`qvel` — muscle activation
  has its own 0.1/0.4 ms dynamics. The pre-existing `proprio_test` demo does not do this, so
  its third condition is contaminated by its second.

## Not Verified

- **No negative control for the neural shortcut.** There are 0 direct motor→afferent synapses
  but **34 relay neurons** forming motor→X→afferent paths reaching 27 of 41 afferents
  (PSP median 1.62, max 5.10 mV). Sub-threshold alone, but the encoder parks afferents near
  threshold, so a shortcut could supply the final few mV. The needed control — stimulate with
  physics frozen, confirm no afferent spikes — was never specified and was not run.
- The 200 Hz ceiling test drove afferents via `SpikeGeneratorGroup`, bypassing the presynaptic
  inhibition measured above. **The real closure bar is therefore harder than that result
  suggests.**
- Only 5 of 15 muscles swept per-driver.
- 0c ran CPU Brian2 only; the GPU path was untouched (0a showed the backends agree on delay).

## Artifacts

- `src/digital_drosophila/network.py` — delay + soft-bounding helpers, `w_max` derivation
- `src/digital_drosophila/neural_model_checks.py` — `check neural_model`
- `src/digital_drosophila/proprioceptive_encoder.py` — calibrated gains, tendon-force channel
- `src/digital_drosophila/body_wiring.py` — `check body_wiring` (the exit gate)
- Issues: [0a](../issues/2026-08-17-babbling-child0a-neural-model.md) ·
  [0b](../issues/2026-08-17-babbling-child0b-sensory-calibration.md) ·
  [0c](../issues/2026-08-17-babbling-child0c-wire-body.md)
- Idea doc: [2026-08-17-sensorimotor-babbling.md](../ideas/2026-08-17-sensorimotor-babbling.md)
