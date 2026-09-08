# 13% of the Network Is Electrically Silenced by an Unexamined Sign Default

**Date:** 2026-08-19
**Status:** sensitivity experiment DONE; policy decision still open
**Type:** defect + sensitivity experiment

> **RESULT (2026-08-19):** [Lab: sign-policy sensitivity](../lab/2026-08-19-sign-policy-sensitivity.md).
> **Level 1 is not policy-dependent** — closure is identical under all three arms (35.4 ms /
> 6 closers / 0 frozen at 0 pA; 12.4 ms / +5.8 ms at 125 pA), and `IN21A004` 800802 holds at
> 46 of 64 / +33.17 mV in every arm, because the closing path contains no `unclear` cell.
> **The L3 outbound top-6 IS policy-dependent** — policy B inserts `DNg34` (+404) and `DNge149`
> (+378) at #2 and #3, both exactly 0.0 under A. But **both have `predictedNt = octopamine`**,
> so policy B contradicts its own rule that octopamine stays 0; holding those 101 cells at 0
> restores A's list exactly. Two corrections to this issue below.
>
> - The census here is on **`predictedNt`**; the live code path reads **`consensusNt`**, giving
>   **2,931 silenced / 658 motor / 2,952 `unclear` / 4.97% of synapses**. Both correct, different
>   columns — importing the map is necessary but not sufficient, the column matters too.
> - `unclear` is **not one class**: 276 of the 2,952 have a specific `predictedNt`
>   (94 acetylcholine, 80 serotonin, 64 glutamate, 21 octopamine, 14 histamine, 3 GABA).
>   Recommended fix is to split by evidence rather than pick a blanket sign.

## Problem

The shared weight formula (`network.py:447`) is

```python
weights_raw = log1p(count) * sign_vector * confidence * sign_scale * scale
```

`sign_vector` is **+1** for acetylcholine, **−1** for GABA/glutamate, and **0** for everything
else. A zero sign does not attenuate a synapse — it deletes it. The presynaptic neuron still
receives input, integrates and fires; nothing downstream ever hears it.

> **CENSUS CORRECTED 2026-08-19.** The figures below were counted from `predictedNt`. The live
> weight path reads **`consensusNt`** (`network.py:435`). Correct numbers: **2,972 of 25,635
> neurons (11.6%)** fully silenced, **4.97%** of synapses, of which `unclear` is 2,952. The
> superclass breakdown is 672 motor / 570 sensory / 188 intrinsic / 99 efferent. The finding is
> unchanged in substance — importing `NT_SIGN_MAP` was necessary but not sufficient; the *column*
> matters too.

**Measured on the full VNC (2026-08-19):**

| | count |
|---|---|
| Synapses with sign = 0 | ~5.5% of 4,114,854 |
| **Neurons whose *entire* output is silenced** | **3,377 of 25,635 (13.2%)** |

The neuron-level number is the one that matters: a neuron with every output at zero is
functionally absent from the circuit.

Which neurons:

| superclass | fully silenced |
|---|---|
| vnc_sensory | 842 |
| **vnc_motor** | **668** |
| vnc_intrinsic | 310 |
| vnc_efferent | 98 |
| ascending_neuron | 48 |

*(Counted with `NT_SIGN_MAP` imported from `constants.py`, not reimplemented.)*

**668 of 702 motor neurons** in the dataset are silenced. 35 descending neurons are too —
including `DNg34`, which was briefly (and wrongly) ranked as the top outbound driver for the
L3 experiment precisely because a sign-blind ranking could not see that it transmits nothing.

By neurotransmitter:

| NT | neurons | share of synapses | verdict |
|----|---------|-------------------|---------|
| `unclear` | 3,230 | 4.17% | **indefensible as zero** — a prediction failure, not a biological fact |
| `serotonin` | 120 | 0.47% | defensible abstraction, but should be a documented decision |
| `octopamine` | 27 | 0.71% | same |
| `dopamine` | 0 present | — | mapped to `None`; no such neurons in this dataset |

`histamine` is **already correctly −1** in `constants.py:7` — an earlier draft of this issue
claimed it was a defect, which was wrong: that came from reimplementing the sign map instead of
importing it. The only sign-zero neurotransmitters are **`unclear`, `serotonin`, `octopamine`**.

## Why this is not a simple fix

1. **`unclear` genuinely has unknown sign.** Defaulting it to excitatory (the 56% majority)
   would inject 3,230 neurons' worth of invented drive. Zero encodes "we don't know" as "it does
   nothing" — the strongest claim from the weakest evidence — but guessing is not obviously better.
2. **It is the shared formula**, so any change alters every result the project has produced.
3. **It is exactly the kind of parameter that can manufacture a desired answer.** Five findings on
   this project have already dissolved into unexamined defaults; this is the sixth. Choosing the
   policy that makes an experiment succeed would be the worst possible way to resolve it.

## Desired Behavior

**Do not pick a sign policy. Measure whether the conclusion depends on one.**

Run the same conduction measurement under three policies for `unclear`:

| policy | `unclear` sign |
|--------|----------------|
| **A (current)** | 0 — silenced |
| **B** | +1 — excitatory, the 56% majority class |
| **C** | −1 — inhibitory |

- If a result holds under all three, the choice does not matter and we record that.
- If it holds under only one, **that policy is the result** and must be justified from biology
  rather than convenience.

Keep `serotonin`/`octopamine` at 0 in all three arms (genuinely neuromodulatory, slower
timescale, arguably not a fast PSP at all) so the sweep isolates one variable.

## What to measure

The L1 conduction result is the cheapest well-characterised probe we have, and it has a clean
control. For each of the three policies report:

- Does the multi-muscle protocol still close the loop? (`3group:strongest x3`, slow 50 Hz + fast
  2 spikes, 200 ms — baseline closes at 35.4 ms with 6 closers, or 12.4 ms at 125 pA background)
- How many closers fire, and how many are presynaptic to in-scope LF motor neurons
- **Frozen-physics false-positive count** — non-negotiable, at every policy
- How many neurons become newly active or newly silent
- Whether `IN21A004` (bodyId 800802) remains the dominant broadcast relay — the finding that
  closed Level 1 rests on it

Also report the effect on the **L3 outbound** figures, since that experiment is live: DNa02's
rank, and the corrected top-6 DN list (DNg100 10056, pIP1 10030, DNg37 10506, DNg101 11527,
DNge073 11737, aSP22 10090). Under policy B, 3,230 previously-silent neurons start transmitting,
which could reorder that list substantially.

## Constraints

- **Settle ~3000 physics steps before measuring** (`dt = 0.1 ms`).
- **Restore `data.act` between conditions**, not just `qpos`/`qvel`.
- **Set the background operating point explicitly** — usable window 0-125 pA constant or
  0-11 Hz Poisson. `create_background_drive`'s own 22 Hz default is *above* the spontaneity
  ceiling. Policy B adds excitation to 3,230 neurons, so **re-verify the spontaneity ceiling per
  policy** rather than assuming Level 1's window transfers.
- Scope: 52 of 64 LF motor neurons (excludes 6 tarsus, 6 `ltm*`).
- Reuse `body_wiring.py` — lockstep loop, frozen-physics mode, background sweep, settle assertions
  all exist. Do not rebuild them.
- `connectivity.npz`: `sources`/`targets` are **row indices into meta.csv, NOT bodyIds**;
  `weights` are synapse counts (1-1032), not mV.

## Verification standard

Every number from a real run — `SpikeMonitor` counts, not computed predictions. A current is not
a spike; this project has already reported a sub-rheobase current as evidence a neuron fired.

**The honest outcome may be that our Level 1 conclusions are policy-dependent.** If so, say it
plainly. Discovering that a headline finding rests on an arbitrary sign default would be a
valuable result, not a failure.

## Related

- [L3 outbound exit gate](2026-08-19-l3-outbound-exit-gate.md) — where the sign-blindness surfaced
- [Lab: relay operating point](../lab/2026-08-18-relay-operating-point.md) — the fifth artefact of
  this kind, and the background-window source
- `src/digital_drosophila/network.py:447` — the formula
