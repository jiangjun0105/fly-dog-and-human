"""Network builder: load data, create NeuronGroup, Synapses, and input drives.

This module provides the building blocks for constructing Brian2 spiking
neural networks from the Digital Drosophila connectome sample data.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from brian2 import (
    Hz,
    Mohm,
    NeuronGroup,
    PoissonGroup,
    Synapses,
    mV,
    ms,
)

from .constants import NT_SIGN_MAP

# Default path to sample data (resolved relative to this file)
_PACKAGE_DIR = Path(__file__).resolve().parent
_DEFAULT_DATA_DIR = _PACKAGE_DIR.parent / "wiki" / "data" / "metrics" / "sample_100"

# --------------------------------------------------------------------------
# Default LIF parameters (from docs/neuroscience/02-lif-model-design.md)
# --------------------------------------------------------------------------
DEFAULT_LIF_PARAMS = {
    "tau_m": 10 * ms,
    "V_rest": -70 * mV,
    "V_th": -50 * mV,
    "V_reset": -70 * mV,
    "R_membrane": 100 * Mohm,
    "t_refract": 2 * ms,
}


def load_sample_data(data_dir=None):
    """Load adjacency matrix and neuron metadata from sample data directory.

    Parameters
    ----------
    data_dir : Path or str, optional
        Path to the sample_100 data directory. Defaults to the bundled sample.

    Returns
    -------
    adj : ndarray
        Adjacency matrix (N x N) of synapse counts.
    neurons_df : DataFrame
        Neuron metadata with columns including 'superclass', 'consensusNt', etc.
    """
    if data_dir is None:
        data_dir = _DEFAULT_DATA_DIR
    data_dir = Path(data_dir)

    adj = np.load(data_dir / "adj.npy")
    neurons_df = pd.read_csv(data_dir / "sample_neurons.csv")
    return adj, neurons_df


def create_neuron_group(n, params=None):
    """Create a LIF NeuronGroup with standard parameters.

    Parameters
    ----------
    n : int
        Number of neurons.
    params : dict, optional
        LIF parameters. Defaults to DEFAULT_LIF_PARAMS.

    Returns
    -------
    G : NeuronGroup
        Brian2 NeuronGroup initialized at V_rest.
    """
    if params is None:
        params = DEFAULT_LIF_PARAMS

    tau_m = params["tau_m"]
    V_rest = params["V_rest"]
    V_th = params["V_th"]
    V_reset = params["V_reset"]
    R_membrane = params["R_membrane"]
    t_refract = params["t_refract"]

    eqs = """
    dv/dt = (-(v - V_rest) + R_membrane * I) / tau_m : volt (unless refractory)
    I : amp
    """

    # Pass namespace explicitly so Brian2 can resolve constants regardless of
    # call-site frame depth (required when invoked from within a package).
    namespace = {
        "tau_m": tau_m,
        "V_rest": V_rest,
        "V_th": V_th,
        "V_reset": V_reset,
        "R_membrane": R_membrane,
    }

    G = NeuronGroup(
        n,
        eqs,
        threshold="v > V_th",
        reset="v = V_reset",
        refractory=t_refract,
        method="euler",
        namespace=namespace,
    )
    G.v = V_rest
    return G


def create_synapses_minimal(G, adj, scale=0.02):
    """Create synapses with raw synapse-count weights (no sign constraint).

    Parameters
    ----------
    G : NeuronGroup
        The neuron group to connect.
    adj : ndarray
        Adjacency matrix of synapse counts.
    scale : float
        Weight scale in mV per synapse count.

    Returns
    -------
    S : Synapses
        Connected Brian2 Synapses object.
    sources : ndarray
        Presynaptic neuron indices.
    targets : ndarray
        Postsynaptic neuron indices.
    """
    S = Synapses(G, G, "w : volt", on_pre="v_post += w")
    sources, targets = adj.nonzero()
    S.connect(i=sources, j=targets)
    S.w = adj[sources, targets] * scale * mV
    return S, sources, targets


def create_synapses_constrained(G, adj, neurons_df, scale=0.6, inh_attenuation=0.5):
    """Create synapses with sign-constrained weights (Dale's principle).

    Weight formula: w_ij = log(1 + synapse_count) * sign_i * confidence_i * scale
    Inhibitory weights are additionally attenuated to reflect GABA-A reversal
    potential proximity to V_rest.

    Parameters
    ----------
    G : NeuronGroup
        The neuron group to connect.
    adj : ndarray
        Adjacency matrix of synapse counts.
    neurons_df : DataFrame
        Neuron metadata (must have 'consensusNt' and 'predictedNtConfidence').
    scale : float
        Weight scale in mV.
    inh_attenuation : float
        Attenuation factor for inhibitory weights.

    Returns
    -------
    S : Synapses
        Connected Brian2 Synapses object.
    sources : ndarray
        Presynaptic neuron indices.
    targets : ndarray
        Postsynaptic neuron indices.
    weights_raw : ndarray
        Raw weight values in mV (before Brian2 unit multiplication).
    sign_vector : ndarray
        Per-neuron sign (+1, -1, or 0).
    """
    # Build sign vector from neurotransmitter types
    nt_series = neurons_df["consensusNt"]
    confidence = neurons_df["predictedNtConfidence"].values
    sign_vector = np.array([NT_SIGN_MAP.get(nt, 0) or 0 for nt in nt_series])

    # Create synapses
    S = Synapses(G, G, "w : volt", on_pre="v_post += w")
    sources, targets = adj.nonzero()
    S.connect(i=sources, j=targets)

    # Compute weights with sign constraint
    sign_scale = np.where(sign_vector[sources] >= 0, 1.0, inh_attenuation)
    weights_raw = (
        np.log1p(adj[sources, targets])
        * sign_vector[sources]
        * confidence[sources]
        * sign_scale
        * scale
    )
    S.w = weights_raw * mV

    return S, sources, targets, weights_raw, sign_vector


def create_poisson_drive(G, neurons_df, target_superclass="descending_neuron",
                         n_sources=50, rate=30 * Hz, weight=2.0 * mV):
    """Create targeted Poisson input to neurons of a specific superclass.

    Parameters
    ----------
    G : NeuronGroup
        Target neuron group.
    neurons_df : DataFrame
        Neuron metadata with 'superclass' column.
    target_superclass : str
        Which superclass to drive.
    n_sources : int
        Number of virtual Poisson sources.
    rate : brian2 quantity
        Firing rate of Poisson sources.
    weight : brian2 quantity
        PSP amplitude per spike.

    Returns
    -------
    PG : PoissonGroup
        The Poisson input group.
    S_input : Synapses
        Synapses from Poisson group to target neurons.
    target_idx : list
        Indices of targeted neurons.
    """
    target_idx = neurons_df[neurons_df["superclass"] == target_superclass].index.tolist()

    PG = PoissonGroup(n_sources, rates=rate)
    S_input = Synapses(PG, G, on_pre=f"v_post += {float(weight/mV)}*mV")
    poisson_i = np.repeat(np.arange(n_sources), len(target_idx))
    poisson_j = np.tile(target_idx, n_sources)
    S_input.connect(i=poisson_i, j=poisson_j)

    return PG, S_input, target_idx


def create_background_drive(G, n_neurons, n_sources=50, rate=22 * Hz, weight=1.3 * mV):
    """Create background Poisson input to all neurons.

    This represents missing network context (the full VNC has ~14,000 neurons;
    the 100-neuron sample lacks many inputs).

    Parameters
    ----------
    G : NeuronGroup
        Target neuron group.
    n_neurons : int
        Number of neurons in G.
    n_sources : int
        Number of background Poisson sources.
    rate : brian2 quantity
        Firing rate of background sources.
    weight : brian2 quantity
        PSP amplitude per spike.

    Returns
    -------
    PG_bg : PoissonGroup
        The background Poisson group.
    S_bg : Synapses
        Synapses from background group to all neurons.
    """
    PG_bg = PoissonGroup(n_sources, rates=rate)
    S_bg = Synapses(PG_bg, G, on_pre=f"v_post += {float(weight/mV)}*mV")
    bg_i = np.repeat(np.arange(n_sources), n_neurons)
    bg_j = np.tile(np.arange(n_neurons), n_sources)
    S_bg.connect(i=bg_i, j=bg_j)

    return PG_bg, S_bg
