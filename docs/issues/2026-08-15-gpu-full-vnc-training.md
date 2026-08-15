---
id: 2026-08-15-gpu-full-vnc-training
title: "Scale GPU training to full 15K-neuron VNC"
created: 2026-08-15T19:40
status: open
priority: medium
type: feature
area: gpu
reporter_side: engineering
need_verify: true
related_issues: ["2026-08-15-gpu-training-integration"]
related_tasks: []
parent_epic: epic6-pygenn-gpu-training
---

# Scale GPU training to full 15K-neuron VNC

Use the complete VNC connectome (15,000 neurons) for training instead of the
100-neuron sample. The larger network has richer dynamics and more biologically
faithful motor neuron pools.

## Current Behavior

Training uses a 100-neuron sample selected by connectivity rank. The full VNC
(15K neurons) runs on GPU in `simulate.py::run_full_vnc()` but is not integrated
into the training/body loop.

## Desired Behavior

- Train the full 15K-neuron VNC network coupled to FlyGym
- Proper motor neuron pool identification (which neurons drive which legs)
- Ascending neuron identification (which neurons receive proprioceptive input)
- Same STDP + homeostatic learning, but on the full biological network
- Estimated ~10-15s per episode on A10G (vs ~118s for 100 neurons on CPU)

## Implementation Plan

### 1. Motor neuron mapping

Query the male-cns:v0.9 dataset to identify:
- Motor neurons → leg assignment (6 legs × 11 actuators each = 66)
- Ascending neurons → sensory input targets
- Use superclass annotations from the VNC neuron metadata

### 2. Adapt PyGeNNBackend for 15K neurons

The existing `run_full_vnc()` already builds 15K neurons on GPU. Adapt this
to work with the backend protocol:
- Sparse connectivity with per-synapse eligibility tracking
- Sensory current injection for ascending neurons
- Motor spike readout from identified motor neuron indices

### 3. Weight conversion and scaling

The 15K network uses different weight scaling (0.15 mV vs 0.6 mV for 100 neurons)
because more recurrent connectivity provides more network drive. Learning rates
may need adjustment.

### 4. Episode-body coupling

Same FlyGym body, same actuators, but motor commands come from a much larger
and more diverse motor neuron pool. The motor adapter needs to handle potentially
hundreds of motor neurons mapped to 66 actuators (population coding).

## Notes

- This is a stretch goal — the 100-neuron GPU training (Issues 6.1+6.2) is the priority
- The full VNC may require different hyperparameters (learning rate, target rate)
- With 15K neurons, eligibility trace storage is ~225M synapses × 4 bytes = ~900MB
  which fits in the A10G's 23GB VRAM
- The scientific payoff is high: training on the real connectome (not a sample)
  gives the strongest test of the "form follows function" hypothesis
