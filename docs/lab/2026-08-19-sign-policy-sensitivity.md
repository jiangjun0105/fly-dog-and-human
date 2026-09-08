# Level 1 Survives the Sign Policy; the L3 DN Ranking Does Not

**Date:** 2026-08-19
**Experiment:** Vary the `unclear` neurotransmitter sign (0 / +1 / −1) and re-measure
everything Level 1 concluded — [issue](../issues/2026-08-19-sign-zero-silenced-neurons.md)

## Summary

**Level 1's conclusions are not policy-dependent. The L3 outbound top-6 is.**

Loop closure is *identical* to three significant figures under all three policies at zero
background — **35.4 ms, 6 closers, 41/41 afferents, 0 frozen false positives, 1.173 rad** — and
identical again at 125 pA (**12.4 ms, +5.8 ms lag, 0 frozen**). `IN21A004` bodyId 800802
contacts **46 of 64** LF MNs at **+33.17 mV** in every arm, because it is cholinergic: its own
synapses are untouched by the `unclear` sign, and no `unclear` cell rises to challenge it
(the broadest `unclear` cell reaches 20 of 64 under policy B, still below `IN21A004`'s 46).

**Under policy B the L3 outbound top-6 gains two new entries at ranks 2 and 3** — `DNg34`
(bodyId 10295, +404 mV) and `DNge149` (11466, +378 mV), both previously exactly 0.0 mV. That is
the same `DNg34` the L3 issue explicitly retired as "electrically silent." So one policy choice
decides whether the second- and third-strongest outbound drivers exist at all.

**And the sweep found a defect in policy B itself.** Both newcomers have
`consensusNt = unclear` but `predictedNt = octopamine`. Policy B forces them to +1, which
contradicts the sweep's own rule that octopamine stays at 0. Keeping the 101 such cells at 0
(policy B′) restores the original top-6 exactly. **So the L3 reordering is not evidence that
`unclear` should be excitatory — it is evidence that "unclear" in `consensusNt` sometimes means
"predicted modulatory," and that a blanket override mislabels those cells.**

## What We Did

Reproduce: `python -m digital_drosophila check sign_policy` (`--quick` for a coarser ladder,
`--policy A,B` for a subset).

Three arms differing in exactly one value:

| policy | `unclear` | serotonin / octopamine / dopamine | histamine |
|---|---|---|---|
| **A** (shipped) | 0 | 0 | −1 |
| **B** | **+1** | 0 | −1 |
| **C** | **−1** | 0 | −1 |

The sign map is built by **copying the imported `constants.NT_SIGN_MAP`** and overriding one
key; `policy_sign_map` *asserts* that the other four are unchanged, so the sweep cannot silently
vary two things. `load_full_vnc(nt_sign_map=...)` threads the override through
`build_live_weights`; the default is verified byte-identical to the shipped map, so no existing
result moved.

Full VNC (25,635 neurons / 4,114,854 synapses), `body_wiring`'s own harness reused throughout:
3000-step settle, `data.act` restored between conditions, physics and network in lockstep at
`dt = 0.1 ms`, 200 ms background settle, force model ON, class-specific drive (slow MNs tonic
50 Hz, fast/intermediate 2 spikes then silent), 200 ms burst, **frozen-physics control at every
one of the 19 background levels in every arm** (114 runs). The MuJoCo body is shared across arms
— it is independent of the sign map and `reset_body` restores `qpos`/`qvel`/`act` before every
condition. Synaptic delays are the same seeded draw (0.80-1.50 ms) in all three arms.

Every verdict is a `SpikeMonitor` count. `idle dV` is the one `StateMonitor` read that is
load-bearing, and it is the quantity being manipulated.

**The policy-A column reproduces the published table exactly** — 35.4 ms / +28.8 ms / 6 closers
at 0 pA, 12.4 ms / +5.8 ms / 125 closers at 125 pA, spontaneity at poisson 20 Hz, pool runaway
from 130 pA. That is what makes the sign the one changed variable.

## The Three Columns

### The wiring

| | A | B | C |
|---|---|---|---|
| synapses exactly 0 | **204,608 (4.97%)** | 2,820 (0.07%) | 2,820 (0.07%) |
| neurons with entire output deleted | **2,931 of 25,593 (11.5%)** | 20 | 20 |
| of which motor | **658** | 0 | 0 |
| of which descending | **35** | 2 | 2 |

### Loop closure

| | A | B | C |
|---|---|---|---|
| **0 pA:** afferents fired | 41/41 | 41/41 | 41/41 |
| closers (presyn to in-scope LF MN) | 6 | 6 | 6 |
| neurons fired downstream | 7 | 7 | 7 |
| in-scope MNs fired | 1 | 1 | 1 |
| **frozen false positives** | **0** | **0** | **0** |
| body-attributable closers | 6 | 6 | 6 |
| closure / lag (ms) | 35.4 / +28.8 | 35.4 / +28.8 | 35.4 / +28.8 |
| excursion (rad) | 1.173 | 1.173 | 1.173 |
| **closes?** | **YES** | **YES** | **YES** |
| **125 pA:** closers | 125 | 141 | 132 |
| in-scope MNs fired | 18 | 19 | 19 |
| **frozen false positives** | **0** | **0** | **0** |
| closure / lag (ms) | 12.4 / +5.8 | 12.4 / +5.8 | 12.4 / +5.8 |
| excursion (rad) | 1.173 | 1.272 | 1.270 |
| **closes?** | **YES** | **YES** | **YES** |

The 0 pA rows are *bit-identical* across arms. That is not a coincidence and it is the
mechanism, not a null result: at 0 pA the only cells that reach threshold are those receiving
the afferent volley through cholinergic and GABA/glutamate synapses, and no `unclear` cell is
on that path. The six closers are the same six cells in the same order at the same times.

### The frozen-physics control

**0 frozen closers and 0 frozen afferent spikes at every usable level in every arm.** The
`freeze_physics` assertion (afferent current constant to <1e-9 pA) passed on all 57 frozen runs.
Policy B is the only arm where the frozen control breaks *inside* the constant-current ladder
(190 pA, 1,731 frozen closers); A and C stay clean to 190 pA.

### Newly active / newly silent

At 0 pA: **0 newly active, 0 newly silent** in all three arms — but only 7 neurons fire
downstream at all there, so that comparison is bounded by the operating point, not by the sign.
Measured at 125 pA, over every neuron that fired (driven pool and afferents excluded):

| | A | B | C |
|---|---|---|---|
| neurons fired | 183 | 208 | 193 |
| newly active vs A | — | **+37** | +14 |
| newly silent vs A | — | **−12** | −4 |

So the policy *does* change who fires once the network has an operating point — it just does not
change the closure verdict, the latency, or the closer set that carries it.

### The spontaneity ceiling — it does shrink under B, on the Poisson arm

Re-measured per policy rather than assumed, with a finer ladder between the shipped rungs
(`refine_ceiling_and_population`):

| | A | B | C |
|---|---|---|---|
| constant: usable max | 125 pA | 125 pA | **135 pA** |
| constant: first spontaneous | none ≤190 | **190 pA** | none ≤190 |
| constant: first pool runaway | 130 pA | 130 pA | 150 pA |
| poisson: usable max | 11 Hz | 11 Hz | 11 Hz |
| **poisson: first spontaneous** | 20 Hz | **14 Hz** | 20 Hz |

**Level 1's 0-125 pA / 0-11 Hz window transfers to all three policies, but B's Poisson headroom
above it shrinks from 20 Hz to 14 Hz.** The prediction that adding excitation to thousands of
neurons would lower the ceiling is confirmed — it just happens above the window we actually use.
`create_background_drive`'s 22 Hz default is above the ceiling in all three arms.

The finer ladder also shows the *pool-runaway* confound arriving much harder under B: at 130 pA
the driven pool goes to 260 Hz (A: 48 Hz, C: 36 Hz). Those rows are excluded, as before.

### IN21A004's broadcast dominance

| | A | B | C |
|---|---|---|---|
| LF MNs contacted / 64 | **46** | **46** | **46** |
| summed PSP onto the 52 | **+33.17 mV** | **+33.17 mV** | **+33.17 mV** |
| rank by breadth, whole VNC | 3 of 2,040 | 3 of 2,047 | 3 of 2,047 |
| broadest closer at 0 pA | IN21A004 46/64 | IN21A004 46/64 | IN21A004 46/64 |
| broadest *excitatory* closer at 125 pA | IN21A004 | IN21A004 | IN21A004 |

**Survives all three, unchanged in every digit.** Two caveats recorded rather than smoothed:

- It was **never rank 1 by breadth**, in any policy. `IN08A002` (800256, glutamate) reaches
  **52 of 64** and `DNg74_b` (525454, GABA) 47. `IN21A004` is the broadest *excitatory* cell,
  which is the claim that matters for a return path STDP would strengthen — but the lab entry's
  "its strongest excitatory relay contacts 72%" should say *excitatory* explicitly, since 72% is
  not the maximum fan-out in the VNC.
- At 125 pA it is **#2 of 125-141 closers**, because `IN08A002` also fires. Level 1 already
  notes this weakens specificity further, not less.

One policy-dependent detail inside the closer table: `Tergotr. MN` (803237, `unclear`) is
Level 1's "structurally presynaptic, electrically silent" curiosity. Under A it contacts
**0** LF MNs at **+0.00 mV**; under B, **11 at +4.91 mV**; under C, **11 at −2.45 mV**. So that
specific anecdote *is* an artefact of policy A — though it does not change any verdict, since it
is a closer in all three arms either way.

### L3 outbound — this is where the policy bites

DNa02 is essentially unmoved: bodyId 523769 is **rank 41-43 of 1,279** at +161.4 mV, and 10360
is **364-378** at +40.0 mV, in every arm. (Both are higher than the issue's "537th and 66th",
which came from a reimplementation.)

The top-6 by summed signed PSP onto interneurons reaching LF MNs:

| policy | top 6 |
|---|---|
| **A** | DNg100 +406, pIP1 +296, DNg37 +295, DNg101 +284, DNge073 +280, aSP22 +279 |
| **B** | DNg100 +406, **DNg34 +404**, **DNge149 +378**, pIP1 +296, DNg37 +295, DNg101 +284 |
| **C** | DNg100 +406, pIP1 +296, DNg37 +295, DNg101 +284, DNge073 +280, aSP22 +279 |

Policy C is identical to A (the `unclear` DNs contribute nothing either way at these ranks);
policy B inserts two cells at #2 and #3 that score **exactly 0.0** under A. The issue's list is
reproduced exactly under A and C, so the reimplementation it warned about was right.

## The Sweep Found a Defect in Its Own Policy B

`DNg34` (10295) and `DNge149` (11466) both have `consensusNt = unclear` **and
`predictedNt = octopamine`** at 0.83 / 0.80 confidence. Policy B assigns them +1 while the same
policy holds octopamine at 0 — an internal contradiction, and the entire L3 reordering rests on
it.

Measured: **101 of the 2,952 `consensusNt = unclear` cells have a modulatory `predictedNt`**
(80 serotonin, 21 octopamine). Holding those 101 at 0 while giving the rest +1 (**policy B′**)
returns the top-6 to exactly A's list. So:

> **The L3 top-6 is not sensitive to the `unclear` sign per se. It is sensitive to whether a
> blanket `unclear = +1` override is allowed to overwrite a specific modulatory prediction.**

This matters because it is the same failure mode the issue was written about, one level down:
"we don't know" is not a single state. `unclear` in `consensusNt` covers 2,676 cells with no
better prediction *and* 276 cells where `predictedNt` says something specific
(94 acetylcholine, 80 serotonin, 64 glutamate, 21 octopamine, 14 histamine, 3 GABA).

## A Second Discrepancy: Which Column the Census Is Taken On

The issue reports **3,377 silenced neurons / 668 motor / 3,230 `unclear`**. This harness measures
**2,931 with outputs (2,972 total) / 658 motor / 2,952 `unclear`**. Both are correct; they read
different columns:

| column | sign-0 neurons | with outputs | motor | `unclear` | synapse share |
|---|---|---|---|---|---|
| `consensusNt` (**live code path**) | 2,972 | 2,931 | 672 (658 with outputs) | 2,952 | 4.97% |
| `predictedNt` | 3,377 | 3,335 | 668 | 3,230 | 5.35% |

`build_live_weights` picks the first non-empty of `consensusNt` / `predictedNt` /
`celltypePredictedNt`, which is always `consensusNt`. **So the numbers that describe our model
are the first row**; the issue's headline figures are the `predictedNt` row. The qualitative
claim is unaffected (11.5% vs 13.2%; 658 vs 668 motor neurons), but the issue's table should be
relabelled, because "counted with `NT_SIGN_MAP` imported from `constants.py`" is necessary and
not sufficient — the *column* matters as much as the map.

## What This Means

**Level 1's headline findings are robust to the sign policy.** The loop conducts, the frozen
control is clean, closure is 35.4 ms at zero background and 12.4 ms at 125 pA, and the return
path is a broadcast dominated by `IN21A004`. None of it moves. So the sign default is **not** a
sixth self-inflicted artefact for Level 1 — this is the first candidate on the list that
survived being swept.

The mechanism is worth stating because it bounds the generality: **Level 1's result is
insensitive because its closing path happens to be entirely non-`unclear`.** That is a property
of this particular circuit, not a licence to assume other results are insensitive. The 125 pA
column already shows 37 neurons switching on under B, and the L3 ranking flips outright.

**The honest conclusion on the policy question: the data does not support choosing one.**
Nothing measured here is *better* under any policy — the three arms are indistinguishable where
it counts and disagree only where the disagreement is a labelling problem (`unclear` vs
`predictedNt`) rather than a biological one. Picking B because it "restores" 3,000 neurons would
be inventing drive; keeping A because it is conservative is still encoding "we don't know" as
"it does nothing."

**Recommendation (a decision to be made by a human, with reasoning, not by this sweep):**

1. **Keep A as the default for now** — not because it is right, but because it is the arm every
   published number was measured under, it is the only one that never invents a synapse, and the
   sweep shows the choice is currently free for Level 1.
2. **Split `unclear` by evidence, and stop treating it as one class.** The 276 cells with a
   specific `predictedNt` should take that prediction's sign (down-weighted by
   `predictedNtConfidence`, which the formula already multiplies in). The 2,676 with nothing
   better are the only genuinely unknown ones. This is a strict improvement under any policy and
   would have prevented the entire `DNg34` episode.
3. **Report sign-sensitivity alongside any result that depends on `unclear` cells** — cheap now
   that `load_full_vnc(nt_sign_map=...)` exists. Rerun the sweep on any new conclusion; do not
   generalise Level 1's insensitivity to it.
4. **Do not use policy B as specified.** Its own top-6 is produced by overriding a modulatory
   prediction the same policy claims to respect.

## Not Verified

- **Only the Level 1 closure probe and the two anatomical rankings were re-run.** The multi-muscle
  sweep's other 22 conditions, the minimum-conducting-rate ladder, the class-protocol grid, and
  the L3 *simulation* (as opposed to its ranking) were not run under B or C. Insensitivity is
  demonstrated for the one condition Level 1 closed on, not for every table in the entry.
- **Policy B′ was computed, not simulated.** The claim "B′ restores A's top-6" is arithmetic on
  the live weight array; no spiking run was made under B′.
- **The Poisson arm is seed-dependent** (the relay-operating-point entry measured +10.2/+19.1 ms
  across 6 runs at 10-11 Hz). All three arms here used `background_seed = 0`, so the 14 Hz vs
  20 Hz ceiling difference is one seed. The constant-current arm is deterministic and is what the
  ceiling claim should rest on.
- **Inhibitory attenuation interacts with policy C and was not swept.** `inh_attenuation = 0.5`
  means policy C's new synapses arrive at half magnitude, so C is a weaker perturbation than B by
  construction — part of why C looks more like A. That 0.5 is itself an unexamined default.
- **No literature check on the `unclear` cells' actual transmitters.** The recommendation to
  split by `predictedNt` is an internal-consistency argument, not a biological validation.
- **Newly-active/newly-silent is a set difference on neuron identity**, not a rate comparison; a
  neuron that fired 1 spike vs 100 counts the same.
- CPU Brian2 only; the GPU path was not exercised.
- The `--quick` path was not used for the reported numbers (full ladder throughout).

## Artifacts

- `src/digital_drosophila/sign_policy.py` — `policy_sign_map`, `silencing_census`,
  `broadcast_ranking`, `closer_broadcast_table`, `dn_outbound_ranking`, `run_policy`,
  `refine_ceiling_and_population`, `compare`, `run_sign_policy`
- `src/digital_drosophila/body_wiring.py` — `nt_sign_map` override on `build_live_weights` /
  `load_full_vnc` (default byte-identical to the shipped map, asserted)
- CLI: `python -m digital_drosophila check sign_policy [--quick] [--policy A,B,C]`
- Issue: [13% of the network is electrically silenced](../issues/2026-08-19-sign-zero-silenced-neurons.md)
- Under test: [multi-muscle loop closure](2026-08-18-multi-muscle-loop-closure.md) ·
  [relay operating point](2026-08-18-relay-operating-point.md)
