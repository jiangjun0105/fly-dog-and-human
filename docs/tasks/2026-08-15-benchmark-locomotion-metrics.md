---
id: 2026-08-15-benchmark-locomotion-metrics
title: "Core locomotion metrics: speed, deviation, stability, energy"
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

# Core locomotion metrics: speed, deviation, stability, energy

## Context

With benchmark infrastructure in place, implement the actual locomotion metrics that
characterize how well the fly moves. These metrics will be used for all controller
comparisons.

## Problem

CoSimulation.get_metrics() only returns forward_distance and mean_motor_rate. We need
richer locomotion characterization: lateral drift, energy cost, gait periodicity, stability.

## Desired Behavior

Given a completed episode from CoSimulation, compute:

1. **Forward speed** — net forward displacement / episode duration (mm/s)
2. **Lateral deviation** — RMS of lateral (Y-axis) position relative to start (mm)
3. **Energy efficiency** — forward distance / sum(|actuator_delta|) (mm per unit effort)
4. **Stance stability** — fraction of timesteps where ≥3 legs have ground contact
5. **Fall indicator** — whether thorax z-position dropped below a threshold
6. **Turn bias** — net heading change over episode (deg/s)
7. **Speed variability** — coefficient of variation of instantaneous speed

## Implementation

Create `src/digital_drosophila/benchmarks/locomotion.py`:

```python
def compute_locomotion_metrics(trajectory_data: dict) -> dict[str, float]:
    """Compute locomotion metrics from episode trajectory.
    
    trajectory_data contains:
        positions: (T, 3) array of thorax CoM positions
        orientations: (T,) heading angles
        leg_contacts: (T, 6) boolean ground contact per leg
        actuator_actions: (T, N_actuators) applied actions
        dt: timestep
    """
    ...
```

The benchmark runner needs to collect this trajectory data during episodes.
Extend CoSimulation (or wrap it) to record per-step:
- Body position (qpos[0:3])
- Body orientation (qpos heading component)
- Leg contact forces (from FlyGym sensor data)
- Actuator commands applied

## Data Collection

Modify the benchmark episode runner to collect trajectory:
```python
trajectory = {"positions": [], "leg_contacts": [], "actuator_actions": []}
while not sim.done:
    sim.step()
    trajectory["positions"].append(sim._data.qpos[0:3].copy())
    trajectory["leg_contacts"].append(get_leg_contacts(sim))
    trajectory["actuator_actions"].append(sim._last_action.copy())
```

## Acceptance Criteria

- [ ] `compute_locomotion_metrics()` returns dict with ≥5 scalar metrics
- [ ] Forward speed matches CoSimulation.get_metrics()["forward_distance_mm"] / duration
- [ ] Stance stability metric in [0, 1] range
- [ ] Energy efficiency is finite and positive for moving fly
- [ ] Metrics work for both neural-driven and CPG-driven episodes
- [ ] Trajectory recording adds <10% overhead to simulation time

## Notes

- FlyGym provides contact forces via `fly.contact_forces` or similar — check flygym API
- Body position is in data.qpos[0:3] (x, y, z of thorax free joint)
- For heading: extract yaw from quaternion in qpos[3:7]
- Leg contacts: threshold on contact force magnitude (> 0.01 N = contact)
- Keep trajectory recording optional (flag) to avoid memory issues in long runs
