# VNC Network Structure: What We Know

A reference document capturing the structural properties of the Drosophila
VNC (Ventral Nerve Cord) connectome and how it compares to machine learning
architectures. Based on analysis of the MANC/male-CNS connectome dataset
(25,635 neurons, 4,114,854 synapses).

## 1. Overall Architecture

The VNC is the fly's equivalent of the vertebrate spinal cord. It receives
high-level commands from the brain and generates the detailed motor patterns
that move the legs. It is NOT a passive relay — it autonomously generates
locomotion.

```
         BRAIN (central complex, premotor slopes)
              │
    1,305 descending neurons (8.7% of motor input)
              │         ↑
              ▼         │ 1,843 ascending neurons (feedback)
┌─────────────────────────────────────────────────────┐
│                        VNC                           │
│                                                     │
│  6,326 sensory ──→ 13,149 intrinsic ──→ 702 motor  │
│    (24.7%)          interneurons         (2.7%)     │
│                      (51.3%)                        │
│                    ↕↕↕↕ (recurrent)                 │
└─────────────────────────────────────────────────────┘
                                               │
                                          Leg muscles
```

### Key statistics

| Property | Value |
|----------|-------|
| Total neurons | 25,635 |
| Total synapses | 4,114,854 |
| Connection density | 0.63% (of n² possible) |
| Avg connections per neuron | 160 in + 160 out |
| Graph diameter | 5 hops (to reach any neuron from motor) |
| Reciprocal connections (A→B and B→A) | 24.8% of all synapses |

### Neuron type breakdown

| Type | Count | % | Role |
|------|-------|---|------|
| Intrinsic interneurons | 13,149 | 51.3% | Local computation, CPG, pattern generation |
| Sensory neurons | 6,326 | 24.7% | Body state → neural signals |
| Ascending neurons | 1,843 | 7.2% | VNC → brain feedback |
| Descending neurons | 1,305 | 5.1% | Brain → VNC commands |
| Motor neurons | 702 | 2.7% | Neural signals → muscle activation |
| Other | ~2,310 | 9.0% | Efferents, unclassified |

### Connection flow between types

The dominant connection pattern (% of all 4.1M synapses):

| Source → Target | % | Interpretation |
|----------------|---|----------------|
| Intrinsic → Intrinsic | **44.5%** | Recurrent computation (the CPG lives here) |
| Sensory → Intrinsic | 8.7% | Sensory input to processing |
| Ascending → Intrinsic | 7.1% | Feedback re-entering local circuits |
| Intrinsic → Ascending | 6.7% | Results sent back to brain |
| Descending → Intrinsic | 6.0% | Brain commands to local circuits |
| Intrinsic → Motor | 3.7% | Processed commands to muscles |

**Key insight:** 44.5% of ALL wiring is interneurons talking to each
other. The VNC is dominated by internal recurrent computation, not
input→output feedforward flow. Only 19% of connections are feedforward-like.

## 2. Segmental Organization (T1, T2, T3)

The VNC is physically divided into neuromeres (segments), each corresponding
to a pair of legs. The `somaNeuromere` annotation records which physical
segment each neuron's cell body resides in.

### Segment sizes

| Segment | Neurons | Role |
|---------|---------|------|
| T1 (prothoracic) | 4,270 | Front legs (also grooming, landing) |
| T2 (mesothoracic) | 5,073 | Mid legs (primary walking support) |
| T3 (metathoracic) | 3,966 | Hind legs (jumping, walking) |
| Abdominal (A1-A10) | ~2,300 | Non-leg functions |
| Unknown | ~9,000 | Not annotated (35%) |

### Cross-segment connectivity

Each segment keeps ~70% of its output local but communicates with neighbors:

```
        → T1       → T2       → T3
T1 →    68%        24%         8%
T2 →    16%        71%        13%
T3 →     8%        21%        70%
```

- **Adjacent segments communicate more** (T1↔T2: 16-24%, T2↔T3: 13-21%)
- **Distant segments communicate less** (T1↔T3: 8%)
- **T2 is the hub** — largest segment, highest connectivity, bridges T1 and T3

This creates a chain-like coordination structure needed for gait:
```
T1 ←→ T2 ←→ T3
(strong)  (strong)
T1 ←————————→ T3
     (weak)
```

### Comparing T1 and T2

| Property | T1 | T2 |
|----------|----|----|
| Total neurons | 4,270 | 5,073 |
| Intrinsic % | 79% | 89% |
| Motor neurons | 162 (3.8%) | 173 (3.4%) |
| Ascending neurons | 719 (16.8%) | 390 (7.7%) |
| Internal synapses per neuron | 197 | 237 |
| Shared cell types with the other | 568 (24.7% of combined set) |

**T1 and T2 are similar but not identical.** They share the same basic
architecture (mostly intrinsic interneurons + small motor pool) but only
25% of cell types appear in both. T1 has more ascending neurons (sends
more feedback to brain — makes sense for front legs that explore/sense
the environment). T2 is larger and more internally connected (the primary
weight-bearing segment during walking).

## 3. Bilateral Symmetry (Left vs Right)

### Within T1: Left and Right are near-perfect mirrors

| Property | T1-Left | T1-Right |
|----------|---------|----------|
| Neurons | 2,104 | 2,074 |
| Cell types | 1,261 | 1,236 |
| Shared cell types | **94.2%** |
| Types with identical L/R count | **85%** |
| Mean count difference | 0.17 neurons |

The left and right halves are genetically specified mirror copies — 94%
of cell types appear on both sides, and 85% of those have the exact same
number of neurons on each side.

### Left-right connectivity within T1

```
            T1-Left        T1-Right
           ┌────────┐    ┌────────┐
           │  63%   │    │  57%   │  (same-side recurrence)
           │  local │←──→│  local │
           └────────┘    └────────┘
                    35-41%
              (cross-midline connections)
```

| Flow | % |
|------|---|
| Same-side (L→L + R→R) | 58.4% |
| Cross-midline (L→R + R→L) | 36.6% |
| Ratio | 1.6:1 |

- **Cross connections are symmetric:** L→R / R→L = 0.95 (nearly equal)
- **The 37% cross-midline wiring** enables left-right alternation during
  walking (one side active → inhibits other side)
- **92 midline neurons** (neither L nor R) may serve as coordination hubs

### Implications for learning

Since L and R are 94% mirror copies, in principle:
- The parameter space could be halved (learn one side, mirror to other)
- But cross-connections (37%) must be learned WITH both sides active,
  since they create the alternating pattern
- A symmetry constraint during training (mirror L updates to R) would
  reduce noise without losing coordination learning

## 4. The Control Hierarchy

### Who sends commands to the legs?

Motor neurons receive input from:
| Source | % of motor input | Role |
|--------|-----------------|------|
| Intrinsic interneurons | **76.1%** | Local CPG pattern generation |
| Descending (brain) | 8.7% | High-level commands (walk/stop/turn) |
| Ascending | 6.3% | Inter-segment coordination |
| Sensory | 4.6% | Direct reflexes |
| Other motor | 1.2% | Motor-motor coupling |

**The brain does NOT directly control the legs.** It provides ~9% of
motor input as high-level commands. The intrinsic interneurons (76%)
generate the actual movement patterns.

### Descending neuron organization

- 1,305 descending neurons total
- 89% excitatory (acetylcholine), 11% inhibitory (GABA)
- They project broadly: 27% → T1, 26% → T2, 16% → T3
- Mostly target intrinsic interneurons (60%), not motor neurons directly
- Functionally: encode speed, direction, gait type, start/stop

### Example: DNa02 (a known walking command neuron)

- 2 neurons (one Left, one Right)
- Each has ~3,000 presynaptic sites → 943 distinct target neurons
- Projects to ALL leg segments (T1: 33%, T2: 25%, T3: 23%)
- Directly contacts motor neurons (10.3% of its output — unusually high)
- Also contacts 68% intrinsic interneurons (the CPG)
- Neurotransmitter: acetylcholine (excitatory)

When DNa02 fires, it provides a tonic "walk" excitation to the locomotor
CPG. But it's not sufficient alone — the full ensemble of ~1,305
descending neurons provides the nuanced patterning needed for coordinated
gait.

### Analogy: human vs fly motor control

| Level | Human | Fly |
|-------|-------|-----|
| Goal selection | Prefrontal cortex | Mushroom body |
| Motor planning | Motor cortex (body map) | Central complex + premotor slopes (no body map) |
| Command transmission | ~1M corticospinal axons | ~1,305 descending neurons |
| Pattern generation | Spinal CPG | VNC intrinsic interneurons |
| Execution | Motor neurons | Motor neurons |
| Bandwidth | High (fine finger control) | Low (stereotyped gaits) |
| Direct cortex→motor | Yes (for hands) | Rare (8.7%) |

## 5. Comparison with ML Architectures

### Structural comparison

| Property | CNN | Transformer | RNN | **Fly VNC** |
|----------|-----|-------------|-----|-------------|
| Connection density | Very sparse (3×3 kernel) | 100% (all-to-all per layer) | 100% (all-to-all) | **0.63% (sparse)** |
| Graph diameter | Deep (10-100 layers) | Shallow per layer, deep overall | 1 hop spatial, deep in time | **5 hops (shallow)** |
| Recurrence | 0% | 0% | 100% within hidden | **44.5%** (intrinsic↔intrinsic) |
| Layer structure | Strict layers | Strict layers | One hidden pool | **No layers — dense soup** |
| Neuron identity | Position in grid | Position in sequence | All equivalent | **Each unique** (morphology, connections, NT) |
| Excitation/Inhibition | No constraint | No constraint | No constraint | **Dale's law** (each neuron fixed E or I) |
| Spatial structure | Grid (image topology) | None (position encoding) | None | **Segments + bilateral symmetry** |
| Learning | Backpropagation | Backpropagation | BPTT | **Local (STDP, reward modulation)** |

### How information propagates

| Architecture | Mechanism |
|-------------|-----------|
| CNN | Slowly, via expanding receptive field (10+ layers to cross an image) |
| Transformer | Instantly within layer (attention), sequentially across layers |
| RNN | Instantly among neurons, information accumulates over timesteps |
| **VNC** | Fast (2 hops to reach any neuron), computation happens in temporal dynamics |

### Closest ML analogue: Echo State Network / Reservoir Computing

The VNC most closely resembles a **reservoir computer**:
- Large recurrent pool with **fixed** internal connections (the 13K intrinsic neurons)
- Input injected into the reservoir (sensory + descending)
- Output read from a small subset (motor neurons, 2.7%)
- In reservoir computing, only the output readout is trained

Key difference: in the VNC, the "reservoir" is not random — it's a highly
structured, evolved network with specific circuit motifs (CPGs, left-right
inhibition, segment coordination). And it can be modulated (neuromodulators
change its dynamics globally).

### Why standard ML training doesn't apply

1. **No layers to backpropagate through** — the network is a recurrent
   soup, not a DAG (directed acyclic graph)
2. **Non-differentiable spikes** — LIF neurons fire discrete all-or-nothing
   events, unlike smooth activations
3. **Physics in the loop** — MuJoCo body simulation breaks the computational
   graph (can't differentiate through physics)
4. **Dale's law** — neurons can't switch between E and I, constraining
   the solution space
5. **Temporal coding** — information is in spike timing, not rate alone;
   requires recurrent dynamics to process

### What the VNC tells us about the "right" learning approach

Given that the VNC is:
- A pre-wired, structured reservoir (not random)
- With autonomous pattern generation (CPGs already built-in)
- Controlled by a low-bandwidth command interface (1,305 descending neurons)
- Where 76% of motor drive comes from local interneurons, not learned pathways

The biological learning strategy is likely:
1. **Development (genetics):** wire the CPG structure, set up bilateral
   symmetry, establish segment connectivity → this is our connectome data
2. **Early life (activity-dependent refinement):** fine-tune connection
   strengths based on sensory feedback → possibly what STDP should be doing
3. **Ongoing (neuromodulation):** shift the operating point (faster/slower,
   more/less responsive) without changing wiring → arousal, dopamine

We may be asking STDP to do step (1) when it's only designed for step (2).
The CPG pattern should already be "in the weights" from the connectome —
STDP should be fine-tuning, not discovering locomotion from scratch.
