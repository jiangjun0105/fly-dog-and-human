---
id: 2026-08-15-arena-system
title: "Arena system: odor fields, obstacle geometries, terrain definitions"
created: 2026-08-15T20:30
status: open
priority: medium
type: task
suitability: auto_agent_ready
depends_on: []
related:
  - 2026-08-15-olfactory-encoder
satisfies:
  - 2026-08-15-benchmark-chemotaxis
  - 2026-08-15-benchmark-navigation
branch: ""
pr: ""
auto_agent_task_id: ""
---

# Arena system: odor fields, obstacle geometries, terrain definitions

## Context

Benchmarks need test environments. This task creates a library of arenas that provide:
- Concentration fields for chemotaxis
- Physical obstacles for navigation
- Various terrain types

## Problem

All current simulations run on flat, featureless terrain with no environmental stimuli.

## Desired Behavior

### Concentration Fields (for chemotaxis)

Callable objects that return concentration at any 2D position:

1. **PointSource** — Gaussian plume from a single point
   - `C(r) = C_max * exp(-r² / (2σ²))` where r = distance to source
2. **LinearGradient** — Uniform gradient in one direction
   - `C(x,y) = C_max * (x - x_min) / (x_max - x_min)` for x-axis gradient
3. **TurbulentPlume** — Patchy/intermittent concentration (Perlin noise modulated Gaussian)
4. **DualSource** — Two point sources at different locations

### Physical Arenas (for navigation)

MuJoCo XML snippets that can be composed with the fly model:

1. **FlatArena** — Open flat surface with walls (default)
2. **ObstacleArena** — Cylindrical pillars at specified positions
3. **CorridorArena** — Narrow corridor with optional turns
4. **UnevenTerrain** — Heightfield-based bumpy surface

### Interface

```python
class ConcentrationField(Protocol):
    def __call__(self, pos_xy: np.ndarray) -> float: ...
    @property
    def source_position(self) -> np.ndarray: ...

class Arena:
    name: str
    size_mm: tuple[float, float]
    
    def get_concentration_field(self) -> ConcentrationField | None: ...
    def get_mujoco_xml_snippet(self) -> str | None: ...
```

## Key Files

| File | Purpose |
|------|---------|
| `src/digital_drosophila/arenas.py` | Arena definitions and concentration fields |

## Acceptance Criteria

- [ ] PointSource returns concentration that decreases with distance from source
- [ ] LinearGradient produces monotonically increasing values along gradient axis
- [ ] All concentration fields are callable with 2D position → float
- [ ] source_position property returns the goal location
- [ ] FlatArena provides default arena bounds (10mm × 10mm)
- [ ] At least 3 concentration field types working

## Notes

- Start with concentration fields only (physical arenas with MuJoCo XML are harder, defer)
- Concentration clipped to [0, 1] range for simplicity
- Point source sigma ~2-3mm gives reasonable gradient over fly body scale
- Arena size: real fly arena is ~10-50mm. Start with 10mm diameter.
- Physical arenas (obstacles, terrain) are for Issue 5.3 — OK to stub those here.
- Keep arenas pure math (no heavy deps) so they're fast to evaluate each timestep.
