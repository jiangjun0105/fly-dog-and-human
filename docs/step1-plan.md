Focusing on **Step 1: Connectome-to-Brian2 Pipeline**, your primary task is to transform static anatomical data into a dynamic, event-based simulation. Below is a breakdown of the resources, data structures, and implementation logic required to build this bridge.

## 1. Data Acquisition: Male CNS v0.9

The **Male CNS v0.9** dataset (`male-cns:v0.9`) is the first complete connectome of an entire adult male *Drosophila melanogaster* central nervous system — covering the **central brain, optic lobes, and ventral nerve cord (VNC)** in a single specimen (Berg, Beckett, Costa, Schlegel, Jefferis et al., 2025). With **166,691 neurons** and millions of synaptic connections, it supersedes the earlier VNC-only MANC dataset and provides a unified source for both Phase 1 (VNC motor control) and Phase 2 (whole-brain integration).

* **Primary Source:** Use [neuPrint](https://neuprint.janelia.org/?dataset=male-cns%3Av0.9) to access the dataset via `neuprint-python`. It provides high-resolution synaptic connectivity, cell type annotations, and neurotransmitter predictions.
* **Neurotransmitter Mapping:** The dataset includes per-neuron and per-synapse neurotransmitter predictions via a CNN applied to EM imagery. Primary fast-acting neurotransmitters: **Acetylcholine (excitatory), GABA (inhibitory), Glutamate (inhibitory in fly CNS)**. Modulatory neurotransmitters (dopamine, serotonin, octopamine, tyramine) are also predicted for certain populations.
* **Key Neurons to Extract (Step 1):** Focus on the **VNC subset** — specifically **Motor Neurons (MNs)** for the six legs and the **Premotor Interneurons** that form the Central Pattern Generators (CPGs). The full brain data will be used in Phase 2.
* **Companion Resources:** [male-cns.janelia.org](https://male-cns.janelia.org/), [GitHub downloads](https://github.com/janelia-flyem/male-cns/blob/main/docs/download.md), Cell Type Explorer for browsing annotations.

## 2. Adjacency Matrix & Synaptic Weighting

In a biologically-mapped SNN, the initial synaptic weight ($W_{ij}$) is typically proportional to the **synapse count** between two neurons.

* **Graph Extraction:** Use `neuprint.fetch_adjacencies` to get a weighted directed graph where the weight is the number of synaptic connections.
* **Weight Scaling:**
* Initialize $W_{ij} = \text{count} \times \text{scaling\_factor}$.
* Apply a sign ($+$ or $-$) based on the neurotransmitter type extracted from the metadata.


* **Structural Priors:** MANC data reveals the "tiling" of the VNC, where specific neuropils control specific legs. This allows you to initialize the Brian2 network with a modular, leg-specific architecture rather than a "black box" (Stürner et al., 2024).

## 3. Translation to Brian2 + GeNN

Brian2 defines networks using **NeuronGroups** (populations with differential equations) and **Synapses** (connectivity with per-synapse weights and plasticity rules). GeNN provides transparent GPU acceleration via NVIDIA CUDA.

### Implementation Blueprint:

| Component | Biological Data | Brian2 Implementation |
| --- | --- | --- |
| **Nodes** | Neurons (ID, Type) | `brian2.NeuronGroup` with LIF equations and per-neuron parameters (vth, tau) |
| **Edges** | Synapse Counts/Types | `brian2.Synapses` with sparse connectivity and signed weights |
| **Topology** | Adjacency Matrix | `Synapses.connect(i=..., j=...)` with explicit index pairs from connectome |
| **Input** | Sensory Afferents | `brian2.SpikeGeneratorGroup` or `brian2.PoissonGroup` |
| **GPU** | — | GeNN backend via `brian2genn` or direct `pygenn` for GPU-accelerated simulation |

* **Scaling Note:** Existing Brian2 + GeNN projects have successfully simulated Drosophila connectomes up to ~138k neurons with dopamine-gated learning. For your VNC phase (~25k neurons), Brian2's native sparse connectivity is well suited. The full male-cns dataset (166k neurons) aligns well with Phase 2 scaling and GeNN's GPU capacity.
* **Key Advantage over Lava:** Brian2 supports arbitrary per-neuron parameters (threshold, time constants) via equation expressions, enabling direct mapping of cell-type-specific properties from the connectome data. STDP and homeostatic plasticity rules are built in.

## 4. Useful Python Tools & Libraries

* **`neuprint-python`**: The standard API for querying Janelia's connectome data.
* **`brian2`**: SNN simulation framework with custom differential equations, per-neuron parameters, and built-in STDP.
* **`genn` / `pygenn`**: GPU-Enhanced Neural Networks — compiles SNN models to optimized CUDA code for NVIDIA GPUs.
* **`brian2genn`**: Bridge that allows Brian2 models to run on GeNN's GPU backend transparently.
* **`fafbseg`**: Useful if you need to cross-reference between the whole-brain (FlyWire) and the VNC. Less critical now that `male-cns:v0.9` provides a unified CNS dataset.

---

### **References**

* Berg, S., Beckett, A., Costa, M., Schlegel, P., Jefferis, G. S. X. E., et al. (2025). Sexual dimorphism in the complete connectome of the Drosophila male central nervous system. *bioRxiv*. DOI: 10.1101/2025.10.09.680999
* Primary dataset source for this project.

* Galili, D. S., Jefferis, G. S. X. E., & Costa, M. (2022). Connectomics and the neural basis of behaviour. *Current Opinion in Insect Science*, *54*, 100968. [https://doi.org/10.1016/j.cois.2022.100968]()
* Cited by: 47


* Stürner, T., et al. (2024). Comparative connectomics of Drosophila descending and ascending neurons. *Nature*. [Research Paper].
* Cited by: 34


* Wang, C. (2026). Model-agnostic linear-memory online learning in spiking neural networks. *PMC - NIH*. [Research Paper].
* Cited by: 1



How do you plan to handle the initial weight initialization—will you rely strictly on synapse counts, or do you intend to use a "burn-in" period of unsupervised STDP to stabilize the network before body integration?