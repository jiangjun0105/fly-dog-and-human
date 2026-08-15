"""Scripted fly locomotion and motor/sensory interface characterization.

Applies sinusoidal CPG-like position commands to the fly's leg actuators
to produce forward walking via a tripod gait, and documents the full
motor-sensory interface of the NeuroMechFly model.

Usage:
    python -m digital_drosophila body locomotion
"""

import os

os.environ.setdefault("MUJOCO_GL", "egl")

import time
from pathlib import Path

import numpy as np


# ---------------------------------------------------------------------------
# Actuator / leg mapping constants
# ---------------------------------------------------------------------------

# Each leg has 11 actuated DOFs in this order (position-controlled):
#   0: coxa-pitch         (thorax-coxa joint)
#   1: coxa-roll          (thorax-coxa joint)
#   2: coxa-yaw           (thorax-coxa joint)
#   3: trochanterfemur-pitch  (coxa-trochanterfemur joint)
#   4: trochanterfemur-roll   (coxa-trochanterfemur joint)
#   5: tibia-pitch        (trochanterfemur-tibia joint)
#   6: tarsus1-pitch      (tibia-tarsus1 joint)
#   7: tarsus2-pitch      (tarsus1-tarsus2 joint)
#   8: tarsus3-pitch      (tarsus2-tarsus3 joint)
#   9: tarsus4-pitch      (tarsus3-tarsus4 joint)
#  10: tarsus5-pitch      (tarsus4-tarsus5 joint)

LEG_NAMES = ["lf", "lm", "lh", "rf", "rm", "rh"]
LEG_FULL_NAMES = {
    "lf": "Left Front (L1)",
    "lm": "Left Middle (L2)",
    "lh": "Left Hind (L3)",
    "rf": "Right Front (R1)",
    "rm": "Right Middle (R2)",
    "rh": "Right Hind (R3)",
}

# Actuator index offsets for each leg (11 DOFs per leg, 66 total)
LEG_OFFSETS = {"lf": 0, "lm": 11, "lh": 22, "rf": 33, "rm": 44, "rh": 55}

# DOF names within each leg
LEG_DOF_NAMES = [
    "coxa-pitch",
    "coxa-roll",
    "coxa-yaw",
    "trochanterfemur-pitch",
    "trochanterfemur-roll",
    "tibia-pitch",
    "tarsus1-pitch",
    "tarsus2-pitch",
    "tarsus3-pitch",
    "tarsus4-pitch",
    "tarsus5-pitch",
]

# Segments per leg with their DOFs
LEG_SEGMENTS = {
    "coxa": {"dofs": ["pitch", "roll", "yaw"], "indices": [0, 1, 2]},
    "trochanter/femur": {"dofs": ["pitch", "roll"], "indices": [3, 4]},
    "tibia": {"dofs": ["pitch"], "indices": [5]},
    "tarsus1": {"dofs": ["pitch"], "indices": [6]},
    "tarsus2": {"dofs": ["pitch"], "indices": [7]},
    "tarsus3": {"dofs": ["pitch"], "indices": [8]},
    "tarsus4": {"dofs": ["pitch"], "indices": [9]},
    "tarsus5": {"dofs": ["pitch"], "indices": [10]},
}

# Tripod gait phase assignment:
#   Group A (phase=0):   LF, RM, LH
#   Group B (phase=pi):  RF, LM, RH
TRIPOD_PHASES = {
    "lf": 0.0,
    "rm": 0.0,
    "lh": 0.0,
    "rf": np.pi,
    "lm": np.pi,
    "rh": np.pi,
}

# Motor neuron type -> FlyGym actuator mapping (coarse)
# Based on connectome cell type naming (MN prefix + body region suffix)
# and VNC ROI localization (LegNp T1/T2/T3)
MOTOR_NEURON_MAPPING = {
    # Leg motor neurons (by segment and thoracic neuropil)
    "MNfl (front leg MNs)": {
        "VNC ROI": "LegNp(T1)(L/R)",
        "FlyGym legs": ["lf", "rf"],
        "actuators": "coxa + trochanterfemur + tibia (11 DOFs each)",
        "example_types": ["MNfl01", "MNfl02", "MNfl03"],
    },
    "MNml (middle leg MNs)": {
        "VNC ROI": "LegNp(T2)(L/R)",
        "FlyGym legs": ["lm", "rm"],
        "actuators": "coxa + trochanterfemur + tibia (11 DOFs each)",
        "example_types": ["MNml01", "MNml02"],
    },
    "MNhl (hind leg MNs)": {
        "VNC ROI": "LegNp(T3)(L/R)",
        "FlyGym legs": ["lh", "rh"],
        "actuators": "coxa + trochanterfemur + tibia (11 DOFs each)",
        "example_types": ["MNhl01", "MNhl02"],
    },
    # Non-leg motor neurons (not actuated in current FlyGym setup)
    "MNwm (wing muscle MNs)": {
        "VNC ROI": "WTct(T2)(L/R)",
        "FlyGym legs": [],
        "actuators": "N/A (wings not actuated in LEGS_ONLY preset)",
        "example_types": ["MNwm01", "MNwm36"],
    },
    "MNnm (neck muscle MNs)": {
        "VNC ROI": "NTct(T1)(L/R)",
        "FlyGym legs": [],
        "actuators": "N/A (neck not actuated in LEGS_ONLY preset)",
        "example_types": ["MNnm01"],
    },
    "MNhm (haltere muscle MNs)": {
        "VNC ROI": "HTct(T3)(L/R)",
        "FlyGym legs": [],
        "actuators": "N/A (haltere not actuated in LEGS_ONLY preset)",
        "example_types": ["MNhm01"],
    },
    "MNad (abdomen MNs)": {
        "VNC ROI": "ANm",
        "FlyGym legs": [],
        "actuators": "N/A (abdomen not actuated in LEGS_ONLY preset)",
        "example_types": ["MNad01", "MNad02"],
    },
}


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def build_simulation():
    """Build the NeuroMechFly simulation with position-controlled leg actuators.

    Returns:
        tuple: (sim, fly, model, data, neutral_ctrl, actuator_names)
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
    from flygym.compose.pose import KinematicPosePreset
    from flygym.utils.math import Rotation3D

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

    # Get neutral standing pose
    neutral_pose = fly.get_pose_lookup(KinematicPosePreset.NEUTRAL)

    # Build world and add fly
    world = FlatGroundWorld()
    spawn_pos = np.array([0.0, 0.0, 0.6])
    spawn_rot = Rotation3D("quat", [1, 0, 0, 0])
    world.add_fly(
        fly,
        spawn_position=spawn_pos,
        spawn_rotation=spawn_rot,
        add_ground_contact_sensors=True,
    )

    sim = Simulation(world)
    model = sim.mj_model
    data = sim.mj_data

    # Build neutral control vector from actuator names
    neutral_ctrl = np.zeros(model.nu)
    actuator_names = []
    for i in range(model.nu):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i)
        actuator_names.append(name)
        # Actuator name: 'nmf/c_thorax-lf_coxa-pitch-position'
        # Neutral pose key: 'c_thorax-lf_coxa-pitch'
        short = name.replace("nmf/", "").replace("-position", "")
        if short in neutral_pose:
            neutral_ctrl[i] = neutral_pose[short]

    # Initialize joint positions to neutral standing pose
    for i in range(model.nu):
        jnt_id = model.actuator_trnid[i, 0]
        qpos_adr = model.jnt_qposadr[jnt_id]
        data.qpos[qpos_adr] = neutral_ctrl[i]

    # Set initial ctrl to neutral
    data.ctrl[:] = neutral_ctrl
    mujoco.mj_forward(model, data)

    return sim, fly, model, data, neutral_ctrl, actuator_names


def settle_simulation(sim, n_steps=2000):
    """Let the fly settle into a stable standing pose.

    Args:
        sim: The FlyGym Simulation instance.
        n_steps: Number of physics steps to settle (default 2000 = 0.2s).
    """
    for _ in range(n_steps):
        sim.step()


def run_tripod_gait(sim, model, data, neutral_ctrl, duration_s=2.0, freq_hz=8.0):
    """Apply sinusoidal CPG-like commands for tripod walking.

    The tripod gait alternates two groups of three legs:
      - Group A (stance while B swings): LF, RM, LH
      - Group B (stance while A swings): RF, LM, RH

    Each leg's actuators are modulated sinusoidally around the neutral
    standing pose. Key DOFs driven:
      - coxa-yaw: forward/backward leg swing (protraction/retraction)
      - trochanterfemur-pitch: leg lift during swing phase
      - tibia-pitch: ground push during stance phase

    Args:
        sim: The FlyGym Simulation instance.
        model: MuJoCo model.
        data: MuJoCo data.
        neutral_ctrl: Neutral standing pose control vector (66,).
        duration_s: Duration of locomotion in seconds.
        freq_hz: CPG oscillation frequency in Hz.

    Returns:
        dict with keys: displacement, speed, n_steps, frames
    """
    from flygym.compose import ActuatorType

    dt = model.opt.timestep
    n_steps = int(duration_s / dt)
    initial_pos = data.qpos[0:3].copy()

    # Gait parameters (radians)
    amp_coxa_pitch = 0.2  # forward thrust
    amp_coxa_yaw = 0.3  # protraction/retraction swing
    amp_femur = 0.4  # leg lift during swing
    amp_tibia = 0.2  # ground push

    # Collect frames for visualization
    frame_interval = n_steps // 6  # capture ~6 frames
    frames = []

    import mujoco

    renderer = mujoco.Renderer(model, height=360, width=480)

    for step in range(n_steps):
        t = step * dt
        phase = 2 * np.pi * freq_hz * t

        action = neutral_ctrl.copy()

        for leg_name, leg_phase in TRIPOD_PHASES.items():
            offset = LEG_OFFSETS[leg_name]
            p = phase + leg_phase

            # Coxa pitch: forward thrust
            action[offset + 0] += amp_coxa_pitch * np.sin(p)
            # Coxa yaw: protraction/retraction
            action[offset + 2] += amp_coxa_yaw * np.sin(p)
            # Femur pitch: lift during swing (phase-shifted by +90 deg)
            action[offset + 3] += amp_femur * np.sin(p + np.pi / 2)
            # Tibia pitch: push during stance (phase-shifted by -45 deg)
            action[offset + 5] += amp_tibia * np.sin(p - np.pi / 4)

        sim.set_actuator_inputs("nmf", ActuatorType.POSITION, action)
        sim.step()

        # Capture frames
        if step % frame_interval == 0 and len(frames) < 6:
            renderer.update_scene(data, camera="nmf/trackcam")
            frames.append(renderer.render().copy())

    renderer.close()

    final_pos = data.qpos[0:3]
    displacement = final_pos - initial_pos

    return {
        "displacement": displacement,
        "speed_mm_per_s": displacement[0] / duration_s,
        "n_steps": n_steps,
        "frames": frames,
        "initial_pos": initial_pos,
        "final_pos": final_pos,
    }


def get_sensor_inventory(model):
    """Enumerate all sensors in the model with their types and dimensions.

    Returns:
        list of dicts with keys: name, type_id, type_name, dim, adr
    """
    import mujoco

    # MuJoCo sensor type names (subset relevant to this model)
    SENSOR_TYPE_NAMES = {
        0: "touch",
        1: "accelerometer",
        2: "velocimeter",
        3: "gyro",
        4: "force",
        5: "torque",
        6: "magnetometer",
        7: "rangefinder",
        8: "jointpos",
        9: "jointvel",
        10: "tendonpos",
        11: "tendonvel",
        12: "actuatorfrc",
        13: "ballquat",
        14: "ballangvel",
        15: "jointlimitpos",
        16: "jointlimitvel",
        17: "jointlimitfrc",
        42: "plugin",
    }

    sensors = []
    for i in range(model.nsensor):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_SENSOR, i)
        type_id = int(model.sensor_type[i])
        sensors.append(
            {
                "name": name,
                "type_id": type_id,
                "type_name": SENSOR_TYPE_NAMES.get(type_id, f"unknown({type_id})"),
                "dim": int(model.sensor_dim[i]),
                "adr": int(model.sensor_adr[i]),
            }
        )

    return sensors


def get_observable_state(sim, model, data):
    """Get the full observable state of the fly.

    Returns a dict describing all available sensory signals.
    """
    import mujoco

    joint_angles = sim.get_joint_angles("nmf")
    joint_velocities = sim.get_joint_velocities("nmf")

    # Body position and orientation (free joint)
    body_pos = data.qpos[0:3].copy()
    body_quat = data.qpos[3:7].copy()
    body_vel = data.qvel[0:3].copy()
    body_angvel = data.qvel[3:6].copy()

    # Ground contact sensor data
    contact_data = data.sensordata.copy()

    return {
        "joint_angles": {"data": joint_angles, "shape": joint_angles.shape},
        "joint_velocities": {"data": joint_velocities, "shape": joint_velocities.shape},
        "body_position_mm": {"data": body_pos, "shape": body_pos.shape},
        "body_quaternion": {"data": body_quat, "shape": body_quat.shape},
        "body_linear_vel_mm_per_s": {"data": body_vel, "shape": body_vel.shape},
        "body_angular_vel_rad_per_s": {
            "data": body_angvel,
            "shape": body_angvel.shape,
        },
        "ground_contact_forces": {
            "data": contact_data,
            "shape": contact_data.shape,
            "note": "6 legs x 16-dim plugin sensor (contact geometry)",
        },
    }


def save_locomotion_strip(frames, outpath):
    """Save a horizontal strip of frames showing the locomotion sequence.

    Args:
        frames: List of rendered frames (numpy arrays).
        outpath: Path to save the PNG.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = len(frames)
    fig, axes = plt.subplots(1, n, figsize=(4 * n, 3))
    if n == 1:
        axes = [axes]

    for i, (ax, frame) in enumerate(zip(axes, frames)):
        ax.imshow(frame)
        ax.set_title(f"t={i * 2.0 / n:.2f}s", fontsize=10)
        ax.axis("off")

    plt.suptitle(
        "NeuroMechFly Tripod Gait (CPG-driven, 8 Hz)", fontsize=12, y=0.98
    )
    plt.tight_layout()
    plt.savefig(str(outpath), dpi=150, bbox_inches="tight")
    plt.close()
    return outpath.stat().st_size


# ---------------------------------------------------------------------------
# Print functions
# ---------------------------------------------------------------------------


def print_actuator_table(actuator_names):
    """Print the full actuator mapping table."""
    print("\n" + "=" * 80)
    print("ACTUATOR MAPPING TABLE (66 position-controlled actuators)")
    print("=" * 80)
    print(f"{'Idx':<4} {'Leg':<6} {'Segment':<18} {'DOF':<8} {'Actuator Name'}")
    print("-" * 80)

    for i, name in enumerate(actuator_names):
        leg_idx = i // 11
        dof_idx = i % 11
        leg = LEG_NAMES[leg_idx]
        leg_full = LEG_FULL_NAMES[leg]
        dof = LEG_DOF_NAMES[dof_idx]

        # Determine segment
        if dof_idx <= 2:
            segment = "coxa"
        elif dof_idx <= 4:
            segment = "trochanter/femur"
        elif dof_idx == 5:
            segment = "tibia"
        else:
            segment = f"tarsus{dof_idx - 5}"

        axis = dof.split("-")[-1]
        print(f"{i:<4} {leg_full:<6} {segment:<18} {axis:<8} {name}")

    print()
    print("Legend:")
    print("  Legs: LF=Left Front, LM=Left Middle, LH=Left Hind")
    print("        RF=Right Front, RM=Right Middle, RH=Right Hind")
    print("  DOFs: pitch=flexion/extension, roll=adduction/abduction, yaw=rotation")
    print("  All actuators are POSITION-controlled (target angle in radians)")


def print_sensor_inventory(sensors, obs_state):
    """Print the sensor signal inventory."""
    print("\n" + "=" * 80)
    print("SENSOR SIGNAL INVENTORY")
    print("=" * 80)

    print("\n--- MuJoCo Native Sensors ---")
    print(f"{'Idx':<4} {'Name':<42} {'Type':<12} {'Dim':<5}")
    print("-" * 65)
    for i, s in enumerate(sensors):
        print(f"{i:<4} {s['name']:<42} {s['type_name']:<12} {s['dim']:<5}")

    print("\n--- Observable State via FlyGym API ---")
    print(f"{'Signal':<35} {'Shape':<15} {'Notes'}")
    print("-" * 75)
    for key, val in obs_state.items():
        note = val.get("note", "")
        print(f"{key:<35} {str(val['shape']):<15} {note}")

    print("\n--- Joint Angle Details ---")
    print("  126 joint DOFs total (all joints in model, including passive)")
    print("  66 actuated DOFs (leg joints only)")
    print("  Remaining 60: head, eyes, antennae, proboscis, abdomen, wings, halteres")

    print("\n--- Ground Contact Sensors ---")
    print("  6 sensors (one per leg), each 16-dimensional")
    print("  Sensor type: plugin (FlyGym ground contact geometry)")
    total_dim = sum(s["dim"] for s in sensors)
    print(f"  Total sensordata dimension: {total_dim}")


def print_motor_neuron_mapping():
    """Print the proposed motor neuron type -> FlyGym actuator mapping."""
    print("\n" + "=" * 80)
    print("PROPOSED MOTOR NEURON TYPE -> FLYGYM ACTUATOR MAPPING")
    print("=" * 80)
    print()
    print("The Drosophila VNC contains 702 motor neurons spanning 142 cell types.")
    print("Motor neuron type names encode body region via suffix (fl/ml/hl/wm/nm/hm/ad).")
    print()
    print(
        f"{'MN Type Group':<25} {'VNC ROI':<20} {'FlyGym Legs':<12} "
        f"{'Actuators'}"
    )
    print("-" * 90)

    for mn_type, info in MOTOR_NEURON_MAPPING.items():
        legs_str = ", ".join(info["FlyGym legs"]) if info["FlyGym legs"] else "N/A"
        print(
            f"{mn_type:<25} {info['VNC ROI']:<20} {legs_str:<12} "
            f"{info['actuators']}"
        )

    print()
    print("Mapping logic:")
    print("  1. MN suffix (fl/ml/hl) identifies thoracic segment (T1/T2/T3)")
    print("  2. VNC ROI (LegNp) confirms body-part assignment")
    print("  3. Each biological leg has ~50-60 muscles; FlyGym abstracts to 11 DOFs")
    print("  4. Multiple MN types map to one FlyGym actuator (many-to-one)")
    print()
    print("Coarse segment mapping (per leg):")
    print("  Coxa MNs         -> actuator indices [0,1,2] (pitch/roll/yaw)")
    print("  Trochanter MNs   -> actuator indices [3,4]   (pitch/roll)")
    print("  Femur/Tibia MNs  -> actuator index   [5]     (pitch)")
    print("  Tarsal MNs       -> actuator indices [6-10]  (pitch x5)")
    print()
    print("Note: Wing (MNwm), neck (MNnm), haltere (MNhm), and abdomen (MNad)")
    print("motor neurons have no corresponding FlyGym actuators in the LEGS_ONLY")
    print("preset. They would require adding wing/head/abdomen actuators.")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_locomotion() -> None:
    """Run the full locomotion characterization pipeline.

    1. Build simulation with neutral standing pose
    2. Settle the fly on the ground
    3. Run tripod gait for 2 seconds
    4. Print actuator mapping, sensor inventory, and motor neuron mapping
    5. Save visualization strip to reports/
    """
    print("=" * 80)
    print("Digital Drosophila: Scripted Locomotion & Interface Characterization")
    print("=" * 80)

    # --- Build simulation ---
    print("\n[1/5] Building NeuroMechFly simulation...")
    t0 = time.time()
    sim, fly, model, data, neutral_ctrl, actuator_names = build_simulation()
    print(f"      Model loaded in {time.time() - t0:.2f}s")
    print(f"      Joints: {model.njnt}, Actuators: {model.nu}, Sensors: {model.nsensor}")
    print(f"      Timestep: {model.opt.timestep}s, Gravity: {model.opt.gravity} mm/s^2")

    # --- Settle ---
    print("\n[2/5] Settling fly into standing pose (0.2s)...")
    settle_simulation(sim, n_steps=2000)
    print(f"      Standing position: {data.qpos[0:3]}")

    # --- Run locomotion ---
    print("\n[3/5] Running tripod gait (2.0s, 8 Hz CPG)...")
    t0 = time.time()
    result = run_tripod_gait(sim, model, data, neutral_ctrl, duration_s=2.0, freq_hz=8.0)
    elapsed = time.time() - t0
    print(f"      Completed {result['n_steps']} steps in {elapsed:.2f}s")
    print(
        f"      Forward displacement: {result['displacement'][0]:.2f} mm "
        f"(speed: {result['speed_mm_per_s']:.2f} mm/s)"
    )
    print(f"      Lateral drift: {result['displacement'][1]:.2f} mm")
    print(f"      Vertical change: {result['displacement'][2]:.2f} mm")
    print(f"      Captured {len(result['frames'])} frames for visualization")

    # --- Get sensor state ---
    sensors = get_sensor_inventory(model)
    obs_state = get_observable_state(sim, model, data)

    # --- Print tables ---
    print_actuator_table(actuator_names)
    print_sensor_inventory(sensors, obs_state)
    print_motor_neuron_mapping()

    # --- Save visualization ---
    print("\n[4/5] Saving visualization...")
    reports_dir = Path(__file__).resolve().parent.parent.parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    outpath = reports_dir / "flygym_locomotion.png"

    if result["frames"]:
        fsize = save_locomotion_strip(result["frames"], outpath)
        print(f"      Saved: {outpath} ({fsize:,} bytes)")
    else:
        print("      WARNING: No frames captured, skipping visualization")

    # --- Cleanup ---
    sim.close()

    # --- Summary ---
    print("\n[5/5] Summary")
    print("=" * 80)
    print(f"  Fly walked forward {result['displacement'][0]:.2f} mm in 2.0s")
    print(f"  Average speed: {result['speed_mm_per_s']:.2f} mm/s")
    print(f"  Gait: tripod (LF+RM+LH vs RF+LM+RH), 8 Hz sinusoidal CPG")
    print(f"  Actuated DOFs: {model.nu} (position-controlled)")
    print(f"  Observable signals: {len(sensors)} native sensors + joint angles/velocities")
    print(f"  Visualization: {outpath}")
    print("=" * 80)
