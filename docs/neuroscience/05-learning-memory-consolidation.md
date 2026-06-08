# Retrieval Dynamics and Memory Consolidation

Mechanisms that enrich the temporal dynamics of learning and enable
the transition from fragile recent memories to stable long-term storage.
Phase 1 establishes the core learning loop (STDP, homeostasis, decay);
this phase makes that learning **realistic** — memories are filtered,
consolidated, and structured across time.

Part of the [Learning Strategies](03-learning-strategies.md) series.

## What Phase 2 unlocks

Phase 1 gets the network from imported connectome to functional motor
control. Once that's achieved, the network needs mechanisms to sustain
healthy learning over extended operation and to build long-term memory.
Phase 2 adds:

- **Proportional stability** — homeostatic scaling preserves learned
  weight ratios while adjusting overall drive (synaptic scaling)
- **Saturation prevention** — per-synapse learning rate modulation
  prevents weights from locking at extremes (metaplasticity)
- **Memory triage** — recent memories are fragile and must be
  consolidated to become permanent (tagging and capture)
- **Offline consolidation** — sleep replays recent activity and
  downscales noise, converting tagged memories to long-term storage

No new parameters become learnable — the same weights and thresholds
from Phase 1 are still the substrate. Phase 2 adds richer dynamics
to *how* those parameters are maintained over time.

---

## The biology of memory consolidation

Although the fruit fly (*Drosophila melanogaster*) lacks a hippocampus
and possesses a brain the size of a poppy seed, it exhibits highly
sophisticated mechanisms for memory formation and retention.

### The Central Complex (The Executive Hub)

The central complex serves as the fly's navigation system and motor
control center. It integrates the generalized "avoid" or "approach"
signals from the mushroom body with real-time sensory data (wind
direction, visual landmarks via ring attractor compass neurons, internal
state) to execute precise, 3D spatial navigation commands. Memory
consolidation ultimately serves this executive hub — learned associations
are useless unless they can be retrieved and translated into action.

### The Role of Sleep in Cognitive Consolidation

Sleep is fundamentally required to transition temporary experiences into
permanent neurological structures. This process is governed by the
**Energy Allocation Hypothesis**: building new memories is incredibly
energy-intensive, requiring the brain to close its sensory gates to
redirect cellular power toward protein synthesis.

#### Mechanisms of Sleep-Induced Memory Optimization

1.  **Memory Consolidation:** Uninterrupted sleep enables the synthesis
    of new proteins necessary to permanently rewire synapses in the
    mushroom body.
2.  **Pausing the Forgetting Chemical:** A baseline drip of dopamine
    actively erases fragile memories during wakefulness. Sleep, triggered
    by the dorsal Fan-Shaped Body (dFB) in the central complex, pauses
    this dopamine release, allowing memories to harden.
3.  **Synaptic Pruning:** Sleep initiates synaptic homeostasis, trimming
    back weak, unimportant neurological connections formed during the day
    to save energy and space.

#### The Critical Window

Memory consolidation requires sleep within a critical 4 to 6-hour
window post-learning. If the fly is kept awake past this window, the
temporary synaptic alterations dissolve, and the memory is lost
permanently. Because flies are crepuscular, a natural midday siesta
ensures that lessons learned in the morning fall perfectly within this
crucial window.

### Memory Typology: Formation and Retention

Fruit flies form different grades of memory based on the intensity and
frequency of the stimuli.

| Memory Type | Trigger Method | Biological Mechanism | Sleep Required? |
| :--- | :--- | :--- | :--- |
| **Short-Term Memory (STM)** | Single Event | Temporary tweaks to existing synaptic proteins (cAMP alters potassium channels). | No |
| **Anesthesia-Resistant Memory (ARM)** | Massed Training (Cramming without breaks) | Heavy-duty chemical scaffolding; lasts 1-2 days without permanent DNA/protein changes. | No |
| **Long-Term Memory (LTM)** | Spaced Training (Repetition with breaks) | Rhythmic cAMP pulses unlock DNA via the CREB pathway, building brand new proteins and synapses. | Yes |

This multi-tiered system ensures the fly can react immediately to
threats while selectively investing its limited biological energy into
remembering only the most critical, recurring features of its
environment.

---

## Mechanisms

### 2a. Synaptic scaling (hours)

**What changes:** All incoming weights to a neuron, scaled uniformly by
the same multiplicative factor.

**Mechanism:** When a neuron's average firing rate deviates from its
target over hours, it scales ALL of its incoming weights up or down:

```
Firing too much → scale all incoming w_ij by 0.95x
Firing too little → scale all incoming w_ij by 1.05x
```

This preserves the **relative** pattern of weights — the structure that
STDP learned. A connection that's 3x stronger than its neighbor stays
3x stronger after scaling; only the absolute magnitudes change.

**Relationship to threshold adjustment (Phase 1):** Both are
homeostatic, but threshold adjustment changes the neuron's sensitivity
(one variable per neuron), while synaptic scaling changes the inputs
themselves (one multiplier across all incoming synapses). Scaling is
more faithful to the biology and preserves learned weight ratios better.

**Implementation priority:** Phase 2. Complements Phase 1 threshold
adjustment — together they provide robust homeostatic control.

### 2b. Metaplasticity — "plasticity of plasticity" (minutes–hours)

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

In standard STDP, every synapse has the same fixed learning rate. In
our metaplasticity formulation, each synapse tracks how much it has
been recently modified and scales its learning rate accordingly:

```
theta_m_ij += |delta_w_ij| - theta_m_ij / tau_meta

eta_ij = eta_base / (1 + theta_m_ij)
```

theta_m_ij accumulates from recent |Δw| (the absolute magnitude of
weight changes after reward gating) and decays with time constant
tau_meta. When theta_m_ij is high (recently modified synapse), the
effective learning rate eta_ij drops — the synapse becomes harder to
change further. When theta_m_ij is low (quiet synapse), eta_ij
approaches eta_base — the synapse is fully plastic.

```
Recently modified synapse (high theta_m_ij):
  → low eta_ij → harder to modify further in either direction
  → must wait for theta_m_ij to decay before regaining plasticity

Quiet synapse (low theta_m_ij):
  → eta_ij ≈ eta_base → fully responsive to STDP
  → ready to capture new associations
```

This formulation deliberately differs from the classical BCM rule,
which slides the threshold based on postsynaptic firing rate. We use
per-synapse |Δw| instead because postsynaptic firing rate is already
the signal that homeostasis uses to adjust V_th (Phase 1 section 1d).
Using the same signal for both mechanisms would create redundancy.
Per-synapse |Δw| tracking gives metaplasticity its own independent
input — the recent modification history of each individual connection —
so the two stability mechanisms complement each other without overlap.

An additional advantage: because our STDP is reward-gated (Phase 1
section 1b), the |Δw| that feeds theta_m reflects the post-gating
weight change (eligibility × dopamine), not raw spike timing
coincidences. This means metaplasticity dampens synapses that are
actually being modified by the learning system, not just synapses that
happen to see correlated spikes.

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
| Signal | Postsynaptic firing rate | Per-synapse |Δw| history |
| Adjusts | Excitability (V_th) or all weights uniformly | STDP learning rate per synapse |
| Prevents | Runaway network activity | Runaway individual weight growth |
| Timescale | Hours (gene expression) | Minutes–hours (protein modification) |
| Analogy | Thermostat (adjusts room temperature) | Thermostat per radiator (adjusts each heater independently) |

Both are needed: homeostasis for network-level stability, metaplasticity
for synapse-level stability. They use different input signals (firing
rate vs modification history), so neither makes the other redundant.

**Implementation:** A per-synapse modification threshold that scales the
STDP learning rate:

```
theta_m_ij += |delta_w_ij| - theta_m_ij / tau_meta
eta_ij = eta_base / (1 + theta_m_ij)

STDP update:
    delta_w_ij = eta_ij * stdp_update(pre, post timing)
```

**Implementation priority:** Phase 2. One extra float per synapse
(theta_m_ij), prevents STDP weight saturation over extended operation.
Not needed for the initial burn-in → first locomotion window, but
critical for sustained long-term learning.

### 2c. Synaptic tagging and capture (minutes–hours)

**What changes:** Whether a recent weight change becomes permanent or
fades.

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

**Model implementation:** Per-synapse tag variables, a neuron-level
protein synthesis signal, and a consolidation mechanism that converts
tagged early-phase changes to permanent late-phase changes.

**Implementation priority:** Phase 2, when we add sleep/wake cycles and
want realistic memory consolidation dynamics.

### 2d. Sleep/wake cycling and oscillatory gating

**What changes:** When and how effectively plasticity occurs — the brain
cycles between states that favor learning, consolidation, and
maintenance.

Neural oscillations — rhythmic, population-level activity patterns —
gate plasticity. The brain doesn't learn uniformly at all times.

Key oscillatory states in *Drosophila*:

- **Circadian rhythms** — flies learn better at certain times of day.
  Clock neurons modulate global arousal and plasticity, with peak
  learning during subjective daytime
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

**How sleep connects to tagging and capture:**

The critical 4–6 hour window described in the biology section above maps
directly to the tag lifetime. Tags set during waking learning persist
for ~1–3 hours. Sleep-driven replay reactivates tagged circuits,
triggering the protein synthesis that captures them. If sleep doesn't
arrive within the window, tags expire and the memory is lost — exactly
what the biology shows.

```
Wake phase:
  → experience → STDP → eligibility → reward → weight change → tag set
  → dopamine drip slowly erases untagged/fragile changes

Sleep phase:
  → sensory gates close
  → dopamine drip pauses (fragile memories stop being erased)
  → replay reactivates recent circuits
  → protein synthesis captures tagged synapses
  → global downscaling prunes noise (synaptic homeostasis)
  → result: consolidated, clean memory state
```

**Implementation priority:** Phase 2 for sleep/wake cycling (global
synaptic downscaling during sleep, replay-driven consolidation). Phase 3
for oscillatory gating within circuits.

---

## Result

With Phase 2 mechanisms active, the network:
- Has realistic temporal dynamics (STF/STD shape moment-to-moment
  transmission)
- Preserves learned structure during homeostatic adjustment (synaptic
  scaling)
- Distinguishes between fragile recent memories and consolidated
  long-term memories (tagging)
- Benefits from sleep — replay consolidates, downscaling cleans (sleep
  cycling)

All the same parameters are learnable as Phase 1 — just better dynamics
for how those parameters are maintained over time.
