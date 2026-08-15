"""Entry point: python -m digital_drosophila simulate <mode>

Usage:
    python -m digital_drosophila simulate minimal
    python -m digital_drosophila simulate constrained
"""

import sys


def main():
    args = sys.argv[1:]

    if not args or args[0] != "simulate":
        print("Usage: python -m digital_drosophila simulate <minimal|constrained>")
        sys.exit(1)

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


if __name__ == "__main__":
    main()
