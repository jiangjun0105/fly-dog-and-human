"""Entry point: python -m digital_drosophila <command> [subcommand]

Usage:
    python -m digital_drosophila simulate minimal
    python -m digital_drosophila simulate constrained
    python -m digital_drosophila body verify
    python -m digital_drosophila body locomotion
"""

import sys


def main():
    args = sys.argv[1:]

    if not args:
        print(
            "Usage: python -m digital_drosophila <command> [subcommand]\n"
            "\nCommands:\n"
            "  simulate <minimal|constrained>   Run SNN simulation\n"
            "  body verify                      Verify MuJoCo/FlyGym installation\n"
            "  body locomotion                  Run scripted locomotion demo"
        )
        sys.exit(1)

    command = args[0]

    if command == "simulate":
        mode = args[1] if len(args) > 1 else "constrained"

        from .simulate import run_minimal, run_constrained

        modes = {
            "minimal": run_minimal,
            "constrained": run_constrained,
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

    else:
        print(f"Unknown command: {command!r}. Choose from: simulate, body")
        sys.exit(1)


if __name__ == "__main__":
    main()
