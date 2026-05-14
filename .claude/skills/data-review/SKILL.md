---
name: data-review
description: Quick reference for reviewing Digital Drosophila connectome datasets. Lists all data files, their formats, and how to load them. Use when a scientist asks about available data, wants to inspect metrics, or needs to find a specific dataset.
---

# Data Review

Reference for scientists working with the Digital Drosophila connectome data.

## Dataset

**Source:** male-cns:v0.9 from the Janelia FlyEM / Cambridge collaboration
**Scope:** Complete male *Drosophila* CNS connectome — 173k neurons, 43M pre-synapses, 131M post-synapses
**Three scopes:**
- **Total** — all 173,239 neurons in the connectome
- **VNC** — 25,635 neurons in the ventral nerve cord (motor control focus)
- **Brain** — 147,604 neurons outside the VNC (vision, decision-making, etc.)

Links:
- [neuPrint query interface](https://neuprint.janelia.org/)
- [Project overview](https://www.janelia.org/project-team/flyem/male-cns-connectome)
- [Male CNS Connectome Site](https://janelia-flyem.github.io/male-cns)
- [Cell Type Explorer](https://reiserlab.github.io/celltype-explorer-drosophila-male-cns)

## Where the data lives

Pre-computed metrics are in `src/wiki/data/metrics/sample_100/`. Each scope has its own subdirectory:

```
src/wiki/data/metrics/sample_100/
├── dataset_stats.json          ← shared: whole-connectome metadata
├── total/                      ← total connectome metrics
│   ├── scope_stats.json
│   ├── roi_distribution.csv
│   ├── superclass.csv
│   ├── cell_types.csv / cell_types_meta.json
│   ├── nt_counts.csv / nt_meta.json
│   ├── syn_pre_clipped.npy / syn_post_clipped.npy / syn_meta.json
│   ├── motor_meta.json / motor_*_breakdown.csv
│   ├── adj.npy / cluster_order.npy / weights_nz.npy / conn_meta.json
│   ├── sample_neurons.csv
│   └── strategy_{0,1,2}_*.{json,npy}
├── vnc/                        ← VNC subset metrics (same file set)
└── brain/                      ← brain-only metrics (same file set)
```

### Shared metadata

| File | Format | What's inside |
|------|--------|---------------|
| `dataset_stats.json` | JSON | Whole-connectome metadata: synapse totals, ROI lists, description |

### Per-scope files (in each `total/`, `vnc/`, `brain/` directory)

| File | Format | What's inside |
|------|--------|---------------|
| `scope_stats.json` | JSON | Neuron count, motor neuron count, pre/post synapse totals for this scope |
| `roi_distribution.csv` | CSV | ROI neuron counts — columns: `roi`, `neuron_count` |
| `superclass.csv` | CSV | Neuron superclass distribution — columns: `superclass`, `count`, `category` |
| `cell_types.csv` | CSV | All cell types ranked by frequency — columns: `type`, `count` |
| `cell_types_meta.json` | JSON | `unique_count`: total number of distinct cell types |
| `nt_counts.csv` | CSV | Neurotransmitter distribution — columns: `neurotransmitter`, `count`, `sign` |
| `nt_meta.json` | JSON | `nt_col` (source column name), `missing_count`, `missing_pct` |
| `syn_pre_clipped.npy` | NumPy | Output synapse counts per neuron (clipped at p99) |
| `syn_post_clipped.npy` | NumPy | Input synapse counts per neuron (clipped at p99) |
| `syn_meta.json` | JSON | Median values for pre and post synapse counts |
| `motor_meta.json` | JSON | Motor neuron `count` and `unique_types` |
| `motor_nt_breakdown.csv` | CSV | Motor neuron neurotransmitter distribution |
| `motor_subclass_breakdown.csv` | CSV | Motor neuron subclass (body part) distribution |
| `motor_neuromere_breakdown.csv` | CSV | Soma neuromere distribution |
| `adj.npy` | NumPy | 100x100 adjacency matrix (synapse counts) |
| `cluster_order.npy` | NumPy | Ward-linkage clustering order for adjacency matrix |
| `weights_nz.npy` | NumPy | Non-zero synapse weights (flat array) |
| `sample_neurons.csv` | CSV | Metadata for the 100 sampled neurons |
| `conn_meta.json` | JSON | `nonzero`, `total`, `fill_pct`, `weight_min`, `weight_median`, `weight_max` |
| `strategy_{0,1,2}_meta.json` | JSON | Strategy name and scale factor |
| `strategy_{0,1,2}_weights.npy` | NumPy | 100x100 converted weight matrix |
| `strategy_{0,1,2}_vth.npy` | NumPy | Threshold vector (100 values) |

## Quick access in Python

```python
import json, numpy as np, pandas as pd
from pathlib import Path

base = Path("src/wiki/data/metrics/sample_100")

# Shared dataset stats
stats = json.loads((base / "dataset_stats.json").read_text())

# Pick a scope: "total", "vnc", or "brain"
scope = "vnc"
data = base / scope

# Scope-level stats
scope_stats = json.loads((data / "scope_stats.json").read_text())
print(f"{scope} neurons: {scope_stats['neuron_count']:,}")

# Distributions
superclass = pd.read_csv(data / "superclass.csv")
cell_types = pd.read_csv(data / "cell_types.csv")
nt_counts  = pd.read_csv(data / "nt_counts.csv")
roi_dist   = pd.read_csv(data / "roi_distribution.csv")

# Connectivity
adj = np.load(data / "adj.npy")
sample_neurons = pd.read_csv(data / "sample_neurons.csv")
```

## Using the wiki metrics API

```python
from wiki.metrics import load_metrics_for_scope

# Load any scope
m = load_metrics_for_scope("brain")
m["scope_stats"]["neuron_count"]        # 147604
m["superclass"]                         # DataFrame
m["connectivity"]["adj"]                # 100x100 ndarray

# Backward-compatible VNC-only shortcut
from wiki.metrics import load_metrics
m = load_metrics()  # same as load_metrics_for_scope("vnc")
```

## Reviewing in the browser

```bash
just wiki
```

The Data Analysis page has three tabs — **Total**, **VNC**, **Brain** — each showing the full set of metrics for that scope.
