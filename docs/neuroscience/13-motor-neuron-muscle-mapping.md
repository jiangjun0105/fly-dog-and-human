# Motor Neuron → Muscle → Joint: The Output Path

How motor neuron firing translates to physical leg movement, using the
FlyMimic musculoskeletal model for the Left Front (LF) leg.

## 1. The Real Anatomy

A fly's leg has 5 segments with joints between them:

```
Body (thorax)
 └── Coxa (hip) ────────── 3 DOFs: yaw, pitch, roll
      └── Trochanter/Femur (thigh) ── 3 DOFs: yaw, pitch, roll
           └── Tibia (shin) ────────── 1 DOF: pitch
                └── Tarsus 1-5 (foot) ── 5 DOFs: pitch each
```

Total: 11 DOFs per leg × 6 legs = 66 DOFs for the whole fly.

Note the trochanter and femur are drawn as one unit above because they are
largely **fused** in *Drosophila* — the trochanter-femur joint carries the
DOFs and there is no separately actuated femur segment. Consistent with
this, the connectome contains **no femur flexor/extensor motor neuron**
among the 19 LF types; the closest are `Fe reductor MN` (coxa/femur
boundary) and `ltm2-femur MN` (a long tendon muscle). A model that welds
the femur is therefore anatomically defensible. A model that welds the
**tarsus** is not — see §6.1.

## 2. Motor Neurons Per Leg

From the MANC connectome, the Left Front leg has **64 motor neurons**:
`superclass == "vnc_motor"`, `subclass == "fl"`, `somaSide == "L"`.

An earlier version of this section claimed 88, adding 14 wing-muscle and
10 neck-muscle neurons said to "exit via the leg nerve". **That was
wrong and is corrected here.** Verified against the dataset: no `wm`
(wing) motor neuron exits via any front-leg nerve — they leave via ADMN,
MesoAN, PDMNa, PDMNp. Neck (`nm`) neurons do share the DProN nerve (20
total, 10 on the left), but they drive neck muscles, not the leg, and are
correctly excluded.

**64 is the number to use.** It is what the code selects and what the
muscle mapping is built from.

| Muscle target | Motor neurons | Joint affected | Direction |
|---------------|---------------|----------------|-----------|
| Tergopleural/Pleural promotor | 4 | Coxa | Swing forward |
| Pleural remotor/abductor | 2 | Coxa | Swing backward + abduct |
| Sternal anterior rotator | 2 | Coxa | Rotate forward |
| Sternal posterior rotator | 4 | Coxa | Rotate backward |
| Sternal adductor | 1 | Coxa | Pull inward |
| Fe reductor | 4 | Coxa/Femur | Pull inward |
| Tr flexor | 8 | Trochanter | Lift thigh |
| Acc. tr flexor | 3 | Trochanter | Lift thigh |
| Sternotrochanter | 2 | Trochanter | Depress thigh |
| Tergotr. | 4 | Trochanter | Lift/extend thigh |
| Tr extensor | 2 | Trochanter | Lower thigh |
| Ti flexor | 5 | Tibia | Bend shin |
| Acc. ti flexor | 9 | Tibia | Bend shin |
| Ti extensor | 2 | Tibia | Straighten shin |
| ltm (long tendon) | 6 | Multi-joint | Cross-joint force |
| Ta depressor | 4 | Tarsus | Curl foot down |
| Ta levator | 2 | Tarsus | Lift foot up |

The rows sum to 64. Note the connectome splits the long tendon muscle
into three distinct `type` values — `ltm MN` (2), `ltm1-tibia MN` (2),
`ltm2-femur MN` (2) — which this table collapses into one row of 6. Code
must match on the three separate strings.

**Key point:** Multiple motor neurons (1-9) control the same muscle.
In biology, this is the "size principle" — recruit more neurons for more
force. They are NOT redundant; each contributes additional force.
See §4: this is why activation must be a weighted **sum**, never a mean.

Full per-leg counts (`subclass` × `somaSide`, verified against the
dataset — an earlier version of this list was off by up to 6):

| Leg | Motor neurons |
|-----|---------------|
| LF (fl, L) | 64 |
| RF (fl, R) | 60 |
| LM (ml, L) | 58 |
| RM (ml, R) | 56 |
| LH (hl, L) | 66 |
| RH (hl, R) | 64 |

368 leg motor neurons in total. Hind legs have the *most* motor neurons,
not the fewest — the reverse of what the earlier list claimed.

## 3. The FlyMimic Muscle Model

FlyGym includes an experimental musculoskeletal model (FlyMimic) that
simulates the Left Front leg with **15 Hill-type muscles**. A Hill-type
muscle is a physics model with:
- Force-length relationship (muscle generates different force depending
  on how stretched it is)
- Force-velocity relationship (faster contraction = less force)
- Activation dynamics (neural signal → muscle activation has a time delay)
- Tendons that connect muscles to bone segments

The 15 muscles and their correspondence to connectome motor neuron types:

```
COXA MUSCLES (7):
  LFC_tergopleural_promotor_a     ← Tergopleural/Pleural promotor MN (4 neurons)
  LFC_tergopleural_promotor_b     ← Tergopleural/Pleural promotor MN (shared)
  LFC_pleural_remotor_and_abductor ← Pleural remotor/abductor MN (2 neurons)
  LFC_pleural_promotor            ← (no direct connectome match - possibly
                                     shared with tergopleural promotor)
  LFC_sternal_anterior_rotator    ← Sternal anterior rotator MN (2 neurons)
  LFC_sternal_posterior_rotator   ← Sternal posterior rotator MN (4 neurons)
  LFC_sternal_adductor            ← Sternal adductor MN (1 neuron)
                                    + Fe reductor MN (4 neurons)

FEMUR/TROCHANTER MUSCLES (6):
  LFF_trochanter_flexor_a         ← Tr flexor MN (8 neurons)
                                    + Sternotrochanter MN (2 neurons)
                                    + ltm/ltm2-femur MN (4 neurons)
  LFF_trochanter_flexor_b         ← Tr flexor MN (shared with flexor_a)
  LFF_accesory_trochanter_flexor  ← Acc. tr flexor MN (3 neurons)
  LFF_sterno-tergo-trochanter_extensor_a ← Tr extensor MN (2 neurons)
  LFF_sterno-tergo-trochanter_extensor_b ← Tr extensor MN (shared)
  LFF_trochanter_extensor         ← Tergotr. MN (4 neurons)

TIBIA MUSCLES (2):
  LFTibia_flex_93434              ← Ti flexor MN (5) + Acc. ti flexor MN (9)
                                    + ltm1-tibia MN (2) = 16 neurons total
  LFTibia_extensor_93932          ← Ti extensor MN (2 neurons)
```

**Listing order above is NOT the model's actuator order.** In the loaded
model `LFF_trochanter_flexor_b` is actuator 7 and `_flexor_a` is actuator
12. Code must resolve muscles by name, never by position in this list.
`muscle_decoder.MUSCLE_NAMES` is asserted against the model's real
actuator order.

### Three mappings above are uncertain — treat as open

1. **`LFC_pleural_promotor` has no connectome match.** The guess above
   pools it with the tergopleural promotor, but §5 measures its joint
   signature as nearly orthogonal to `promotor_a`/`_b`
   (−0.37/−0.28/−0.25 vs −0.14/0/+0.13). Different mechanics means it is
   almost certainly a different muscle, so this pooling is likely wrong.
2. **`Fe reductor MN` → `LFC_sternal_adductor` is dubious.** §2 places Fe
   reductor on the coxa/femur joint, but pooling it with the sternal
   adductor creates a 5-neuron pool spanning two anatomically distinct
   muscles. FlyMimic has no femur-reductor actuator, so there is nowhere
   better to put it.
3. **`ltm MN` / `ltm2-femur MN` → `trochanter_flexor_a` discards their
   multi-joint character.** §2 describes the long tendon muscles as
   crossing joints; collapsing them into the flexor loses that. All 6
   `ltm*` neurons are excluded from babbling for this reason — see §6.1.

The `_a`/`_b` variants currently share one undivided pool, so they
co-activate identically — yet §5 shows they differ mechanically
(`trochanter_flexor_b` moves Tr_pitch +0.78, `_flexor_a` only −0.06).
There is no principled basis in the annotations to split them. This is
the weakest part of the mapping.

**Coverage:** 58 of 64 LF motor neurons map to one of these 15 muscles.
The 6 that don't are `Ta depressor MN` (4) and `Ta levator MN` (2) —
FlyMimic has tarsus *segments* but no tarsus **joints**, so there is
nothing for them to move.

Mapped ≠ usable, though: of the 58, the 6 `ltm*` neurons are pooled into
single-joint muscles that misrepresent their multi-joint action. **Only 52
of 64 are valid babbling targets** — see §6.1.

## 4. How Firing Rate Converts to Muscle Activation

For each muscle, the activation level is a function of its motor neuron
population's firing rates:

```
activation(muscle) = f(rates of all motor neurons targeting that muscle)
```

**Do NOT use `mean(rates)`.** A mean breaks the size principle from
Section 2: if one large motor neuron fires while four small ones stay
silent, the mean divides activation by 5. Adding a silent neuron must
never weaken a muscle. It must be a **sum over neurons**.

### 4.1 The current model: per-class force per spike

*(Replaced the flat-`max_rate` model on 2026-08-18. The superseded version
is kept in §4.3 because it is what every measurement before that date
used.)*

Each motor neuron is assigned a **force class** — slow, intermediate or
fast — and contributes force according to *its own class*, not a shared
rate ceiling:

```
force_uN(muscle)  = sum over neurons i of  class_force(class_i, rate_i)
activation        = clip( force_uN / pool_max_force_uN, 0, 1 )
pool_max_force_uN = sum over i of  class_force(class_i, max_rate[class_i])
```

`activation_scale` is therefore **derived from the per-class maxima of the
neurons actually in the pool**. There is no `max_rate ~ 200 Hz` anywhere.

The per-class constants, all from Azevedo et al. 2020 (*eLife* 9:e56754),
which recorded *identified* femur/tibia-flexor MNs in the **front leg** —
the same pool this decoder drives:

| class | force per spike | resting | rate ceiling used | regime |
|-------|-----------------|---------|-------------------|--------|
| fast | **10 µN** (≈ body weight) | silent | 250 Hz | phasic, saturates ~10 spikes |
| intermediate | **1 µN** | silent | 250 Hz | phasic, saturates ~10 spikes |
| slow | **0.013 µN** | ~30 Hz | **150 Hz** | tonic, linear in rate |

Two regimes, because the classes differ in kind and not only magnitude:

- **fast / intermediate** are phasic and their fibres fatigue, which is
  what Azevedo attributes the ~10-spike saturation to. With
  `n = rate * fusion_tau`, `F = F_sat * (1 - 0.6**n)`. The `0.6` is not a
  free parameter: Azevedo reports "the force produced by two spikes was
  ~1.6X the force produced by a single spike", and `F(2)/F(1) = 1 + x`
  gives `x = 0.6` exactly — which then puts `F(10)/F_sat` at 0.994, i.e.
  reproduces the separately stated "~10 spikes" saturation. The two
  numbers agree, which is a consistency check on the reading.
- **slow** is tonic and fatigue-*resistant*, so it must not inherit
  fast-fibre fatigue. `F = force_per_spike * rate * fusion_tau`, linear in
  rate and clipped at 150 Hz. This is what "integrates over rate" means.

The 250 Hz ceiling for the phasic classes is **not a force gain**: their
force function has already saturated there, so moving it changes the
class's maximum force by <1%. Azevedo gives these classes a spike count,
not a rate; 250 Hz is the rate that puts 10 spikes inside one fusion
window.

`fusion_tau = 40 ms` is the one constant with **no fly source** — it is
`1/25 s`, from the ~20-25 Hz tetanic-fusion frequency Harischandra et al.
(2019) measured in *locust* extensor tibiae. A cross-species import,
flagged as such. It is not load-bearing: the phasic classes have
saturated regardless, and the slow class is a few percent of any pool's
maximum either way.

**`baseline_hz = 15` is retired.** It was a flat deadband and is
indefensible at both ends of the gradient. Fast/intermediate MNs are
*silent* at rest, so every spike they fire is signal — a single fast spike
in a 50 ms rate window reads as 20 Hz, and a 15 Hz deadband deletes three
quarters of exactly the class whose one spike is supposed to move the
tibia. Slow MNs *idle* at ~30 Hz and that idle is a real resting force
(Azevedo: the slow MN holds "constant force on the probe" at rest), so
subtracting a baseline models the tonic class's own operating point as
zero output. Posture is held instead by the muscle `ctrlrange` floor
(1e-4) and the model's passive joint stiffness, which is where it belongs.

### 4.2 Class assignment is an ASSUMPTION, not an annotation

Class is assigned by **`size` rank within each (leg, `type`) pool**, with
Azevedo's pool proportions applied by rank. This is a labelled assumption.
Three things were checked and none of them supports a principled
assignment:

1. **`size` cannot carry the gradient by magnitude.** Azevedo's classes
   are distinguished *within one muscle pool*. Our Ti flexor pool spans
   only **2.1×** in `size` across 5 neurons; Ti extensor 1.4× across 2. A
   2.1× anatomical spread cannot encode a 1000× force ratio. The 14×
   figure quoted elsewhere in this doc is the spread across all 64 LF MNs
   of *different muscles* — a different quantity, and not a within-pool
   gradient.
2. **`synweight` is no better as a *class* variable.** It spans more (122×
   within the trochanter-flexor DOF pool) but it counts synapses, and it
   tracks connectivity rather than contractile capacity. It also
   correlates strongly with `size` anyway — Spearman ρ = **0.83** over the
   64 LF MNs (p = 4e-17, measured) — so it would largely reproduce the
   same ordering while being harder to justify.
3. **Azevedo's identified cells cannot be matched to MANC types.** His
   classes are Gal4 lines (fast R81A07, intermediate R22A08, slow
   R35C09). MANC's `type` for all 64 LF MNs names only the *muscle*
   ("Ti flexor MN"), and every column that might carry a finer identity is
   empty for this population — `flywireType`, `hemibrainType`, `synonyms`,
   `class`, `supertype` all NaN, and `mancType` merely repeats `type`.
   **There is no join key.**

So what the assignment uses from the data is **rank, not magnitude**:

- The size principle predicts recruitment order correlates with motor
  neuron size, and Azevedo's paper *is* that principle — his fast cell has
  "an exceptionally large soma", his slow cell "the smallest cell body,
  dendrites, and axon". The *ordering* by `size` should therefore track
  class even where the connectome's dynamic range understates the force
  ratio.
- The **proportions** come from Azevedo's anatomical count of the tibia
  flexor pool: ~15 MNs made up of 1 fast, 2-5 intermediate, 8-9 slow.
  Applied as pool *fractions* (1/15 fast, 3.5/15 intermediate) so they
  generalise to the 2-16 neuron pools this connectome actually has.
- The pool is `(leg, type)`, i.e. one MANC muscle — not a FlyMimic
  actuator. `LFTibia_flex_93434` pools Ti flexor + Acc. ti flexor +
  ltm1-tibia, three anatomically distinct muscles, and ranking across them
  would compare a large neuron of one muscle against a small one of
  another.

Two properties are guaranteed and asserted rather than assumed: every pool
gets exactly one fast neuron (its largest), and the assignment is monotone
in `size` (verified: **0 non-monotone pools of 140**).

### 4.3 Superseded: the flat-`max_rate` model

Everything measured before 2026-08-18 used:

```
activation       = clip( sum(w_i * rate_i) / activation_scale, 0, 1 )
activation_scale = sum(w_i) * max_rate,   max_rate ~ 200 Hz
w_i              = size_i / mean(size over that muscle's population)
```

**`max_rate ~ 200 Hz` was written here unsourced, and it had
consequences.** No fly leg MN has been measured at or near 200 Hz in any
condition. Because `activation_scale` *divides* by `max_rate`, normalising
against an unreachable rate makes activation systematically too low — so
producing movement demands compensating drive. The multi-muscle
loop-closure experiment needed exactly 200 Hz sustained for 200 ms, which
was this constant reappearing as an apparent empirical requirement.

The deeper defect was that the equation had **no motor neuron classes at
all**: a 1000× biological force-per-spike gradient represented as a 14×
spread, in the wrong variable (`w_i` scaled *drive*, not force per spike).

The `w_i` size weights, for reference — the 5 Ti flexor MNs:

| Ti flexor MN bodyId | size | synweight | class now assigned |
|---------------------|--------|-----------|--------------------|
| 807165 | 3.22e9 | 3399 | fast |
| 809912 | 2.07e9 | 2010 | intermediate |
| 819384 | 1.62e9 | 578 | slow |
| 818057 | 1.58e9 | 823 | slow |
| 909831 | 1.53e9 | 553 | slow |

`MuscleDecoder(force_model=False)` still reproduces this decode exactly,
so the two can be compared in one run. It exists for that comparison only.

### 4.4 The Hill-type muscle does admit the gradient

This was an open question — a 1000× per-spike range is useless if the
muscle model's own force scaling clamps it. **Measured, it does not.**
Driving `LFTibia_flex_93434` alone from the settled posture, actuator
force is very nearly linear in `ctrl` across four decades:

| ctrl | peak \|actuator force\| | excursion (rad) |
|------|------------------------|-----------------|
| 1e-4 | 0.007 | 0.0006 |
| 1e-2 | 1.36 | 0.009 |
| 1e-1 | 13.6 | 0.093 |
| 0.5 | 68.1 | 0.435 |
| 1.0 | 136.2 | 0.704 |

A 2×10⁴ force span over the usable `ctrl` range, so a 1000× gradient fits
inside it with room to spare, and `forcelimited` is `False` on all 15
actuators. The *excursion* saturates well before the force does (joint
limits), but that is mechanics, not a clamp on the force range.

Hill-type muscle then converts activation (0-1) to force, accounting for:
- Current muscle length (from joint angle)
- Contraction velocity
- Activation-to-force dynamics (`dynprm` 0.1/0.4 ms — so `data.act` is
  part of the state and must be restored between conditions)

## 5. What Happens When One Muscle Fires

We tested each of the 15 muscles at full activation (1.0) for 500
physics steps and measured the resulting joint angle changes, minus the
gravity baseline. Results (showing only significant effects > 0.05 rad):

### Coxa muscles → primarily move Coxa joints

| Muscle | Coxa_yaw | Coxa_pitch | Coxa_roll |
|--------|----------|------------|-----------|
| tergopleural_promotor_a | -0.14 | | +0.13 |
| tergopleural_promotor_b | **-0.45** | **-0.60** | +0.26 |
| pleural_remotor_and_abductor | **+0.20** | **+0.18** | **-0.09** |
| pleural_promotor | **-0.37** | **-0.28** | **-0.25** |
| sternal_anterior_rotator | -0.16 | | |
| sternal_posterior_rotator | -0.09 | +0.16 | +0.19 |
| sternal_adductor | -0.12 | | -0.14 |

### Femur muscles → primarily move Trochanter joints

| Muscle | Tr_yaw | Tr_pitch | Tr_roll |
|--------|--------|----------|---------|
| trochanter_flexor_b | **-0.53** | **+0.78** | +0.15 |
| sterno-tergo_extensor_a | +0.16 | **-0.21** | -0.16 |
| sterno-tergo_extensor_b | -0.18 | +0.16 | |
| accesory_trochanter_flexor | -0.11 | | |
| trochanter_extensor | **+0.53** | **-0.33** | |
| trochanter_flexor_a | -0.06 | | |

### Tibia muscles → move Tibia pitch

| Muscle | Tibia_pitch |
|--------|-------------|
| LFTibia_flex | **+0.54** (bend shin) |
| LFTibia_extensor | **-0.37** (straighten shin) |

### Distinguishability

Mean pairwise cosine similarity between muscle signatures: **-0.011**
(nearly orthogonal — each muscle produces a unique pattern).

Best case: Tibia flex vs extensor = **-1.000** (perfect opposites)
Worst case: Some trochanter flexor variants = +0.99 (same muscle type)

**Conclusion:** Each muscle (and therefore each motor neuron group)
produces a physically distinguishable movement. A sensory system
encoding joint angles can identify which muscle fired.

## 6. The Full Motor Complement Across All Legs

Counts below are measured, and the DOF-mapped column is what
`muscle_decoder.py` actually achieves (not an estimate):

| Leg | Motor neurons | Muscle-mapped | Babbling-valid | DOF-mapped | FlyMimic support |
|-----|---------------|---------------|----------------|-----------|------------------|
| LF | 64 | 58 (91%) | **52 (81%)** | 64 | Yes — 15 Hill-type muscles |
| RF | 60 | — | — | 59 | Segments only, no muscles |
| LM | 58 | — | — | 46 | Segments only, no muscles |
| RM | 56 | — | — | 45 | Segments only, no muscles |
| LH | 66 | — | — | 52 | Segments only, no muscles |
| RH | 64 | — | — | 51 | Segments only, no muscles |

317 of 368 leg motor neurons map to a DOF. The 51 that don't have
uninterpretable `MNml*`/`MNhl*` type codes or a blank `type`.

**FlyMimic has muscles for the LF leg only.** Verified by loading the
model: it contains body segments for all six legs but exactly **15 muscle
actuators, every one LF** (prefixes `LFC`×7, `LFF`×6, `LFT`×2). There is
no RF muscle set — an earlier version of this table implied RF had a
14-DOF muscle path, which it does not.

This is why the babbling experiment is **LF-only**. The other five legs
fall back to position actuators via the 66-DOF vector, which is adequate
for postural support but cannot provide Hill-type force dynamics.

### 6.1 What FlyMimic cannot represent — 12 of 64 LF neurons

Verified by walking the model's kinematic tree. FlyMimic has **14 joints
total** (LF 3+3+1, RF 3+3+1). The full LF chain is present as bodies with
meshes — coxa → trochanter → femur → tibia → tarsus 1-5 — but:

```
LFCoxa         joints: Coxa_yaw, Coxa_pitch, Coxa_roll
 └─ LFTrochanter   joints: Troch_yaw, Troch_pitch, Troch_roll
     └─ LFFemur       joints: NONE  (welded — defensible, see §1)
         └─ LFTibia       joints: Tibia_pitch
             └─ LFTarsus1-5   joints: NONE  (welded — NOT defensible)
```

**Group A — 6 tarsus neurons have no possible target.** `Ta depressor MN`
(4) + `Ta levator MN` (2). The earlier wording here said FlyMimic "models
no tarsus muscles", which understates it: it has no tarsus **joints**, so
these neurons cannot act even in principle. In the real fly they are
substantial, well-annotated T1 neurons (`synweight` 151-3292) driving the
tarsal levator/depressor — the muscles a fly uses to grip, climb, and
groom. This is a model limitation, not a biological absence.

**Group B — 6 `ltm` neurons are mechanically misrepresented.** `ltm MN`
(2), `ltm1-tibia MN` (2), `ltm2-femur MN` (2). These are **long tendon
muscles**: a proximal muscle belly whose tendon spans multiple joints to
move distal segments. §3 currently pools `ltm`/`ltm2-femur` into
`trochanter_flexor_a` and `ltm1-tibia` into `LFTibia_flex` — collapsing a
deliberately multi-joint actuator into single-joint muscles, which
defeats its function. With the femur welded, half its mechanical role has
nowhere to act at all.

**Consequence for babbling.** These 12 neurons will receive babbling
drive and produce either no movement (Group A) or the wrong movement
(Group B), so STDP can only learn a null or incorrect association for
them. They must be **excluded from the loop-closure statistics**, not
counted as failures — otherwise Child 1's "≥50% of tested motor neurons
show loop closure" criterion measures FlyMimic's limitations rather than
connectome biology.

**Valid babbling scope: 52 of 64 LF neurons** (64 − 6 tarsus − 6 ltm) —
those driving coxa, trochanter, and tibia muscles with live DOFs.

## 7. Implications for the Babbling Experiment

**What we've confirmed:**
1. Each motor neuron type drives a specific, identifiable muscle
2. Each muscle produces a distinguishable joint movement pattern
3. Multiple motor neurons per muscle = graded force control
4. The FlyMimic model gives us realistic muscle physics (not just
   position servos)

**What this enables:**
- When a specific motor neuron fires during babbling, it produces a
  UNIQUE physical effect (specific joints move in a specific pattern)
- The sensory system can detect WHICH motor neuron fired by reading
  joint angles
- STDP can then learn the correlation: "when this motor neuron fires,
  this specific sensory pattern follows" — **provided the motor burst is
  sustained long enough to avoid the anti-causality trap in §8.1**
- This is the forward half of the loop; the return path (sensory →
  local interneuron → back to motor) is confirmed structurally (see §8)

## 8. The Return Path (Local Sensory → Interneuron → Motor)

**Superseded:** an earlier version of this section routed the return path
through **ascending neurons**. That was biologically inverted. Ascending
neurons are output cables carrying state *up to the brain*; they are not
the local reflex loop. The babbling loop runs through **local ProLN
sensory neurons and local T1 interneurons**.

The corrected path is measured in
`14-sensory-motor-loop-structure.md`. Summary:

- 65 local proprioceptive neurons enter via ProLN
  (`entryNerve == "ProLN"`, `class == "mechanosensory_proprioceptive"`)
- Of those, **58 are `superclass == "vnc_sensory"`** — the local reflex
  population. The other 6+1 are `sensory_ascending` (the SApp23 group),
  which have **zero** direct motor connections and are excluded
- **134 direct monosynaptic** sensory → motor synapses (22 sensory
  neurons onto 46 of 64 motor neurons)
- **19,565 one-hop paths** via **736 local interneurons** reach all
  64/64 motor neurons. Key relays: IN21A004, IN13A006, IN19A005

Note on the neuromere filter: the feedback suggested selecting
`neuromere == 'T1L'`. That does not work on this dataset — `somaNeuromere`
is `T1/T2/T3` with no side suffix, and is **NaN for all 65** of these
sensory neurons (their somata sit in the leg periphery, not a neuromere).
`entryNerve == "ProLN"` + `somaSide` on the motor side is the working
filter. Also `vnc_sensory` is a **`superclass`** value, not a `class`
value, in MANC.

The full loop:
```
Motor neuron fires (network)
    → muscle contracts (Hill-type physics, ~5ms activation rise)
    → joint moves (MuJoCo physics, ~1-5ms response)
    → joint angle change → current injected into local ProLN sensory neurons
    → direct (0 synapses) or via 1 local interneuron (~1-2ms)
    → arrives back at motor neuron

Total round-trip estimate: 7-14 ms
STDP window: 20 ms
→ Loop FITS within STDP timing window
```

### 8.1 The STDP Anti-Causality Problem

Fitting inside the 20 ms window is necessary but **not sufficient**.
There is a sign problem that would make naive babbling learn the exact
opposite of what we want.

To strengthen the **sensory → motor** synapse, the sensory neuron is
*pre* and the motor neuron is *post*. But the babbling timeline is:

```
t=0ms   motor neuron fires        (post fires FIRST)
t=5ms   muscle activates
t=10ms  sensory neuron fires      (pre fires SECOND)
```

Post-before-pre by 10 ms. Standard asymmetric STDP reads that as
anti-causal and **depresses** the synapse. Run naively, babbling would
systematically *weaken* every correct reflex arc — and the failure would
look like "no loop closure detected" rather than a sign error.

Two fixes, both applied:

1. **Sustained motor bursts, not 5 ms twitches.** Drive the babbled
   motor neuron for **30-50 ms** instead of a single brief pulse. The
   motor neuron is still firing when sensory feedback arrives at t=10ms,
   so later motor spikes (t=15, 20, 25...) follow the sensory spike and
   register genuine pre-before-post potentiation. This is the preferred
   fix: it changes the protocol, not the learning rule, and it matches
   the sustained character of real fetal motor twitching.

2. **Symmetric / Hebbian window during babbling only.** Strengthen on
   near-coincidence regardless of order. Reserve this for the
   developmental phase; goal-directed Phase 2 keeps the standard
   asymmetric rule.

`12-sensorimotor-babbling.md` §Level 1 has been updated to 30-50 ms
accordingly.

## 9. Open Questions for the Experiment

1. **Can STDP detect the timing above network noise?** The round-trip
   is 7-14 ms. But the network also has recurrent activity (intrinsic
   neurons firing spontaneously). Signal-to-noise ratio is unknown.

2. **How many babbling episodes are needed?** Each episode provides one
   timing sample per motor neuron. With 58 motor neurons and noisy
   correlations, convergence may require hundreds of episodes.

3. **Does SNpp51's broad connectivity cause cross-contamination?** It
   targets all three joint groups. The hypothesis is that timing saves
   specificity: only the motor neuron actually bursting gets the
   pre-before-post correlation. Untested.

4. **Do the 736 relay interneurons need to be in the trained subnet?**
   Only 2.7% (20/736) are in the 6-hop functional network, which is why
   babbling must run on the full VNC.

*(Resolved and moved to `14-sensory-motor-loop-structure.md`: how to
encode joints into sensory neurons, and which neurons carry LF
proprioception.)*
