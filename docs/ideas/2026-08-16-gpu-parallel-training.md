# Idea: GPU-Parallel Training Architectures

**Status:** Proposed  
**Date:** 2026-08-16  
**Motivation:** Current training is bottlenecked by CPU-side MuJoCo physics (~7-8s/episode even with GPU neural sim). Need faster iteration for longer/larger experiments.

## The Problem

The coupling loop runs ~500 steps per second of simulated time:
1. PyGeNN steps neural network (20 × 0.1ms) → GPU, ~0.1ms
2. Decode spike rates → actuator positions → CPU, Python
3. MuJoCo steps physics → CPU, ~0.5ms
4. Read body state → sensory currents → CPU, Python
5. Feed currents back to PyGeNN → GPU transfer

The neural sim is near-instant on GPU. The bottleneck is the tight CPU↔GPU round-trip
and CPU-bound MuJoCo physics. GPU utilization reads ~0% because the network is too small
to saturate it.

## Proposed Approaches

### Approach A: Mini-batch STDP (parallel evaluation, sequential updates)

Run K flies simultaneously with the same starting weights. Each gets a different random
initial state, produces a different trajectory, gets a different reward. Average the K
weight updates:

```
Batch 1: weights_0 → run 8 parallel episodes → average Δw → weights_1
Batch 2: weights_1 → run 8 parallel episodes → average Δw → weights_2
```

50 episodes ÷ 8 per batch = ~6 sequential update steps instead of 50.

**Requires:** MJX (MuJoCo XLA) for parallel physics + JAX neural network (replaces Brian2/PyGeNN)
**Pros:** Variance reduction (averaging 8 rewards), massive speedup (~8×)
**Cons:** Fewer update steps, requires full rewrite in JAX, less granular learning

### Approach B: Population-based / Evolutionary

No STDP. Maintain a population of N weight configurations. Run all N in parallel. Keep the
top performers, mutate to make new population. Repeat.

**Requires:** MJX for parallel physics, no neural sim framework needed (just matrix ops in JAX)
**Pros:** Fully parallel — no sequential dependency. Can escape local optima.
**Cons:** Replaces STDP entirely (abandons biological plausibility goal). Needs large population
for high-dimensional weight space (~1000+ synapses).

### Approach C: Continuous reward (no batching needed)

Don't batch — instead, make single-episode learning much richer. Replace the scalar
end-of-episode reward with **instantaneous velocity** as the reward signal at every coupling
step (every 2ms). STDP eligibility traces get reinforced continuously, not once per 2s.

**Requires:** Minor code change (reward_signal = current_velocity instead of episode_total_displacement)
**Pros:** Solves credit assignment (reward is immediate, not delayed 2s). No architecture change.
**Cons:** Instantaneous velocity is noisy. May reinforce random twitches that happen to move forward.

## Trade-offs

| Approach | Speedup | Architecture change | Biological plausibility |
|----------|---------|-------------------|------------------------|
| A (mini-batch) | ~8× | Major (JAX rewrite) | Moderate (still STDP) |
| B (evolutionary) | ~50× | Major (JAX rewrite) | Low (not bio-learning) |
| C (continuous reward) | 1× speed, ~50× learning efficiency | Minor | High (neuromodulation) |

## Intermediate Finding (2026-08-16)

Tested Approach C (continuous reward every 2ms, 3-hop, η=0.005):
- Shows learning (+0.533mm last-10) but weaker than episodic (+0.934mm last-10)
- Per-step displacement (~0.001mm) is too noisy for clean credit assignment
- EMA baseline (α=0.01) too slow to track rapidly varying micro-displacements
- Needs: larger update interval (500ms?), sliding-window velocity, learning rate sweep
- Not a dead end — needs hyperparameter work to beat episodic

## Recommendation

Episodic reward (end-of-episode) currently outperforms continuous with default params.
Approach C needs tuning before it can replace episodic. The key insight: per-step
displacement is too noisy at 2ms granularity. A 100-500ms sliding window average velocity
might be the right middle ground between episodic (2s) and instantaneous (2ms).

For speedup, Approach A (batched MJX) remains the architectural investment for future
large-scale experiments. Approach B is the fallback if STDP fundamentally can't scale.
