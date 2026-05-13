# Project Digital Drosophila: Hierarchical Embodied Learning

**Objective:** To demonstrate that a biologically-mapped Spiking Neural Network (SNN) can learn to control a complex biomechanical body using localized, biological learning rules instead of centralized backpropagation.

### Technical Stack

* **Neural Framework:** Brian2 + GeNN (GPU-accelerated spiking neural network simulation via NVIDIA CUDA).
* **Physics Engine:** MuJoCo (via the NeuroMechFly framework).
* **Biological Data:** Male CNS v0.9 (`male-cns:v0.9`) — the complete male *Drosophila* central nervous system connectome (166,691 neurons: brain + optic lobes + VNC). Supersedes MANC/FANC and FlyWire as a single unified source.
* **Learning Paradigms:** Three-factor STDP (Dopamine-gated Hebbian learning), MSCN (Structural Plasticity), and Sleep-mediated memory consolidation.

---

## Phase 1: The Synthetic Spinal Cord (VNC)

The goal of this phase is to achieve a stable, learned walking gait using the ~15,000–20,000 neurons of the fly's motor center.

### Step 1: Connectome-to-Brian2 Pipeline

* **Data Acquisition:** Query the **male-cns:v0.9** dataset via `neuprint-python` to extract the VNC subset's adjacency matrix (who connects to whom) and neurotransmitter types (excitatory vs. inhibitory).
* **Translation Script:** Develop a Python utility to parse the graph data into **Brian2 NeuronGroups and Synapses**. This script will initialize the synaptic weights ($W_{ij}$) based on biological synapse counts, creating a "good enough" structural scaffold. Per-neuron parameters (threshold, time constants) are derived from cell type annotations.

### Step 2: Architecture & Body Integration

* **Network Definition:** Define the SNN using Leaky Integrate-and-Fire (LIF) neurons within Brian2, with GPU acceleration via GeNN.
* **The "Body" Module:** Integrate **NeuroMechFly**, a high-fidelity MuJoCo model of the *Drosophila* anatomy.
* **The Interface:** Map the VNC’s motor neurons to the virtual joint actuators and link the body’s proprioceptive sensors (leg contact and joint angles) back into the VNC as sensory input.

### Step 3: Embodied Learning & Consolidation

* **Online Learning:** Implement a dopamine-gated STDP rule. The network receives a reward signal based on the body's forward velocity and stability.
* **Refinement:** Use the **MSCN** (Multi-Synaptic Cooperative Network) logic to allow the network to prune "noisy" or useless connections while strengthening vital ones.
* **Sleep Phase:** Periodically disconnect sensory input to run "digital sleep" cycles, replaying successful motor patterns to stabilize the network against catastrophic forgetting.

---

## Phase 2: Scaling to the Whole Brain

If the VNC successfully learns to coordinate the six legs and maintain a stable gait, the project will scale to the full central nervous system.

### Step 4: The Central Brain Integration

* **The Connectome:** Scale to the full **male-cns:v0.9** dataset (~166,691 neurons), incorporating the central brain and optic lobes already available in the same connectome used for Phase 1.
* **Hierarchical Control:** Connect the central brain to the VNC via the **Descending Neurons (DNs)**.
* **Advanced Behavior:** Train the central brain to issue high-level commands (e.g., "turn left" or "target odor") that the VNC must then translate into mechanical movement.

---

### Key Research Hypotheses

1. **Form Follows Function:** A network with biological topology will learn motor control faster and more efficiently than a generic, fully connected SNN.
2. **Stability via Consolidation:** Sleep-inspired replay will allow the fly to retain walking skills even when introduced to new "tasks" like navigating uneven terrain.
3. **Local vs. Global:** Localized learning rules (STDP) can replace backpropagation in complex, multi-jointed robotic control.
