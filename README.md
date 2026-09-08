# Digital Drosophila

Biologically-mapped spiking neural network for *Drosophila* motor control using Brian2 + GeNN and the male-cns:v0.9 connectome.

## Quick start

```bash
# 1. Install tooling
curl -LsSf https://astral.sh/uv/install.sh | sh          # Python package manager
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/.local/bin  # task runner

# 2. Clone & install
git clone <repo-url> ai-experiments && cd ai-experiments
cp .env.example .env   # then fill in your neuPrint API token
uv sync                # installs Python 3.12 + all dependencies

# 3. Launch the wiki
just wiki
```

## Prerequisites

- Linux (tested on Ubuntu 22.04, kernel 6.8)
- NVIDIA GPU with CUDA support (tested on A10G, 23GB VRAM)
- NVIDIA driver installed (`nvidia-smi` should work)
- CUDA Toolkit 12.6 (`sudo apt-get install -y cuda-toolkit-12-6`)

## Environment setup

### uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
uv --version  # tested with 0.11.14
```

### just

```bash
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/.local/bin
```

Make sure `~/.local/bin` is on your `PATH`. Add to your shell profile if needed:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

### CUDA Toolkit

GeNN compiles CUDA kernels at runtime and needs `nvcc`:

```bash
sudo apt-get update && sudo apt-get install -y cuda-toolkit-12-6
export PATH="/usr/local/cuda/bin:$PATH"  # add to shell profile
```

### neuPrint API token

1. Sign in at https://neuprint.janelia.org/
2. Copy your token from the account menu
3. Create `.env` in the repo root:

```bash
echo 'NEU_PRINT_API_KEY=<your-token>' > .env
```

### Python dependencies

```bash
uv sync
```

This installs Python 3.12 and all dependencies. Note: `pygenn` is built from source (~2 min first time).

## Available commands

```
just wiki       # Launch the Streamlit connectome explorer
```

## Project structure

```
src/digital_drosophila/     # research code
├── constants.py            # domain constants (NT signs, colors)
└── data.py                 # neuPrint API access with disk caching (joblib)

src/wiki/                   # interactive explorer (Streamlit)
├── app.py                  # sidebar-routed multi-page UI
├── metrics.py              # pre-computed metrics layer (all cached)
├── theme.py                # Plotly/chart styling
├── pages/                  # one module per wiki page
│   ├── data_analysis.py    # connectome overview, distributions, connectivity
│   └── strategies.py       # parameter conversion strategy comparison
└── data/metrics/           # exported metrics (JSON/CSV/npy, git-tracked)

scripts/
└── explore_connectome.py   # static HTML report generator

data/cache/                 # cached API responses (gitignored)
```

## Detailed setup guide

See [docs/environment-setup.md](docs/environment-setup.md) for full setup instructions including verification steps and troubleshooting.

## Multica auto-agent

This repository was visited by the Multica auto-agent crew on 2026-08-15, running a demo task via Multica dispatch to verify the full dispatch→execute→PR loop.
