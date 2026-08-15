---
id: 2026-08-15-sensorimotor-closed-loop
title: "Close the sensorimotor loop: sensory feedback + bidirectional flow"
created: 2026-08-15T14:30
status: open
priority: medium
type: feature
area:
reporter_side: engineering
need_verify: true
related_issues: ["2026-08-15-sensorimotor-motor-output"]
related_tasks: []
parent_epic: epic3-sensorimotor-loop
---

# Close the sensorimotor loop: sensory feedback + bidirectional flow

The bicycle for Epic 3: close the loop. Sensory signals from the body (joint angles,
contact forces) are encoded as input currents to sensory neurons. The fly now responds
to its own movement — a true sensorimotor loop.

## Current Behavior

(After Issue 3.1) Motor spikes drive the body one-way. The network doesn't know
what the body is doing.

## What's Wrong

No sensory feedback means the network can't react to body state, can't learn from
consequences of actions, and can't produce adaptive behavior.

## Desired Behavior

- Sensory signals (joint angles, velocities, contact forces) are read from FlyGym
  each timestep
- Signals are normalized and scaled into input currents for sensory neurons
- The sensory → network → motor → body → sensory loop runs continuously for ≥1s
- A perturbation test proves the loop is closed: externally perturb the body →
  observe changed sensory input → observe changed neural activity → observe changed
  motor output

## Demo

Run `python -m digital_drosophila loop closed_loop` →
1. Closed loop runs for 2s simulated time
2. At t=1s, apply an external perturbation (push/force on the body)
3. Output: time-series plot showing perturbation → sensor spike → neural response → motor change
4. The loop is demonstrably closed (not just one-way)

## Notes

- Sensory encoding: linear scaling with configurable gain per signal type
- Proprioceptive signals (joint angles/velocities) are continuous → Poisson rate modulation
- Contact forces (tarsal) are phasic → current pulses on contact events
- Need to identify which neurons in the connectome are sensory (ascending neurons in the VNC)
- Synchronization: Brian2 runs 20 steps of 0.1ms per MuJoCo 2ms step
