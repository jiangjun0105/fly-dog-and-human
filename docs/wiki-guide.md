# Wiki Guide

The Digital Drosophila wiki is a Streamlit app that presents the male-cns:v0.9 connectome data as interactive charts and tables. It is the project's shared reference for both developers building new pages and scientists reviewing data.

## Background

The dataset comes from the Janelia FlyEM / Cambridge collaboration — a complete male *Drosophila* CNS connectome (166k neurons, 45M pre-synapses, 311M post-synapses). We focus on the VNC (ventral nerve cord) subset: 25,635 neurons including 702 motor neurons across 4,206 cell types.

The wiki does not query the neuPrint API at runtime. All metrics are pre-computed and exported to flat files (JSON, CSV, NumPy) that are committed to git. This means the wiki can run on any machine without API credentials.

Source dataset: `male-cns:v0.9` on [neuprint.janelia.org](https://neuprint.janelia.org/)

## Running the wiki

```bash
just wiki             # starts on http://localhost:8501
```

## For developers

### File structure

```
src/wiki/
├── app.py                  # entry point — sidebar navigation, page routing
├── metrics.py              # data loading (reads from data/metrics/)
├── theme.py                # Plotly template, color constants, chart styling
├── pages/                  # one module per page
│   ├── data_analysis.py    # connectome overview, distributions, connectivity
│   └── strategies.py       # parameter conversion strategy comparison
└── data/metrics/           # pre-computed metrics (git-tracked)
    └── sample_100/         # default sample size
```

### Adding a new page

1. Create `src/wiki/pages/your_page.py` with a `render()` function:

```python
import streamlit as st

def render():
    st.title("Your Page Title")
    # ... rendering code
```

2. Register it in `src/wiki/app.py`:

```python
from wiki.pages import your_page

PAGES = [
    # ... existing pages
    st.Page(your_page.render, title="Your Page", icon=":material/icon:", url_path="your-page"),
]
```

That's it — the sidebar picks it up automatically.

### Loading data in a page

All pre-computed data is available through `wiki.metrics`:

```python
from wiki.metrics import load_metrics

m = load_metrics()
m["dataset_stats"]           # dict — neuron counts, ROI lists
m["superclass"]              # DataFrame — superclass distribution
m["cell_types"]              # (DataFrame, unique_count) — cell type counts
m["neurotransmitters"]       # dict — NT counts, missing stats
m["synapse_distributions"]   # dict — pre/post synapse histograms
m["motor_neurons"]           # dict — motor neuron breakdowns
m["connectivity"]            # dict — adjacency matrix, clustering, strategies
```

For the connectivity section with a sample-size slider:

```python
from wiki.metrics import load_connectivity_metrics

conn = load_connectivity_metrics(sample_size=150)  # cached per value
```

### Charting conventions

- Use **Altair** for bar charts, histograms, and distributions (most charts)
- Use **Plotly** for heatmaps, treemaps, and 3D/interactive plots
- Call `setup_plotly_theme()` once at app startup (handled in `app.py`)
- Color constants live in `wiki/theme.py` (Plotly) and `digital_drosophila/constants.py` (domain-specific like NT colors)

### Re-exporting metrics

If the source data or computation logic changes:

```bash
just export           # re-generates src/wiki/data/metrics/sample_100/
```

This requires a neuPrint API token in `.env` (see `.env.example`). After export, commit the updated files.

## For scientists

### Where the data lives

All pre-computed metrics are in `src/wiki/data/metrics/sample_100/`. These are plain files you can load directly in Python, R, or any tool:

| File | Format | Contents |
|------|--------|----------|
| `dataset_stats.json` | JSON | Neuron counts, ROI lists, dataset description |
| `superclass.csv` | CSV | VNC neuron superclass distribution (superclass, count, category) |
| `cell_types.csv` | CSV | All cell types ranked by frequency (type, count) |
| `nt_counts.csv` | CSV | Neurotransmitter distribution (neurotransmitter, count, sign) |
| `syn_pre_clipped.npy` / `syn_post_clipped.npy` | NumPy | Synapse count arrays (clipped at p99) |
| `syn_meta.json` | JSON | Median synapse counts |
| `motor_meta.json` | JSON | Motor neuron count and unique type count |
| `motor_nt_breakdown.csv` | CSV | Motor neuron neurotransmitter distribution |
| `motor_subclass_breakdown.csv` | CSV | Motor neuron subclass (body part) distribution |
| `motor_neuromere_breakdown.csv` | CSV | Motor neuron soma neuromere distribution |
| `adj.npy` | NumPy | 100x100 adjacency matrix (top neurons by input synapses) |
| `cluster_order.npy` | NumPy | Ward-linkage clustering order for the adjacency matrix |
| `weights_nz.npy` | NumPy | Non-zero synapse weights |
| `sample_neurons.csv` | CSV | Metadata for the 100 sampled neurons (bodyId, type, superclass, ...) |
| `conn_meta.json` | JSON | Edge count, fill %, weight min/median/max |
| `strategy_0/1/2_weights.npy` | NumPy | Converted weight matrices per strategy |
| `strategy_0/1/2_vth.npy` | NumPy | Threshold vectors per strategy |
| `strategy_0/1/2_meta.json` | JSON | Strategy name and scale factor |

### Quick access in Python

```python
import json, numpy as np, pandas as pd
from pathlib import Path

data = Path("src/wiki/data/metrics/sample_100")

stats = json.loads((data / "dataset_stats.json").read_text())
print(f"VNC neurons: {stats['vnc_neuron_count']:,}")

superclass = pd.read_csv(data / "superclass.csv")
adj = np.load(data / "adj.npy")
```

### Reviewing data in the browser

Run `just wiki` and use the sidebar to navigate:

- **Data Analysis** — dataset overview metrics, superclass/cell-type/neurotransmitter distributions, synapse histograms, motor neuron breakdowns, adjacency matrix heatmaps (raw + clustered), synapse weight distributions
- **Parameter Strategies** — comparison of three approaches for mapping synapse counts to spiking neuron parameters (weight/threshold distributions per strategy)
