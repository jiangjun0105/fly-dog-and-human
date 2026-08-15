---
id: 2026-08-15-sensorimotor-motor-output
title: "Motor output adapter: Brian2 spikes → FlyGym actuator torques"
created: 2026-08-15T14:30
status: open
priority: medium
type: feature
area:
reporter_side: engineering
need_verify: true
related_issues: ["2026-08-15-mujoco-locomotion-interface"]
related_tasks: []
parent_epic: epic3-sensorimotor-loop
---

# Motor output adapter: Brian2 spikes → FlyGym actuator torques

The skateboard for Epic 3: prove we can translate neural activity into physical
movement. Motor neuron spikes are decoded into torques, the fly twitches. One-way
(open-loop) — no sensory feedback yet.

## Current Behavior

Brian2 network produces motor neuron spikes (from Epic 1). FlyGym body accepts
actuator torques (from Epic 2). Nothing connects them.

## What's Wrong

The neural network and body simulation run independently — there's no bridge.

## Desired Behavior

- A module decodes motor neuron spike trains into actuator torque vectors using
  rate coding (spike count in sliding window × gain)
- The motor neuron type → actuator mapping from Issue 2.2 is used to route
  spikes to the correct joints
- Running the combined system produces visible fly twitching driven by neural activity
- The fly's movement is clearly driven by the network (not scripted) — disabling
  neural input → no movement

## Demo

Run `python -m digital_drosophila loop motor_test` →
1. Brian2 network runs for 2s with burn-in activity
2. Motor neuron spikes are decoded into torques every 2ms
3. FlyGym body steps with those torques
4. Output: video/frames showing the fly twitching + a plot of motor neuron rates vs. resulting joint angles

## Notes

- Rate coding: count spikes in a 50ms sliding window, multiply by gain factor
- Motor mapping comes from Epic 2 Issue 2.2's output (neuron type → actuator)
- This is open-loop — the body moves but doesn't feed back. That's Issue 3.2.
- The fly will twitch randomly/incoherently — that's expected and sufficient.
