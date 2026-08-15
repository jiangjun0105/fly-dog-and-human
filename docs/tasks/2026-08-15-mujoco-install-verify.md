---
id: 2026-08-15-mujoco-install-verify
title: "Install MuJoCo + FlyGym and verify Drosophila model loads"
created: 2026-08-15T14:00
status: open
priority: high
type: task
suitability: auto_agent_ready
depends_on: []
related: []
satisfies: []
branch: ""
pr: ""
auto_agent_task_id: ""
---

# Install MuJoCo + FlyGym and verify Drosophila model loads

## Context

Epic 2 (MuJoCo + NeuroMechFly) is the "body" side of the sensorimotor loop. This
skateboard task proves the physics engine installs, the fly body model loads, and we
can step and render headlessly. Nothing fancy — just "packages install, model loads,
simulation steps without crashing."

Parent issue: `docs/issues/2026-08-15-mujoco-install-verify.md`

## Problem

MuJoCo, FlyGym, and gymnasium are not installed. We have no physics simulation capability.
Epic 3 (sensorimotor loop) needs this as a prerequisite.

## Desired Behavior

1. `flygym` and `mujoco` packages install successfully via `uv pip install flygym`
2. A module `src/digital_drosophila/body.py` loads the NeuroMechFly/FlyGym Drosophila model
3. The simulation steps for 1000 timesteps without error
4. The module prints the model's joint names, actuator names, and sensor names
5. A headless render produces a single frame PNG showing the fly model
6. Invocable as `python -m digital_drosophila body verify`

## Demo

```bash
python -m digital_drosophila body verify
```
→ loads the FlyGym fly model, steps 1000 timesteps (< 5 seconds), prints joint/actuator/sensor
lists, saves a single-frame render to `reports/flygym_hello.png`. The fly is visible in the image.

## Key Files

| File | Purpose |
|------|---------|
| `src/digital_drosophila/__main__.py` | CLI dispatcher — add `body` subcommand |
| `src/digital_drosophila/body.py` | NEW — FlyGym/MuJoCo interface module |
| `pyproject.toml` | Add `flygym` to dependencies |
| `docs/issues/2026-08-15-mujoco-install-verify.md` | Parent issue spec |

## Suggested Approach

### 1. Install FlyGym

Add to `pyproject.toml` dependencies:
```toml
"flygym>=1.0",
```

Then run `uv pip install -e .` to install with the new dependency. FlyGym pulls
`mujoco` and `gymnasium` automatically.

### 2. Set headless rendering

This server has EGL available (`libegl1` installed). Set the environment variable:
```python
import os
os.environ["MUJOCO_GL"] = "egl"
```
This must be set BEFORE importing mujoco or flygym.

If EGL fails, fall back to:
```python
os.environ["MUJOCO_GL"] = "osmesa"
```

### 3. Create `src/digital_drosophila/body.py`

```python
"""FlyGym/MuJoCo interface for the Drosophila body model."""

import os
os.environ.setdefault("MUJOCO_GL", "egl")

from pathlib import Path
import numpy as np

def verify_installation():
    """Load fly model, step simulation, render a frame."""
    from flygym import NeuroMechFly
    
    sim = NeuroMechFly()
    
    # Print model interface
    print("Joint names:", sim.joint_names)
    print("Actuator names:", sim.actuator_names)  
    print("Sensor names:", sim.sensor_names)
    
    # Step 1000 timesteps
    for _ in range(1000):
        action = np.zeros(sim.action_space.shape)
        obs, reward, terminated, truncated, info = sim.step(action)
    
    # Render single frame
    img = sim.render()
    
    # Save
    reports_dir = Path(__file__).resolve().parent.parent.parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.imsave(reports_dir / "flygym_hello.png", img)
    print(f"Saved: {reports_dir / 'flygym_hello.png'}")
    
    sim.close()
```

**NOTE:** The exact FlyGym API (class name, method signatures, attribute names) may
differ from this sketch. The implementer MUST check `flygym`'s actual API:
- Try `from flygym import Fly, Camera, SingleFlySimulation` (newer API)
- Or `from flygym import NeuroMechFly` (older API)
- Check `dir()` on the simulation object to find joint/actuator/sensor attributes
- The render method might be `sim.render()` or require a Camera object

### 4. Extend `__main__.py`

Add a `body` subcommand to the CLI dispatcher that calls `verify_installation()`.

### Key constraints

- **Set MUJOCO_GL before any mujoco import** — this is critical for headless rendering
- **Don't hardcode the FlyGym API** — inspect the actual installed package, as the API
  has changed between versions. Use `dir()` and `help()` to find the right attributes.
- **Keep it simple** — this is a hello-world, not a full interface. Just prove it works.
- **Follow the package pattern** — code in `src/digital_drosophila/body.py`, entry via `__main__.py`

## Implementation Approach

- **Artifact type:** New module (`src/digital_drosophila/body.py`) + pyproject.toml update
- **Extend existing:** Add to the `__main__.py` CLI dispatcher pattern
- **Do not:** Create scripts in `scripts/`, over-engineer the interface, implement locomotion (that's Issue 2.2)

## Acceptance Criteria

- [ ] `flygym` installs without error (added to pyproject.toml, `uv pip install -e .` succeeds)
- [ ] `python -m digital_drosophila body verify` runs without error
- [ ] Output prints joint names, actuator names, and sensor names
- [ ] Simulation steps 1000 timesteps without crash
- [ ] `reports/flygym_hello.png` is produced and contains a visible fly model (file > 10KB)
- [ ] Total runtime < 30 seconds

## Notes

- EGL is available on this server (`libegl1` confirmed installed)
- If `MUJOCO_GL=egl` fails, try `osmesa`. If both fail, document the error — this becomes a `needs_human` blocker.
- FlyGym bundles the MJCF model — no separate download needed
- The FlyGym API may have changed between versions. The implementer should adapt to whatever `pip install flygym` gives. The key deliverable is "it works", not "it matches this exact API sketch."
- This is the prerequisite for Issue 2.2 (scripted locomotion + interface characterization)
