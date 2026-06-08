# LIF Model Design

Design reference for the Leaky Integrate-and-Fire (LIF) spiking neuron
model used in the Digital Drosophila project. Covers the mathematical
foundation, all parameters, neuromodulation, learning rules, and how
the connectome data maps into each. For the implementation timeline, see
[implementation phases](08-implementation-phases.md).

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

| Symbol | Name | Meaning |
|--------|------|---------|
| w_ij | Synaptic weight | Strength of the connection from neuron i to neuron j. Sign determines excitatory (+) vs inhibitory (−) |
| t_spike_i | Spike time | The time at which presynaptic neuron i most recently fired |
| delta(t - t_spike_i) | Dirac delta | An idealized instantaneous pulse — zero everywhere except at the exact moment t = t_spike_i, where it delivers all its energy in one instant. This is a mathematical convenience: real synaptic currents have a brief rise and decay, but for the LIF model we collapse that into a single point event |

Each time a presynaptic neuron i fires at time t_spike_i, it delivers
an instantaneous current pulse of magnitude w_ij to neuron j. The sign
of w_ij determines the effect:

- **w_ij > 0** (excitatory): pushes V toward threshold — from
  acetylcholine neurons
- **w_ij < 0** (inhibitory): pushes V away from threshold — from GABA
  and glutamate neurons (including motor neurons — see sign map below)

This is where the connectome data maps directly into the model: the
adjacency matrix provides the w_ij values, and the neurotransmitter
identity provides the sign. All connections in the adjacency matrix are
CNS-to-CNS (neuron-to-neuron within the central nervous system); motor
neuron output to muscles is not a synapse in the network but an output
interface handled by the body model (see
[motor neuron output](#motor-neuron-output)).

### Why delta functions instead of realistic synaptic currents

In biology, a spike arriving at a synapse triggers a multi-step process
(calcium influx → vesicle fusion → NT release → receptor binding → ion
channel opening) that produces a current with a fast rise (~0.5 ms) and
slow exponential decay (~2–5 ms):

```
Real synaptic current (alpha function):

    I(t) = w * (t/tau_syn) * exp(-t/tau_syn)

                  ╱╲
                 ╱  ╲
                ╱    ╲___
               ╱         ╲____
              ╱                ╲________
         ─────                          ─────
              ↑
          spike arrives
```

The delta function collapses this entire shape into a single
instantaneous pulse — same total energy (w), delivered in zero time:

```
Delta approximation:

    I(t) = w * delta(t - t_spike)

              │
              │
              │
              │
         ─────┼─────────────────────────
              ↑
          spike arrives
```

This works because the membrane equation already has its own time
constant (tau_m) that acts as a low-pass filter. When a delta pulse
hits the membrane, V doesn't stay at its new value — the leak term
`-(V - V_rest)` exponentially decays it back. The membrane smooths
the instantaneous kick over time, producing a voltage response similar
to what a realistic synaptic current would produce.

The approximation is best when tau_m >> tau_syn (the membrane is much
slower than the synapse). For motor neurons (tau_m ~20 ms vs tau_syn
~2–5 ms) the match is good. For sensory neurons (tau_m ~5 ms) the
approximation is rougher — if we need more accurate sensory dynamics
later, we can replace the delta with an alpha or exponential synapse
model without changing the rest of the framework.

In the Brian2 implementation, the delta function becomes a simple
addition at spike time: `I_post += w` in the `on_pre` block.

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

What each parameter does during simulation — its resolution, whether
it changes, and why. For concrete initial values, see the
[initialization summary](#initialization-summary).

| Parameter | Resolution | Behavior | Rationale |
|-----------|-----------|----------|-----------|
| **Topology** (i→j) | per connection | **Fixed** | The connectome wiring is the scaffold. Structural plasticity operates on developmental timescales, not relevant for online learning |
| **sign(w_ij)** | per neuron | **Constrained** (Phase 1–2) · **Driftable** (Phase 3) | Dale's principle holds at the transmitter level. Effective sign depends on postsynaptic receptors. Phase 1–2: STDP cannot cross zero. Phase 3: slow epigenetic drift can shift signs via receptor switching |
| **w_ij** | per connection | **Learned** (Layer 1: STDP + reward) · **Decayed** (Layer 4) · **Rate-modulated** (Layer 5: metaplasticity) | THE primary learning mechanism. Magnitudes change via STDP, fade via decay, learning rate adjusted per-synapse by metaplasticity |
| **V_th** | per neuron | **Learned** (Layer 2: homeostatic) + **Modulated** (Layer 3: arousal) | Two timescales: slow homeostatic adjustment toward target firing rate + fast modulatory shift from arousal state |
| **tau_m** | per cell type | **Fixed base** + **Modulated** (Layer 3: arousal) | Determined by physical neuron properties. Effective value shifted by neuromodulators opening additional ion channels |
| **V_rest** | per neuron | **Fixed base** + **Modulated** (Layer 3: arousal) | Biophysical baseline is constant; neuromodulators shift it via receptor-mediated ion channel modulation |
| **V_reset** | global | **Fixed** | Biophysical constant — not tuned by the brain at any timescale |
| **t_refract** | per superclass | **Fixed** | Ion channel recovery kinetics. Could refine per superclass later but low impact on first simulation |
| **R** | global | **Fixed** (folded into weights) | Membrane resistance is absorbed into the weight scaling — R × w_ij treated as single value |
| **k_tau, k_vth, k_rest** | per cell type | **Tunable hyperparameters** | Modulatory coupling strengths. Per cell type because receptor expression varies by genetic identity |
| **target_rate** | per superclass | **Fixed** | Homeostatic set point. Each neuron class has a different healthy operating range |
| **eta_homeo** | global | **Tunable hyperparameter** | Controls homeostatic adaptation speed. Must be slower than STDP timescale |
| **lambda_decay** | global | **Tunable hyperparameter** | Controls forgetting speed. Balance against STDP learning rate determines retention |
| **theta_m** | per synapse | **Learned** (Layer 5: metaplasticity) | Sliding modification threshold. Accumulates from STDP activity, decays with tau_meta |
| **tau_meta** | global | **Tunable hyperparameter** | Controls how fast metaplasticity state decays back toward baseline |
| **tau_eligibility** | global | **Tunable hyperparameter** | Window during which dopamine can consolidate a pending STDP weight change |
| **sign_constraint** | global | **Config** | Controls sign handling mode: 'hard', 'soft', or 'none' |

### Design principle: fix the structure, learn the function

The connectome tells us **what can connect** (topology) and **with what
sign** (NT identity). These form the scaffold — topology is permanently
fixed, signs are initialized with confidence weighting and constrained
during normal learning.

Learning fills in **how strong** each connection is (w_ij via STDP) and
**how excitable** each neuron is (V_th via homeostasis). These are the
degrees of freedom the real fly brain uses to adapt through experience.

Neuromodulation sits between structure and learning — it doesn't change
the wiring, but it shifts the operating point of the entire network
based on behavioral state. A fly walking vs resting uses the same
circuit with different gain settings.

### Design principle: configurable learning layers

Each learning mechanism is implemented as an independent, toggleable
layer. This lets us run controlled experiments — enable STDP alone, add
homeostasis, add decay, add metaplasticity — and observe the effect of
each mechanism on network behavior.

```
Layer config = {
    'burn_in':          True,   # spontaneous activity bootstrapping
    'stdp':             True,   # spike-timing-dependent plasticity
    'reward_gating':    True,   # dopamine-gated eligibility traces
    'synaptic_decay':   True,   # use-it-or-lose-it weight fade
    'homeostasis':      True,   # firing rate → threshold adjustment
    'metaplasticity':   True,   # per-synapse STDP rate modulation (BCM)
    'arousal':          True,   # neuromodulatory state switching
    'sign_constraint':  'hard', # 'hard' = cannot cross zero (Phase 1–2)
                                # 'soft' = slow drift allowed (Phase 3)
                                # 'none' = unconstrained
}
```

Each layer reads and writes specific parameters (see decision table).
Layers with no dependencies can be toggled independently. Dependencies:

```
reward_gating    requires  stdp
metaplasticity   requires  stdp
synaptic_decay   independent (operates on w_ij directly)
homeostasis      independent (operates on V_th directly)
arousal          independent (operates on effective params)
burn_in          requires  at least stdp + homeostasis
```

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

**sign — confidence-weighted initialization, constrained during normal
learning:** Dale's principle holds at the transmitter level — a neuron
releases the same neurotransmitter at all synapses. But the *effective*
sign of a connection depends on postsynaptic receptor type (e.g.,
nicotinic ACh receptors are excitatory, muscarinic are inhibitory).
The `consensusNt` field provides the transmitter identity, but not all
assignments are high-confidence — some neurons are labeled "unclear."

Initialization uses confidence weighting: high-confidence signs are
initialized far from zero (strong prior), "unclear" neurons are
initialized near zero (weak prior, letting STDP determine the effective
sign from activity).

Phase 1–2 (`sign_constraint: 'hard'`): STDP updates cannot cross zero.
A weight initialized positive stays positive; negative stays negative.
Near-zero "unclear" weights can settle on either side during burn-in
but are then locked. This prevents destabilization during normal
learning and through the dynamics/consolidation phase.

Phase 3 (`sign_constraint: 'soft'`): Slow epigenetic drift (hours–days
timescale) can shift receptor profiles, allowing effective signs to
change. This models postsynaptic receptor switching — the presynaptic
neuron still releases the same transmitter, but the postsynaptic
response can change polarity. See
[under-pressure learning](06-learning-under-pressure.md) section 2b.

**Topology — fixed, never learned:** The physical wiring of the fly's
nervous system is established during development and does not rewire on
the timescales relevant to behavior and learning (seconds to hours).
The adjacency matrix from the connectome is the permanent scaffold.

## Burn-in: bootstrapping the connectome

The imported connectome has adult topology but no activity-shaped
weights — the synapse counts have never been refined by neural activity.
Before any task-driven learning, the model needs a **burn-in period**
to reach a self-consistent baseline.

```
Burn-in protocol:
1. Drive sensory neurons with low-rate Poisson input (~5 Hz)
2. Enable: stdp + homeostasis + synaptic_decay (no reward_gating)
3. Let STDP establish initial correlational structure
4. Let homeostasis find each neuron's operating range
5. Let decay prune spurious weight initializations
6. For sign_constraint 'hard': near-zero "unclear" weights settle
   on a side during burn-in, then lock
7. Run until firing rates stabilize near target rates
8. Snapshot weights and thresholds as the post-burn-in baseline
```

Only after burn-in is the network ready for task-driven learning
(enable reward_gating, present structured stimuli). The burn-in serves
the same function as developmental spontaneous activity in biology —
see [normal learning](04-learning-normal.md) for detailed rationale.

**Configurable:** `burn_in: True/False`. When False, the simulation
starts directly from connectome-initialized weights (useful for testing
or when loading a previously burned-in snapshot).

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

**Phase 2 addition: synaptic scaling.** Threshold adjustment is a
single knob per neuron — it raises or lowers excitability uniformly. In
Phase 2, a second form of homeostasis is added: multiplicative scaling
of all incoming weights. Scaling preserves the relative weight ratios
that STDP learned while adjusting absolute magnitudes, making it less
destructive to learned structure. See
[normal learning](04-learning-normal.md) section 1d for threshold
adjustment, and [memory consolidation](05-learning-memory-consolidation.md)
section 2b for synaptic scaling.

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

**Configurable:** `arousal: True/False`. When False, all effective
parameters equal their base values (tau_m_eff = tau_m_base, etc.).

### Layer 4: Synaptic decay — "use it or lose it" (hours–days)

All synaptic weights decay continuously toward zero. Only active
reinforcement via STDP counteracts the decay:

```
At each timestep:
    w_ij *= (1 - lambda_decay * dt)
```

lambda_decay is small — the time constant is hours to days of simulated
time. A connection that is regularly reinforced by STDP persists; an
unused connection quietly fades.

**Three roles:**
1. **Forgetting** — clears stale associations that are no longer reinforced
2. **Capacity management** — prevents weight saturation over long runs
3. **Noise cleanup** — spurious STDP coincidences are not consistently
   reinforced, so decay removes them

The balance between lambda_decay and STDP learning rate determines how
quickly the network forgets vs retains. This is a tunable hyperparameter.

**Configurable:** `synaptic_decay: True/False`. When False, weights only
change via STDP. Useful for short simulations where saturation isn't a
concern, or for isolating STDP effects during debugging.

**Monitor during simulation: near-zero weight trap.** Under
`sign_constraint: 'hard'`, decay can push weights to near-zero where
they deliver negligible current, making causal pre→post pairings
unlikely, reducing STDP reinforcement, and letting decay pull them
closer to zero — a positive feedback loop toward silence. The weight
is not permanently dead (STDP can still strengthen it from coincidental
timing), but recovery odds worsen the weaker it gets. Homeostasis
(lowering V_th when the postsynaptic neuron goes quiet) and
metaplasticity (maximizing eta for inactive synapses) partially
counteract this, but whether they're sufficient is an empirical
question. Watch for: growing fraction of near-zero weights over time,
especially during long burn-in runs.

See [normal learning](04-learning-normal.md) section 1c for full biological
rationale.

### Layer 5: Metaplasticity — BCM sliding threshold (minutes–hours)

Each synapse tracks its recent modification history and adjusts its
STDP sensitivity. This is the BCM (Bienenstock-Cooper-Munro) mechanism
— the "plasticity of plasticity":

```
theta_m_ij = running average of recent |delta_w_ij| changes

STDP effective learning rate per synapse:
    eta_ij = eta_base * f(theta_m_ij)

where f() decreases when theta_m_ij is high (recently active synapse
is harder to modify further) and increases when theta_m_ij is low
(quiet synapse becomes more plastic).
```

**What it prevents:** Without metaplasticity, STDP tends toward bimodal
weight distributions — strong weights get stronger (more postsynaptic
firing → more causal coincidences → more strengthening), weak weights
get weaker. Metaplasticity counteracts this "rich get richer" dynamic
by making recently strengthened synapses harder to strengthen further.

**Comparison with homeostasis:**
- Homeostasis adjusts the *neuron's* excitability (global, one knob per neuron)
- Metaplasticity adjusts each *synapse's* learning rate (local, one knob per synapse)
- Both are needed: homeostasis for network-level stability, metaplasticity for synapse-level stability

**Configurable:** `metaplasticity: True/False`. When False, all synapses
use the same fixed STDP learning rate. Useful for comparing network
dynamics with and without per-synapse rate modulation.

See [memory consolidation](05-learning-memory-consolidation.md) section 2b
for full biological rationale.

### Layer interaction summary

```
Layer               Operates on          Timescale        Prevents
────────────────────────────────────────────────────────────────────
STDP + reward       w_ij (individual)    seconds          —
Synaptic decay      w_ij (all, uniform)  hours–days       Weight saturation, stale associations
Metaplasticity      eta_ij (per synapse) minutes–hours    Bimodal weight distribution
Homeostasis         V_th (per neuron)    minutes–hours    Runaway excitation / silence
Arousal             tau_m, V_th, V_rest  seconds          — (state switching, not stability)
```

## Implementation reference

Library-agnostic pseudocode for each mechanism. All layers are
independently toggleable via the config flags.

### Layer config

```
config = {
    burn_in:          true/false
    stdp:             true/false
    reward_gating:    true/false    (requires stdp)
    synaptic_decay:   true/false
    homeostasis:      true/false
    metaplasticity:   true/false    (requires stdp)
    arousal:          true/false
    sign_constraint:  'hard' | 'soft' | 'none'
}
```

### Per-neuron state

```
v               — membrane voltage (the simulated variable)
v_th            — homeostatic threshold (adjusted by Layer 2)
rate            — firing rate estimate (smoothed spike count over a
                  sliding window, used by homeostasis only)

Base properties (set from connectome / cell type, fixed during sim):
    tau_m_base, v_rest_base, k_tau, k_vth, k_rest, target_rate

Effective properties (base + modulation, recomputed each step):
    tau_m_eff  = tau_m_base  * (1 - arousal * k_tau)
    v_rest_eff = v_rest_base + modulatory_shift * k_rest
    v_th_eff   = v_th + v_th_base - arousal * k_vth
    (when arousal layer is off: arousal = 0, modulatory_shift = 0)
```

### Per-synapse state

```
w               — synaptic weight (learned)
w_sign          — +1 or -1, from NT identity
w_confidence    — 0.0 (unclear) to 1.0 (high confidence)
eligibility     — STDP eligibility trace, decays with tau_eligibility
theta_m         — metaplasticity: accumulated |Δw| history
```

### Neuron update (each timestep dt)

```
dv/dt = (v_rest_eff - v + R * I) / tau_m_eff

if v >= v_th_eff:
    emit spike
    v = v_rest_base
    enter refractory period (t_refract)
```

### Spike delivery

```
on presynaptic spike (neuron i fires, delivered to synapse i→j):
    I_j += w_ij
    eligibility_ij += A_plus * f(time since last postsynaptic spike)

on postsynaptic spike (neuron j fires, applied to synapse i→j):
    eligibility_ij -= A_minus * f(time since last presynaptic spike)

where f() is an exponential decay with time constant tau_stdp.
```

### Layer 1: Reward-modulated STDP (periodic, every reward_dt)

```
if reward_gating:
    delta_w = dopamine_level * eligibility
else:
    delta_w = eligibility

if metaplasticity:
    eta_scale = 1 / (1 + theta_m)
    delta_w *= eta_scale
    theta_m += |delta_w| - theta_m / tau_meta

w += delta_w

sign constraint enforcement:
    'hard': clamp w to [0, +inf) if w_sign > 0, (-inf, 0] if w_sign < 0
    'soft': allow slow drift across zero (Phase 3, epigenetic timescale)
    'none': unconstrained
```

### Layer 2: Homeostatic threshold (periodic, slower than STDP)

```
dv_th/dt = eta_homeo * (rate - target_rate)
(set eta_homeo = 0 to disable)
```

### Layer 4: Synaptic decay (periodic, every decay_dt)

```
w *= (1 - lambda_decay * decay_dt)
(set lambda_decay = 0 to disable)
```

### Burn-in protocol

```
1. Drive sensory neurons with low-rate random input (~5 Hz Poisson)
2. Enable: stdp + homeostasis + synaptic_decay (no reward_gating)
3. Run until firing rates stabilize near target_rate
4. Snapshot weights and thresholds as post-burn-in baseline
5. Enable reward_gating for task-driven learning
```

## Initialization summary

Concrete initial values for all parameters. For design rationale and
runtime behavior, see the [decision table](#decision-table).

| Parameter | Initial value | Source |
|-----------|--------------|--------|
| **Topology** (i→j) | Adjacency matrix | Connectome (`adj.npy`) |
| **sign(w_ij)** | +1 or −1 per neuron | `consensusNt` → sign map (see below). Motor neurons resolved to −1 (glutamatergic, inhibitory within CNS) |
| **w_confidence** | 0.0–1.0 per neuron | `consensusNt` classification confidence. Motor neurons: high (known glutamatergic). Remaining "unclear": low ≈ 0 |
| **w_ij** | `log(1 + synapse_count) × sign × confidence × scale` | Connectome + confidence weighting |
| **V_th** | Degree-scaled from in-degree | Connectome. Higher in-degree → higher initial threshold |
| **V_rest_base** | −70 mV | Standard *Drosophila* value |
| **V_reset** | −70 mV (= V_rest_base) | Standard |
| **tau_m_base** | Sensory ~5 ms · Intrinsic ~10 ms · Motor ~20 ms | Per superclass |
| **t_refract** | 2 ms | Standard. Caps max firing at ~500 Hz |
| **R** | 1 (dimensionless) | Folded into weight scaling |
| **k_tau, k_vth, k_rest** | Per cell type, defaulting to superclass | Three-level fallback: k_global → superclass multiplier → cell type override. 4,206 slots |
| **target_rate** | Sensory ~50 Hz · Intrinsic ~20 Hz · Motor ~10 Hz | Electrophysiology literature, per superclass |
| **eta_homeo** | Small (TBD) | Tunable. Set to 0 when homeostasis layer disabled |
| **tau_eligibility** | ~1–5 seconds | Dopamine learning literature |
| **lambda_decay** | Small (time constant hours–days, TBD) | Tunable. Set to 0 when synaptic_decay layer disabled |
| **theta_m** | 0.0 per synapse | Starts at zero — accumulates during simulation |
| **tau_meta** | Minutes–hours (TBD) | Tunable |
| **sign_constraint** | `'hard'` (Phase 1) | Config. `'hard'` / `'soft'` / `'none'` |

### Sign map

The preprocessing pipeline resolves `consensusNt` to a per-neuron sign
for all outgoing connections within the CNS:

| consensusNt | Sign | Notes |
|-------------|:----:|-------|
| Acetylcholine | +1 | Dominant excitatory NT in *Drosophila* |
| GABA | −1 | Primary fast inhibition |
| Glutamate | −1 | Inhibitory within the CNS (opposite of vertebrate convention) |
| Glutamate (motor neurons) | −1 | Same rule. The 672 "unclear" motor neurons are glutamatergic — classified "unclear" by the automated pipeline because glutamate is excitatory at the neuromuscular junction (outside the CNS). Within the adjacency matrix all connections are CNS-to-CNS, so the standard CNS convention applies. Confidence set to high |
| Unclear (non-motor) | ±1 | Low confidence, initialized near zero. Sign settles during burn-in |
| Serotonin | 0 | Modulatory — not modeled as a signed synaptic weight |
| Histamine | −1 | Rare in VNC (9 neurons) |

### Motor neuron output

Motor neurons are the final output layer of the SNN. Within the
adjacency matrix, they are ordinary CNS neurons — they receive input
from interneurons and descending neurons, and their glutamatergic
connections to other CNS neurons are inhibitory (sign = −1), same as
any other glutamatergic neuron.

Their effect on muscles is **not** a synapse in the network. The
neuromuscular junction is a separate interface between the SNN and a
body model. When the SNN is connected to a body:

- **Excitatory motor neurons** (glutamatergic): spikes → muscle
  contraction. Glutamate is excitatory at the *Drosophila*
  neuromuscular junction — the opposite of its CNS role.
- **Inhibitory motor neurons** (GABAergic): spikes → muscle relaxation.
  *Drosophila*, like other arthropods, has dedicated inhibitory motor
  neurons that actively relax muscles — unlike vertebrates, where
  muscles relax only when excitatory drive stops.
- **Modulatory motor neurons** (octopaminergic): spikes → adjust muscle
  gain and fatigue properties.

This excitatory/inhibitory distinction at the muscle is a property of
the body model's motor interface, not of the SNN's sign map. The body
model maps each motor neuron's spike output to the appropriate muscle
effect based on its neurotransmitter and target muscle.
