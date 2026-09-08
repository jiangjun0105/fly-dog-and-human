# Sensory → Motor Loop Structure: The Return Path

Data-driven analysis of how proprioceptive sensory neurons connect back
to motor neurons in the VNC connectome, using the Left Front leg as the
test case for sensorimotor babbling.

## 1. The Neurons Involved

**Motor output:** 64 neurons (superclass=`vnc_motor`, subclass=`fl`,
somaSide=`L`), exiting via ProLN nerve to the left front leg muscles.

**Sensory input:** 65 neurons (entryNerve=`ProLN`,
class=`mechanosensory_proprioceptive`) entering via the ProLN nerve.

> ### CORRECTION — these 65 span BOTH sides
>
> The 65 are **not** all left-leg. `somaSide` is **NaN for all 65** —
> afferent somata sit in the leg periphery, not in a neuromere, so the
> laterality column is **`rootSide`**, which splits **45 L / 20 R**.
>
> **Every per-type count in §4 and §5 below therefore over-counts the
> left leg, by roughly 2× for some types.** Worked example: §4 says
> "SNpp39 (n=8)", but that is 5 right + **only 3 left**.
>
> Encoding right-leg afferents from left-leg joint angles is a body-side
> mismatch and would inject fabricated feedback. For LF babbling the
> selection must add `rootSide == "L"` → **45 neurons, 41 encoded after
> excluding ascending**.
>
> `proprioceptive_encoder.py` defaults the side to match the leg. The
> per-type counts below are left uncorrected as the *both-sides*
> figures — read them as upper bounds, and see the bucket table in §5 for
> the real left-side assignment.

Also note `vnc_sensory` is a **`superclass`** value in MANC, not a
`class` value. Of the 65: 58 are `vnc_sensory` (local reflex population),
7 are `sensory_ascending`.

| Sensory subclass | Count | Type codes | Likely function |
|-----------------|-------|------------|-----------------|
| Chordotonal organ | 36 | SNpp39/40/41/43/47/50/51/57/59/60, SApp23 | Joint angle, velocity, vibration |
| Leg (generic) | 23 | SNppxx, nan | Mixed proprioceptive |
| Campaniform sensilla | 4 | SNpp53 | Cuticular strain / force |
| Hair plate | 1 | SNpp45 | Proximal joint position |

## 2. Direct Monosynaptic Connections (Sensory → Motor)

134 direct synapses connect 22 of 65 sensory neurons to 46 of 64 motor
neurons. These are the reflex arcs — no interneurons needed.

Strongest direct connections:

| Sensory type | Motor target | Weight |
|-------------|--------------|--------|
| SNpp51 (chordotonal) | Tergopleural promotor MN | 32 |
| SNppxx (leg) | Ti extensor MN | 28 |
| SNpp51 (chordotonal) | Tergotr. MN | 23 |
| SNpp51 (chordotonal) | Ti flexor MN | 21 |

**22/65 sensory neurons have direct motor connections. These are the
fastest possible loop (body response + 0 synaptic delays).**

## 3. One-Hop Paths (Sensory → Interneuron → Motor)

19,565 unique paths through 736 interneurons connect 57/65 sensory
neurons to all 64/64 motor neurons.

Strongest 1-hop paths (by product of weights):

| Sensory | Interneuron | Motor | w₁×w₂ |
|---------|-------------|-------|--------|
| SNpp51 | IN21A004 | Ti flexor MN | 25,149 |
| SNpp51 | IN13A006 | Ti extensor MN | 21,528 |
| SNpp51 | IN21A004 | Ti flexor MN | 15,352 |
| SNpp39 | IN19A005 | Ti extensor MN | 14,300 |
| SNpp51 | IN21A004 | Ti extensor MN | 13,231 |

**Key interneurons mediating the loop:**
- IN21A004: major hub between SNpp51 sensory and tibia motors
- IN13A006: strong path to Ti extensor from multiple sensory types
- IN19A005: SNpp39 → Ti extensor relay (550 synaptic weight output)
- IN13A002: leg sensory → Ti flexor relay

## 4. Functional Specialization of Sensory Types

### SNpp39 — Tibia Position Encoder (n=8, chordotonal organ)
- **Direct:** 100% to tibia motors (specifically Acc. ti flexor)
- **1-hop:** 48% tibia, 39% coxa, 10% trochanter
- **Inferred role:** fCO claw neuron encoding tibia-femur angle
- **Specificity:** HIGH for tibia at monosynaptic level

### SNpp51 — Multi-Joint Integrator (n=4, chordotonal organ)
- **Direct:** 29% tibia, 30% trochanter, 41% coxa
- **1-hop:** 48% tibia, 22% trochanter, 27% coxa
- **Inferred role:** broad proprioceptive integrator (overall leg posture)
- **Specificity:** LOW — distributes to all joint groups
- **Note:** Highest total weight (277 direct), most connected type

### SNpp53 — Trochanter Force Sensor (n=4, campaniform sensilla)
- **Direct:** 78% trochanter (69% to Tergotr. alone)
- **1-hop:** 74% trochanter, 20% coxa, 5% tibia
- **Inferred role:** force/load sensor at femur-trochanter junction
- **Specificity:** HIGH for trochanter

### SNppxx — Tibia Velocity Encoder (n=7, generic leg)
- **Direct:** 59% tibia (mostly Ti extensor), 37% trochanter
- **1-hop:** 32% tibia, 35% trochanter, 30% coxa (more diffuse)
- **Inferred role:** possibly fCO hook neurons (velocity encoding)
- **Specificity:** MEDIUM (joint-specific direct, diffuse at 1-hop)

### SNpp50 — Distal Joint Sensor (n=1, chordotonal organ)
- **Direct:** 42% Ta levator, 29% Ti extensor, mixed coxa/trochanter
- **Inferred role:** tarsus/distal position sensor
- **Specificity:** MEDIUM

### SApp23 — Ascending Proprioceptive (n=7, 4 on the left)
- **Direct motor connections:** NONE
- **Inferred role:** carries proprioceptive info toward brain (ascending)
- **For babbling:** not part of the local reflex loop — excluded
- **Count is 7, not 6.** One (bodyId 342042) has `subclass = NaN`, so the
  §1 subclass table split it off and it went uncounted. Match on `type`
  containing `SApp23`, not on subclass.

### SNpp45 — Hair Plate (n=1)
- **Inferred role:** coxa/trochanter joint-angle detector at joint fold
- **Note:** too few neurons for statistical inference

## 5. The Complete Sensory Encoding Design for Babbling

Assign each afferent a **(joint group, modality)** role by `type`. The
role table below is the design; the counts are the *as-built* left-side
numbers from `proprioceptive_encoder.py`.

| Joint group | Modality | n (LF) | Types |
|-------------|----------|--------|-------|
| tibia | position | 8 | SNpp39, 40, 43, 50, 59, 60 |
| tibia | velocity | 11 | SNppxx, untyped |
| trochanter | position | 8 | SNpp40, 41, 43, 59, 60, untyped |
| trochanter | force | 2 | SNpp53 |
| coxa | position | 6 | SNpp40, 45, 47, 57, 60 |
| coxa | velocity | 3 | untyped |
| multi | posture | 3 | SNpp51 |
| *excluded* | *ascending* | *4* | *SApp23* |

**45 selected (rootSide=L) → 41 encoded, 4 excluded.**

Superseded arithmetic: an earlier version of this section said "~52
encoded (65 − 6 ascending − 7 untyped)". That was wrong three ways — it
used both-sides counts, said 6 ascending when there are 7 (4 left), and
subtracted the 7 SNppxx as "untyped" when they are already assigned to
tibia velocity. It also claimed 16 unassigned neurons; there are exactly
**13** untyped, split round-robin across tibia-velocity /
trochanter-position / coxa-velocity.

Two role assignments in that earlier version were underspecified and were
resolved as follows:
- **SNpp47** — said "subset of", with no criterion given. All of them are
  used, as coxa position.
- **SNpp41** — the header said "pitch, yaw" while the body text said
  Tergotr. + sternal adductor. Resolved to trochanter **pitch only**
  (single DOF, cleaner receptive field).

The round-robin types (SNpp40, 43, 57, 59, 60) are split in bodyId order
— deterministic but arbitrary. **This is the least biologically grounded
part of the design** and the first thing to revisit if babbling shows
poor specificity.

### Encoding Function

For each sensory neuron, inject current proportional to its joint's
state, using current injection (NOT Poisson spike generation — preserves
STDP timing):

```python
I_sensory = gain_pA * activation_function(joint_state)
```

Where:
- Position neurons: `activation = |angle - rest_angle| / half_range`
- Velocity neurons: `activation = |angular_velocity| / max_velocity`
  (`max_velocity` = 25 rad/s)
- Force neurons: `activation = |tendon tension| / max_force`

> ### CORRECTION — the "50-100 pA" gain note was never checked against rheobase
>
> An earlier version of this section said `gain_pA = 75 pA default (50-100
> range, tuned for ~50-100 Hz in LIF)`. That is **below rheobase**: with
> `V_th − V_rest = 20 mV` over `R_membrane = 100 MΩ`, a LIF neuron needs
> **200 pA** to fire at all. Measured on real LIF neurons: 200 pA → 0.0 Hz,
> 201 pA → 18 Hz. At 75 pA **no afferent could ever spike**, at any duration.
>
> The "60.68 pA" figures in §9 were *sub-threshold currents*, not firing
> rates. **Never conclude an afferent responds by computing a current — count
> spikes on real LIF neurons.**
>
> Calibrated per-modality gains, each measured as the gain putting that
> channel in the 40-100 Hz band under a 50 ms single-muscle burst at muscle
> activation 0.40 (mean over the three joint groups):
>
> | modality | gain | measured mean Hz | why it differs |
> |----------|------|------------------|----------------|
> | position | 700 pA | 79 | reaches activation 0.35-0.49 |
> | velocity | 1200 pA | 67 (burst-integrated) | transient: peaks ~25 ms in, then decays |
> | force | 1400 pA | 64 | tonic but small: rest activation 0.005-0.033 |
> | posture | 2000 pA | 71 | weighted mean over 3 groups dilutes it ~4x |
>
> A **single shared gain cannot serve all four** — the in-band gains span
> 2.9x. Calibrating at activation 1.0 would also be wrong: only tibia
> position ever approaches 1.0.
>
> Reproduce with `python -m digital_drosophila loop sensory_calibration`.

> ### CORRECTION — the position reference is the settled posture, not `springref`
>
> The MJCF `springref` is **not** the posture the tethered leg relaxes into.
> After 3000 settling steps the LF joints sit 0.008-0.38 half-ranges away from
> it (tibia: 1.611 rad settled vs 2.00 springref). Referencing `|angle − rest|`
> to `springref` therefore (a) leaves afferents tonically active at rest —
> 0.384 activation on the tibia — and (b) makes activation **non-monotonic in
> movement**: driving the tibia flexor carries the joint *through* springref,
> so activation runs 0.384 → 0.001 → 0.424 and the same current is emitted at
> two different postures. `SETTLED_LF_ANGLES` is now the zero.

> ### CORRECTION — the force channel reads tendon tension, not ground reaction
>
> An earlier version said the load channel is "the summed MuJoCo normal
> contact force on the LF geoms. Measured: ~80 standing, 12-120 under muscle
> drive, so `max_force = 120`", concluding it sits "tonically at ~0.66
> activation".
>
> **That reading was an artifact.** True LF↔floor ground reaction in the
> tethered world is **exactly 0.0000** — the tarsus never touches the floor.
> The ~116 the old code summed came entirely from four **Thorax↔Coxa
> self-collisions** (`dist = −0.045`, interpenetration, not weight-bearing),
> which are *constant* and independent of leg state: unmodulated, so they
> carried no proprioceptive information either way.
>
> `SNpp53` now reads **tendon tension** — `sum |d.actuator_force|` over that
> joint group's muscles. This is a correction *toward* biology: campaniform
> sensilla measure cuticle strain and muscle load, not ground contact. A
> tethered fly pulling its tibia against a tether fires its CS as strongly as
> one standing.
>
> Measured tendon load, settled: coxa **0.68**, trochanter **1.373**, tibia
> **4.88** (non-zero, unlike ground reaction), rising to 15-336 under
> single-muscle drive. `max_force = 150`.
>
> So the load channel is **tonic but weak (activation 0.005-0.033)**, not
> tonic at 0.66. At the calibrated 1400 pA gain rest yields 13 pA — safely
> sub-rheobase and **silent** — while drive crosses threshold. This inverts
> the earlier concern: the force channel is *phasic in practice*, and does
> not have a continuous-firing STDP-eligibility problem.

Position and velocity channels rest at exactly 0 (settled reference) and
only go up. Do not assume a common zero-baseline across modalities when
interpreting babbling results.

**The unsigned position channel is direction-blind.** `|angle − rest|`
gives flexion and extension the same sign, and measurably the same rate:
tibia flexion of +0.778 rad and extension of −0.769 rad both produce
**152 Hz** at 700 pA. For Level 1 this is acceptable — babbling asks "did
this motor neuron move this joint", which magnitude answers — but
agonist/antagonist credit assignment (Level 2) will need a signed or
push-pull encoding. Not fixed yet.

## 6. Loop Timing Analysis

For the babbling experiment, the complete sensorimotor loop timing:

```
Motor neuron fires (injected current, 30-50ms sustained burst
                    — NOT a 5ms pulse; see doc 13 §8.1)
    → muscle activates (Hill-type, ~5ms rise time)
    → joint moves (MuJoCo physics, ~1-5ms response)
    → joint angle change detected
    → current injected into sensory neurons (instantaneous in sim)
    → sensory neuron fires (LIF, ~1-2ms to spike)
    → propagates to motor neuron:
        Direct path: 0 synapses, ~0ms = 7-12ms total
        1-hop path: 1 synapse, ~1-2ms = 8-14ms total
    
Total round-trip: 7-14 ms
STDP window: 20 ms
→ FITS within STDP timing window
```

## 7. Specificity Predictions for STDP

Given the wiring above, STDP during babbling should produce:

**Strong, specific strengthening:**
- Ti flexor fires → tibia bends → SNpp39 fires → arrives back at
  Ti flexor/Acc ti flexor within 10ms → STDP strengthens this loop
- Tergotr. fires → trochanter lifts → SNpp53 fires (force change) →
  arrives back at Tergotr. within 10ms → STDP strengthens

**Moderate, semi-specific strengthening:**
- Coxa motors fire → coxa moves → SNpp51 fires (multi-joint) →
  arrives at MANY motor neurons → STDP strengthens broadly
  (less specific, but still correlated)

**Weak/no strengthening:**
- SApp23 neurons fire from joint movement but have no motor connections
  → no loop closure → no STDP effect

**Cross-contamination risk:**
- SNpp51 connects to ALL motor types. When any motor fires and
  changes posture, SNpp51 fires and sends signal to all motors.
  However, TIMING specificity saves us: only the motor that fired
  5-15ms earlier gets the pre-before-post STDP window right.
  Other motors weren't firing → no temporal correlation → no STDP.

## 8. Open Questions

1. **Are the "nan" type neurons (n=13) really proprioceptive?**
   They're classified as `mechanosensory_proprioceptive` but have no
   type annotation. May be incompletely annotated or genuinely novel.

2. **Is SNpp51's broad connectivity a feature or a limitation?**
   It could encode "whole-leg posture" — useful for coordinated
   movements but problematic for single-motor babbling specificity.

3. **Should we include efferent neurons (n=99, superclass=vnc_efferent)?**
   These exit via leg nerves and may carry motor-related signals.
   They're distinct from vnc_motor and may be neuromodulatory.

4. **RESOLVED — use the full VNC.** The 736 intermediary interneurons are
   almost entirely outside the old 6-hop functional network (2.7%
   overlap, 20/736); key relays IN21A004, IN13A006, IN19A005 have 0-2
   instances in it. The 6-hop subnet captured descending command
   pathways, not proprioceptive feedback. **The 6-hop network is now
   retired — the full VNC (25,635 neurons) is the network.** Babbling on
   the full VNC then lets goal-directed training modulate
   pre-established reflex loops, which is biology's ordering: reflexes
   first, descending control second.

## 9. Implementation Status

| Piece | Module | State |
|-------|--------|-------|
| Sensory encoding (LF, 41 afferents) | `proprioceptive_encoder.py` | Built, **gains calibrated on real LIF spikes** |
| Motor → muscle decoding (58 MN → 15 muscles) | `muscle_decoder.py` | Built, demo verified |
| Muscles driving physics | — | **NOT wired** |

Demo commands:
```
uv run python -m digital_drosophila loop sensory_calibration
uv run python -m digital_drosophila loop proprio_test
MUJOCO_GL=egl uv run python -c "from digital_drosophila.muscle_decoder import run_muscle_decoder_demo; run_muscle_decoder_demo()"
```

Encoder specificity is confirmed at the calibrated gains: driving
`LFTibia_flex` at full activation moves the tibia-velocity bucket
0.28 → **968 pA** while coxa position stays at 0.86 pA; driving
`LFF_trochanter_extensor` raises trochanter-position 0.0 → **164 pA** and
trochanter-force 12.8 → **241 pA**.

> The earlier version of this paragraph read "driving `LFTibia_flex` moves
> the tibia-velocity bucket 0.68 → 60.68 pA" and offered that as evidence the
> encoder worked. **60.68 pA is 0.30× rheobase — zero spikes.** A current
> delta is not evidence of a response.

Afferents verified 0 Hz → in-band as gain crosses rheobase, driven by real
physics through `ProprioceptiveEncoder.encode` into real LIF neurons:

| bodyId | type | modality | 75 pA (shipped) | calibrated gain |
|--------|------|----------|-----------------|-----------------|
| 813177 | `<untyped>` | position | 0.0 Hz | 700 pA → 90 Hz |
| 811689 | `<untyped>` | velocity | 0.0 Hz | 1200 pA → 54 Hz |
| 899926 | SNpp53 | force | 0.0 Hz | 1400 pA → 32 Hz |
| 815843 | SNpp51 | posture | 0.0 Hz | 2000 pA → 128 Hz |

**Minimum detectable movement** (tibia, position channel, 50 ms burst) —
the sensory analogue of the motor firing-rate floor:

| gain | first spike at | muscle activation needed |
|------|----------------|--------------------------|
| 300 pA | 0.778 rad | 1.00 (only at maximum) |
| 500 pA | 0.512 rad | 0.60 |
| 700 pA | 0.356 rad | 0.40 |
| 800 pA | 0.273 rad | 0.30 |
| 1000 pA | 0.273 rad | 0.30 |

Note the table above holds the end-of-burst displacement as a steady current.
**Counted inside the 50 ms burst itself the position channel is slower still** —
displacement has to accumulate before it crosses threshold, so at 700 pA the
position channel emits its first in-burst spike only at muscle activation
**0.60**:

| muscle act | end position activation | position Hz (700 pA, held) | position spikes *within* the 50 ms burst | velocity Hz (1200 pA, in-burst) |
|-----------|------------------------|---------------------------|------------------------------------------|--------------------------------|
| 0.189 | 0.174 | 0 | 0 | 0 |
| 0.20 | 0.183 | 0 | 0 | 20 |
| 0.30 | 0.270 | 0 | 0 | 60 |
| 0.40 | 0.352 | 52 | 0 | 80 |
| 0.60 | 0.506 | 98 | 40 | 140 |
| 1.00 | 0.769 | 152 | 60 | 180 |

**Consequence for babbling: the velocity channel, not the position channel,
is what closes the loop inside one burst.** Velocity peaks ~25 ms in, while
position is still integrating; velocity fires from activation 0.20 and reaches
60 Hz by 0.30, where position is still silent. The two floors therefore do
overlap — but through the velocity channel, at muscle activation **≳0.20-0.30**
(vs the motor floor's 0.189 ≈ 50 Hz). Any protocol that relies on the position
channel for within-burst feedback needs activation ≥0.60, or a longer burst.

**Two gaps before the babbling experiment can run:**

1. **The muscle path does not drive physics yet.** `functional_training`
   builds `NeuroMechFly` (66 position DOFs), not `MusculoskeletalFly`, so
   the 15 Hill-type muscles are computed but inert.
2. **`baseline_hz = 15` is now a hard deadband** — the weighted-sum
   decoder clips sub-baseline rates to zero, so nothing below 15 Hz
   produces movement. If the network's tonic motor rate sits near 15 Hz
   the decoder will read as dead. Measure the actual motor-rate
   distribution before fixing a baseline, and expect `motor_gain` to need
   raising to ~0.5-0.6 since activation is now unipolar [0,1].
