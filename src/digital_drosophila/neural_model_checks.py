"""Verification probes for the synaptic-delay and soft-bounded-STDP changes.

Three checks, all run against real simulators (no analytic stand-ins):

1. ``check_propagation_delay`` — Brian2 chain probe. Stimulates a neuron above
   rheobase, records the downstream spike, and reports the elapsed time with
   and without the configured per-synapse delay. Covers both the monosynaptic
   (direct) and disynaptic (one interneuron) paths, so the result can be
   compared with the 2-4 ms / 5-8 ms expectation in the Level 1 spec.

2. ``check_propagation_delay_gpu`` — the same chain on the PyGeNN GPU backend,
   to confirm the two backends do not silently disagree on timings.

3. ``check_soft_bounding`` — drives a real Brian2 STDP synapse with sustained
   bursts (the Child 2 regime: unmodulated two-factor STDP, no reward term
   opposing growth) and shows the weight approaching ``w_max`` asymptotically
   rather than crossing it, next to the unbounded additive rule for contrast.

Usage
-----
    python -m digital_drosophila check neural_model
"""

import numpy as np

from .network import (
    DEFAULT_LIF_PARAMS,
    DEFAULT_SYNAPTIC_DELAY,
    DEFAULT_W_MAX_MV,
    apply_bounded_update,
    sample_synaptic_delays_ms,
    synapse_w_max,
)

# Rheobase for DEFAULT_LIF_PARAMS: (V_th - V_rest) / R_membrane
#   = 20 mV / 100 MOhm = 200 pA. Below this a neuron never fires.
RHEOBASE_PA = 200.0


# ==========================================================================
# 1 + 3. Brian2 probes
# ==========================================================================

def _build_chain(n_neurons, sources, targets, weights_mV, delays_ms, dt_ms=0.1):
    """Build a small Brian2 LIF chain with explicit per-synapse delays."""
    import brian2
    brian2.prefs.codegen.target = "numpy"
    from brian2 import (
        Network, NeuronGroup, SpikeMonitor, Synapses,
        defaultclock, mV, ms,
    )

    defaultclock.dt = dt_ms * ms

    p = DEFAULT_LIF_PARAMS
    eqs = """
    dv/dt = (-(v - V_rest) + R_membrane * I) / tau_m : volt (unless refractory)
    I : amp
    """
    namespace = {
        "tau_m": p["tau_m"],
        "V_rest": p["V_rest"],
        "R_membrane": p["R_membrane"],
        "V_th": p["V_th"],
        "V_reset": p["V_reset"],
    }
    G = NeuronGroup(
        n_neurons, eqs,
        threshold="v > V_th", reset="v = V_reset",
        refractory=p["t_refract"], method="euler", namespace=namespace,
    )
    G.v = p["V_rest"]

    S = Synapses(G, G, "w : volt", on_pre="v_post += w")
    S.connect(i=list(sources), j=list(targets))
    S.w = np.asarray(weights_mV) * mV
    S.delay = np.asarray(delays_ms) * ms

    M = SpikeMonitor(G)
    net = Network(G, S, M)
    return net, G, S, M


def _first_spike_times(M, n_neurons):
    """Return the first spike time (ms) per neuron, or NaN if it never fired."""
    from brian2 import ms
    t = np.asarray(M.t / ms)
    i = np.asarray(M.i)
    out = np.full(n_neurons, np.nan)
    for nid in range(n_neurons):
        ts = t[i == nid]
        if len(ts):
            out[nid] = ts.min()
    return out


def _run_chain_probe(psp_mV, delays_ms, drive_pA, duration_ms=200.0, dt_ms=0.1):
    """Run a 3-neuron chain (0 -> 1 -> 2) and return first-spike latencies.

    Returns
    -------
    dict with ``t0``, ``t1``, ``t2`` (absolute first-spike times in ms) and
    ``direct`` = t1 - t0, ``via_interneuron`` = t2 - t0.
    """
    from brian2 import ms, pA

    net, G, S, M = _build_chain(
        3, sources=[0, 1], targets=[1, 2],
        weights_mV=[psp_mV, psp_mV], delays_ms=delays_ms, dt_ms=dt_ms,
    )
    G.I = 0 * pA
    G.I[0] = drive_pA * pA
    net.run(duration_ms * ms)

    t = _first_spike_times(M, 3)
    return {
        "t0": t[0], "t1": t[1], "t2": t[2],
        "direct": t[1] - t[0],
        "via_interneuron": t[2] - t[0],
    }


def _run_pool_probe(pool_size, psp_mV, delays_ms, drive_pA,
                    duration_ms=200.0, dt_ms=0.1, jitter_frac=0.25, seed=7):
    """Convergent-pool chain: pool -> relay -> target, connectome-scale PSPs.

    A single presynaptic neuron carrying a real connectome weight cannot fire a
    postsynaptic LIF cell at any rate (see ``check_propagation_delay``), so the
    biologically representative latency probe needs convergence.

    Layout (P = ``pool_size``):

        A: neurons [0 .. P-1]     driven pool (current injected)
        B: neurons [P .. 2P-1]    relay interneurons, each receiving all of A
        T: neuron  2P             target, receiving all of B

    "direct" is A -> B (one synapse). "via_interneuron" is A -> B -> T (two
    synapses). Both hops are equally convergent, so the difference between them
    is one synapse's delay plus one round of real membrane integration, not an
    artefact of the second hop being driven harder than the first.

    The pool's drive currents are jittered by ``jitter_frac`` so pool spikes
    arrive spread over a few ms instead of in one perfectly synchronous
    timestep. Without jitter, Brian2's delta synapses deliver every PSP in the
    same timestep and postsynaptic latency collapses to a step function of pool
    size — an artefact of an unrealistically synchronous volley, not a property
    of the model.
    """
    from brian2 import ms, pA

    P = pool_size
    n = 2 * P + 1
    target = 2 * P

    a = np.arange(P)
    b = np.arange(P, 2 * P)

    sources = np.concatenate([np.repeat(a, P), b])
    targets = np.concatenate([np.tile(b, P), np.full(P, target)])
    weights = np.full(len(sources), psp_mV)

    delays = np.atleast_1d(np.asarray(delays_ms, dtype=float))
    if len(delays) == 1:
        delays = np.full(len(sources), delays[0])

    net, G, S, M = _build_chain(n, sources, targets, weights, delays, dt_ms)

    rng = np.random.default_rng(seed)
    drives = drive_pA * (1.0 + jitter_frac * (rng.random(P) - 0.5) * 2)
    G.I = 0 * pA
    G.I[:P] = drives * pA
    net.run(duration_ms * ms)

    t = _first_spike_times(M, n)
    t_pool = np.nanmin(t[:P])
    seg = t[P:2 * P]
    t_relay = np.nanmin(seg) if np.any(~np.isnan(seg)) else np.nan
    return {
        "t_pool": t_pool, "t_relay": t_relay, "t_target": t[target],
        "direct": t_relay - t_pool,
        "via_interneuron": t[target] - t_pool,
    }


def check_propagation_delay(drive_pA=400.0, psp_mV=25.0, pool_size=111,
                            pool_psp_mV=0.405, delay_ms=None, verbose=True):
    """Measure per-hop propagation latency with and without synaptic delay.

    Two probes are run at each delay setting:

    * ``suprathreshold`` — one presynaptic spike is enough to fire the
      postsynaptic cell (PSP > 20 mV). Membrane integration collapses to one
      timestep, so latency ~= delay. This is the probe that isolates the delay
      term and lets the measured increase be checked against the configured
      value rather than against something else.
    * ``convergent_pool`` — ``pool_size`` presynaptic neurons at the *median*
      full-VNC weight (0.405 mV), with ``pool_size`` defaulting to the median
      full-VNC in-degree (111). Latency here contains both the delay and real
      membrane integration, so this is the number comparable with the spec's
      2-4 ms direct / 5-8 ms via one interneuron. Latency is a strong function
      of convergence — at this PSP the target needs ~50 coincident inputs to
      cross threshold at all, so a pool of 60 gives ~12 ms while a pool of 150
      gives ~2.6 ms.

    A single connectome-weight synapse is deliberately not used as the
    "realistic" probe because it cannot fire the postsynaptic cell at all: at
    2x rheobase the presynaptic ISI is 8.93 ms, so a single PSP must exceed
    ``20 mV * (1 - exp(-8.93/10)) = 11.8 mV`` to ever reach threshold, while the
    largest weight anywhere in the connectome is 3.98 mV.

    Parameters
    ----------
    drive_pA : float
        Current injected into the driven neuron(s). Must exceed
        ``RHEOBASE_PA`` (200 pA).
    psp_mV : float
        PSP amplitude for the suprathreshold probe.
    pool_size : int
        Number of converging presynaptic neurons for the pool probe.
    pool_psp_mV : float
        Per-synapse PSP for the pool probe (default: full-VNC median |w|).
    delay_ms : float, optional
        Fixed delay to test. Defaults to the midpoint of
        ``DEFAULT_SYNAPTIC_DELAY``.
    """
    if drive_pA <= RHEOBASE_PA:
        raise ValueError(
            f"drive_pA={drive_pA} is at or below rheobase ({RHEOBASE_PA} pA); "
            "the driven neuron would never fire and the probe would show nothing."
        )

    if delay_ms is None:
        delay_ms = 0.5 * (DEFAULT_SYNAPTIC_DELAY["min_ms"]
                          + DEFAULT_SYNAPTIC_DELAY["max_ms"])

    results = {}

    results["suprathreshold"] = {
        "psp_mV": psp_mV,
        "before": _run_chain_probe(psp_mV, [0.0, 0.0], drive_pA),
        "after": _run_chain_probe(psp_mV, [delay_ms, delay_ms], drive_pA),
    }
    results["convergent_pool"] = {
        "psp_mV": pool_psp_mV,
        "pool_size": pool_size,
        "before": _run_pool_probe(pool_size, pool_psp_mV, [0.0], drive_pA),
        "after": _run_pool_probe(pool_size, pool_psp_mV, [delay_ms], drive_pA),
    }
    for r in results.values():
        r["increase_direct"] = r["after"]["direct"] - r["before"]["direct"]
        r["increase_via_interneuron"] = (r["after"]["via_interneuron"]
                                        - r["before"]["via_interneuron"])

    if verbose:
        print("=" * 74)
        print("CHECK 1 — propagation latency (Brian2 CPU, dt = 0.1 ms)")
        print("=" * 74)
        print(f"  drive: {drive_pA:.0f} pA ({drive_pA / RHEOBASE_PA:.1f}x rheobase "
              f"of {RHEOBASE_PA:.0f} pA)")
        print(f"  configured delay: {delay_ms:.2f} ms per synapse")
        for label, r in results.items():
            extra = (f", pool of {r['pool_size']}" if "pool_size" in r else "")
            print(f"\n  [{label} probe, PSP = {r['psp_mV']:.3f} mV{extra}]")
            print(f"    direct (1 synapse)        "
                  f"before {r['before']['direct']:6.2f} ms  ->  "
                  f"after {r['after']['direct']:6.2f} ms  "
                  f"(+{r['increase_direct']:.2f} ms; expect +{delay_ms:.2f})")
            print(f"    via interneuron (2 syn)   "
                  f"before {r['before']['via_interneuron']:6.2f} ms  ->  "
                  f"after {r['after']['via_interneuron']:6.2f} ms  "
                  f"(+{r['increase_via_interneuron']:.2f} ms; "
                  f"expect +{2 * delay_ms:.2f})")
        rr = results["convergent_pool"]["after"]
        print("\n  vs spec expectation (2-4 ms direct / 5-8 ms via one interneuron):")
        print(f"    measured direct           {rr['direct']:.2f} ms")
        print(f"    measured via interneuron  {rr['via_interneuron']:.2f} ms")

    results["delay_ms"] = delay_ms
    return results


def check_soft_bounding(n_updates=400, burst_ms=40.0, drive_pA=400.0,
                        learning_rate=0.02, w_start=0.6, w_max=None,
                        verbose=True):
    """Drive a real STDP synapse with sustained bursts and watch the bound.

    Reproduces the Child 2 regime: unmodulated two-factor STDP (dopamine fixed
    at +1, nothing opposing growth) with sustained 30-50 ms bursts that pair
    pre and post dozens of times. The same eligibility trace is fed through
    both the additive rule (what the code did before) and the soft-bounded
    rule, so runaway vs. saturation is visible side by side.

    Returns a dict with the two weight trajectories and the ceiling.
    """
    import brian2
    brian2.prefs.codegen.target = "numpy"
    from brian2 import (
        Network, NeuronGroup, SpikeMonitor, Synapses,
        defaultclock, mV, ms, pA, second,
    )

    defaultclock.dt = 0.1 * ms

    if w_max is None:
        w_max = DEFAULT_W_MAX_MV
    syn_sign = np.array([1])                     # one excitatory synapse
    ceiling = float(synapse_w_max(syn_sign, w_max)[0])

    p = DEFAULT_LIF_PARAMS
    eqs = """
    dv/dt = (-(v - V_rest) + R_membrane * I) / tau_m : volt (unless refractory)
    I : amp
    """
    namespace = {
        "tau_m": p["tau_m"], "V_rest": p["V_rest"],
        "R_membrane": p["R_membrane"], "V_th": p["V_th"], "V_reset": p["V_reset"],
    }
    G = NeuronGroup(
        2, eqs, threshold="v > V_th", reset="v = V_reset",
        refractory=p["t_refract"], method="euler", namespace=namespace,
    )
    G.v = p["V_rest"]

    stdp_model = """
    w : volt
    dApre/dt = -Apre / tau_stdp : 1 (event-driven)
    dApost/dt = -Apost / tau_stdp : 1 (event-driven)
    deligibility/dt = -eligibility / tau_e : 1 (clock-driven)
    """
    S = Synapses(
        G, G, model=stdp_model,
        on_pre="v_post += w\nApre += 1.0\neligibility += Apost",
        on_post="Apost += 1.0\neligibility += Apre",
        namespace={"tau_stdp": 20 * ms, "tau_e": 1 * second},
    )
    S.connect(i=[0], j=[1])
    delays_ms = sample_synaptic_delays_ms(1)
    S.delay = delays_ms * ms

    M = SpikeMonitor(G)
    net = Network(G, S, M)

    w_bounded = np.array([float(w_start)])
    w_additive = np.array([float(w_start)])
    traj_bounded = [float(w_bounded[0])]
    traj_additive = [float(w_additive[0])]
    n_crossings = 0

    for _ in range(n_updates):
        # Sustained burst: drive both cells suprathreshold so pre/post pair
        # repeatedly in both directions (the anti-causality fix from the idea
        # doc — later pre spikes follow the post spike).
        S.eligibility = 0.0
        S.Apre = 0.0
        S.Apost = 0.0
        S.w = w_bounded * mV
        G.v = p["V_rest"]
        G.I = drive_pA * pA
        net.run(burst_ms * ms)
        G.I = 0 * pA

        elig = float(np.asarray(S.eligibility[:])[0])
        dw = learning_rate * elig            # unmodulated: no reward factor

        w_bounded = apply_bounded_update(w_bounded, np.array([dw]), syn_sign,
                                        w_max=w_max)
        w_additive = w_additive + dw
        if abs(w_bounded[0]) > ceiling:
            n_crossings += 1

        traj_bounded.append(float(w_bounded[0]))
        traj_additive.append(float(w_additive[0]))

    traj_bounded = np.array(traj_bounded)
    traj_additive = np.array(traj_additive)

    if verbose:
        print("\n" + "=" * 74)
        print("CHECK 2 — soft-bounded STDP saturation (Brian2, real STDP synapse)")
        print("=" * 74)
        print(f"  regime: unmodulated two-factor STDP, {n_updates} x "
              f"{burst_ms:.0f} ms bursts at {drive_pA:.0f} pA, lr = {learning_rate}")
        print(f"  w_max (excitatory ceiling): {ceiling:.4f} mV")
        print(f"  synaptic delay on the pair: {delays_ms[0]:.3f} ms")
        print(f"\n  {'update':>8} {'soft-bounded':>14} {'additive':>12} "
              f"{'|w|/w_max':>11}")
        for k in (0, 1, 5, 10, 25, 50, 100, 200, n_updates):
            if k >= len(traj_bounded):
                continue
            print(f"  {k:>8} {traj_bounded[k]:>14.5f} {traj_additive[k]:>12.5f} "
                  f"{traj_bounded[k] / ceiling:>11.5f}")
        gaps = ceiling - traj_bounded
        print(f"\n  final soft-bounded: {traj_bounded[-1]:.5f} mV "
              f"({100 * traj_bounded[-1] / ceiling:.3f}% of w_max)")
        print(f"  final additive:     {traj_additive[-1]:.5f} mV "
              f"({traj_additive[-1] / ceiling:.2f}x w_max)")
        print(f"  crossings of w_max under soft bound: {n_crossings}")
        print(f"  remaining gap to w_max shrinking monotonically: "
              f"{bool(np.all(np.diff(gaps) <= 1e-12))}")
        # Asymptotic (not linear) approach: successive increments must shrink.
        d = np.diff(traj_bounded)
        pos = d[d > 0]
        if len(pos) > 2:
            print(f"  increments decreasing (geometric approach): "
                  f"{bool(np.all(np.diff(pos) <= 1e-12))}  "
                  f"(first {pos[0]:.6f} -> last {pos[-1]:.3e} mV)")

    return {
        "w_max": ceiling,
        "bounded": traj_bounded,
        "additive": traj_additive,
        "n_crossings": n_crossings,
        "delay_ms": float(delays_ms[0]),
    }


# ==========================================================================
# 2. GPU (PyGeNN) probe
# ==========================================================================

def check_propagation_delay_gpu(drive_pA=400.0, psp_mV=200.0,
                                realistic_psp_mV=60.0, delay_ms=None,
                                duration_ms=200.0, verbose=True):
    """Same chain probe on the PyGeNN GPU backend, via PyGeNNBackend.

    Uses the production ``PyGeNNBackend`` (not a hand-rolled model), so the
    delay path being verified is the one training actually runs.

    The ``psp_mV`` defaults are larger than the Brian2 probe's on purpose. GeNN
    delivers input through ``ExpCurr`` (a 5 ms exponential current) after the
    backend's ``_MV_TO_NA = 0.02`` conversion, not as an instantaneous voltage
    step like Brian2's delta synapses, so the same nominal mV figure produces a
    much smaller peak depolarisation. Only the *increase* in latency is
    comparable between backends; the absolute value at a given nominal weight
    is not.
    """
    from .gpu_backend import PyGeNNBackend
    import scipy.sparse as sp

    if delay_ms is None:
        delay_ms = 0.5 * (DEFAULT_SYNAPTIC_DELAY["min_ms"]
                          + DEFAULT_SYNAPTIC_DELAY["max_ms"])

    def run(psp, delay):
        adj = sp.coo_matrix(
            (np.ones(2), (np.array([0, 1]), np.array([1, 2]))), shape=(3, 3)
        )
        thresholds = np.full(3, -50.0)
        weights = np.array([psp, psp], dtype=np.float32)
        backend = PyGeNNBackend(
            adj, weights, thresholds,
            motor_indices=[2], ascending_indices=[0],
            dt_ms=0.1, coupling_dt_ms=duration_ms,
            delay_params={"min_ms": delay, "max_ms": delay},
        )
        backend.build()
        backend.reset(weights.astype(float), thresholds)

        # step() filters to motor spikes only, so drive the model directly and
        # read the raw recording buffer to get every neuron's spike times.
        currents = np.zeros(3, dtype=np.float32)
        currents[0] = drive_pA * PyGeNNBackend._PA_TO_NA
        backend._pop.extra_global_params["Iext"].view[:] = currents
        backend._pop.extra_global_params["Iext"].push_to_device()
        for _ in range(backend._steps_per_coupling):
            backend._model.step_time()
        backend._model.pull_recording_buffers_from_device()
        times, ids = backend._pop.spike_recording_data[0]

        first = np.full(3, np.nan)
        for nid in range(3):
            ts = times[ids == nid]
            if len(ts):
                first[nid] = ts.min()
        delays_simulated = backend.synapse_delays_ms
        backend.close()
        return {
            "t0": first[0], "t1": first[1], "t2": first[2],
            "direct": first[1] - first[0],
            "via_interneuron": first[2] - first[0],
            "delays_simulated_ms": delays_simulated,
        }

    results = {}
    for label, psp in (("suprathreshold", psp_mV), ("realistic", realistic_psp_mV)):
        before = run(psp, 0.0)
        after = run(psp, delay_ms)
        results[label] = {
            "psp_mV": psp, "before": before, "after": after,
            "increase_direct": after["direct"] - before["direct"],
            "increase_via_interneuron": (after["via_interneuron"]
                                        - before["via_interneuron"]),
        }

    if verbose:
        print("\n" + "=" * 74)
        print("CHECK 3 — same probe on the PyGeNN GPU backend")
        print("=" * 74)
        print(f"  configured delay: {delay_ms:.2f} ms "
              f"(quantised to {results['suprathreshold']['after']['delays_simulated_ms']} ms)")
        for label, r in results.items():
            print(f"\n  [{label} probe, weight = {r['psp_mV']:.1f} mV]")
            print(f"    direct                    "
                  f"before {r['before']['direct']:6.2f} ms  ->  "
                  f"after {r['after']['direct']:6.2f} ms  "
                  f"(+{r['increase_direct']:.2f} ms)")
            print(f"    via interneuron           "
                  f"before {r['before']['via_interneuron']:6.2f} ms  ->  "
                  f"after {r['after']['via_interneuron']:6.2f} ms  "
                  f"(+{r['increase_via_interneuron']:.2f} ms)")

    results["delay_ms"] = delay_ms
    return results


def check_backend_delay_agreement(dt_ms=0.1, verbose=True):
    """Confirm the two backends quantise the same configured delay identically.

    Brian2 rounds ``delay/dt`` half *up* (``spikequeue.h``:
    ``(int)(delay/_dt + 0.5)``). The GPU path must match, otherwise a delay that
    lands on a half-step boundary — like the 1.15 ms midpoint of the default
    range — is simulated as 12 steps on CPU and 11 on GPU, and the backends
    disagree by 0.1 ms per hop with nothing in the output to show it.
    """
    from .network import quantize_delays_to_steps

    probes = np.array([0.80, 0.85, 0.90, 1.00, 1.05, 1.10, 1.15,
                       1.20, 1.25, 1.45, 1.50])
    gpu_steps = quantize_delays_to_steps(probes, dt_ms)

    cpu_steps = []
    for d in probes:
        base = _run_chain_probe(25.0, [0.0, 0.0], 400.0, duration_ms=40.0)["direct"]
        measured = _run_chain_probe(25.0, [d, d], 400.0,
                                    duration_ms=40.0)["direct"]
        cpu_steps.append(int(round((measured - base) / dt_ms)))
    cpu_steps = np.array(cpu_steps)

    agree = bool(np.all(cpu_steps == gpu_steps))
    if verbose:
        print("\n" + "=" * 74)
        print("CHECK 4 — CPU/GPU delay quantisation agreement")
        print("=" * 74)
        print(f"  {'delay (ms)':>11} {'Brian2 steps':>14} {'GPU steps':>11}  ok")
        for d, c, g in zip(probes, cpu_steps, gpu_steps):
            print(f"  {d:>11.2f} {c:>14d} {g:>11d}  {'y' if c == g else 'MISMATCH'}")
        print(f"\n  all agree: {agree}")

    return {"delays_ms": probes, "cpu_steps": cpu_steps,
            "gpu_steps": gpu_steps, "agree": agree}


def run_all_checks(skip_gpu=False):
    """Run every check and print a summary. Entry point for the CLI."""
    out = {}
    out["propagation"] = check_propagation_delay()
    out["soft_bounding"] = check_soft_bounding()
    out["backend_agreement"] = check_backend_delay_agreement()
    if not skip_gpu:
        try:
            out["propagation_gpu"] = check_propagation_delay_gpu()
        except Exception as exc:          # noqa: BLE001 — diagnostic path
            print(f"\n[check] GPU probe unavailable: {type(exc).__name__}: {exc}")
    return out
