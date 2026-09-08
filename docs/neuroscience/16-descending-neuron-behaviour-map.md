# Descending Neurons: Which Ones Drive Which Behaviour

**Date:** 2026-08-19
**Source:** External literature search (forwarded), with every MANC-side claim verified against
`data/cache/full_vnc_network/` before being recorded here.
**Why this exists:** our dataset has **no function annotation** for descending neurons. The `class`
column is NaN for every DN we checked, and names like `DNa02` encode soma position and tract, not
behaviour. Function has to come from the literature.

## Why we needed it

Our first Level 3 experiment picked its stimulus by **summed synaptic strength** onto interneurons
reaching front-leg motor neurons, because that is all our data supports. Two consequences:

1. The winning 6-type set included **`pIP1`**, a documented courtship/song neuron, purely because it
   ranked second by connection strength. Driving by weight alone merges behaviourally distinct
   circuits that happen to project heavily into the VNC.
2. `DNa02`, which we had called "the walking command" internally since Epic 1, **fired 0 of 52 motor
   neurons at every physiological rate.**

## 1. Behaviourally characterised DNs

Activation (causal) vs recording-only (correlational) is distinguished because it decides whether a
neuron is usable as a *stimulus*.

| DN | also known as | behaviour | method | laterality | citation |
|----|---------------|-----------|--------|------------|----------|
| **MDN** | Moonwalker | **backward walking** — initiation + maintenance | opto + thermogenetic activation | bilateral | Bidaye et al. 2014 *Science*; Lee et al. 2023 *PNAS* |
| **DNg100** | **BDN2** | **forward walking** — initiates + maintains | opto activation | bilateral | Sapkal et al. 2023/24 (Bidaye lab) |
| **DNg97** | **oDN1** | **forward walking** | opto activation | bilateral | Sapkal et al. 2023/24 |
| **DNa02** | — | **high-gain steering** (turn velocity) | single-cell ephys (recording) + opto | **unilateral** — drives ipsilateral turn | Rayshubskiy et al. *eLife* |
| **DNp09** | — | **freezing / stopping** (looming-evoked halt) | opto activation; Kir2.1 silencing | bilateral | Zacarias et al. 2018 *Nat Commun* |
| **pIP10** | pIP1, P2b | **courtship song** (wing vibration) | opto + thermogenetic activation | bilateral | von Philipsborn et al. 2011 *Cell* |
| **Giant Fiber** | GF | **escape / takeoff** | opto + electrical | bilateral | Lima & Miesenböck 2005 *Cell* |

### All of these exist in our dataset — verified

| DN | cells in MANC | signed PSP onto LF-reaching interneurons |
|----|---------------|----------------------------------------|
| **DNg100 (BDN2)** | 2 | **+544.5 mV** |
| **DNg97 (oDN1)** | 2 | +377.0 |
| MDN | 4 | +224.6 |
| DNa02 | 2 | +201.4 |
| DNp09 | 2 | +160.9 |
| pIP10 | 2 | **+73.2** (lowest — consistent with not being locomotor) |

Computed with the live weight formula (`log1p(count) · sign · confidence · inh_attenuation · scale`,
`consensusNt`). Naming is via the `synonyms` field: `DNg100` reads *"Sapkal 2024: BDN2"* and `DNg97`
reads *"Sapkal 2024: oDN1"*.

## 2. The connectome independently found the right neuron — and missed another

**`DNg100` was the single highest-scoring DN in our strength ranking, and it is BDN2, the documented
forward-walking command.** The anatomy picked out the correct neuron without knowing what it did.
That is a real validation of ranking by connectivity.

But it is not sufficient:

- It also swept in **`pIP1`/`pIP10`** (courtship) at rank 2, because strength is behaviour-blind.
- It **missed `DNg97`/`oDN1`** — the other documented forward-walking DN, +377 mV, absent from our
  set.

**Lesson: strength ranking is a useful prior and a bad selector.** Use it to generate candidates,
use the literature to filter them.

## 3. DNa02 — we were using it wrong

Our repeated failure to drive walking with DNa02 was **not a modelling defect.**

- It is a **steering** neuron, not an initiator.
- **Turning velocity is set by the right–left *difference* in DNa02 activity** — a see-saw
  arrangement. We drove **both cells equally and bilaterally**, which commands a turn in *no*
  direction while supplying no forward drive. Failure to walk is the expected outcome.
- The literature treats it as whole-body orientation, not front-leg-specific.

**Correct usage: bias a model that is already walking. Do not use it to start one.**

This retroactively affects prior work — DNa02 has been our default "walk" stimulus since Epic 1, so
Epic 4/5/6 training runs were driven by a steering command applied bilaterally from rest.

## 4. The "command neuron" framing is wrong for walking — and this vindicates our result

Asked to push back on our premise, the literature does:

- Population recordings of ~100 DNs in behaving flies (Aimon et al. 2022 *eLife*) find the largest
  fraction of DNs encode walking, and that natural walking uses **partially overlapping subsets of
  dozens of DNs in parallel**.
- Optogenetically forcing 2 cells to produce behaviour demonstrates **sufficiency, not mechanism**.

**So our own finding — 2 cells fail, 12 co-activated cells succeed — is a feature, not a bug.** The
VNC expects distributed excitation. This is the **third** time this project has been pushed from a
clean single-source stimulus to a messier multi-source one:

| level | single source | what actually worked |
|-------|---------------|---------------------|
| L1 motor | single muscle → 0 of 8 conditions | 3 muscles across joint groups |
| L1 neural | single synapse cannot fire a cell | convergence of many |
| L3 command | DNa02 pair → 0/52 | 12 co-activated DN cells |

Design implication: compare **functionally grouped bundles of ~10-15 cells**, not pairs.

## 5. Stimulation parameters — the weakest part

- **Firing rates: not reported.** Optogenetics papers give light intensity (mW/mm²), not evoked
  spike rates, because patch-clamping a freely walking fly is impractical. Tethered single-cell
  ephys suggests native descending commands operate in the **tens of Hz (10-100)**. **Our 50 Hz is
  therefore plausible but uncalibrated.**
- **Duration:** sustained states (forward/backward walking via BDN2 or MDN) need **sustained
  illumination**, seconds. Transient behaviours (GF escape) need only a brief pulse.
- **Population size — a genuine tension, not resolved:** split-Gal4 activation experiments typically
  drive only **2-4 cells** (MDN is 4 total; DNa02 is a pair). Yet natural walking recruits dozens.
  **Both cannot be reconciled in our favour: real experiments make 2 cells suffice and our model
  cannot.** Either our excitability is too low, or optogenetic drive is far stronger than anything
  we simulate. Worth stating rather than assuming the population argument settles it.
- **Latencies:** not found for walking/stopping DNs. The Giant Fiber escape reflex is the exception
  at ~4 ms.

## 6. Recommended command sets for a discriminability test

Three functionally distinct pairs, in ascending order of contrast:

**Pair 1 — forward vs backward walking.** `DNg100`/`BDN2` (+ optionally `DNg97`/`oDN1`) against
`MDN`. Both drive coordinated leg movement, but inter-joint phase must reverse. Identical output for
both would mean the VNC's temporal dynamics are collapsing in our model.

**Pair 2 — locomotion vs arrest (the sharpest contrast).** `DNg100`/`BDN2` against `DNp09`. DNp09
actively halts running. If the circuit cannot distinguish *walk* from *stop*, it cannot distinguish
anything.

**Pair 3 — negative control.** `pIP10`/`pIP1` against `DNg100`. Courtship song drives wing
vibration, not locomotion, so it should recruit far fewer leg motor neurons. Note its PSP score
(+73.2) is already the lowest of the six, which is a consistency check we can make *before* running
anything.

## 7. Not verified / not found

- **Evoked spike rates in Hz** for any of these neurons under optogenetic activation. Our 50 Hz is
  unvalidated.
- **Behavioural onset latencies** for walking/stopping DNs.
- Whether **DNa02 anatomically isolates the front legs**; functional literature treats it as
  whole-body steering. Checkable in MANC, not yet checked by us.
- The 2-4 cell vs dozens-of-cells tension above.
- Citations are as forwarded. `DNg100 = BDN2` and `DNg97 = oDN1` are confirmed **in our own data**
  via the `synonyms` field; the behavioural attributions are not independently confirmed by us.
  Three previously forwarded critiques on this project cited real papers for numbers those papers
  did not contain, so treat the citation column as a pointer to check rather than as established.

## Related

- [Idea: full loop / descending command](../ideas/2026-08-19-full-loop-descending-command.md)
- [Lab: L3 outbound exit gate](../lab/2026-08-19-l3-outbound-exit-gate.md) — the run that used
  strength-ranked sets
- [Task: this literature search](../tasks/2026-08-19-dn-behaviour-literature-search.md)
- `15-lf-leg-neuron-census.md` — what we model vs what exists
