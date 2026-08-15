---
id: 2026-08-15-benchmark-gait-analysis
title: "Gait analysis: phase extraction, coordination indices, step frequency"
created: 2026-08-15T20:00
status: open
priority: medium
type: task
suitability: auto_agent_ready
depends_on:
  - 2026-08-15-benchmark-locomotion-metrics
related: []
satisfies:
  - 2026-08-15-benchmark-locomotion
branch: ""
pr: ""
auto_agent_task_id: ""
---

# Gait analysis: phase extraction, coordination indices, step frequency

## Context

Beyond simple speed/stability metrics, we want to analyze the fly's gait pattern.
Real Drosophila use specific gait patterns (tripod, tetrapod, wave) depending on speed.
Can our connectome network produce any recognizable gait pattern?

## Problem

We can see the fly moves, but we don't know if it's coordinated leg movement or random
thrashing. Gait analysis extracts the temporal structure of leg movements.

## Desired Behavior

### Gait Metrics

1. **Step frequency** — dominant frequency from leg contact FFT (Hz)
2. **Gait regularity** — autocorrelation peak height of leg contact patterns (0-1)
3. **Tripod coordination index** — phase coherence between {LF, RM, LH} vs {RF, LM, RH}
4. **Inter-leg phase** — phase relationships between all 6 legs (6×6 matrix)
5. **Duty factor** — stance duration / (stance + swing) per leg
6. **Swing/stance symmetry** — left-right symmetry of duty factors

### Analysis Methods

```python
def extract_leg_phases(leg_contacts: np.ndarray, dt: float) -> dict:
    """Extract phase information from binary leg contact data.
    
    Parameters
    ----------
    leg_contacts : (T, 6) boolean array, columns = [LF, LM, LH, RF, RM, RH]
    dt : timestep
    
    Returns
    -------
    dict with:
        step_frequency: dominant frequency (Hz)
        gait_regularity: autocorrelation peak (0-1)
        duty_factors: (6,) stance fraction per leg
        inter_leg_phases: (6, 6) phase difference matrix
        tripod_index: coherence of tripod pattern
    """
```

### Gait Classification

Based on inter-leg phases, classify the gait:
- **Tripod**: alternating groups of 3 (phase ~π between groups)
- **Tetrapod**: wave-like with 4 legs in stance
- **Wave (metachronal)**: sequential leg lifting
- **Uncoordinated**: no consistent phase relationship

## Implementation

Use signal processing:
- FFT of leg contact binary signal → dominant frequency
- Cross-correlation between leg pairs → phase relationships
- Autocorrelation → periodicity measure
- Hilbert transform for instantaneous phase (if signals are clean enough)

## Key Files

| File | Purpose |
|------|---------|
| `src/digital_drosophila/benchmarks/gait.py` | Gait analysis functions |

## Acceptance Criteria

- [ ] Step frequency correctly identifies 8 Hz for scripted tripod gait
- [ ] Tripod coordination index > 0.9 for CPG controller
- [ ] Tripod coordination index < 0.3 for random/noise controller
- [ ] Duty factor in [0, 1] range for all legs
- [ ] Gait phase diagram visualizable (polar plot or phase diagram)
- [ ] Works on both neural-driven and CPG episodes

## Notes

- Binary contact signal may need smoothing before FFT (low-pass or Gaussian kernel)
- The neural-driven fly probably won't show clean gait — that's the point of the measurement
- Inter-leg phase matrix is analogous to coherence matrix in EEG analysis
- Real fly tripod: LF, RM, LH move together (one tripod), RF, LM, RH (other tripod)
- dt for FlyGym is 1e-4s (0.1ms); contact sampled at coupling_dt (2ms) if using CoSimulation
