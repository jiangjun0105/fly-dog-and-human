# EPIC — Digital Drosophila Phase 1: From Connectome Data to Learning Locomotion

**EPIC — container, do not execute; work lives in child epics.**

## Capability List

Take the existing connectome data and complete design docs and produce a running simulation
where a biologically-constrained spiking neural network controls a Drosophila body model and
learns locomotion through localized learning rules.

## Child Epics

1. **[Epic 1: Brian2 Neural Network](epic1-brian2-network.md)** — translate VNC connectome into a running spiking network
2. **[Epic 2: MuJoCo + NeuroMechFly](epic2-mujoco-neuromechfly.md)** — install and verify the physics/body environment
3. **[Epic 3: Sensorimotor Loop](epic3-sensorimotor-loop.md)** — bridge neural network to body (walking skeleton)
4. **[Epic 4: Learning & Locomotion](epic4-learning-locomotion.md)** — implement learning rules, run experiments

## Dependency Spine

```
Epic 1 (Brian2 model) ──┐
                         ├──▶ Epic 3 (Integration) ──▶ Epic 4 (Learning)
Epic 2 (MuJoCo setup) ──┘
```

Epics 1 and 2 are parallelizable. Epic 3 is the first end-to-end value. Epic 4 answers the research question.
