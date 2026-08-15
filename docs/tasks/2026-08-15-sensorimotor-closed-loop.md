---
id: 2026-08-15-sensorimotor-closed-loop
title: "Close the sensorimotor loop: sensory encoding + bidirectional neural-body coupling"
created: 2026-08-15T16:00
status: open
priority: high
type: task
suitability: auto_agent_ready
depends_on:
  - 2026-08-15-sensorimotor-motor-output
related: []
satisfies: []
branch: ""
pr: ""
auto_agent_task_id: ""
---

# Close the sensorimotor loop: sensory encoding + bidirectional neural-body coupling

## Context

Issue 3.1 (motor output adapter) proved we can drive the fly body from neural spikes
(open-loop). This task closes the loop: body sensors feed back into the network as
input currents. The fly now responds to its own movement.

Parent issue: `docs/issues/2026-08-15-sensorimotor-closed-loop.md`

## Problem

The motor output adapter drives the body one-way. The network doesn't know what the
body is doing — it fires the same pattern regardless of body state. Without sensory
feedback, the system can't adapt or react.

## Desired Behavior

1. A `SensoryEncoder` class reads FlyGym body state (joint angles, velocities, contact
   forces) and converts them into input currents for ascending/sensory neurons
2. The closed loop runs: Brian2 produces spikes → motor adapter → FlyGym steps →
   sensory encoder → Brian2 receives currents → repeat
3. A perturbation test proves the loop is closed: externally changing body state →
   changes sensory input → changes neural activity → changes motor output
4. The system runs for ≥2 seconds without crashing or diverging

## Demo

Run `python -m digital_drosophila loop closed_loop` →
1. Closed loop runs for 2 seconds
2. Prints per-step summary: motor rates, sensory input magnitude, body displacement
3. Shows the loop is responsive (neural activity correlates with body state)
4. Saves `reports/closed_loop_traces.png` — time-series of sensory input, motor output,
   and body position showing coupled dynamics

## Key Files

| File | Purpose |
|------|---------|
| `src/digital_drosophila/motor_adapter.py` | Motor output (from Issue 3.1) |
| `src/digital_drosophila/locomotion.py` | FlyGym interface, sensor inventory |
| `src/digital_drosophila/network.py` | Brian2 network builders |
| `src/digital_drosophila/simulate.py` | Existing simulation patterns |

## Suggested Approach

### 1. Sensory encoding

The 100-neuron sample has 15 ascending neurons (superclass='ascending_neuron') —
these are the sensory pathway. Inject current into them proportional to body state:

```python
class SensoryEncoder:
    def __init__(self, ascending_indices, n_actuated=66):
        self.ascending_indices = ascending_indices
        # Map: groups of ascending neurons respond to different signals
        # 15 ascending neurons → distribute across 6 legs + body state
    
    def encode(self, joint_angles, joint_velocities, body_vel):
        """Convert body state to current injection values for ascending neurons."""
        # Normalize signals to [0, 1]
        # Scale to current range (e.g., 0-500 pA)
        # Return array of currents indexed by ascending neuron
        currents = np.zeros(100)  # full network size
        for i, asc_idx in enumerate(self.ascending_indices):
            # Each ascending neuron gets a mix of proprioceptive signals
            signal = joint_angles[i % len(joint_angles)] / np.pi  # normalize
            currents[asc_idx] = signal * 500e-12  # 500 pA max
        return currents
```

### 2. True co-simulation (not two-pass)

Unlike Issue 3.1, this MUST be a true co-simulation — the sensory feedback changes
what the network does next. Use Brian2's incremental `run()`:

```python
from brian2 import Network, ms

# Build the Brian2 network
net = Network(G, S, S_input, S_bg, M)
net.store('initial')

# Co-simulation loop
dt_coupling = 2.0  # ms - coupling timestep
n_coupling_steps = int(2000 / dt_coupling)  # 2 seconds

for step in range(n_coupling_steps):
    # Inject sensory currents into ascending neurons
    G.I[ascending_indices] = sensory_currents
    
    # Run Brian2 for dt_coupling
    net.run(dt_coupling * ms)
    
    # Decode motor spikes from this window
    recent_spikes = get_recent_spikes(M, dt_coupling)
    rates = decoder.update_and_get_rates(recent_spikes)
    
    # Convert to actuator commands
    action = compute_action(rates, neutral_ctrl, mapping)
    
    # Step FlyGym (dt_coupling / flygym_dt steps)
    n_flygym_steps = int(dt_coupling / (model.opt.timestep * 1000))
    for _ in range(n_flygym_steps):
        sim.set_actuator_inputs("nmf", ActuatorType.POSITION, action)
        sim.step()
    
    # Read sensors → encode as currents for next step
    obs = get_observable_state(sim, model, data)
    sensory_currents = encoder.encode(obs)
```

### 3. Brian2 current injection

To inject time-varying current into specific neurons:
```python
# Set the I parameter directly (it's defined in the LIF equations as 'I : amp')
G.I = 0 * pA  # reset all
G.I[ascending_indices] = sensory_currents  # inject into ascending neurons
```

This works because the LIF equation includes `R_membrane * I` — non-zero I drives
membrane potential toward threshold.

### 4. Perturbation test

At t=1.0s, apply a sudden force to the body:
```python
if step == n_coupling_steps // 2:
    data.qvel[0] += 10.0  # sudden forward push (mm/s)
```

Then verify: sensory input spikes → neural activity changes → motor output changes.

## Implementation Approach

- **Artifact type:** New module `src/digital_drosophila/sensory_encoder.py` + update `__main__.py`
- **Extend existing:** Import motor_adapter.py components, locomotion.py FlyGym interface
- **Do not:** Modify motor_adapter.py or locomotion.py, implement learning (that's Epic 4)

## Acceptance Criteria

- [ ] `python -m digital_drosophila loop closed_loop` runs for 2 seconds without error
- [ ] Sensory signals are read from FlyGym each coupling step
- [ ] Sensory signals are encoded as currents injected into ascending neurons
- [ ] The full loop runs: spikes → motor → body → sensors → currents → spikes
- [ ] Perturbation at t=1s produces visible change in neural + motor activity
- [ ] `reports/closed_loop_traces.png` shows coupled dynamics (not flat lines)
- [ ] Runtime < 120 seconds for 2s simulated time

## Notes

- The 100-neuron sample has 15 ascending neurons (indices vary — check superclass)
- Brian2's `Network.run()` can be called incrementally — each call advances by dt
- Between runs, we can modify neuron parameters (like I) and they take effect
- The coupling timestep (2ms) means Brian2 runs 20 steps of 0.1ms per coupling step
- FlyGym timestep is 0.1ms (from locomotion.py), so 20 FlyGym steps per coupling step too
- If performance is too slow, increase coupling timestep to 5ms or 10ms
- The fly won't walk coordinately — reacting to perturbation is sufficient
