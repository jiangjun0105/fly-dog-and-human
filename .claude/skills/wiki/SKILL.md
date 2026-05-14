---
name: wiki
description: Wiki maintenance guide for developers. Explains the wiki architecture, how to add pages, where data flows from, and the charting conventions. Use when creating or modifying wiki pages.
---

# Wiki Maintenance

Reference for developers working on the Digital Drosophila wiki (Streamlit app).

## Architecture

The wiki is a sidebar-routed multi-page Streamlit app. All data is pre-computed — pages only render, never compute.

```
src/wiki/
├── app.py                  # entry point — st.navigation routing
├── metrics.py              # data loading layer (reads pre-exported files)
├── theme.py                # Plotly template, color palettes, layout constants
├── pages/                  # one module per page
│   ├── data_analysis.py    # connectome overview, distributions, connectivity
│   └── strategies.py       # parameter conversion strategy comparison
└── data/metrics/           # pre-computed metrics (JSON, CSV, NumPy — git-tracked)
    └── sample_100/         # default sample size
```

Entry point: `run_app.py` → calls `wiki.app.main()`.
Launch: `just wiki` (or `uv run streamlit run run_app.py`).

## How to add a new page

1. Create `src/wiki/pages/your_page.py` with a `render()` function:

```python
import streamlit as st
from wiki.metrics import load_metrics

def render():
    st.title("Your Page Title")
    m = load_metrics()
    # render using m["dataset_stats"], m["connectivity"], etc.
```

2. Register it in `src/wiki/app.py`:

```python
from wiki.pages import your_page

PAGES = [
    # existing pages ...
    st.Page(your_page.render, title="Your Page", icon=":material/icon:", url_path="your-page"),
]
```

The sidebar picks it up automatically. Each page must have a unique `url_path`.

## Data loading

All pre-computed metrics are accessed through `wiki.metrics`:

```python
from wiki.metrics import load_metrics, load_connectivity_metrics

m = load_metrics()                        # all sections
conn = load_connectivity_metrics(150)     # connectivity only, for slider re-renders
```

`load_metrics()` returns a dict with these keys:

| Key | Type | Contents |
|-----|------|----------|
| `dataset_stats` | dict | Neuron counts, ROI lists, dataset description |
| `superclass` | DataFrame | Superclass name, count, category |
| `cell_types` | (DataFrame, int) | Cell type counts + unique count |
| `neurotransmitters` | dict | NT counts DataFrame, missing stats, column name |
| `synapse_distributions` | dict | Per pre/post: clipped value arrays + median |
| `motor_neurons` | dict | Count, unique types, breakdown DataFrames |
| `connectivity` | dict | Adjacency matrix, clustering, weight stats, strategies |

Data is loaded from `src/wiki/data/metrics/sample_<n>/`. If those files don't exist, it falls back to computing via the neuPrint API (requires `.env` with API token).

## Re-exporting metrics

When computation logic in `metrics.py` changes, or to generate data for a new sample size:

```bash
just export
```

This writes clean JSON/CSV/npy files to `src/wiki/data/metrics/sample_100/`. Commit the updated files to git so the wiki can run without API access.

## Charting conventions

- **Altair**: bar charts, histograms, distributions (most charts)
- **Plotly**: heatmaps, treemaps, interactive 3D
- `setup_plotly_theme()` is called once at startup in `app.py`
- Domain colors (neurotransmitters): `digital_drosophila.constants.NT_COLORS`
- Chart colors and Plotly layout: `wiki.theme` (`SUPERCLASS_COLORS`, `ADJ_COLORSCALE`, `HEATMAP_LAYOUT`)

## Current pages

- **Data Analysis** (`data-analysis`) — dataset overview metrics, superclass/cell-type/neurotransmitter distributions, synapse histograms, motor neuron breakdowns, adjacency matrix heatmaps, weight distributions
- **Parameter Strategies** (`strategies`) — three approaches for mapping synapse counts to SNN parameters, summary table, weight/threshold distribution charts per strategy
