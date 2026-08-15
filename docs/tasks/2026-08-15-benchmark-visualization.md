---
id: 2026-08-15-benchmark-visualization
title: "Benchmark visualization: comparison charts, gait diagrams, learning curves"
created: 2026-08-15T20:00
status: open
priority: medium
type: task
suitability: auto_agent_ready
depends_on:
  - 2026-08-15-benchmark-locomotion-metrics
  - 2026-08-15-benchmark-baselines
related:
  - 2026-08-15-benchmark-gait-analysis
satisfies:
  - 2026-08-15-benchmark-locomotion
branch: ""
pr: ""
auto_agent_task_id: ""
---

# Benchmark visualization: comparison charts, gait diagrams, learning curves

## Context

Benchmark results need clear visualizations for interpretation and potential publication.
This task creates reusable plotting functions for all Epic 5 benchmarks.

## Problem

Raw metrics dictionaries are useful for automation but hard for humans to interpret.
We need standardized plots that make controller comparisons obvious at a glance.

## Desired Behavior

### Plot Types

1. **Metric comparison bar chart** — grouped bars, one group per metric, one bar per controller, with error bars (±1 std)
2. **Radar/spider plot** — all metrics on radial axes, one polygon per controller (overview)
3. **Gait phase diagram** — one row per leg, colored bars for stance/swing (ethogram-style)
4. **Trajectory plot** — overhead XY path with start/end markers
5. **Learning curve** — metric vs episode number (for STDP comparison)
6. **Distribution violin/box** — per-episode metric distributions across controllers

### Output

All plots saved to `reports/benchmarks/` with descriptive names:
- `locomotion_comparison.png` — bar chart across controllers
- `locomotion_radar.png` — radar overview
- `gait_ethogram_<controller>.png` — gait diagrams
- `trajectory_overlay.png` — all controller paths overlaid

### Style

- Matplotlib with consistent color scheme (one color per controller)
- Publication-quality: labeled axes, legends, tight layout
- Colorblind-safe palette (tab10 or similar)
- DPI 150 for reports, vector PDF optional

## Key Files

| File | Purpose |
|------|---------|
| `src/digital_drosophila/benchmarks/plotting.py` | All benchmark visualization |

## Suggested API

```python
def plot_metric_comparison(results: list[BenchmarkResult], 
                          metrics: list[str] = None,
                          output_path: Path = None) -> None:
    """Bar chart comparing metrics across controllers."""

def plot_gait_ethogram(leg_contacts: np.ndarray, dt: float,
                       title: str = "", output_path: Path = None) -> None:
    """Stance/swing diagram for 6 legs over time."""

def plot_trajectory_overlay(trajectories: dict[str, np.ndarray],
                           output_path: Path = None) -> None:
    """Overhead XY paths for multiple controllers."""

def plot_radar(results: list[BenchmarkResult], 
              metrics: list[str], output_path: Path = None) -> None:
    """Spider/radar plot of normalized metrics."""
```

## Acceptance Criteria

- [ ] Bar chart renders for 3+ controllers × 5+ metrics
- [ ] Error bars correctly show ±1 std from per-episode data
- [ ] Gait ethogram clearly shows stance/swing periods for 6 legs
- [ ] Trajectory plot distinguishes controllers by color
- [ ] All plots save to PNG without errors
- [ ] Works with BenchmarkResult objects from Task 5.1.1

## Notes

- Import matplotlib only inside functions (heavy dep, don't slow module imports)
- Use `plt.style.use('seaborn-v0_8-whitegrid')` for clean look
- Controller color map: biological=blue, random=orange, cpg=green, zero=gray, noise=red
- For radar plots, normalize each metric to [0, 1] range across controllers
- Gait ethogram: similar to published Drosophila papers (DeAngelis et al.)
