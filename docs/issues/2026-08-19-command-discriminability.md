# Does This Connectome Discriminate Between Commands At All?

**Date:** 2026-08-19
**Status:** todo
**Parent:** [Idea: full loop / descending command](../ideas/2026-08-19-full-loop-descending-command.md)
**Type:** experiment (gates the full-loop experiment)

## Problem

**This is now the central question of the babbling programme, not a caveat.** The same result has
appeared at every level we have measured, and in the static wiring:

| where | finding |
|-------|---------|
| L1 return path | one relay (`IN21A004`, bodyId 800802) reaches **46 of 64** LF motor neurons |
| L3 outbound | conducting conditions fire **96%** of the motor pool; Jaccard overlap between different DN sets **up to 1.000** — *identical* motor output from different commands |
| static wiring | **36%** of the 2,047 neurons presynaptic to LF motor neurons also drive another leg's motor neurons; 54 touch all six |

**If distinct commands cannot produce distinct motor patterns, sensorimotor babbling fails at every
level** — there would be nothing for body-mediated correlation to teach. That is a premise problem,
not a Level 3 problem, so it must be settled before the full-loop experiment is built. A full loop
that cannot distinguish its own commands would not be interpretable.

## Why the earlier version of this test would have been uninterpretable

The first plan was "drive DN set A vs set B and see whether output differs." But our sets were
chosen by **summed synaptic strength**, not function — and one of them (`pIP1`) turned out to be a
courtship neuron included purely because it ranked second by connection weight.

With strength-ranked sets, a null result cannot distinguish:

- "the circuit genuinely cannot discriminate commands", from
- "we picked two arbitrary bundles that happen to overlap".

**So the sets must be defined by documented behaviour.** See
`../neuroscience/16-descending-neuron-behaviour-map.md`.

## The command sets — verified present in MANC

| DN | = | cells | signed PSP onto LF-reaching relays | documented behaviour |
|----|---|-------|-----------------------------------|---------------------|
| `DNg100` | **BDN2** | 2 | **+544.5 mV** | forward walking (initiates + maintains) |
| `DNg97` | **oDN1** | 2 | +377.0 | forward walking |
| `MDN` | Moonwalker | 4 | +224.6 | backward walking |
| `DNp09` | — | 2 | +160.9 | freezing / stopping |
| `pIP10` | pIP1 | 2 | **+73.2** | courtship song (wing, not leg) |
| `DNa02` | — | 2 | +201.4 | **steering — see caveat below** |

## The three tests, in ascending order of contrast

**Test 1 — forward vs backward.** `DNg100` (+`DNg97`) versus `MDN`. Both drive coordinated leg
movement, but inter-joint phase must reverse. Identical output would mean the VNC's temporal
dynamics collapse in our model.

**Test 2 — locomotion vs arrest. The sharpest available contrast.** `DNg100` versus `DNp09`. DNp09
actively halts running. **If the circuit cannot distinguish walk from stop, it cannot distinguish
anything**, and that is the result that would end the programme in its current form.

**Test 3 — negative control.** `pIP10` versus `DNg100`. Courtship song drives wing vibration, not
locomotion, so it should recruit markedly fewer leg motor neurons. Note `pIP10` already has the
lowest PSP score of the six — a consistency check available *before* running anything. **If pIP10
produces the same leg output as BDN2, the model is not discriminating at all** and Tests 1-2 need no
interpretation.

Run Test 3 first. It is the cheapest and the most diagnostic: a failure there invalidates the others.

## DNa02 must be driven differently, or excluded

**Turning velocity is set by the right–left *difference* in DNa02 activity** — a see-saw. Our
earlier run drove **both cells equally and bilaterally**, which commands a turn in no direction with
no forward drive; 0 of 52 motor neurons fired, which is the correct outcome for that stimulus.

If DNa02 is included, drive it **unilaterally** (one side only) and expect asymmetry, not
locomotion. Better: use it only as a bias on top of an already-walking `DNg100` condition. **Do not
use it to initiate movement** — that was our error, not the model's.

## What to measure

For each pair, and for each of the two sets in it:

- **Which of the 52 in-scope LF motor neurons fire** — the identity set, not just the count
- **Jaccard overlap** between the two sets' motor outputs. This is the headline number.
- **A chance baseline.** Overlap must be compared against what random DN sets of the same size
  produce, not against zero. **Design this baseline explicitly** — if two random size-matched DN
  sets already overlap at 0.9, then 0.95 for BDN2-vs-MDN means nothing.
- **Per-joint-group breakdown** (coxa / trochanter / tibia) — the whole-pool count may hide
  structure. Forward vs backward should differ in *phase*, possibly not in *which* neurons fire.
- **Firing-rate profiles, not just binary fired/didn't.** Two commands could recruit the same
  neurons at different rates, which is still discrimination. Binary overlap would miss it.
- **Timing** — order of motor neuron recruitment. Phase reversal between forward and backward may
  show up here and nowhere else.

## Non-negotiable controls

- **Frozen-physics control for every condition** — pin `qpos`/`qvel`/`act` so nothing can move, all
  neural drive unchanged. Anything firing in both conditions did not hear from the body.
- **Cut-projection control** — zero the driven DNs' outgoing synapses. If motor neurons still fire,
  the DN projection was not responsible. (Added by an agent on the last experiment after noticing a
  clean-looking pass could have been spurious; keep it.)
- **Settle ~3000 physics steps before measuring** (`dt = 0.1 ms`).
- **Restore `data.act` between conditions**, not just `qpos`/`qvel`.
- **Set the background operating point explicitly.** Usable window 0-125 pA constant / 0-11 Hz
  Poisson; above that relays fire spontaneously. `create_background_drive`'s own 22 Hz default is
  *above* that ceiling. This was the fifth self-inflicted artefact on this project.
- Force model on (default in `MuscleDecoder`). Scope 52 of 64 LF motor neurons.
- Drive **~10-15 cells per condition** where the functional set allows it — the literature says
  natural walking recruits dozens of DNs in parallel, and our own result is that 2 cells fail while
  12 succeed. Report the cell count with every condition.

## Gotchas

- `connectivity.npz`: `sources`/`targets` are **row indices into meta.csv, NOT bodyIds**; `weights`
  are synapse counts (1-1032), not mV.
- A type name can cover several cells across sides and segments. Resolve by bodyId; report per-cell.
- `MDN` has 4 cells, the others 2. Cell count differs between conditions — control for it or state
  it, since more cells means more drive.

## Verification standard

Every number from a real run: `SpikeMonitor` counts, not computed predictions. **A current is not a
spike** — this project once reported 60.68 pA (0.38× rheobase) as evidence an encoder worked.

**Six findings here have dissolved into our own unexamined defaults.** Before reporting any number
as biology, ask whether it is a property of a value we chose. Finding a seventh would be a good
outcome.

**If the answer is "no, it does not discriminate", say so plainly.** That is the most valuable
result this experiment can produce, and it would redirect the whole programme rather than just this
level. Do not tune until the numbers look better.

## Report

Jaccard overlap per pair, against an explicit chance baseline. Which motor neurons fire per command,
per joint group. Rate profiles and recruitment order, not just binary sets. All four controls per
condition. Whether the circuit discriminates — and if only weakly, at what granularity (whole pool /
joint group / rate / timing). Anything you could not verify, flagged rather than smoothed over.

## Related

- `../neuroscience/16-descending-neuron-behaviour-map.md` — where the command sets come from
- `../lab/2026-08-19-l3-outbound-exit-gate.md` — the 1.000 overlap that motivates this
- `../neuroscience/15-lf-leg-neuron-census.md` — the 36% multi-leg input figure
