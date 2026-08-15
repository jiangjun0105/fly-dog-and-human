# EPIC — Behavioral Benchmarks & Capability Evaluation

**EPIC — container, do not execute; work lives in child issues.**

**Parent:** epic-phase1-implementation
**Depends on:** epic3-sensorimotor-loop (locomotion benchmarks), epic4-learning-locomotion (learned vs naive comparison)

## Epic Demo

Run a comprehensive evaluation suite that characterizes what the connectome-derived spiking
network can do: locomotion efficiency, chemotaxis performance, and environment navigation.
Produce quantitative benchmark results with visualizations suitable for publication figures.

## Motivation

Phase 1 proved the pipeline works. Before investing in longer training (Epic 4.2/4.3), we
need to understand the current network's baseline capabilities — what emerges from biological
structure alone, and where learning is needed. This also establishes evaluation infrastructure
that Epic 4's experiments will reuse.

## Children (value-sliced: skateboard → bicycle → car)

1. **[Skateboard — Locomotion Benchmarks](2026-08-15-benchmark-locomotion.md)**: Speed, efficiency, stability, gait analysis. Compare neural-driven vs scripted CPG vs random-weight network.
2. **[Bicycle — Chemotaxis & Odor Navigation](2026-08-15-benchmark-chemotaxis.md)**: Add olfactory input layer, gradient-following task, source localization, multi-odor discrimination.
3. **[Car — Environment Navigation](2026-08-15-benchmark-navigation.md)**: Obstacle avoidance, gap crossing, phototaxis, open-field exploration with diverse arena geometries.

## Dependency Spine

```
Issue 5.1 (Locomotion) ──┐
                         ├──▶ Issue 5.3 (Navigation) 
Issue 5.2 (Chemotaxis) ──┘
```

Issues 5.1 and 5.2 are parallelizable (independent sensory modalities). Issue 5.3 combines them in complex environments.

## Key Design Decisions

- **Metrics framework**: Each benchmark returns a standardized dict with scalar metrics + time-series data. All benchmarks share a `BenchmarkResult` dataclass.
- **Baselines**: Every benchmark compares at minimum: (a) biological connectome weights, (b) random-weight same-topology, (c) scripted/CPG controller where applicable.
- **Olfactory model**: Use connectome's antennal lobe → mushroom body pathway. Simplified odor = chemical concentration gradient as Poisson rate modulation.
- **Arena system**: FlyGym supports custom terrain via MuJoCo XML. Build a library of test arenas.
- **Episode-based**: All benchmarks use CoSimulation episode API for consistency.
- **Reproducibility**: Fixed seeds, parameter sweeps logged to JSON, plots regenerated from data.

## Success Criteria

1. Locomotion benchmark produces speed/efficiency/stability metrics with error bars across 10+ episodes
2. Chemotaxis benchmark shows the fly can follow a gradient (even weakly) with biological structure
3. Navigation benchmark demonstrates obstacle-dependent behavior changes
4. All results compared against meaningful baselines
5. Report with figures saved to `reports/benchmarks/`

## Key References

- `docs/neuroscience/01-architecture-overview.md` — VNC sensory/motor layout
- `docs/neuroscience/02-neuron-parameters.md` — neuron type properties
- FlyGym documentation: terrain API, sensor specification
- Drosophila chemotaxis literature: Álvarez-Salvado et al. 2018, Demir et al. 2020
