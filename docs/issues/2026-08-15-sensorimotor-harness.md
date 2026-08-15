---
id: 2026-08-15-sensorimotor-harness
title: "Co-simulation harness with diagnostics and visualization"
created: 2026-08-15T14:30
status: open
priority: medium
type: feature
area:
reporter_side: engineering
need_verify: true
related_issues: ["2026-08-15-sensorimotor-closed-loop"]
related_tasks: []
parent_epic: epic3-sensorimotor-loop
---

# Co-simulation harness with diagnostics and visualization

The car for Epic 3: a production-quality co-simulation harness with configurable
parameters, proper logging, diagnostics, and visualization. This is what Epic 4
(learning) will use as its training environment.

## Current Behavior

(After Issue 3.2) The closed loop works but is hardcoded — fixed timesteps, no
logging, no easy way to vary parameters or visualize what's happening.

## What's Wrong

Learning experiments (Epic 4) need: configurable episode length, reset-to-initial,
reward extraction, metric logging, and the ability to run many episodes efficiently.
The hardcoded loop from 3.2 doesn't support this.

## Desired Behavior

- A `CoSimulation` class that encapsulates the full loop with configurable parameters
- Episode API: `reset()`, `step(duration)`, `get_reward()`, `get_metrics()`
- Configurable: Brian2 dt, MuJoCo dt, spike-to-torque gain, sensor-to-current gain
- Logging: per-step metrics (firing rates, torques, sensor values, body state)
- Visualization: produce time-series plots and video from a completed episode
- Performance: full loop runs at ≥10× realtime for the 100-neuron sample

## Demo

```python
from digital_drosophila.loop import CoSimulation

sim = CoSimulation(neural_mode="constrained", episode_length=5.0)
sim.reset()
metrics = sim.run_episode()
print(f"Forward distance: {metrics.forward_distance:.2f}mm")
print(f"Mean motor rate: {metrics.mean_motor_rate:.1f} Hz")
sim.save_video("reports/episode_0.mp4")
sim.plot_timeseries("reports/episode_0_traces.png")
```

## Notes

- This is the "gym environment" that Epic 4's learning rules interact with
- The `get_reward()` API extracts forward velocity from MuJoCo body state
- `reset()` resets body to standing pose and runs neural burn-in
- Performance target assumes CPU Brian2 on 100-neuron sample; full-scale (15k on GeNN) is separate
- Consider Gymnasium-compatible interface for future RL baselines (optional)
