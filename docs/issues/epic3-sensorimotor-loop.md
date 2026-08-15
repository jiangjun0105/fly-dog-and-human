# EPIC — Sensorimotor Loop Integration

**EPIC — container, do not execute; work lives in child issues.**

**Parent:** epic-phase1-implementation
**Depends on:** epic1-brian2-network, epic2-mujoco-neuromechfly

## Epic Demo

Run a closed-loop simulation where Brian2 motor neuron spikes drive the FlyGym body,
sensory feedback flows back into the network, and the loop runs for ≥1 second. The fly
visibly twitches in response to its own movement (random is fine — coordinated locomotion
is Epic 4's job).

## Children (value-sliced: skateboard → bicycle → car)

1. **[Skateboard — Motor output adapter + one-way drive](2026-08-15-sensorimotor-motor-output.md)**: Motor neuron spikes → actuator torques → fly twitches (open-loop, no feedback yet)
2. **[Bicycle — Sensory feedback + closed loop](2026-08-15-sensorimotor-closed-loop.md)**: Add sensory encoding, close the loop, fly responds to its own movement
3. **[Car — Co-simulation harness + diagnostics](2026-08-15-sensorimotor-harness.md)**: Proper synchronization, configurable timesteps, time-series visualization, perturbation test

## Dependency Spine

```
Issue 3.1 (motor output) → Issue 3.2 (sensory + closed loop) → Issue 3.3 (harness + diagnostics)
```

Linear — each builds on the previous. 3.1 needs Epic 1 (for the neural network) and
Epic 2 Issue 2.2 (for the motor neuron → actuator mapping).

## Key Design Decisions

- **Spike-to-torque**: Rate coding (spike count in 50ms sliding window × gain → torque magnitude). Simplest and biologically defensible.
- **Sensor-to-current**: Linear scaling with configurable gain. Proprioceptive = continuous; contact = phasic.
- **Synchronization**: Run Brian2 in chunks matching MuJoCo timestep (e.g., 2ms = 20 Brian2 steps of 0.1ms).
- **Motor neuron mapping**: Use the mapping table produced by Epic 2 Issue 2.2 (motor neuron types → FlyGym actuators by leg segment).

## Key References

- `docs/neuroscience/02-lif-model-design.md` — synaptic input model, motor output interface
- `docs/neuroscience/01-connectome-terminology.md` — motor neuron types (702 neurons, 142 types)
- Epic 1 output: running Brian2 network with motor/sensory neuron groups
- Epic 2 Issue 2.2 output: motor mapping table + sensory signal inventory
