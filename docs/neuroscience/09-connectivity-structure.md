# Connectivity Structure

Analysis of the neuron-to-neuron wiring in the male-cns:v0.9 connectome.
The connectome provides exact, synapse-resolution connectivity: we know
which neuron connects to which, and how many synapses form each
connection. The relationship is **many-to-many** at every level.

## Many-to-many at two levels

### Neuron level

Each neuron sends to many downstream partners and receives from many
upstream partners. From the top-100 VNC sample (neurons ranked by input
synapse count):

| Metric | Min | p25 | Median | p75 | p90 | Max |
|--------|----:|----:|-------:|----:|----:|----:|
| **Fan-out** (# targets a neuron sends to) | 0 | 7 | 14 | 17 | 21 | 31 |
| **Fan-in** (# sources feeding a neuron) | 3 | 8 | 11 | 16 | 24 | 30 |

A typical neuron sends to ~14 partners and receives from ~11. The most
connected neuron in the sample — DNg74_a, a descending neuron — sends
to 31 targets and receives from 30 sources.

### Synapse level

Each neuron-to-neuron connection is not a single wire but a bundle of
individual synapses. In the top-100 sample:

- Total synapses across all connections: **29,199**
- Average synapses per connection: **22.9**
- Range: 1 to 228 synapses per connection pair

More synapses generally means stronger influence. The adjacency matrix
(`adj.npy`) stores this synapse count as the edge weight.

On top of that, each individual presynaptic T-bar is **polyadic** — it
broadcasts to ~7 postsynaptic partners simultaneously (see
[connectome-terminology.md](01-connectome-terminology.md#why-there-are-7x-more-postsynapses-than-presynapses)).

So the many-to-many structure is nested:

```
one T-bar   → ~7 postsynaptic partners    (synapse level, polyadic)
one neuron  → ~14 target neurons           (circuit level, divergence)
one neuron  ← ~11 source neurons           (circuit level, convergence)
```

## Reciprocity

Not all connections are one-way. Of the 1,275 non-zero connections in
the top-100 sample:

- **335 pairs** are reciprocal (A→B and B→A both exist)
- **605 connections** are unidirectional

Reciprocal wiring is common in local circuits — two interneurons may
mutually inhibit each other to form a winner-take-all motif, or
mutually excite to amplify a shared signal.

## Sparsity

The adjacency matrix is sparse: only **12.75%** of possible neuron pairs
have a direct connection. This is typical of real neural circuits — most
information flow is indirect, passing through chains of intermediate
neurons rather than direct point-to-point wiring.

For the spiking model, sparsity matters: it means most weight matrix
entries are zero, which both reduces computation and reflects the
biological constraint that axons can only reach a limited set of
partners.

## Data source

All numbers in this document come from the pre-computed VNC adjacency
matrix at `src/wiki/data/metrics/sample_100/vnc/adj.npy` — the top 100
VNC neurons by input synapse count. The full VNC contains 25,635 neurons;
the patterns here (heavy-tailed degree distribution, sparse connectivity,
reciprocal motifs) are expected to hold at full scale.
