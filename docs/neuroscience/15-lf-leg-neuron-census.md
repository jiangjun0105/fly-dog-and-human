# Left Front Leg: Neuron Census and What We Actually Model

**Date:** 2026-08-19
**Purpose:** One place for "how many neurons are there, and how many do we use?" Every figure
here was measured from `data/cache/full_vnc_network/` (25,635 neurons, 4,114,854 synapses) rather
than quoted from another document.

The short version: **we model 81% of the motor side and 8% of the sensory side.** That asymmetry
is not obvious from any of our other documents and it is worth keeping in view.

## 1. Motor neurons — 64 anatomically, 52 testable

Selection: `superclass == "vnc_motor"` & `subclass == "fl"` & `somaSide == "L"`.

**64 is complete.** `fl` splits 64 left / 60 right, and **zero** `fl` motor neurons have a missing
`somaSide`, so the filter drops nothing silently.

All 702 motor neurons in the dataset, for scale:

| subclass | L | R | body part |
|----------|-----|-----|-----------|
| ad | 111 | 110 | abdomen |
| **fl** | **64** | 60 | **front leg** |
| hl | 66 | 64 | hind leg |
| ml | 58 | 56 | middle leg |
| wm | 33 | 34 | wing |
| nm | 12 | 12 | neck |
| hm | 8 | 8 | haltere |
| xm | 3 | 3 | other |

Note hind legs have the **most** motor neurons (66), not the fewest.

**We test 52 of the 64.** The 12 excluded have no live DOF in FlyMimic:

- **6 tarsus** (`Ta depressor MN` ×4, `Ta levator MN` ×2) — FlyMimic welds all five tarsus
  segments into one rigid body, so there is nothing to actuate even in principle. **The real fly
  does innervate them** (`synweight` up to 3,292), so this is a model defect, not biology.
- **6 long tendon** (`ltm MN`, `ltm1-tibia MN`, `ltm2-femur MN`) — pooled into single-joint
  muscles, which defeats their multi-joint function.

Counting these 12 would measure FlyMimic's limitations rather than connectome biology. See
`13-motor-neuron-muscle-mapping.md` §6.1.

**Coverage: 52/64 = 81%.**

## 2. Sensory neurons — 504 available, 41 modelled

Selection: `entryNerve == "ProLN"` (the front-leg nerve) & `rootSide == "L"`.

**963 neurons enter via ProLN** — 504 left, 459 right. By class:

| class | L | R | modelled? |
|-------|-----|-----|-----------|
| mechanosensory_tactile | 151 | 113 | no |
| gustatory | 149 | 150 | no |
| unknown_sensory | 142 | 164 | no |
| **mechanosensory_proprioceptive** | **45** | 20 | **yes** |
| chemosensory | 11 | 8 | no |
| (NaN) | 6 | 5 | no |

Of the 45 left proprioceptors we encode **41**, excluding 4 `SApp23` (ascending, zero motor
connections). Left-side types: `SNppxx` 7, `SApp23` 4, `SNpp39`/`SNpp40`/`SNpp51`/`SNpp60` 3 each,
`SNpp43`/`SNpp47`/`SNpp53`/`SNpp59` 2 each, `SNpp41`/`SNpp45`/`SNpp50`/`SNpp57` 1 each.

**Coverage: 41/504 = 8.1%.**

### Laterality must use `rootSide`, not `somaSide`

**`somaSide` is NaN for all 65 proprioceptive afferents** — their somata sit out in the leg
periphery, not in the VNC. Using `somaSide` silently returns nothing; using both sides would
encode right-leg afferents from left-leg joint angles.

### Are the exclusions justified? Mostly — one is not

Measured: do the excluded classes actually reach LF motor neurons?

| class | n | direct synapses → LF MN | MNs reached directly | via 1 interneuron |
|-------|-----|------------------------|---------------------|-------------------|
| mechanosensory_proprioceptive | 45 | 121 | 45 | 64/64 |
| mechanosensory_tactile | 151 | 147 | 9 | 64/64 |
| **unknown_sensory** | **142** | **78** | **30** | 64/64 |
| gustatory | 149 | **0** | 0 | 63/64 |
| chemosensory | 11 | **0** | 0 | 64/64 |

- **Gustatory and chemosensory: clearly right to exclude.** Taste and smell do not report limb
  state, and neither has a single direct synapse onto a motor neuron.
- **Tactile: defensible.** Touch is not proprioception. But 147 direct synapses onto 9 motor
  neurons means it is not irrelevant to leg control either.
- **`unknown_sensory`: questionable.** 142 neurons with **78 direct synapses onto 30 of 64 motor
  neurons**, excluded purely because the class label reads "unknown." Some fraction are almost
  certainly proprioceptors — the label reflects *annotation uncertainty*, not a biological
  category.

**This is structurally the same error as the `unclear` neurotransmitter default: treating
"unlabelled" as "absent."** See `2026-08-19-sign-zero-silenced-neurons.md`. The honest treatment is
the same too — measure whether a conclusion depends on the exclusion rather than assuming it does
not.

Note the one-hop column tempers the concern: **every** sensory class reaches 63-64 of 64 motor
neurons through a single interneuron. So including more classes would not buy specificity; it would
add more broadcast. It could, however, change **conduction** — our Level 1 finding was that 41
afferents cannot deliver enough charge to fire a relay, and 142 additional direct-to-motor sensory
neurons might move that ceiling.

## 3. What is presynaptic to LF motor neurons

**2,047 distinct neurons**, across **16,663 synapses**, synapse onto the 64 LF motor neurons:

| superclass | count |
|------------|-------|
| vnc_intrinsic (local interneurons) | 1,361 |
| descending_neuron (from brain) | 228 |
| ascending_neuron | 224 |
| vnc_sensory | 149 |
| vnc_motor (motor → motor) | 47 |
| other | 4 |

### Only 64% are leg-specific

Of those 2,047, **729 (36%) also synapse onto another leg's motor neurons**:

| touches | neurons |
|---------|---------|
| 1 leg only | **1,318 (64%)** |
| 2 legs | 340 |
| 3 legs | 180 |
| 4 legs | 102 |
| 5 legs | 53 |
| **all 6 legs** | **54** |

So a third of the input onto front-left motor neurons comes from cells that also steer other legs.
A signal arriving there may genuinely not be *about* the front left leg. This is structural — no
parameter we sweep changes it — and it independently supports the broadcast finding from Levels 1
and 3.

### "Connected to the leg" means at least three different things

Worth separating, because a single query flattens them:

1. **Motor neurons** reach muscle directly — they are the only cells that move anything.
2. **The 149 `vnc_sensory`** in that list originate *in* the leg and report its state.
3. **The 228 `descending_neuron`** come from the brain and never touch the leg themselves.

## 4. Why so few neurons fire in our experiments

Our multi-muscle loop-closure run reported **7 "closers"** — neurons that fired and synapse onto an
LF motor neuron. That is **0.34% of the 2,047** available presynaptic partners.

Two filters shrink 2,047 → 7:

1. **Reachability** — most of the 2,047 receive nothing from the 41 afferents we stimulate. A
   descending neuron synapses onto motor neurons but is not downstream of leg proprioception.
2. **Threshold** — of those that are reachable, most receive too little charge to fire. A single
   synchronous volley must clear ~11.8 mV, and the strongest relay receives 15.56 mV against a
   20 mV threshold.

**So "7 closers" means seven neurons conducted a timed signal, not seven neurons exist in the
pathway.** When earlier documents call the return path "thin," the thinness was never about how
many neurons exist — 2,047 is ample. It is that the ones which can actually fire from a sensory
volley are few, and the ones that do fire are the least specific.

## 5. Not verified

- **99 `vnc_efferent`** neurons (92 with no subclass) are excluded everywhere in this project
  without anyone checking whether any innervate leg muscle. Efferents are typically
  neuromodulatory or glandular rather than skeletal motor, so exclusion is *probably* right — but
  it is an assumption, not a measurement.
- All counts here are **direct** synapses. Allow two hops and the numbers balloon; median in-degree
  across the VNC is 111.
- These are wiring counts, **not conduction**. Most of these connections cannot fire their target
  from a single volley — see §4.
- The 7-closer figure comes from one drive condition. A different stimulus could recruit different
  closers; whether the set discriminates between origins is still an open question.

## Related

- `13-motor-neuron-muscle-mapping.md` — motor → muscle → joint mapping, §6.1 for the 12 exclusions
- `14-sensory-motor-loop-structure.md` — the measured return path
- `../issues/2026-08-19-sign-zero-silenced-neurons.md` — the "unlabelled means absent" pattern
- `../lab/2026-08-18-multi-muscle-loop-closure.md` — where the 7 closers come from
- `../lab/2026-08-19-l3-outbound-exit-gate.md` — the descending-command side
