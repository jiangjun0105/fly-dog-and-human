---
id: 2026-08-15-sensorimotor-motor-output
title: "Motor output adapter: Brian2 motor neuron spikes → FlyGym actuator positions"
created: 2026-08-15T15:30
status: done
priority: high
type: task
suitability: auto_agent_ready
depends_on:
  - 2026-08-15-brian2-biological-constraints
  - 2026-08-15-mujoco-install-verify
related:
  - 2026-08-15-refactor-scripts-to-package
satisfies: []
branch: ""
pr: ""
auto_agent_task_id: ""
---

# Motor output adapter: Brian2 motor neuron spikes → FlyGym actuator positions

## Context

Epic 1 produces a working Brian2 spiking network (100 neurons including 18 motor neurons).
Epic 2 produces a working FlyGym locomotion environment (66 position-controlled actuators).
This task bridges them: decode motor neuron spike trains into actuator position commands.

This is the skateboard for Epic 3 (Sensorimotor Loop) — one-way open-loop: spikes drive
the body, but no sensory feedback yet.

Parent issue: `docs/issues/2026-08-15-sensorimotor-motor-output.md`

## Problem

The neural network and body simulation exist independently. Motor neuron spikes have
no effect on the body. We need a decoder that translates spike trains into physical
movement.

## Desired Behavior

1. A module `src/digital_drosophila/motor_adapter.py` decodes spike trains from the
   Brian2 motor neuron population into FlyGym actuator position commands
2. Rate coding: count spikes in a sliding window → normalize → map to actuator range
3. Motor neurons are mapped to actuators by superclass (all 18 motor neurons in the
   sample drive leg actuators, distributed across the 6 legs)
4. Running the combined system: Brian2 generates activity → adapter decodes → FlyGym
   steps → the fly visibly twitches/moves
5. Disabling neural input → no movement (proves it's neurally driven)

## Demo

Run `python -m digital_drosophila loop motor_test` →
1. Brian2 constrained network runs for 2 seconds
2. Every 2ms (matching FlyGym timestep), motor neuron spikes are decoded into positions
3. FlyGym steps with those positions
4. Output: multi-frame strip showing fly movement + plot of motor neuron rates vs joint angles
5. Prints forward displacement (even random twitching counts)

## Key Files

| File | Purpose |
|------|---------|
| `src/digital_drosophila/simulate.py` | Brian2 constrained network (run_constrained) |
| `src/digital_drosophila/locomotion.py` | FlyGym interface (build_simulation, LEG_OFFSETS, etc.) |
| `src/digital_drosophila/network.py` | Network builders |
| `src/digital_drosophila/plotting.py` | Visualization |

## Suggested Approach

### 1. Motor neuron → Actuator mapping

The 100-neuron sample has 18 motor neurons (indices: [14, 17, 22, 34, 47, 55, 56, 59,
61, 62, 63, 65, 69, 74, 76, 84, 89, 98]). Map them to 6 legs × 3 primary DOFs:

```python
# Simple round-robin assignment: 18 neurons → 6 legs × 3 DOFs (coxa-pitch, femur-pitch, tibia-pitch)
# This is coarse but gives each leg ~3 neurons driving it
MOTOR_NEURON_TO_ACTUATOR = {}
primary_dofs = [0, 3, 5]  # coxa-pitch, femur-pitch, tibia-pitch per leg
for i, mn_idx in enumerate(motor_neuron_indices):
    leg_idx = i % 6  # distribute across legs
    dof_idx = primary_dofs[(i // 6) % 3]
    actuator_idx = LEG_OFFSETS[LEG_NAMES[leg_idx]] + dof_idx
    MOTOR_NEURON_TO_ACTUATOR[mn_idx] = actuator_idx
```

### 2. Spike rate decoding

```python
class SpikeRateDecoder:
    """Decode spike trains into continuous signals using a sliding window."""
    
    def __init__(self, neuron_indices, window_ms=50.0, dt_ms=0.1):
        self.window_size = int(window_ms / dt_ms)
        self.spike_buffer = {idx: deque(maxlen=self.window_size) for idx in neuron_indices}
    
    def update(self, spike_indices, timestep):
        """Record spikes for this timestep."""
        for idx in spike_indices:
            if idx in self.spike_buffer:
                self.spike_buffer[idx].append(1)
        # Advance non-spiking neurons
        for idx in self.spike_buffer:
            if idx not in spike_indices:
                self.spike_buffer[idx].append(0)
    
    def get_rates(self):
        """Get normalized firing rates [0, 1] for each neuron."""
        return {idx: sum(buf) / len(buf) if buf else 0.0
                for idx, buf in self.spike_buffer.items()}
```

### 3. Rate → Position conversion

```python
# Convert normalized rate [0, 1] to position offset from neutral
# Higher firing rate → larger deflection from neutral pose
amplitude = 0.3  # radians max deflection
position_offset = (rate - baseline_rate) * amplitude / max_rate
actuator_command = neutral_ctrl[actuator_idx] + position_offset
```

### 4. Co-simulation loop structure

```python
# Brian2 runs at 0.1ms, FlyGym at 0.1ms (same timestep!)
# But we decode spikes every 2ms (20 Brian2 steps) for smoothness

for mujoco_step in range(n_mujoco_steps):
    # Run Brian2 for 20 steps (2ms)
    brian2_network.run(2*ms)
    
    # Decode motor neuron spikes from the last 2ms
    recent_spikes = spike_monitor.i[spike_monitor.t > current_time - 2*ms]
    decoder.update(recent_spikes)
    rates = decoder.get_rates()
    
    # Convert rates to actuator positions
    action = neutral_ctrl.copy()
    for mn_idx, actuator_idx in mapping.items():
        action[actuator_idx] += (rates[mn_idx] - baseline) * amplitude
    
    # Step FlyGym
    sim.set_actuator_inputs("nmf", ActuatorType.POSITION, action)
    sim.step()
```

### 5. Key challenge: Brian2 simulation timing

Brian2's `run()` advances the whole simulation — we can't easily pause/resume in a
tight loop. Two approaches:

**Option A (recommended for 100 neurons):** Run the full Brian2 simulation first (2s),
record all spikes, then replay them against FlyGym in a second pass. This decouples
the simulations and is simpler to debug.

**Option B (true co-simulation):** Use Brian2's `Network.run()` in small increments.
This works but is slower due to repeated overhead.

Start with Option A. Epic 3 Issue 3.3 will implement the proper co-simulation harness.

## Implementation Approach

- **Artifact type:** New module `src/digital_drosophila/motor_adapter.py` + CLI mode in `__main__.py`
- **Extend existing:** Import from `locomotion.py` (build_simulation, neutral_ctrl, LEG_OFFSETS) and `simulate.py` (run_constrained pattern)
- **Do not:** Implement sensory feedback (that's Issue 3.2), implement true co-simulation (that's Issue 3.3), modify existing modules

## Acceptance Criteria

- [ ] `python -m digital_drosophila loop motor_test` runs without error
- [ ] Brian2 network runs and produces motor neuron spikes
- [ ] Spikes are decoded into actuator positions via rate coding
- [ ] FlyGym body moves driven by neural activity (non-zero displacement)
- [ ] Disabling spikes → no movement (control test)
- [ ] Output includes visualization (frame strip or plot)
- [ ] Runtime < 60 seconds for 2s simulated time

## Notes

- The 100-neuron sample has 18 motor neurons, all with "unclear" neurotransmitter type
  (sign=0 in the constrained network, so they receive but don't transmit strong signals).
  This is fine — they still fire due to input from excitatory descending neurons.
- Motor neurons fire at ~10-25 Hz in the constrained simulation — sufficient for rate coding
- The fly will NOT walk coordinately — random/spastic movement is expected and sufficient
- Position control means we command target angles, not torques — simpler than torque control
- The 2ms decode window (20 Brian2 steps) gives ~100 Hz update rate to FlyGym, smooth enough
