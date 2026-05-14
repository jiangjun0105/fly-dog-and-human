# Normal Environment Learning

Mechanisms that operate during stable conditions — the fly is exploring,
foraging, navigating, acquiring skills. The neural scaffold (topology,
cell types, receptor profiles) is stable; only weights and thresholds
adapt.

Part of the [Learning Strategies](learning-strategies.md) series.

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

Adding neurons to a trained network (adult neurogenesis):
  Existing network is functional → new neuron inserted →
  has no meaningful connections → must integrate into an
  already-optimized system without breaking it

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

For Phase 3 (cross-generational learning), the burn-in evolves into a
full **developmental simulation** — see
[cross-generational learning](learning-cross-generational.md) section
3d for why this distinction matters.

**Implementation priority:** Phase 1. Required before any meaningful
simulation — without burn-in, the network starts in an arbitrary state
that may be far from any stable operating point.

## 1a. Short-term synaptic dynamics (ms–seconds)

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

**Model parameter:** Not a weight change — implemented as a dynamic
scaling factor on w_ij that decays back to 1.0 between spikes.

**Implementation priority:** Phase 2. Not critical for first simulation
but important for realistic temporal dynamics (e.g., central pattern
generators that produce rhythmic leg movement need STD to alternate
between leg phases).

## 1b. Spike-timing-dependent plasticity — STDP (seconds–minutes)

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
(see 1c) to learn selectively.

**Model parameter:** Changes w_ij magnitude. Sign is not changed by
STDP in normal conditions (see [under-pressure learning](learning-under-pressure.md)
for sign changes).

## 1c. Reward-modulated learning — dopamine gating (seconds–minutes)

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

## 1d. Synaptic decay — "use it or lose it" (hours–days)

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

## 1e. Homeostatic plasticity (minutes–hours)

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

### Two forms of homeostatic plasticity

**1. Threshold adjustment (intrinsic plasticity)** — the neuron adjusts
its own firing threshold:

```
dV_th/dt = eta_homeo * (firing_rate - target_rate)

Firing too much → raise V_th → need more input to fire
Firing too little → lower V_th → need less input to fire
```

This changes the neuron's overall excitability uniformly — all inputs
are affected equally. Simpler to implement but cruder.

**2. Synaptic scaling** — the neuron scales ALL of its incoming weights
up or down by the same multiplicative factor:

```
Firing too much → scale all incoming w_ij by 0.95x
Firing too little → scale all incoming w_ij by 1.05x
```

This preserves the **relative** pattern of weights — the structure that
STDP learned. A connection that's 3x stronger than its neighbor stays
3x stronger after scaling; only the absolute magnitudes change. This is
important because it doesn't destroy what STDP learned, it just adjusts
the volume knob.

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

**Implementation priority:** Phase 1, in two steps. Threshold
adjustment first (simpler, one variable per neuron). Synaptic scaling
in Phase 2 (more biologically faithful, preserves learned weight
ratios).

## 1f. Metaplasticity — "plasticity of plasticity" (minutes–hours)

**What changes:** The learning rate of individual synapses — how
responsive each synapse is to future STDP events.

**Mechanism:** The history of a synapse's activity changes how plastic
it is going forward. This is the BCM (Bienenstock-Cooper-Munro) theory.
Each synapse tracks its recent modification history and adjusts its
STDP sensitivity accordingly:

```
Synapse recently strengthened (LTP):
  → becomes harder to strengthen further
  → becomes easier to weaken
  → the "modification threshold" slides upward

Synapse recently weakened (LTD):
  → becomes harder to weaken further
  → becomes easier to strengthen
  → the "modification threshold" slides downward
```

The molecular mechanism involves the recent history of calcium influx
and the phosphorylation state of plasticity-related proteins (CaMKII,
calcineurin). A synapse that just underwent LTP has a different
biochemical state that makes the next LTP event require a stronger
signal.

**The sliding threshold:**

In standard STDP, there's a fixed boundary: pre-before-post strengthens,
post-before-pre weakens. In BCM/metaplasticity, this boundary **slides**
based on the postsynaptic neuron's recent average activity:

```
theta_m = f(average postsynaptic firing rate)

If firing rate is high → theta_m increases:
  → a larger timing difference is needed to trigger LTP
  → LTD becomes easier
  → net effect: recent winners are harder to strengthen further

If firing rate is low → theta_m decreases:
  → even weak timing correlations can trigger LTP
  → net effect: quiet synapses get a chance to strengthen
```

**Biological function:** Metaplasticity solves a different problem than
homeostasis. Homeostasis adjusts the neuron's overall excitability (the
volume knob). Metaplasticity adjusts how changeable each individual
synapse is (the learning rate per synapse).

Without metaplasticity, STDP tends to produce a bimodal weight
distribution — all weights get pushed to maximum or minimum over time,
because strong synapses drive more postsynaptic firing, which creates
more pre-before-post coincidences, which strengthens them further. This
is the "rich get richer" problem at the single-synapse level.

Metaplasticity prevents this by making recently strengthened synapses
harder to strengthen again and recently weakened ones harder to weaken
further. The result: weights stay in a useful middle range where they
can still change in either direction, preserving the network's capacity
for future learning.

**Comparison with homeostasis:**

| Property | Homeostatic plasticity | Metaplasticity |
|----------|----------------------|----------------|
| Operates on | The whole neuron (global) | Individual synapses (local) |
| Adjusts | Excitability (V_th) or all weights uniformly | STDP learning rate per synapse |
| Prevents | Runaway network activity | Runaway individual weight growth |
| Timescale | Hours (gene expression) | Minutes–hours (protein modification) |
| Analogy | Thermostat (adjusts room temperature) | Thermostat per radiator (adjusts each heater independently) |

Both are needed: homeostasis for network-level stability, metaplasticity
for synapse-level stability.

**Implementation:** A per-synapse sliding threshold that modifies the
STDP update rule:

```
theta_m_ij = running average of recent w_ij changes

STDP update becomes:
    if pre-before-post AND delta_w > theta_m_ij:  strengthen
    if post-before-pre OR delta_w < theta_m_ij:   weaken
```

**Implementation priority:** Phase 1. Simple to implement (one extra
variable per synapse), prevents STDP weight saturation, and
complementary to homeostasis — homeostasis keeps firing rates stable,
metaplasticity keeps individual weights in a useful range.

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

### Synaptic tagging and capture (memory consolidation)

STDP creates an initial weight change (early-phase LTP/LTD), but this
change is **temporary** — it depends on short-lived biochemical
modifications (phosphorylation) that last ~1–3 hours. For a weight
change to become permanent (late-phase LTP/LTD), new protein synthesis
is required.

The mechanism has two steps:

1. **Tagging** — an active synapse gets a molecular "tag" (a
   temporary biochemical marker) when STDP modifies it. The tag itself
   doesn't stabilize the weight change — it just marks the synapse as
   "recently modified."

2. **Capture** — when a strong learning event triggers protein
   synthesis in the neuron's cell body (a costly, neuron-wide process),
   the newly synthesized plasticity-related proteins (PRPs) are shipped
   out along dendrites. Tagged synapses **capture** these proteins and
   use them to stabilize their weight changes. Untagged synapses don't
   capture PRPs, so their changes fade.

```
Weak learning event:
  → STDP changes weight (early-phase)
  → synapse gets tagged
  → if no protein synthesis within ~1–3 hours → tag expires
  → weight change fades (forgotten)

Strong learning event:
  → STDP changes weight (early-phase)
  → synapse gets tagged
  → strong signal triggers protein synthesis (neuron-wide)
  → tagged synapses capture PRPs → weight change stabilized (permanent)
  → nearby tagged synapses also capture PRPs → "synaptic clustering"
```

**Biological function:** This explains several memory phenomena:
- **Why cramming is less effective than spaced repetition** — spaced
  learning events each trigger tagging and protein synthesis; cramming
  triggers tagging but the tags expire before enough protein synthesis
  occurs
- **Why sleep matters for memory** — during sleep, replay of recent
  activity patterns retriggers protein synthesis and consolidates tagged
  synapses
- **Why emotionally significant events are remembered better** — strong
  dopamine/norepinephrine signals during emotional events trigger more
  protein synthesis, consolidating more tags

**Impact on our model:** Without tagging and capture, all STDP weight
changes are treated equally — there's no distinction between fragile
recent memories and consolidated long-term memories. In long-running
simulations, this means old memories are as vulnerable to decay as new
ones.

**Implementation difficulty:** Moderate. Requires per-synapse tag
variables, a neuron-level protein synthesis signal, and a consolidation
mechanism that converts tagged early-phase changes to permanent
late-phase changes.

**Priority:** Phase 2, when we add sleep/wake cycles and want realistic
memory consolidation dynamics.

### Oscillatory gating and sleep

Neural oscillations — rhythmic, population-level activity patterns —
gate when and how effectively plasticity occurs. The brain doesn't learn
uniformly at all times; it cycles between states that favor learning,
consolidation, and maintenance.

Key oscillatory states in *Drosophila*:

- **Circadian rhythms** — flies learn better at certain times of day.
  Clock neurons (which use gap junctions for synchronization) modulate
  global arousal and plasticity, with peak learning during subjective
  daytime
- **Sleep** — *Drosophila* has genuine sleep (consolidated rest periods
  with reduced responsiveness and homeostatic rebound). During sleep:
  - Recently active circuits are replayed (reactivation)
  - Synaptic tagging and capture consolidates the day's learning
  - Global synaptic downscaling occurs — all weights are slightly
    reduced, improving signal-to-noise ratio (the "synaptic homeostasis
    hypothesis")
- **Gamma-like oscillations** — fast oscillations (~20–50 Hz) in the
  mushroom body synchronize KC activity during odor processing, creating
  temporal windows where STDP is particularly effective

**Impact on our model:** Without oscillatory gating, our model learns
continuously at a uniform rate. It has no concept of "now is a good time
to learn" vs "now is a good time to consolidate." This means it may
learn more slowly than biology (because biology concentrates learning
into optimal windows) and consolidate less effectively (because it
doesn't have sleep-dependent cleanup).

**Implementation difficulty:** Moderate for basic sleep/wake cycling.
High for realistic oscillatory dynamics within brain regions.

**Priority:** Phase 2 for sleep/wake cycling (global synaptic
downscaling during sleep, replay-driven consolidation). Phase 3 for
oscillatory gating within circuits.

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
