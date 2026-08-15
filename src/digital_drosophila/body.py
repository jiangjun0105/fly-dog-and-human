"""FlyGym/MuJoCo interface for the Drosophila body model.

Loads the NeuroMechFly model, adds joints and actuators, steps the
simulation, and renders a headless frame to verify the physics pipeline.
"""

import os

os.environ.setdefault("MUJOCO_GL", "egl")

import time
from pathlib import Path

import numpy as np


def verify_installation() -> None:
    """Load fly model, step simulation, render a frame.

    Proves that MuJoCo + FlyGym install correctly, the Drosophila body model
    loads with articulated joints, the simulation steps without error, and
    headless EGL rendering produces a valid image.
    """
    import mujoco
    from flygym import Simulation
    from flygym.anatomy import (
        ActuatedDOFPreset,
        AxisOrder,
        JointPreset,
        Skeleton,
    )
    from flygym.compose import ActuatorType, FlatGroundWorld, NeuroMechFly
    from flygym.utils.math import Rotation3D

    print("=" * 60)
    print("FlyGym / MuJoCo Installation Verification")
    print("=" * 60)

    # --- Build the fly model with joints and actuators ---
    fly = NeuroMechFly()
    skeleton = Skeleton(
        axis_order=AxisOrder.PITCH_ROLL_YAW,
        joint_preset=JointPreset.ALL_BIOLOGICAL,
    )
    fly.add_joints(skeleton)

    actuated_dofs = skeleton.get_actuated_dofs_from_preset(
        ActuatedDOFPreset.LEGS_ONLY
    )
    fly.add_actuators(actuated_dofs, ActuatorType.POSITION, kp=40.0)
    fly.add_tracking_camera()

    # --- Assemble world ---
    world = FlatGroundWorld()
    spawn_pos = np.array([0.0, 0.0, 0.6])
    spawn_rot = Rotation3D("quat", [1, 0, 0, 0])
    world.add_fly(
        fly,
        spawn_position=spawn_pos,
        spawn_rotation=spawn_rot,
        add_ground_contact_sensors=False,
    )

    # --- Create simulation ---
    sim = Simulation(world)
    model = sim.mj_model
    data = sim.mj_data

    # --- Report model interface ---
    joint_names = [
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, i)
        for i in range(model.njnt)
    ]
    actuator_names = [
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i)
        for i in range(model.nu)
    ]
    sensor_names = [
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_SENSOR, i)
        for i in range(model.nsensor)
    ]

    print(f"\nJoint names ({model.njnt}):")
    for name in joint_names[:15]:
        print(f"  {name}")
    if model.njnt > 15:
        print(f"  ... ({model.njnt} total)")

    print(f"\nActuator names ({model.nu}):")
    for name in actuator_names[:15]:
        print(f"  {name}")
    if model.nu > 15:
        print(f"  ... ({model.nu} total)")

    print(f"\nSensor names ({model.nsensor}):")
    for name in sensor_names[:15]:
        print(f"  {name}")
    if model.nsensor > 15:
        print(f"  ... ({model.nsensor} total)")

    # --- Step 1000 timesteps ---
    t0 = time.time()
    for _ in range(1000):
        mujoco.mj_step(model, data)
    elapsed = time.time() - t0
    print(f"\nStepped 1000 timesteps in {elapsed:.3f}s (timestep={model.opt.timestep}s)")

    # --- Render single frame ---
    renderer = mujoco.Renderer(model, height=480, width=640)
    renderer.update_scene(data, camera="nmf/trackcam")
    img = renderer.render()
    print(f"Rendered frame: {img.shape}")

    # --- Save image ---
    reports_dir = Path(__file__).resolve().parent.parent.parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    outpath = reports_dir / "flygym_hello.png"

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.imsave(str(outpath), img)
    fsize = outpath.stat().st_size
    print(f"Saved: {outpath} ({fsize:,} bytes)")

    # --- Cleanup ---
    renderer.close()
    sim.close()

    print("\n" + "=" * 60)
    print("PASS: MuJoCo + FlyGym verification complete.")
    print("=" * 60)
