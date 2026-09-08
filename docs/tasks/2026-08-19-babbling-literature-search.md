---
id: 2026-08-19-babbling-literature-search
title: "Literature search: motor babbling in flies, and body-mediated learning on connectome models"
created: 2026-08-19T14:00
status: open
priority: high
type: research
suitability: literature_only
depends_on: []
related:
  - 2026-08-19-dn-behaviour-literature-search
satisfies: []
branch: ""
pr: ""
auto_agent_task_id: ""
---

# Literature search: motor babbling in flies, and body-mediated learning on connectome models

## What we are doing, so you can judge relevance

We built a spiking neural network from the real *Drosophila* ventral nerve cord connectome (MANC:
25,635 neurons, 4.1M synapses) and coupled it to a MuJoCo physics body with Hill-type muscles. We
are testing an idea we call **sensorimotor babbling**:

> Before any reward-based learning, drive motor neurons semi-randomly. The body moves, proprioceptive
> sensors fire, and the feedback returns through the nervous system. If the round trip lands inside a
> plasticity window, the connections that genuinely move the body get strengthened — **the body
> itself is the teacher**, with no reward signal and no supervision.

The motivation: our reward-modulated STDP training produces no visible behaviour. We suspect it is
being asked to discover *which pathways move the body* and *how to coordinate them for locomotion*
simultaneously, and that biology separates these into a developmental phase followed by a
goal-directed one.

**We need to know whether this has already been done, and whether it is known to work or fail.**

## The five questions, in priority order

### 1. Has anyone run body-mediated plasticity on a connectome-derived network? (highest value)

Specifically: a spiking network whose *wiring comes from a real connectome* (*Drosophila* MANC/FAFB/
FlyWire/hemibrain, *C. elegans*, larval *Drosophila*, mouse cortical reconstructions), coupled to a
physics simulation, with plasticity driven by sensory feedback from the body rather than by a task
loss.

- Does this exist? If so, what did it find?
- Distinguish carefully between: (a) connectome-wired networks that are **simulated but not
  embodied**, (b) embodied networks with **hand-designed or random** wiring, and (c) genuinely
  **connectome-wired + embodied + plastic**. We believe (c) is rare or absent; please confirm or
  refute.
- Relevant projects to check: NeuroMechFly (Ramdya lab), the various *C. elegans* whole-animal
  simulations (OpenWorm), Flywire/MANC-based simulation papers, "digital twin" fly efforts.

### 2. Do *Drosophila* show spontaneous motor activity analogous to fetal babbling?

Vertebrate fetuses and neonates produce spontaneous twitches during sleep that appear to build
somatotopic maps (Blumberg's lab is the name we associate with this — please verify).

- Is there an insect or *Drosophila* equivalent? Larval peristaltic waves before hatching, pupal
  spontaneous activity, adult post-eclosion motor exploration?
- Is such activity **known to be instructive** (shaping connectivity) or merely a byproduct of
  circuit maturation? This distinction is the crux for us.
- Does *Drosophila* leg motor control develop through activity-dependent refinement at all, or is it
  largely hardwired genetically? **If fly locomotor circuits are essentially prewired, our entire
  premise may be biologically inappropriate for this organism** — we would rather know.

### 3. Motor babbling as an algorithm: what does it require to work?

Developmental robotics has a motor-babbling literature (we associate Kuniyoshi, Pfeifer, Der &
Martius, and "goal babbling" work — please verify and correct).

- What are the **documented preconditions** for it to succeed? In particular: does it require
  *specific*, low-fan-out sensorimotor pairings?
- **This is our sharpest concern.** Our connectome is highly convergent and divergent: one return
  relay contacts 46 of 64 front-leg motor neurons (72%); driving different descending commands fires
  ~96% of the motor pool with set overlap up to 1.000; 36% of neurons presynaptic to front-leg motor
  neurons also drive other legs. **If babbling algorithms depend on specific pairings, a broadcast
  architecture may be structurally unable to support them.** Has anyone characterised this limit?
- Are there published analyses of when motor babbling **fails**, and why?

### 4. Published negative results

We have accumulated several negative or null findings. We want to know if they are novel or already
known:

- Loop closure through the body is anatomically possible but the return path is **non-specific**
  (broadcast), so credit cannot be assigned to individual motor neurons.
- Distinct descending commands produce nearly identical motor output.
- Reward-modulated STDP on a connectome-wired network produces no measurable behaviour change.

Has any of this been reported? A published negative would be as valuable to us as a positive.

### 5. STDP with long delays, and the credit-assignment problem in embodied loops

- Our measured loop latency is 35-49 ms; our eligibility trace is 1000 ms, so timing is not our
  blocker. But is there literature on **what plasticity rule is appropriate** when action and
  consequence are separated by body physics rather than by synaptic delays? (We associate the terms
  *eligibility trace*, *behavioural timescale synaptic plasticity / BTSP*, *three-factor learning* —
  verify.)
- Our current rule is **additive in both directions and has no depression term** — nothing
  decrements. Is a depression term considered necessary for this class of unsupervised embodied
  learning, or do bounded/normalised additive rules suffice?
- Anything on **spatial** (not temporal) credit assignment in broadcast architectures?

## Deliverable

A markdown document for `docs/neuroscience/`, structured as:

1. **Does prior work exist?** — a direct answer to Q1, with citations
2. **Fly-specific developmental evidence** — Q2, including whether fly locomotor circuits are
   activity-refined or prewired
3. **Preconditions for babbling to work** — Q3, especially any specificity requirement
4. **Known negative results** — Q4
5. **Plasticity-rule guidance** — Q5
6. **What could not be found**, explicitly
7. **Verdict:** is our approach novel, already-done, or already-known-to-fail?

## Rules — please follow these strictly

**Say clearly what you could not find.** "No connectome-wired embodied plasticity study found" is a
genuinely useful answer and may well be the correct one. Do **not** fill gaps with plausible-sounding
work.

**Do not invent or half-remember citations.** We will act on what you report. A confident wrong
citation is worse than an admitted gap. On this project, a forwarded critique cited three real papers
for three numbers — two of those numbers did not appear in those papers, and its central
recommendation would have broken our model had we applied it. We now verify everything, so an
unverifiable claim costs us time rather than saving it.

**The paper-name test:** every claim should be traceable to a specific paper we could go read. If you
cannot name it, say so rather than describing the finding generically.

**Distinguish:** *Drosophila* from other insects from vertebrates; primary research from reviews;
simulation from experiment; correlation from causation.

**Flag figure-derived numbers** rather than presenting them as stated values.

If something is paywalled, say so and name what would need manual retrieval.

## Context that may help you search

- Our terminology may not match the field's. We say "sensorimotor babbling"; the literature may say
  motor babbling, goal babbling, spontaneous motor activity, motor exploration, sensorimotor
  contingency learning, or developmental self-organisation. Please search broadly.
- We are testing at three levels: motor neuron origin, interneuron origin, descending-command origin.
- Our body is one tethered front leg with 15 Hill-type muscles (FlyGym/NeuroMechFly's
  `MusculoskeletalFly`), so whole-body gait is out of scope for now.
- Related internal docs: `docs/neuroscience/12-sensorimotor-babbling.md` (the concept),
  `docs/neuroscience/16-descending-neuron-behaviour-map.md` (a prior literature search that worked
  well — same expected standard).
