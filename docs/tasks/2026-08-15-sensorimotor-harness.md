---
id: 2026-08-15-sensorimotor-harness
title: "Co-simulation harness with episode API and visualization"
created: 2026-08-15T16:30
status: open
priority: medium
type: task
suitability: auto_agent_ready
depends_on:
  - 2026-08-15-sensorimotor-closed-loop
related: []
satisfies: []
branch: ""
pr: ""
auto_agent_task_id: ""
---

# Co-simulation harness with episode API and visualization

## Context

Issues 3.1 and 3.2 proved the motor output and sensory feedback work. This task wraps
them into a clean `CoSimulation` class with an episode-based API that Epic 4 (learning)
will use as its training environment.

Parent issue: `docs/issues/2026-08-15-sensorimotor-harness.md`

## Problem

The closed loop from Issue 3.2 is functional but hardcoded — no reset, no episode
structure, no metric logging, no easy configuration. Learning experiments need to run
hundreds of episodes with parameter variation.

## Desired Behavior

1. A `CoSimulation` class encapsulates the full neural-body loop
2. Episode API: `reset()` → `step(duration_ms)` → `get_metrics()` → `close()`
3. `reset()` restores body to standing pose and runs neural burn-in
4. Configurable parameters: coupling_dt, amplitude_gain, sensory_gain, episode_length
5. Metrics: forward_distance, mean_motor_rate, mean_sensory_input, energy_cost
6. Visualization: `save_episode_summary(path)` produces traces + frame strip
7. Performance: full episode (2s simulated) in < 60s wall-clock

## Demo

```python
from digital_drosophila.loop import CoSimulation

sim = CoSimulation(episode_length_s=2.0)
sim.reset()
while not sim.done:
    sim.step(coupling_dt_ms=2.0)
metrics = sim.get_metrics()
print(f"Forward: {metrics['forward_distance_mm']:.2f} mm")
sim.save_episode_summary("reports/episode_demo.png")
sim.close()
```

Also: `python -m digital_drosophila loop episode_demo` runs the above.

## Key Files

| File | Purpose |
|------|---------|
| `src/digital_drosophila/motor_adapter.py` | Spike decoding (from 3.1) |
| `src/digital_drosophila/sensory_encoder.py` | Sensory encoding (from 3.2) |
| `src/digital_drosophila/locomotion.py` | FlyGym setup |
| `src/digital_drosophila/network.py` | Brian2 builders |

## Suggested Approach

Create `src/digital_drosophila/loop.py`:

```python
class CoSimulation:
    def __init__(self, episode_length_s=2.0, coupling_dt_ms=2.0,
                 motor_gain=0.3, sensory_gain=500e-12,
                 neural_mode="constrained"):
        self.episode_length_s = episode_length_s
        self.coupling_dt_ms = coupling_dt_ms
        # ... store config
        self._build()
    
    def _build(self):
        """Build both simulators and adapters."""
        # Build Brian2 network
        # Build FlyGym simulation
        # Build motor decoder + sensory encoder
    
    def reset(self):
        """Reset body to standing, run neural burn-in (500ms)."""
        # Reset FlyGym body position
        # Reset Brian2 network state (or rebuild)
        # Run 500ms burn-in with Poisson input only
    
    def step(self, coupling_dt_ms=None):
        """Advance one coupling step."""
        # Inject sensory currents
        # Run Brian2 for coupling_dt
        # Decode motor spikes
        # Step FlyGym
        # Read sensors
        # Log metrics
    
    def get_metrics(self):
        """Return episode metrics dict."""
        return {
            "forward_distance_mm": ...,
            "mean_motor_rate_hz": ...,
            "mean_sensory_input_pa": ...,
            "episode_duration_s": ...,
        }
    
    def save_episode_summary(self, path):
        """Save traces + frame strip."""
```

## Implementation Approach

- **Artifact type:** New module `src/digital_drosophila/loop.py` + CLI mode
- **Extend existing:** Compose motor_adapter + sensory_encoder + locomotion + network
- **Do not:** Reimplement the adapter/encoder logic (import from 3.1/3.2 modules)

## Acceptance Criteria

- [ ] `python -m digital_drosophila loop episode_demo` runs a complete episode
- [ ] `CoSimulation` class has reset/step/get_metrics/close API
- [ ] reset() restores body and runs burn-in
- [ ] get_metrics() returns forward_distance, motor_rate, sensory_input
- [ ] save_episode_summary() produces a readable visualization
- [ ] Can run 2+ episodes sequentially (reset between them)
- [ ] Runtime < 60s per 2s episode
- [ ] Clean importable API: `from digital_drosophila.loop import CoSimulation`

## Notes

- Brian2 Network.store()/restore() can save/load network state for fast reset
- FlyGym body reset: restore initial qpos/qvel from saved state
- The episode API is designed to plug directly into Epic 4's learning loop
- Don't over-engineer — keep it simple enough that learning code can just call step() in a loop
- The `done` property is True when elapsed time >= episode_length_s
