---
id: 2026-08-15-mujoco-install-verify
title: "Install MuJoCo + FlyGym and verify Drosophila model loads"
created: 2026-08-15T12:00
status: open
priority: high
type: feature
area:
reporter_side: engineering
need_verify: true
related_issues: []
related_tasks: []
parent_epic: epic2-mujoco-neuromechfly
---

# Install MuJoCo + FlyGym and verify Drosophila model loads

The skateboard for Epic 2: prove we can install the physics engine, load the
Drosophila body model, and step the simulation. Nothing fancy — just "packages
install, model loads, simulation steps without crashing."

## Current Behavior

MuJoCo, FlyGym, and NeuroMechFly are not installed. We have no physics simulation
capability.

## What's Wrong

Can't simulate the fly body — needed for the sensorimotor loop (Epic 3).

## Desired Behavior

- `mujoco` and `flygym` packages install successfully via pip/uv
- A script loads the NeuroMechFly/FlyGym Drosophila model
- The simulation steps for 1000 timesteps without error
- The script prints the model's joint names, actuator names, and sensor names
- A headless render produces a single frame PNG showing the fly model

## Demo

Run `python scripts/verify_mujoco.py` → installs confirmed, loads the fly MJCF model,
steps 1000 timesteps (takes < 5 seconds), prints joint/actuator/sensor lists, saves a
single-frame render to `reports/flygym_hello.png`. The fly is visible in the image.

## Notes

- FlyGym (https://github.com/NeLy-EPFL/flygym) is the maintained successor to NeuroMechFly
- It provides a Gymnasium-compatible interface and includes the MJCF model
- Install: `pip install flygym` (pulls mujoco as a dependency)
- Headless rendering: may need `MUJOCO_GL=osmesa` or `egl` on this headless server
- If FlyGym doesn't work, fallback: raw `mujoco` + download the MJCF from the NeuroMechFly repo
