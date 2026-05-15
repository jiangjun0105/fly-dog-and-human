# Implementation Phases

How the learning mechanisms are divided into implementation phases.
Organized by what each phase unlocks, not by which document describes
the mechanism. Each phase builds on the previous one — later phases
unlock parameters that earlier phases held fixed.

## Phase 1 — Functional learning in stable environment

The minimum set to go from imported connectome to a network that learns
motor tasks. All signs, baselines, and topology are fixed.

| Mechanism | Source doc | What it does |
|-----------|-----------|--------------|
| Burn-in | [normal 1](learning-normal.md) | Bootstrap imported connectome to functional state via spontaneous activity |
| STDP + reward gating | [normal 1b, 1c](learning-normal.md) | Core learning — adjust weights based on spike timing, gated by dopamine |
| Homeostatic threshold adjustment | [normal 1e](learning-normal.md) | Per-neuron V_th adjustment toward target firing rate. Prevents runaway excitation / silence |
| Metaplasticity | [normal 1f](learning-normal.md) | Per-synapse STDP learning rate modulation. Prevents weight saturation |
| Synaptic decay | [normal 1d](learning-normal.md) | Use-it-or-lose-it weight fade. Forgetting, capacity management, noise cleanup |
| Arousal / state switching | [under-pressure 2a](learning-under-pressure.md) | Neuromodulatory gain control (octopamine, serotonin). Needed for basic locomotion |
| Hard sign constraint | [LIF model](lif-model-design.md) | Weights cannot cross zero. Signs fixed from NT identity |

**Result:** The network can learn motor tasks through reward-modulated
STDP within a fixed scaffold. Arousal switches between resting and
active operating states.

## Phase 2 — Richer dynamics and memory consolidation

Make existing learning more realistic without changing what parameters
can adapt. Phase 1 mechanisms continue to operate.

| Mechanism | Source doc | What it does |
|-----------|-----------|--------------|
| Short-term facilitation/depression | [normal 1a](learning-normal.md) | Temporal filtering — burst sensitivity, spike-rate adaptation. Critical for CPG rhythms |
| Synaptic scaling | [normal 1e](learning-normal.md) | Homeostatic scaling of all incoming weights uniformly. Preserves learned weight ratios |
| Synaptic tagging and capture | [normal (acknowledged)](learning-normal.md) | Distinguishes fragile recent memories from consolidated long-term memories |
| Sleep/wake cycling | [normal (acknowledged)](learning-normal.md) | Replay-driven consolidation during sleep, global synaptic downscaling |

**Result:** The network has realistic temporal dynamics, distinguishes
between recent and consolidated memories, and benefits from sleep. All
the same parameters are learnable as Phase 1 — just better dynamics.

## Phase 3 — Slow adaptation to changing environments

Unlock parameters that Phase 1–2 held fixed. The network can now adapt
its fundamental operating characteristics in response to sustained
environmental change.

| Mechanism | Source doc | What it does |
|-----------|-----------|--------------|
| Epigenetic drift | [under-pressure 2b](learning-under-pressure.md) | Slow receptor profile changes, baseline shifts, channel density adjustments |
| Soft sign constraint | [LIF model](lif-model-design.md) | Weights can cross zero via receptor switching — effective sign changes |
| Structural plasticity | [under-pressure 2c](learning-under-pressure.md) | Topology changes — new connections form, dead connections are pruned |

**Result:** The network can rewire and change its operating point in
response to sustained environmental pressure (injury, temperature
shift, new predators). Parameters that were fixed scaffolding in
Phase 1–2 become adaptive.

## Phase 4 — Cross-generational evolution

The outer optimization loop. Not within a single lifetime but across
many generations.

| Mechanism | Source doc | What it does |
|-----------|-----------|--------------|
| Developmental simulation | [cross-generational 3d](learning-cross-generational.md) | Staged network growth with spontaneous activity, replacing Phase 1 burn-in |
| Evolutionary outer loop | [cross-generational 3a](learning-cross-generational.md) | Evolve genomes (developmental programs), not networks. Select on behavioral fitness |
| Transgenerational epigenetic inheritance | [cross-generational 3b](learning-cross-generational.md) | Parent's epigenetic state transfers to offspring (2–3 generations of persistence) |

**Result:** Populations of networks that evolve developmental programs.
The genome encodes brain-building rules; the inner loop runs lifetime
learning; selection acts on behavioral fitness.

## What each phase holds fixed vs learns

| Parameter | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|-----------|:-------:|:-------:|:-------:|:-------:|
| **w_ij magnitude** | Learned (STDP) | Learned (STDP) | Learned (STDP) | Learned (STDP) |
| **w_ij sign** | Fixed | Fixed | Driftable (epigenetic) | Evolved initial + driftable |
| **V_th** | Learned (homeostatic) | Learned (homeostatic) | Learned + baseline drift | Evolved initial + learned |
| **tau_m effective** | Modulated (arousal) | Modulated (arousal) | Modulated + base drift | Evolved base + modulated |
| **Topology** | Fixed | Fixed | Plastic (structural) | Evolved (developmental) |
| **STF/STD dynamics** | — | Active | Active | Active |
| **Memory consolidation** | — | Tagging + sleep | Tagging + sleep | Tagging + sleep |
| **Genome** | — | — | — | Evolved |
