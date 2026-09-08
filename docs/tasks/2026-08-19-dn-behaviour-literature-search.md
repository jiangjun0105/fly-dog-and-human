---
id: 2026-08-19-dn-behaviour-literature-search
title: "Literature search: which Drosophila descending neurons drive which behaviour"
created: 2026-08-19T12:00
status: open
priority: high
type: research
suitability: literature_only
depends_on: []
related:
  - 2026-08-19-l3-outbound-exit-gate
satisfies: []
branch: ""
pr: ""
auto_agent_task_id: ""
---

# Literature search: which *Drosophila* descending neurons drive which behaviour

## The question

**Which descending neurons (DNs) in *Drosophila* are experimentally documented to drive specific
behaviours — and what exactly was done to them to produce that behaviour?**

We need this to pick stimuli by *function* rather than by anatomical connection strength.

## Why we need it — the concrete problem

We simulate the fly ventral nerve cord connectome (25,635 neurons, 4.1M synapses, MANC) as a
spiking network coupled to a MuJoCo body. We want to test whether a "brain command" produces a
distinguishable leg-movement pattern.

We ran a first version and it exposed a gap we cannot close from our own data:

- We drove `DNa02` because we had been calling it "the walking command" internally. **It failed to
  make any motor neuron fire at any physiologically plausible rate.**
- We then drove a set of 6 DN types chosen purely by *summed synaptic strength* onto interneurons
  that reach front-leg motor neurons. That worked — 50 of 52 motor neurons fired.

But the working set is not a command. It is a strength-ranked list, and it includes **`pIP1`**,
which we later realised is a documented **courtship/song** neuron. We put a courtship neuron in a
set meant to drive walking because it ranked second by synapse count.

**Our dataset has no function annotation.** The `class` column is NaN for every DN we checked.
Names like `DNa02` encode anatomy (soma position, tract), not behaviour. The only functional hints
are literature citations in a `synonyms` field, e.g. `"Kimura 2008, Kohatsu 2010: P2b; Cachero
2010: pIP-a; Yu 2010: pIP1"`.

So: function has to come from the literature. Without it, our planned discriminability test
("do different commands produce different movements?") is uninterpretable — a null result would not
distinguish "the circuit cannot discriminate" from "we picked two arbitrary bundles that overlap."

## What to find

### 1. A table of behaviourally characterised DNs

For each DN with a documented behavioural role, report:

- **Name(s)** — including synonyms across papers, since naming is inconsistent (DNa02, aSP22/DNa12,
  DNg100/BDN2 are examples we have already hit). Give the MANC/FlyWire type name if stated.
- **Behaviour driven** — be specific: forward walking, backward walking, turning/steering, stopping,
  grooming, escape/takeoff, courtship song, landing, etc.
- **What was done experimentally** — optogenetic activation (CsChrimson?), thermogenetic (dTrpA1?),
  electrical stimulation, or only *recording* during spontaneous behaviour. **This distinction is
  critical**: a neuron whose activity *correlates* with walking is not the same as one whose
  activation *causes* walking.
- **Was the effect unilateral or bilateral?** Several DNs turn the fly when driven on one side.
- **Citation** — author, year, journal, and whether the finding is in the text or read from a figure.

### 2. Stimulation parameters actually used

This is as important as the neuron identity, because our model needs numbers:

- **Firing rates** evoked or imposed. We currently need 50 Hz on 12 cells to make our circuit
  conduct, and we do not know whether that is plausible.
- **Duration** of stimulation, and whether behaviour required sustained drive or a brief pulse.
- **How many cells** were driven — single neuron, a bilateral pair, or a whole Gal4/split-Gal4
  population? **If populations, roughly how many cells?** Our result depends critically on
  co-activation: single DNs fail in our model and 12 cells succeed, so knowing the real recruitment
  size would tell us whether that is biological or an artefact.
- Any reported **latency** from stimulation onset to movement onset.

### 3. Specifically: DNa02

We have used it throughout the project and it does not work in our model. Please establish:

- What behaviour is DNa02 actually documented to drive? Our current belief is **steering/turning**
  (possibly Rayshubskiy et al.), **not** initiating walking from rest — please confirm or refute.
- Does the literature support DNa02 driving **front-leg** motor neurons specifically?
- Is it usually driven **unilaterally** (one side) to produce turning?
- Are its two cells (one per side) functionally distinct?

### 4. DNs to avoid, and known antagonists

- Which well-known DNs drive behaviours **irrelevant or opposed** to walking (courtship, grooming,
  escape)? We need this to build a *negative* control set for the discriminability test — pairs of
  commands that should produce clearly different motor output if the circuit discriminates at all.
- Are there documented **stopping** DNs (e.g. "brake" neurons)? A walk-vs-stop pair would be the
  sharpest discriminability test available.

### 5. Whether a "command neuron" framing is even right

Push back on our premise if the literature does. Do papers describe DNs as individually sufficient
commands, or as **populations whose combined activity** specifies behaviour? If the latter, our
plan to compare "command A vs command B" may be the wrong experimental design, and we would rather
know that now.

## Likely relevant labs and papers

Not exhaustive — treat as starting points, not a reading list to confirm:

- **Gwyneth Card / Wyatt Korff** — escape, takeoff, giant fiber pathway
- **John Tuthill** — leg proprioception and motor control
- **Rachel Wilson / Jonathan Rayshubskiy** — DNa02 and steering
- **Michael Dickinson** — flight control
- **Barry Dickson** — moonwalker (MDN) backward walking, courtship circuits
- **Salil Bidaye** — walking DNs, "BDN2" appeared in our data as a Sapkal 2024 synonym
- **MANC / FlyWire connectome papers** — may include function annotations our cached CSV lacks
- Reviews of *Drosophila* descending control would be an efficient entry point

## Deliverable

A markdown document suitable for `docs/neuroscience/`, structured as:

1. **Summary table**: DN name(s) → behaviour → method (activation vs recording) → citation
2. **Stimulation parameters** section: rates, durations, population sizes, latencies
3. **DNa02 verdict**: what it does, whether our usage was wrong
4. **Recommended command sets** for a discriminability test — ideally 2-3 functionally distinct,
   well-documented sets, with the reasoning for each
5. **What could not be found**, explicitly

## Rules — please follow these strictly

**Say clearly what you could not find.** "No stimulation rate is reported for this neuron" is a
useful and expected answer. Do **not** fill gaps with plausible-sounding numbers.

**Do not invent or half-remember citations.** We will act on what you report. A confident wrong
citation is worse than an admitted gap — we have already had a forwarded critique cite three real
papers for three numbers, two of which did not exist in them, and one recommendation which would
have broken our model had we applied it.

**Distinguish causation from correlation** everywhere: activation experiments vs recording-only.

**Distinguish *Drosophila* from other insects**, and primary research from reviews.

**Flag figure-derived numbers as such** rather than presenting them as stated values.

If a paper is paywalled and you cannot read the relevant part, say so and name what would need to
be retrieved manually.

## Context that may help

- The connectome we use has **1,305 descending neurons** and only 4 `cb_intrinsic` (brain) neurons,
  so we model the VNC and treat DNs as the input boundary.
- We are testing "sensorimotor babbling": whether the body's own physics can teach the network which
  neurons move it, before any reward learning.
- Prior finding that motivates the specificity question: in our model, different DN sets produced
  **Jaccard overlap up to 1.000** in which motor neurons fired — i.e. identical motor output from
  different commands. We want to know whether that is a property of the connectome or an artefact of
  choosing our command sets badly.
