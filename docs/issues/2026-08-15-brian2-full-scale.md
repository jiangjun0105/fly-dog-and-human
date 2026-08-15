---
id: 2026-08-15-brian2-full-scale
title: "Scale Brian2 network to full VNC connectome with burn-in validation"
created: 2026-08-15T10:02
status: open
priority: medium
type: feature
area:
reporter_side: engineering
need_verify: true
related_issues: ["2026-08-15-brian2-biological-constraints"]
related_tasks: []
parent_epic: epic1-brian2-network
---

# Scale Brian2 network to full VNC connectome with burn-in validation

Scale from the 100-neuron proof-of-concept to the full VNC (~15,000-20,000 neurons).
Add the burn-in protocol from the design docs. Validate that the full-scale network
produces biologically plausible spontaneous activity. This is the "car" — the complete
deliverable Epic 3 (sensorimotor loop) will connect to.

## Current Behavior

(After Issue 2) A 100-neuron biologically-constrained network works correctly. But the
full VNC has ~15,000-20,000 neurons and ~12.75% connectivity density — 100× larger.

## What's Wrong

100 neurons is a toy. The sensorimotor loop (Epic 3) needs the full VNC with all 702
motor neurons and all sensory inputs to produce meaningful body control.

## Desired Behavior

- Query the full VNC connectome via neuPrint API (or load from cached data) and build
  a Brian2 network with all ~15,000-20,000 VNC neurons
- Use GeNN backend (GPU acceleration) to handle the scale
- Run burn-in protocol: Poisson input to sensory neurons at biologically plausible rates,
  let network reach steady-state spontaneous activity
- Validation passes: mean firing rates 1-30 Hz per superclass, no population goes silent,
  no runaway excitation, E/I balance maintained
- The full network runs at ≥10× realtime on the A10G GPU (1 second simulated in ≤100ms wall clock)

## Demo

Run `python scripts/run_brian2_full_vnc.py` → queries neuPrint (or loads cache), builds the
full VNC network on GPU via GeNN, runs 5-second burn-in, and produces:
(1) a population firing rate time-series (one line per superclass) showing convergence to steady state,
(2) a final raster plot (subsampled for visibility) showing healthy spontaneous activity,
(3) a validation report: rates per superclass, E/I ratio, no silent/saturated populations.
Total wall-clock time < 30 seconds for the 5-second simulation.

## Notes

- Data acquisition: use `src/digital_drosophila/data.py` functions (`load_vnc_neurons()`, `load_connectivity()`) with joblib caching
- GeNN setup: requires CUDA + pygenn (already in pyproject.toml dependencies)
- Burn-in protocol per `docs/neuroscience/04-learning-normal.md`: Poisson input to sensory neurons bootstraps spontaneous activity
- Scale concerns: 15k neurons × 12.75% density = ~28M synapses. GeNN handles this on GPU but memory usage needs monitoring
- If full VNC is too large initially, intermediate step: all motor neurons + their direct presynaptic partners (~2,000-3,000 neurons)
- The output of this issue is the "neural network" half that Epic 3 connects to the body
