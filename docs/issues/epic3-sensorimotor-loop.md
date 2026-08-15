# Sensorimotor Loop Integration (Walking Skeleton)

**Parent:** epic-phase1-implementation
**Depends on:** child1-brian2-network, child2-mujoco-neuromechfly

## Desired Behavior

Bridge the Brian2 neural network to the MuJoCo body so that neural activity drives movement and
body sensors feed back into the network. This is the first end-to-end vertical: a complete
closed-loop simulation, even if the behavior is random/uncoordinated.

### Demo

Run a simulation that:
1. Brian2 network runs (with burn-in activity or sensory-driven input)
2. Motor neuron spikes are decoded into actuator torques via a rate-code adapter
3. MuJoCo steps the body with those torques
4. Sensory signals (joint angles, contact forces) are encoded as currents into sensory neurons
5. Loop runs for ≥1 second of simulated time
6. Output: video of the fly twitching/moving (even randomly), plus a time-series plot showing the closed loop (motor spikes → torques → movement → sensor signals → sensory currents)

The fly does NOT need to walk — just demonstrably respond to its own movement. Random twitching
driven by the closed loop is a successful demo.

### Tasks (estimated)

1. **Motor output adapter** — Convert motor neuron spike trains to actuator torques. Strategy: sliding-window spike rate (e.g., 50ms window) × gain factor → torque. Map motor neuron groups to actuators using Child 2's mapping table (~2 tasks)
2. **Sensory input adapter** — Convert MuJoCo sensor readings to Brian2 input currents. Strategy: normalize sensor values → scale to current range → inject into sensory NeuronGroup via `TimedArray` or direct current injection each MuJoCo step (~2 tasks)
3. **Timestep synchronization** — Brian2 runs at ~0.1ms; MuJoCo at ~1-2ms. Design the co-simulation loop: run Brian2 for N steps, collect spikes, compute torques, step MuJoCo, read sensors, inject currents, repeat. Handle the clock mismatch cleanly (~1-2 tasks)
4. **Co-simulation harness** — Single script/class that orchestrates the loop: init both sims, run the co-simulation for T seconds, collect logs (~1 task)
5. **Smoke test & visualization** — Run for 1s, produce video + time-series plot. Verify the loop is closed (perturbation in body → change in sensory input → change in network activity → change in motor output). Document any tuning needed (~1-2 tasks)

### Key Design Decisions

- **Spike-to-torque conversion**: Rate coding (spike count in window → torque magnitude) is simplest and biologically defensible for motor output. Alternative: precise spike timing → force pulses (more realistic but harder to debug).
- **Sensor-to-current conversion**: Linear scaling with configurable gain. Proprioceptive signals are continuous; contact signals are binary/phasic.
- **Synchronization granularity**: Run Brian2 in chunks matching MuJoCo timestep (e.g., 2ms = 20 Brian2 steps of 0.1ms). This is the simplest correct approach.

### Key References

- `docs/neuroscience/02-lif-model-design.md` — synaptic input model (delta functions)
- `docs/step1-plan.md` — mentions the integration goal
- Child 1 output: running Brian2 network with motor/sensory neuron groups identified
- Child 2 output: motor mapping table + sensory signal list
