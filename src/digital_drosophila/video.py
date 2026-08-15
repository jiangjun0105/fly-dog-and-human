"""Video rendering for neural-driven fly simulation.

Renders the closed-loop co-simulation (Brian2 SNN driving FlyGym body) to MP4.

Usage:
    python -m digital_drosophila demo video [--duration 3.0] [--fps 30]

    from digital_drosophila.video import render_neural_video
    render_neural_video(duration_s=3.0, output_path="reports/demo.mp4")
"""

import os

os.environ.setdefault("MUJOCO_GL", "egl")

import time
from pathlib import Path

import numpy as np


_PACKAGE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _PACKAGE_DIR.parent.parent
_DEFAULT_REPORTS_DIR = _PROJECT_ROOT / "reports"


def render_neural_video(duration_s=3.0, output_path=None, fps=30,
                        width=640, height=480, camera="nmf/trackcam"):
    """Run closed-loop neural simulation and render to MP4.

    Parameters
    ----------
    duration_s : float
        Simulation duration in seconds.
    output_path : str or Path, optional
        Output MP4 path. Defaults to reports/neural_demo.mp4.
    fps : int
        Video frame rate.
    width, height : int
        Frame dimensions.
    camera : str
        MuJoCo camera name for rendering.

    Returns
    -------
    dict
        Simulation metrics and output path.
    """
    import imageio
    import mujoco

    if output_path is None:
        reports_dir = Path(os.environ.get(
            "DIGITAL_DROSOPHILA_REPORTS_DIR", str(_DEFAULT_REPORTS_DIR)
        ))
        reports_dir.mkdir(parents=True, exist_ok=True)
        output_path = reports_dir / "neural_demo.mp4"
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Neural-Driven Fly Demo — Video Render")
    print(f"  Duration: {duration_s}s | FPS: {fps} | Resolution: {width}x{height}")
    print("=" * 70)

    # Build co-simulation
    print("\n[1/3] Building co-simulation (Brian2 + FlyGym)...")
    t0 = time.time()

    from .loop import CoSimulation

    sim = CoSimulation(episode_length_s=duration_s, coupling_dt_ms=2.0)
    sim.reset()

    build_time = time.time() - t0
    print(f"  Built in {build_time:.1f}s")

    # Set up renderer
    model = sim._model
    data = sim._data
    renderer = mujoco.Renderer(model, height=height, width=width)

    # Calculate frame capture interval
    coupling_dt_s = sim.coupling_dt_ms / 1000.0
    steps_per_frame = max(1, int(1.0 / (fps * coupling_dt_s)))
    n_total_steps = int(duration_s / coupling_dt_s)

    print(f"\n[2/3] Running simulation and capturing frames...")
    print(f"  Total coupling steps: {n_total_steps}")
    print(f"  Capturing every {steps_per_frame} steps ({fps} fps target)")

    # Run simulation and capture frames
    writer = imageio.get_writer(
        str(output_path), fps=fps, codec="libx264",
        output_params=["-crf", "23", "-preset", "medium"],
    )

    t_sim_start = time.time()
    step_count = 0
    frame_count = 0

    while not sim.done:
        sim.step()
        step_count += 1

        if step_count % steps_per_frame == 0:
            renderer.update_scene(data, camera=camera)
            frame = renderer.render()
            writer.append_data(frame)
            frame_count += 1

        if step_count % 250 == 0:
            elapsed = time.time() - t_sim_start
            pct = step_count / n_total_steps * 100
            print(f"  Step {step_count}/{n_total_steps} ({pct:.0f}%) | "
                  f"frames: {frame_count} | elapsed: {elapsed:.1f}s")

    writer.close()
    renderer.close()

    sim_time = time.time() - t_sim_start
    metrics = sim.get_metrics()
    sim.close()

    # Summary
    print(f"\n[3/3] Summary")
    print(f"  Simulation: {duration_s}s in {sim_time:.1f}s wall-clock")
    print(f"  Frames captured: {frame_count}")
    print(f"  Video saved: {output_path}")
    print(f"  Forward displacement: {metrics['forward_distance_mm']:.4f} mm")
    print(f"  Mean motor rate: {metrics['mean_motor_rate_hz']:.1f} Hz")
    print(f"  Total spikes: {metrics['total_spikes']}")
    print("=" * 70)

    return {
        **metrics,
        "output_path": str(output_path),
        "frame_count": frame_count,
        "wall_time_s": sim_time,
    }


def render_tripod_video(duration_s=3.0, output_path=None, fps=30,
                        width=640, height=480):
    """Render scripted tripod gait (no neural network) to MP4 for comparison.

    Parameters
    ----------
    duration_s : float
        Simulation duration.
    output_path : str or Path, optional
        Output path. Defaults to reports/tripod_demo.mp4.
    fps, width, height : int
        Video parameters.
    """
    import imageio
    import mujoco
    from flygym.compose import ActuatorType

    if output_path is None:
        reports_dir = Path(os.environ.get(
            "DIGITAL_DROSOPHILA_REPORTS_DIR", str(_DEFAULT_REPORTS_DIR)
        ))
        reports_dir.mkdir(parents=True, exist_ok=True)
        output_path = reports_dir / "tripod_demo.mp4"
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Tripod Gait Demo — Video Render (scripted, no neural network)")
    print(f"  Duration: {duration_s}s | FPS: {fps}")
    print("=" * 70)

    from .locomotion import (
        build_simulation, settle_simulation,
        TRIPOD_PHASES, LEG_OFFSETS,
    )

    sim, fly, model, data, neutral_ctrl, actuator_names = build_simulation()
    settle_simulation(sim, n_steps=2000)

    renderer = mujoco.Renderer(model, height=height, width=width)
    dt = model.opt.timestep
    n_steps = int(duration_s / dt)
    steps_per_frame = max(1, int(1.0 / (fps * dt)))

    amp_coxa_pitch = 0.2
    amp_coxa_yaw = 0.3
    amp_femur = 0.4
    amp_tibia = 0.2
    freq_hz = 8.0

    writer = imageio.get_writer(
        str(output_path), fps=fps, codec="libx264",
        output_params=["-crf", "23", "-preset", "medium"],
    )

    initial_pos = data.qpos[0:3].copy()
    frame_count = 0

    print(f"  Running {n_steps} physics steps...")
    t0 = time.time()

    for step in range(n_steps):
        t = step * dt
        phase = 2 * np.pi * freq_hz * t

        action = neutral_ctrl.copy()
        for leg_name, leg_phase in TRIPOD_PHASES.items():
            offset = LEG_OFFSETS[leg_name]
            p = phase + leg_phase
            action[offset + 0] += amp_coxa_pitch * np.sin(p)
            action[offset + 2] += amp_coxa_yaw * np.sin(p)
            action[offset + 3] += amp_femur * np.sin(p + np.pi / 2)
            action[offset + 5] += amp_tibia * np.sin(p - np.pi / 4)

        sim.set_actuator_inputs("nmf", ActuatorType.POSITION, action)
        sim.step()

        if step % steps_per_frame == 0:
            renderer.update_scene(data, camera="nmf/trackcam")
            writer.append_data(renderer.render())
            frame_count += 1

    writer.close()
    renderer.close()

    wall_time = time.time() - t0
    final_pos = data.qpos[0:3].copy()
    displacement = final_pos - initial_pos
    sim.close()

    print(f"  Done in {wall_time:.1f}s | {frame_count} frames")
    print(f"  Forward: {displacement[0]:.3f} mm ({displacement[0] / duration_s:.2f} mm/s)")
    print(f"  Video saved: {output_path}")
    print("=" * 70)

    return {
        "forward_distance_mm": float(displacement[0]),
        "speed_mm_per_s": float(displacement[0] / duration_s),
        "output_path": str(output_path),
        "frame_count": frame_count,
    }


def render_trained_video(checkpoint_path, duration_s=5.0, output_path=None, fps=30,
                         width=640, height=480, camera="nmf/trackcam"):
    """Render a trained network (from checkpoint) driving the fly body to MP4.

    Parameters
    ----------
    checkpoint_path : str or Path
        Path to .npz checkpoint (with 'weights' and 'thresholds' arrays).
    duration_s : float
        Simulation duration in seconds.
    output_path : str or Path, optional
        Output MP4 path. Defaults to reports/trained_demo.mp4.
    fps : int
        Video frame rate.
    width, height : int
        Frame dimensions.
    camera : str
        MuJoCo camera name for rendering.

    Returns
    -------
    dict
        Simulation metrics and output path.
    """
    import imageio
    import mujoco

    checkpoint_path = Path(checkpoint_path)
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    if output_path is None:
        reports_dir = Path(os.environ.get(
            "DIGITAL_DROSOPHILA_REPORTS_DIR", str(_DEFAULT_REPORTS_DIR)
        ))
        reports_dir.mkdir(parents=True, exist_ok=True)
        output_path = reports_dir / "trained_demo.mp4"
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Trained Network Demo — Video Render")
    print(f"  Checkpoint: {checkpoint_path.name}")
    print(f"  Duration: {duration_s}s | FPS: {fps} | Resolution: {width}x{height}")
    print("=" * 70)

    # Build controller from checkpoint
    print("\n[1/3] Building trained controller (Brian2 + FlyGym)...")
    t0 = time.time()

    from .training import TrainedController

    ctrl = TrainedController(checkpoint_path, episode_length_s=duration_s)
    ctrl.reset()

    build_time = time.time() - t0
    print(f"  Built in {build_time:.1f}s")

    # Set up renderer
    model = ctrl._model
    data = ctrl._data
    renderer = mujoco.Renderer(model, height=height, width=width)

    # Frame capture interval
    coupling_dt_s = ctrl._coupling_dt_ms / 1000.0
    steps_per_frame = max(1, int(1.0 / (fps * coupling_dt_s)))
    n_total_steps = ctrl._n_steps_total

    print(f"\n[2/3] Running simulation and capturing frames...")
    print(f"  Total coupling steps: {n_total_steps}")
    print(f"  Capturing every {steps_per_frame} steps ({fps} fps target)")

    # Run and capture
    writer = imageio.get_writer(
        str(output_path), fps=fps, codec="libx264",
        output_params=["-crf", "23", "-preset", "medium"],
    )

    t_sim_start = time.time()
    step_count = 0
    frame_count = 0

    while not ctrl.done:
        ctrl.step()
        step_count += 1

        if step_count % steps_per_frame == 0:
            renderer.update_scene(data, camera=camera)
            frame = renderer.render()
            writer.append_data(frame)
            frame_count += 1

        if step_count % 250 == 0:
            elapsed = time.time() - t_sim_start
            pct = step_count / n_total_steps * 100
            print(f"  Step {step_count}/{n_total_steps} ({pct:.0f}%) | "
                  f"frames: {frame_count} | elapsed: {elapsed:.1f}s")

    writer.close()
    renderer.close()

    sim_time = time.time() - t_sim_start
    metrics = ctrl.get_metrics()
    ctrl.close()

    # Summary
    print(f"\n[3/3] Summary")
    print(f"  Simulation: {duration_s}s in {sim_time:.1f}s wall-clock")
    print(f"  Frames captured: {frame_count}")
    print(f"  Video saved: {output_path}")
    if "forward_speed_mm_per_s" in metrics:
        print(f"  Forward speed: {metrics['forward_speed_mm_per_s']:.4f} mm/s")
        print(f"  Lateral deviation: {metrics['lateral_deviation_mm']:.4f} mm")
    print("=" * 70)

    return {
        **metrics,
        "output_path": str(output_path),
        "frame_count": frame_count,
        "wall_time_s": sim_time,
    }


def run_demo_video(duration_s=3.0, fps=30):
    """Entry point for CLI: renders both neural and tripod videos."""
    print("Rendering neural-driven demo video...")
    neural_result = render_neural_video(duration_s=duration_s, fps=fps)

    print("\n\nRendering scripted tripod comparison video...")
    tripod_result = render_tripod_video(duration_s=duration_s, fps=fps)

    print("\n\n" + "=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)
    print(f"\n  Neural-driven video: {neural_result['output_path']}")
    print(f"    Forward: {neural_result['forward_distance_mm']:.4f} mm")
    print(f"\n  Tripod gait video:   {tripod_result['output_path']}")
    print(f"    Forward: {tripod_result['forward_distance_mm']:.3f} mm")
    print(f"\n  The tripod gait is a scripted CPG — the neural demo shows the")
    print(f"  actual connectome-derived spiking network driving the same body.")
    print("=" * 70)
