---
id: 2026-08-15-mujoco-locomotion-interface
title: "Scripted fly locomotion + motor/sensory interface characterization"
created: 2026-08-15T12:01
status: open
priority: medium
type: feature
area:
reporter_side: engineering
need_verify: true
related_issues: ["2026-08-15-mujoco-install-verify"]
related_tasks: []
parent_epic: epic2-mujoco-neuromechfly
---

# Scripted fly locomotion + motor/sensory interface characterization

Thicken the MuJoCo skateboard: make the fly walk with a scripted CPG gait, and
document the full motor/sensory interface that Epic 3 will connect the neural
network to.

## Current Behavior

(After Issue 2.1) MuJoCo/FlyGym installed and verified — model loads and steps.
But we don't know which actuators move which joints, what sensors are available,
or how to make the fly actually walk.

## What's Wrong

Epic 3 (sensorimotor loop) needs to know: "when motor neuron X fires, which
actuator should receive torque?" and "what sensor signals feed back to sensory
neurons?" We don't have this mapping yet.

## Desired Behavior

- A script applies sinusoidal CPG-like torques to the fly's leg actuators and the
  fly moves forward (even if the gait is crude)
- The script produces a mapping table: actuator_name → joint → leg → degrees_of_freedom
- The script documents all available sensor signals: joint angles, joint velocities,
  contact forces (tarsal), body position/velocity/orientation
- Output includes the vector shapes (how many dimensions each signal has)
- A coarse mapping from connectome motor neuron types to FlyGym actuators is proposed
  (doesn't need to be perfect — just good enough for Epic 3)

## Demo

Run `python scripts/flygym_locomotion.py` → applies sinusoidal gait for 2 seconds,
saves a video or multi-frame PNG strip showing the fly walking, prints:
(1) actuator mapping table,
(2) sensor signal inventory with shapes,
(3) proposed motor_neuron_type → actuator mapping (first draft).
The fly visibly moves forward in the output.

## Notes

- FlyGym may have built-in locomotion examples or a pre-tuned CPG — use those if available
- The motor neuron → actuator mapping is coarse at this stage: map by leg segment
  (coxa, trochanter, femur, tibia, tarsus) and leg identity (L1/R1/L2/R2/L3/R3)
- There are 702 motor neurons with 142 unique types in the connectome — we only need
  to map the types, not individual neurons
- Sensory interface should document: what's the observation space shape? What units?
  What range? This is what Epic 3 will scale into input currents for sensory neurons
- Reference: `docs/neuroscience/01-connectome-terminology.md` for motor neuron types
