# LIF Model Design

Design reference for the Leaky Integrate-and-Fire (LIF) spiking neuron
model used in the Digital Drosophila project. Covers the mathematical
foundation, all parameters, neuromodulation, learning rules, and how
the connectome data maps into each.

## The membrane equation

The LIF model describes how a neuron's membrane voltage evolves over
time in response to synaptic input:

```
tau_m * dV/dt = -(V - V_rest) + R * I(t)
```

| Symbol | Name | Meaning |
|--------|------|---------|
| V | Membrane voltage | The neuron's state variable — the thing we simulate |
| V_rest | Resting potential | Voltage when no input is present (equilibrium) |
| tau_m | Membrane time constant | How fast V decays back to V_rest without input |
| R | Membrane resistance | Converts input current to voltage change |
| I(t) | Total input current | Sum of all synaptic inputs at time t |

The term `-(V - V_rest)` is the **leak** — without input, V exponentially
decays back to rest with time constant tau_m. More input pushes V up;
the leak pulls it back down. It behaves like a leaky bucket: pour water
in (synaptic input), the level rises, but it's always draining.

## The spike rule

When V crosses a threshold, the neuron fires a spike and resets:

```
if V >= V_th:
    emit spike
    V = V_reset
    wait for t_refract
```

| Symbol | Name | Meaning |
|--------|------|---------|
| V_th | Firing threshold | Voltage at which the neuron fires |
| V_reset | Reset potential | Voltage after a spike (typically = V_rest) |
| t_refract | Refractory period | Dead time after a spike during which the neuron cannot fire again |

The spike itself is not modeled as a voltage waveform — it's a discrete
event. What matters is *when* it happens, not its shape.

## Synaptic input

The input current I(t) for neuron j is the sum of all incoming spikes,
weighted by connection strength:

```
I_j(t) = sum over all presynaptic neurons i:  w_ij * delta(t - t_spike_i)
```

Each time a presynaptic neuron i fires at time t_spike_i, it delivers
an instantaneous current pulse of magnitude w_ij to neuron j. The sign
of w_ij determines the effect:

- **w_ij > 0** (excitatory): pushes V toward threshold — from
  acetylcholine neurons
- **w_ij < 0** (inhibitory): pushes V away from threshold — from GABA
  and glutamate neurons

This is where the connectome data maps directly into the model: the
adjacency matrix provides the w_ij values, and the neurotransmitter
identity provides the sign.

## Neuromodulated membrane equation

The basic LIF equation above uses fixed parameters. In reality,
neuromodulators (dopamine, octopamine, serotonin) shift the operating
state of neurons by modulating ion channel properties. The full
modulated equation is:

```
tau_m_eff * dV/dt = -(V - V_rest_eff) + R * I(t)

where:
    tau_m_eff   = tau_m_base[cell_type]   * (1 - arousal * k_tau[cell_type])
    V_rest_eff  = V_rest_base             + modulatory_shift * k_rest[cell_type]
    V_th_eff    = V_th_homeo              - arousal * k_vth[cell_type]
    V_th_homeo  = V_th_base + homeostatic adjustment (see Learning section)
```

Neuromodulators are **broadcast signals** — a handful of modulatory
neurons (octopamine: ~100, serotonin: 20, dopamine: sparse) influence
thousands of targets. They don't carry specific information; they shift
the entire network's operating state (e.g., from "resting fly" to
"walking fly").

### What neuromodulators change and why

| Parameter | Effect | Mechanism |
|-----------|--------|-----------|
| **tau_m** | Arousal shortens integration window — neurons respond faster | Octopamine opens additional ion channels, lowering effective membrane resistance |
| **V_rest** | Can depolarize (closer to threshold) or hyperpolarize | Depends on receptor type: D1-like depolarizes, D2-like hyperpolarizes |
| **V_th** | Arousal lowers threshold — neurons fire more easily | Modulates voltage-gated sodium channel availability |
| **w_ij** | Modulates presynaptic release probability | Changes how many vesicles are released per spike at a given synapse |

### Modulatory coupling constants (k parameters)

Each k parameter controls how strongly a neuromodulatory signal affects
a given neuron's property. These are defined **per cell type** because
receptor expression is determined by a neuron's genetic identity, and
cell type is the classification that captures this — neurons of the same
cell type share morphology, connectivity, AND gene expression.

Two intrinsic interneurons in different circuits (e.g., leg CPG vs
sensory processing) can have very different octopamine sensitivity
despite sharing the superclass `vnc_intrinsic`, because they are
different cell types expressing different receptor profiles.

The k values are initialized through a three-level fallback:

```
Level 1: k_global           — one tunable hyperparameter (starting point)
Level 2: k_default[superclass] = k_global * multiplier
                              — qualitative adjustment by functional role
Level 3: k_override[cell_type] — specific value from literature or
                                  electrophysiology, when available
```

Most cell types start at their superclass default. The architecture
stores 4,206 slots (one per cell type) so overrides slot in without
restructuring.

**Superclass defaults** (multipliers relative to k_global):

| Superclass | Multiplier | Reasoning |
|------------|:----------:|-----------|
| vnc_motor | 1.5x | Primary octopamine targets for locomotion — large gain change |
| vnc_intrinsic | 1.0x | Baseline — the main computational layer |
| vnc_sensory | 0.5x | Already fast; modest additional modulation |
| descending_neuron | 1.0x | Command neurons — moderate sensitivity |
| ascending_neuron | 0.5x | Reporting upstream, less affected by motor arousal |

These multipliers are directionally correct but the magnitudes are
initial guesses. The specific values would come from electrophysiology
literature measuring neuronal responses before/after neuromodulator
application, or from tuning against realistic firing rate targets.

### Modulatory systems in *Drosophila*

| Modulator | VNC neurons | Signals | Primary effect on motor circuits |
|-----------|:----------:|---------|--------------------------------|
| **Octopamine** | ~100 | Arousal, locomotion onset | Global gain increase — lowers threshold, shortens tau_m. Invertebrate equivalent of norepinephrine |
| **Serotonin** | 20 | Sustained arousal, aggression | Slower state changes — shifts baseline excitability |
| **Dopamine** | sparse | Reward / punishment | Gates learning (see below). In VNC, also modulates specific motor patterns |

## Parameter design decisions

### Decision table

| Parameter | Resolution | Fixed / Learned / Modulated | Initialization | Rationale |
|-----------|-----------|:---------------------------:|----------------|-----------|
| **Topology** (i→j) | per connection | **Fixed** | From adjacency matrix | The connectome wiring is the scaffold. Structural plasticity operates on developmental timescales, not relevant for online learning |
| **sign(w_ij)** | per neuron | **Fixed** | From `consensusNt` → sign map | Dale's principle — a neuron does not switch its neurotransmitter |
| **w_ij** | per connection | **Learned** (STDP + reward gating) | Log-scaled synapse counts from connectome | THE primary learning mechanism. Initialize from biology, then let plasticity tune. Magnitudes change; signs don't |
| **V_th** | per neuron | **Learned** (homeostatic) + **Modulated** (arousal) | Degree-scaled from in-degree | Two components: slow homeostatic adjustment toward target firing rate + fast modulatory shift from arousal state |
| **tau_m** | per cell type | **Fixed base** + **Modulated** | Base per superclass (sensory ~5 ms, intrinsic ~10 ms, motor ~20 ms). Effective value shifted by arousal | Real neurons don't tune tau_m on behavioral timescales, but neuromodulators shift it by changing ion channel conductances |
| **V_rest** | per neuron | **Fixed base** + **Modulated** | -70 mV base. Modulatory shift from dopamine/octopamine | Biophysical baseline is constant; neuromodulators shift it via receptor-mediated ion channel modulation |
| **V_reset** | global | **Fixed** | -70 mV (= V_rest_base) | Biophysical constant — not tuned by the brain at any timescale |
| **t_refract** | per superclass | **Fixed** | 2 ms (all types initially) | Ion channel recovery kinetics. Could refine per superclass later but low impact on first simulation |
| **R** | global | **Fixed** (folded into weights) | 1 (dimensionless) | Membrane resistance is absorbed into the weight scaling — R * w_ij treated as single value |
| **k_tau, k_vth, k_rest** | per cell type | **Tunable hyperparameters** | Superclass default (see above) | Modulatory coupling strengths. Per cell type because receptor expression varies by genetic identity. Initialized from superclass, overridden when literature data available |

### Design principle: fix the structure, learn the function

The connectome tells us **what can connect** (topology) and **with what
sign** (NT identity). These are fixed — they are the genetically
determined scaffold.

Learning fills in **how strong** each connection is (w_ij via STDP) and
**how excitable** each neuron is (V_th via homeostasis). These are the
degrees of freedom the real fly brain uses to adapt through experience.

Neuromodulation sits between structure and learning — it doesn't change
the wiring, but it shifts the operating point of the entire network
based on behavioral state. A fly walking vs resting uses the same
circuit with different gain settings.

### Why these specific decisions

**w_ij — learned via STDP, not fixed:** If we fix weights at their
connectome values, the network has zero ability to adapt. The synapse
counts from the EM reconstruction represent the anatomy of one specific
fly at one moment — they don't encode the learned associations that fly
accumulated over its lifetime. STDP lets the network develop its own
functional weights starting from the anatomical scaffold.

**V_th — learned (homeostatic) + modulated:** Threshold is the most
dynamic parameter in the model. It operates at two timescales:
(1) Homeostatic plasticity (minutes) — each neuron adjusts its threshold
toward a target firing rate, preventing runaway excitation or network
death. This is critical for stability when STDP is also changing weights.
(2) Arousal modulation (seconds) — octopamine lowers threshold globally
when the fly transitions to an active state, making the whole circuit
more responsive.

**tau_m — fixed base per superclass, modulated by arousal:** Membrane
time constant is determined by the neuron's physical properties (cell
size, channel density), which don't change on behavioral timescales.
But the *effective* time constant changes under neuromodulation because
modulators open additional ion channels. Setting different base values
per superclass captures real functional differences: sensory neurons
integrate briefly (~5 ms, for fast responses), motor neurons integrate
longer (~20 ms, for smooth output).

**sign — fixed, never learned:** Dale's principle. A neuron uses the
same neurotransmitter at all of its synapses throughout its life. The
sign comes from the `consensusNt` field in the connectome data. Allowing
sign flips would be biologically wrong and would destabilize learning.

**Topology — fixed, never learned:** The physical wiring of the fly's
nervous system is established during development and does not rewire on
the timescales relevant to behavior and learning (seconds to hours).
The adjacency matrix from the connectome is the permanent scaffold.

## Learning rules

### Layer 1: Reward-modulated STDP (weight learning)

STDP (Spike-Timing-Dependent Plasticity) adjusts weights based on the
relative timing of pre- and post-synaptic spikes:

```
Pre fires before post (causal):    delta_w > 0  (strengthen)
Post fires before pre (acausal):   delta_w < 0  (weaken)
```

Pure STDP is unsupervised — it has no notion of good or bad outcomes.
Reward modulation adds this by introducing an eligibility trace:

```
STDP computes:     e_ij(t) = eligibility trace (candidate weight change)
Dopamine signal:   d(t)    = reward/punishment broadcast
Actual update:     w_ij += d(t) * e_ij(t)
```

The eligibility trace e_ij decays over a short window (~seconds). If a
dopamine signal arrives within that window, the pending weight change is
consolidated. If no dopamine arrives, the trace fades and the weights
don't change. This is how the fly's mushroom body circuit
(DAN → KC → MBON) actually works — it's the best-characterized
learning circuit in *Drosophila*.

### Layer 2: Homeostatic threshold plasticity

Each neuron adjusts its firing threshold toward a target firing rate:

```
dV_th/dt = eta_homeo * (firing_rate - target_rate)
```

If the neuron fires too much → V_th increases (harder to fire).
If the neuron fires too little → V_th decreases (easier to fire).

This operates on a slower timescale than STDP (eta_homeo is small) and
provides network stability. Without homeostasis, STDP can drive the
network into runaway excitation or complete silence.

### Layer 3: Global state modulation (arousal)

Neuromodulatory signals shift the operating point of the network. These
are not "learning" in the traditional sense but they gate when and how
effectively learning occurs:

```
arousal        = octopamine_level   (0.0 = quiescent, 1.0 = fully active)
reward_signal  = dopamine_level     (0.0 = neutral, >0 = reward, <0 = punishment)
```

Arousal makes the network more responsive (lower threshold, faster
dynamics), creating conditions where more spikes occur and more STDP
eligibility traces are generated. Dopamine then selects which of those
traces become permanent weight changes.

## Brian2 implementation sketch

```python
eqs = '''
dv/dt = (v_rest_eff - v + R * I) / tau_m_eff : volt
I : amp

# Homeostatic threshold
dv_th/dt = eta_homeo * (rate - target_rate) : volt

# Effective parameters (base + modulation)
tau_m_eff = tau_m_base * (1 - arousal * k_tau) : second
v_rest_eff = v_rest_base + modulatory_shift * k_rest : volt
v_th_eff = v_th + v_th_base - arousal * k_vth : volt

# Per-neuron properties (set from connectome / cell type)
tau_m_base : second
k_tau : 1
k_vth : volt
k_rest : 1
'''

neurons = NeuronGroup(
    N, eqs,
    threshold='v > v_th_eff',
    reset='v = v_rest_base',
    refractory=t_refract,
)

# STDP synapses with eligibility trace
stdp_eqs = '''
deligibility/dt = -eligibility / tau_eligibility : 1
w : 1
'''
on_pre = '''
I_post += w
eligibility += A_plus * exp(-(t - lastspike_post) / tau_stdp)
'''
on_post = '''
eligibility -= A_minus * exp(-(t - lastspike_pre) / tau_stdp)
'''

synapses = Synapses(neurons, neurons, stdp_eqs,
                    on_pre=on_pre, on_post=on_post)
synapses.connect(i=pre_indices, j=post_indices)
synapses.w = initial_weights  # from log-scaled connectome data

# Dopamine reward signal consolidates eligibility traces
@network_operation(dt=reward_dt)
def apply_reward():
    synapses.w += dopamine_level * synapses.eligibility
```

## Initialization summary

| Parameter | Initial value | Source | Notes |
|-----------|--------------|--------|-------|
| Topology (i→j) | Adjacency matrix | Connectome | Fixed for lifetime of simulation |
| sign(w_ij) | From NT identity | `consensusNt` → sign map | Fixed (Dale's principle) |
| w_ij | log(1 + synapse_count) * sign * scale | Connectome + Strategy C | Learned via reward-modulated STDP |
| V_th | Degree-scaled from in-degree | Connectome | Learned via homeostatic plasticity + arousal modulation |
| V_rest_base | -70 mV | Standard *Drosophila* value | Fixed base; shifted by neuromodulation |
| V_reset | -70 mV | = V_rest_base | Fixed |
| tau_m_base | Sensory ~5 ms, intrinsic ~10 ms, motor ~20 ms | Per superclass | Fixed base; effective value shifted by arousal |
| t_refract | 2 ms | Standard | Fixed; caps firing at ~500 Hz |
| R | 1 (dimensionless) | Folded into weights | Fixed |
| k_tau, k_vth, k_rest | Per cell type, defaulting to superclass | Tunable hyperparameters | 4,206 slots; most start at superclass default, override from literature when available |
| target_rate | TBD per superclass | Electrophysiology literature | Homeostatic set point; sensory neurons fire faster than motor neurons |
| eta_homeo | Small (slow adaptation) | Tunable | Must be slower than STDP timescale to maintain stability |
| tau_eligibility | ~seconds | From dopamine learning literature | Window during which reward can consolidate a weight change |
