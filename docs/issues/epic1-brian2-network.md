# EPIC — Build Brian2 Neural Network from VNC Connectome

**EPIC — container, do not execute; work lives in child issues.**

**Parent:** epic-phase1-implementation

## Epic Demo

Run a script that loads the full VNC connectome (~15,000-20,000 neurons), constructs a
Brian2/GeNN spiking neural network with biologically-constrained connectivity and sign
constraints, runs burn-in, and produces a raster plot showing spontaneous activity with
firing rates in biological range (1-30 Hz typical, no runaway excitation/silence).

## Children (value-sliced: skateboard → bicycle → car)

1. **[Skateboard — Minimal firing network](2026-08-15-brian2-minimal-network.md)**: Load the 100-neuron sample, build the simplest LIF network, see spikes
2. **[Bicycle — Biological constraints](2026-08-15-brian2-biological-constraints.md)**: Add sign constraints, proper weight init, NT types, superclass partitioning
3. **[Car — Full VNC scale + burn-in](2026-08-15-brian2-full-scale.md)**: Scale to ~15k-20k neurons, burn-in protocol, validate biological plausibility

## Dependency Spine

```
Issue 1 (minimal) → Issue 2 (biological fidelity) → Issue 3 (full scale)
```

Linear — each thickens the previous.

## Key References

- `docs/neuroscience/02-lif-model-design.md` — LIF equations, parameter table
- `docs/neuroscience/09-connectivity-structure.md` — topology stats
- `src/digital_drosophila/constants.py` — NT_SIGN_MAP
- `src/wiki/data/metrics/sample_100/` — pre-computed metrics
- `docs/neuroscience/08-implementation-phases.md` — Phase 1 parameters
