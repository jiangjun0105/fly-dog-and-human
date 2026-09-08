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

# --------------------------------------------------------------------------
# Synaptic transmission delay
# --------------------------------------------------------------------------
# Chemical synaptic transmission in Drosophila costs ~0.8-1.5 ms per synapse
# (vesicle release + diffusion + receptor kinetics), on top of the ~1-4 ms of
# postsynaptic membrane integration that the LIF equation already models.
# Without this term every measured round trip is optimistic by 1-3 ms per hop,
# which matters because loop-closure latency is compared against the ~20 ms
# STDP window.
#
# The range is a literature estimate, so it is configuration rather than a
# constant: pass a dict of the same shape to override it (e.g. to test
# sensitivity of a latency result to the assumed delay).
#
#   min_ms / max_ms : bounds of the per-synapse uniform draw. Setting both to
#                     the same value gives a homogeneous delay; setting both to
#                     0.0 restores the old instantaneous behaviour.
#   seed            : RNG seed so delays are reproducible across runs and
#                     across the CPU/GPU backends.
DEFAULT_SYNAPTIC_DELAY = {
    "min_ms": 0.8,
    "max_ms": 1.5,
    "seed": 20260817,
}

# --------------------------------------------------------------------------
# Soft-bound ceiling on synaptic weight magnitude (mV)
# --------------------------------------------------------------------------
# Derived from the weight distribution of the full VNC connectome
# (data/cache/full_vnc_network/) run through the standard weight formula
#   |w| = log1p(synapse_count) * confidence * (0.5 if inhibitory else 1.0) * 0.6
#
# Over the 3,910,246 sign-constrained synapses, log|w| is close to Gaussian
# (skew 0.14, excess kurtosis -0.59), i.e. |w| is log-normal.  Taking the +3 sd
# point of that log-normal fit per polarity:
#
#   excitatory  n=2,316,547  median 0.638  p99 2.401  max 3.978  ->  exp(mu+3sd) = 3.56
#   inhibitory  n=1,593,699  median 0.291  p99 1.113  max 1.861  ->  exp(mu+3sd) = 1.66
#
# 65 excitatory (0.0028%) and 61 inhibitory (0.0038%) real synapses sit above
# their own ceiling, so this is the connectome's own upper edge rather than a
# round number.  Polarities are separated because inhibitory weights are
# additionally attenuated by 0.5 (GABA-A reversal near V_rest); a single shared
# ceiling would let inhibition grow to twice anything present in the connectome.
#
# "unsigned" applies to synapses whose presynaptic neurotransmitter is
# modulatory or unclear (sign 0, 204,608 synapses).  Those start at exactly
# 0 mV and carry no Dale constraint, so they are bounded by magnitude only,
# using the wider of the two ceilings.
DEFAULT_W_MAX_MV = {
    "excitatory": 3.56,
    "inhibitory": 1.66,
    "unsigned": 3.56,
}


def sample_synaptic_delays_ms(n_synapses, delay_params=None):
    """Draw per-synapse transmission delays in milliseconds.

    Parameters
    ----------
    n_synapses : int
        Number of synapses to draw delays for.
    delay_params : dict, optional
        Overrides for ``DEFAULT_SYNAPTIC_DELAY`` (``min_ms``, ``max_ms``,
        ``seed``). Missing keys fall back to the default.

    Returns
    -------
    delays_ms : ndarray of float
        Delay per synapse in ms, in the same order as the synapse list.
    """
    params = dict(DEFAULT_SYNAPTIC_DELAY)
    if delay_params:
        params.update(delay_params)

    min_ms = float(params["min_ms"])
    max_ms = float(params["max_ms"])
    if min_ms < 0 or max_ms < min_ms:
        raise ValueError(
            f"Invalid synaptic delay range: min_ms={min_ms}, max_ms={max_ms}"
        )

    if max_ms == min_ms:
        return np.full(n_synapses, min_ms, dtype=float)

    rng = np.random.default_rng(params["seed"])
    return rng.uniform(min_ms, max_ms, size=n_synapses)


def quantize_delays_to_steps(delays_ms, dt_ms):
    """Convert delays in ms to whole simulation timesteps.

    Uses ``floor(delay/dt + 0.5)`` (round half *up*), which is exactly what
    Brian2's spike queue does internally (``brian2/synapses/spikequeue.h``:
    ``(int)(delay / _dt + 0.5)``). The GPU backend must use the same rule or the
    two backends disagree by one timestep on any delay landing on a half-step
    boundary. Two details matter and both were observed to bite:

    * ``np.rint`` rounds half to *even*, so 1.15 ms at dt = 0.1 ms would give
      11 steps where Brian2 gives 12.
    * The division must be done in SI seconds, as Brian2 does. In milliseconds
      ``1.15 / 0.1`` evaluates to 11.499999999999998 and floors to 11, while
      ``1.15e-3 / 0.1e-3`` is exactly 11.5 and floors to 12. 1.15 ms is the
      midpoint of the default 0.8-1.5 ms range, so this is not a corner case.

    Parameters
    ----------
    delays_ms : ndarray
        Delays in milliseconds.
    dt_ms : float
        Simulation timestep in milliseconds.

    Returns
    -------
    steps : ndarray of int
        Delay in whole timesteps.
    """
    delays_s = np.asarray(delays_ms, dtype=float) * 1e-3
    dt_s = float(dt_ms) * 1e-3
    return np.floor(delays_s / dt_s + 0.5).astype(int)


def assign_synaptic_delays(S, delay_params=None):
    """Set per-synapse transmission delays on a connected Brian2 Synapses object.

    Must be called after ``S.connect(...)``.

    Parameters
    ----------
    S : brian2.Synapses
        Connected synapses object.
    delay_params : dict, optional
        See :func:`sample_synaptic_delays_ms`.

    Returns
    -------
    delays_ms : ndarray
        The delays that were assigned, in ms.
    """
    n_synapses = len(S)
    delays_ms = sample_synaptic_delays_ms(n_synapses, delay_params)
    S.delay = delays_ms * ms
    return delays_ms


def synapse_w_max(syn_sign, w_max=None):
    """Per-synapse magnitude ceiling from presynaptic polarity.

    Parameters
    ----------
    syn_sign : ndarray
        Per-synapse presynaptic sign (+1 excitatory, -1 inhibitory, 0 unsigned),
        i.e. ``sign_vector[sources]``.
    w_max : dict or float, optional
        Overrides for ``DEFAULT_W_MAX_MV``. A scalar applies one ceiling to all
        polarities.

    Returns
    -------
    w_max_per_synapse : ndarray of float
        Ceiling on ``|w|`` in mV for each synapse.
    """
    if np.isscalar(w_max):
        return np.full(len(syn_sign), float(w_max), dtype=float)

    params = dict(DEFAULT_W_MAX_MV)
    if w_max:
        params.update(w_max)

    out = np.full(len(syn_sign), float(params["unsigned"]), dtype=float)
    out[syn_sign > 0] = float(params["excitatory"])
    out[syn_sign < 0] = float(params["inhibitory"])
    return out


def enforce_dale(weights, syn_sign):
    """Project weights back onto their allowed sign (Dale's principle).

    Parameters
    ----------
    weights : ndarray
        Per-synapse weights in mV (modified in place and returned).
    syn_sign : ndarray
        Per-synapse presynaptic sign (``sign_vector[sources]``).

    Returns
    -------
    weights : ndarray
        The same array, with excitatory weights >= 0 and inhibitory <= 0.
    """
    exc_mask = syn_sign > 0
    inh_mask = syn_sign < 0
    weights[exc_mask] = np.maximum(weights[exc_mask], 0.0)
    weights[inh_mask] = np.minimum(weights[inh_mask], 0.0)
    return weights


def apply_bounded_update(weights, dw, syn_sign, w_max=None):
    """Apply a weight update with soft-bounded potentiation and Dale's principle.

    Potentiation (any change that increases ``|w|`` in the synapse's allowed
    direction) is scaled by ``(1 - |w| / w_max)``, so growth saturates smoothly
    and asymptotically instead of being clipped. Depression is left additive,
    then floored at zero so the sign never flips.

    Because inhibitory weights are negative, the bound is applied in magnitude
    space: the update is rotated into ``|w|`` using the synapse's allowed sign,
    attenuated there, and rotated back. Unsigned (modulatory / unclear
    presynaptic NT) synapses have no allowed direction, so their *current* sign
    is used and any growth in magnitude is attenuated symmetrically.

    Parameters
    ----------
    weights : ndarray
        Current per-synapse weights in mV.
    dw : ndarray or float
        Proposed weight change in mV (same units/order as ``weights``).
    syn_sign : ndarray
        Per-synapse presynaptic sign (``sign_vector[sources]``).
    w_max : dict or float, optional
        See :func:`synapse_w_max`.

    Returns
    -------
    new_weights : ndarray
        Updated weights (new array; inputs are not modified).
    """
    weights = np.asarray(weights, dtype=float)
    dw = np.broadcast_to(np.asarray(dw, dtype=float), weights.shape)
    syn_sign = np.asarray(syn_sign)
    w_max_per_syn = synapse_w_max(syn_sign, w_max)

    # Allowed direction of growth. Unsigned synapses have none, so follow the
    # weight they currently hold (and treat exactly-zero as excitatory-facing
    # so that dw itself picks the direction).
    direction = np.where(syn_sign != 0, syn_sign, np.sign(weights))
    direction = np.where(direction == 0, 1.0, direction).astype(float)

    magnitude = weights * direction          # >= 0 for well-formed weights
    d_magnitude = dw * direction             # > 0 means potentiation

    headroom = np.clip(1.0 - np.abs(magnitude) / w_max_per_syn, 0.0, 1.0)
    d_magnitude = np.where(d_magnitude > 0, d_magnitude * headroom, d_magnitude)

    new_magnitude = np.maximum(magnitude + d_magnitude, 0.0)
    new_weights = new_magnitude * direction

    return enforce_dale(new_weights, syn_sign)


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


def create_synapses_minimal(G, adj, scale=0.02, delay_params=None):
    """Create synapses with raw synapse-count weights (no sign constraint).

    Parameters
    ----------
    G : NeuronGroup
        The neuron group to connect.
    adj : ndarray
        Adjacency matrix of synapse counts.
    scale : float
        Weight scale in mV per synapse count.
    delay_params : dict, optional
        Synaptic transmission delay overrides; see ``DEFAULT_SYNAPTIC_DELAY``.

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
    assign_synaptic_delays(S, delay_params)
    return S, sources, targets


def create_synapses_constrained(G, adj, neurons_df, scale=0.6, inh_attenuation=0.5,
                                delay_params=None):
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
    delay_params : dict, optional
        Synaptic transmission delay overrides; see ``DEFAULT_SYNAPTIC_DELAY``.

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
    assign_synaptic_delays(S, delay_params)

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

    # No transmission delay here, deliberately. These are virtual Poisson
    # sources standing in for drive that originates outside the modelled
    # population, not identified presynaptic neurons — there is no synapse whose
    # latency we would be modelling. A fixed delay on a stationary Poisson
    # process is also statistically a no-op (it only shifts the spike train,
    # which is time-shift invariant), so it would cost delay buffers and buy
    # nothing measurable. Latency measurements should be made against the
    # recurrent connectome synapses, which do carry delay.
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
    # As in create_poisson_drive: no delay on background input. See the note
    # there.
    PG_bg = PoissonGroup(n_sources, rates=rate)
    S_bg = Synapses(PG_bg, G, on_pre=f"v_post += {float(weight/mV)}*mV")
    bg_i = np.repeat(np.arange(n_sources), n_neurons)
    bg_j = np.tile(np.arange(n_neurons), n_sources)
    S_bg.connect(i=bg_i, j=bg_j)

    return PG_bg, S_bg
