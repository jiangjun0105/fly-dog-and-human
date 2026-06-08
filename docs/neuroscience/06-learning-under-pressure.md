# Under-Pressure Learning (Changing Environments)

When the environment changes significantly — new predators, temperature
shift, food scarcity, injury — the normal learning mechanisms may not
be sufficient. The fly needs to change not just *how strongly*
connections operate but potentially *how they operate at all*. These
mechanisms modify parameters that are normally stable.

Part of the [Learning Strategies](03-learning-strategies.md) series.

## 2a. Neuromodulatory state switching (seconds–minutes)

**What changes:** Global operating point — effective thresholds,
time constants, and gain across entire circuits.

**Mechanism:** Stress, danger, or arousal triggers release of
neuromodulators (octopamine, serotonin) that shift the network's
operating state:

```
Resting state:    low octopamine → high thresholds, long tau_m
                  Network is slow, energy-efficient, low activity

Aroused state:    high octopamine → low thresholds, short tau_m
                  Network is fast, responsive, high activity

Stressed state:   high serotonin → shifted baselines
                  Sustained alertness, altered risk sensitivity
```

**Biological function:** This is the fastest response to environmental
change. It doesn't create new circuits — it changes the gain on
existing ones. A fly that detects a predator doesn't need to learn a
new escape route; it needs its existing escape circuits to be faster and
more sensitive.

**Model parameter:** Modulates tau_m_eff, V_th_eff, V_rest_eff via
the k coupling constants (see [LIF model design](02-lif-model-design.md)).

**Implementation priority:** Phase 1. The arousal system is important
even for basic locomotion — the transition from standing to walking
involves octopaminergic state switching.

## 2b. Epigenetic regulation (hours–days)

**What changes:** Receptor expression profiles, ion channel densities,
and potentially the effective sign of connections.

**Mechanism:** Sustained environmental signals (not momentary spikes,
but hours of changed conditions) trigger epigenetic changes —
methylation patterns, histone modifications — that turn genes on or off
without altering the DNA sequence:

```
Sustained cold exposure:
  → upregulate certain K+ channels → shift V_rest, tau_m
  → change receptor subunit expression → could shift NT sensitivity

Sustained stress:
  → upregulate octopamine receptor expression in motor circuits
  → increase dopamine receptor density (heightened reward sensitivity)
  → potentially switch receptor subtypes → effective sign change

Sustained social isolation vs group housing:
  → different serotonin receptor profiles
  → different aggression/courtship circuit tuning
```

**Sign changes via receptor switching:** This is the mechanism by which
signs can effectively change within one lifetime. If a neuron
downregulates its nicotinic acetylcholine receptors (excitatory) and
upregulates muscarinic receptors (inhibitory) at a particular synapse,
that connection flips from excitatory to inhibitory. The presynaptic
neuron still releases the same transmitter (Dale's principle holds), but
the postsynaptic response changes.

**Biological function:** Medium-term adaptation to sustained
environmental change. The fly that develops in a cold environment has
genuinely different neural properties than one in a warm environment —
not because its DNA is different, but because different genes are active.
This is more powerful than just adjusting weights: it changes the
fundamental operating characteristics of neurons.

**What can change at this timescale:**

| Parameter | How it changes | Biological mechanism |
|-----------|---------------|---------------------|
| **Connection signs** | Receptor subtype switching | Upregulate inhibitory receptors, downregulate excitatory (or vice versa) |
| **tau_m base values** | Ion channel density changes | Express more/fewer leak channels |
| **V_rest baseline** | Resting conductance changes | Different balance of ion channel types |
| **Modulatory coupling (k values)** | Receptor density changes | Express more/fewer modulatory receptors |
| **STDP parameters** | Plasticity rule tuning | Change expression of plasticity-related proteins (CaMKII, calcineurin) |

**What does NOT change at this timescale:**

| Parameter | Why not |
|-----------|---------|
| **Topology** (which neurons connect) | Axon/dendrite structure is physically established during development. Pruning/sprouting happens but on longer timescales |
| **Cell type identity** | Determined during embryonic development. A motor neuron doesn't become a sensory neuron |
| **Dale's principle** | The presynaptic neuron's transmitter is fixed. Only the postsynaptic response changes |

**Model implementation:** Slow parameter drift driven by sustained
environmental signals. Not spike-driven (unlike STDP) — driven by
aggregate statistics like average stress level, temperature, or
resource availability over hours:

```
IF sustained_stress_hours > threshold:
    receptor_profile[cell_type] shifts toward high-alertness preset
    → k_values change
    → some connection signs may flip
    → STDP learning rate may increase (faster adaptation under pressure)
```

**Implementation priority:** Phase 2–3. Important for long-running
simulations where the environment changes, but not needed for initial
motor learning.

## 2c. Structural plasticity (days–weeks)

**What changes:** The physical topology — new synapses form, existing
synapses are eliminated, dendritic spines grow or retract.

**Mechanism:** Sustained activity patterns can trigger physical growth
of new connections or pruning of unused ones. This is downstream of
STDP — connections that are consistently weakened to near-zero may
eventually be physically pruned, and strongly active neurons may
sprout new connections to frequently co-active partners.

**Biological function:** Consolidation of learned circuits. While STDP
adjusts existing connection strengths, structural plasticity can add
new connections or remove useless ones. This is particularly relevant
after injury (rewiring around damaged circuits) or during development
(activity-dependent refinement of the initial wiring).

**What can change:**

| Change | Mechanism |
|--------|-----------|
| **New connections** | Axonal/dendritic sprouting toward active partners |
| **Removed connections** | Pruning of consistently silent synapses |
| **Connection relocation** | Spines retract from one partner and extend to another |

**Model implementation:** Periodic topology updates (every N simulation
hours): add connections where eligibility traces have been consistently
high but no connection exists; remove connections where w_ij has been
near zero for an extended period.

**Implementation priority:** Phase 3. The initial connectome topology
is rich enough for phase 1–2 learning. Structural plasticity becomes
relevant when simulating development, injury recovery, or very
long-term adaptation.

## Acknowledged simplifications

The following mechanisms are established in the neuroscience literature
for adaptation under changing or stressful conditions, but are not
included in our current model. Documented here for future reference.

### Sensitization and habituation (non-associative learning)

Under threat, animals exhibit two forms of learning that don't require
associative pairing (no STDP, no reward signal):

- **Sensitization** — a single noxious stimulus (e.g., a predator
  attack) causes increased responsiveness to *all* subsequent stimuli,
  not just the original one. A fly that was just attacked will startle
  more easily at unrelated touch or vibration. The mechanism is
  serotonin-mediated in invertebrates: serotonin released by
  nociceptive interneurons acts on presynaptic terminals of sensory
  neurons, increasing their neurotransmitter release probability. This
  can last minutes to hours after a single event, or days after
  repeated trauma.

- **Habituation** — repeated presentation of a harmless stimulus
  leads to decreased response. A fly stops reacting to repeated gentle
  air puffs. The mechanism is vesicle depletion and reduced release
  probability at specific synapses — mechanistically related to
  short-term depression (STD, section 1e in [normal learning](04-learning-normal.md))
  but operating on longer timescales and with molecular consolidation.

These are distinct from STDP because they modify the *gain* of entire
reflex pathways rather than individual connection weights based on spike
timing. Sensitization is particularly relevant under threat — it's the
nervous system's way of saying "something bad happened, be more
responsive to everything for a while."

In *Drosophila* specifically, both are well-characterized in larval
nociceptive rolling behavior and adult olfactory jump reflex. The
molecular pathways (cAMP/PKA for short-term, CREB-dependent gene
expression for long-term) are among the best-understood in neuroscience,
originally characterized in *Aplysia* by Eric Kandel's lab.

**Impact on our model:** Without sensitization, our model can only
increase responsiveness via octopaminergic arousal (section 2a), which
is a broadcast signal. Sensitization provides a more targeted gain
increase on specific reflex pathways. Without habituation, the model
will continue responding to repeated irrelevant stimuli indefinitely.

**Implementation difficulty:** Moderate. Sensitization requires a
per-synapse presynaptic release probability variable modulated by
serotonin. Habituation requires activity-dependent vesicle pool
dynamics.

**Priority:** Phase 2 for habituation (simple, important for filtering
noise). Phase 2–3 for sensitization (requires serotonergic pathway
modeling).

### Nociceptive plasticity (peripheral sensitization)

After tissue damage, the sensory neurons themselves become more
sensitive at the injury site — the threshold for detecting pain drops,
and the response to a given stimulus is amplified. This is
**peripheral** plasticity, distinct from all the central mechanisms
above.

In *Drosophila*, class IV multidendritic (md) neurons are the primary
nociceptors. After UV-induced tissue damage or thermal injury:
- Their firing threshold drops (thermal nociception threshold shifts
  from ~39°C to ~32°C)
- Their receptive field expands (nearby undamaged tissue also becomes
  more sensitive)
- The molecular mechanism involves TNF-alpha/Eiger signaling from
  damaged tissue to the sensory neuron, which upregulates the TRPA1
  heat-sensing channel

This is the fly equivalent of the inflammation response that makes a
burn or cut hurt more when you touch it — the sensor itself has been
reprogrammed, not just the brain's processing of the signal.

**Impact on our model:** Our model treats sensory input as an external
signal (SpikeGeneratorGroup or PoissonGroup). We don't model the
sensory neurons' own plasticity — input statistics are set by the
simulation, not by the sensory neurons' history. Missing this means our
model can't capture injury-related behavioral changes like limping or
guarding.

**Implementation difficulty:** Low–moderate. Could be modeled as
activity-dependent changes to the input generation parameters (rate,
threshold) of sensory neuron groups, driven by simulated damage signals.

**Priority:** Phase 3. Relevant when modeling injury recovery or
body-environment interaction with damage.

### Temperature compensation

*Drosophila* is a poikilotherm — its body temperature equals the
ambient temperature. Every biochemical process in the nervous system
is temperature-dependent: ion channel kinetics, neurotransmitter
release, enzymatic reactions. The Q10 effect (reaction rate roughly
doubles for every 10°C increase) means a fly at 30°C has fundamentally
different neural dynamics than one at 15°C.

Without active compensation, a CPG circuit tuned at 25°C would produce
completely different rhythms at 15°C or 35°C — channels would gate
slower or faster, changing the timing relationships that the circuit
depends on. Yet flies walk, fly, and behave across a ~15–35°C range.

Compensation mechanisms:
- **Acute (seconds–minutes):** Different ion channel types have
  different Q10 values. If a circuit uses a mix of channels with
  opposing temperature sensitivities (e.g., one activates faster when
  hot, another slower), the net effect can be partially self-canceling.
  This is a "built-in" robustness from the channel composition.
- **Medium-term (hours–days):** Neurons adjust ion channel expression
  to compensate — upregulating channels that counteract the temperature
  shift. This overlaps with epigenetic regulation (section 2b) but is
  specifically driven by temperature-sensing pathways (TRP channels,
  thermosensory neurons in the antenna and brain).
- **Evolved (generations):** The specific mix of ion channels in each
  cell type was shaped by evolution to provide robustness across the
  species' ecological temperature range.

This is particularly well-studied in crustacean stomatogastric ganglion
(STG) CPGs and in *Drosophila* larval locomotion CPGs — directly
relevant to our motor control model.

**Impact on our model:** Our model uses fixed tau_m base values per
superclass. At different simulated temperatures, these would need to
change according to Q10 rules. Without temperature compensation, any
temperature-dependent simulation would show unrealistic behavior — CPG
rhythms would speed up or slow down proportionally with temperature
rather than being buffered.

**Implementation difficulty:** Moderate. Requires temperature-dependent
scaling of all time constants and possibly conductances. The
compensation mechanisms add another layer of slow parameter adjustment.

**Priority:** Phase 3. Only relevant if the simulation includes a
temperature variable as part of the environment. Not needed for
constant-temperature simulations.

### Metabolic state modulation (hunger, energy)

The fly's nutritional state directly modulates neural circuit function
and learning through insulin/adipokinetic hormone (AKH) signaling:

- **Starvation increases learning:** Hungry flies learn odor-food
  associations faster and retain them longer. Insulin-producing cells
  (IPCs) in the brain reduce their output during starvation, which
  disinhibits mushroom body output neurons (MBONs), altering the
  valence of odor memories.
- **AKH (fly glucagon) modulates locomotion:** AKH released during
  energy deficit increases locomotor activity (foraging behavior) by
  acting on octopaminergic neurons. This is a cross-talk between
  metabolic signaling and the arousal system (section 2a).
- **Insulin signaling modulates STDP:** Insulin receptors on mushroom
  body neurons gate plasticity — high insulin (fed state) reduces
  plasticity, low insulin (hungry state) enhances it. The fly literally
  learns better when hungry.
- **dNPF/NPF (fly NPY):** Neuropeptide F signals motivational state
  and modulates dopaminergic neuron activity, changing the reward
  signal that gates STDP (section 1b in [normal learning](04-learning-normal.md)).

**Impact on our model:** Without metabolic state modulation, our model's
learning rate is constant regardless of the simulated organism's energy
state. A fly that is "starving" in simulation would learn no differently
from a satiated one. Missing this removes a major behavioral driver —
much of a fly's behavior is organized around finding food.

**Implementation difficulty:** Moderate. Requires a metabolic state
variable (energy level) that modulates dopamine gain, STDP rates, and
octopamine baseline via insulin/AKH signaling pathways.

**Priority:** Phase 2–3. Relevant when the simulation includes a
body with metabolic needs and foraging behavior.

### Hormonal gating (ecdysone)

Ecdysone is the primary steroid hormone in insects. During development
it drives metamorphosis and massive circuit remodeling, but in adult
flies it continues to modulate neural function:

- **Mushroom body plasticity:** Ecdysone receptor (EcR) expression in
  mushroom body neurons gates long-term memory formation. Ecdysone
  levels rise after mating, environmental enrichment, and some stressors,
  creating windows of enhanced plasticity.
- **Circuit remodeling in adults:** While large-scale structural changes
  are developmental, ecdysone in adults can trigger localized dendritic
  remodeling in specific neuron populations.
- **Behavioral state transitions:** Ecdysone level changes are associated
  with transitions between behavioral states (e.g., post-mating changes
  in female receptivity and egg-laying behavior are partially
  ecdysone-mediated, though this is better characterized in females).

**Impact on our model:** Without ecdysone gating, our model has no
concept of hormonal windows of enhanced plasticity. Learning capacity
is uniform over time rather than being gated by hormonal state.

**Implementation difficulty:** Low. Could be modeled as a slow-timescale
multiplier on STDP learning rate and structural plasticity rate, driven
by simulated life events.

**Priority:** Phase 3. Only relevant for very long simulations that
model life-stage transitions.

### Immune-neural interactions

Immune activation directly alters neural function and behavior in
*Drosophila*. The innate immune pathways (Toll and Imd) are activated by
infection or injury, and their downstream signaling affects the nervous
system:

- **Sickness behavior:** Infected flies show reduced locomotion, altered
  sleep patterns (increased sleep), reduced feeding, and impaired
  learning. These are active behavioral responses orchestrated by
  immune-neural crosstalk, not just side effects of being sick.
- **NF-κB in neurons:** The transcription factor NF-κB (downstream of
  Toll/Imd) is expressed in neurons and modulates synaptic function.
  Chronic immune activation can cause neurodegeneration.
- **Antimicrobial peptides (AMPs) in the brain:** Some AMPs produced
  during immune responses are expressed in neurons and affect neural
  excitability independently of their antimicrobial function.
- **Glial immune response:** Glia (especially in the blood-brain
  barrier) are the first responders to systemic infection and relay
  immune signals to neurons via cytokine-like molecules.

**Impact on our model:** Without immune-neural interactions, our model
cannot capture infection-related behavioral changes. For a motor control
model this is probably irrelevant, but for a whole-organism behavioral
model it removes a significant source of state-dependent behavioral
modulation.

**Implementation difficulty:** High. Requires modeling immune state
as a separate system with bidirectional coupling to neural circuits.

**Priority:** Phase 3 or beyond. Low priority for motor control.
Potentially relevant for disease modeling.

### Rapid homeostatic plasticity

Section 1d in [normal learning](04-learning-normal.md) describes
homeostatic plasticity operating on an hours timescale via gene
expression. Under extreme perturbation — sudden loss of a major input,
pharmacological blockade, or acute injury — a faster mode of homeostatic
compensation can engage, operating on **minutes** rather than hours.

The fast mode uses different molecular machinery:
- **Local protein translation** — mRNA molecules pre-positioned at
  synapses are translated locally without waiting for nuclear gene
  expression. This produces new receptors and ion channels within
  minutes.
- **Post-translational modification** — existing proteins are rapidly
  phosphorylated or dephosphorylated to change their function, rather
  than waiting for new proteins to be synthesized.
- **Rapid receptor trafficking** — receptors already present in
  intracellular vesicles are quickly inserted into or removed from the
  postsynaptic membrane.

This fast mode is less precise than the slow gene-expression mode —
it makes coarser adjustments — but it prevents the circuit from
catastrophically failing while the slower, more precise homeostatic
mechanism catches up.

**Impact on our model:** Our homeostatic plasticity has a single
timescale (slow, hours). Under sudden large perturbations (e.g.,
simulated injury removing a set of neurons), the network would take
unrealistically long to compensate. The fast mode would provide
immediate partial recovery followed by gradual fine-tuning.

**Implementation difficulty:** Low. Same equation as slow homeostasis
but with a faster learning rate that only activates when the deviation
from target rate exceeds a large threshold.

**Priority:** Phase 2. Particularly relevant if the simulation includes
perturbation experiments (removing neurons, blocking pathways).

### Compensatory plasticity after sensory loss

When one sensory modality is lost or reduced, the remaining modalities
can be enhanced through large-scale circuit rebalancing. In *Drosophila*:

- **Dark-rearing** enhances olfactory and mechanosensory processing —
  neurons that would normally be tuned to visual input become more
  responsive to other modalities.
- **Antennal ablation** (removing olfactory input) leads to enhanced
  visual and mechanosensory responses in downstream circuits.
- The mechanism involves both homeostatic upregulation of remaining
  inputs (the silent neurons become more excitable, section 1d) and
  structural plasticity (section 2c) where new connections form from
  remaining sensory pathways to the deprived target circuits.

This is a multi-mechanism process that recruits homeostasis, structural
plasticity, and epigenetic regulation working together over days to
weeks.

**Impact on our model:** Without compensatory plasticity, simulated
sensory loss would leave large portions of the network permanently
underutilized. The network wouldn't reallocate computational resources
to remaining senses. This matters for injury modeling and for
understanding the robustness of the biological network.

**Implementation difficulty:** Not a separate mechanism — it emerges
from the interaction of homeostasis, structural plasticity, and
epigenetic regulation if all three are implemented. The challenge is
getting the timescales and magnitudes right so that the compensation
is realistic.

**Priority:** Phase 3. Emerges naturally if the component mechanisms
are implemented correctly. Interesting as a validation test — if we
remove visual input and see enhanced olfactory processing emerge, that's
evidence the model captures something real.
