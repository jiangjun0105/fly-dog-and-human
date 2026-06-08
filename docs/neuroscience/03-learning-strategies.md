# Learning Strategies

How the Digital Drosophila model adapts at different timescales — from
millisecond spike timing to cross-generational evolution. Each timescale
operates on different parameters with different mechanisms, and they
nest inside each other: fast learning runs within the constraints set by
slower adaptation, which runs within the scaffold set by evolution.

## Timescale overview

```
Timescale          Mechanism                What changes
─────────────────────────────────────────────────────────────────────
ms–seconds         Synaptic dynamics        Short-term facilitation/depression
seconds–minutes    STDP + reward gating     Weight magnitudes (w_ij)
minutes–hours      Synaptic tagging         Marks recent changes for consolidation
minutes–hours      Homeostatic plasticity   Firing thresholds (V_th)
hours–days         Sleep/wake cycling       Consolidates tagged memories, prunes noise
hours–days         Synaptic decay           Unused weights fade toward zero
hours–days         Epigenetic regulation    Signs, receptor profiles, baselines
generations        Evolution                Topology, cell types, all of the above
```

These timescales are organized into four regimes, each covered in a
separate document:

| Document | Regime | Timescale | What adapts |
|----------|--------|-----------|-------------|
| [Normal learning](04-learning-normal.md) | Stable environment | ms – hours | Weights, thresholds, learning rates |
| [Memory consolidation](05-learning-memory-consolidation.md) | Retrieval dynamics | ms – hours | Temporal filtering, memory triage, sleep consolidation |
| [Under-pressure learning](06-learning-under-pressure.md) | Changing environment | seconds – weeks | Operating point, signs, topology |
| [Cross-generational learning](07-learning-cross-generational.md) | Across lifetimes | generations | Everything — the genome encodes brain-building rules |

## How the timescales nest

Fast mechanisms run **within** the constraints set by slower ones:

```
Evolution sets:        cell types, wiring rules, baseline parameters
  └─ Epigenetics sets: receptor profiles, channel densities, active gene presets
       └─ Homeostasis sets: target firing rates, threshold baselines
            └─ Neuromodulation sets: current gain, effective thresholds
                 └─ STDP adjusts: individual connection strengths
                      └─ STF/STD shapes: moment-to-moment transmission
```

Each layer takes the output of the slower layer above it as a given
constraint and optimizes within it. A fly's STDP doesn't redesign the
wiring — it tunes weights within the existing topology. Epigenetics
doesn't invent new cell types — it adjusts the operating parameters of
existing ones. Only evolution can change the fundamental architecture.

## Parameter adaptation across timescales

| Parameter | Fast (STDP) | Medium (homeostatic) | Slow (epigenetic) | Evolution |
|-----------|:-----------:|:--------------------:|:-----------------:|:---------:|
| **w_ij magnitude** | ✓ (primary) | — | — | initial scale |
| **w_ij sign** | — | — | ✓ (receptor switching) | initial assignment |
| **V_th** | — | ✓ (primary) | ✓ (baseline shift) | initial value |
| **tau_m** | — | — | ✓ (channel density) | base per type |
| **V_rest** | — | — | ✓ (channel balance) | base value |
| **k coupling** | — | — | ✓ (receptor density) | initial values |
| **STDP params** | — | — | ✓ (plasticity proteins) | learning rate, window |
| **Topology** | — | — | — (mostly) | wiring rules |
| **Cell types** | — | — | — | type specifications |

## Cross-species universality

Every learning mechanism in this series reduces to a small set of
mathematical primitives — scalar gain modulation, threshold shifts,
exponential decay with activity-dependent renewal, sliding learning
rates. The specific molecules differ between species (octopamine in
flies vs norepinephrine in mammals, TRPA1 vs TRPV1, ecdysone vs
cortisol), but the equations are the same.

| Mathematical operation | Examples across species |
|---|---|
| Scalar multiplier on circuit gain | Octopamine (fly), norepinephrine (mammal), insulin, AKH |
| Slow multiplier on learning rate | Ecdysone (fly), cortisol/estrogen (mammal) |
| Threshold shift on sensory input | TRPA1 (fly), TRPV1 (mammal) |
| Q10 scaling on time constants | Temperature compensation — all poikilotherms |
| Exponential decay with activity-dependent renewal | Sensitization, habituation — conserved from *Aplysia* to humans |

What actually differs between species is not the math but the
**configuration**: the connectome (topology, cell types), the parameter
values (time constants, coupling strengths), and which modulatory
pathways exist and what they target.

**Design implication:** The simulation code should be species-agnostic.
All *Drosophila*-specific knowledge belongs in the connectome data and
parameter initialization, not in the equations. The same Brian2 model
equations should work for a fly VNC, a bee brain, or a mammalian
cortical column — swapping the connectome and parameter file, not the
code.

## Practical implementation roadmap

For the full phase breakdown with source doc references and a
fixed-vs-learned parameter matrix, see
[implementation phases](08-implementation-phases.md).

**Phase 1 — Functional learning in stable environment**
(see [normal learning](04-learning-normal.md)):
- Burn-in period (spontaneous activity to bootstrap the imported
  connectome into a functional state)
- Reward-modulated STDP (weight learning)
- Homeostatic threshold plasticity
- Synaptic decay (use-it-or-lose-it weight fade)
- Short-term synaptic dynamics (STF/STD — required for CPG rhythms)
- Neuromodulatory state switching (arousal)
- Hard sign constraint (w_ij cannot cross zero — initialized with
  confidence weighting, high-confidence signs start far from zero,
  "unclear" neurons start near zero and settle during burn-in)

**Phase 2 — Retrieval dynamics and memory consolidation**
(see [memory consolidation](05-learning-memory-consolidation.md)):
- Synaptic scaling (homeostatic scaling of all incoming weights,
  preserves learned weight ratios — complements Phase 1 threshold
  adjustment)
- Metaplasticity (per-synapse STDP rate modulation — prevents weight
  saturation over extended operation)
- Synaptic tagging and capture (memory consolidation)
- Sleep/wake cycling (global synaptic downscaling, replay)

**Phase 3 — Slow adaptation to changing environments**
(see [under-pressure learning](06-learning-under-pressure.md)):
- Soft sign constraint (w_ij can cross zero via slow epigenetic drift
  — receptor switching allows effective sign changes, section 2b)
- Epigenetic parameter drift (slow sign changes, baseline shifts)
- Structural plasticity (topology updates)

**Phase 4 — Cross-generational evolution**
(see [cross-generational learning](07-learning-cross-generational.md)):
- Developmental simulation (spontaneous activity-driven network growth
  — replacing the Phase 1 burn-in with a staged growth process where
  the genome encodes developmental rules, not a fixed connectome)
- Outer loop evolving genomes (developmental programs, not networks)
- Inner loop running lifetime learning
- Selection on behavioral fitness
- Transgenerational epigenetic inheritance
- Epigenetic switching rules as evolved conditional strategies
