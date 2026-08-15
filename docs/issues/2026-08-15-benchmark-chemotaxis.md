# Issue 5.2 — Chemotaxis & Odor Navigation Benchmarks

**Parent:** epic5-behavioral-benchmarks
**Depends on:** epic3-sensorimotor-loop
**Priority:** medium

## Problem

Drosophila relies heavily on olfaction for survival (food finding, mate localization,
predator avoidance). Our current sensory encoder handles proprioception only. To evaluate
whether biological network structure provides any advantage for chemotaxis, we need:
1. An olfactory input layer that maps chemical gradients to neural activity
2. Benchmark arenas with odor sources
3. Metrics for gradient-following performance

## Desired Behavior

### Olfactory Model

The fly's olfactory circuit: odorant → olfactory receptor neurons (ORNs) → antennal lobe
(projection neurons, PNs) → higher brain (mushroom body for learning, lateral horn for innate).

Simplified for Phase 1:
- 2 "antennae" (left, right) each with N olfactory channels
- Concentration at antenna position → Poisson firing rate (Weber-Fechner: rate ∝ log(1 + C/C_half))
- Bilateral difference → turning bias (natural chemotaxis algorithm)
- Input injected as current to ascending sensory neurons (repurpose or extend sensory encoder)

### Benchmark Arenas

1. **Point source** — single odor at fixed location, Gaussian diffusion plume
2. **Linear gradient** — uniform concentration gradient across arena (simplest test)
3. **Turbulent plume** — patchy concentration with wind direction (realistic)
4. **Dual source** — two sources at different locations (preference test)
5. **Repellent** — negative valence source the fly should avoid

### Metrics

| Metric | Description | Unit |
|--------|-------------|------|
| Source arrival rate | Fraction of trials where fly reaches source zone | 0-1 |
| Approach time | Time to reach source (successful trials only) | s |
| Path efficiency | Straight-line distance / actual path length | 0-1 |
| Upwind bias | Fraction of movement oriented toward source | 0-1 |
| Cast frequency | Turns per second during search | Hz |
| Turn sharpness toward source | Mean turn angle when turning toward vs away | deg |
| Bilateral comparison | Correlation between L-R antenna difference and turning | r |
| Odor preference index | (time_near_A - time_near_B) / (time_near_A + time_near_B) | -1 to 1 |

### Baselines

1. **Biological connectome** — with olfactory input layer
2. **Random weights** — same topology, scrambled connections
3. **Pure bilateral algorithm** — direct antenna-to-motor mapping (no neural network)
4. **Anosmic control** — same network, zero olfactory input

## Demo

```bash
python -m digital_drosophila benchmark chemotaxis [--arena point_source] [--trials 20]
```

## Key Files to Create

| File | Purpose |
|------|---------|
| `src/digital_drosophila/olfaction.py` | Olfactory model: ORN encoding, antenna positions |
| `src/digital_drosophila/arenas.py` | Odor arena definitions (concentration fields) |
| `src/digital_drosophila/benchmarks/chemotaxis.py` | Chemotaxis benchmark suite |

## Tasks

1. **Task 5.2.1** — Olfactory encoder: bilateral antenna model, concentration → firing rate, Weber-Fechner law
2. **Task 5.2.2** — Arena system: point source with Gaussian plume, linear gradient, arena boundary handling
3. **Task 5.2.3** — Integration: connect olfactory input to sensory encoder, extend CoSimulation for odor
4. **Task 5.2.4** — Chemotaxis metrics: path efficiency, approach time, bilateral correlation
5. **Task 5.2.5** — Advanced arenas: turbulent plume (patchy), dual source, repellent
6. **Task 5.2.6** — Visualization: trajectory plots with concentration overlay, metric comparison

## Acceptance Criteria

- [ ] Olfactory encoder converts 2D concentration field to bilateral neural input
- [ ] Point-source arena: fly with biological weights approaches source better than anosmic control
- [ ] Path efficiency metric computed for all trials
- [ ] Bilateral comparison shows correlation between L-R difference and turning
- [ ] Results JSON + trajectory figures saved to reports/benchmarks/

## Notes

- Real Drosophila chemotaxis uses "run and tumble" with modulated turn probability — our network may produce this emergently from bilateral input asymmetry driving different motor neuron pools.
- Start with 2D (top-down) odor field even though fly walks in 3D — concentration at antenna height.
- Antenna positions: left/right by ~0.2mm from body midline at head position.
- Weber-Fechner: rate = rate_max * log(1 + C/K) / log(1 + C_max/K), where K = half-saturation.
- This may reveal whether the VNC has any innate turning circuits activated by asymmetric input — a genuinely interesting scientific question.
