# Sensorimotor Loop Latency Fits the STDP Window — With a Firing-Rate Floor

**Date:** 2026-08-17
**Experiment:** Measure the motor→muscle→joint→sensory round-trip on FlyMimic, and build
the connectome-driven sensory encoder and motor decoder for LF babbling

## What We Did

Three things, all on the full VNC (25,635 neurons) and the FlyMimic musculoskeletal model:

1. Traced the proprioceptive return path in the connectome (sensory → motor, direct and
   1-hop) to establish whether a reflex loop exists in the wiring.
2. Built two modules: `proprioceptive_encoder.py` (joint state → per-afferent current) and
   `muscle_decoder.py` (motor firing rates → 15 Hill-type muscle activations).
3. Measured actual physics latency: how long after a muscle activates does the joint move,
   as a function of activation level and neuron recruitment.

## What We Observed

**The loop exists structurally.** 134 direct monosynaptic sensory→motor synapses (22 of 65
afferents onto 46 of 64 motor neurons), plus 19,565 one-hop paths via 736 local
interneurons reaching all 64 motor neurons. Strongest relay: SNpp51 → IN21A004 → Ti flexor
(weight product 25,149).

**Latency is inertial, not accumulative.** Tendon force rises in **0.2 ms** regardless of
activation level. Joint movement takes **3.2–15.5 ms**, set by joint mass, damping (0.02),
and stiffness (0.4).

| activation | t_move (ms) |
|-----------|-------------|
| 0.05 | 15.5 |
| 0.20 | 7.2 |
| 0.40 | 5.0 |
| 1.00 | 3.2 |

**Round-trip fits the 20 ms STDP window — but only above a firing-rate floor.** Chaining
rate → activation → latency on `LFTibia_flex` (16-neuron pool), round-trip = t_move + 2 ms
neural estimate; `--` means no closure within 20 ms:

| recruited | 30 Hz | 50 Hz | 80 Hz | 120 Hz | 200 Hz |
|-----------|-------|-------|-------|--------|--------|
| 1/16  | -- | -- | -- | -- | 13.8 |
| 2/16  | -- | -- | 14.6 | 11.5 | 8.9 |
| 4/16  | -- | 15.6 | 11.5 | 9.1 | 7.4 |
| 8/16  | -- | 12.0 | 9.1 | 7.7 | 6.2 |
| 12/16 | 16.1 | 10.8 | 8.3 | 6.8 | 5.6 |
| 16/16 | 14.3 | 9.5 | 7.5 | 6.3 | 5.2 |

**The size-principle bug in motor decoding was real and severe.** The previous
`_decode_biological()` averaged per-neuron offsets across the 8 neurons sharing each
actuator, and a silent neuron contributed −0.3 rad rather than zero. Measured: 1 of 8
neurons firing at 200 Hz drove the joint **backwards** (−0.225 rad); 4 of 8 were needed
just to reach neutral. After switching to a size-weighted sum with silence = zero:

| n firing @200 Hz | new activation | old offset |
|---|---|---|
| 1  | 0.137 | −0.262 rad |
| 4  | 0.389 | −0.150 |
| 16 | 1.000 | +0.300 |

The same bug existed in a second copy inside `FunctionalTrainedController`.

**Sensory encoding is joint-specific and verified.** Driving `LFTibia_flex` moves the
tibia-velocity bucket 0.68 → 60.68 pA while coxa stays flat (0.31 → 0.58). Driving
`LFF_trochanter_extensor` raises trochanter-position 16.6 → 21.0 pA.

## What This Means

**Level 1 is viable, but the protocol needs two corrections that would otherwise have
produced false negatives.**

1. **STDP anti-causality.** Motor fires at t=0, sensory feedback returns at t≈10 ms — that
   is post-before-pre, which standard asymmetric STDP *depresses*. Naive babbling would
   systematically weaken the very reflex arcs it should strengthen, and the symptom would
   look like "no loop closure detected." Fix: sustained 30–50 ms bursts so later motor
   spikes follow the sensory spike causally.

2. **Firing-rate floor.** Below ~30 Hz at full recruitment the joint moves too slowly for
   feedback to return in time. Weak drive yields *no detectable loop*, not a small one.
   Babbling must target 50–80 Hz or higher.

**The single-neuron premise is the weakest part of Level 1.** The epic assumes stimulating
one motor neuron produces detectable feedback. One neuron closes the loop only at ~200 Hz,
with 6 ms of margin, and that margin rests on an unmeasured 2 ms neural term. Small
co-firing groups may be necessary — which dilutes the "one motor neuron learns its own
effect" claim.

**Scope is narrower than assumed:** 52 of 64 LF motor neurons are valid targets. 6 tarsus
neurons have no joint to move (FlyMimic welds all 5 tarsus segments, though the real fly
innervates them — `synweight` up to 3292), and 6 `ltm*` long-tendon neurons have their
multi-joint action collapsed into single-joint muscles. Counting these 12 would measure
FlyMimic's limitations rather than connectome biology.

## Corrections to Prior Documents

Several claims in docs 13/14 were wrong and are now fixed:

- **"LF has 88 motor neurons"** — wrong. No wing-muscle MN exits via a leg nerve (they use
  ADMN/MesoAN/PDMNa/PDMNp). The number is **64**.
- **Laterality used `somaSide`** — that column is NaN for all 65 afferents. Correct column
  is `rootSide` (45 L / 20 R). Per-type counts in doc 14 §4–5 were inflated ~2×; "SNpp39
  n=8" is only 3 on the left.
- **Per-leg counts off by up to 6, and backwards** — LH has 66, the *most* of any leg,
  where the doc said hind legs had the fewest.
- **"Ascending neurons carry the return path"** — biologically inverted. The loop runs
  through local ProLN afferents and local T1 interneurons.
- **Femur vs tarsus welding conflated** — femur welding is anatomically correct (no femur
  MN exists in the connectome; trochanter/femur are fused in *Drosophila*). Tarsus welding
  is a genuine model defect.

Two of my own claims during this session were also wrong and worth recording as method
lessons: I reported "no ground geom" after grepping for the substring `ground` when the
geom is named `floor`, and I reported contact force as 0.0 by reading `d.cfrc_ext` without
first calling `mj_rnePostConstraint` (real value: 326.5). I also measured from a leg that
had settled only 500 steps when settling takes ~3000.

## Next Steps

1. **Measure the 2 ms neural propagation term** on the real spiking network. Everything in
   the scale table depends on it.
2. **Wire `MusculoskeletalFly` into the training harness.** `functional_training` builds
   `NeuroMechFly` (66 position servos), so the 15 muscles are computed but inert.
3. **Switch the SNpp53 channel to `d.actuator_force`.** Ground reaction force is
   identically zero in the tethered world — the tarsus clears the floor by 0.97 and the
   only contacts are Thorax↔Coxa self-collisions.
4. **Retune `motor_gain` / `baseline_hz`.** Activation is now unipolar [0,1]; `baseline_hz
   = 15` is a hard deadband, so if tonic motor rates sit near 15 Hz the decoder reads dead.

## Artifacts

- `src/digital_drosophila/proprioceptive_encoder.py` — 41 LF afferents, 8 role buckets
- `src/digital_drosophila/muscle_decoder.py` — 58 MN → 15 muscles, size-weighted
- Demos: `uv run python -m digital_drosophila loop proprio_test`;
  `MUJOCO_GL=egl uv run python -c "from digital_drosophila.muscle_decoder import run_muscle_decoder_demo; run_muscle_decoder_demo()"`
- Idea doc: [2026-08-17-sensorimotor-babbling.md](../ideas/2026-08-17-sensorimotor-babbling.md)
