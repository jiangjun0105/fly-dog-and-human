from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Protocol


class Controller(Protocol):
    def reset(self) -> None: ...
    def step(self) -> None: ...
    @property
    def done(self) -> bool: ...
    def get_metrics(self) -> dict[str, float]: ...
    def close(self) -> None: ...


@dataclass
class BenchmarkResult:
    benchmark_name: str
    controller_name: str
    episodes: int
    duration_s: float
    scalar_metrics: dict[str, float] = field(default_factory=dict)
    metric_stds: dict[str, float] = field(default_factory=dict)
    per_episode: list[dict[str, float]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = asdict(self)
        # Convert any numpy arrays/scalars to plain Python types
        data = _sanitize_for_json(data)
        path.write_text(json.dumps(data, indent=2))

    @classmethod
    def from_json(cls, path: str | Path) -> BenchmarkResult:
        data = json.loads(Path(path).read_text())
        return cls(**data)

    def summary_table(self) -> str:
        lines = [
            f"Benchmark: {self.benchmark_name}",
            f"Controller: {self.controller_name}",
            f"Episodes: {self.episodes}  Duration: {self.duration_s:.2f}s",
            "",
            f"{'Metric':<30} {'Mean':>12} {'Std':>12}",
            "-" * 56,
        ]
        for key, mean in self.scalar_metrics.items():
            std = self.metric_stds.get(key, 0.0)
            lines.append(f"{key:<30} {mean:>12.4f} {std:>12.4f}")
        return "\n".join(lines)


class BenchmarkRunner:
    def __init__(
        self,
        controller_factory: Callable[[], Controller],
        metric_fn: Callable[[Controller], dict[str, float]] | None = None,
        controller_name: str = "unnamed",
    ):
        self._factory = controller_factory
        self._metric_fn = metric_fn
        self._controller_name = controller_name

    def run(self, benchmark_name: str, n_episodes: int = 10) -> BenchmarkResult:
        per_episode: list[dict[str, float]] = []
        t0 = time.perf_counter()

        for _ in range(n_episodes):
            ctrl = self._factory()
            ctrl.reset()

            while not ctrl.done:
                ctrl.step()

            if self._metric_fn is not None:
                metrics = self._metric_fn(ctrl)
            else:
                metrics = ctrl.get_metrics()

            per_episode.append(metrics)
            ctrl.close()

        duration_s = time.perf_counter() - t0

        scalar_metrics, metric_stds = _aggregate(per_episode)

        return BenchmarkResult(
            benchmark_name=benchmark_name,
            controller_name=self._controller_name,
            episodes=n_episodes,
            duration_s=duration_s,
            scalar_metrics=scalar_metrics,
            metric_stds=metric_stds,
            per_episode=per_episode,
        )


def _aggregate(
    per_episode: list[dict[str, float]],
) -> tuple[dict[str, float], dict[str, float]]:
    if not per_episode:
        return {}, {}

    keys = per_episode[0].keys()
    means: dict[str, float] = {}
    stds: dict[str, float] = {}

    for key in keys:
        values = [ep[key] for ep in per_episode if key in ep]
        n = len(values)
        if n == 0:
            continue
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / n
        means[key] = mean
        stds[key] = variance**0.5

    return means, stds


def _sanitize_for_json(obj: Any) -> Any:
    """Recursively convert numpy types to plain Python for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    # Handle numpy scalar types without importing numpy at module level
    type_name = type(obj).__module__
    if type_name == "numpy":
        if hasattr(obj, "tolist"):
            return obj.tolist()
    return obj
