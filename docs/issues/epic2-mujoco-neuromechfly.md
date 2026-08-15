# MuJoCo + NeuroMechFly Environment Setup

**Parent:** epic-phase1-implementation

## Desired Behavior

Install MuJoCo and NeuroMechFly, verify the Drosophila body model runs, and characterize the
motor/sensory interface so we know exactly how to connect the neural network.

### Demo

Run a script that:
1. Loads the NeuroMechFly Drosophila model in MuJoCo
2. Applies a scripted sinusoidal torque pattern to leg actuators
3. The fly performs a simple gait (even if crude/hardcoded)
4. Prints a mapping table: motor neuron type → actuator name → joint
5. Prints available sensory signals: joint angles, contact forces, body velocity

### Tasks (estimated)

1. **MuJoCo installation** — Install MuJoCo (pip install mujoco), verify with a minimal headless render test (~1 task)
2. **NeuroMechFly installation** — Install NeuroMechFly package, load the Drosophila MJCF model, verify it renders/steps without error (~1 task)
3. **Scripted locomotion test** — Apply sinusoidal joint torques (CPG-like pattern) to all 6 legs, run simulation, verify the body moves forward. Record video or screenshot as evidence (~1-2 tasks)
4. **Motor interface characterization** — Document the full mapping from NeuroMechFly actuator names to anatomical joints. Cross-reference with the 702 motor neurons (142 unique types) from the connectome. Produce a mapping table: `motor_neuron_type → actuator(s)` (~2 tasks)
5. **Sensory interface characterization** — Document all sensor outputs NeuroMechFly provides: proprioception (joint angles/velocities), contact sensors (tarsal ground contact), body state (position, velocity, orientation). Define the input vector shape for the neural network (~1 task)

### Key References

- `docs/neuroscience/01-connectome-terminology.md` — motor neuron types (702 neurons, 142 types)
- `docs/neuroscience/02-lif-model-design.md` — discusses motor output interface
- NeuroMechFly paper: Lobato-Rios et al. (2022) — fly body model for MuJoCo
- `docs/environment-setup.md` — existing environment setup patterns

### Open Questions

- NeuroMechFly v1 or v2? v2 has more actuators and better sensor models. Recommend: check latest release.
- Headless rendering sufficient or do we need a viewer? Recommend: headless for CI/automation, viewer optional for debugging.
- Degree of motor neuron → actuator mapping fidelity at this stage? Recommend: coarse mapping (neuron type → joint group) is sufficient for Child 3; refine in Child 4 if needed.
