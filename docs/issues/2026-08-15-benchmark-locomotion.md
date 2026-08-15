# Issue 5.1 — Locomotion Benchmarks

**Parent:** epic5-behavioral-benchmarks
**Depends on:** epic3-sensorimotor-loop
**Priority:** high

## Problem

We have a neural-driven fly that moves, but we lack quantitative characterization of its
locomotion. Without benchmarks we cannot:
- Know how far from biological performance we are
- Measure whether learning improves things
- Compare biological vs random topology meaningfully

## Desired Behavior

A benchmark suite that runs the fly through standardized locomotion tests and produces:

### Metrics

| Metric | Description | Unit |
|--------|-------------|------|
| Forward speed | Mean displacement / time | mm/s |
| Lateral deviation | RMS lateral displacement from straight-line path | mm |
| Energy efficiency | Forward distance / total actuator energy | mm/J |
| Gait regularity | Autocorrelation periodicity of leg phases | 0-1 |
| Stance stability | Fraction of time ≥3 legs on ground | 0-1 |
| Tripod coordination index | Phase coherence between alternating leg groups | 0-1 |
| Turn bias | Net angular displacement over trial | deg/s |
| Step frequency | Dominant frequency from leg contact pattern | Hz |
| Fall rate | Episodes where body contacts ground / total episodes | fraction |

### Baselines to Compare

1. **Biological weights** — the connectome-derived network (current state)
2. **Random weights** — same topology, shuffled weight magnitudes, signs preserved
3. **Zero weights** — network with no synaptic transmission (pure noise baseline)
4. **Scripted CPG** — deterministic tripod gait (upper bound for gait metrics)
5. **After STDP** — network after N episodes of reward-modulated learning

### Test Conditions

1. **Flat terrain** — standard locomotion (primary benchmark)
2. **Inclined plane** — 5° and 10° slopes (tests force generation)
3. **Variable friction** — smooth vs rough surface
4. **Extended duration** — 30s trials to test stability over time

## Demo

```bash
python -m digital_drosophila benchmark locomotion [--episodes 10] [--duration 5.0]
```

Output:
```
Locomotion Benchmark Results (10 episodes × 5.0s each)
═══════════════════════════════════════════════════════
                    Biological   Random    CPG      Zero
Forward speed       0.42±0.12   0.08±0.05  4.42    0.01±0.01  mm/s
Lateral deviation   0.31±0.15   0.89±0.34  0.02    0.92±0.41  mm
Gait regularity     0.23±0.08   0.05±0.03  0.97    0.02±0.02
Stance stability    0.78±0.09   0.51±0.15  0.99    0.44±0.20
...

Report saved: reports/benchmarks/locomotion_results.json
Figures saved: reports/benchmarks/locomotion_*.png
```

## Key Files to Create

| File | Purpose |
|------|---------|
| `src/digital_drosophila/benchmarks/__init__.py` | Benchmark package |
| `src/digital_drosophila/benchmarks/locomotion.py` | Locomotion benchmark suite |
| `src/digital_drosophila/benchmarks/common.py` | BenchmarkResult, metrics utilities |
| `src/digital_drosophila/benchmarks/baselines.py` | Baseline controllers (random, zero, CPG) |

## Tasks (skateboard → bicycle → car)

1. **Task 5.1.1** — Benchmark infrastructure: `BenchmarkResult` dataclass, metric computation utilities, JSON serialization, CLI hook
2. **Task 5.1.2** — Core locomotion metrics: speed, deviation, stability, energy from CoSimulation episodes
3. **Task 5.1.3** — Baseline controllers: random-weight network builder, zero-weight variant, CPG wrapper
4. **Task 5.1.4** — Gait analysis: leg phase extraction, autocorrelation, tripod coordination index, step frequency
5. **Task 5.1.5** — Visualization: learning curves, metric comparison bar charts, gait phase diagrams
6. **Task 5.1.6** — Extended conditions: incline, friction, duration sweeps

## Acceptance Criteria

- [ ] `python -m digital_drosophila benchmark locomotion` runs 10 episodes and prints metrics
- [ ] At least 5 scalar metrics computed (speed, deviation, stability, energy, gait regularity)
- [ ] Biological network outperforms zero-weight baseline on forward speed
- [ ] CPG outperforms all neural controllers (expected — validates metrics are correct)
- [ ] Results saved to JSON for downstream analysis
- [ ] Comparison figure saved to reports/benchmarks/

## Notes

- Episode length of 5s balances runtime (~250s per episode) against statistical stability
- The biological network may not walk well yet — that's fine! The benchmark establishes the baseline that learning (Epic 4) should improve.
- Real Drosophila walks at ~20-30 mm/s. Our simplified 100-neuron model won't match that, but should exceed random.
- Energy metric: sum of |Δactuator_position| per step as proxy for metabolic cost.
