# Cross-Generational Learning (Evolution)

This is the outer optimization loop — not simulated within a single
fly's lifetime but across many generations.

Part of the [Learning Strategies](03-learning-strategies.md) series.

## 3a. Genetic evolution (many generations)

**What changes:** Everything. The genome encodes the rules for building
the brain, not the brain itself:

```
Genome encodes:
  - Cell type specifications (which genes each type expresses)
  - Wiring rules (which types tend to connect, with what probability)
  - Receptor profiles (initial sign assignments for each cell type pair)
  - Baseline parameters (channel densities → tau_m, V_rest)
  - Modulatory architecture (which neurons release dopamine, where)
  - Plasticity rules (STDP time constants, learning rates)
  - Epigenetic switching rules (when to activate which presets)
```

**Model implementation:** An evolutionary algorithm (genetic algorithm,
NEAT, or evolutionary strategy) as the outer loop:

```
for each generation:
    genome = select + mutate from previous generation

    for each lifetime:
        brain = build_network(genome)     # topology, signs, baselines
        run_simulation(brain, environment)  # STDP + homeostasis + modulation
        fitness = evaluate(behavior)

    select fittest genomes for next generation
```

**What evolves vs what is learned:**

| Evolved (outer loop) | Learned (inner loop) |
|---------------------|---------------------|
| Which cell types exist | How strong each connection is |
| Which types connect to which | Firing thresholds |
| Initial receptor profiles (signs) | — |
| Baseline tau_m per type | Effective tau_m (via modulation) |
| STDP learning rate | — |
| Epigenetic switching rules | Which epigenetic preset is active |
| Modulatory coupling strengths (k) | — |

**Implementation priority:** Phase 3. This is the long-term vision —
evolving connectomes that learn efficiently. Phase 1–2 use the fixed
connectome from the EM reconstruction as a known-good starting point.

## The open problem: encoding learned skills in the genome

Before we can implement cross-generational learning, we need to solve a
prerequisite problem: **how do we represent a learned skill in a form
that can be inherited?**

A fly that learns an efficient gait through STDP ends up with a
specific pattern of weight magnitudes across thousands of synapses.
That weight pattern *is* the learned skill — but it's not in a form
that can be passed to offspring. The genome doesn't store weight
matrices; it stores rules for building brains. The challenge is: how
does useful information flow from learned weights back into the genome?

### What the genome should encode

The genome shouldn't store the skill itself (the specific weights) — it
should encode **the capacity and predisposition to learn that skill
quickly**. The next generation starts from scratch but benefits from
accumulated knowledge in the form of:

- **Better initial conditions** — weights initialized closer to the
  useful solution, so STDP converges faster
- **Switchable feature presets** — the ability to turn learned
  capabilities on or off rather than forgetting them entirely. After
  an environment change, a previously useful skill should be dormant
  and reactivatable, not erased. This is analogous to how epigenetic
  presets work within a lifetime (section 2b in
  [under-pressure learning](06-learning-under-pressure.md)) but encoded
  at the genetic level
- **Tuned learning rules** — STDP parameters, homeostatic set points,
  and modulatory coupling constants that make the offspring's circuits
  predisposed to discover the same solutions the parent found

This is exactly how real evolution works: a newborn fly can walk within
minutes not because it inherited its parent's specific synaptic weights,
but because evolution shaped the connectome, the initial parameters, and
the learning rules so that the right motor patterns emerge rapidly from
minimal experience.

### Why this is hard

The gap between "learned weight pattern" and "genome that produces
brains that learn that pattern quickly" is the fundamental challenge.
Classical evolutionary algorithms sidestep it — they just mutate genome
parameters and select on fitness, letting the mapping emerge implicitly.
But this is slow (many generations) and opaque (we can't inspect what
was "learned" at the genetic level).

A more principled approach would require:
1. **Skill representation** — a compact encoding of what a trained
   circuit can do, independent of the specific weight values
2. **Genome-to-phenotype mapping** — a differentiable (or at least
   searchable) mapping from genome parameters to the circuit properties
   that produce that skill
3. **Selective inheritance** — the ability to inherit some skills while
   leaving others plastic, rather than an all-or-nothing transfer

We don't yet have a clear design for any of these. This is the primary
research question that needs to be answered before Phase 3 implementation
can begin.

## Established cross-generational mechanisms

Beyond classical genetic evolution (section 3a), several other
cross-generational mechanisms are well-established in the literature.

### 3b. Transgenerational epigenetic inheritance

Epigenetic marks — DNA methylation patterns, histone modifications,
small RNA profiles — can be passed from parent to offspring **without
any change to the DNA sequence**. This is the bridge between
within-lifetime epigenetic regulation (section 2b in
[under-pressure learning](06-learning-under-pressure.md)) and genetic
evolution (section 3a): faster than waiting for random mutations, but
still heritable.

In *Drosophila* specifically:
- Parental **diet** alters offspring metabolic gene expression for 2–3
  generations via changes in histone methylation (H3K27me3)
- Parental **temperature exposure** can shift offspring thermal
  preference and cold tolerance through epigenetic reprogramming of
  thermosensory circuits
- Parental **stress** (predator exposure, starvation) produces offspring
  with higher baseline arousal and faster escape responses — the
  parents' experience primes the next generation's neural operating
  point

The mechanism: during gametogenesis (egg/sperm production), the
chromatin state of the parent's cells — shaped by their lifetime
experiences — is partially preserved in the gametes. The offspring
inherits not just the DNA sequence but a modified epigenetic landscape
that biases gene expression.

**Relevance to the open problem:** This is nature's partial solution to
skill inheritance. The parent doesn't pass down specific weight patterns,
but it passes down an epigenetic context that shifts the offspring's
baseline parameters (V_rest, tau_m, k values, receptor profiles) toward
configurations that were useful in the parent's environment. It's a
soft, probabilistic transfer — not "here's how to escape predators" but
"be more alert, your parent lived in a dangerous place."

**Model implementation:** Between generations, transfer the parent's
epigenetic state (the slow parameter modifications from section 2b) as
initial conditions for the offspring, with some decay (not all marks
survive gametogenesis — typically 2–3 generations of persistence, not
permanent).

**Implementation priority:** Phase 3, but conceptually simpler than
full genetic evolution — it's parameter inheritance rather than
architecture search.

### 3c. The Baldwin effect (genetic assimilation)

The Baldwin effect describes how learning and evolution interact: if a
population can *learn* to solve a problem within their lifetimes, those
individuals survive, and over generations, random mutations that
"hardcode" the same solution into the genome are selected for. A learned
behavior gradually becomes innate.

Waddington demonstrated this directly in *Drosophila* in 1953: exposing
fly embryos to heat shock induced a wing vein phenotype (crossveinless).
After selecting for this phenotype for ~20 generations, the flies
produced it *without* heat shock — the initially learned/induced
response had become genetically fixed.

The implications for our model are direct:
- In early generations, the inner loop (STDP) does most of the work —
  flies learn motor patterns through experience
- Over many generations, the outer loop (evolution) gradually shifts
  initial parameters so that the same motor patterns emerge with less
  and less learning — connections start closer to their "trained" values
- Eventually, some behaviors become essentially innate — the connectome
  is wired so that the right patterns emerge from the architecture alone,
  no STDP needed

This is why a newborn fly can walk almost immediately — millions of
generations of Baldwin effect have hardcoded the CPG tuning that earlier
flies had to learn.

**Model implementation:** No special mechanism needed — this emerges
naturally if the evolutionary outer loop can modify initial weight
values, threshold baselines, and STDP parameters. The key requirement is
that the genome must be able to encode initial conditions for the
parameters that STDP modifies, so that evolution can gradually move
those initial conditions toward the learned optima.

**Implementation priority:** Phase 3. Emerges from having both inner
(STDP) and outer (evolution) loops — but only if the genome
representation is rich enough to encode initial parameter values, not
just architecture.

## 3d. Spontaneous activity-driven development

In biology, a new brain doesn't appear fully formed — it **grows**
through a staged process where spontaneous neural activity shapes the
wiring as it forms. This is fundamentally different from our Phase 1
approach of importing a complete adult connectome.

### How biological development works

The genome doesn't encode a connectome. It encodes a **developmental
program** — a sequence of instructions for building one:

```
Stage 1 — Cell specification:
  Genome → transcription factors → cell fate decisions
  → neurons of specific types are born in specific locations

Stage 2 — Rough wiring:
  Axon guidance molecules (Semaphorin, Netrin, Slit/Robo) →
  axons grow toward target regions → initial coarse connectivity
  Many incorrect connections are made at this stage

Stage 3 — Spontaneous activity refinement:
  Before any sensory input, neurons generate spontaneous
  bursts of activity → STDP-like rules strengthen correlated
  connections and weaken uncorrelated ones → topology is pruned
  and refined

Stage 4 — Critical period refinement:
  Early sensory experience further refines the wiring during
  time-limited windows of high plasticity → activity-dependent
  fine-tuning of the connections that spontaneous activity
  couldn't fully specify
```

The key insight: **at every stage, the network is functional.** There is
never a moment where a complete but untrained network exists. Neurons
integrate into an active, already-partially-functional circuit as they
are born. The network grows and refines simultaneously.

### Spontaneous activity in *Drosophila*

This is not a vertebrate-only phenomenon. *Drosophila* has well-documented
developmental spontaneous activity:

- **Motor circuit maturation** — before hatching, *Drosophila* motor
  circuits in the VNC generate spontaneous coordinated bursting that
  refines CPG wiring. The exact circuits we're modeling were shaped by
  this process.
- **Retinal waves equivalent** — spontaneous photoreceptor activity
  during pupal development refines the retinotopic map in the optic
  lobes (relevant for Phase 2 brain integration).
- **Mushroom body** — spontaneous KC activity during late pupal
  development refines the KC→MBON connectivity that will later support
  associative learning.
- **VNC coordinated waves** — spontaneous activity waves propagate
  along the VNC during development, pruning incorrect intersegmental
  connections and establishing the left-right and anterior-posterior
  coordination patterns.

### Why this matters for cross-generational learning

For the evolutionary outer loop (Phase 3), each new generation needs
more than parameter initialization — it needs a **developmental
process**:

```
What we do in Phase 1 (shortcut):
  Genome → [skip development] → adult connectome from EM data
  → burn-in with random activity → trained network

What nature does (and Phase 3 should approximate):
  Genome → developmental program → neurons born in stages →
  spontaneous activity refines each stage → critical period
  tuning → adult network that was always functional
```

The difference is not cosmetic. Developmental growth produces networks
with qualitatively different properties:

1. **Graceful integration** — new neurons join an active circuit and
   find their role through activity-dependent mechanisms. They don't
   disrupt existing function because existing function shaped their
   integration.
2. **Redundancy and robustness** — the pruning process eliminates
   weak/incorrect connections, leaving multiple independent pathways
   for critical functions.
3. **Topology co-adapted with weights** — the wiring was shaped by the
   same activity patterns that the weights encode. In our Phase 1 model,
   the topology comes from biology but the weights come from our
   burn-in — they were never co-optimized.

The genome doesn't evolve to produce a good network — **it evolves to
produce a good developmental process that produces a good network.**
This is a crucial distinction for Phase 3: the evolutionary algorithm
should optimize developmental rules (cell birth timing, guidance
molecule gradients, spontaneous activity patterns, critical period
durations), not network parameters directly.

### The same genome, different brains

Because development is activity-dependent and activity has stochastic
components, the same genome produces slightly different connectomes each
time. The EM reconstruction we're using (male-cns:v0.9) is one specific
instance — one roll of the developmental dice. Other flies of the same
genotype would have the same cell types and gross wiring patterns but
different fine-scale connectivity.

This variability is **not a bug** — it's a feature. The genome specifies
wiring *probabilities* and *rules*, not an exact adjacency matrix. The
developmental process samples from this distribution, and the resulting
diversity makes the population more robust to environmental variation.

### Relationship to Phase 1 burn-in

The burn-in period described in [normal learning](04-learning-normal.md)
is our Phase 1 approximation of developmental spontaneous activity.
It's a simplification — burn-in can only adjust weights and thresholds
on a fixed topology, while real development co-optimizes both. But for
Phase 1 with a known-good connectome, burn-in is sufficient to reach a
functional starting state.

**Implementation priority:** Phase 3. Requires a generative model that
produces connectomes from genome specifications — a developmental
simulator that runs the growth program, generates staged spontaneous
activity, and applies activity-dependent refinement at each stage.
Essential for the evolutionary loop to work properly, since evolution
acts on genomes that produce developmental programs, not on brains
directly.

## Acknowledged simplifications

The following cross-generational mechanisms are documented in the
literature but are not included in our current design.

### Maternal effects

The mother's environment affects offspring neural development through
non-genetic, non-epigenetic mechanisms:
- **Egg provisioning** — the amount of yolk, mRNA, and nutrients
  deposited in the egg depends on maternal nutrition and stress state.
  This affects the resources available for embryonic brain development.
- **Maternal hormones** — ecdysone and juvenile hormone levels in the
  mother influence egg development, potentially altering the offspring's
  developmental trajectory.
- **Oviposition site selection** — where the mother lays eggs determines
  the offspring's early environment (temperature, food quality, pathogen
  exposure), which shapes activity-dependent development.

**Impact on our model:** Without maternal effects, offspring start from
identical conditions regardless of parental experience (aside from
epigenetic inheritance). Including them would add another channel of
cross-generational information transfer.

**Implementation difficulty:** Moderate. Could be modeled as
environment-dependent perturbations to offspring initial conditions.

**Priority:** Phase 3 or beyond.

### Sexual selection and dimorphism

Our model uses the male-cns dataset. Male and female *Drosophila* have
substantially different neural circuits in specific regions — the
*fruitless* (fru) and *doublesex* (dsx) transcription factors create
sex-specific neuron populations and connectivity. Evolution acts
differently on male and female circuits via sexual selection (e.g.,
male courtship song circuits are under strong sexual selection; female
egg-laying circuits are under natural selection).

**Impact on our model:** Using only the male connectome means our model
cannot capture sex-specific circuit evolution. For VNC motor control this
is minor (locomotion is largely shared), but for brain circuits (Phase
2+) it becomes significant.

**Implementation difficulty:** Low if we just model one sex. High if we
want to model sexual selection with dimorphic circuits.

**Priority:** Phase 3 or beyond.

### Somatic mosaicism from transposable elements

Transposable elements (TEs) are DNA sequences that copy and insert
themselves into new genomic locations. They are active in *Drosophila*
neurons, causing insertional mutations in somatic (non-germline) DNA.
This means individual neurons within the same brain can be genetically
distinct — carrying different TE insertions that may alter gene
expression.

This is a source of neural diversity beyond what the genome specifies:
two neurons of the same cell type, with the same genome, may express
slightly different channel densities due to somatic TE insertions. It
may be adaptive (generating functional diversity for selection to act on
at the circuit level) or just genomic noise.

**Impact on our model:** Without somatic mosaicism, all neurons of the
same cell type are identical in their base parameters. Including it
would add per-neuron noise to cell-type-level parameters.

**Implementation difficulty:** Low. Random perturbation of per-neuron
parameters around the cell-type mean.

**Priority:** Phase 3 or beyond. Could be included as a simple noise
model if we need per-neuron parameter diversity.

### Genetic drift

Not all cross-generational change is adaptive. In small populations,
random fluctuations in allele frequency can fix or lose alleles
regardless of their fitness effect. This is particularly relevant for:
- Small population simulations where stochastic effects dominate
- Neutral mutations that don't affect fitness but accumulate over
  generations
- Genetic bottlenecks (a few survivors founding a new population)

**Impact on our model:** If the evolutionary loop uses small population
sizes (likely, due to computational cost of simulating each individual),
drift will be significant. Some "evolved" changes won't be adaptive —
they'll be random fixation. This is biologically realistic but makes
it harder to interpret what evolution "learned."

**Implementation difficulty:** None — drift happens automatically in
any finite-population evolutionary algorithm.

**Priority:** Not a mechanism to implement but a phenomenon to be
aware of when interpreting evolutionary results.

### Niche construction

Organisms modify their environment — pheromone trails, food caches,
silk structures, waste products — and these modifications change the
selection pressures on future generations. A fly population that creates
a fermentation-rich food source (by inoculating fruit with yeast) alters
the nutritional environment for its offspring, selecting for different
metabolic and foraging traits.

**Impact on our model:** If the evolutionary loop includes a static
environment, we miss the feedback loop where organisms shape their own
selection pressures. Including niche construction would mean the
environment co-evolves with the population.

**Implementation difficulty:** Moderate. Requires a mutable environment
that organisms can modify and that persists across generations.

**Priority:** Phase 3 or beyond. Interesting for open-ended evolution
but not needed for basic evolutionary optimization.

## Ideas

> **Note:** The ideas below are exploratory and intended for future
> investigation. They are not part of the current implementation plan.

### Defining the SNN's DNA as a probabilistic generative model

The "DNA" of our SNN can be thought of as two things: the **connection
structure** (topology) and the **weights**. Rather than storing a
specific connectome, the DNA could encode a **probabilistic model**
capable of generating a neural network — one that produces structurally
similar but not identical networks each time, much like how biological
DNA produces brains that share gross architecture but differ in
fine-scale wiring (see "The same genome, different brains" above).

Concretely, the DNA file would define:

1. **Neuron type specifications** — how many distinct neuron types exist,
   along with the fixed or predefined parameters for each type. These
   parameters include the size and coefficients of the
   [LIF equation](02-lif-model-design.md) (tau_m, V_rest, V_thresh,
   refractory period, etc.) that govern each type's electrical behavior.

2. **Connectivity rules** — the number of neurons per type and the
   probabilistic rules for how they connect to each other. Rather than
   an explicit adjacency matrix, this would be connection probabilities,
   fan-in/fan-out distributions, and type-to-type wiring tendencies —
   enough to sample a concrete network from the distribution.

3. **Spatial layout** — where each neuron type is located within the
   brain, defining the spatial constraints that influence connectivity
   (neurons that are physically close are more likely to connect,
   axon guidance is region-dependent, etc.).

Given these parameters, the DNA file encodes enough information to
**reconstruct a neural network** that is structurally faithful to the
original — same cell types, same broad connectivity patterns, same
parameter ranges — without being an exact copy. Each instantiation
would be a different sample from the same generative distribution.

The neural network itself is defined using the LIF model design
documented in the same folder. The DNA layer sits above it: it
specifies *which* LIF neurons to create, *how* to parameterize them,
and *how* to wire them together.

This idea connects directly to section 3d (spontaneous activity-driven
development): the probabilistic DNA would produce the initial rough
wiring, and then developmental spontaneous activity would refine it
into a functional circuit — just as in biology.
