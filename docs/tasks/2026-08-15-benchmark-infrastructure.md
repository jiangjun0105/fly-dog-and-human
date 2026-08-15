---
id: 2026-08-15-benchmark-infrastructure
title: "Benchmark infrastructure: BenchmarkResult, metrics utilities, CLI"
created: 2026-08-15T20:00
status: open
priority: high
type: task
suitability: auto_agent_ready
depends_on: []
related: []
satisfies:
  - 2026-08-15-benchmark-locomotion
branch: ""
pr: ""
auto_agent_task_id: ""
---

# Benchmark infrastructure: BenchmarkResult, metrics utilities, CLI

## Context

Epic 5 (Behavioral Benchmarks) needs a common framework for running benchmarks,
collecting metrics, and producing reports. This task creates the shared infrastructure
that all benchmarks will use.

## Problem

No standardized way to run, record, or compare benchmark results across different
test conditions and controllers.

## Desired Behavior

1. A `BenchmarkResult` dataclass that holds:
   - benchmark_name, controller_name, timestamp, duration_s
   - scalar_metrics: dict[str, float]
   - timeseries: dict[str, np.ndarray] (optional, for plots)
   - metadata: dict (parameters, seeds, versions)
2. A `BenchmarkRunner` that:
   - Runs N episodes with a given controller
   - Collects metrics per episode
   - Computes mean ± std across episodes
   - Saves results to JSON
3. CLI integration: `python -m digital_drosophila benchmark <suite>` dispatcher
4. JSON serialization: results → reproducible records in `reports/benchmarks/`
5. Comparison utilities: load multiple results, produce comparison tables

## Key Files to Create

| File | Purpose |
|------|---------|
| `src/digital_drosophila/benchmarks/__init__.py` | Package exports |
| `src/digital_drosophila/benchmarks/common.py` | BenchmarkResult, BenchmarkRunner |
| `src/digital_drosophila/benchmarks/plotting.py` | Generic comparison charts |

## Suggested Implementation

```python
from dataclasses import dataclass, field
from typing import Any
import json
import numpy as np
from pathlib import Path

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

    def to_json(self, path: Path):
        ...

    @classmethod
    def from_json(cls, path: Path):
        ...

    def summary_table(self) -> str:
        ...


class BenchmarkRunner:
    def __init__(self, benchmark_fn, controller_factory, n_episodes=10, 
                 episode_duration_s=5.0, seed=42):
        ...

    def run(self) -> BenchmarkResult:
        ...
```

## CLI Extension

Add to `__main__.py`:
```python
elif command == "benchmark":
    subcommand = args[1] if len(args) > 1 else ""
    if subcommand == "locomotion":
        from .benchmarks.locomotion import run_locomotion_benchmark
        run_locomotion_benchmark(...)
```

## Acceptance Criteria

- [ ] `BenchmarkResult` dataclass with serialization to/from JSON
- [ ] `BenchmarkRunner` executes N episodes, computes stats
- [ ] CLI `python -m digital_drosophila benchmark` shows usage
- [ ] `reports/benchmarks/` directory created on first run
- [ ] Comparison table formatter works for side-by-side display
- [ ] Unit-testable: BenchmarkResult round-trips through JSON

## Notes

- Keep it minimal — don't over-engineer. The value is in the benchmarks themselves.
- numpy arrays in timeseries should be saved as lists in JSON (or use separate .npz files)
- Seeds passed through for reproducibility
- This is infrastructure, so make it import-clean (no heavy deps at module level)
