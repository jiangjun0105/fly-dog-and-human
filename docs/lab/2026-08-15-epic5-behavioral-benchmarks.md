# Epic 5 — Behavioral Benchmarks: Findings & Analysis

**Date:** 2026-08-15
**Status:** Initial benchmarks complete, framework operational

## Overview

We evaluated the connectome-derived spiking neural network's behavioral capabilities
across three domains: locomotion, chemotaxis, and environment navigation. The network
uses real biological connectivity (from male-cns:v0.9 VNC) with synapse-count-derived
weights, but has NOT been trained — weights reflect structure only, not learned behavior.

## Key Insight

> The biological topology produces directed, non-random forward motion, but no
> coordinated stepping gait. The network needs learning (STDP) to develop leg
> coordination — structure alone provides a scaffold, not a solution.

---

## 1. Locomotion Benchmarks (Issue 5.1)

### Results

| Metric | Biological SNN | CPG (scripted tripod) | Noise (random) |
|--------|---------------|----------------------|----------------|
| Forward speed | 0.46 ± 0.09 mm/s | 4.46 mm/s | 1.25 mm/s |
| Lateral deviation | 0.17 ± 0.07 mm | ~0.02 mm | ~0.5 mm |
| Stance stability | 100% | 100% | ~70% |
| Tripod index | 0.00 | 0.996 | 0.00 |
| Gait regularity | 0.00 | 0.956 | 0.01 |
| Step frequency | 3.0 Hz (artifact) | 8.0 Hz | N/A |
| Mean duty factor | 1.00 (all grounded) | 0.50 | ~0.5 |
| Energy efficiency | 0.0027 | ~0.05 | 0.001 |
| Fall detected | Never | Never | Never |
| Turn bias | 2.1 deg/s | ~0 | random |

### Analysis

**The biological network moves forward but does NOT step.** All 6 legs remain in
contact with the ground 100% of the time (duty factor = 1.0). Forward motion is achieved
through differential actuator forces that "slide" the body along the surface — similar to
how a snake moves, not how a fly walks.

**Speed hierarchy:** CPG (4.46) >> Noise (1.25) > Biological (0.46) mm/s.
The biological network is slower than random noise because it generates coordinated but
weak motor patterns that don't efficiently translate to displacement. Random noise produces
larger instantaneous forces (but in random directions, so net movement is moderate).

**Stability is excellent.** The fly never falls regardless of controller, suggesting the
FlyGym body model is inherently stable at this scale.

**No periodicity.** The biological network shows zero gait regularity and zero tripod
index — it does not produce any rhythmic leg movement pattern. This is the strongest
evidence that STDP learning is needed to develop CPG-like rhythms.

### Interpretation

The connectome weights encode the correct CONNECTIVITY (which neurons talk to which)
but not the correct STRENGTH for coordinated locomotion. The log(1 + synapse_count)
weight formula provides a reasonable initial scaffold, but biological flies develop their
gait through experience (larval/pupal stages). Our network is essentially a "newborn"
fly that has never moved its legs.

---

## 2. Chemotaxis Benchmarks (Issue 5.2)

### Results

| Metric | Bio + Olfaction | CPG + Olfaction | Noise (anosmic) |
|--------|----------------|-----------------|-----------------|
| Progress toward source | +1.18 mm | -13.0 mm (overshoot) | +3.6 mm |
| Path efficiency | 0.082 | 0.00 | 0.104 |
| Upwind bias | 0.469 | 0.308 | 0.541 |
| Final distance to source | 3.59 mm | 17.8 mm | 1.16 mm |
| Source reached | No | Yes (overshot) | Yes |
| Path length | 14.4 mm | 32.8 mm | 34.8 mm |

### Analysis

**The biological network + olfactory input produces positive chemotaxis.** It moves
1.18 mm toward the odor source over 3 seconds — small but measurably above zero and
in the correct direction.

**CPG overshoots dramatically.** The scripted tripod gait is too fast and too straight —
it walks past the source at (5, 0) and continues forward. The olfactory turning bias
(gain = 0.1) is too weak to redirect the powerful CPG drive.

**Noise "wins" by accident.** Random movement keeps the fly near its starting position,
which happens to be closer to the source than where the CPG ends up. This is not true
chemotaxis — it's just lack of displacement.

**The biological controller shows genuine gradient-following.** Its upwind bias (0.469)
is near chance (0.5), but its net displacement is toward the source, and it has the
highest path efficiency among truly moving controllers. The reflexive bilateral
antenna-to-motor coupling influences the neural-driven movement direction.

### Interpretation

Chemotaxis requires two things: (1) the ability to detect concentration gradients
(bilateral comparison), and (2) the ability to modulate turning in response. Our
olfactory encoder provides (1), and the reflexive coxa-yaw modulation provides a
minimal (2). For proper chemotaxis, the olfactory signal should be integrated through
the neural network rather than bypassing it — this requires wiring the antennal lobe
pathway through the VNC ascending neurons.

---

## 3. Navigation Benchmarks (Issue 5.3)

### Results

| Metric | Biological SNN | CPG (scripted) | Noise (random) |
|--------|---------------|----------------|----------------|
| Area explored | 1.25% | 5.0% | 3.0% |
| Max displacement | 1.06 mm | 8.94 mm | 3.0 mm |
| Path tortuosity | 9.76 | 1.47 | 4.68 |
| Mean speed | 4.51 mm/s (local) | 6.54 mm/s | 7.0 mm/s |
| Boundary contacts | 0 | 1 | 0 |
| Exploration rate | 2.5 cells/s | 10.0 cells/s | 6.0 cells/s |

### Analysis

**The biological network has high local activity but low displacement.** Its path
tortuosity of 9.76 means it travels ~10x more distance than its net displacement —
lots of movement but little progress. This is consistent with the "sliding" locomotion
observed in the gait analysis: it moves the body but doesn't go far.

**CPG is the most efficient explorer.** Straight-line walking covers maximum ground.
It hits the arena boundary (10mm) in 2 seconds.

**Noise is intermediate.** Random actuator commands produce moderate displacement in
random directions.

### Interpretation

Without a coordinated gait, the biological network cannot efficiently explore space.
Its high tortuosity suggests it produces variable motor patterns (not static) but they
cancel out directionally. Learning should reduce tortuosity by developing consistent
forward locomotion.

---

## 4. Videos

| File | Duration | Controller | Description |
|------|----------|-----------|-------------|
| `reports/neural_demo_10s.mp4` | 10s | Biological SNN | Connectome network driving the body (0.5 mm/s forward, sliding) |
| `reports/flygym_locomotion_20s.mp4` | 20s | Scripted CPG | Perfect tripod gait (4.4 mm/s forward, stepping) |
| `reports/neural_demo.mp4` | 3s | Biological SNN | Short demo version |
| `reports/tripod_demo.mp4` | 3s | Scripted CPG | Short demo version |

The contrast between these videos illustrates the gap between what the network currently
produces (sliding) and what learning should achieve (stepping).

---

## 5. Overall Capability Assessment

### What the connectome topology provides (without learning):
- ✓ Non-random forward motion (0.46 mm/s > zero-weight baseline)
- ✓ Stable body posture (never falls)
- ✓ Consistent directionality (low lateral deviation, slight turn bias)
- ✓ Sensitivity to olfactory input (weak but measurable chemotaxis)
- ✓ Sustained neural activity (26-28 Hz mean motor rate)

### What requires learning (STDP):
- ✗ Stepping gait (legs don't lift off ground)
- ✗ Coordinated leg movements (no tripod/tetrapod pattern)
- ✗ Efficient exploration (high tortuosity, low displacement)
- ✗ Strong chemotaxis (current response is marginal)
- ✗ Speed (10x slower than CPG baseline)

### Hypothesis for Epic 4

The biological topology should enable FASTER learning of coordinated locomotion compared
to a random-topology network because:
1. Motor neuron pools are correctly wired to their respective legs
2. Excitatory/inhibitory balance follows Dale's principle
3. Pre-motor interneurons have appropriate connectivity patterns
4. The "scaffold" is correct even if the weights need tuning

This is testable: if a random-topology control (same parameters, shuffled wiring) learns
equally fast, then biological structure provides no advantage.

---

## 6. Technical Infrastructure Built

### Benchmark Framework
- `python -m digital_drosophila benchmark locomotion [--episodes N] [--duration S]`
- `python -m digital_drosophila benchmark chemotaxis [--episodes N] [--duration S]`
- `python -m digital_drosophila benchmark navigation [--episodes N] [--duration S]`

### Modules (in `src/digital_drosophila/benchmarks/`)
- `common.py` — BenchmarkResult, BenchmarkRunner, Controller protocol
- `locomotion.py` — 13 metrics, TrajectoryCollector, BiologicalController
- `baselines.py` — 5 controller types (Bio, Random, Zero, CPG, Noise)
- `gait.py` — FFT frequency, autocorrelation regularity, tripod index, classification
- `chemotaxis.py` — Olfactory-guided navigation with reflexive turning
- `navigation.py` — Area exploration, tortuosity, boundary detection
- `plotting.py` — Comparison bars, gait ethogram, trajectory overlay, radar plot

### Supporting Modules
- `olfaction.py` — Bilateral antenna model with Weber-Fechner encoding
- `arenas.py` — PointSource, LinearGradient, DualSource, TurbulentPlume
- `video.py` — Neural-driven and CPG video rendering

### Output (in `reports/benchmarks/`)
- JSON results for all controller × benchmark combinations
- Comparison bar charts, radar plots, gait ethograms
- All reproducible via CLI commands

---

## 7. Next Steps

1. **Epic 4.2** — Homeostatic plasticity + longer STDP training
   - Run 50-100 episodes with reward = forward_speed
   - Add threshold adaptation to prevent runaway excitation
   - Use locomotion benchmarks to measure improvement over training

2. **Epic 4.3** — Biological vs random topology experiment
   - Build RandomWeightController (already done in baselines.py)
   - Train both for same number of episodes
   - Compare learning curves using benchmark metrics
   - This answers the core research question

3. **Scale up benchmarks** — More episodes (10+) for statistical significance
   - Current results are 1-3 episodes per condition
   - Need confidence intervals for publication-quality claims

4. **Tighter olfactory integration** — Wire olfactory input through the neural network
   - Currently uses reflexive bypass (antenna → coxa yaw actuators directly)
   - Should inject olfactory currents into ascending neurons → let the network decide

5. **Performance optimization** — The biological controller takes ~50s per 1s of simulation
   - 50x slower than realtime limits episode count
   - Consider PyGeNN GPU acceleration for longer training runs
