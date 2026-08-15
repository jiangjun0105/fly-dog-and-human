# Issue 5.3 — Environment Navigation Benchmarks

**Parent:** epic5-behavioral-benchmarks
**Depends on:** 2026-08-15-benchmark-locomotion, 2026-08-15-benchmark-chemotaxis
**Priority:** medium

## Problem

Real flies navigate complex environments with obstacles, gaps, walls, and varying terrain.
Testing only on flat open ground fails to assess whether the neural network produces adaptive
behavior — changing its motor patterns in response to environmental context. This issue tests
the fly's ability to navigate physically challenging environments.

## Desired Behavior

### Test Environments

1. **Open field** — Flat arena with walls (baseline exploration)
2. **Obstacle course** — Small pillars the fly must navigate around
3. **Gap crossing** — Gap in the walking surface the fly must bridge
4. **Corridor maze** — Simple T-maze or Y-maze with dead ends
5. **Uneven terrain** — Sinusoidal bumps or random height field
6. **Phototaxis arena** — Light gradient that can attract/repel

### Metrics

| Metric | Description | Unit |
|--------|-------------|------|
| Area explored | Unique grid cells visited / total cells | 0-1 |
| Wall collision rate | Body-wall contacts per second | Hz |
| Obstacle clearance | Minimum distance to obstacles during navigation | mm |
| Gap crossing success | Fraction of trials crossing the gap | 0-1 |
| Maze solve rate | Fraction reaching maze goal | 0-1 |
| Maze solve time | Time to reach goal (successful trials) | s |
| Terrain adaptability | Speed on uneven / speed on flat | ratio |
| Phototaxis index | (time_in_light - time_in_dark) / total_time | -1 to 1 |
| Path tortuosity | Total path length / displacement | ratio |
| Recovery from perturbation | Time to resume locomotion after push | ms |

### Baselines

1. **Biological connectome** — current network
2. **Random walk** — random actuator noise (null model)
3. **Scripted CPG** — tripod gait with no sensory feedback (reactive baseline)
4. **CPG + reflexes** — tripod gait with simple collision reflexes
5. **After STDP learning** — trained network

### Sensory Requirements

Navigation requires:
- **Contact sensors** — leg tip force/contact (already in FlyGym: contact forces)
- **Proprioception** — joint angles, angular velocities (already encoded)
- **Vision/light** — simplified: light intensity at head position → phototaxis input
- **Antennae** — touch sensors for obstacle detection (FlyGym has antenna collision)

## Demo

```bash
python -m digital_drosophila benchmark navigation [--arena obstacle_course] [--trials 10]
```

## Key Files to Create

| File | Purpose |
|------|---------|
| `src/digital_drosophila/arenas.py` | MuJoCo arena definitions (extend from 5.2) |
| `src/digital_drosophila/benchmarks/navigation.py` | Navigation benchmark suite |
| `src/digital_drosophila/sensors.py` | Extended sensor processing (contact, antenna, light) |

## Tasks

1. **Task 5.3.1** — Arena builder: MuJoCo XML generation for test environments (walls, obstacles, gaps)
2. **Task 5.3.2** — Contact/antenna sensor encoding: leg contact → reflexive input, antenna touch
3. **Task 5.3.3** — Open field exploration: area coverage metric, wall avoidance, path tortuosity
4. **Task 5.3.4** — Obstacle navigation: clearance metric, collision counting, path around obstacles
5. **Task 5.3.5** — Gap crossing & uneven terrain: terrain adaptability, crossing success
6. **Task 5.3.6** — Phototaxis: light gradient encoding, phototaxis index, approach behavior
7. **Task 5.3.7** — Visualization: overhead trajectory heat maps, arena diagrams, metric dashboards

## Acceptance Criteria

- [ ] At least 3 arena types functional (open field, obstacles, uneven terrain)
- [ ] Area exploration metric shows biological network explores more than random walk
- [ ] Obstacle collision rate differs between controllers (CPG vs neural vs random)
- [ ] Contact sensors produce measurable response in neural activity
- [ ] Arena visualizations: overhead trajectory plots with obstacle outlines
- [ ] Results JSON + figures saved to reports/benchmarks/

## Notes

- FlyGym supports custom arena XML — we can add boxes, cylinders, heightfields directly.
- The fly's antenna contact detection is built into the FlyGym model.
- This is the most ambitious benchmark — some arenas may need physics tuning.
- Gap crossing is genuinely hard for a 100-neuron network — don't expect success, just measure.
- Phototaxis is interesting because descending neurons in the real fly carry light-driven commands to VNC.
- Start with the simplest arenas (open field, single obstacle) and add complexity.
- The scientific value: does biological topology produce any proto-reflexive behavior (obstacle avoidance from contact feedback) without explicit learning?
