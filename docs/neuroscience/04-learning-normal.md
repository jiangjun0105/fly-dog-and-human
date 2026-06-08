# Normal Environment Learning

Mechanisms that operate during stable conditions — the fly is exploring,
foraging, navigating, acquiring skills. The neural scaffold (topology,
cell types, receptor profiles) is stable; only weights and thresholds
adapt.

Part of the [Learning Strategies](03-learning-strategies.md) series.

## Burn-in: bootstrapping a connectome that never developed

Our model faces a unique initialization problem. In biology, the adult
connectome is the product of a **developmental process** — neurons are
born gradually, generate spontaneous activity, and that activity shapes
the wiring as it forms. The network was never "broken" because it was
functional at every stage of growth.

We skip all of that. We start with the *output* of development (the
adult connectome from EM reconstruction) but not the *process* that
produced it. The topology is already refined, but the weights are just
scaled synapse counts — they've never been shaped by activity.

This creates three situations that are fundamentally different:

```
Biological development (what nature does):
  Neurons born gradually → fire spontaneously →
  activity shapes wiring AS IT FORMS → topology and
  weights co-develop → always functional at each stage

Our Phase 1 (connectome import):
  Full adult topology arrives pre-built → weights initialized
  from synapse counts but never activity-shaped → need to
  bring this to a functional state
```

Before any task-driven learning, the model needs a **burn-in period** —
a phase of spontaneous or random activity where STDP, homeostasis, and
decay operate freely to bring the network to a self-consistent baseline.
This serves the same function as developmental spontaneous activity but
can only adjust weights and thresholds (topology is fixed).

The burn-in should:
- Start with low-rate spontaneous activity (Poisson input to sensory
  neurons)
- Let STDP establish initial correlational structure
- Let homeostasis find each neuron's operating range
- Let decay prune spurious weight initializations
- Run until firing rates stabilize near target rates

Only after burn-in is the network ready for task-driven learning
(reward-modulated STDP with environmental interaction).

For Phase 4 (cross-generational learning), the burn-in evolves into a
full **developmental simulation** — see
[cross-generational learning](07-learning-cross-generational.md) section
3d for why this distinction matters.

**Implementation priority:** Phase 1. Required before any meaningful
simulation — without burn-in, the network starts in an arbitrary state
that may be far from any stable operating point.

## 1a. Spike-timing-dependent plasticity — STDP (seconds–minutes)

**What changes:** Synaptic weight magnitudes (w_ij). The core learning
rule.

**Mechanism:** The relative timing of pre- and post-synaptic spikes
determines whether a connection strengthens or weakens:

```
Pre fires → Post fires shortly after (causal):     strengthen (LTP)
Post fires → Pre fires shortly after (acausal):    weaken (LTD)
```

The timing window is ~20 ms on each side. Spikes further apart than
this have diminishing effect.

**Biological function:** Encodes causal relationships. If neuron A
consistently fires just before neuron B, the A→B connection
strengthens — the circuit learns that A's activity predicts B's.
This is the neural basis of associative learning and skill acquisition.

**On its own, STDP is unsupervised** — it strengthens correlations
regardless of whether they're useful. A fly touching a hot surface and
then withdrawing its leg would strengthen the touch→withdraw pathway,
but so would any other coincidental pairing. STDP needs reward gating
(see 1b) to learn selectively.

**Model parameter:** Changes w_ij magnitude. Sign is not changed by
STDP in normal conditions (see [under-pressure learning](06-learning-under-pressure.md)
for sign changes).

## 1b. Reward-modulated learning — dopamine gating (seconds–minutes)

**What changes:** Which STDP weight changes become permanent.

**Mechanism:** STDP doesn't directly change weights — it creates an
**eligibility trace** (a pending weight change that decays over
~seconds). The weight change only becomes permanent when a dopamine
signal arrives within that window:

```
1. Pre-post spike timing → eligibility trace e_ij (candidate change)
2. e_ij decays with time constant tau_eligibility (~1–5 seconds)
3. Dopamine signal d(t) arrives (or not)
4. Actual weight update: Δw_ij = d(t) * e_ij(t)
```

- d(t) > 0 (reward): recent causal pairings are strengthened —
  "that worked, do it again"
- d(t) < 0 (punishment): recent causal pairings are weakened —
  "that was bad, don't do it again"
- d(t) = 0 (neutral): eligibility trace decays, no lasting change

**Biological function:** This is how the fly learns which behaviors
lead to good outcomes. The mushroom body circuit (DAN → KC → MBON)
implements exactly this: Kenyon cells (KC) form STDP-eligible
connections to mushroom body output neurons (MBON), and dopaminergic
neurons (DAN) deliver the reward/punishment signal that consolidates
the useful changes.

**Relationship to neuroplasticity:** STDP and reward-modulated STDP are
both forms of **synaptic plasticity**, which is one category of
neuroplasticity. Neuroplasticity is the broader umbrella term covering
all forms of neural adaptation — synaptic, structural, homeostatic, and
modulatory. Everything in the learning strategies series falls under
neuroplasticity.

**Skill learning:** This mechanism is what underlies skill acquisition.
A fly learning to navigate a maze or optimize its gait is repeatedly:
(1) attempting a motor pattern (generating spikes), (2) experiencing
the outcome (reward/punishment via dopamine), and (3) consolidating the
weight changes that led to good outcomes. Over many trials, the circuit
converges on an efficient motor program — a learned skill.

**Implementation priority:** Phase 1. This is the primary learning
mechanism and should be in the first simulation.

## 1c. Synaptic decay — "use it or lose it" (hours–days)

**What changes:** All synaptic weights, continuously and uniformly.
Weights that aren't actively reinforced decay toward zero.

**Mechanism:** Synaptic strength depends on physical structures —
receptor proteins in the postsynaptic membrane, scaffolding proteins
that hold them in place, vesicle pools in the presynaptic terminal.
These proteins have finite lifetimes (hours to days) and are constantly
being degraded and recycled:

```
Active synapse:
  spikes → calcium → protein synthesis → receptors replenished
  Weight maintained or strengthened

Inactive synapse:
  no spikes → no calcium signal → no protein synthesis
  Existing proteins degrade naturally → weight decays toward zero
```

The synapse isn't being actively destroyed — it's just not being
maintained, so it fades. This is "use it or lose it" at the molecular
level.

The implementation is a constant multiplicative decay on all weights:

```
At each timestep:
    w_ij *= (1 - lambda_decay * dt)

    where lambda_decay is small (time constant of hours–days)
```

Every weight is constantly shrinking toward zero. The only thing that
counteracts it is active STDP reinforcement. A connection that is
regularly used (pre and post fire in causal patterns, reinforced by
dopamine) gets strengthened by STDP faster than decay weakens it — so
it persists. A connection that is never used quietly fades away.

**Biological function — three roles:**

**1. Forgetting:** Clears stale associations. If the fly learned "this
place has food" but the food is gone, the relevant weight changes
gradually fade unless reinforced by new experiences. Without decay, the
fly would forever approach a location that no longer has food.

**2. Capacity management:** Without decay, every experience would leave
permanent weight changes. Over a lifetime, the network would saturate —
all weights would drift to their maximum or minimum, and the network
would lose the ability to learn new things. Decay frees up capacity by
clearing what isn't being used.

**3. Noise cleanup:** STDP inevitably creates spurious weight changes
from coincidental spike pairings. These are not consistently reinforced
(they were coincidence, not real causal structure), so decay removes
them while genuine learned associations — which are regularly
reinforced — persist.

**Lifecycle of an unused connection:**

```
STDP stops reinforcing it
  → weight decay gradually weakens it (hours–days)
  → weight approaches zero
  → if near zero long enough → structural plasticity physically
    removes it (days–weeks, see under-pressure learning doc)
```

**Interaction with other mechanisms:**

| Mechanism | Direction | Timescale |
|-----------|-----------|-----------|
| STDP | Strengthens or weakens specific connections | seconds |
| Weight decay | Weakens ALL connections uniformly | hours–days |
| Homeostatic scaling | Scales all inputs to a neuron up or down | hours |
| Structural plasticity | Physically removes silent synapses | days–weeks |

Weight decay and STDP are in constant tension — decay pulls everything
toward zero while STDP selectively reinforces useful connections. The
balance between them determines how quickly the network forgets:
stronger decay = faster forgetting, more capacity for new learning, but
less retention of old skills. This balance (lambda_decay) is a tunable
hyperparameter — and in the evolutionary outer loop (Phase 3), it would
be evolved.

**Implementation priority:** Phase 1. Simple to implement (one line per
timestep), critical for preventing weight saturation during long
learning runs.

## 1d. Homeostatic plasticity (minutes–hours)

**What changes:** Firing thresholds (V_th) and synaptic scaling of
incoming weights.

### The problem homeostatic plasticity solves

STDP alone is a **positive feedback loop**. When STDP strengthens a
connection, the postsynaptic neuron fires more, which creates more
causal pairings, which strengthens connections further, which makes it
fire even more. Without a counteracting force, the network has two
failure modes:

- **Runaway excitation** — a few neurons fire constantly, dominate the
  network, all weights to them grow, everything else goes silent
- **Complete silence** — if early STDP weakens a few key connections,
  less firing means fewer pairings, fewer pairings means less
  strengthening, activity dies out

Real brains have the same problem but never explode or go silent.
Homeostatic plasticity is the negative feedback loop that keeps every
neuron in a useful operating range.

### The biological mechanism

Each neuron has an internal sensor that tracks its own average firing
rate over hours. The molecular machinery behind this is
calcium-dependent gene expression:

```
Neuron fires a lot (over hours)
  → intracellular calcium stays elevated
  → calcium activates transcription factors (CaMKIV, CREB)
  → these turn on genes that REDUCE excitability:
      - insert more potassium leak channels (raises threshold)
      - reduce AMPA receptor density at synapses (weaken all inputs)
      - reduce sodium channel density (harder to spike)

Neuron fires too little (over hours)
  → calcium drops below baseline
  → different transcription factors activate
  → genes that INCREASE excitability:
      - remove potassium channels (lower threshold)
      - insert more AMPA receptors (strengthen all inputs)
      - increase sodium channel availability
```

This is a **gene expression** process, which is why it takes hours, not
seconds. The neuron is literally manufacturing new ion channel proteins
and inserting or removing them from its membrane.

### The thermostat analogy

Each neuron has a "set point" — a target firing rate that represents its
healthy operating regime:

- A sensory neuron's set point might be ~50 Hz — needs to be active
  and responsive
- An interneuron's set point might be ~20 Hz — moderate background
  processing
- A motor neuron's set point might be ~10 Hz — should only fire for
  specific commands

The homeostatic mechanism works like a thermostat:

```
Measure: current average firing rate (over hours)
Compare: to target rate (the set point)
Adjust:  if too high → become less excitable
         if too low  → become more excitable
```

Just like a thermostat doesn't care *why* the room is too hot (heater
too high? sunny day? oven open?), homeostatic plasticity doesn't care
*why* the neuron is firing too much (strong STDP? excessive input?
neuromodulation?). It adjusts excitability to bring the rate back toward
the set point.

### Threshold adjustment (intrinsic plasticity)

The neuron adjusts its own firing threshold:

```
dV_th/dt = eta_homeo * (firing_rate - target_rate)

Firing too much → raise V_th → need more input to fire
Firing too little → lower V_th → need less input to fire
```

This changes the neuron's overall excitability uniformly — all inputs
are affected equally.

### Why the timescale matters

Homeostasis MUST be slower than STDP. If STDP strengthens a connection
(because the fly learned something useful) and homeostasis immediately
compensated by raising the threshold, the learning would be erased. The
neuron would fire at the same rate as before, as if nothing was learned.

The slow timescale (hours) means homeostasis allows short-term learning
to happen freely. It only corrects for sustained, large deviations.
STDP can make a neuron fire 30% more for the next few minutes — that's
fine, the homeostatic mechanism barely notices. But if STDP drives a
neuron to fire 300% more for hours, homeostasis gradually pulls it back
to a sustainable level.

The result: the network can learn and change moment-to-moment, while
remaining globally stable over longer periods.

**Implementation priority:** Phase 1. One variable per neuron (V_th).

## 1e. Short-term synaptic dynamics (ms–seconds)

**What changes:** The effective strength of a synapse on a per-spike
basis, without any lasting structural change.

**Mechanisms:**

- **Short-term facilitation (STF)** — repeated presynaptic spikes
  cause progressively more neurotransmitter release. The second spike
  in a burst is stronger than the first. This happens because residual
  calcium accumulates in the presynaptic terminal.
- **Short-term depression (STD)** — the opposite: repeated spikes
  deplete available vesicles, making each successive spike weaker until
  the pool recovers.

**Biological function:** These are automatic, biophysical processes —
not "learning" in the cognitive sense. They act as temporal filters:
facilitating synapses are sensitive to bursts, depressing synapses are
sensitive to isolated spikes. Together they shape how information flows
through a circuit moment-to-moment.

**Why Phase 1 needs this:** Central pattern generators (CPGs) that
produce rhythmic leg movement depend on STD to alternate between leg
phases. Without temporal filtering, the network cannot generate the
rhythmic output needed for basic locomotion — the primary Phase 1 goal.

**Model parameter:** Not a weight change — implemented as a dynamic
scaling factor on w_ij that decays back to 1.0 between spikes.

**Implementation priority:** Phase 1. Required for CPG-driven motor
control.

## Acknowledged simplifications

The following mechanisms are established in the neuroscience literature
but are not included in our current model. They are documented here so
that if we need to add them in the future, we have a reference for what
they do and why they matter.

### Gap junctions (electrical synapses)

Not all neural communication is chemical. Some neurons are directly
connected by **gap junctions** — protein channels (connexins in
vertebrates, innexins in *Drosophila*) that span the membranes of
both cells, allowing ions to flow directly between them.

Properties:
- **Fast** — no synaptic delay (ions flow directly, no
  neurotransmitter release/binding cycle)
- **Bidirectional** — current flows in whichever direction the voltage
  gradient dictates, unlike chemical synapses which are unidirectional
- **No neurotransmitter involved** — sign is determined by the voltage
  difference, not by a chemical
- **Often between same-type neurons** — gap junctions tend to connect
  neurons of the same type, synchronizing their activity

In *Drosophila*, gap junctions are well-documented in:
- The **giant fiber escape circuit** (DNp01/GF in our dataset) — gap
  junctions between the giant fiber and its target motor neurons enable
  the extremely fast escape response (~1 ms latency)
- **Motor neuron synchronization** — gap junctions between motor neurons
  innervating the same muscle ensure coordinated contraction
- **Clock neurons** — gap junctions synchronize circadian oscillators

**Impact on our model:** Our model only has chemical synapses (w_ij
with delays). Gap junctions would be modeled as instantaneous,
bidirectional, unsigned connections — a different connection type
entirely. Missing them means our giant fiber escape circuit will be
slower than biology, and motor neuron synchronization within a muscle
group won't emerge naturally.

**Implementation difficulty:** Moderate. Brian2 supports gap junctions
natively. The main challenge is identifying which connections in the
connectome are gap junctions vs chemical synapses — the EM data doesn't
always distinguish them clearly.

**Priority:** Phase 2 for specific circuits (giant fiber, motor neuron
pools).

### Retrograde signaling

In our model, information flows one way: pre → post. In real synapses,
the postsynaptic neuron can send signals **back** to the presynaptic
terminal — nitric oxide (NO), endocannabinoids, and other retrograde
messengers.

What they do:
- **Modify presynaptic release probability** — the postsynaptic neuron
  can tell the presynaptic neuron "send more" or "send less"
- **Depolarization-induced suppression of inhibition (DSI)** — when a
  postsynaptic neuron is very active, it releases endocannabinoids that
  temporarily suppress inhibitory input to itself (a form of local
  disinhibition)
- **Nitric oxide (NO) signaling** — NO diffuses from the postsynaptic
  site and affects nearby synapses (not just the one that triggered it),
  creating a local volume signal

**Impact on our model:** Without retrograde signaling, the postsynaptic
neuron has no direct control over its inputs (other than homeostatic
scaling, which is slow and global). Retrograde signals allow fast, local
feedback that can fine-tune individual connections. Missing them means
our model may need longer to converge on stable activity patterns.

**Implementation difficulty:** Moderate. Requires per-synapse
presynaptic state variables that are modulated by postsynaptic activity.

**Priority:** Phase 2–3.

### Dendritic computation

Our LIF model treats each neuron as a **single point** — all synaptic
inputs are summed into one I(t) value regardless of where on the neuron
they arrive. Real neurons have elaborate dendritic trees, and the
physical location of a synapse matters enormously:

- **Proximal synapses** (near the cell body) have much more influence
  on firing than **distal synapses** (far away on thin dendrites),
  because voltage attenuates along the dendrite
- **Dendritic spikes** — dendrites have their own voltage-gated
  channels and can generate local, all-or-nothing spikes that amplify
  inputs in a specific branch. This means two inputs landing on the
  same branch can interact **multiplicatively** rather than additively
- **Branch-specific computation** — different dendritic branches can
  function as semi-independent computational units. A single neuron
  with 10 dendritic branches can effectively implement 10 separate
  AND gates
- **Direction selectivity** — in visual neurons (T4/T5 in the optic
  lobe), the spatial arrangement of synapses along a dendrite is what
  computes motion direction

**Impact on our model:** This is the most fundamental simplification in
any point-neuron model. We lose the ability to model spatially-specific
computation within a single neuron. For the VNC motor circuits this is
probably acceptable — most of the relevant computation happens between
neurons, not within dendrites. For the brain (Phase 2+), especially
visual processing circuits, this limitation becomes more significant.

The alternative — **multi-compartment models** — divides each neuron
into segments with separate voltage equations. This is much more
biologically faithful but vastly more computationally expensive.
Simulating 25,000 multi-compartment neurons with detailed dendritic
trees is currently impractical for real-time or near-real-time
simulation.

**Implementation difficulty:** High. Requires moving from point neurons
to multi-compartment models, which is a fundamental model change, not
just an added feature. Brian2 supports multi-compartment models via its
`SpatialNeuron` class, but the computational cost scales roughly with
the number of compartments per neuron (typically 10–100x more expensive).

**Priority:** Phase 3 or beyond, and likely only for specific neurons
where dendritic computation is functionally critical.

### Glial cell modulation

Neurons are not the only cells in the nervous system. **Glial cells**
(astrocytes in vertebrates; their functional equivalents in *Drosophila*
include cortex glia, ensheathing glia, and astrocyte-like glia) actively
modulate synaptic transmission:

- **Neurotransmitter clearance** — glia take up neurotransmitter from
  the synaptic cleft via transporters, controlling how long the signal
  lasts. Slower clearance = longer postsynaptic response. Glial
  glutamate transporters are particularly important for preventing
  excitotoxicity
- **Gliotransmission** — glia release their own signaling molecules
  (ATP, D-serine, glutamate) that modulate synaptic transmission. The
  "tripartite synapse" concept (pre + post + glia) is increasingly
  accepted
- **Ionic homeostasis** — glia buffer extracellular potassium, which
  affects neuronal excitability. During intense activity, potassium
  accumulates outside neurons; glia absorb it and redistribute it,
  preventing spreading depolarization
- **Metabolic support** — glia provide lactate and glucose to active
  neurons, coupling energy supply to demand. Under metabolic stress,
  reduced glial support can limit sustained neural activity

In *Drosophila* specifically:
- Cortex glia wrap neuronal cell bodies and regulate the ionic
  environment
- Ensheathing glia form boundaries between brain regions (neuropil
  compartments — the ROIs in our dataset)
- Astrocyte-like glia infiltrate neuropil and modulate synaptic
  transmission

**Impact on our model:** Without glia, our model assumes instantaneous
neurotransmitter clearance, unlimited metabolic supply, and no tripartite
modulation. For short simulations of motor circuits, this is acceptable.
For longer simulations or simulations involving metabolic constraints
(fatigue, energy efficiency), the absence of glia becomes more
noticeable.

**Implementation difficulty:** High. Requires modeling a separate
population of non-spiking cells with their own dynamics, spatially
coupled to neurons. There's no standard framework for this in Brian2.

**Priority:** Phase 3 or beyond. Glial modulation in the *Drosophila*
VNC specifically is poorly characterized. Worth revisiting if the
project moves to modeling fatigue, metabolic constraints, or
neuroprotection.
