# How Our Training Actually Works

A ground-truth reference for the training system as implemented. Not
aspirational — this documents what the code does today, with honest
assessment of where it succeeds and where it falls short.

## 1. The Big Picture (30-second version)

We have a spiking neural network (subset of the Drosophila VNC
connectome) controlling a simulated fly body. The network fires spikes,
spikes drive leg motors, the body moves (or doesn't), and we use the
resulting displacement as a reward signal to strengthen or weaken
synapses via STDP.

```
┌─────────────────────────────────────────────────────────────────┐
│                     One Coupling Step (2 ms)                     │
│                                                                 │
│  ┌──────────┐   spikes    ┌──────────┐   action   ┌──────────┐ │
│  │  Neural  │───────────→ │  Motor   │──────────→ │  Physics │ │
│  │   Sim    │             │  Decode  │            │ (MuJoCo) │ │
│  │ (PyGeNN) │             └──────────┘            └──────────┘ │
│  └──────────┘                                          │       │
│       ↑                                                │       │
│       │              sensory currents                   │       │
│       └────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
                              × 1000 steps = 1 episode (2 s)
                              
After each episode:
  reward = x_final - x_initial   (forward displacement in mm)
  Δw = η × eligibility × (reward - baseline)
  threshold += η_homeo × (firing_rate - target_rate)
  inactive synapses *= (1 - λ)
```

## 2. The Neuron Model

Each neuron is a **Leaky Integrate-and-Fire** (LIF) with adaptive threshold:

```
Membrane:    τ_m × dV/dt = -(V - V_rest) + R × I(t)
Spike:       if V ≥ V_th_adapt → emit spike, V = V_reset, wait t_refract
```

| Parameter | Value | Meaning |
|-----------|-------|---------|
| τ_m | 20 ms | How fast voltage decays without input |
| V_rest | -65 mV | Resting potential (equilibrium) |
| V_th_adapt | starts at -50 mV | Firing threshold (adjusted by homeostasis) |
| V_reset | -65 mV | Voltage after spike |
| R | 100 MΩ | Converts current → voltage |
| t_refract | 2 ms | Dead time after spike |

**What this means intuitively:** each neuron is a leaky bucket. Synaptic
input pours water in, the leak drains it. If the level hits threshold,
the bucket overflows (spike) and is emptied (reset). The threshold moves
up or down based on how often the neuron fires (homeostasis).

## 3. The Network

### Neuron selection

We trace backward from identified **motor neurons** (neurons whose axons
exit through leg nerves, identified via the `exitNerve` column in the
MANC connectome) N hops upstream:

- **1 hop (248 neurons):** motor + immediate premotor interneurons
- **2 hops (398 neurons):** adds pattern generator interneurons
- **3 hops (498 neurons):** adds descending command neurons ← **current best**

### Connectivity

Synapses come directly from the connectome adjacency matrix. For 3-hop:
~23,000 synapses connecting 498 neurons. Each synapse has:
- **Weight (mV):** how much a presynaptic spike changes the postsynaptic voltage
- **Sign:** determined by neurotransmitter identity (Dale's principle — each neuron is either excitatory or inhibitory)

### Initial weights

```python
w_initial = log(1 + synapse_count) × sign × confidence × scale

where:
  synapse_count  = number of individual synaptic contacts (from connectome)
  sign           = +1 (acetylcholine) or -1 (GABA/glutamate) 
  confidence     = neurotransmitter prediction confidence (0-1)
  scale          = 0.6 (excitatory) or 0.3 (inhibitory, attenuated 50%)
```

This is a major assumption: we're using synapse count as a proxy for
connection strength. The log transform prevents high-synapse-count
connections from dominating. The inhibitory attenuation (0.5×) reflects
that inhibitory synapses in biology are typically weaker per contact.

### Background drive

Without the rest of the VNC (~25,000 neurons we're NOT simulating), our
498 neurons lack their normal excitatory context. We compensate with:

- **Tonic background:** 180 pA to all neurons (constant "missing network" current)
- **Descending extra:** +30 pA to descending neurons (simulates brain commands)

This is crude. In biology, descending neurons receive specific patterned
input from the brain. We're replacing that with a constant "go" signal.

## 4. The Coupling Loop (what happens every 2 ms)

Every 2 ms of simulated time, the following happens in sequence:

### Step 1: Neural simulation (GPU, ~0.1 ms wall time)

PyGeNN advances the network by 20 timesteps of 0.1 ms each:
- Each neuron integrates its synaptic input + background current
- Neurons that cross threshold fire spikes
- Spikes propagate through synapses, delivering current to postsynaptic neurons
- STDP traces (Apre, Apost, eligibility) are updated at each spike

### Step 2: Decode motor output (CPU, negligible)

We read which motor neurons spiked, compute a 50-ms sliding-window
firing rate for each motor neuron, then convert to actuator positions:

```python
rate_hz = spike_count_in_50ms_window / 0.050
offset = (rate_hz - 15) / 15 × motor_gain   # centered at 15 Hz baseline
action[actuator] = neutral_position + offset
```

Each motor neuron drives specific actuators on its anatomically correct
leg (from `exitNerve` mapping). Multiple motor neurons targeting the
same actuator have their offsets averaged.

**motor_gain = 0.3** — this means a neuron firing at 30 Hz (double
baseline) produces a +0.3 radian offset. A neuron at 0 Hz produces
-0.3. The range is ±0.3 radians from neutral.

### Step 3: Physics simulation (CPU, ~0.5 ms wall time)

MuJoCo steps the fly body forward by 2 ms (multiple physics substeps).
The actuator positions from step 2 are applied as position targets.
The body responds according to its dynamics, gravity, ground contact, etc.

### Step 4: Encode sensory feedback (CPU, negligible)

We read joint angles and body velocity from MuJoCo, convert them to
currents, and inject them into ascending (sensory) neurons:

```python
sensory_current[ascending_neuron_i] = gain × (joint_angle_deviation + velocity_component)
```

**sensory_gain = 500 pA** — typical sensory current magnitude.

This closes the loop: body state → sensory currents → neural activity →
motor output → body state.

## 5. The Learning Rule (Three-Factor STDP)

This is the core of the system. Learning happens in three stages:

### Stage 1: Mark candidate synapses (during episode, automatic)

Every time a pre- and postsynaptic neuron fire in close temporal
proximity, an **eligibility trace** is created on their shared synapse:

```
When presynaptic neuron fires:
    Apre += 1.0                    # "I just fired" trace
    eligibility += Apost           # if post fired recently, mark this synapse
    V_post += w                    # deliver synaptic current

When postsynaptic neuron fires:
    Apost += 1.0                   # "I just fired" trace  
    eligibility += Apre            # if pre fired recently, mark this synapse

Continuous decay:
    dApre/dt = -Apre / τ_STDP     # traces decay with τ_STDP = 20 ms
    dApost/dt = -Apost / τ_STDP
    d(eligibility)/dt = -eligibility / τ_elig   # eligibility decays with τ_elig = 1 s
```

**What this means:** eligibility is high when pre and post spike close
together in time (within ~40 ms of each other). It decays over 1 second.
By episode end, only recently-active synapses have significant eligibility.

**Critical limitation:** eligibility decays with τ = 1 s, but episodes
last 2 s. Synapses active in the first second have eligibility ≈ e^(-1)
= 37% of their peak by episode end. Synapses active at t=0 have
eligibility ≈ e^(-2) = 13%. Only the last ~1 s of activity effectively
contributes to learning.

### Stage 2: Compute reward (after episode)

```python
reward = x_position_final - x_position_initial   # forward displacement in mm
```

That's it. One scalar number per 2-second episode. Typical values:
- Untrained: ~1.0 mm (passive drift from initial neural activity)
- Best trained (3-hop, η=0.005): ~2.5 mm
- Random controller: ~0.0 mm

### Stage 3: Update weights (after episode)

```python
baseline = mean(last 5 episode rewards)
dopamine = reward - baseline                     # positive = "better than average"
Δw = learning_rate × eligibility × dopamine      # the three-factor update

# Enforce Dale's principle: excitatory weights stay ≥ 0, inhibitory stay ≤ 0
w_new = clip(w_old + Δw, by sign constraint)
```

| Parameter | Value | Role |
|-----------|-------|------|
| learning_rate | 0.001 mV | Step size for weight changes |
| baseline_window | 5 episodes | How many recent rewards to average |
| dopamine | reward - baseline | The "surprise" signal — positive means this episode was better than recent average |

**What the three factors contribute:**
1. **Eligibility** — *which* synapses were active (temporal credit assignment)
2. **Dopamine** — *whether* to strengthen or weaken (reward prediction error)
3. **Learning rate** — *how much* to change (step size)

## 6. Auxiliary Mechanisms

### Homeostatic plasticity (after each episode)

Adjusts firing thresholds to keep neurons near a target rate:

```python
firing_rate = spike_count / episode_length        # Hz
deviation = firing_rate - target_rate             # target = 25 Hz
V_th_adapt += η_homeo × deviation                # raise threshold if firing too much

# Clamped to [-70, -30] mV
```

| η_homeo | Effect |
|---------|--------|
| 0.01 | Too strong — erases STDP improvements faster than reward reinforces them |
| 0.005 | Sweet spot — stabilizes without fighting learning |
| 0.0 | Network becomes unstable (runaway excitation at ~86 Hz) |

**The tension:** homeostasis and STDP fight each other. STDP strengthens
useful synapses → neurons fire more → homeostasis raises thresholds →
neurons fire less → STDP effect is undone. With η=0.01, homeostasis wins.
With η=0.005, they coexist, but homeostasis still erodes gains.

### Synaptic decay (after each episode)

Prunes inactive synapses (those with low eligibility):

```python
inactive = abs(eligibility) < 0.01               # threshold
w[inactive] *= (1 - λ)                           # λ = 0.001 → 0.1% decay per episode

# 50 episodes → inactive synapses lose ~5% of their weight
```

**Purpose:** prevent weight accumulation in unused synapses. But it's
very weak (λ=0.001) and probably does little in 50 episodes.

## 7. The Signal-to-Noise Problem

This is the fundamental challenge of our approach. Consider the
information flow:

```
23,000 synapses (things we're trying to tune)
         ↓
1 scalar reward every 2 seconds (information we get back)
```

The credit assignment problem: which of the 23,000 synapses contributed
to the reward? Eligibility traces help — they narrow it to synapses that
were recently active. But "recently active" still means thousands of
synapses in a 498-neuron network.

**Signal-to-noise estimate:**
- ~23,000 synapses total
- Maybe ~5,000 have significant eligibility at episode end (τ=1s decay)
- Each gets the same dopamine signal
- Useful synapses (ones that actually helped locomotion): maybe ~200-500
- The other 4,500+ get reward/punishment they don't "deserve"

This means roughly **90% of weight updates are noise**. Learning happens
because the 10% signal is consistent across episodes while the 90%
noise averages out — but it averages out slowly.

**Scaling disaster:** For full VNC (4.1M synapses), the signal fraction
drops below 0.01%. This is why full-VNC training shows zero learning.

## 8. What's Working

1. **Functional neuron selection** — 3-hop from motor neurons captures the
   right circuit. Mean reward improves from 1.0 mm to ~1.5 mm.
2. **Homeostatic stability** — η=0.005 keeps the network alive without
   crushing learning.
3. **Consistent improvement direction** — last-10 episodes average 0.934 mm
   improvement, meaning the signal IS getting through the noise.
4. **GPU speedup** — 30× faster than CPU, enabling more experiments.

## 9. What's NOT Working (or Concerning)

### Problem 1: Tiny effect size

Best result: +0.934 mm improvement over 50 episodes. The fly body is
~2.5 mm long. After 50 episodes of training, we've improved locomotion
by less than half a body length per 2-second episode. Untrained passive
drift is already ~1 mm.

**Is this meaningful?** It's statistically real (improving trend) but
biologically trivial. A real fly walks at ~30 mm/s = 60 mm per 2s.
We're at 0.75 mm/s. That's 40× slower than biology.

### Problem 2: The reward signal is impoverished

One scalar every 2 seconds is almost no information. In biology:
- Proprioceptive feedback arrives continuously (every ms)
- Dopaminergic reward signals fire at specific moments
- Motor learning uses error signals, not just scalar success/failure
- Visual/tactile feedback provides rich gradient information

We're trying to learn a 23,000-dimensional weight vector from a binary
signal (good/bad episode). Information theory says this requires
O(23,000) episodes to converge, even with perfect credit assignment.

### Problem 3: No temporal structure in reward

Our reward says "you moved 1.5 mm in 2 seconds" but not "the movement
at t=0.3s was good and the movement at t=1.7s was bad." Eligibility
traces provide some temporal structure, but they're just an exponential
decay — not a precise timing signal.

Continuous reward mode (reward every 2ms) partially addresses this but
introduces noise: per-step displacement is ~0.001 mm, comparable to
simulation jitter.

### Problem 4: No gradient, just direction

STDP gives us the sign of the update (strengthen/weaken) but not the
magnitude. There's no "this synapse needs to be 2.3× stronger" signal
— just "this was active when something good happened, make it slightly
bigger." This is why convergence is so slow compared to gradient-based
methods.

### Problem 5: Homeostasis as an opponent

Every time STDP strengthens useful synapses, homeostasis raises
thresholds to compensate. The network finds a new equilibrium, but
that equilibrium may erase the behavioral improvement. We've tuned
η_homeo to 0.005 (from 0.01) which helps, but the tension remains.

## 10. What We're NOT Doing (from the design doc)

The design doc (02-lif-model-design.md) describes several mechanisms
we haven't implemented:

| Mechanism | Design doc says | Implementation |
|-----------|----------------|----------------|
| Arousal modulation | τ_m, V_th vary with octopamine level | Not implemented — all neurons use fixed τ_m |
| Metaplasticity | Learning rate adapts based on activity history | Not implemented |
| Neuromodulatory shifts | V_rest shifts with dopamine/serotonin | Not implemented |
| Burn-in settling | Extended settling with homeostasis before learning | Partial — 500 ms burn-in, no settling phase |
| Multiple reward signals | Different neuromodulators for different aspects | Single scalar forward-displacement |
| Cell-type-specific k parameters | 4,206 cell types with unique modulation profiles | Uniform parameters across all neurons |

## 11. Summary: Our Position

We have a biologically-grounded spiking network controlling a realistic
fly body, learning from a reward signal. The architecture works — the
closed-loop coupling, neuron selection, motor mapping, and STDP are all
functioning correctly. The network produces behavior, and that behavior
improves with training.

But the improvement is tiny, slow, and may be fundamentally limited by:
1. **Information bottleneck** — 1 scalar / 2s for 23K parameters
2. **No gradient** — STDP is a sign-only update (not magnitude)
3. **Homeostatic opposition** — stability mechanisms fight plasticity
4. **Temporal credit assignment** — 1s eligibility window for a 2s episode

The question isn't whether our implementation is correct (it is — it
matches the design for what we've implemented). The question is whether
reward-modulated STDP with episodic scalar reward can produce meaningful
locomotion at all, or whether we need:
- Richer reward signals (continuous, per-leg, directional)
- Richer learning rules (gradient-based, evolutionary, curriculum)
- Pre-structured dynamics (oscillators, CPG patterns given not learned)
- Or some combination of these

## Appendix A: Parameter Table (All Tunable Values)

| Parameter | Symbol | Value | Location | Effect |
|-----------|--------|-------|----------|--------|
| Membrane time constant | τ_m | 20 ms | LIF params | Integration speed |
| Resting potential | V_rest | -65 mV | LIF params | Equilibrium voltage |
| Initial threshold | V_th | -50 mV | LIF params | Firing threshold (before homeostasis) |
| Reset voltage | V_reset | -65 mV | LIF params | Post-spike voltage |
| Membrane resistance | R | 100 MΩ | LIF params | Current-to-voltage conversion |
| Refractory period | t_refract | 2 ms | LIF params | Minimum inter-spike interval |
| Episode length | - | 2.0 s | Training config | Time per episode |
| Coupling timestep | - | 2.0 ms | Training config | Neural↔physics sync rate |
| STDP time constant | τ_STDP | 20 ms | Training config | Pre/post trace decay |
| Eligibility time constant | τ_elig | 1.0 s | Training config | How long synapses "remember" being active |
| Learning rate | η | 0.001 mV | Training config | Weight update step size |
| Baseline window | - | 5 episodes | Training config | Reward prediction average |
| Homeostatic rate | η_homeo | 0.005 mV/Hz | Training config | Threshold adaptation strength |
| Target firing rate | - | 25 Hz | Training config | Homeostatic set point |
| Synaptic decay rate | λ | 0.001 | Training config | Inactive synapse pruning rate |
| Motor gain | - | 0.3 rad | Training config | Max actuator deflection |
| Sensory gain | - | 500 pA | Training config | Body→neural current scale |
| Background current | - | 180 pA | GPU backend | Missing-network compensation |
| Descending extra current | - | 30 pA | GPU backend | Command signal proxy |
| Inhibitory attenuation | - | 0.5× | Weight init | Inhibitory weight scaling |
| Weight scale | - | 0.6 | Weight init | Overall weight magnitude |
| Hop count | - | 3 | Neuron selection | Upstream tracing depth |
| Neurons (3-hop) | - | 498 | Derived | Network size |
| Synapses (3-hop) | - | ~23,000 | Derived | Parameters to learn |

## Appendix B: One Episode Timeline

```
t = -0.5s:   Burn-in (500 ms, no sensory input, just background current)
             Purpose: let membrane voltages settle to steady state
             
t = 0.0s:    Episode starts, record initial x position
             Sensory feedback loop begins

t = 0.0 to 2.0s:  1000 coupling steps (each 2 ms):
   - PyGeNN runs 20 neural steps (0.1 ms each) → spikes
   - Motor decode: 50-ms windowed rate → actuator position
   - MuJoCo steps physics → body moves (or doesn't)
   - Sensory encode: joint angles + velocity → currents to ascending neurons
   - STDP traces updated at each spike (eligibility accumulates)

t = 2.0s:    Episode ends, record final x position
             reward = x_final - x_initial
             dopamine = reward - mean(last 5 rewards)
             Δw = 0.001 × eligibility × dopamine     ← THE WEIGHT UPDATE
             V_th += 0.005 × (rate - 25)             ← HOMEOSTATIC ADJUSTMENT
             inactive weights *= 0.999               ← SYNAPTIC DECAY

             Then: reset network, reset body, start next episode
```

## Appendix C: What the Numbers Look Like

From the best experiment (3-hop, η_homeo=0.005, 50 episodes):

```
Episode 1:   reward = +1.2 mm, mean rate = 35 Hz, threshold adapting
Episode 10:  reward = +1.8 mm, mean rate = 27 Hz, threshold stabilizing
Episode 25:  reward = +1.4 mm, mean rate = 25 Hz, homeostasis at target
Episode 40:  reward = +2.1 mm, mean rate = 25 Hz
Episode 50:  reward = +1.9 mm, mean rate = 25 Hz

Trend: first-10 avg = 0.7 mm improvement, last-10 avg = 0.93 mm improvement
Weight change: ~0.001 mV per synapse per episode (tiny)
Total weight drift after 50 eps: mean(|Δw|) ≈ 0.01-0.05 mV (still tiny)
```

For comparison, initial weights range from -3 to +4 mV. After 50
episodes of learning, weights have moved by ~1% of their initial value.
