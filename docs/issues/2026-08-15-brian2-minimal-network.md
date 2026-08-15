---
id: 2026-08-15-brian2-minimal-network
title: "Minimal Brian2 network from 100-neuron connectome sample"
created: 2026-08-15T10:00
status: open
priority: high
type: feature
area:
reporter_side: engineering
need_verify: true
related_issues: []
related_tasks: []
parent_epic: epic1-brian2-network
---

# Minimal Brian2 network from 100-neuron connectome sample

The thinnest possible vertical: prove that we can go from pre-computed connectome
data → a running Brian2 simulation that produces spikes. No biological fidelity yet —
just "data in, spikes out."

## Current Behavior

We have pre-computed connectome data (`adj.npy`, `sample_neurons.csv`) but no Brian2
network code. The data sits in `src/wiki/data/metrics/sample_100/` and is only used
for Streamlit visualization.

## What's Wrong

Can't run any neural simulation — the core research tool doesn't exist yet.

## Desired Behavior

- Run a single Python script that loads the 100-neuron adjacency matrix and produces
  a Brian2 simulation with visible spiking activity
- The script completes without error in under 60 seconds
- Output includes a raster plot (spike times × neuron index) showing that neurons fire

## Demo

Run `python scripts/run_brian2_minimal.py` → it loads `adj.npy` and `sample_neurons.csv`,
builds 100 LIF neurons connected by the adjacency matrix, simulates for 1 second, and
saves a raster plot PNG showing spikes. Neurons fire (not all silent, not all maxed out).

## Notes

- Use the simplest possible LIF model: `tau * dv/dt = -(v - v_rest) + R*I` with fixed parameters
- All weights = adjacency matrix values (raw synapse counts), no sign logic yet
- Drive with Poisson input to get activity started (sensory neurons or all neurons)
- Plain Brian2 (CPU), not GeNN — correctness first
- This is the "does Brian2 work with our data at all?" test
