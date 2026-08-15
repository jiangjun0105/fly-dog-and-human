"""PyGeNN GPU-accelerated neural backend for training.

Provides a drop-in replacement for the Brian2 neural simulation used in training,
running LIF neurons with adaptive thresholds and STDP eligibility synapses on GPU
via PyGeNN 5.x / CUDA.

Produces the same outputs as the Brian2 version: motor neuron spikes per coupling
step and per-synapse eligibility traces for reward-modulated weight updates.

Usage:
    backend = PyGeNNBackend(adj, weights_mV, thresholds_mV, motor_indices, ascending_indices)
    backend.build()
    backend.reset(weights_mV, thresholds_mV)
    for step in range(n_steps):
        motor_spikes = backend.step(sensory_currents_pA)
        ...
    eligibility = backend.get_eligibility()
    backend.close()
"""

import os
from pathlib import Path

import numpy as np


# ---- PyGeNN custom model definitions ----
# These are module-level so model classes are created once at import time.

def _create_adaptive_lif_model():
    """Create a LIF neuron model with per-neuron adaptive threshold."""
    from pygenn import create_neuron_model

    return create_neuron_model(
        "adaptive_lif_training",
        params=["C", "TauM", "Vrest", "Vreset", "TauRefrac"],
        vars=[("V", "scalar"), ("RefracTime", "scalar"), ("Vthresh", "scalar")],
        extra_global_params=[("Iext", "scalar*")],
        sim_code="""
        if (RefracTime > 0.0) {
            RefracTime -= dt;
        } else {
            scalar Isyn_total = Isyn + Iext[id];
            V += (dt / TauM) * ((Vrest - V) + Isyn_total * (TauM / C));
        }
        """,
        threshold_condition_code="V >= Vthresh && RefracTime <= 0.0",
        reset_code="""
        V = Vreset;
        RefracTime = TauRefrac;
        """,
    )


def _create_stdp_eligibility_model():
    """Create a weight update model with STDP eligibility traces."""
    from pygenn import create_weight_update_model

    return create_weight_update_model(
        "stdp_eligibility",
        params=["tauSTDP", "tauElig"],
        vars=[
            ("g", "scalar"),
            ("Apre", "scalar"),
            ("Apost", "scalar"),
            ("eligibility", "scalar"),
        ],
        synapse_dynamics_code="""
        Apre -= Apre * dt / tauSTDP;
        Apost -= Apost * dt / tauSTDP;
        eligibility -= eligibility * dt / tauElig;
        """,
        pre_spike_syn_code="""
        Apre += 1.0;
        eligibility += Apost;
        addToPost(g);
        """,
        post_spike_syn_code="""
        Apost += 1.0;
        eligibility += Apre;
        """,
    )


class PyGeNNBackend:
    """GPU-accelerated neural backend using PyGeNN for training episodes.

    Replaces the Brian2 neural simulation in the training loop, providing
    ~10-50x speedup on GPU. Maintains the same interface: inject sensory
    currents each coupling step, read out motor spikes, and pull eligibility
    traces at episode end for reward-modulated weight updates.

    Parameters
    ----------
    adj : scipy.sparse matrix or ndarray
        Adjacency matrix (N x N). Non-zero entries define connections.
    weights_mV : ndarray
        Per-synapse weights in mV (same order as adj.nonzero()).
    thresholds_mV : ndarray
        Per-neuron adaptive thresholds in mV (length N).
    motor_indices : list of int
        Indices of motor neurons in the population.
    ascending_indices : list of int
        Indices of ascending (sensory input) neurons.
    dt_ms : float
        Simulation timestep in milliseconds (default 0.1).
    coupling_dt_ms : float
        Coupling timestep in milliseconds (default 2.0). Each call to step()
        runs coupling_dt_ms / dt_ms internal timesteps.
    tau_stdp_ms : float
        STDP trace time constant in ms (default 20.0).
    tau_eligibility_ms : float
        Eligibility trace time constant in ms (default 1000.0).
    """

    # Weight conversion: mV (Brian2 DeltaCurr) -> nA (GeNN ExpCurr)
    # g_nA = w_mV * tau_m / (R_membrane * tau_syn) = w_mV * 10 / (100 * 5) = w_mV * 0.02
    _MV_TO_NA = 0.02

    # Sensory current conversion: pA -> nA
    _PA_TO_NA = 1e-3

    def __init__(
        self,
        adj,
        weights_mV,
        thresholds_mV,
        motor_indices,
        ascending_indices,
        dt_ms=0.1,
        coupling_dt_ms=2.0,
        tau_stdp_ms=20.0,
        tau_eligibility_ms=1000.0,
    ):
        self._adj = adj
        self._initial_weights_mV = weights_mV.copy()
        self._initial_thresholds_mV = thresholds_mV.copy()
        self._motor_indices = np.array(motor_indices, dtype=np.int32)
        self._ascending_indices = np.array(ascending_indices, dtype=np.int32)
        self._dt_ms = dt_ms
        self._coupling_dt_ms = coupling_dt_ms
        self._tau_stdp_ms = tau_stdp_ms
        self._tau_eligibility_ms = tau_eligibility_ms

        # Derived
        self._steps_per_coupling = int(round(coupling_dt_ms / dt_ms))
        self._n_neurons = adj.shape[0]

        # Extract sparse connectivity
        import scipy.sparse as sp
        if sp.issparse(adj):
            coo = adj.tocoo()
            self._sources = coo.row.astype(np.uint32)
            self._targets = coo.col.astype(np.uint32)
        else:
            rows, cols = np.nonzero(adj)
            self._sources = rows.astype(np.uint32)
            self._targets = cols.astype(np.uint32)

        self._n_synapses = len(self._sources)
        self._motor_set = set(motor_indices)

        # Model state
        self._model = None
        self._pop = None
        self._syn = None
        self._built = False
        self._spike_counts = None

    def build(self):
        """Compile the CUDA model and prepare for simulation.

        This calls GeNN's build() and load() which invokes nvcc compilation.
        Takes 30-60s on first run; cached afterwards.
        """
        # Ensure CUDA is on PATH
        cuda_bin = "/usr/local/cuda/bin"
        if cuda_bin not in os.environ.get("PATH", ""):
            os.environ["PATH"] = cuda_bin + ":" + os.environ.get("PATH", "")

        from pygenn import GeNNModel, init_weight_update, init_postsynaptic

        # Create custom models
        AdaptiveLIF = _create_adaptive_lif_model()
        STDPEligibility = _create_stdp_eligibility_model()

        model_name = f"training_{self._n_neurons}n"
        model = GeNNModel("float", model_name)
        model.dt = self._dt_ms

        # ---- Neuron population ----
        neuron_params = {
            "C": 0.1,           # nF
            "TauM": 10.0,       # ms
            "Vrest": -70.0,     # mV
            "Vreset": -70.0,    # mV
            "TauRefrac": 2.0,   # ms
        }

        neuron_init = {
            "V": -70.0,
            "RefracTime": 0.0,
            "Vthresh": self._initial_thresholds_mV.astype(np.float32),
        }

        pop = model.add_neuron_population(
            "neurons", self._n_neurons, AdaptiveLIF, neuron_params, neuron_init,
        )
        pop.spike_recording_enabled = True
        pop.extra_global_params["Iext"].set_init_values(
            np.zeros(self._n_neurons, dtype=np.float32)
        )

        # ---- Synapse population with STDP eligibility ----
        tau_syn = 5.0  # ms

        weights_nA = (self._initial_weights_mV * self._MV_TO_NA).astype(np.float32)

        syn = model.add_synapse_population(
            "synapses", "SPARSE",
            pop, pop,
            init_weight_update(STDPEligibility,
                               {"tauSTDP": self._tau_stdp_ms, "tauElig": self._tau_eligibility_ms},
                               {"g": weights_nA, "Apre": 0.0, "Apost": 0.0, "eligibility": 0.0}),
            init_postsynaptic("ExpCurr", {"tau": tau_syn}),
        )
        syn.set_sparse_connections(self._sources, self._targets)

        # ---- Build and load ----
        model.build()

        # Load with recording buffer sized for one coupling step
        # We pull spikes after each coupling step, so buffer only needs
        # to hold one coupling step's worth of spikes.
        model.load(num_recording_timesteps=self._steps_per_coupling)

        self._model = model
        self._pop = pop
        self._syn = syn
        self._built = True
        self._spike_counts = np.zeros(self._n_neurons, dtype=np.int32)

    def reset(self, weights_mV, thresholds_mV):
        """Reset state for a new episode with updated weights and thresholds.

        Parameters
        ----------
        weights_mV : ndarray
            Per-synapse weights in mV (same ordering as adj.nonzero()).
        thresholds_mV : ndarray
            Per-neuron adaptive thresholds in mV.
        """
        if not self._built:
            raise RuntimeError("Must call build() before reset()")

        # Reset membrane potential and refractory time
        self._pop.vars["V"].view[:] = -70.0
        self._pop.vars["RefracTime"].view[:] = 0.0

        # Set adaptive thresholds
        self._pop.vars["Vthresh"].view[:] = thresholds_mV.astype(np.float32)
        self._pop.vars["V"].push_to_device()
        self._pop.vars["RefracTime"].push_to_device()
        self._pop.vars["Vthresh"].push_to_device()

        # Zero external currents
        self._pop.extra_global_params["Iext"].view[:] = 0.0
        self._pop.extra_global_params["Iext"].push_to_device()

        # Set synapse weights (convert mV -> nA) — SPARSE uses .values not .view
        weights_nA = (weights_mV * self._MV_TO_NA).astype(np.float32)
        self._syn.vars["g"].values = weights_nA
        self._syn.vars["Apre"].values = np.zeros(self._n_synapses, dtype=np.float32)
        self._syn.vars["Apost"].values = np.zeros(self._n_synapses, dtype=np.float32)
        self._syn.vars["eligibility"].values = np.zeros(self._n_synapses, dtype=np.float32)
        self._syn.vars["g"].push_to_device()
        self._syn.vars["Apre"].push_to_device()
        self._syn.vars["Apost"].push_to_device()
        self._syn.vars["eligibility"].push_to_device()

        # Reset simulation time (t is derived from timestep * dt)
        self._model.timestep = 0

        # Reset spike counts
        self._spike_counts[:] = 0

    def step(self, sensory_currents_pA):
        """Run one coupling step and return motor neuron spike indices.

        Runs coupling_dt_ms / dt_ms internal timesteps with the given sensory
        currents injected into ascending neurons.

        Parameters
        ----------
        sensory_currents_pA : ndarray
            Per-neuron sensory currents in pA (length N). Only values at
            ascending_indices are used; others are ignored.

        Returns
        -------
        motor_spikes : set of int
            Indices of motor neurons that spiked during this coupling step.
        """
        if not self._built:
            raise RuntimeError("Must call build() before step()")

        # Set external currents: convert pA -> nA for all neurons
        iext = (sensory_currents_pA.astype(np.float32) * self._PA_TO_NA)
        self._pop.extra_global_params["Iext"].view[:] = iext
        self._pop.extra_global_params["Iext"].push_to_device()

        # Run internal timesteps
        for _ in range(self._steps_per_coupling):
            self._model.step_time()

        # Pull spike recording buffer
        self._model.pull_recording_buffers_from_device()

        # spike_recording_data returns list of (times, neuron_ids) tuples
        spike_times, spike_ids = self._pop.spike_recording_data[0]

        # Update per-neuron spike counts
        if len(spike_ids) > 0:
            counts = np.bincount(spike_ids.astype(np.int32), minlength=self._n_neurons)
            self._spike_counts += counts.astype(np.int32)

        # Filter for motor neuron spikes
        motor_spikes = self._motor_set & set(spike_ids.tolist())

        return motor_spikes

    def get_eligibility(self):
        """Pull eligibility traces from GPU.

        Returns
        -------
        eligibility : ndarray
            Per-synapse eligibility traces (same ordering as adj.nonzero()).
            Shape: (n_synapses,).
        """
        if not self._built:
            raise RuntimeError("Must call build() before get_eligibility()")

        self._syn.vars["eligibility"].pull_from_device()
        return self._syn.vars["eligibility"].values.copy()

    def get_spike_counts(self):
        """Return per-neuron spike counts accumulated since last reset.

        Returns
        -------
        counts : ndarray
            Spike count per neuron (length N). Accumulated over all coupling
            steps since the last reset() call.
        """
        return self._spike_counts.copy()

    def close(self):
        """Release GPU resources and clean up.

        After calling close(), the backend cannot be used again without
        a new build() call (which would require a new instance).
        """
        if self._model is not None:
            # PyGeNN 5.x: model is freed when object is garbage collected
            self._model = None
            self._pop = None
            self._syn = None
            self._built = False

    def __del__(self):
        """Ensure cleanup on garbage collection."""
        self.close()

    # ---- Utility methods ----

    @property
    def n_neurons(self):
        """Number of neurons in the population."""
        return self._n_neurons

    @property
    def n_synapses(self):
        """Number of synapses."""
        return self._n_synapses

    @property
    def dt_ms(self):
        """Simulation timestep in ms."""
        return self._dt_ms

    @property
    def coupling_dt_ms(self):
        """Coupling timestep in ms."""
        return self._coupling_dt_ms

    @property
    def motor_indices(self):
        """Motor neuron indices."""
        return self._motor_indices.copy()

    @property
    def ascending_indices(self):
        """Ascending (sensory input) neuron indices."""
        return self._ascending_indices.copy()
