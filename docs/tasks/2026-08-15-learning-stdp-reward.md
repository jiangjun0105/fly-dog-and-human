---
id: 2026-08-15-learning-stdp-reward
title: "Reward-modulated STDP: three-factor plasticity on the sensorimotor loop"
created: 2026-08-15T17:00
status: open
priority: high
type: task
suitability: auto_agent_ready
depends_on:
  - 2026-08-15-sensorimotor-harness
related: []
satisfies: []
branch: ""
pr: ""
auto_agent_task_id: ""
---

# Reward-modulated STDP: three-factor plasticity on the sensorimotor loop

## Context

Epic 3 gives us a working closed-loop co-simulation with an episode API (`CoSimulation`).
Now we add plasticity: the network should learn from reward signals to improve its
motor output over episodes.

Parent issue: `docs/issues/2026-08-15-learning-stdp-reward.md`

## Problem

Synaptic weights are fixed — the network produces the same stochastic activity
regardless of behavioral outcome. Without learning, it can never improve.

## Desired Behavior

1. Three-factor STDP implemented in Brian2:
   - Factor 1: Pre-post spike timing (STDP window, causal ~20ms)
   - Factor 2: Eligibility trace (decaying memory of correlations, tau ~1-2s)
   - Factor 3: Reward/dopamine signal (gates actual weight updates)
2. Reward signal: forward velocity from `CoSimulation.get_metrics()`
3. Running 20+ episodes shows measurable improvement in forward distance
4. Weights change in response to reward (not randomly)
5. Hard sign constraint maintained (excitatory stays ≥0, inhibitory stays ≤0)

## Demo

Run `python -m digital_drosophila learn stdp_basic --episodes 20` →
1. Runs 20 episodes of 2s each with STDP active
2. Prints per-episode: forward_distance, mean_motor_rate, weight_change_magnitude
3. Shows learning curve (even if noisy, should have positive trend or at least
   demonstrate weight modulation by reward)
4. Saves `reports/learning_curve.png`

## Key Files

| File | Purpose |
|------|---------|
| `src/digital_drosophila/loop.py` | CoSimulation (from Issue 3.3) |
| `src/digital_drosophila/network.py` | Brian2 builders — modify to add STDP synapses |
| `docs/neuroscience/04-learning-normal.md` | STDP parameters and design |

## Suggested Approach

### 1. STDP synapse model in Brian2

Replace the simple `on_pre="v_post += w"` with a plasticity model:

```python
stdp_eqs = '''
w : volt
deligibility/dt = -eligibility / tau_e : 1 (event-driven)
'''

stdp_pre = '''
v_post += w
eligibility += A_pre * exp(-(t - lastspike_post) / tau_stdp)
'''

stdp_post = '''
eligibility += A_post * exp(-(t - lastspike_pre) / tau_stdp)
'''
```

Actually Brian2 has a specific STDP pattern. The three-factor approach:

```python
# Eligibility trace accumulates STDP-like correlations
# Dopamine/reward signal gates weight updates

synapse_eqs = '''
w : volt
deligibility/dt = -eligibility / tau_eligibility : 1 (clock-driven)
dApre/dt = -Apre / tau_stdp : 1 (event-driven)
dApost/dt = -Apost / tau_stdp : 1 (event-driven)
'''

on_pre = '''
v_post += w
Apre += delta_Apre
eligibility += Apost  # post before pre → depression
'''

on_post = '''
Apost += delta_Apost
eligibility += Apre  # pre before post → potentiation
'''

# Weight update (applied periodically, not per-spike):
# dw = learning_rate * eligibility * dopamine_signal
# Applied at end of each coupling step or episode
```

### 2. Parameters (from doc 04)

- `tau_stdp = 20 * ms` — STDP window
- `tau_eligibility = 1 * second` — eligibility trace decay
- `learning_rate = 0.01 * mV` — weight change per update
- `delta_Apre = 0.01` — pre-spike trace amplitude
- `delta_Apost = -0.01 * 1.05` — post-spike trace (slightly asymmetric for LTD)

### 3. Reward computation

```python
# After each episode:
metrics = sim.get_metrics()
reward = metrics["forward_distance_mm"]  # simple: more forward = more reward
baseline_reward = running_mean(rewards)  # subtract baseline for variance reduction
dopamine = reward - baseline_reward  # positive = reinforce, negative = punish
```

### 4. Weight update

```python
# At end of each episode, update weights:
for syn in plastic_synapses:
    dw = learning_rate * syn.eligibility * dopamine
    syn.w += dw
    # Enforce sign constraint
    syn.w = clip(syn.w, min=0) if excitatory else clip(syn.w, max=0)
```

### 5. Integration with CoSimulation

Modify or subclass `CoSimulation` to:
- Use STDP synapse model instead of static synapses
- Expose eligibility traces for weight updates
- Accept dopamine signal after each episode

Or create a `LearningLoop` class that wraps CoSimulation:
```python
class LearningLoop:
    def __init__(self, n_episodes=20, ...):
        self.sim = CoSimulation(...)  # with STDP synapses
    
    def train(self):
        for ep in range(self.n_episodes):
            self.sim.reset()
            while not self.sim.done:
                self.sim.step()
            reward = self.sim.get_metrics()["forward_distance_mm"]
            self._update_weights(reward)
```

## Implementation Approach

- **Artifact type:** New module `src/digital_drosophila/learning.py` + CLI mode
- **Extend existing:** May need to modify `network.py` to support STDP synapse creation, or create network variant
- **Do not:** Implement homeostatic plasticity (that's Issue 4.2), change the body model

## Acceptance Criteria

- [ ] `python -m digital_drosophila learn stdp_basic --episodes 20` runs
- [ ] Three-factor STDP model works (eligibility traces accumulate, reward gates updates)
- [ ] Weights change after each episode (weight delta is non-zero)
- [ ] Sign constraint maintained (excitatory ≥ 0, inhibitory ≤ 0)
- [ ] Learning curve plot saved to `reports/learning_curve.png`
- [ ] Multiple episodes run sequentially without crash
- [ ] Some trend visible in forward distance (even noisy improvement counts)

## Notes

- Brian2 STDP is well-documented — look at Brian2 examples for the standard pattern
- Three-factor = standard STDP + eligibility trace + reward modulation
- The "unclear" motor neurons (sign=0) have zero weights — they WON'T learn. That's OK.
  Learning happens in the excitatory/inhibitory pathways that DRIVE motor neurons.
- Don't expect clean learning in 20 episodes — even noisy improvement or demonstrated
  weight modulation is sufficient for this skateboard.
- If the simulation is too slow for 20 episodes, reduce episode_length to 1s.
- The closed-loop sim takes ~100s per 2s episode. 20 episodes = ~33 minutes.
  Consider reducing episode length to 1s (50s each, 20 episodes = ~17 min).
