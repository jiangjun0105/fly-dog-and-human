# Issues

## Active Epics

### Phase 1: From Connectome Data to Learning Locomotion

**[epic-phase1-implementation.md](epic-phase1-implementation.md)** — Top-level container

| # | Epic | Depends On | Status |
|---|------|-----------|--------|
| 1 | [Brian2 Neural Network](epic1-brian2-network.md) | — | Not started |
| 2 | [MuJoCo + NeuroMechFly](epic2-mujoco-neuromechfly.md) | — | Not started |
| 3 | [Sensorimotor Loop](epic3-sensorimotor-loop.md) | 1, 2 | Not started |
| 4 | [Learning & Locomotion](epic4-learning-locomotion.md) | 3 | Not started |

```
Epic 1 (Brian2) ──┐
                   ├──▶ Epic 3 (Integration) ──▶ Epic 4 (Learning)
Epic 2 (MuJoCo) ──┘
```

Epics 1 and 2 are parallelizable. Start both now.

---

### Epic 1 — Brian2 Neural Network (decomposed)

| # | Issue | Demo | Status |
|---|-------|------|--------|
| 1.1 | [Minimal firing network (100 neurons)](2026-08-15-brian2-minimal-network.md) | Run script → raster plot with spikes | Not started |
| 1.2 | [Biological constraints](2026-08-15-brian2-biological-constraints.md) | Color-coded raster by superclass, rates in range | Not started |
| 1.3 | [Full VNC scale + burn-in](2026-08-15-brian2-full-scale.md) | 15k neurons on GPU, steady-state validation | Not started |

```
1.1 (minimal) → 1.2 (bio constraints) → 1.3 (full scale)
```
