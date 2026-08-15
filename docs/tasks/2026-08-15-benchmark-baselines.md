---
id: 2026-08-15-benchmark-baselines
title: "Baseline controllers: random-weight, zero-weight, CPG wrapper"
created: 2026-08-15T20:00
status: open
priority: high
type: task
suitability: auto_agent_ready
depends_on:
  - 2026-08-15-benchmark-infrastructure
related: []
satisfies:
  - 2026-08-15-benchmark-locomotion
branch: ""
pr: ""
auto_agent_task_id: ""
---

# Baseline controllers: random-weight, zero-weight, CPG wrapper

## Context

Benchmarks are only meaningful with baselines. This task creates the comparison controllers:
networks with randomized or zeroed weights, and a scripted CPG wrapper that uses the same
episode interface.

## Problem

Currently we only have one controller: the biological-weight network. Without controls,
we can't claim any metric reflects topology rather than happenstance.

## Desired Behavior

### Controller Interface

All controllers implement a common protocol usable by BenchmarkRunner:

```python
class Controller(Protocol):
    def reset(self) -> None: ...
    def step(self) -> None: ...
    @property
    def done(self) -> bool: ...
    def get_trajectory_step(self) -> dict: ...
    def get_metrics(self) -> dict: ...
    def close(self) -> None: ...
```

### Baseline Controllers

1. **BiologicalController** — wraps existing CoSimulation (connectome weights)
2. **RandomWeightController** — same network topology, weight magnitudes shuffled
   - Preserve sign constraints (Dale's principle)
   - Same weight distribution (shuffle among same-sign synapses)
   - Same connectivity pattern, same neuron params
3. **ZeroWeightController** — all synaptic weights set to 0 (isolated neurons, only noise)
4. **CPGController** — scripted tripod gait using FlyGym directly (no neural network)
   - Wraps the tripod gait from locomotion.py
   - Provides same step()/get_metrics() API
5. **NoiseController** — random actuator noise each step (null model)

### Implementation

For random/zero weight variants, modify the network building step:
```python
def build_random_weight_network(seed=42):
    """Build network with same topology but shuffled weights."""
    # Build normal constrained network
    # Extract weights, shuffle magnitudes within sign groups
    # Reassign shuffled weights
    ...
```

For CPG controller:
```python
class CPGController:
    """Scripted tripod gait with same episode API as CoSimulation."""
    def __init__(self, episode_length_s=5.0, freq_hz=8.0):
        ...
    def reset(self):
        # Reset FlyGym body
    def step(self):
        # Apply tripod gait pattern
    ...
```

## Key Files

| File | Purpose |
|------|---------|
| `src/digital_drosophila/benchmarks/baselines.py` | All baseline controllers |
| `src/digital_drosophila/benchmarks/common.py` | Controller protocol (extend) |

## Acceptance Criteria

- [ ] All 5 controller types instantiate and run 1 episode without crash
- [ ] RandomWeightController preserves sign constraints (no excitatory→inhibitory flip)
- [ ] ZeroWeightController produces near-zero forward movement (validates metric sensitivity)
- [ ] CPGController produces consistent forward movement matching tripod gait results
- [ ] All controllers work with BenchmarkRunner from Task 5.1.1
- [ ] Controllers are parameterizable (seed for random, freq for CPG)

## Notes

- Random weight controller is the key scientific control for Epic 4.3
- Keep the controller interface minimal — don't add methods that only one controller needs
- CPG controller doesn't need Brian2 at all — it's just FlyGym + sine waves
- Memory: each controller may hold a full Brian2 Network. Ensure proper cleanup via close()
- Seed management: BenchmarkRunner passes seeds to ensure reproducibility
