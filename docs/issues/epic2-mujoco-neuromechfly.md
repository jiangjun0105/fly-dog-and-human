# EPIC — MuJoCo + NeuroMechFly Environment Setup

**EPIC — container, do not execute; work lives in child issues.**

**Parent:** epic-phase1-implementation

## Epic Demo

Run a script that loads the NeuroMechFly Drosophila model in MuJoCo, applies a scripted
sinusoidal gait, the fly walks forward, and prints the full motor/sensory interface mapping
(actuator names → joints → motor neuron types; sensor names → signal types → vector shapes).

## Children (value-sliced: skateboard → bicycle → car)

1. **[Skateboard — MuJoCo + FlyGym install and hello-world](2026-08-15-mujoco-install-verify.md)**: Install packages, load fly model, step the sim, see it move
2. **[Bicycle — Scripted locomotion + interface characterization](2026-08-15-mujoco-locomotion-interface.md)**: Apply CPG gait, characterize motor/sensory interface, produce mapping tables

## Dependency Spine

```
Issue 2.1 (install + verify) → Issue 2.2 (locomotion + interface mapping)
```

Linear — 2.1 proves the environment works, 2.2 characterizes what Epic 3 needs to connect to.

## Key References

- `docs/neuroscience/01-connectome-terminology.md` — motor neuron types (702 neurons, 142 types)
- `docs/neuroscience/02-lif-model-design.md` — motor output interface
- NeuroMechFly/FlyGym: Lobato-Rios et al. — fly body model for MuJoCo
- `docs/environment-setup.md` — existing setup patterns

## Open Questions

- FlyGym (the successor package to NeuroMechFly) vs raw NeuroMechFly? FlyGym is actively maintained and provides a Gymnasium-compatible API. Recommend: use FlyGym.
- Headless rendering sufficient? Yes for automation; viewer optional for debugging.
- Motor mapping fidelity? Coarse (neuron type → joint group) is sufficient for Epic 3.
