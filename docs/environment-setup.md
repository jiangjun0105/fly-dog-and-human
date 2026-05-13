# Environment Setup

Instructions for setting up the Digital Drosophila development environment from scratch.

## Prerequisites

- Linux (tested on Ubuntu 22.04, kernel 6.8)
- NVIDIA GPU with CUDA support (tested on A10G, 23GB VRAM, compute capability 8.6)
- NVIDIA driver installed (`nvidia-smi` should work)
- Internet access (for neuPrint API and package downloads)

## 1. Install uv (Python package manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc  # or restart your shell
```

Verify:
```bash
uv --version  # tested with 0.11.14
```

## 2. Install CUDA Toolkit

The NVIDIA driver provides `libcuda.so`, but GeNN needs the CUDA compiler (`nvcc`) to build GPU kernels at runtime.

```bash
sudo apt-get update
sudo apt-get install -y cuda-toolkit-12-6
```

Verify:
```bash
/usr/local/cuda/bin/nvcc --version  # should show CUDA 12.6
```

Add to your shell profile if not already present:
```bash
export PATH="/usr/local/cuda/bin:$PATH"
```

## 3. Clone and initialize the project

```bash
git clone <repo-url> ai-experiments
cd ai-experiments
```

## 4. Set up the neuPrint API token

1. Go to https://neuprint.janelia.org/ and sign in with Google
2. Copy your API token from the account menu
3. Create a `.env` file in the repository root:

```bash
echo 'NEU_PRINT_API_KEY=<your-token-here>' > .env
```

## 5. Install Python dependencies

```bash
uv sync
```

This installs Python 3.12 (managed by uv) and all dependencies defined in `pyproject.toml`:

| Package | Version | Purpose |
|---------|---------|---------|
| `brian2` | 2.10.1 | SNN simulation framework |
| `pygenn` | 5.4.0 | GPU-accelerated SNN backend (compiled from GitHub source) |
| `neuprint-python` | 0.6.1 | Query the male-cns:v0.9 connectome via neuPrint API |
| `plotly` | 6.7.0 | Interactive HTML visualizations |
| `pandas` | 3.0.3 | Data manipulation |
| `numpy` | 2.4.4 | Numerical computing |
| `scipy` | 1.17.1 | Sparse matrices, scientific computing |
| `python-dotenv` | 1.2.2 | Load `.env` file for API tokens |

Note: `pygenn` is installed from source (`https://github.com/genn-team/genn/archive/refs/tags/5.4.0.zip`) because it is not published on PyPI. The first build takes ~2 minutes as it compiles C++ extensions.

## 6. Verify the installation

Run these checks to confirm everything works:

```bash
# Brian2
uv run python -c "import brian2; print(f'Brian2: {brian2.__version__}')"

# PyGeNN (needs CUDA in PATH)
CUDA_PATH=/usr/local/cuda uv run python -c "
from pygenn import GeNNModel
model = GeNNModel('float', 'verify')
model.dt = 1.0
model.add_neuron_population('test', 10, 'LIF',
    {'C': 1.0, 'TauM': 20.0, 'Vrest': -60.0, 'Vreset': -60.0, 'Vthresh': -50.0, 'Ioffset': 0.0, 'TauRefrac': 2.0},
    {'V': -60.0, 'RefracTime': 0.0})
model.build()
model.load()
print('GeNN: GPU build and load OK')
"

# neuPrint API connection
uv run python -c "
import os
from dotenv import load_dotenv
from neuprint import Client, set_default_client, fetch_meta
load_dotenv('.env')
c = Client('neuprint.janelia.org', dataset='male-cns:v0.9', token=os.environ['NEU_PRINT_API_KEY'])
set_default_client(c)
meta = fetch_meta()
print(f'neuPrint: connected to male-cns:v0.9')
"
```

All three should complete without errors. The GeNN verification step compiles a small CUDA kernel (creates a `verify_CODE/` directory, which is gitignored).

## 7. Generate the exploration report

```bash
uv run python scripts/explore_connectome.py
```

This queries the neuPrint API, fetches VNC neuron data, and generates an interactive HTML report at `reports/connectome_exploration.html`. Open it in a browser to explore the dataset.

## Troubleshooting

### `nvcc` not found
Ensure CUDA toolkit is installed and `/usr/local/cuda/bin` is on your `PATH`.

### PyGeNN build fails
- Check that `nvcc --version` works
- Set `CUDA_PATH=/usr/local/cuda` before running
- GeNN 5.4.0 requires CUDA 11.0+ and a GPU with compute capability 3.5+

### neuPrint connection fails
- Verify your API token is correct in `.env`
- Check that `NEU_PRINT_API_KEY` is the exact variable name
- The token expires after ~1 year; generate a new one at https://neuprint.janelia.org/

### `brian2genn` import error (`pkg_resources`)
This is a known issue — `brian2genn` depends on the deprecated `pkg_resources` module. It is not needed; use PyGeNN directly for GPU acceleration instead.

### GeNN `*_CODE/` directories
GeNN compiles CUDA kernels into directories named `<model_name>_CODE/`. These are build artifacts and are gitignored. Delete them freely; they are regenerated on the next run.
