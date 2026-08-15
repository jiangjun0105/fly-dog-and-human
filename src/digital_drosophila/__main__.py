"""Entry point: python -m digital_drosophila <command> [subcommand]

Usage:
    python -m digital_drosophila simulate minimal
    python -m digital_drosophila simulate constrained
    python -m digital_drosophila simulate full_vnc
    python -m digital_drosophila body verify
    python -m digital_drosophila body locomotion
    python -m digital_drosophila loop motor_test
    python -m digital_drosophila loop closed_loop
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
            "  loop closed_loop                          Run closed-loop co-simulation"
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
        else:
            print(
                "Usage: python -m digital_drosophila loop <motor_test|closed_loop>"
            )
            sys.exit(1)

    else:
        print(f"Unknown command: {command!r}. Choose from: simulate, body, loop")
        sys.exit(1)


if __name__ == "__main__":
    main()
