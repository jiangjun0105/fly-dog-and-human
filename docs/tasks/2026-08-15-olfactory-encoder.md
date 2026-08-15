---
id: 2026-08-15-olfactory-encoder
title: "Olfactory encoder: bilateral antenna model, concentration to firing rate"
created: 2026-08-15T20:30
status: open
priority: medium
type: task
suitability: auto_agent_ready
depends_on: []
related: []
satisfies:
  - 2026-08-15-benchmark-chemotaxis
branch: ""
pr: ""
auto_agent_task_id: ""
---

# Olfactory encoder: bilateral antenna model, concentration to firing rate

## Context

The Digital Drosophila has proprioceptive input but no olfactory sense. Real flies have
bilateral antennae that detect chemical concentrations, and the left-right difference
drives turning behavior (chemotaxis). This task adds olfactory input capability.

## Problem

No way to inject odor information into the spiking neural network. Without this, we
cannot test chemotaxis — a fundamental Drosophila behavior.

## Desired Behavior

1. A `OlfactoryEncoder` class that:
   - Models 2 antennae (left, right) positioned at the fly's head
   - Given a concentration field and fly position/heading, computes concentration at each antenna
   - Converts concentration → firing rate using Weber-Fechner law
   - Outputs current injection values for sensory neurons (pA)
   
2. Integration with CoSimulation:
   - OlfactoryEncoder can extend or compose with SensoryEncoder
   - Provides bilateral current injection each coupling step

## Implementation

```python
class OlfactoryEncoder:
    def __init__(self, n_channels=2, antenna_separation_mm=0.2,
                 rate_max_hz=200, half_saturation=0.1,
                 current_scale_pa=500e-12):
        self.n_channels = n_channels  # independent odor channels
        self.antenna_sep = antenna_separation_mm
        self.rate_max = rate_max_hz
        self.K = half_saturation
        self.scale = current_scale_pa

    def get_antenna_positions(self, fly_pos_xy, heading_rad):
        """Compute left/right antenna world positions from fly pose."""
        # Antennae are antenna_sep/2 to each side of head, 
        # rotated by heading angle
        ...

    def encode(self, concentration_field, fly_pos_xy, heading_rad):
        """Convert concentration at antennae to neural input currents.
        
        Returns dict: {"left": current_pA, "right": current_pA}
        """
        left_pos, right_pos = self.get_antenna_positions(fly_pos_xy, heading_rad)
        c_left = concentration_field(left_pos)
        c_right = concentration_field(right_pos)
        
        # Weber-Fechner: rate = rate_max * log(1 + C/K) / log(1 + C_max/K)
        rate_left = self.rate_max * np.log(1 + c_left / self.K) / np.log(1 + 1.0 / self.K)
        rate_right = self.rate_max * np.log(1 + c_right / self.K) / np.log(1 + 1.0 / self.K)
        
        # Rate → current (linear mapping, clipped)
        i_left = np.clip(rate_left / self.rate_max, 0, 1) * self.scale
        i_right = np.clip(rate_right / self.rate_max, 0, 1) * self.scale
        
        return {"left_pa": i_left, "right_pa": i_right, 
                "concentration_left": c_left, "concentration_right": c_right}
```

## Key Files

| File | Purpose |
|------|---------|
| `src/digital_drosophila/olfaction.py` | OlfactoryEncoder class |
| `src/digital_drosophila/sensory_encoder.py` | Existing proprioceptive encoder (reference) |

## Acceptance Criteria

- [ ] OlfactoryEncoder instantiates with default parameters
- [ ] get_antenna_positions() correctly computes bilateral positions from pose
- [ ] encode() returns currents that increase with concentration
- [ ] Weber-Fechner produces logarithmic response (not linear)
- [ ] Left-right asymmetry in concentration produces asymmetric outputs
- [ ] Works with a simple callable concentration field (e.g., lambda pos: ...)

## Notes

- Weber-Fechner law: perceived intensity ~ log(stimulus). This matches biological ORN responses.
- Real Drosophila antenna separation ~0.2mm (tiny!) but the concentration gradient over that distance is what drives chemotaxis
- Start simple: 1 odor channel. Multi-odor (n_channels > 1) is an extension for later.
- The OlfactoryEncoder should NOT depend on Brian2 — it produces currents that can be injected by whoever manages the network.
- Concentration field is a callable: field(pos_xy) → float. Arena modules will provide these.
