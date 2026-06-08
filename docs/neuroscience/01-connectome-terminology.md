# Connectome Terminology

Reference for key terms used throughout the Digital Drosophila project,
focused on the male-cns:v0.9 VNC (ventral nerve cord) connectome data.

## Presynapses and Postsynapses

### Presynapse (output)

A **presynaptic site** is where a neuron **sends** a signal. The naming
comes from the synapse's perspective, not the neuron's: "pre" means
"before the synaptic cleft," on the sending side.

```
Neuron A          synapse          Neuron B
─────────►  [pre]──gap──[post]  ─────────►
 sending                          receiving
```

In the EM (electron microscopy) reconstruction, each presynapse is a
physically identified release site called a **T-bar** (named for its shape
in cross-section). When we say a neuron has 240 presynapses, it has 240
distinct sites where it releases neurotransmitter.

In our dataset: **45.7M** total presynapses across the full connectome.
Median per VNC neuron: **240**.

### Postsynapse (input)

A **postsynaptic site** is where a neuron **receives** a signal — the
receptor-bearing membrane on the downstream side of the cleft.

In our dataset: **311.8M** total postsynapses. Median per VNC neuron: **493**.

### Why there are ~7x more postsynapses than presynapses

In *Drosophila*, synapses are **polyadic**: a single presynaptic T-bar
releases neurotransmitter into a small volume, and multiple postsynaptic
neurons have receptor sites clustered around that same release site.

```
        Neuron A
           │
         ┌─┴─┐        ← one T-bar (1 presynapse)
         │   │
    ┌────┘   └────┐
    ▼    ▼    ▼   ▼    ← multiple postsynaptic densities
    B    C    D   E       (each counted as 1 postsynapse)
```

One presynaptic release broadcasts to **~7 postsynaptic partners** on
average. This is efficient wiring: one release, many listeners. It is a
distinctly invertebrate feature — mammalian synapses are mostly one-to-one.

### Presynapses and postsynapses in the adjacency matrix

In the 100x100 connectivity matrix (`adj.npy`), each weight is the
synapse count from neuron A (pre) to neuron B (post). A weight of 50
means neuron A has 50 presynaptic sites that contact neuron B's
postsynaptic densities.

## Regions of Interest (ROIs)

ROIs are **anatomically defined neuropil compartments** — physically
distinct regions of the fly nervous system that map to specific body
parts and functions. They are segmented (manually or semi-automatically)
in the EM volume.

The full connectome has **5,412 ROIs** (152 primary). The VNC subset we
work with has **21 ROIs**.

### VNC ROIs and what they control

| ROI | Full name | Body function |
|-----|-----------|---------------|
| LegNp(T1)(L/R) | Leg neuropil, 1st thoracic segment | **Front legs** |
| LegNp(T2)(L/R) | Leg neuropil, 2nd thoracic segment | **Middle legs** |
| LegNp(T3)(L/R) | Leg neuropil, 3rd thoracic segment | **Hind legs** |
| NTct(T1)(L/R) | Neck tectulum | **Head/neck** movement |
| WTct(T2)(L/R) | Wing tectulum | **Wing** motor control |
| HTct(T3)(L/R) | Haltere tectulum | **Haltere** (balance organ) control |
| mVAC(T1–T3)(L/R) | Medial ventral association center | **Integration zones** — sensory and motor convergence |
| ANm | Abdominal neuromere | **Abdomen** (reproduction, excretion) |
| VNC | Ventral nerve cord | Catch-all for the cord |
| VNC-unspecified | — | Synapses not assigned to a specific sub-region |

The **L/R** suffix denotes left/right — the fly is bilaterally symmetric,
so each structure exists on both sides.

### How ROI membership is determined

ROIs are segmented (semi-automatically + manual curation) from the EM
volume into named neuropil compartments. Every synapse has a 3D
coordinate; if that coordinate falls within a compartment boundary, the
synapse is assigned to that ROI. Because neurons arborize widely, a
single neuron often has synapses in **many ROIs** — for example, the
descending neuron DNa02 has presynaptic sites in LegNp(T1–T3),
HTct, NTct, WTct, and ANm simultaneously.

This is why the VNC ROI distribution sums to far more than 25,635
neurons — it counts each neuron once per ROI it touches.

### Why ROIs matter for the spiking model

ROI localization lets us infer function from anatomy. If a motor neuron's
synapses are concentrated in LegNp(T2)(R), it almost certainly drives a
muscle in the right middle leg. This maps connectivity data to body-part
function without needing behavioral experiments.

## Neuron Types

The dataset classifies neurons along two axes: **superclass** (functional
role) and **cell type** (fine morphological identity). These are
**orthogonal** to the ROI system: every neuron has exactly one superclass
but can have synapses in many ROIs. Superclass tells you the neuron's
**information flow direction**; ROIs tell you **where in physical space**
its synapses sit.

### Superclass

Superclass describes a neuron's projection pattern — where it sends and
receives signals relative to the VNC.

Annotators assign superclass by **tracing each neuron's morphology**
through the EM volume: where the cell body sits (inside or outside the
VNC), whether the axon projects upward to the brain, downward from the
brain, stays local, or exits the CNS entirely to reach muscle or
peripheral sense organs.

| Superclass | Count | Role |
|------------|------:|------|
| vnc_intrinsic | 13,149 | **Local interneurons** — connect within the VNC, don't project out. The backbone of local circuit computation |
| vnc_sensory | 6,326 | **Sensory neurons** — bring information in from the body (mechanoreceptors, proprioceptors) |
| ascending_neuron | 1,843 | Project **up** from VNC to brain — carry processed signals to higher centers |
| descending_neuron | 1,305 | Project **down** from brain to VNC — carry commands to motor circuits |
| vnc_motor | 702 | **Motor neurons** — project out of the CNS to muscles. The final output layer |
| vnc_efferent | 99 | Other efferents (e.g., neuromodulatory outputs) |
| sensory_ascending | 534 | Sensory neurons that also ascend to the brain |
| vnc_tbc / *_tbc | ~67 | "To be confirmed" — morphological trace was ambiguous, classification pending |

### How superclass and ROIs cross-cut

These two axes are independent and complementary:

- **Superclass** answers: *what is this neuron's role in the circuit?*
  (sensory input, local processing, motor output, long-range relay)
- **ROI** answers: *which body parts does it wire to?*
  (front legs, wings, abdomen, etc.)

Knowing both lets you make functional inferences without behavioral
experiments. A `vnc_motor` neuron whose synapses concentrate in
LegNp(T2)(R) almost certainly drives a right-middle-leg muscle.
A `descending_neuron` with outputs across all six LegNp regions is
likely a locomotion command neuron broadcasting to all legs.

### Cell type

A finer classification: neurons of the same cell type share the same
morphology, connectivity pattern, and (usually) neurotransmitter. The
VNC contains **4,206 distinct cell types**. The 702 motor neurons alone
span **142 unique types**.

Cell types are assigned by the Janelia/Cambridge annotation team through:

1. **Morphological similarity** — neurons are traced in the EM volume
   and their 3D arbor shape is compared. Mirror-image pairs (left/right)
   and serial repeats (same shape in T1, T2, T3) are grouped together.
2. **Connectivity pattern** — neurons of the same type connect to the
   same upstream and downstream partners in the same proportions. This
   disambiguates when morphology alone is unclear.
3. **Cross-referencing prior datasets** — matches to previously published
   connectomes (hemibrain, MANC, FlyWire) are carried forward when
   confirmed. The dataset columns `hemibrainType`, `mancType`, and
   `flywireType` record these correspondences.

### Cell type naming convention

Type names are systematic. The prefix encodes superclass and the suffix
often encodes body region, so you can read functional identity directly
from the name:

| Prefix | Meaning | Example |
|--------|---------|---------|
| **SN** | Sensory neuron | SNta29, SNch10 |
| **IN** | Intrinsic (local interneuron) | IN01B095 |
| **AN** | Ascending neuron | AN10B045 |
| **DN** | Descending neuron | DNa02, DNp103 |
| **MN** | Motor neuron | MNad02, MNwm36 |
| **Lg** | Leg-specific circuit neuron | LgLG1a, LgLG2 |
| **W**  | Wing-specific circuit neuron | WG1–WG4 |

Common body-region suffixes (especially visible in motor and sensory
types):

| Suffix | Body region |
|--------|-------------|
| **ad** | Abdomen |
| **fl** | Front leg |
| **ml** | Middle leg |
| **hl** | Hind leg |
| **wm** | Wing muscle |
| **nm** | Neck muscle |
| **hm** | Haltere muscle |
| **ta** | Tarsal (touch/mechanoreceptor) |
| **ch** | Chordotonal (proprioception) |

Other naming patterns:

- **Bilateral pairs** share the same type with an L/R instance suffix:
  `DNa02_L` and `DNa02_R` are both type `DNa02`.
- **Composite names** like `SNta02,SNta09` indicate types that could not
  be confidently split.
- **XXX** in the name (e.g., `INXXX027`) means the type is provisional
  and awaiting further confirmation.

The full hierarchy from coarsest to finest is: **superclass** (8
categories) → **subclass** (body region, ~13 categories) → **cell
type** (4,206 distinct morphological identities).

### Neurotransmitter identity

Each neuron is assigned a primary neurotransmitter, which determines its
sign (excitatory, inhibitory, or modulatory) in the spiking model.

The NT is a property of the **sending (presynaptic) neuron** — it is the
chemical that neuron releases from all of its presynaptic T-bars into
the synaptic cleft. This follows **Dale's principle**: a neuron uses the
same transmitter at all of its synapses. So assigning one NT per neuron
determines the sign of every outgoing connection from that neuron.

| Neurotransmitter | Count | Effect | Notes |
|------------------|------:|--------|-------|
| Acetylcholine | 14,221 | Excitatory (+1) | Dominant excitatory NT in *Drosophila* (unlike vertebrates, where glutamate fills this role) |
| GABA | 6,044 | Inhibitory (-1) | Primary fast inhibition, same as vertebrates |
| Glutamate | 2,389 | Inhibitory (-1) | Inhibitory in the *Drosophila* CNS (opposite of vertebrates) |
| Unclear | 2,952 | Modulatory | Could not be confidently assigned |
| Serotonin | 20 | Modulatory | Neuromodulator |
| Histamine | 9 | Inhibitory (-1) | Used by photoreceptors; rare in VNC |

### How neurotransmitter identity is determined

NT assignments are **not direct biochemical measurements** — they are
machine-learning predictions from EM image features (synapse morphology,
vesicle shape and size). The dataset provides three columns that
represent a prediction pipeline:

1. **`predictedNt`** — a per-neuron classifier prediction based on that
   individual neuron's EM features. Comes with a confidence score
   (`predictedNtConfidence`); median confidence is ~0.94, but some
   neurons score as low as 0.25.
2. **`celltypePredictedNt`** — an aggregated prediction across all
   neurons of the same cell type. If most neurons in type `DNa02`
   predict acetylcholine, the whole type gets that label. This smooths
   out noisy individual predictions.
3. **`consensusNt`** — the final call combining both predictions. This
   is the column used throughout the project.

In the top-100 sample, all three columns agree for **94%** of neurons.
The remaining ~6% disagreement is concentrated in low-confidence
neurons and motor neurons.

**Motor neuron resolution:** 672 of 702 motor neurons are classified as
"unclear" by the automated pipeline because they use glutamate, which
has opposite effects depending on context: **inhibitory** within the CNS
(the *Drosophila* convention) but **excitatory** at the neuromuscular
junction (like vertebrates). The classifier cannot resolve this
ambiguity because it doesn't distinguish target types.

For the spiking model, this is resolved in the preprocessing pipeline:
all connections in the adjacency matrix are CNS-to-CNS, so motor neuron
glutamate connections get sign = −1 (inhibitory), same as all other
glutamatergic CNS neurons. Their excitatory effect on muscles is handled
separately by the body model's motor interface — it is not a synapse
in the network. See [LIF model design](02-lif-model-design.md#sign-map)
for the full sign map and [motor neuron output](02-lif-model-design.md#motor-neuron-output)
for how motor neurons interface with the body.

*Drosophila* also has dedicated **inhibitory motor neurons** (GABAergic,
~30 of the 702) that actively relax muscles, and **modulatory motor
neurons** (octopaminergic) that adjust muscle gain — unlike vertebrates,
where all motor neurons at the neuromuscular junction are excitatory.
