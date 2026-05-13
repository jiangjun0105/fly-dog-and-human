"""Domain constants for the Digital Drosophila project."""

NT_SIGN_MAP: dict[str, int | None] = {
    "acetylcholine": +1,
    "gaba": -1,
    "glutamate": -1,
    "histamine": -1,
    "dopamine": None,
    "serotonin": None,
    "octopamine": None,
    "unclear": None,
}

NT_COLORS: dict[str, str] = {
    "acetylcholine": "#2ecc71",
    "gaba": "#e74c3c",
    "glutamate": "#3498db",
    "histamine": "#9b59b6",
    "dopamine": "#f39c12",
    "serotonin": "#1abc9c",
    "octopamine": "#e67e22",
    "unclear": "#95a5a6",
}

NT_SIGN_LABELS: dict[int | None, str] = {
    1: "excitatory (+1)",
    -1: "inhibitory (−1)",
    None: "modulatory",
}

DEFAULT_SAMPLE_SIZE = 100


def superclass_category(name: str) -> str:
    s = str(name)
    if "motor" in s:
        return "Motor"
    if "intrinsic" in s:
        return "Intrinsic"
    if "sensory" in s:
        return "Sensory"
    return "Other"
