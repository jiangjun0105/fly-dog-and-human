"""Entry point: python -m digital_drosophila <command> [subcommand]

Usage:
    python -m digital_drosophila simulate minimal
    python -m digital_drosophila simulate constrained
    python -m digital_drosophila simulate full_vnc
    python -m digital_drosophila body verify
    python -m digital_drosophila body locomotion
    python -m digital_drosophila loop motor_test
    python -m digital_drosophila loop closed_loop
    python -m digital_drosophila loop episode_demo
    python -m digital_drosophila learn stdp_basic [--episodes N]
    python -m digital_drosophila learn train [--episodes 50] [--episode-length 2.0] [--topology biological|random] [--backend cpu|gpu]
    python -m digital_drosophila learn train_gpu [--episodes 50] [--episode-length 2.0]
    python -m digital_drosophila learn train_functional [--episodes 50] [--hops 2] [--episode-length 2.0] [--force-rebuild] [--backend gpu|cpu]
    python -m digital_drosophila learn evaluate --checkpoint PATH [--episodes 3] [--duration 5.0]
    python -m digital_drosophila learn experiment [--episodes 50] [--episode-length 2.0]
    python -m digital_drosophila demo video [--duration 3.0] [--fps 30]
    python -m digital_drosophila demo tripod [--duration 3.0] [--fps 30]
    python -m digital_drosophila demo functional_trained --checkpoint PATH [--duration 5.0] [--fps 30]
    python -m digital_drosophila demo functional_baseline [--duration 5.0] [--fps 30]
    python -m digital_drosophila benchmark locomotion [--episodes 10] [--duration 5.0]
    python -m digital_drosophila benchmark chemotaxis [--episodes 10] [--duration 10.0]
    python -m digital_drosophila benchmark navigation [--episodes 5] [--duration 5.0]
"""

import sys


def main():
    args = sys.argv[1:]

    if not args:
        print(
            "Usage: python -m digital_drosophila <command> [subcommand]\n"
            "\nCommands:\n"
            "  simulate <minimal|constrained|full_vnc>   Run SNN simulation\n"
            "  body verify                               Verify MuJoCo/FlyGym installation\n"
            "  body locomotion                           Run scripted locomotion demo\n"
            "  loop motor_test                           Run motor output adapter test\n"
            "  loop closed_loop                          Run closed-loop co-simulation\n"
            "  loop episode_demo                         Run episode-based harness demo\n"
            "  learn stdp_basic [--episodes N]           Run STDP learning (default 10 episodes)\n"
            "  learn train [--episodes N] [--backend cpu|gpu]    Extended training with homeostasis\n"
            "  learn train_gpu [--episodes N]                    GPU-accelerated training (PyGeNN)\n"
            "  benchmark <locomotion|chemotaxis|navigation>  Run benchmark suite"
        )
        sys.exit(1)

    command = args[0]

    if command == "simulate":
        mode = args[1] if len(args) > 1 else "constrained"

        from .simulate import run_minimal, run_constrained, run_full_vnc

        modes = {
            "minimal": run_minimal,
            "constrained": run_constrained,
            "full_vnc": run_full_vnc,
        }

        if mode not in modes:
            print(f"Unknown mode: {mode!r}. Choose from: {', '.join(modes.keys())}")
            sys.exit(1)

        modes[mode]()

    elif command == "body":
        subcommand = args[1] if len(args) > 1 else ""

        if subcommand == "verify":
            from .body import verify_installation

            verify_installation()
        elif subcommand == "locomotion":
            from .locomotion import run_locomotion

            run_locomotion()
        else:
            print(
                "Usage: python -m digital_drosophila body <verify|locomotion>"
            )
            sys.exit(1)

    elif command == "loop":
        subcommand = args[1] if len(args) > 1 else ""

        if subcommand == "motor_test":
            from .motor_adapter import run_motor_test

            run_motor_test()
        elif subcommand == "closed_loop":
            from .closed_loop import run_closed_loop

            run_closed_loop()
        elif subcommand == "episode_demo":
            from .loop import run_episode_demo

            run_episode_demo()
        else:
            print(
                "Usage: python -m digital_drosophila loop "
                "<motor_test|closed_loop|episode_demo>"
            )
            sys.exit(1)

    elif command == "learn":
        subcommand = args[1] if len(args) > 1 else ""

        if subcommand == "stdp_basic":
            # Parse --episodes flag
            episodes = 10
            for i, arg in enumerate(args[2:], start=2):
                if arg == "--episodes" and i + 1 < len(args):
                    try:
                        episodes = int(args[i + 1])
                    except ValueError:
                        print(f"Invalid episodes value: {args[i + 1]!r}")
                        sys.exit(1)

            from .learning import run_stdp_basic

            run_stdp_basic(episodes=episodes)

        elif subcommand in ("train", "train_gpu"):
            # Parse --episodes, --episode-length, --topology, --backend flags
            episodes = 50
            episode_length = 2.0
            topology = "biological"
            backend = "gpu" if subcommand == "train_gpu" else "cpu"
            for i, arg in enumerate(args[2:], start=2):
                if arg == "--episodes" and i + 1 < len(args):
                    try:
                        episodes = int(args[i + 1])
                    except ValueError:
                        print(f"Invalid episodes value: {args[i + 1]!r}")
                        sys.exit(1)
                elif arg == "--episode-length" and i + 1 < len(args):
                    try:
                        episode_length = float(args[i + 1])
                    except ValueError:
                        print(f"Invalid episode-length value: {args[i + 1]!r}")
                        sys.exit(1)
                elif arg == "--topology" and i + 1 < len(args):
                    topology = args[i + 1]
                    if topology not in ("biological", "random"):
                        print(f"Invalid topology: {topology!r}. "
                              "Choose 'biological' or 'random'.")
                        sys.exit(1)
                elif arg == "--backend" and i + 1 < len(args):
                    backend = args[i + 1]
                    if backend not in ("cpu", "gpu"):
                        print(f"Invalid backend: {backend!r}. "
                              "Choose 'cpu' or 'gpu'.")
                        sys.exit(1)

            from .training import run_training

            run_training(
                episodes=episodes, episode_length=episode_length,
                topology=topology, backend=backend,
            )

        elif subcommand == "evaluate":
            # Parse --checkpoint, --episodes, --duration
            checkpoint = None
            episodes = 3
            duration = 5.0
            for i, arg in enumerate(args[2:], start=2):
                if arg == "--checkpoint" and i + 1 < len(args):
                    checkpoint = args[i + 1]
                elif arg == "--episodes" and i + 1 < len(args):
                    try:
                        episodes = int(args[i + 1])
                    except ValueError:
                        print(f"Invalid episodes value: {args[i + 1]!r}")
                        sys.exit(1)
                elif arg == "--duration" and i + 1 < len(args):
                    try:
                        duration = float(args[i + 1])
                    except ValueError:
                        print(f"Invalid duration value: {args[i + 1]!r}")
                        sys.exit(1)

            if checkpoint is None:
                print("Error: --checkpoint path required")
                sys.exit(1)

            from .training import run_evaluation

            run_evaluation(checkpoint, episodes=episodes, duration=duration)

        elif subcommand == "train_functional":
            # Parse --episodes, --hops, --episode-length, --force-rebuild, --backend
            episodes = 50
            episode_length = 2.0
            force_rebuild = False
            n_hops = 2
            backend = "gpu"
            for i, arg in enumerate(args[2:], start=2):
                if arg == "--episodes" and i + 1 < len(args):
                    try:
                        episodes = int(args[i + 1])
                    except ValueError:
                        print(f"Invalid episodes value: {args[i + 1]!r}")
                        sys.exit(1)
                elif arg == "--episode-length" and i + 1 < len(args):
                    try:
                        episode_length = float(args[i + 1])
                    except ValueError:
                        print(f"Invalid episode-length value: {args[i + 1]!r}")
                        sys.exit(1)
                elif arg == "--hops" and i + 1 < len(args):
                    try:
                        n_hops = int(args[i + 1])
                        if n_hops < 1 or n_hops > 3:
                            print(f"Invalid hops value: {args[i + 1]!r}. "
                                  "Choose 1, 2, or 3.")
                            sys.exit(1)
                    except ValueError:
                        print(f"Invalid hops value: {args[i + 1]!r}")
                        sys.exit(1)
                elif arg == "--backend" and i + 1 < len(args):
                    backend = args[i + 1]
                    if backend not in ("cpu", "gpu"):
                        print(f"Invalid backend: {backend!r}. "
                              "Choose 'cpu' or 'gpu'.")
                        sys.exit(1)
                elif arg == "--force-rebuild":
                    force_rebuild = True

            from .functional_training import run_functional_training

            run_functional_training(
                episodes=episodes,
                episode_length=episode_length,
                force_rebuild=force_rebuild,
                n_hops=n_hops,
                backend=backend,
            )

        elif subcommand == "experiment":
            # Parse --episodes and --episode-length
            episodes = 50
            episode_length = 2.0
            for i, arg in enumerate(args[2:], start=2):
                if arg == "--episodes" and i + 1 < len(args):
                    try:
                        episodes = int(args[i + 1])
                    except ValueError:
                        print(f"Invalid episodes value: {args[i + 1]!r}")
                        sys.exit(1)
                elif arg == "--episode-length" and i + 1 < len(args):
                    try:
                        episode_length = float(args[i + 1])
                    except ValueError:
                        print(f"Invalid episode-length value: {args[i + 1]!r}")
                        sys.exit(1)

            from .training import run_experiment

            run_experiment(episodes=episodes, episode_length=episode_length)

        else:
            print(
                "Usage: python -m digital_drosophila learn "
                "<stdp_basic|train|train_gpu|train_functional|evaluate|experiment> [options]\n"
                "\n  stdp_basic [--episodes N]"
                "\n  train [--episodes N] [--episode-length S] [--topology bio|random] [--backend cpu|gpu]"
                "\n  train_gpu [--episodes N] [--episode-length S]"
                "\n  train_functional [--episodes N] [--hops 1|2|3] [--episode-length S] "
                "[--backend gpu|cpu] [--force-rebuild]"
                "\n  evaluate --checkpoint PATH [--episodes N] [--duration S]"
                "\n  experiment [--episodes N] [--episode-length S]"
            )
            sys.exit(1)

    elif command == "demo":
        subcommand = args[1] if len(args) > 1 else "video"

        # Parse --duration, --fps, --checkpoint
        duration = 3.0
        fps = 30
        checkpoint = None
        for i, arg in enumerate(args[2:], start=2):
            if arg == "--duration" and i + 1 < len(args):
                try:
                    duration = float(args[i + 1])
                except ValueError:
                    print(f"Invalid duration: {args[i + 1]!r}")
                    sys.exit(1)
            elif arg == "--fps" and i + 1 < len(args):
                try:
                    fps = int(args[i + 1])
                except ValueError:
                    print(f"Invalid fps: {args[i + 1]!r}")
                    sys.exit(1)
            elif arg == "--checkpoint" and i + 1 < len(args):
                checkpoint = args[i + 1]

        if subcommand == "video":
            from .video import render_neural_video

            render_neural_video(duration_s=duration, fps=fps)
        elif subcommand == "tripod":
            from .video import render_tripod_video

            render_tripod_video(duration_s=duration, fps=fps)
        elif subcommand == "both":
            from .video import run_demo_video

            run_demo_video(duration_s=duration, fps=fps)
        elif subcommand == "trained":
            if checkpoint is None:
                print("Error: --checkpoint path required for 'demo trained'")
                sys.exit(1)
            from .video import render_trained_video

            render_trained_video(checkpoint, duration_s=duration, fps=fps)
        elif subcommand == "functional_trained":
            if checkpoint is None:
                print("Error: --checkpoint path required for 'demo functional_trained'")
                sys.exit(1)
            from .video import render_functional_trained_video

            render_functional_trained_video(checkpoint, duration_s=duration, fps=fps)
        elif subcommand == "functional_baseline":
            from .video import render_functional_baseline_video

            render_functional_baseline_video(duration_s=duration, fps=fps)
        else:
            print(
                "Usage: python -m digital_drosophila demo "
                "<video|tripod|trained|functional_trained|functional_baseline|both> "
                "[--duration S] [--fps N] [--checkpoint PATH]"
            )
            sys.exit(1)

    elif command == "benchmark":
        subcommand = args[1] if len(args) > 1 else ""

        # Parse --episodes and --duration flags
        episodes = 10
        duration = 5.0
        for i, arg in enumerate(args[2:], start=2):
            if arg == "--episodes" and i + 1 < len(args):
                try:
                    episodes = int(args[i + 1])
                except ValueError:
                    print(f"Invalid episodes value: {args[i + 1]!r}")
                    sys.exit(1)
            elif arg == "--duration" and i + 1 < len(args):
                try:
                    duration = float(args[i + 1])
                except ValueError:
                    print(f"Invalid duration value: {args[i + 1]!r}")
                    sys.exit(1)

        if subcommand == "locomotion":
            from .benchmarks.locomotion import run_locomotion_benchmark

            run_locomotion_benchmark(n_episodes=episodes, duration_s=duration)
        elif subcommand == "chemotaxis":
            from .benchmarks.chemotaxis import run_chemotaxis_benchmark

            run_chemotaxis_benchmark(n_episodes=episodes, duration_s=duration)
        elif subcommand == "navigation":
            from .benchmarks.navigation import run_navigation_benchmark

            run_navigation_benchmark(n_episodes=episodes, duration_s=duration)
        else:
            print(
                "Usage: python -m digital_drosophila benchmark "
                "<locomotion|chemotaxis|navigation> [--episodes N] [--duration S]\n"
                "\nAvailable benchmarks:\n"
                "  locomotion   Evaluate locomotion controller performance\n"
                "  chemotaxis   Evaluate chemotaxis gradient-following\n"
                "  navigation   Evaluate goal-directed navigation"
            )
            sys.exit(1)

    else:
        print(f"Unknown command: {command!r}. Choose from: simulate, body, loop, learn, demo, benchmark")
        sys.exit(1)


if __name__ == "__main__":
    main()
