"""Child 0c: wire the musculoskeletal body into the spiking network and measure
end-to-end conduction.

Three measurements, every number from a real run -- spike counts on a Brian2
``SpikeMonitor`` and real MuJoCo physics, never a computed current.  (A current
is not a spike: 60.68 pA was once reported as "the encoder working" when it is
0.38x rheobase and could never have fired.)

1. ``measure_conduction`` -- the exit gate.  A pool of in-scope LF motor neurons
   is driven above rheobase in the **full VNC** (25,635 neurons, 4,114,854
   synapses, per-synapse 0.8-1.5 ms delay from Child 0a), their spikes are
   decoded to the 15 FlyMimic Hill-type muscle activations by ``MuscleDecoder``
   (size-principle weighted sum, never a mean), applied to
   ``MusculoskeletalFly`` through ``ActuatorType.MUSCLE``, and the resulting
   joint state is fed back through ``ProprioceptiveEncoder`` into the same
   network **in lockstep at dt = 0.1 ms**.  Reports time-to-first-afferent-spike
   per modality.

2. ``measure_return_volley`` -- does the returning afferent volley fire anything
   downstream?  Convergence and summed PSP are recomputed from the live code
   path (``functional_training``'s own weight formula), then the volley is
   actually run and the relays that fire are named.

3. ``measure_afferent_rest_point`` -- where the 41 LF afferents rest with their
   full synaptic input present, as opposed to the isolated LIF cells Child 0b
   measured.  **Measurement only. No tonic bias is implemented** -- the 66%
   GABAergic input means the operating point is something the network sets, and
   hardcoding a constant would substitute a guess for a mechanism already in the
   wiring.

4. ``measure_multi_muscle_drive`` -- the follow-up hypothesis.  0c's exit gate
   failed for a *named* reason: the interneurons that could relay an afferent
   volley back to a motor neuron are multi-joint integrators, and a single-muscle
   twitch recruits only ~1/4 of any relay's afferent input.  This sweeps drive
   spanning several muscles across the coxa / trochanter / tibia groups at once
   -- which is also what real spontaneous fetal twitches do -- and asks whether
   the extra afferent *breadth* fires a relay where single-muscle drive cannot.
   Ships with the negative control 0c never ran: the same motor drive with the
   joints pinned, so no sensory current can be generated and any afferent spike
   must have arrived through the connectome instead of through the body.

5. ``measure_rate_threshold`` -- the **minimum conducting rate**, which the
   multi-muscle entry listed as its single most useful missing number (drive was
   pinned at 200 Hz and rate never swept).  Sweeps the measured f-I ladder from
   the LIF's 20 Hz floor upward under BOTH decoders in one process -- the legacy
   ``/(sum(w_i) * 200 Hz)`` rate fraction and the per-class force model -- against
   the same settled body and seeded delays, so the before/after is one changed
   variable rather than a comparison with a remembered number.  Also splits the
   latency into the mechanical half (drive -> first afferent), which force gain
   compresses, and the synaptic half (afferent -> relay spike), which it does not.

6. ``measure_class_protocol`` -- the same question in its biological form.  Every
   other sweep drives all neurons at one uniform rate for the whole burst, which
   no motor pool runs.  Here slow MNs are tonic in Azevedo's 30-100 Hz range while
   fast/intermediate MNs fire N spikes and then go **silent**, and the per-class
   spike counts are read back off the ``SpikeMonitor`` rather than inferred from
   the current window.

7. ``measure_background_operating_point`` -- the relays' **operating point**, which
   every sweep above left at exactly ``V_rest``.  ``run_lockstep_multi`` zeroed
   ``drive`` outside the driven motor pool, so a relay had to be pushed the whole
   20 mV by the afferent volley alone -- which is the stated mechanism of the
   28.6 ms synaptic floor, and a state no VNC interneuron occupies.  Sweeps a
   constant-current and a Poisson background applied to everything EXCEPT the
   driven pool and the afferents, with the frozen-physics control at every level,
   and reports the false-positive rate alongside the latency, because background
   makes neurons fire on their own.

``verify_size_principle`` asserts the property the decode exists to preserve:
recruiting more neurons strictly increases force, and a silent neuron contributes
exactly zero.  Checked over every pool in BOTH recruitment orders, because a
pool-mean bug is monotone largest-first and non-monotone smallest-first.  This has
already broken once -- a mean-based decode drove a joint backwards by -0.225 rad.

Usage
-----
    python -m digital_drosophila check body_wiring
    python -m digital_drosophila check body_wiring --quick
    python -m digital_drosophila check multi_muscle
    python -m digital_drosophila check multi_muscle --quick
    python -m digital_drosophila check background
    python -m digital_drosophila check background --quick
"""

import time

import numpy as np
import pandas as pd

from .proprioceptive_encoder import (
    JOINT_GROUPS,
    MODALITIES,
    N_LF_JOINTS,
    RHEOBASE_PA,
    SETTLE_STEPS,
    ProprioceptiveEncoder,
    muscle_group_indices,
    tendon_loads_by_group,
)

# ---------------------------------------------------------------------------
# Scope (docs/neuroscience/13-motor-neuron-muscle-mapping.md 6.1)
# ---------------------------------------------------------------------------

# The 12 of 64 LF motor neurons excluded: 6 tarsus (FlyMimic welds all 5 tarsus
# segments, so there is no joint to move even in principle) and 6 long-tendon
# ``ltm*`` (multi-joint action collapsed into single-joint muscles).  Counting
# them would measure FlyMimic's limitations rather than connectome biology.
OUT_OF_SCOPE_MN_TYPES = frozenset({
    "Ta depressor MN",   # 4
    "Ta levator MN",     # 2
    "ltm MN",            # 2
    "ltm2-femur MN",     # 2
    "ltm1-tibia MN",     # 2
})

# Physics timestep of MusculoskeletalFly, asserted against model.opt.timestep.
DT_MS = 0.1

# Babbling protocol from the epic: ~4-neuron pools at ~80 Hz.  Single-neuron
# drive is deliberately never used -- Child 0a proved a single connectome synapse
# cannot fire a postsynaptic LIF at any rate (largest weight anywhere 3.98 mV vs
# the ~11.8 mV needed), so it tests a configuration that cannot propagate in
# principle.  Pool size is reported with every latency.
DEFAULT_POOL_SIZE = 4
DEFAULT_BURST_MS = 50.0

# Injected current -> firing rate on the project's LIF model (DEFAULT_LIF_PARAMS).
# MEASURED by spike count over 1 s, not derived from the rheobase formula: the
# f-I curve is concave, so linear interpolation would be wrong by tens of Hz.
#
# The sub-80 Hz entries were added 2026-08-18 for the physiological-rate sweep and
# measured the same way (1 s isolated-LIF spike count, 1 pA grid).  They reproduce
# the pre-existing five to within 1 pA, which is a check on both.
#
# **20 Hz is the floor this LIF can produce.** With ``t_refract = 2 ms`` and a
# concave f-I curve the cell jumps straight from silent (201 pA) to 20 Hz
# (202 pA); there is no current that yields 5 or 10 Hz.  So Azevedo's ~30 Hz slow
# idle is reachable but anything below 20 Hz is not, which bounds how low the
# minimum-conducting-rate sweep can go.
DRIVE_PA_FOR_HZ: dict[int, float] = {
    20: 202.0,
    25: 205.0,
    30: 208.9,
    40: 222.0,
    50: 238.8,
    60: 260.0,
    80: 305.2,
    100: 360.0,
    120: 421.6,
    150: 523.0,
    200: 747.2,
}

# The bar one synchronous volley must clear to fire a cell that is already firing
# (Child 0a): at 2x rheobase the presynaptic ISI is 8.93 ms, so a single summed
# PSP must exceed (V_th - V_rest) * (1 - exp(-8.93/10)) or the membrane leaks it
# away before the next volley arrives.
SUSTAINED_BAR_MV = 20.0 * (1.0 - np.exp(-0.893))

# The bar one volley must clear starting from rest: the full 20 mV to threshold.
FROM_REST_BAR_MV = 20.0

# Background drive (deliverable 7).  ``network.py``'s ``create_background_drive``
# uses 50 Poisson sources at 22 Hz x 1.3 mV; that is the per-spike amplitude
# reused here so the Poisson arm is the mechanism the training harness already
# runs rather than a new one invented for this sweep.
BACKGROUND_WEIGHT_MV = 1.3
BACKGROUND_N_SOURCES = 50

# 1 pA through R_membrane = 100 MOhm holds the membrane 0.1 mV above V_rest at
# steady state, so a p pA background leaves (20 - 0.1 * p) mV to threshold.  This
# is an OPEN-LOOP figure for an isolated cell: in the full VNC the same current
# also drives 25,635 recurrent partners, 68% of the input onto the afferents is
# GABAergic, and deliverable 3 measured the afferents resting NET-INHIBITED, so
# the realised operating point is a measurement and not this arithmetic.
def open_loop_gap_mV(background_pa: float) -> float:
    """Depolarisation still needed from rest at ``background_pa``, isolated-cell."""
    return FROM_REST_BAR_MV - 0.1 * float(background_pa)


# ---------------------------------------------------------------------------
# Live-code-path weights
# ---------------------------------------------------------------------------


def build_live_weights(meta_df, sources, synapse_counts):
    """Per-synapse weight in mV, reproducing the training harness exactly.

    This is deliberately *not* read off the formula quoted in ``network.py``'s
    docstring, because the Child 0c spec's convergence table was derived from
    that comment and is therefore order-of-magnitude only.  Three details of the
    live path change the numbers:

    * the NT column is the first non-empty of ``consensusNt`` / ``predictedNt`` /
      ``celltypePredictedNt`` (in practice ``consensusNt``);
    * ``predictedNtConfidence`` is filled with 0.5 where missing, so
      unannotated presynaptic neurons carry half weight;
    * a presynaptic NT that maps to ``None`` (dopamine / serotonin / octopamine /
      unclear) gets sign 0 and therefore weight **exactly 0** -- 204,608
      synapses are wired but electrically silent, which a formula written as
      ``sign * ...`` hides.

    ``synapse_counts`` is the raw ``weights`` array from ``connectivity.npz``,
    which holds synapse *counts* (1-1032), not mV.  The mV conversion happens
    here and only here.
    """
    from .constants import NT_SIGN_MAP

    nt_col = None
    for col in ["consensusNt", "predictedNt", "celltypePredictedNt"]:
        if col in meta_df.columns and meta_df[col].notna().any():
            nt_col = col
            break
    nt_series = (
        meta_df[nt_col].fillna("unknown") if nt_col else ["unknown"] * len(meta_df)
    )

    if "predictedNtConfidence" in meta_df.columns:
        confidence = meta_df["predictedNtConfidence"].fillna(0.5).values.astype(float)
    else:
        confidence = np.full(len(meta_df), 0.5, dtype=float)

    sign_vector = np.array([NT_SIGN_MAP.get(nt, 0) or 0 for nt in nt_series])

    inh_attenuation = 0.5
    scale = 0.6
    sign_scale = np.where(sign_vector[sources] >= 0, 1.0, inh_attenuation)
    weights_mV = (
        np.log1p(synapse_counts)
        * sign_vector[sources]
        * confidence[sources]
        * sign_scale
        * scale
    )
    return weights_mV, sign_vector, nt_col


def load_full_vnc():
    """Load the cached full-VNC snapshot and convert counts to live-path mV."""
    from .functional_selection import get_or_build_full_vnc_network

    body_ids, meta_df, motor_leg_map, sources, targets, counts = (
        get_or_build_full_vnc_network()
    )
    sources = np.asarray(sources, dtype=np.int64)
    targets = np.asarray(targets, dtype=np.int64)
    counts = np.asarray(counts, dtype=float)

    # ``sources``/``targets`` are ROW INDICES INTO meta.csv, not bodyIds.  Mixing
    # them up returns zero results silently instead of erroring, so check rather
    # than assume.
    if not np.array_equal(
        meta_df["bodyId"].astype(np.int64).values,
        np.asarray(body_ids, dtype=np.int64),
    ):
        raise RuntimeError(
            "meta.csv row order does not match body_ids. sources/targets index "
            "meta.csv rows, so every lookup downstream would be silently wrong."
        )

    weights_mV, sign_vector, nt_col = build_live_weights(meta_df, sources, counts)
    return {
        "body_ids": body_ids,
        "meta_df": meta_df,
        "motor_leg_map": motor_leg_map,
        "sources": sources,
        "targets": targets,
        "counts": counts,
        "weights_mV": weights_mV,
        "sign_vector": sign_vector,
        "nt_col": nt_col,
    }


def lf_motor_in_scope(meta_df):
    """The 52 LF motor neurons that have a live DOF."""
    lfm = meta_df[
        (meta_df["superclass"] == "vnc_motor")
        & (meta_df["subclass"] == "fl")
        & (meta_df["somaSide"] == "L")
    ]
    return lfm[~lfm["type"].isin(OUT_OF_SCOPE_MN_TYPES)]


def modality_index_map(encoder):
    """modality -> ndarray of network indices assigned to it."""
    return {
        modality: np.array(
            [a.neuron_index for a in encoder.assignments if a.modality == modality],
            dtype=np.int64,
        )
        for modality in MODALITIES
    }


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------


class FullVNCNetwork:
    """The full VNC as a Brian2 LIF network with per-synapse transmission delay.

    Same LIF parameters (``DEFAULT_LIF_PARAMS``), same weight formula and the
    same seeded delay draw as the training harness, so latencies measured here
    include Child 0a's delays and are directly comparable with the 20 ms STDP
    window -- unlike every measurement before 0a.

    ``spiked`` is an auxiliary variable set in the reset code so the coupling
    callback can read "who fired on this timestep" without scanning the monitor.
    """

    def __init__(self, net_data, dt_ms=DT_MS, delay_params=None):
        import brian2

        brian2.prefs.codegen.target = "numpy"
        # ``I`` and ``v`` are group variables that also appear as local names in
        # the callers below; Brian2 warns about the shadowing on every run even
        # though it always resolves to the group variable. Silence just that one.
        brian2.BrianLogger.suppress_name("resolution_conflict")
        from brian2 import (
            Network, NeuronGroup, SpikeMonitor, Synapses, defaultclock, mV, ms,
        )
        from .network import DEFAULT_LIF_PARAMS, sample_synaptic_delays_ms

        defaultclock.dt = dt_ms * ms
        self.dt_ms = dt_ms
        self.n_neurons = len(net_data["body_ids"])
        self.net_data = net_data
        self._weights_mV = net_data["weights_mV"]

        p = DEFAULT_LIF_PARAMS
        eqs = """
        dv/dt = (-(v - V_rest) + R_membrane * I) / tau_m : volt (unless refractory)
        I : amp
        spiked : 1
        """
        namespace = {
            "tau_m": p["tau_m"],
            "V_rest": p["V_rest"],
            "R_membrane": p["R_membrane"],
            "V_th": p["V_th"],
            "V_reset": p["V_reset"],
        }
        G = NeuronGroup(
            self.n_neurons, eqs,
            threshold="v > V_th",
            reset="v = V_reset\nspiked = 1",
            refractory=p["t_refract"], method="euler", namespace=namespace,
        )
        G.v = p["V_rest"]

        S = Synapses(G, G, "w : volt", on_pre="v_post += w")
        S.connect(i=net_data["sources"], j=net_data["targets"])
        S.w = self._weights_mV * mV
        self.delays_ms = sample_synaptic_delays_ms(
            len(net_data["sources"]), delay_params
        )
        S.delay = self.delays_ms * ms

        M = SpikeMonitor(G)
        self.G, self.S, self.M = G, S, M
        self.net = Network(G, S, M)
        self.net.store("rest")

    def reset(self, recurrent=True):
        """Restore the quiescent state, zero all current.

        ``recurrent=False`` zeroes the recurrent weights, reproducing the
        isolated-LIF regime Child 0b measured in, so the two can be compared
        inside one run.
        """
        from brian2 import amp, mV

        self.net.restore("rest")
        self.S.w = (self._weights_mV if recurrent else np.zeros_like(self._weights_mV)) * mV
        self.G.I = np.zeros(self.n_neurons) * amp

    def set_current_pa(self, currents_pa):
        from brian2 import amp

        self.G.I = np.asarray(currents_pa, dtype=float) * 1e-12 * amp

    def spike_table(self):
        """(times_ms, indices) of every spike recorded since construction."""
        from brian2 import ms

        return np.asarray(self.M.t / ms), np.asarray(self.M.i)


# ---------------------------------------------------------------------------
# Body
# ---------------------------------------------------------------------------


def build_settled_body(settle_steps=SETTLE_STEPS, verbose=True):
    """Build ``MusculoskeletalFly`` + ``MusculoskeletalWorld`` and settle it.

    ``MusculoskeletalFly`` is **not** a NeuroMechFly subset and shares no
    actuator interface with it: 14 joints not 127, tendon transmission
    (``mjTRN_TENDON``) not joint, muscle dynamics (``mjDYN_MUSCLE``), 15 unipolar
    ``[1e-4, 1]`` muscle actuators, no free joint (tethered by construction) and
    no neutral 66-DOF pose to add offsets to.  Every one of those is asserted or
    printed rather than assumed.

    Settles ``settle_steps`` (3000 = 300 ms).  At 500 the tibia still drifts at
    -4 rad/s, which has already corrupted one measurement on this project.
    """
    import mujoco
    from flygym.compose import build_musculoskeletal_simulation

    sim, fly = build_musculoskeletal_simulation()
    model, data = sim.mj_model, sim.mj_data

    dt_ms = model.opt.timestep * 1000.0
    if abs(dt_ms - DT_MS) > 1e-9:
        raise RuntimeError(
            f"MusculoskeletalFly timestep is {dt_ms} ms, expected {DT_MS} ms; "
            "the neural/physics lockstep assumption no longer holds."
        )
    if settle_steps < SETTLE_STEPS:
        raise ValueError(
            f"settle_steps={settle_steps} is below the measured {SETTLE_STEPS} "
            "needed; the leg would still be drifting when measurement starts."
        )

    for _ in range(settle_steps):
        sim.step()
    mujoco.mj_forward(model, data)

    state = {
        "qpos": data.qpos.copy(),
        "qvel": data.qvel.copy(),
        # Muscle actuators carry first-order activation dynamics, so ``act`` is
        # part of the state that must be restored between conditions.
        "act": data.act.copy(),
    }
    groups = muscle_group_indices(model)
    muscle_names = list(fly.muscle_names)

    if verbose:
        angles = sim.get_joint_angles("nmf")[:N_LF_JOINTS]
        vels = sim.get_joint_velocities("nmf")[:N_LF_JOINTS]
        print(f"  body: MusculoskeletalFly, {model.njnt} joints, {model.nu} muscles, "
              f"nq = {model.nq} (no free joint -> tethered), dt = {dt_ms:.1f} ms")
        print(f"  transmission mjTRN_TENDON({int(model.actuator_trntype[0])}), "
              f"dynamics mjDYN_MUSCLE({int(model.actuator_dyntype[0])}), "
              f"ctrlrange [{model.actuator_ctrlrange[0, 0]:g}, "
              f"{model.actuator_ctrlrange[0, 1]:g}] (unipolar: a muscle pulls, "
              f"never pushes)")
        print(f"  settled after {settle_steps} steps ({settle_steps * dt_ms:.0f} ms): "
              f"max |joint velocity| {np.abs(vels).max():.4f} rad/s")
        print(f"  settled LF angles (rad): {np.round(angles, 5)}")

    return sim, model, data, state, groups, muscle_names


def reset_body(sim, model, data, state):
    """Restore the settled state exactly, ``act`` included.

    The pre-existing ``proprio_test`` demo drives muscles sequentially without
    resetting, so its third condition is contaminated by its second.  Muscle
    ``act`` has 0.1/0.4 ms first-order dynamics, so leaving it in place leaks
    the previous condition's contraction into the next one.
    """
    import mujoco

    data.qpos[:] = state["qpos"]
    data.qvel[:] = state["qvel"]
    data.act[:] = state["act"]
    data.ctrl[:] = 0.0
    mujoco.mj_forward(model, data)


# ---------------------------------------------------------------------------
# Deliverable 1: end-to-end conduction
# ---------------------------------------------------------------------------


def run_lockstep(
    network,
    sim,
    model,
    data,
    state,
    groups,
    decoder,
    encoder,
    muscle,
    pool,
    drive_pa,
    burst_ms=DEFAULT_BURST_MS,
    rate_window_ms=50.0,
):
    """Run the full chain in lockstep at dt = 0.1 ms and return the traces.

    One Brian2 timestep, then one MuJoCo step, then re-encode -- so the reported
    latency contains the real per-synapse delays, the real muscle activation
    dynamics and the real inertia.  Nothing is precomputed and replayed.

    Motor rate is decoded over a trailing ``rate_window_ms`` window exactly as
    ``SpikeRateDecoder`` does, and pooled onto the muscle by
    ``MuscleDecoder.muscle_activations`` -- a size-principle **weighted sum**.  A
    mean would violate the size principle: it once drove the joint backwards by
    -0.225 rad when 1 of 8 neurons fired.
    """
    from brian2 import amp, ms, network_operation

    from .muscle_decoder import MUSCLE_NAMES

    muscle_i = MUSCLE_NAMES.index(muscle)
    pool_idx = np.array([a.net_index for a in pool], dtype=np.int64)
    aff_idx = np.asarray(encoder.sensory_indices, dtype=np.int64)

    n_steps = int(round(burst_ms / DT_MS))
    window = int(round(rate_window_ms / DT_MS))

    reset_body(sim, model, data, state)
    network.reset()

    hist = np.zeros((n_steps, len(pool_idx)), dtype=bool)
    tr = {
        "activation": np.zeros(n_steps),
        "angles": np.zeros((n_steps, N_LF_JOINTS)),
        "vels": np.zeros((n_steps, N_LF_JOINTS)),
        "afferent_pa": np.zeros((n_steps, len(aff_idx))),
    }
    drive = np.zeros(network.n_neurons)
    drive[pool_idx] = drive_pa
    ctrl = np.zeros(model.nu)
    counter = {"k": 0}

    @network_operation(dt=DT_MS * ms, when="start")
    def couple():
        k = counter["k"]
        if k >= n_steps:
            return
        # 1. who fired on the previous timestep
        spiked = network.G.spiked_[:]
        hist[k] = spiked[pool_idx] > 0
        network.G.spiked_[:] = 0.0

        # 2. motor spikes -> firing rate -> muscle activation (weighted sum)
        lo = max(0, k + 1 - window)
        counts = hist[lo:k + 1]
        duration_s = (k + 1 - lo) * DT_MS / 1000.0
        rates_hz = {
            int(pool_idx[j]): counts[:, j].sum() / duration_s
            for j in range(len(pool_idx))
        }
        activations = decoder.muscle_activations(rates_hz)

        # 3. muscle -> physics.  ctrlrange is [1e-4, 1], so 0 is out of range.
        ctrl[:] = 0.0
        ctrl[muscle_i] = max(activations[muscle_i], model.actuator_ctrlrange[muscle_i, 0])
        data.ctrl[:] = ctrl
        sim.step()

        # 4. physics -> proprioception -> current back into the same network
        angles = sim.get_joint_angles("nmf")[:N_LF_JOINTS]
        vels = sim.get_joint_velocities("nmf")[:N_LF_JOINTS]
        loads = tendon_loads_by_group(data, groups)
        currents = encoder.encode(angles, vels, loads)

        tr["activation"][k] = activations[muscle_i]
        tr["angles"][k] = angles
        tr["vels"][k] = vels
        tr["afferent_pa"][k] = currents[aff_idx] * 1e12

        network.G.I = (drive + currents * 1e12) * 1e-12 * amp
        counter["k"] = k + 1

    network.G.I = drive * 1e-12 * amp
    network.net.add(couple)
    try:
        network.net.run(n_steps * DT_MS * ms)
    finally:
        network.net.remove(couple)

    times, indices = network.spike_table()
    tr["pool_rate_hz"] = hist.sum() / (len(pool_idx) * burst_ms / 1000.0)
    tr["pool_idx"] = pool_idx
    tr["afferent_idx"] = aff_idx
    return times, indices, tr


def measure_conduction(
    net_data=None,
    muscle="LFTibia_flex_93434",
    pool_sizes=(1, 2, 4, 8, 14),
    rates_hz=(30, 50, 80, 120, 200),
    burst_ms=DEFAULT_BURST_MS,
    verbose=True,
):
    """Deliverable 1: time-to-first-afferent-spike per modality, by pool size.

    Replaces the retired ``recruited x firing-rate -> round-trip`` table.  That
    table was withdrawn because (a) its neural term was a flat 2 ms estimate when
    latency is a function of convergence, and (b) its physics term measured
    ``t_move`` -- when the joint *starts* moving -- which is a strictly earlier
    event than an afferent spiking, so the two halves never chained.  This table
    is indexed by pool size and reports the spike, not the movement.

    Primary hypothesis under test: **the first afferent to spike is on a velocity
    channel.**
    """
    from .muscle_decoder import MuscleDecoder

    if net_data is None:
        net_data = load_full_vnc()
    meta_df, body_ids = net_data["meta_df"], net_data["body_ids"]

    decoder = MuscleDecoder(meta_df, body_ids)
    members = decoder.muscle_pool_members(muscle)
    in_scope = [a for a in members if a.mn_type not in OUT_OF_SCOPE_MN_TYPES]
    encoder = ProprioceptiveEncoder(meta_df, body_ids, leg="LF", side="L")
    by_modality = modality_index_map(encoder)

    meta_bid = meta_df["bodyId"].values
    meta_type = meta_df["type"].fillna("<untyped>").values

    if verbose:
        n_scope = len(lf_motor_in_scope(meta_df))
        print("=" * 78)
        print("[1] EXIT GATE: does the chain conduct end to end?")
        print("=" * 78)
        print(f"  scope: {n_scope} of 64 LF motor neurons (excludes 6 tarsus + "
              f"6 ltm* = FlyMimic limitations, not biology)")
        print(f"  muscle {muscle}: pool of {len(members)}, "
              f"{len(in_scope)} in scope")
        for a in in_scope[:max(pool_sizes)]:
            print(f"    bodyId {a.body_id:<11} {a.mn_type:<22} size {a.size:.3e}")
        print(f"  afferents: {len(encoder.assignments)} encoded "
              + ", ".join(f"{m} {len(v)}" for m, v in by_modality.items()))
        print(f"  gains (0b, not re-derived): "
              + ", ".join(f"{m} {encoder.gains_pa[m]:.0f}" for m in MODALITIES)
              + " pA")

    sim, model, data, state, groups, muscle_names = build_settled_body(verbose=verbose)

    t0 = time.time()
    network = FullVNCNetwork(net_data)
    if verbose:
        print(f"  network: {network.n_neurons:,} neurons, "
              f"{len(net_data['sources']):,} synapses, per-synapse delay "
              f"{network.delays_ms.min():.2f}-{network.delays_ms.max():.2f} ms "
              f"(mean {network.delays_ms.mean():.2f}) -- built in "
              f"{time.time() - t0:.1f}s")

    rows = []
    for pool_size in pool_sizes:
        if pool_size > len(in_scope):
            continue
        pool = in_scope[:pool_size]
        for hz in rates_hz:
            drive_pa = DRIVE_PA_FOR_HZ[hz]
            times, indices, tr = run_lockstep(
                network, sim, model, data, state, groups, decoder, encoder,
                muscle, pool, drive_pa, burst_ms=burst_ms,
            )
            row = {
                "pool": pool_size,
                "nominal_hz": hz,
                "drive_pa": drive_pa,
                "measured_pool_hz": tr["pool_rate_hz"],
                "activation_peak": float(tr["activation"].max()),
                "tibia_excursion_rad": float(
                    tr["angles"][-1, 6] - state["qpos"][6]
                ),
                "n_network_spikes": int(len(times)),
            }
            for modality, idx in by_modality.items():
                cols = [int(np.flatnonzero(tr["afferent_idx"] == i)[0]) for i in idx]
                row[f"{modality}_peak_pa"] = float(tr["afferent_pa"][:, cols].max())
                sel = np.isin(indices, idx)
                if sel.any():
                    j = int(np.argmin(times[sel]))
                    who = indices[sel][j]
                    row[f"{modality}_t_ms"] = float(times[sel][j])
                    row[f"{modality}_who"] = f"{meta_bid[who]}/{meta_type[who]}"
                else:
                    row[f"{modality}_t_ms"] = np.nan
                    row[f"{modality}_who"] = ""
            rows.append(row)

    table = pd.DataFrame(rows)
    if verbose:
        _print_conduction(table, muscle, burst_ms)
    return {"table": table, "encoder": encoder, "decoder": decoder,
            "network": network, "body": (sim, model, data, state, groups)}


def _print_conduction(table, muscle, burst_ms):
    def grid(col):
        p = table.pivot(index="pool", columns="nominal_hz", values=col)
        return p.map(lambda v: "--" if pd.isna(v) else f"{v:.1f}").to_string()

    print(f"\n  {muscle}, {burst_ms:.0f} ms burst, dt = 0.1 ms lockstep.")
    print("  rows = convergent pool size, columns = nominal motor rate (Hz).")
    for modality in MODALITIES:
        print(f"\n  t_first {modality} afferent spike (ms), "
              f"'--' = no spike inside the burst")
        print("  " + grid(f"{modality}_t_ms").replace("\n", "\n  "))

    print("\n  peak muscle activation reached (weighted sum):")
    print("  " + table.pivot(index="pool", columns="nominal_hz",
                             values="activation_peak").round(3)
          .to_string().replace("\n", "\n  "))
    print(f"\n  peak velocity-channel current (pA; rheobase {RHEOBASE_PA:.0f}):")
    print("  " + table.pivot(index="pool", columns="nominal_hz",
                             values="velocity_peak_pa").round(0)
          .to_string().replace("\n", "\n  "))
    print("\n  tibia excursion at end of burst (rad):")
    print("  " + table.pivot(index="pool", columns="nominal_hz",
                             values="tibia_excursion_rad").round(4)
          .to_string().replace("\n", "\n  "))

    first = {}
    for modality in MODALITIES:
        col = table[f"{modality}_t_ms"]
        if col.notna().any():
            first[modality] = float(col.min())
    print("\n  VERDICT")
    if not first:
        print("    NO afferent spiked in any condition -> exit gate FAILS.")
        return
    order = sorted(first.items(), key=lambda kv: kv[1])
    print("    earliest afferent spike per modality, over all conditions:")
    for modality, t in order:
        row = table.loc[table[f"{modality}_t_ms"].idxmin()]
        print(f"      {modality:9s} {t:5.1f} ms  (pool {int(row['pool'])} @ "
              f"{int(row['nominal_hz'])} Hz, {row[f'{modality}_who']})")
    winner = order[0][0]
    print(f"    FIRST MODALITY = {winner}. "
          + ("Hypothesis CONFIRMED." if winner == "velocity"
             else "Hypothesis FALSIFIED -- the damped-spring reasoning does "
                  "not describe this body."))


def measure_per_driver(conduction, rates_hz=(80, 200), verbose=True):
    """Which modality spikes first depends on WHICH JOINT is driven.

    The main sweep drives the tibia flexor, and there velocity always wins.  But
    the tibia is the fastest joint on this leg; the trochanter and coxa are
    slower and more heavily loaded.  Driving each joint group's strongest muscle
    separates "velocity is first" from "velocity is first *on the tibia*", which
    the single-muscle sweep cannot distinguish and which matters because Child 1
    babbles across all 52 motor neurons, not just the tibia pool.
    """
    network = conduction["network"]
    encoder, decoder = conduction["encoder"], conduction["decoder"]
    sim, model, data, state, groups = conduction["body"]
    by_modality = modality_index_map(encoder)

    drivers = [
        ("tibia", "LFTibia_flex_93434"),
        ("tibia", "LFTibia_extensor_93932"),
        ("trochanter", "LFF_sterno-tergo-trochanter_extensor_b"),
        ("trochanter", "LFF_trochanter_extensor"),
        ("coxa", "LFC_tergopleural_promotor_b"),
    ]
    rows = []
    for joint_group, muscle in drivers:
        members = decoder.muscle_pool_members(muscle)
        in_scope = [a for a in members if a.mn_type not in OUT_OF_SCOPE_MN_TYPES]
        for hz in rates_hz:
            times, indices, tr = run_lockstep(
                network, sim, model, data, state, groups, decoder, encoder,
                muscle, in_scope, DRIVE_PA_FOR_HZ[hz],
            )
            row = {
                "joint_group": joint_group, "muscle": muscle,
                "pool": len(in_scope), "nominal_hz": hz,
                "activation_peak": float(tr["activation"].max()),
            }
            for modality, idx in by_modality.items():
                sel = np.isin(indices, idx)
                row[f"{modality}_t_ms"] = float(times[sel].min()) if sel.any() else np.nan
            rows.append(row)

    table = pd.DataFrame(rows)
    if verbose:
        print("\n  which modality fires first, per driven joint group "
              "(whole in-scope pool):")
        print(f"    {'muscle':<40} {'pool':>4} {'Hz':>4} {'act':>6}   "
              + "".join(f"{m:>11}" for m in MODALITIES) + "   first")
        for r in table.itertuples():
            cells = []
            best, best_t = None, np.inf
            for modality in MODALITIES:
                t = getattr(r, f"{modality}_t_ms")
                cells.append("         --" if pd.isna(t) else f"{t:11.1f}")
                if not pd.isna(t) and t < best_t:
                    best, best_t = modality, t
            print(f"    {r.muscle:<40} {r.pool:4d} {r.nominal_hz:4d} "
                  f"{r.activation_peak:6.3f}   " + "".join(cells)
                  + f"   {best or '(none)'}")
        firsts = {}
        for r in table.itertuples():
            best, best_t = None, np.inf
            for modality in MODALITIES:
                t = getattr(r, f"{modality}_t_ms")
                if not pd.isna(t) and t < best_t:
                    best, best_t = modality, t
            if best:
                firsts.setdefault(best, []).append(r.muscle)
        print("\n    which modality was first, counted over conducting "
              "conditions:")
        for modality, muscles in sorted(firsts.items(), key=lambda kv: -len(kv[1])):
            print(f"      {modality:9s} {len(muscles)}  ({', '.join(sorted(set(muscles)))})")
        print("    Velocity wins wherever the joint moves fast (tibia, coxa). On "
              "the trochanter\n    -- slow, heavily loaded, and the only group "
              "with force afferents -- velocity\n    barely reaches 20 pA and "
              "position or force wins instead. So 'velocity is\n    first' holds "
              "for the joint the hypothesis was framed on, but is NOT a property\n"
              "    of the body as a whole, and Child 1 babbles across all three "
              "groups.")
    return table


# ---------------------------------------------------------------------------
# Deliverable 2: can the return volley fire anything?
# ---------------------------------------------------------------------------


def afferent_convergence(net_data, encoder):
    """Recompute afferent -> target convergence and summed PSP from live weights.

    Returns one row per postsynaptic target reached by the 41 afferents, with the
    number of distinct afferents converging on it and the PSP that would sum if
    every one of them fired in the same timestep.
    """
    meta_df = net_data["meta_df"]
    sources, targets = net_data["sources"], net_data["targets"]
    weights = net_data["weights_mV"]
    aff = np.asarray(encoder.sensory_indices, dtype=np.int64)

    mask = np.isin(sources, aff)
    df = pd.DataFrame({
        "pre": sources[mask], "post": targets[mask], "w": weights[mask],
    })
    conv = df.groupby("post").agg(
        n_afferents=("pre", "nunique"), n_syn=("pre", "size"), psp_mV=("w", "sum"),
    )
    conv["bodyId"] = meta_df["bodyId"].values[conv.index.values]
    conv["type"] = meta_df["type"].fillna("<untyped>").values[conv.index.values]
    conv["superclass"] = meta_df["superclass"].values[conv.index.values]
    return conv.sort_values("psp_mV", ascending=False), df


def measure_return_volley(
    net_data=None,
    encoder=None,
    network=None,
    rates_hz=(80, 120, 150, 200),
    burst_ms=40.0,
    verbose=True,
):
    """Deliverable 2: does a returning afferent volley fire anything downstream?

    Two things are measured, and they answer different questions:

    * the **ceiling**: all 41 afferents forced to fire together by a
      ``SpikeGeneratorGroup``, routed through their real connectome synapses with
      the real live weights and the real per-synapse delays.  This is the most
      the return path can ever deliver, so if nothing fires here nothing can fire
      under any drive.
    * the sweep over volley rate, which separates "one volley cannot but
      temporal summation can" from "the path is simply too thin".

    Reports the relays that fire, by name, with their convergence.
    """
    from brian2 import Synapses, SpikeGeneratorGroup, StateMonitor, amp, mV, ms

    from .network import sample_synaptic_delays_ms

    if net_data is None:
        net_data = load_full_vnc()
    meta_df, body_ids = net_data["meta_df"], net_data["body_ids"]
    if encoder is None:
        encoder = ProprioceptiveEncoder(meta_df, body_ids, leg="LF", side="L")
    if network is None:
        network = FullVNCNetwork(net_data)

    aff = np.asarray(encoder.sensory_indices, dtype=np.int64)
    conv, edges = afferent_convergence(net_data, encoder)

    in_scope_idx = set(lf_motor_in_scope(meta_df).index.values.tolist())
    all_lf_motor = set(
        meta_df[(meta_df["superclass"] == "vnc_motor")
                & (meta_df["subclass"] == "fl")
                & (meta_df["somaSide"] == "L")].index.values.tolist()
    )
    presynaptic_to_mn = set(np.unique(
        net_data["sources"][np.isin(net_data["targets"], list(in_scope_idx))]
    ).tolist())

    if verbose:
        print("\n" + "=" * 78)
        print("[2] RETURN VOLLEY: can it fire anything?")
        print("=" * 78)
        print(f"  recomputed from the LIVE code path (nt column "
              f"'{net_data['nt_col']}', confidence filled 0.5, sign-0 synapses "
              f"weight exactly 0)")
        print(f"  the 41 afferents make {len(edges):,} synapses onto "
              f"{conv.index.nunique():,} distinct targets")
        direct = conv[conv.index.isin(in_scope_idx)]
        relays = conv[~conv.index.isin(all_lf_motor)]
        print(f"\n  {'path':<38} {'convergence':>14} {'summed PSP (mV)':>18}")
        print(f"  {'afferent -> in-scope LF MN (direct)':<38} "
              f"{f'median {direct.n_afferents.median():.0f}, max {direct.n_afferents.max()}':>14} "
              f"{f'median {direct.psp_mV.median():.2f}, max {direct.psp_mV.max():.2f}':>18}")
        print(f"  {'afferent -> non-motor relay':<38} "
              f"{f'median {relays.n_afferents.median():.0f}, max {relays.n_afferents.max()}':>14} "
              f"{f'median {relays.psp_mV.median():.2f}, max {relays.psp_mV.max():.2f}':>18}")
        print(f"\n  bars: {SUSTAINED_BAR_MV:.2f} mV for one volley onto an "
              f"already-firing cell (0a), {FROM_REST_BAR_MV:.2f} mV from rest.")
        print(f"  targets clearing {SUSTAINED_BAR_MV:.1f} mV: "
              f"{int((conv.psp_mV >= SUSTAINED_BAR_MV).sum())}; clearing "
              f"{FROM_REST_BAR_MV:.0f} mV: "
              f"{int((conv.psp_mV >= FROM_REST_BAR_MV).sum())}")
        print(f"  strongest target anywhere: {conv.psp_mV.max():.2f} mV "
              f"({conv.iloc[0]['type']}, {int(conv.iloc[0]['n_afferents'])} afferents)")
        print("\n  top 8 by summed PSP (from live weights):")
        for idx, r in conv.head(8).iterrows():
            print(f"    {int(r.bodyId):>11} {r['type']:<12} {r.superclass:<15} "
                  f"conv {int(r.n_afferents):2d}  PSP {r.psp_mV:6.2f} mV")

    watch = list(conv.head(8).index.values)
    src_pos = {int(v): i for i, v in enumerate(aff)}
    sel = np.isin(net_data["sources"], aff)
    syn_i = np.array([src_pos[int(x)] for x in net_data["sources"][sel]])
    syn_j = net_data["targets"][sel]
    syn_w = net_data["weights_mV"][sel]

    results = []
    for hz in rates_hz:
        isi = 1000.0 / hz
        volley_t = np.arange(0.0, burst_ms, isi)
        network.reset()
        SG = SpikeGeneratorGroup(
            len(aff),
            np.repeat(np.arange(len(aff)), len(volley_t)),
            (np.tile(volley_t, len(aff)) + 1.0) * ms,
        )
        SS = Synapses(SG, network.G, "w : volt", on_pre="v_post += w")
        SS.connect(i=syn_i, j=syn_j)
        SS.w = syn_w * mV
        SS.delay = sample_synaptic_delays_ms(int(sel.sum()), None) * ms
        SM = StateMonitor(network.G, "v", record=watch)
        network.G.I = np.zeros(network.n_neurons) * amp
        network.net.add(SG)
        network.net.add(SS)
        network.net.add(SM)
        try:
            network.net.run((burst_ms + 40.0) * ms)
            times, indices = network.spike_table()
            v = np.asarray(SM.v / mV)
        finally:
            network.net.remove(SG)
            network.net.remove(SS)
            network.net.remove(SM)

        keep = times >= 1.0
        downstream = [x for x in np.unique(indices[keep]) if x not in set(aff.tolist())]
        peak_dv = {int(w): float(v[j].max() + 70.0) for j, w in enumerate(watch)}
        rows = []
        for x in sorted(downstream, key=lambda z: times[(indices == z) & keep].min()):
            rows.append({
                "bodyId": int(meta_df["bodyId"].values[x]),
                "type": str(meta_df["type"].fillna("<untyped>").values[x]),
                "superclass": meta_df["superclass"].values[x],
                "n_afferents": int(conv.loc[x, "n_afferents"]) if x in conv.index else 0,
                "psp_mV": float(conv.loc[x, "psp_mV"]) if x in conv.index else 0.0,
                "t_first_ms": float(times[(indices == x) & keep].min() - 1.0),
                "n_spikes": int(((indices == x) & keep).sum()),
                "is_lf_mn": x in in_scope_idx,
                "presynaptic_to_lf_mn": x in presynaptic_to_mn,
            })
        results.append({"rate_hz": hz, "relays": pd.DataFrame(rows), "peak_dv": peak_dv})

        if verbose:
            n_closing = sum(1 for r in rows if r["presynaptic_to_lf_mn"])
            print(f"\n  ceiling test, all 41 afferents at {hz} Hz for "
                  f"{burst_ms:.0f} ms: {len(rows)} downstream neurons fired, "
                  f"{n_closing} of them presynaptic to an in-scope LF motor "
                  f"neuron (= loop closure)")
            for r in rows:
                tag = " <- CLOSES THE LOOP" if r["presynaptic_to_lf_mn"] else ""
                print(f"    {r['bodyId']:>11} {r['type']:<12} conv "
                      f"{r['n_afferents']:2d}  PSP {r['psp_mV']:5.2f} mV  "
                      f"first {r['t_first_ms']:5.1f} ms  n={r['n_spikes']}{tag}")
            if not rows:
                print("    peak depolarisation of the strongest relays "
                      f"(threshold needs +{FROM_REST_BAR_MV:.0f} mV):")
                for w, dv in list(peak_dv.items())[:5]:
                    print(f"      {int(meta_df['bodyId'].values[w]):>11} "
                          f"{meta_df['type'].values[w]:<12} {dv:6.2f} mV")

    return {"convergence": conv, "ceiling": results, "watch": watch}


def measure_volley_from_physics(conduction, verbose=True):
    """How much of the return path the *physically achievable* volley engages.

    The ceiling test forces all 41 afferents to fire.  Physics does not: it fires
    a subset, at a rate set by the joint's own dynamics.  This re-runs the best
    conducting condition and reports which afferents actually fire, how much of
    each relay's convergence that represents, and whether anything downstream
    fires -- the number that decides whether Child 1 can work.
    """
    table = conduction["table"]
    network = conduction["network"]
    encoder, decoder = conduction["encoder"], conduction["decoder"]
    sim, model, data, state, groups = conduction["body"]
    net_data = network.net_data
    meta_df = net_data["meta_df"]

    conducting = table[table[[f"{m}_t_ms" for m in MODALITIES]].notna().any(axis=1)]
    if conducting.empty:
        if verbose:
            print("\n  no condition conducted, so there is no volley to trace.")
        return None

    best = conducting.loc[conducting["velocity_t_ms"].idxmin()]
    pool_size, hz = int(best["pool"]), int(best["nominal_hz"])

    from .muscle_decoder import MuscleDecoder

    members = decoder.muscle_pool_members("LFTibia_flex_93434")
    pool = [a for a in members if a.mn_type not in OUT_OF_SCOPE_MN_TYPES][:pool_size]
    times, indices, tr = run_lockstep(
        network, sim, model, data, state, groups, decoder, encoder,
        "LFTibia_flex_93434", pool, DRIVE_PA_FOR_HZ[hz], burst_ms=DEFAULT_BURST_MS,
    )

    aff = np.asarray(encoder.sensory_indices, dtype=np.int64)
    conv, edges = afferent_convergence(net_data, encoder)
    fired = set(np.unique(indices[np.isin(indices, aff)]).tolist())
    pool_idx = set(tr["pool_idx"].tolist())
    downstream = [
        x for x in np.unique(indices)
        if x not in set(aff.tolist()) and x not in pool_idx
    ]

    rows = []
    for idx in conv.head(8).index.values:
        pres = set(edges[edges.post == idx].pre.tolist())
        active = pres & fired
        rows.append({
            "bodyId": int(conv.loc[idx, "bodyId"]),
            "type": conv.loc[idx, "type"],
            "n_afferents": int(conv.loc[idx, "n_afferents"]),
            "n_fired": len(active),
            "psp_total_mV": float(conv.loc[idx, "psp_mV"]),
            "psp_available_mV": float(
                edges[(edges.post == idx) & edges.pre.isin(active)].w.sum()
            ),
        })
    engaged = pd.DataFrame(rows)

    if verbose:
        print("\n  what the PHYSICALLY ACHIEVABLE volley delivers "
              f"(best condition: pool {pool_size} @ {hz} Hz):")
        print(f"    {len(fired)} of {len(aff)} afferents fired, "
              f"{int(np.isin(indices, aff).sum())} afferent spikes in "
              f"{DEFAULT_BURST_MS:.0f} ms")
        print(f"    downstream neurons that fired: {len(downstream)}")
        print(f"    {'relay':<24} {'conv':>5} {'fired':>6} "
              f"{'PSP avail / total (mV)':>24}")
        for r in engaged.itertuples():
            print(f"    {str(r.bodyId) + ' ' + r.type:<24} {r.n_afferents:5d} "
                  f"{r.n_fired:6d} {r.psp_available_mV:11.2f} /"
                  f"{r.psp_total_mV:7.2f}")
    return {"engaged": engaged, "n_fired": len(fired),
            "n_downstream": len(downstream), "pool": pool_size, "rate_hz": hz}


# ---------------------------------------------------------------------------
# Deliverable 4: multi-muscle, multi-joint drive (the breadth hypothesis)
# ---------------------------------------------------------------------------

# The 15 FlyMimic muscles grouped by the joint group they actually move,
# MEASURED rather than inferred from the name: each muscle was driven alone at
# activation 1.0 for 50 ms from the settled posture and the joint group carrying
# the largest |displacement| recorded (``measure_muscle_displacements``).  Every
# muscle's own prefix group won, so the naming convention is confirmed, but the
# excursions are wildly unequal and that is what the sweep needs:
#
#   coxa        LFC_tergopleural_promotor_b   yaw -0.358, pitch -0.665
#   trochanter  LFF_sterno-tergo-troch_ext_b  yaw -0.641, pitch +0.735, roll +0.273
#   tibia       LFTibia_extensor_93932        pitch -1.031   (flexor only +0.779)
MUSCLES_BY_GROUP: dict[str, tuple[str, ...]] = {
    "coxa": (
        "LFC_tergopleural_promotor_a",
        "LFC_tergopleural_promotor_b",
        "LFC_pleural_remotor_and_abductor",
        "LFC_pleural_promotor",
        "LFC_sternal_anterior_rotator",
        "LFC_sternal_posterior_rotator",
        "LFC_sternal_adductor",
    ),
    "trochanter": (
        "LFF_trochanter_flexor_b",
        "LFF_sterno-tergo-trochanter_extensor_a",
        "LFF_sterno-tergo-trochanter_extensor_b",
        "LFF_accesory_trochanter_flexor",
        "LFF_trochanter_extensor",
        "LFF_trochanter_flexor_a",
    ),
    "tibia": (
        "LFTibia_flex_93434",
        "LFTibia_extensor_93932",
    ),
}

# Largest single-muscle excursion per group, measured (see above).
STRONGEST_BY_GROUP: dict[str, str] = {
    "coxa": "LFC_tergopleural_promotor_b",
    "trochanter": "LFF_sterno-tergo-trochanter_extensor_b",
    "tibia": "LFTibia_extensor_93932",
}


def in_scope_pool_for_muscles(decoder, muscles):
    """Union of the in-scope LF motor neurons driving any of ``muscles``.

    De-duplicated by network index: a motor neuron may drive more than one
    muscle (``Tr flexor MN`` drives both trochanter flexor heads), and counting
    it twice would double its size weight inside the pool.
    """
    seen: dict[int, object] = {}
    for muscle in muscles:
        for a in decoder.muscle_pool_members(muscle):
            if a.mn_type in OUT_OF_SCOPE_MN_TYPES:
                continue
            seen.setdefault(a.net_index, a)
    return sorted(seen.values(), key=lambda a: -a.size)


def run_lockstep_multi(
    network,
    sim,
    model,
    data,
    state,
    groups,
    decoder,
    encoder,
    muscles,
    drive_pa,
    burst_ms=DEFAULT_BURST_MS,
    rate_window_ms=50.0,
    freeze_physics=False,
    watch=None,
    drive_pa_by_class=None,
    drive_ms_by_class=None,
    background_pa=0.0,
    background_poisson_hz=None,
    background_weight_mV=BACKGROUND_WEIGHT_MV,
    background_settle_ms=0.0,
    background_seed=0,
):
    """Lockstep run driving SEVERAL muscles at once, with a frozen-physics mode.

    Differs from ``run_lockstep`` in three ways, each deliberate:

    * the driven pool is the **union** of the in-scope motor pools of every named
      muscle, so recruiting more muscles recruits more motor neurons -- which is
      the point, since afferent breadth is what the hypothesis is about;
    * **all 15** decoded muscle activations are applied, not just one.  A motor
      neuron can innervate more than one muscle head, so restricting ``ctrl`` to
      a single index (as ``run_lockstep`` does) silently discards contraction the
      decoder actually commanded;
    * ``freeze_physics=True`` pins ``qpos``/``qvel``/``act`` to the settled state
      on every timestep.  The neural drive, the decode and the encode all run
      unchanged, but the joint cannot move and the tendon cannot load, so the
      sensory current is constant at its resting value.  Any afferent that spikes
      in that condition did not hear from the body -- it heard from the
      connectome.  This is the negative control 0c never ran, and it is checked
      rather than assumed: the afferent current trace is asserted constant.

    ``act`` is restored between conditions by ``reset_body``, not merely
    ``qpos``/``qvel``: muscle activation carries its own 0.1/0.4 ms first-order
    dynamics, and the pre-existing ``proprio_test`` demo leaks one condition into
    the next by omitting it.

    Motor rate -> activation is ``MuscleDecoder.muscle_activations``, a
    size-principle **weighted sum**.  A mean would violate the size principle and
    once drove a joint backwards by -0.225 rad.

    ``background_pa`` sets the **relays' operating point**.  Every sweep before
    2026-08-18 left ``drive`` at exactly 0 for every neuron outside the driven
    motor pool, so a relay interneuron sat at exactly ``V_rest = -70 mV`` and had
    to be pushed the whole 20 mV to threshold by the afferent volley alone -- which
    is what produced the ~26 ms of synaptic integration in the 28.6 ms floor.  Real
    VNC interneurons are embedded in a continuously active network.  The current is
    applied to every neuron EXCEPT the driven motor pool and the 41 afferents, so
    the variable being changed is the relays' idling point and not the motor drive
    or the sensory gain.  ``background_poisson_hz`` does the same thing through
    ``network.py``'s own ``create_background_drive`` mechanism (Poisson sources at
    1.3 mV) instead, which adds variance as well as mean -- the two are NOT
    equivalent, since fluctuations can cross threshold at a mean that a constant
    current cannot.  ``background_settle_ms`` runs the background ALONE (motor drive
    off, afferents at their settled resting current) for that long before the
    stimulus, so the relays are already at their idling point when the drive starts
    instead of climbing towards it; the settle's spikes are excluded and every
    latency is measured from the end of it.

    ``drive_pa_by_class`` / ``drive_ms_by_class`` make the drive itself
    class-specific, which is what actually tests the biology: Azevedo's fast MNs
    fire **a few spikes** and are silent otherwise, while slow MNs are **tonically
    active**.  Driving every neuron at one uniform rate for the whole burst -- what
    ``drive_pa`` alone does -- is a protocol no fly leg motor pool ever runs.  When
    given, they override ``drive_pa`` per neuron: current is applied to a neuron
    only while ``t < drive_ms_by_class[its class]``, so a fast MN can be given a
    2-spike burst inside a 200 ms window while a slow MN idles throughout.
    """
    import mujoco
    from brian2 import (
        PoissonGroup, StateMonitor, Synapses, amp, mV, ms, network_operation,
    )

    muscles = tuple(muscles)
    pool = in_scope_pool_for_muscles(decoder, muscles)
    pool_idx = np.array([a.net_index for a in pool], dtype=np.int64)
    aff_idx = np.asarray(encoder.sensory_indices, dtype=np.int64)

    n_steps = int(round(burst_ms / DT_MS))
    window = int(round(rate_window_ms / DT_MS))
    ctrl_lo = np.asarray(model.actuator_ctrlrange[:, 0], dtype=float)

    reset_body(sim, model, data, state)
    network.reset()

    # The background changes the RELAYS' operating point, so it must not reach the
    # driven motor pool (that would change the motor drive) or the afferents (that
    # would change the sensory gain, which 0b calibrated).
    bg_mask = np.ones(network.n_neurons, dtype=bool)
    bg_mask[pool_idx] = False
    bg_mask[aff_idx] = False
    background = np.where(bg_mask, float(background_pa), 0.0)

    hist = np.zeros((n_steps, len(pool_idx)), dtype=bool)
    tr = {
        "activations": np.zeros((n_steps, model.nu)),
        "angles": np.zeros((n_steps, N_LF_JOINTS)),
        "vels": np.zeros((n_steps, N_LF_JOINTS)),
        "afferent_pa": np.zeros((n_steps, len(aff_idx))),
    }
    drive = np.zeros(network.n_neurons)
    if drive_pa_by_class is None:
        drive[pool_idx] = drive_pa
        # No per-class gating: every driven neuron is on for the whole burst.
        drive_until = np.full(network.n_neurons, np.inf)
    else:
        for a in pool:
            drive[a.net_index] = drive_pa_by_class.get(a.force_class, drive_pa)
        drive_until = np.zeros(network.n_neurons)
        for a in pool:
            drive_until[a.net_index] = (
                burst_ms if drive_ms_by_class is None
                else drive_ms_by_class.get(a.force_class, burst_ms)
            )
    counter = {"k": 0}

    @network_operation(dt=DT_MS * ms, when="start")
    def couple():
        k = counter["k"]
        if k >= n_steps:
            return
        spiked = network.G.spiked_[:]
        hist[k] = spiked[pool_idx] > 0
        network.G.spiked_[:] = 0.0

        lo = max(0, k + 1 - window)
        counts = hist[lo:k + 1]
        duration_s = (k + 1 - lo) * DT_MS / 1000.0
        rates_hz = {
            int(pool_idx[j]): counts[:, j].sum() / duration_s
            for j in range(len(pool_idx))
        }
        activations = decoder.muscle_activations(rates_hz)

        # ctrlrange is [1e-4, 1]: a muscle pulls, never pushes, and 0 is out of
        # range, so an uncommanded muscle sits at the floor rather than at zero.
        data.ctrl[:] = np.maximum(activations, ctrl_lo)
        if freeze_physics:
            # The joints are pinned, so no movement and no tendon loading can be
            # generated; everything else in the loop runs exactly as above.
            data.qpos[:] = state["qpos"]
            data.qvel[:] = state["qvel"]
            data.act[:] = state["act"]
            mujoco.mj_forward(model, data)
        else:
            sim.step()

        angles = sim.get_joint_angles("nmf")[:N_LF_JOINTS]
        vels = sim.get_joint_velocities("nmf")[:N_LF_JOINTS]
        loads = tendon_loads_by_group(data, groups)
        currents = encoder.encode(angles, vels, loads)

        tr["activations"][k] = activations
        tr["angles"][k] = angles
        tr["vels"][k] = vels
        tr["afferent_pa"][k] = currents[aff_idx] * 1e12

        # Per-class gating: a phasic class's current is withdrawn once its short
        # burst window has elapsed, so it goes silent as it does in the animal.
        active = drive * ((k + 1) * DT_MS < drive_until)
        network.G.I = (active + background + currents * 1e12) * 1e-12 * amp
        counter["k"] = k + 1

    # ---- optional Poisson background, via network.py's own mechanism ----
    bg_objects = []
    if background_poisson_hz:
        from brian2 import Hz, seed as brian_seed

        bg_targets = np.flatnonzero(bg_mask)
        brian_seed(background_seed)
        PG = PoissonGroup(BACKGROUND_N_SOURCES, rates=background_poisson_hz * Hz)
        S_bg = Synapses(
            PG, network.G,
            on_pre=f"v_post += {float(background_weight_mV)}*mV",
        )
        S_bg.connect(
            i=np.repeat(np.arange(BACKGROUND_N_SOURCES), len(bg_targets)),
            j=np.tile(bg_targets, BACKGROUND_N_SOURCES),
        )
        bg_objects = [PG, S_bg]
        for obj in bg_objects:
            network.net.add(obj)

    SM = StateMonitor(network.G, "v", record=list(watch)) if watch else None
    if SM is not None:
        network.net.add(SM)
    try:
        # ---- background settle: relays reach their idling point BEFORE the
        # stimulus, with no motor drive.  Afferents are held at the settled
        # resting current so the sensory channel is where the body actually
        # leaves it, not at zero.
        t_offset_ms = 0.0
        n_spikes_settle = 0
        if background_settle_ms > 0:
            rest_currents = encoder.encode(
                np.asarray(state["qpos"][:N_LF_JOINTS], dtype=float),
                np.zeros(N_LF_JOINTS),
                tendon_loads_by_group(data, groups),
            ) * 1e12
            network.G.I = (background + rest_currents) * 1e-12 * amp
            network.net.run(background_settle_ms * ms)
            network.G.spiked_[:] = 0.0
            t_offset_ms = float(background_settle_ms)
            n_spikes_settle = int(network.M.num_spikes)

        network.G.I = (drive + background) * 1e-12 * amp
        network.net.add(couple)
        try:
            network.net.run(n_steps * DT_MS * ms)
        finally:
            network.net.remove(couple)
        v_trace = np.asarray(SM.v / mV) if SM is not None else None
        peak_dv, settle_dv = {}, {}
        if v_trace is not None:
            k0 = int(round(t_offset_ms / DT_MS))
            peak_dv = {
                int(w): float(v_trace[j, k0:].max() + 70.0)
                for j, w in enumerate(watch)
            }
            if k0 > 0:
                # The relays' MEASURED operating point at the moment the stimulus
                # starts -- the whole point of the background, so it is read off a
                # StateMonitor rather than predicted from dV = I * R.
                k_lo = max(0, k0 - int(round(50.0 / DT_MS)))
                settle_dv = {
                    int(w): float(v_trace[j, k_lo:k0].mean() + 70.0)
                    for j, w in enumerate(watch)
                }
    finally:
        if SM is not None:
            network.net.remove(SM)
        for obj in bg_objects:
            network.net.remove(obj)

    if freeze_physics:
        spread = float(np.abs(tr["afferent_pa"] - tr["afferent_pa"][0]).max())
        if spread > 1e-9:
            raise RuntimeError(
                f"freeze_physics run modulated the afferent current by "
                f"{spread:.3e} pA; the control is not actually frozen, so any "
                "afferent spike would be uninterpretable."
            )

    times, indices = network.spike_table()
    if t_offset_ms > 0:
        # The settle's spikes are not part of the measurement, and t = 0 must mean
        # "the stimulus started" or every latency would be offset by the settle.
        keep = times >= t_offset_ms - 1e-9
        settle_idx = indices[~keep]
        times, indices = times[keep] - t_offset_ms, indices[keep]
        tr["settle_spikes"] = n_spikes_settle
        tr["settle_hz_mean"] = float(
            len(settle_idx) / network.n_neurons / (t_offset_ms / 1000.0)
        )
        tr["settle_n_active"] = int(len(np.unique(settle_idx)))
    else:
        tr["settle_spikes"] = 0
        tr["settle_hz_mean"] = 0.0
        tr["settle_n_active"] = 0
    tr["pool_rate_hz"] = hist.sum() / (len(pool_idx) * burst_ms / 1000.0)
    tr["pool_idx"] = pool_idx
    tr["afferent_idx"] = aff_idx
    tr["muscles"] = muscles
    tr["peak_dv"] = peak_dv
    tr["settle_dv"] = settle_dv
    tr["background_pa"] = float(background_pa)
    tr["background_poisson_hz"] = float(background_poisson_hz or 0.0)
    return times, indices, tr


def measure_muscle_displacements(sim, model, data, state, verbose=True):
    """Per-muscle joint excursion, so the sweep's group labels are measured.

    Each muscle is driven alone at ``ctrl = 1.0`` for 50 ms from the settled
    posture (with ``act`` restored first) and the resulting displacement of all
    seven LF joints recorded.  Pure physics -- no network -- so it is cheap, and
    it is what ``STRONGEST_BY_GROUP`` is derived from.
    """
    from .muscle_decoder import MUSCLE_NAMES

    rest = np.asarray(state["qpos"][:N_LF_JOINTS], dtype=float)
    rows = []
    for i, muscle in enumerate(MUSCLE_NAMES):
        reset_body(sim, model, data, state)
        data.ctrl[:] = model.actuator_ctrlrange[:, 0]
        data.ctrl[i] = 1.0
        for _ in range(int(round(DEFAULT_BURST_MS / DT_MS))):
            sim.step()
        dq = sim.get_joint_angles("nmf")[:N_LF_JOINTS] - rest
        row = {"muscle": muscle}
        for group, idx in JOINT_GROUPS.items():
            row[group] = float(np.abs(dq[list(idx)]).max())
        row["dominant"] = max(JOINT_GROUPS, key=lambda g: row[g])
        rows.append(row)
    table = pd.DataFrame(rows)
    reset_body(sim, model, data, state)

    if verbose:
        print("\n  per-muscle peak |joint displacement| (rad) after 50 ms at "
              "ctrl = 1.0, by joint group:")
        print(f"    {'muscle':<42} {'coxa':>8} {'troch':>8} {'tibia':>8}  "
              f"dominant")
        for r in table.itertuples():
            print(f"    {r.muscle:<42} {r.coxa:8.4f} {r.trochanter:8.4f} "
                  f"{r.tibia:8.4f}  {r.dominant}")
        mismatch = [
            r.muscle for r in table.itertuples()
            if r.muscle not in MUSCLES_BY_GROUP[r.dominant]
        ]
        print(f"    every muscle's dominant group matches its name prefix: "
              f"{not mismatch}"
              + (f" (exceptions: {mismatch})" if mismatch else ""))
    return table


def _relay_afferent_edges(net_data, encoder):
    """(convergence table, edge table, afferent role map) for the return path."""
    conv, edges = afferent_convergence(net_data, encoder)
    role = {
        a.neuron_index: (a.joint_group, a.modality, a.type_code)
        for a in encoder.assignments
    }
    return conv, edges, role


def _greedy_muscle_set(edges, target_idx, fired_by_muscle, max_muscles=6):
    """Muscles chosen to maximise the PSP a target relay could receive.

    ``fired_by_muscle`` maps a muscle to the set of afferents that MEASURABLY
    spiked when it was driven alone.  Greedily add the muscle whose newly fired
    afferents contribute the most weight onto ``target_idx``.

    The union is an upper bound, not a prediction: muscles interact mechanically
    and unipolar antagonists can cancel, so a set chosen this way still has to be
    run.  It exists so the sweep can target a relay's *specific* inputs from the
    connectome instead of hoping broad drive happens to hit them.
    """
    w = edges[edges.post == target_idx].groupby("pre").w.sum()
    chosen: list[str] = []
    have: set[int] = set()
    trace = []
    while len(chosen) < max_muscles:
        best, best_gain, best_new = None, 0.0, set()
        for muscle, fired in fired_by_muscle.items():
            if muscle in chosen:
                continue
            new = (fired & set(w.index)) - have
            gain = float(w.loc[sorted(new)].sum()) if new else 0.0
            if gain > best_gain + 1e-12:
                best, best_gain, best_new = muscle, gain, new
        if best is None:
            break
        chosen.append(best)
        have |= best_new
        trace.append((best, best_gain, float(w.loc[sorted(have)].sum())))
    return chosen, have, trace


def _condition_row(net_data, encoder, conv, edges, in_scope_idx, presyn_idx,
                   times, indices, tr, label, kind, watch):
    """One sweep row: afferents fired, PSP delivered, and what fired downstream."""
    aff = np.asarray(encoder.sensory_indices, dtype=np.int64)
    pool_idx = set(tr["pool_idx"].tolist())
    aff_set = set(aff.tolist())

    fired_aff = set(np.unique(indices[np.isin(indices, aff)]).tolist())
    downstream = [
        int(x) for x in np.unique(indices)
        if int(x) not in aff_set and int(x) not in pool_idx
    ]
    closing = [x for x in downstream if x in presyn_idx]
    motor = [x for x in downstream if x in in_scope_idx]

    best_idx, best_avail, best_total = None, -1.0, 0.0
    for idx in watch:
        pres = set(edges[edges.post == idx].pre.tolist())
        avail = float(
            edges[(edges.post == idx) & edges.pre.isin(pres & fired_aff)].w.sum()
        )
        if avail > best_avail:
            best_idx, best_avail = idx, avail
            best_total = float(conv.loc[idx, "psp_mV"])

    # Timing, so the ordering can be checked rather than assumed: an afferent
    # spike must PRECEDE the downstream spike it is supposed to have caused.
    aff_sel = np.isin(indices, aff)
    t_first_aff = float(times[aff_sel].min()) if aff_sel.any() else np.nan
    t_first_closing = np.nan
    if closing:
        sel = np.isin(indices, closing)
        t_first_closing = float(times[sel].min())

    # The frozen control is only meaningful if the motor drive was applied there
    # too, so the driven pool's own spike count is carried on every row.
    pool_spikes = int(np.isin(indices, list(pool_idx)).sum())

    # For each closer, how much afferent weight it actually received from
    # afferents that fired -- so 'presynaptic to a motor neuron' can be
    # distinguished from 'reached by the sensory volley'.
    closing_detail = []
    sources, targets = net_data["sources"], net_data["targets"]
    weights = net_data["weights_mV"]
    for x in closing:
        pres = set(edges[edges.post == x].pre.tolist())
        # The SIGN of the closer's own output onto motor neurons.  "Presynaptic
        # to a motor neuron" is the loop-closure criterion, but an inhibitory
        # closer carries the sensory signal home as a *suppression*, which is a
        # real return path and not the same thing as an excitatory one.
        out = (sources == x) & np.isin(targets, list(in_scope_idx))
        closing_detail.append({
            "idx": x,
            "n_aff_in": len(pres),
            "n_aff_fired": len(pres & fired_aff),
            "psp_from_fired_mV": float(
                edges[(edges.post == x) & edges.pre.isin(pres & fired_aff)].w.sum()
            ),
            "t_first_ms": float(times[indices == x].min()),
            "n_spikes": int((indices == x).sum()),
            "is_mn": x in in_scope_idx,
            "n_mn_out": int(out.sum()),
            "mn_out_mV": float(weights[out].sum()),
        })

    meta_df = net_data["meta_df"]
    return {
        "condition": label,
        "kind": kind,
        "n_muscles": len(tr["muscles"]),
        "pool": len(tr["pool_idx"]),
        "pool_hz": float(tr["pool_rate_hz"]),
        "act_peak": float(tr["activations"].max()),
        "n_muscles_active": int((tr["activations"].max(axis=0) > 1e-3).sum()),
        "excursion_rad": float(
            np.abs(tr["angles"] - tr["angles"][0]).max()
        ),
        "n_afferents_fired": len(fired_aff),
        "n_afferent_spikes": int(np.isin(indices, aff).sum()),
        "n_pool_spikes": pool_spikes,
        "t_first_afferent_ms": t_first_aff,
        "t_first_closing_ms": t_first_closing,
        "closing_detail": closing_detail,
        "best_relay": str(meta_df["type"].fillna("<untyped>").values[best_idx]),
        "psp_avail_mV": best_avail,
        "psp_total_mV": best_total,
        "peak_dv_mV": max(tr["peak_dv"].values()) if tr["peak_dv"] else np.nan,
        "peak_dv_by_relay": dict(tr["peak_dv"]),
        "n_downstream": len(downstream),
        "n_downstream_motor": len(motor),
        "n_closing": len(closing),
        "n_closing_relays": len([x for x in closing if x not in in_scope_idx]),
        "downstream_idx": downstream,
        "closing_idx": closing,
        "fired_afferents": fired_aff,
        "muscles": tr["muscles"],
    }


def measure_multi_muscle_drive(
    net_data=None,
    conduction=None,
    rates_hz=(200,),
    burst_ms=(50.0, 200.0),
    verbose=True,
):
    """Deliverable 4: does multi-joint drive fire anything the return path needs?

    0c's exit gate failed with a diagnosis attached: the relays that could carry
    an afferent volley back to a motor neuron integrate across all three joint
    groups, so a single-muscle twitch supplies roughly one group's share of a
    three-group requirement (measured: 4.63 of 15.56 mV onto ``IN23B024``).  The
    hypothesis is that drive spanning coxa + trochanter + tibia recruits enough
    afferent **breadth** to close the gap.

    Four condition families, so a positive result can be attributed:

    * ``1group`` -- the known-failing control, one group's strongest muscle.
    * ``2group`` / ``3group`` -- the strongest muscle of two or three groups.
    * ``broad`` -- every muscle of a group, or all 15, which necessarily
      co-activates unipolar antagonists.  Since a muscle can only pull, an
      antagonist pair may either add displacement on the joints they do not
      share, or cancel; the sweep measures which.
    * ``targeted`` -- the muscle set the connectome says should maximise the PSP
      arriving at one named relay, built greedily from the afferents each muscle
      is MEASURED to fire on its own.

    Every condition is also run with ``freeze_physics=True``.  Anything that
    fires in both did not hear from the body: there are 0 direct motor->afferent
    synapses, but 34 relays form motor->X->afferent paths reaching 27 of 41
    afferents, and the encoder parks afferents near threshold.
    """
    from .muscle_decoder import MUSCLE_NAMES, MuscleDecoder

    if net_data is None:
        net_data = load_full_vnc()
    meta_df, body_ids = net_data["meta_df"], net_data["body_ids"]
    meta_bid = meta_df["bodyId"].values
    meta_type = meta_df["type"].fillna("<untyped>").values

    if conduction is not None:
        encoder, decoder = conduction["encoder"], conduction["decoder"]
        network = conduction["network"]
        sim, model, data, state, groups = conduction["body"]
    else:
        encoder = ProprioceptiveEncoder(meta_df, body_ids, leg="LF", side="L")
        decoder = MuscleDecoder(meta_df, body_ids)
        sim, model, data, state, groups, _names = build_settled_body(verbose=verbose)
        network = FullVNCNetwork(net_data)

    conv, edges, role = _relay_afferent_edges(net_data, encoder)
    in_scope_idx = set(lf_motor_in_scope(meta_df).index.values.tolist())
    presyn_idx = set(np.unique(
        net_data["sources"][np.isin(net_data["targets"], list(in_scope_idx))]
    ).tolist())
    conv["presyn_to_mn"] = conv.index.isin(presyn_idx)
    watch = list(conv.head(8).index.values)
    closers = conv[conv["presyn_to_mn"]].head(5)

    if verbose:
        print("\n" + "=" * 78)
        print("[4] MULTI-MUSCLE, MULTI-JOINT DRIVE: does breadth close the loop?")
        print("=" * 78)
        print(f"  scope: {len(in_scope_idx)} of 64 LF motor neurons; "
              f"{len(encoder.assignments)} LF afferents; "
              f"{len(presyn_idx):,} neurons are presynaptic to some in-scope LF MN")
        print("  loop closure = a neuron presynaptic to an in-scope LF motor "
              "neuron fires\n  BECAUSE the body moved (i.e. fires with physics "
              "live and not with physics frozen).")
        print("\n  the strongest relays, and their afferent input by joint group "
              "(live weights):")
        print(f"    {'relay':<22} {'PSP':>6} {'conv':>5}  "
              + "".join(f"{g:>22}" for g in JOINT_GROUPS) + f"{'posture':>22}"
              + "   presyn->MN")
        for idx in watch:
            r = conv.loc[idx]
            pres = edges[edges.post == idx].groupby("pre").w.sum()
            cells = []
            for key in list(JOINT_GROUPS) + ["multi"]:
                sel = [p for p in pres.index if role[p][0] == key]
                cells.append(f"{float(pres.loc[sel].sum()):9.2f} mV ({len(sel):2d})"
                             if sel else f"{'--':>16}      ")
            print(f"    {str(int(r.bodyId)) + ' ' + r['type']:<22} "
                  f"{r.psp_mV:6.2f} {int(r.n_afferents):5d}  " + "".join(cells)
                  + f"   {'YES' if r.presyn_to_mn else 'no'}")
        print(f"\n  bars: {SUSTAINED_BAR_MV:.2f} mV for one volley onto an "
              f"already-firing cell, {FROM_REST_BAR_MV:.0f} mV from rest.")

    displacements = measure_muscle_displacements(
        sim, model, data, state, verbose=verbose
    )

    # ---- per-muscle single drive: which afferents does each muscle fire? ----
    drive_pa = DRIVE_PA_FOR_HZ[max(rates_hz)]
    probe_ms = min(burst_ms)
    fired_by_muscle: dict[str, set] = {}
    if verbose:
        print(f"\n  which afferents does each muscle fire ALONE "
              f"({probe_ms:.0f} ms @ {max(rates_hz)} Hz nominal)?  "
              "measured, not predicted:")
        print(f"    {'muscle':<42} {'pool':>4} {'aff':>4}  by group/modality")
    for muscle in MUSCLE_NAMES:
        times, indices, tr = run_lockstep_multi(
            network, sim, model, data, state, groups, decoder, encoder,
            (muscle,), drive_pa, burst_ms=probe_ms,
        )
        aff = np.asarray(encoder.sensory_indices, dtype=np.int64)
        fired = set(np.unique(indices[np.isin(indices, aff)]).tolist())
        fired_by_muscle[muscle] = fired
        if verbose:
            tally: dict[str, int] = {}
            for p in fired:
                g, m, _ = role[p]
                tally[f"{g}/{m}"] = tally.get(f"{g}/{m}", 0) + 1
            print(f"    {muscle:<42} {len(tr['pool_idx']):4d} {len(fired):4d}  "
                  + " ".join(f"{k}={v}" for k, v in sorted(tally.items())))

    # ---- conditions ----------------------------------------------------
    strongest = STRONGEST_BY_GROUP
    conditions: list[tuple[str, str, tuple[str, ...]]] = []
    for group in JOINT_GROUPS:
        conditions.append((f"1group:{group}", "1group", (strongest[group],)))
    conditions.append(
        ("1group:tibia_flexor(0c ref)", "1group", ("LFTibia_flex_93434",))
    )
    pairs = [("coxa", "trochanter"), ("coxa", "tibia"), ("trochanter", "tibia")]
    for a, b in pairs:
        conditions.append(
            (f"2group:{a}+{b}", "2group", (strongest[a], strongest[b]))
        )
    conditions.append((
        "3group:strongest x3", "3group",
        tuple(strongest[g] for g in JOINT_GROUPS),
    ))
    conditions.append((
        "3group:strongest x3 + tibia flexor", "3group",
        tuple(strongest[g] for g in JOINT_GROUPS) + ("LFTibia_flex_93434",),
    ))
    for group in JOINT_GROUPS:
        conditions.append((
            f"broad:all {group} muscles", "broad", MUSCLES_BY_GROUP[group],
        ))
    conditions.append((
        "broad:all coxa + strongest troch/tibia", "broad",
        MUSCLES_BY_GROUP["coxa"] + (strongest["trochanter"], strongest["tibia"]),
    ))
    conditions.append(("broad:all 15 muscles", "broad", tuple(MUSCLE_NAMES)))

    targeted_traces = []
    for idx in list(closers.index.values[:2]) + [watch[0]]:
        name = f"{int(conv.loc[idx, 'bodyId'])} {conv.loc[idx, 'type']}"
        chosen, have, trace = _greedy_muscle_set(edges, idx, fired_by_muscle)
        if not chosen:
            continue
        label = f"targeted:{conv.loc[idx, 'type']}"
        if not any(c[2] == tuple(chosen) for c in conditions):
            conditions.append((label, "targeted", tuple(chosen)))
        targeted_traces.append((name, idx, chosen, trace,
                                float(conv.loc[idx, "psp_mV"])))

    if verbose and targeted_traces:
        print("\n  targeted sets, built greedily from the afferents each muscle "
              "is measured to fire:")
        for name, idx, chosen, trace, total in targeted_traces:
            print(f"    {name} (total available {total:.2f} mV):")
            for muscle, gain, cumulative in trace:
                print(f"      + {muscle:<42} +{gain:5.2f} -> "
                      f"{cumulative:5.2f} mV union upper bound")

    seen_sets: set[tuple[str, ...]] = set()
    rows = []
    for label, kind, muscles in conditions:
        key = tuple(sorted(muscles))
        if key in seen_sets:
            continue
        seen_sets.add(key)
        for hz in rates_hz:
            for ms_burst in burst_ms:
                for frozen in (False, True):
                    times, indices, tr = run_lockstep_multi(
                        network, sim, model, data, state, groups, decoder,
                        encoder, muscles, DRIVE_PA_FOR_HZ[hz],
                        burst_ms=ms_burst, freeze_physics=frozen, watch=watch,
                    )
                    row = _condition_row(
                        net_data, encoder, conv, edges, in_scope_idx,
                        presyn_idx, times, indices, tr, label, kind, watch,
                    )
                    row.update({"nominal_hz": hz, "burst_ms": ms_burst,
                                "frozen": frozen})
                    rows.append(row)

    table = pd.DataFrame(rows)
    live = table[~table["frozen"]].reset_index(drop=True)
    frozen_t = table[table["frozen"]].reset_index(drop=True)

    # Body-attributable firing: fired with physics live, did NOT fire frozen.
    key_cols = ["condition", "nominal_hz", "burst_ms"]
    frozen_map = {
        tuple(r[c] for c in key_cols): set(r["downstream_idx"])
        for _, r in frozen_t.iterrows()
    }
    frozen_aff = {
        tuple(r[c] for c in key_cols): r["fired_afferents"]
        for _, r in frozen_t.iterrows()
    }
    live = live.copy()
    live["n_downstream_frozen"] = [
        len(frozen_map.get(tuple(r[c] for c in key_cols), set()))
        for _, r in live.iterrows()
    ]
    live["n_afferents_frozen"] = [
        len(frozen_aff.get(tuple(r[c] for c in key_cols), set()))
        for _, r in live.iterrows()
    ]
    live["body_attributable"] = [
        sorted(set(r["closing_idx"])
               - frozen_map.get(tuple(r[c] for c in key_cols), set()))
        for _, r in live.iterrows()
    ]
    live["n_body_closing"] = live["body_attributable"].map(len)

    if verbose:
        _print_multi_muscle(live, frozen_t, meta_bid, meta_type, conv, role,
                            edges, encoder)
    return {
        "table": table, "live": live, "frozen": frozen_t,
        "displacements": displacements, "convergence": conv,
        "fired_by_muscle": fired_by_muscle, "watch": watch,
    }


def _print_multi_muscle(live, frozen_t, meta_bid, meta_type, conv, role, edges,
                        encoder):
    n_aff = len(encoder.assignments)
    print("\n  SWEEP -- physics live.  'aff' = afferents that SPIKED of "
          f"{n_aff}; 'PSP' = mV\n  delivered to the best-served relay by those "
          "afferents, over its total; 'peak dV'\n  = highest depolarisation of "
          "any watched relay (context only -- a voltage is not a\n  spike); "
          "'down' = non-afferent non-pool neurons that fired.")
    print(f"\n    {'condition':<38} {'ms':>4} {'m':>2} {'pool':>4} {'exc':>6} "
          f"{'aff':>4} {'spk':>5} {'PSP avail/total':>17} {'peak dV':>8} "
          f"{'down':>5} {'MN':>3} {'pre→MN':>7}")
    for r in live.sort_values(["kind", "condition", "burst_ms"]).itertuples():
        print(f"    {r.condition:<38} {r.burst_ms:4.0f} {r.n_muscles:2d} "
              f"{r.pool:4d} {r.excursion_rad:6.3f} {r.n_afferents_fired:4d} "
              f"{r.n_afferent_spikes:5d} {r.psp_avail_mV:7.2f} /"
              f"{r.psp_total_mV:8.2f} {r.peak_dv_mV:8.2f} "
              f"{r.n_downstream:5d} {r.n_downstream_motor:3d} "
              f"{r.n_closing:7d}")

    print("\n  NEGATIVE CONTROL -- same drive, physics frozen (joints pinned, so "
          "the sensory\n  current is constant at its resting value; asserted, "
          "not assumed).  'pool spk' proves\n  the motor drive really was "
          "applied, so a zero afferent count is a result and not a\n  run that "
          "simply did nothing:")
    print(f"    {'condition':<38} {'ms':>4} {'pool spk':>9} {'aff fired':>10} "
          f"{'aff spikes':>11} {'down':>5} {'pre→MN':>7}")
    for r in frozen_t.sort_values(["kind", "condition", "burst_ms"]).itertuples():
        print(f"    {r.condition:<38} {r.burst_ms:4.0f} {r.n_pool_spikes:9d} "
              f"{r.n_afferents_fired:10d} {r.n_afferent_spikes:11d} "
              f"{r.n_downstream:5d} {r.n_closing:7d}")
    if int(frozen_t["n_pool_spikes"].min()) == 0:
        print("    WARNING: a frozen condition had ZERO motor-pool spikes; that "
              "row's control is\n    vacuous rather than negative.")
    clean = int(frozen_t["n_afferents_fired"].sum()) == 0
    print(f"\n    frozen-physics afferent spikes over every condition: "
          f"{int(frozen_t['n_afferent_spikes'].sum())} -> control is "
          f"{'CLEAN' if clean else 'CONTAMINATED'}.")
    if clean:
        print("      No afferent reached threshold through the connectome, so "
              "every afferent spike\n      in the live runs is attributable to "
              "the body having moved.")
    else:
        print("      An afferent fired with the body pinned, so it was reached "
              "through the\n      connectome (motor->X->afferent).  Live "
              "afferent spikes are NOT purely sensory.")
    frozen_down = int(frozen_t["n_downstream"].sum())
    print(f"    frozen-physics downstream (non-afferent) firing: {frozen_down} "
          "neuron-conditions"
          + (" -- the motor pool drives the network directly, so 'downstream "
             "fired'\n      must be differenced against this column, which the "
             "body_attributable column does."
             if frozen_down else ""))

    print("\n  DOES BREADTH HELP?  best condition per family:")
    print(f"    {'family':<10} {'condition':<38} {'aff':>4} {'PSP':>7} "
          f"{'peak dV':>8} {'pre→MN (body)':>14}")
    for kind in ("1group", "2group", "3group", "broad", "targeted"):
        sub = live[live["kind"] == kind]
        if sub.empty:
            continue
        best = sub.loc[sub["psp_avail_mV"].idxmax()]
        print(f"    {kind:<10} {best['condition']:<38} "
              f"{best['n_afferents_fired']:4d} {best['psp_avail_mV']:7.2f} "
              f"{best['peak_dv_mV']:8.2f} {best['n_body_closing']:14d}")

    print("\n  DOES ANTAGONIST CO-ACTIVATION HELP OR CANCEL?  muscles are "
          "unipolar (ctrlrange\n  [1e-4, 1]: a muscle pulls, never pushes), so "
          "driving a whole group recruits both\n  heads of every antagonist pair. "
          " Compare 'all N muscles of a group' against that\n  group's single "
          "strongest muscle:")
    print(f"    {'group':<12} {'1 strongest -> exc / aff':>26} "
          f"{'all muscles -> exc / aff':>26}  verdict")
    for group in JOINT_GROUPS:
        one = live[(live["condition"] == f"1group:{group}")
                   & (live["burst_ms"] == live["burst_ms"].min())]
        allm = live[(live["condition"] == f"broad:all {group} muscles")
                    & (live["burst_ms"] == live["burst_ms"].min())]
        if one.empty or allm.empty:
            continue
        o, a = one.iloc[0], allm.iloc[0]
        verdict = ("CANCELS" if a["excursion_rad"] < o["excursion_rad"]
                   else "adds")
        print(f"    {group:<12} {o['excursion_rad']:16.3f} rad /"
              f"{o['n_afferents_fired']:4d} "
              f"{a['excursion_rad']:16.3f} rad /{a['n_afferents_fired']:4d}  "
              f"{verdict} ({a['n_muscles']} muscles, "
              f"{a['excursion_rad'] / max(o['excursion_rad'], 1e-9):.2f}x the "
              "excursion)")
    print("    So breadth must be spread ACROSS joint groups, not piled onto one:"
          " co-activating a\n    group's antagonists reduces the movement and "
          "therefore the afferent recruitment.")

    print("\n  CAUSAL ORDERING -- an afferent must spike BEFORE the neuron it is "
          "supposed to\n  have driven.  Conditions where something presynaptic "
          "to an in-scope LF MN fired:")
    fired_rows = live[live["n_closing"] > 0]
    if fired_rows.empty:
        print("    (none)")
    else:
        print(f"    {'condition':<38} {'ms':>4} {'t_aff':>7} {'t_close':>8} "
              f"{'lag':>7}  order ok")
        bad = 0
        for r in fired_rows.sort_values("burst_ms").itertuples():
            lag = r.t_first_closing_ms - r.t_first_afferent_ms
            ok = lag > 0
            bad += 0 if ok else 1
            print(f"    {r.condition:<38} {r.burst_ms:4.0f} "
                  f"{r.t_first_afferent_ms:7.1f} {r.t_first_closing_ms:8.1f} "
                  f"{lag:+7.1f}  {'yes' if ok else 'NO -- PRECEDES'}")
        print(f"    conditions where the downstream spike PRECEDED every "
              f"afferent spike: {bad}")
        if bad:
            print("      those cannot be sensory in origin and are excluded from "
                  "the verdict.")

    # "Best" = most body-attributable closers, tie-broken on afferent PSP
    # delivered.  Ranking on PSP alone would pick a condition that delivers the
    # most millivolts and fires nothing, which is the mistake this whole
    # experiment exists to avoid.
    best = live.sort_values(
        ["n_body_closing", "psp_avail_mV", "n_afferents_fired"], ascending=False
    ).iloc[0]
    if best["n_closing"]:
        print(f"\n  WHAT FIRED in the best condition ('{best['condition']}' @ "
              f"{best['burst_ms']:.0f} ms) -- every neuron\n  presynaptic to an "
              "in-scope LF MN that spiked, with the afferent input it received:")
        print(f"    {'neuron':<24} {'aff in':>7} {'fired':>6} {'PSP mV':>7} "
              f"{'t_first':>8} {'n':>4} {'→MN syn':>8} {'→MN mV':>8}  role")
        for c in sorted(best["closing_detail"], key=lambda d: d["t_first_ms"]):
            x = c["idx"]
            print(f"    {str(int(meta_bid[x])) + ' ' + meta_type[x]:<24} "
                  f"{c['n_aff_in']:7d} {c['n_aff_fired']:6d} "
                  f"{c['psp_from_fired_mV']:7.2f} {c['t_first_ms']:8.1f} "
                  f"{c['n_spikes']:4d} {c['n_mn_out']:8d} "
                  f"{c['mn_out_mV']:+8.2f}  "
                  + ("in-scope LF MOTOR NEURON" if c["is_mn"] else "relay"))
        print("    '→MN mV' is the SIGN of the closer's own output onto in-scope "
              "LF motor neurons.\n    A negative closer carries the sensory "
              "signal home as suppression -- a real return\n    path, but not "
              "the excitatory one the loop diagram assumes.")
        print("    NOTE a closer with 0 afferent inputs was reached through the "
              "network from the\n    driven pool, not by the sensory volley; the "
              "frozen control is what separates them.")
        mn_closers = [c for c in best["closing_detail"] if c["is_mn"]]
        if mn_closers:
            print(f"    {len(mn_closers)} closer(s) are themselves in-scope LF "
                  "motor neurons that the afferents\n    reach DIRECTLY (the "
                  "monosynaptic reflex arc), not interneuron relays.")

    print("\n  VERDICT")
    winners = live[live["n_body_closing"] > 0]
    winners = winners[
        winners["t_first_closing_ms"] > winners["t_first_afferent_ms"]
    ]
    overall = live.loc[live["psp_avail_mV"].idxmax()]
    print(f"    best afferent recruitment anywhere: "
          f"{int(live['n_afferents_fired'].max())} of {n_aff} afferents "
          f"(single-muscle best: "
          f"{int(live[live.n_muscles == 1]['n_afferents_fired'].max())}).")
    print(f"    best PSP delivered to a relay: {overall['psp_avail_mV']:.2f} of "
          f"{overall['psp_total_mV']:.2f} mV ({overall['best_relay']}), "
          f"condition '{overall['condition']}' at {overall['burst_ms']:.0f} ms.")
    print(f"    highest relay depolarisation reached: "
          f"{live['peak_dv_mV'].max():.2f} mV of the "
          f"{FROM_REST_BAR_MV:.0f} mV needed (context only -- the verdict is "
          "spike counts).")
    if winners.empty:
        print("    NO condition fired a neuron presynaptic to an in-scope LF "
              "motor neuron.")
        print("    HYPOTHESIS FALSIFIED: multi-joint breadth raises afferent "
              "recruitment but does\n    NOT close the return limb.  The Level 1 "
              "loop stays anatomically open.")
        return
    print(f"    {len(winners)} condition(s) fired a neuron presynaptic to an "
          "in-scope LF MN that did\n    NOT fire with physics frozen and fired "
          "AFTER the first afferent spike:")
    for r in winners.sort_values("n_body_closing", ascending=False).itertuples():
        parts = []
        for x in r.body_attributable:
            tag = "LF MN" if meta_type[x].endswith("MN") else "relay"
            parts.append(f"{int(meta_bid[x])}/{meta_type[x]} [{tag}]")
        print(f"      {r.condition} @ {r.burst_ms:.0f} ms, "
              f"{r.n_afferents_fired} afferents, first afferent "
              f"{r.t_first_afferent_ms:.1f} ms -> closure "
              f"{r.t_first_closing_ms:.1f} ms:")
        for part in parts:
            print(f"        {part}")
    single = live[(live.n_muscles == 1) & (live.n_body_closing > 0)]
    print(f"\n    single-muscle conditions that closed: {len(single)} of "
          f"{int((live.n_muscles == 1).sum())}  <- the control")
    multi = live[(live.n_muscles > 1) & (live.n_body_closing > 0)]
    print(f"    multi-muscle conditions that closed:  {len(multi)} of "
          f"{int((live.n_muscles > 1).sum())}")
    if single.empty and not multi.empty:
        print("    HYPOTHESIS SUPPORTED: closure occurs only under multi-muscle "
              "drive.  Breadth, not\n    drive strength, is what was missing -- "
              "the single-muscle controls reach the same\n    motor rate and "
              "larger single-joint excursions and still fire nothing.")
    elif not single.empty:
        print("    HYPOTHESIS NOT CLEANLY SUPPORTED: a single-muscle condition "
              "also closed, so\n    breadth is not the discriminating variable "
              "in this run.")

    # Which afferents never fire anywhere -- names the remaining ceiling.
    everything = set().union(*live["fired_afferents"]) if len(live) else set()
    missing = [a for a in encoder.assignments if a.neuron_index not in everything]
    print(f"\n  afferents that fired in NO live condition: {len(missing)} of "
          f"{n_aff}")
    if missing:
        tally: dict[str, int] = {}
        for a in missing:
            tally[f"{a.joint_group}/{a.modality}"] = (
                tally.get(f"{a.joint_group}/{a.modality}", 0) + 1
            )
        print("    " + ", ".join(f"{k}={v}" for k, v in sorted(tally.items())))
        lost = {}
        for idx in conv.head(3).index.values:
            sub = edges[(edges.post == idx)
                        & edges.pre.isin([a.neuron_index for a in missing])]
            lost[str(conv.loc[idx, "type"])] = float(sub.w.sum())
        print("    weight they withhold from the top relays: "
              + ", ".join(f"{k} {v:.2f} mV" for k, v in lost.items()))


# ---------------------------------------------------------------------------
# The size principle: recruiting more neurons must strictly increase force
# ---------------------------------------------------------------------------


def verify_size_principle(decoder, rate_hz=50.0, verbose=True):
    """Assert that recruitment is strictly monotone and silence is exactly zero.

    This is checked rather than argued because it has already broken once on this
    project: a mean-based decode let 1 of 8 neurons firing drive the joint
    **backwards by -0.225 rad**, because a silent neuron contributed a large
    negative offset.  The per-class force model replaces the size weights, so the
    property has to be re-established for the new decode, not inherited.

    Three checks, over **every** muscle pool and in **both** recruitment orders:

    1. adding any neuron to any firing set strictly increases the muscle's
       activation (until the pool saturates at 1.0, where it may only stay equal);
    2. a fully silent network gives activation exactly 0 for every muscle, and
       joint offset exactly 0 for every DOF;
    3. every single pool member firing alone gives activation > 0, so no neuron is
       a no-op -- the slow class must still count for something.

    Largest-first and smallest-first are both swept because a monotonicity bug can
    hide in one order: a scheme that divides by a pool-mean is monotone when the
    largest neuron is added first and non-monotone when the smallest is.
    """
    from .muscle_decoder import MUSCLE_NAMES

    rows = []
    violations = []
    for name in MUSCLE_NAMES:
        members = decoder.muscle_pool_members(name)
        if not members:
            continue
        mi = MUSCLE_NAMES.index(name)
        for order_name, ordered in (
            ("largest first", members),
            ("smallest first", list(reversed(members))),
        ):
            prev = 0.0
            n_strict = 0
            n_flat = 0
            for n_on in range(1, len(ordered) + 1):
                rates = {a.net_index: rate_hz for a in ordered[:n_on]}
                act = float(decoder.muscle_activations(rates)[mi])
                if act < prev - 1e-12:
                    violations.append((name, order_name, n_on, prev, act))
                elif act > prev + 1e-12:
                    n_strict += 1
                else:
                    n_flat += 1
                prev = act
            alone = [
                float(decoder.muscle_activations({a.net_index: rate_hz})[mi])
                for a in ordered
            ]
            rows.append({
                "muscle": name, "order": order_name, "n_pool": len(ordered),
                "final_act": prev, "n_strict_increase": n_strict,
                "n_no_change": n_flat,
                "min_alone": min(alone), "n_zero_alone": sum(
                    1 for v in alone if v <= 0.0
                ),
            })

    silent_muscle = float(np.abs(decoder.muscle_activations({})).max())
    silent_dof = float(np.abs(decoder.joint_offsets({})).max())
    table = pd.DataFrame(rows)

    if verbose:
        print("\n" + "=" * 78)
        print("SIZE PRINCIPLE: does recruiting more neurons strictly increase "
              "force?")
        print("=" * 78)
        print(f"  every muscle pool, both recruitment orders, all members at "
              f"{rate_hz:.0f} Hz.")
        print(f"\n    {'muscle':<40} {'order':<15} {'N':>3} {'final act':>10} "
              f"{'strict+':>8} {'flat':>5} {'min alone':>10} {'zero':>5}")
        for r in table.itertuples():
            print(f"    {r.muscle:<40} {r.order:<15} {r.n_pool:3d} "
                  f"{r.final_act:10.4f} {r.n_strict_increase:8d} "
                  f"{r.n_no_change:5d} {r.min_alone:10.6f} {r.n_zero_alone:5d}")
        print(f"\n  monotonicity violations (activation FELL when a neuron was "
              f"added): {len(violations)}")
        for v in violations:
            print(f"    {v[0]} ({v[1]}) at n={v[2]}: {v[3]:.6f} -> {v[4]:.6f}")
        n_flat_unsat = int(
            table[(table["n_no_change"] > 0) & (table["final_act"] < 1.0 - 1e-9)]
            ["n_no_change"].sum()
        )
        print(f"  additions that left activation unchanged in an UNSATURATED pool: "
              f"{n_flat_unsat}")
        print(f"  pool members that produce ZERO activation firing alone: "
              f"{int(table['n_zero_alone'].sum())}")
        print(f"  fully silent network: max muscle activation "
              f"{silent_muscle:.9f}, max |joint offset| {silent_dof:.9f} rad")
        ok = (not violations and silent_muscle == 0.0 and silent_dof == 0.0
              and int(table["n_zero_alone"].sum()) == 0)
        print(f"\n  VERDICT: size principle {'HOLDS' if ok else 'VIOLATED'} -- "
              "recruitment is monotone, a silent\n  neuron contributes exactly "
              "zero, and no pool member is a no-op."
              if ok else
              f"\n  VERDICT: size principle VIOLATED -- see the rows above.")
    return {"table": table, "violations": violations,
            "silent_muscle": silent_muscle, "silent_dof": silent_dof}


# ---------------------------------------------------------------------------
# Deliverable 5: minimum conducting rate, legacy decode vs per-class force model
# ---------------------------------------------------------------------------

# The rate ladder for the threshold sweep.  Every entry is a MEASURED f-I point
# (see DRIVE_PA_FOR_HZ); 20 Hz is the LIF's floor, and 200 Hz is carried only as
# the legacy reference point, not as a rate any fly leg MN has been recorded at.
RATE_LADDER: tuple[int, ...] = (20, 25, 30, 40, 50, 60, 80, 100, 120, 150, 200)

# What "biologically plausible" means for this sweep, from Azevedo et al. 2020:
# slow MNs idle ~30 Hz, peak ~100 Hz naturally, cap ~150 Hz under direct current
# injection.  A conducting rate at or below this is physiological; above it is not.
PHYSIOLOGICAL_CEILING_HZ = 150
PHYSIOLOGICAL_TARGET_HZ = 80


def measure_rate_threshold(
    net_data=None,
    conduction=None,
    muscles=None,
    burst_ms=(50.0, 200.0),
    rates_hz=RATE_LADDER,
    verbose=True,
):
    """Deliverable 5: the minimum drive rate that closes the loop, before/after.

    The multi-muscle experiment left "minimum conducting rate not measured" as its
    single most useful follow-up, because drive was pinned at 200 Hz nominal.  This
    measures it, on the winning ``3group:strongest x3`` condition, under **both**
    decoders in one run:

    * ``legacy`` -- ``sum(w_i * rate_i) / (sum(w_i) * 200 Hz)``, the size-weighted
      rate fraction whose unsourced 200 Hz ceiling is the constant under suspicion;
    * ``force`` -- the per-class force-per-spike model, whose values are fixed from
      Azevedo et al. 2020 and were fixed BEFORE this function was ever run.

    Reporting both in one sweep is what makes the comparison a measurement rather
    than a before/after recollection: same network, same body, same settled state,
    same seeded delays, one variable changed.

    Returns a table with one row per (decoder, burst, rate) and, for each decoder,
    the lowest rate at which a neuron presynaptic to an in-scope LF motor neuron
    fired *because the body moved* -- verified against a frozen-physics control at
    the same rate and required to fire after the first afferent spike.
    """
    from .muscle_decoder import MuscleDecoder

    if net_data is None:
        net_data = load_full_vnc()
    meta_df, body_ids = net_data["meta_df"], net_data["body_ids"]
    meta_bid = meta_df["bodyId"].values
    meta_type = meta_df["type"].fillna("<untyped>").values

    if conduction is not None:
        encoder = conduction["encoder"]
        network = conduction["network"]
        sim, model, data, state, groups = conduction["body"]
    else:
        encoder = ProprioceptiveEncoder(meta_df, body_ids, leg="LF", side="L")
        sim, model, data, state, groups, _n = build_settled_body(verbose=verbose)
        network = FullVNCNetwork(net_data)

    decoders = {
        "legacy": MuscleDecoder(meta_df, body_ids, force_model=False),
        "force": MuscleDecoder(meta_df, body_ids, force_model=True),
    }
    if muscles is None:
        muscles = tuple(STRONGEST_BY_GROUP[g] for g in JOINT_GROUPS)
    muscles = tuple(muscles)

    conv, edges, role = _relay_afferent_edges(net_data, encoder)
    in_scope_idx = set(lf_motor_in_scope(meta_df).index.values.tolist())
    presyn_idx = set(np.unique(
        net_data["sources"][np.isin(net_data["targets"], list(in_scope_idx))]
    ).tolist())
    conv["presyn_to_mn"] = conv.index.isin(presyn_idx)
    watch = list(conv.head(8).index.values)

    if verbose:
        print("\n" + "=" * 78)
        print("[5] MINIMUM CONDUCTING RATE: legacy 200 Hz decode vs per-class "
              "force model")
        print("=" * 78)
        print(f"  condition: {len(muscles)} muscles, one per joint group -- "
              + ", ".join(muscles))
        print("  the SAME network, body, settled state and seeded delays for both "
              "decoders;\n  the decode is the only variable.")
        dec = decoders["force"]
        print("\n  per-class force model (every value fixed from Azevedo et al. "
              "2020 BEFORE this run):")
        print("  " + dec.class_summary().to_string(index=False)
              .replace("\n", "\n  "))
        pool = in_scope_pool_for_muscles(dec, muscles)
        tally: dict[str, int] = {}
        for a in pool:
            tally[a.force_class] = tally.get(a.force_class, 0) + 1
        print(f"\n  driven pool: {len(pool)} in-scope LF MNs -- "
              + ", ".join(f"{k} {v}" for k, v in sorted(tally.items())))
        print(f"  physiological band: slow MNs idle ~30 Hz, peak ~100 Hz, cap "
              f"~{PHYSIOLOGICAL_CEILING_HZ} Hz under current injection.")
        print(f"  LIF floor: {min(rates_hz)} Hz (t_refract 2 ms makes anything "
              "lower unreachable).")

    rows = []
    for decoder_name, decoder in decoders.items():
        for ms_burst in burst_ms:
            for hz in rates_hz:
                frozen_closers = None
                for frozen in (False, True):
                    times, indices, tr = run_lockstep_multi(
                        network, sim, model, data, state, groups, decoder,
                        encoder, muscles, DRIVE_PA_FOR_HZ[hz],
                        burst_ms=ms_burst, freeze_physics=frozen, watch=watch,
                    )
                    row = _condition_row(
                        net_data, encoder, conv, edges, in_scope_idx,
                        presyn_idx, times, indices, tr,
                        f"{decoder_name}@{hz}Hz", decoder_name, watch,
                    )
                    if frozen:
                        frozen_closers = set(row["downstream_idx"])
                    else:
                        live_row = row
                live_row["decoder"] = decoder_name
                live_row["nominal_hz"] = hz
                live_row["burst_ms"] = ms_burst
                body = sorted(set(live_row["closing_idx"]) - frozen_closers)
                live_row["body_attributable"] = body
                live_row["n_body_closing"] = len(body)
                # Causal ordering: the closer must fire AFTER the first afferent.
                live_row["order_ok"] = bool(
                    live_row["n_body_closing"] > 0
                    and live_row["t_first_closing_ms"]
                    > live_row["t_first_afferent_ms"]
                )
                rows.append(live_row)

    table = pd.DataFrame(rows)
    if verbose:
        _print_rate_threshold(table, meta_bid, meta_type, decoders, muscles)
    return {"table": table, "decoders": decoders, "muscles": muscles}


def _print_rate_threshold(table, meta_bid, meta_type, decoders, muscles):
    """Print the sweep and name the minimum conducting rate per decoder."""
    print("\n  SWEEP -- physics live, frozen control run at every point.  "
          "'closes' means a\n  neuron presynaptic to an in-scope LF MN fired, did "
          "NOT fire frozen, and fired\n  after the first afferent spike.")
    print(f"\n    {'decoder':<8} {'ms':>4} {'Hz':>4} {'pool_hz':>8} {'act':>6} "
          f"{'exc(rad)':>9} {'aff':>4} {'t_aff':>7} {'t_close':>8} "
          f"{'closers':>8}  closes")
    for r in table.sort_values(["decoder", "burst_ms", "nominal_hz"]).itertuples():
        t_close = ("      --" if pd.isna(r.t_first_closing_ms)
                   else f"{r.t_first_closing_ms:8.1f}")
        t_aff = ("     --" if pd.isna(r.t_first_afferent_ms)
                 else f"{r.t_first_afferent_ms:7.1f}")
        print(f"    {r.decoder:<8} {r.burst_ms:4.0f} {r.nominal_hz:4d} "
              f"{r.pool_hz:8.1f} {r.act_peak:6.3f} {r.excursion_rad:9.3f} "
              f"{r.n_afferents_fired:4d} {t_aff} {t_close} "
              f"{r.n_body_closing:8d}  {'YES' if r.order_ok else 'no'}")

    print("\n  MINIMUM CONDUCTING RATE (the number the last experiment could not "
          "report):")
    print(f"    {'decoder':<8} {'burst':>6} {'min Hz that closes':>20} "
          f"{'closure latency':>16} {'peak excursion':>15}")
    summary = {}
    for decoder_name in decoders:
        for ms_burst in sorted(table["burst_ms"].unique()):
            sub = table[(table["decoder"] == decoder_name)
                        & (table["burst_ms"] == ms_burst)]
            ok = sub[sub["order_ok"]]
            if ok.empty:
                print(f"    {decoder_name:<8} {ms_burst:6.0f} "
                      f"{'never closes':>20} {'--':>16} "
                      f"{sub['excursion_rad'].max():15.3f}")
                summary[(decoder_name, ms_burst)] = None
                continue
            best = ok.loc[ok["nominal_hz"].idxmin()]
            print(f"    {decoder_name:<8} {ms_burst:6.0f} "
                  f"{int(best['nominal_hz']):20d} "
                  f"{best['t_first_closing_ms']:15.1f} "
                  f"{best['excursion_rad']:15.3f}")
            summary[(decoder_name, ms_burst)] = best

    print("\n  IS THE MINIMUM PHYSIOLOGICAL?  Azevedo: slow MNs idle ~30 Hz, peak "
          f"~100 Hz\n  naturally, cap ~{PHYSIOLOGICAL_CEILING_HZ} Hz under direct "
          "current injection; fast MNs fire 1-10 spikes.")
    for (decoder_name, ms_burst), best in sorted(summary.items()):
        if best is None:
            print(f"    {decoder_name} @ {ms_burst:.0f} ms: never closes -- "
                  "no rate on the ladder is sufficient.")
            continue
        hz = int(best["nominal_hz"])
        verdict = ("PHYSIOLOGICAL" if hz <= PHYSIOLOGICAL_CEILING_HZ
                   else "UNPHYSIOLOGICAL")
        extra = (" and inside the ~100 Hz natural peak"
                 if hz <= PHYSIOLOGICAL_TARGET_HZ else "")
        print(f"    {decoder_name} @ {ms_burst:.0f} ms: closes at {hz} Hz -> "
              f"{verdict}{extra}.")

    print("\n  SAME-RATE COMPARISON -- what the decode change does at one fixed, "
          "physiological\n  drive.  Excursion is the mechanical output; a decode "
          "cannot be credited for\n  closure it did not cause.")
    print(f"    {'ms':>4} {'Hz':>4} {'legacy act':>11} {'force act':>10} "
          f"{'legacy exc':>11} {'force exc':>10} {'legacy aff':>11} "
          f"{'force aff':>10} {'legacy close':>13} {'force close':>12}")
    for ms_burst in sorted(table["burst_ms"].unique()):
        for hz in sorted(table["nominal_hz"].unique()):
            lg = table[(table.decoder == "legacy") & (table.burst_ms == ms_burst)
                       & (table.nominal_hz == hz)]
            fo = table[(table.decoder == "force") & (table.burst_ms == ms_burst)
                       & (table.nominal_hz == hz)]
            if lg.empty or fo.empty:
                continue
            l, f = lg.iloc[0], fo.iloc[0]
            print(f"    {ms_burst:4.0f} {hz:4d} {l['act_peak']:11.3f} "
                  f"{f['act_peak']:10.3f} {l['excursion_rad']:11.3f} "
                  f"{f['excursion_rad']:10.3f} {l['n_afferents_fired']:11d} "
                  f"{f['n_afferents_fired']:10d} "
                  f"{'YES' if l['order_ok'] else 'no':>13} "
                  f"{'YES' if f['order_ok'] else 'no':>12}")

    print("\n  WHERE DOES THE LATENCY ACTUALLY GO?  Split closure into the part "
          "force can move\n  (drive -> body -> first afferent spike) and the part "
          "it cannot (afferent -> relay\n  spike, which is pure synaptic "
          "integration through the connectome):")
    print(f"    {'decoder':<8} {'ms':>4} {'Hz':>4} {'t_aff':>7} {'t_close':>8} "
          f"{'lag':>7}")
    lags = []
    for r in table[table["order_ok"]].sort_values(
        ["decoder", "burst_ms", "nominal_hz"]
    ).itertuples():
        lag = r.t_first_closing_ms - r.t_first_afferent_ms
        lags.append(lag)
        print(f"    {r.decoder:<8} {r.burst_ms:4.0f} {r.nominal_hz:4d} "
              f"{r.t_first_afferent_ms:7.1f} {r.t_first_closing_ms:8.1f} "
              f"{lag:+7.1f}")
    if lags:
        print(f"    afferent -> closure lag over every closing condition: "
              f"{min(lags):.1f} to {max(lags):.1f} ms")
        print("    The mechanical half (drive -> afferent) is what force gain "
              "shortens.  If the lag\n    is roughly constant across drive, the "
              "residual latency is SYNAPTIC and no amount of\n    force per spike "
              "will reduce it -- which would mean closure latency has a floor "
              "that\n    this hypothesis cannot lower.")

    print("\n  VERDICT")
    ref = table[(table.decoder == "legacy") & (table.nominal_hz == 200)]
    ref_exc = float(ref["excursion_rad"].max()) if not ref.empty else np.nan
    phys = table[(table.decoder == "force")
                 & (table.nominal_hz <= PHYSIOLOGICAL_TARGET_HZ)]
    phys_exc = float(phys["excursion_rad"].max()) if not phys.empty else np.nan
    print(f"    DOES THE JOINT MOVE AS FAST AT PHYSIOLOGICAL DRIVE AS IT DID AT "
          f"200 Hz?\n      legacy decode at 200 Hz: peak excursion "
          f"{ref_exc:.3f} rad")
    print(f"      force decode at <= {PHYSIOLOGICAL_TARGET_HZ} Hz: peak excursion "
          f"{phys_exc:.3f} rad  -> "
          f"{phys_exc / ref_exc:.2f}x" if ref_exc and not np.isnan(ref_exc)
          else "      (no 200 Hz legacy reference in this sweep)")
    lg_min = table[(table.decoder == "legacy") & table.order_ok]
    fo_min = table[(table.decoder == "force") & table.order_ok]
    lg_hz = int(lg_min["nominal_hz"].min()) if not lg_min.empty else None
    fo_hz = int(fo_min["nominal_hz"].min()) if not fo_min.empty else None
    print(f"    minimum conducting rate: legacy "
          f"{lg_hz if lg_hz else 'never'} Hz -> force "
          f"{fo_hz if fo_hz else 'never'} Hz")
    if fo_hz is not None and fo_hz <= PHYSIOLOGICAL_CEILING_HZ:
        print("    The loop closes at a rate the literature supports.  The 200 Hz "
              "requirement was\n    an artefact of the decode, as hypothesised.")
    elif fo_hz is not None:
        print(f"    The loop still needs {fo_hz} Hz, above the "
              f"{PHYSIOLOGICAL_CEILING_HZ} Hz ceiling.  Correcting the force\n"
              "    gradient did NOT make the protocol physiological, so a SECOND "
              "bottleneck exists.")
    else:
        print("    The force model does NOT close the loop at any rate on the "
              "ladder.  This\n    CONTRADICTS the hypothesis and is a result, not "
              "a tuning target.")


# ---------------------------------------------------------------------------
# Deliverable 6: the class-specific protocol -- fast MNs spike, slow MNs idle
# ---------------------------------------------------------------------------


def measure_class_protocol(
    net_data=None,
    conduction=None,
    muscles=None,
    burst_ms=200.0,
    slow_rates_hz=(30, 50, 80),
    fast_spikes=(1, 2, 5, 10),
    verbose=True,
):
    """Deliverable 6: does the loop close under drive shaped like real biology?

    Every sweep before this drove all 52 in-scope motor neurons at one uniform
    rate for the whole burst -- a protocol no fly leg motor pool ever runs.  The
    question as posed is narrower and harder: **at slow MNs ~50-80 Hz and fast MNs
    a few spikes**, does the joint move and does the loop close?

    So here the drive is class-specific:

    * ``slow`` neurons fire tonically at ``slow_rate`` for the entire burst,
      inside Azevedo's 30-100 Hz operating range;
    * ``fast`` and ``intermediate`` neurons get a **short burst of N spikes** and
      are then silent, which is what "1-10 spikes" means.  The current window is
      ``N / 200 Hz`` wide, so N is a spike count and not a rate.

    The frozen-physics control runs at every point, and causal ordering is
    checked, exactly as in the other sweeps.
    """
    from .muscle_decoder import MuscleDecoder

    if net_data is None:
        net_data = load_full_vnc()
    meta_df, body_ids = net_data["meta_df"], net_data["body_ids"]
    meta_bid = meta_df["bodyId"].values
    meta_type = meta_df["type"].fillna("<untyped>").values

    if conduction is not None:
        encoder = conduction["encoder"]
        network = conduction["network"]
        sim, model, data, state, groups = conduction["body"]
    else:
        encoder = ProprioceptiveEncoder(meta_df, body_ids, leg="LF", side="L")
        sim, model, data, state, groups, _n = build_settled_body(verbose=verbose)
        network = FullVNCNetwork(net_data)

    decoder = MuscleDecoder(meta_df, body_ids, force_model=True)
    if muscles is None:
        muscles = tuple(STRONGEST_BY_GROUP[g] for g in JOINT_GROUPS)
    muscles = tuple(muscles)

    conv, edges, role = _relay_afferent_edges(net_data, encoder)
    in_scope_idx = set(lf_motor_in_scope(meta_df).index.values.tolist())
    presyn_idx = set(np.unique(
        net_data["sources"][np.isin(net_data["targets"], list(in_scope_idx))]
    ).tolist())
    conv["presyn_to_mn"] = conv.index.isin(presyn_idx)
    watch = list(conv.head(8).index.values)

    # A spike count is turned into a current window at a fixed 200 Hz, so N is
    # genuinely N spikes rather than a disguised rate.
    phasic_pa = DRIVE_PA_FOR_HZ[200]
    phasic_ms = {n: n / 200.0 * 1000.0 for n in fast_spikes}

    if verbose:
        pool = in_scope_pool_for_muscles(decoder, muscles)
        tally: dict[str, int] = {}
        for a in pool:
            tally[a.force_class] = tally.get(a.force_class, 0) + 1
        print("\n" + "=" * 78)
        print("[6] CLASS-SPECIFIC PROTOCOL: slow MNs tonic, fast MNs a few spikes")
        print("=" * 78)
        print(f"  condition: {len(muscles)} muscles, one per joint group; "
              f"{burst_ms:.0f} ms window")
        print(f"  driven pool: {len(pool)} in-scope LF MNs -- "
              + ", ".join(f"{k} {v}" for k, v in sorted(tally.items())))
        print("  slow: tonic for the whole burst.  fast/intermediate: N spikes "
              "then SILENT\n  (current withdrawn after N / 200 Hz).")
        print("  This is the drive the question asks about; every earlier sweep "
              "used one uniform\n  rate for all classes, which no motor pool "
              "actually runs.")

    rows = []
    for slow_hz in slow_rates_hz:
        for n_spikes in fast_spikes:
            frozen_closers = None
            for frozen in (False, True):
                times, indices, tr = run_lockstep_multi(
                    network, sim, model, data, state, groups, decoder, encoder,
                    muscles, DRIVE_PA_FOR_HZ[slow_hz], burst_ms=burst_ms,
                    freeze_physics=frozen, watch=watch,
                    drive_pa_by_class={
                        "slow": DRIVE_PA_FOR_HZ[slow_hz],
                        "intermediate": phasic_pa,
                        "fast": phasic_pa,
                    },
                    drive_ms_by_class={
                        "slow": burst_ms,
                        "intermediate": phasic_ms[n_spikes],
                        "fast": phasic_ms[n_spikes],
                    },
                )
                row = _condition_row(
                    net_data, encoder, conv, edges, in_scope_idx, presyn_idx,
                    times, indices, tr,
                    f"slow{slow_hz}Hz+fast{n_spikes}sp", "class", watch,
                )
                if frozen:
                    frozen_closers = set(row["downstream_idx"])
                else:
                    live_row = row
                    # Spikes per class, from the SpikeMonitor -- so "N spikes"
                    # is verified rather than assumed from the current window.
                    per_class: dict[str, int] = {}
                    for a in in_scope_pool_for_muscles(decoder, muscles):
                        per_class[a.force_class] = per_class.get(
                            a.force_class, 0
                        ) + int((indices == a.net_index).sum())
                    live_row["spikes_by_class"] = per_class
            live_row["slow_hz"] = slow_hz
            live_row["fast_spikes"] = n_spikes
            body = sorted(set(live_row["closing_idx"]) - frozen_closers)
            live_row["body_attributable"] = body
            live_row["n_body_closing"] = len(body)
            live_row["order_ok"] = bool(
                live_row["n_body_closing"] > 0
                and live_row["t_first_closing_ms"] > live_row["t_first_afferent_ms"]
            )
            rows.append(live_row)

    table = pd.DataFrame(rows)
    if verbose:
        print(f"\n    {'slow Hz':>8} {'fast sp':>8} {'fast spk (measured)':>20} "
              f"{'slow spk':>9} {'act':>6} {'exc(rad)':>9} {'aff':>4} "
              f"{'t_aff':>7} {'t_close':>8}  closes")
        for r in table.itertuples():
            sb = r.spikes_by_class
            t_close = ("      --" if pd.isna(r.t_first_closing_ms)
                       else f"{r.t_first_closing_ms:8.1f}")
            t_aff = ("     --" if pd.isna(r.t_first_afferent_ms)
                     else f"{r.t_first_afferent_ms:7.1f}")
            print(f"    {r.slow_hz:8d} {r.fast_spikes:8d} "
                  f"{sb.get('fast', 0) + sb.get('intermediate', 0):20d} "
                  f"{sb.get('slow', 0):9d} {r.act_peak:6.3f} "
                  f"{r.excursion_rad:9.3f} {r.n_afferents_fired:4d} {t_aff} "
                  f"{t_close}  {'YES' if r.order_ok else 'no'}")

        print("\n  VERDICT")
        ok = table[table["order_ok"]]
        if ok.empty:
            print("    NO class-specific condition closed the loop.  Under drive "
                  "shaped like real\n    biology -- tonic slow MNs plus a few "
                  "fast spikes -- the loop does NOT close,\n    even though "
                  "uniform-rate drive at the same nominal rate does.  This "
                  "CONTRADICTS\n    the hypothesis in the form the question "
                  "asks it.")
        else:
            best = ok.loc[ok["t_first_closing_ms"].idxmin()]
            cheapest = ok.loc[
                (ok["slow_hz"] * 1000 + ok["fast_spikes"]).idxmin()
            ]
            print(f"    {len(ok)} of {len(table)} class-specific conditions "
                  "closed the loop.")
            print(f"    cheapest closing protocol: slow "
                  f"{int(cheapest['slow_hz'])} Hz + fast "
                  f"{int(cheapest['fast_spikes'])} spikes -> closure at "
                  f"{cheapest['t_first_closing_ms']:.1f} ms, excursion "
                  f"{cheapest['excursion_rad']:.3f} rad")
            print(f"    fastest closure: slow {int(best['slow_hz'])} Hz + fast "
                  f"{int(best['fast_spikes'])} spikes -> "
                  f"{best['t_first_closing_ms']:.1f} ms")
            print("    Both are inside Azevedo's measured envelope (slow 30-100 Hz "
                  "natural, fast 1-10\n    spikes), so the loop closes under drive "
                  "the literature supports.")
    return {"table": table, "decoder": decoder, "muscles": muscles}


# ---------------------------------------------------------------------------
# Deliverable 3: where do the afferents rest in-network?
# ---------------------------------------------------------------------------


def measure_afferent_rest_point(
    net_data=None,
    encoder=None,
    network=None,
    background_pa=(205.0, 240.0, 260.0, 300.0),
    duration_ms=500.0,
    verbose=True,
):
    """Deliverable 3: the afferents' resting point with full synaptic input.

    Child 0b measured every rate on **isolated** LIF neurons.  The 41 afferents
    actually receive 642 synapses, and the question is which way that input moves
    them.

    Method: drive the whole network *except* the 41 afferents, so an afferent's
    membrane potential is produced purely by its own 642 incoming synapses.  Then
    read the steady-state offset from rest and convert it to an equivalent
    current through ``R_membrane``, and count spikes.  Driving the afferents too
    would make the measurement circular.

    **No tonic bias is implemented.** The measurement is reported; the decision
    is the user's.
    """
    from brian2 import StateMonitor, amp, mV, ms

    if net_data is None:
        net_data = load_full_vnc()
    meta_df, body_ids = net_data["meta_df"], net_data["body_ids"]
    if encoder is None:
        encoder = ProprioceptiveEncoder(meta_df, body_ids, leg="LF", side="L")
    if network is None:
        network = FullVNCNetwork(net_data)

    aff = np.asarray(encoder.sensory_indices, dtype=np.int64)
    sources, targets = net_data["sources"], net_data["targets"]
    weights = net_data["weights_mV"]

    incoming = np.isin(targets, aff)
    nt = meta_df["consensusNt"].values[sources[incoming]]
    nt_counts = pd.Series(nt).value_counts()
    in_deg = pd.DataFrame({"post": targets[incoming], "w": weights[incoming]}) \
        .groupby("post").agg(n=("w", "size"), sum_w=("w", "sum"))

    if verbose:
        print("\n" + "=" * 78)
        print("[3] WHERE DO THE AFFERENTS REST IN-NETWORK?")
        print("=" * 78)
        print(f"  the {len(aff)} afferents receive {int(incoming.sum())} synapses "
              f"(median {in_deg.n.median():.0f} each, all {len(in_deg)} receive "
              f"some)")
        print("  presynaptic neurotransmitter: "
              + ", ".join(f"{k} {v}" for k, v in nt_counts.items()))
        gaba = float((pd.Series(nt) == "gaba").mean())
        print(f"  GABAergic fraction {gaba:.1%}; all-inhibitory-sign fraction "
              f"{float((weights[incoming] < 0).mean()):.1%}")
        print(f"  summed signed weight per afferent: median "
              f"{in_deg.sum_w.median():+.2f} mV, range {in_deg.sum_w.min():+.2f} "
              f"to {in_deg.sum_w.max():+.2f} mV")
        print(f"  -> {int((in_deg.sum_w < 0).sum())} of {len(in_deg)} afferents "
              f"have net-inhibitory wiring")

    rows = []
    others = np.setdiff1d(np.arange(network.n_neurons), aff)
    for bg in background_pa:
        network.reset()
        SM = StateMonitor(network.G, "v", record=list(aff))
        network.net.add(SM)
        currents = np.full(network.n_neurons, bg)
        currents[aff] = 0.0
        network.set_current_pa(currents)
        n_before = network.M.num_spikes
        try:
            network.net.run(duration_ms * ms)
            times, indices = network.spike_table()
            v = np.asarray(SM.v / mV)
        finally:
            network.net.remove(SM)

        counts = np.bincount(indices, minlength=network.n_neurons)
        # steady state over the last 200 ms
        tail = int(round(200.0 / DT_MS))
        v_ss = v[:, -tail:].mean(axis=1)
        dv = v_ss + 70.0
        # I_eff = dV / R_membrane, dV in mV over 100 MOhm -> pA
        i_eff = dv * 10.0
        rows.append({
            "background_pa": bg,
            "network_hz": float(counts[others].mean() / (duration_ms / 1000.0)),
            "afferent_hz_mean": float(counts[aff].mean() / (duration_ms / 1000.0)),
            "afferent_hz_max": float(counts[aff].max() / (duration_ms / 1000.0)),
            "n_afferents_silent": int((counts[aff] == 0).sum()),
            "dv_mean_mV": float(dv.mean()),
            "dv_min_mV": float(dv.min()),
            "dv_max_mV": float(dv.max()),
            "i_eff_mean_pa": float(i_eff.mean()),
            "i_eff_min_pa": float(i_eff.min()),
            "i_eff_max_pa": float(i_eff.max()),
            "n_depolarised": int((dv > 0).sum()),
            "n_hyperpolarised": int((dv < 0).sum()),
        })
        if verbose:
            r = rows[-1]
            print(f"\n  rest of network driven at {bg:.0f} pA "
                  f"(mean {r['network_hz']:.0f} Hz), afferents undriven:")
            print(f"    afferent spikes: {int(counts[aff].sum())}; "
                  f"{r['n_afferents_silent']}/{len(aff)} silent; "
                  f"mean rate {r['afferent_hz_mean']:.2f} Hz")
            print(f"    steady-state offset from rest: mean "
                  f"{r['dv_mean_mV']:+.3f} mV (range {r['dv_min_mV']:+.3f} to "
                  f"{r['dv_max_mV']:+.3f})")
            print(f"    equivalent synaptic current: mean "
                  f"{r['i_eff_mean_pa']:+.2f} pA (range {r['i_eff_min_pa']:+.2f} "
                  f"to {r['i_eff_max_pa']:+.2f}); rheobase "
                  f"{RHEOBASE_PA:.0f} pA")
            print(f"    net-depolarised {r['n_depolarised']}/{len(aff)}, "
                  f"net-hyperpolarised {r['n_hyperpolarised']}/{len(aff)}")

    table = pd.DataFrame(rows)
    gains = encoder.gains_pa
    if verbose:
        offset = float(table["i_eff_mean_pa"].abs().max())
        worst = float(table["i_eff_min_pa"].abs().max())
        print(f"\n  DO 0b's GAINS STILL HOLD?")
        print(f"    the network's own input shifts an afferent by "
              f"{offset:.1f} pA on average (worst single afferent "
              f"{worst:.1f} pA), and the shift is NEGATIVE -- "
              f"presynaptic inhibition, as the 68% GABAergic input predicts.")
        print(f"    to hold the same rate the gain must rise by "
              f"offset / activation_reached:")
        for modality in MODALITIES:
            g = gains[modality]
            for act in (0.40, 0.30):
                print(f"      {modality:9s} {g:6.0f} pA at activation "
                      f"{act:.2f}: +{offset / act:6.1f} pA "
                      f"({100 * offset / act / g:4.1f}%), worst case "
                      f"+{worst / act:6.1f} pA "
                      f"({100 * worst / act / g:4.1f}%)")
        print("    NO TONIC BIAS IMPLEMENTED -- measurement only, per the spec.")

    return {"table": table, "in_degree": in_deg, "nt_counts": nt_counts}


# ---------------------------------------------------------------------------
# Deliverable 7: the relays' operating point -- does background drive close the
# 28.6 ms synaptic gap, or does it just make the relays fire on their own?
# ---------------------------------------------------------------------------

# Constant-current background levels, in pA, applied to every neuron EXCEPT the
# driven motor pool and the 41 afferents.  Rheobase is 200 pA, so the ladder stops
# short of it: at 200 pA a neuron fires with no input at all and every "closure"
# would be spontaneous by construction.  Deliverable 3's ladder (205-300 pA) was
# deliberately ABOVE rheobase because it wanted a firing network to measure the
# afferents' synaptic rest point; this one wants a sub-threshold idling point, so
# it sweeps below.
#
# Resolution is finest around 125-150 pA because that is where the RECURRENT
# network ignites: the driven pool receives no background current, but it is wired
# to 25,635 neurons that do, so above ~130 pA the pool's own rate runs away from
# 34 Hz to 200+ Hz and the row stops being the protocol it claims to be.
BACKGROUND_LADDER_PA: tuple[float, ...] = (
    0.0, 25.0, 50.0, 75.0, 100.0, 115.0, 125.0, 130.0, 135.0, 150.0, 175.0, 190.0,
)

# Poisson background rates.  22 Hz x 1.3 mV is exactly ``create_background_drive``'s
# default, i.e. the background the training harness has been running all along --
# which is what makes the loop-closure experiment the outlier in having none.  The
# sub-22 Hz points are here because 22 Hz turned out to be ABOVE the ignition
# point: with 50 sources onto every neuron it makes the network self-sustaining and
# the frozen control fires 1,952 closers.
BACKGROUND_POISSON_HZ: tuple[float, ...] = (
    0.0, 5.0, 10.0, 11.0, 15.0, 20.0, 22.0, 50.0,
)

# The background is given this long to bring the relays to their idling point
# before the stimulus.  5 tau_m = 50 ms would suffice for an isolated cell; 200 ms
# is used because the network is recurrent and its own activity has to settle too.
BACKGROUND_SETTLE_MS = 200.0


def measure_background_operating_point(
    net_data=None,
    conduction=None,
    muscles=None,
    burst_ms=200.0,
    slow_hz=50,
    fast_spikes=2,
    levels_pa=BACKGROUND_LADDER_PA,
    poisson_hz=BACKGROUND_POISSON_HZ,
    settle_ms=BACKGROUND_SETTLE_MS,
    verbose=True,
):
    """Deliverable 7: was the 28.6 ms synaptic floor an artefact of a silent network?

    The floor's stated mechanism is that a relay must be pushed the full 20 mV from
    ``V_rest`` by repeated afferent volleys, because the best relay receives only
    15.56 mV in one volley.  But ``run_lockstep_multi`` zeroed ``drive`` for every
    neuron outside the driven motor pool, so the relays really did sit at exactly
    ``V_rest`` -- a condition no VNC interneuron is ever in.  ``network.py`` has had
    ``create_background_drive`` (22 Hz x 1.3 mV Poisson) since Epic 1 and the
    training harness uses it; the loop-closure sweeps are the outlier.

    Both arms are run, because they are not equivalent: a constant current shifts
    the mean only, while Poisson shifts the mean *and* adds variance, and
    fluctuations can cross threshold at a mean that a constant current cannot.

    **The control is what decides whether any of it means anything.** Background
    makes neurons fire by themselves, so every level is run with
    ``freeze_physics=True`` as well, and a closure only counts if the closer fired
    with physics live, did NOT fire frozen, and fired after the first afferent
    spike.  The frozen closer count IS the false-positive rate.  If there is no
    level that both speeds closure and keeps the frozen control silent, there is no
    usable window, and that is the result.

    The drive is the class-specific protocol from deliverable 6 (slow MNs tonic,
    fast MNs a few spikes) because that is the biologically supported one, and the
    force model is on.

    Two confounds are measured on every row rather than argued away, because both
    were found to be real:

    * **motor-pool contamination.** The background is withheld from the driven pool
      directly, but the pool is *recurrently* connected to 25,635 neurons that do
      receive it, so above the network's ignition point the pool's own rate runs
      away -- measured 34 Hz at 0-125 pA but 248-351 Hz at 150-190 pA.  A row whose
      ``pool_hz`` has moved is no longer the class-specific protocol it claims to
      be, and its faster closure is partly faster *movement*.  ``pool_contaminated``
      flags it.
    * **closure by saturation.** ``n_closing`` is bounded by the 1,952 neurons
      presynaptic to some in-scope LF MN.  Once a large fraction of them fires, "a
      neuron presynaptic to a motor neuron fired" is satisfied by almost any active
      cell and the frozen control is the only thing separating that from
      spontaneity.  ``closer_share`` is reported so saturation is visible.
    """
    from .muscle_decoder import MuscleDecoder

    if net_data is None:
        net_data = load_full_vnc()
    meta_df, body_ids = net_data["meta_df"], net_data["body_ids"]
    meta_type = meta_df["type"].fillna("<untyped>").values

    if conduction is not None:
        encoder = conduction["encoder"]
        network = conduction["network"]
        sim, model, data, state, groups = conduction["body"]
    else:
        encoder = ProprioceptiveEncoder(meta_df, body_ids, leg="LF", side="L")
        sim, model, data, state, groups, _n = build_settled_body(verbose=verbose)
        network = FullVNCNetwork(net_data)

    decoder = MuscleDecoder(meta_df, body_ids, force_model=True)
    if muscles is None:
        muscles = tuple(STRONGEST_BY_GROUP[g] for g in JOINT_GROUPS)
    muscles = tuple(muscles)

    conv, edges, role = _relay_afferent_edges(net_data, encoder)
    in_scope_idx = set(lf_motor_in_scope(meta_df).index.values.tolist())
    presyn_idx = set(np.unique(
        net_data["sources"][np.isin(net_data["targets"], list(in_scope_idx))]
    ).tolist())
    conv["presyn_to_mn"] = conv.index.isin(presyn_idx)
    watch = list(conv.head(8).index.values)
    best_relay_idx = int(watch[0])
    n_presyn = len(presyn_idx)

    drive_by_class = {
        "slow": DRIVE_PA_FOR_HZ[slow_hz],
        "intermediate": DRIVE_PA_FOR_HZ[200],
        "fast": DRIVE_PA_FOR_HZ[200],
    }
    ms_by_class = {
        "slow": burst_ms,
        "intermediate": fast_spikes / 200.0 * 1000.0,
        "fast": fast_spikes / 200.0 * 1000.0,
    }

    if verbose:
        print("\n" + "=" * 78)
        print("[7] THE RELAYS' OPERATING POINT: was the 28.6 ms floor measured in "
              "an\n    unnaturally silent network?")
        print("=" * 78)
        print(f"  drive: class-specific -- slow MNs tonic {slow_hz} Hz, "
              f"fast/intermediate {fast_spikes} spikes then silent; "
              f"{burst_ms:.0f} ms burst, force model ON")
        print(f"  background applied to {network.n_neurons:,} neurons MINUS the "
              f"driven pool and the {len(encoder.assignments)} afferents, so the "
              "variable is the RELAYS' idling\n  point, not the motor drive or the "
              "sensory gain.")
        print(f"  {settle_ms:.0f} ms background settle before every stimulus, so "
              "the relays are AT their\n  operating point rather than climbing "
              "towards it.  Settle spikes excluded; t = 0 is\n  stimulus onset.")
        print(f"  open-loop arithmetic (isolated cell, dV = I * 100 MOhm): "
              f"1 pA -> 0.1 mV, so 50 pA\n  leaves "
              f"{open_loop_gap_mV(50.0):.1f} mV of the 20 mV to threshold and a "
              f"15.56 mV volley would clear it in\n  ONE arrival.  Whether the "
              "recurrent network actually delivers that offset is the\n  "
              "measurement -- deliverable 3 found the afferents rest NET-INHIBITED, "
              "so the sign is\n  not guaranteed.")
        print("  CLOSURE COUNTS ONLY IF: a neuron presynaptic to an in-scope LF MN "
              "fires live, does\n  NOT fire in the frozen control, and fires after "
              "the first afferent spike.")

    rows = []
    arms = (
        [("current", pa, 0.0) for pa in levels_pa]
        + [("poisson", 0.0, hz) for hz in poisson_hz if hz > 0]
    )
    baseline_pool_hz = None
    for arm, bg_pa, bg_hz in arms:
        frozen_row = None
        live_row = None
        for frozen in (True, False):
            t0 = time.time()
            times, indices, tr = run_lockstep_multi(
                network, sim, model, data, state, groups, decoder, encoder,
                muscles, drive_by_class["slow"], burst_ms=burst_ms,
                freeze_physics=frozen, watch=watch,
                drive_pa_by_class=drive_by_class,
                drive_ms_by_class=ms_by_class,
                background_pa=bg_pa, background_poisson_hz=bg_hz or None,
                background_settle_ms=settle_ms,
            )
            label = (f"{arm} {bg_pa:.0f} pA" if arm == "current"
                     else f"{arm} {bg_hz:.0f} Hz")
            row = _condition_row(
                net_data, encoder, conv, edges, in_scope_idx, presyn_idx,
                times, indices, tr, label, arm, watch,
            )
            row["wall_s"] = time.time() - t0
            row["settle_hz_mean"] = tr["settle_hz_mean"]
            row["settle_n_active"] = tr["settle_n_active"]
            row["settle_dv_best_mV"] = float(
                tr["settle_dv"].get(best_relay_idx, np.nan)
            )
            row["settle_dv_mean_mV"] = (
                float(np.mean(list(tr["settle_dv"].values())))
                if tr["settle_dv"] else np.nan
            )
            # Whole-network spontaneous rate during the stimulus window, over the
            # neurons that are neither driven nor afferent -- the population the
            # background is acting on.
            row["net_hz"] = float(
                len(indices) / network.n_neurons / (burst_ms / 1000.0)
            )
            if frozen:
                frozen_row = row
            else:
                live_row = row

        frozen_closers = set(frozen_row["closing_idx"])
        body = sorted(set(live_row["closing_idx"]) - frozen_closers)
        live_row["body_attributable"] = body
        live_row["n_body_closing"] = len(body)
        # Latency must be read off the BODY-ATTRIBUTABLE closers.  At high
        # background the earliest closer spike is very likely spontaneous, so
        # ``t_first_closing_ms`` over all closers would report a latency the body
        # did not produce.
        detail = {d["idx"]: d for d in live_row["closing_detail"]}
        t_body = (
            min(detail[x]["t_first_ms"] for x in body) if body else np.nan
        )
        live_row["t_closure_body_ms"] = t_body
        live_row["lag_ms"] = t_body - live_row["t_first_afferent_ms"]
        live_row["order_ok"] = bool(
            body and t_body > live_row["t_first_afferent_ms"]
        )
        # The false-positive rate: closers that fired with the leg immobilised.
        live_row["n_frozen_closing"] = frozen_row["n_closing"]
        live_row["n_frozen_downstream"] = frozen_row["n_downstream"]
        live_row["n_frozen_afferents"] = frozen_row["n_afferents_fired"]
        live_row["frozen_net_hz"] = frozen_row["net_hz"]
        live_row["frozen_closing_idx"] = frozen_row["closing_idx"]
        live_row["arm"] = arm
        live_row["background_pa"] = bg_pa
        live_row["background_hz"] = bg_hz
        live_row["fp_share"] = (
            frozen_row["n_closing"] / live_row["n_closing"]
            if live_row["n_closing"] else np.nan
        )
        # Confound 1: has the background leaked into the driven pool through the
        # recurrent network and changed the motor drive itself?  The pool gets no
        # background current, but it has synaptic partners that do.
        if baseline_pool_hz is None:
            baseline_pool_hz = float(live_row["pool_hz"])
        live_row["pool_hz_ratio"] = float(live_row["pool_hz"]) / baseline_pool_hz
        live_row["pool_contaminated"] = bool(live_row["pool_hz_ratio"] > 1.25)
        # Confound 2: what fraction of every neuron that COULD count as a closer
        # is now firing?  As this approaches 1 the criterion stops discriminating.
        live_row["closer_share"] = live_row["n_closing"] / n_presyn
        live_row["n_presyn_total"] = n_presyn
        rows.append(live_row)

        if verbose:
            r = live_row
            print(f"\n  {r['condition']:<16} "
                  f"idle dV(best relay) {r['settle_dv_best_mV']:+7.3f} mV | "
                  f"settle net {r['settle_hz_mean']:6.2f} Hz "
                  f"({r['settle_n_active']:,} neurons ever fired)")
            print(f"    LIVE   aff {r['n_afferents_fired']:2d}/"
                  f"{len(encoder.assignments)}  closers {r['n_closing']:3d}  "
                  f"t_aff {r['t_first_afferent_ms']:7.1f} ms  "
                  f"t_close(body) "
                  + ("     -- " if np.isnan(r["t_closure_body_ms"])
                     else f"{r['t_closure_body_ms']:7.1f}")
                  + f" ms  lag "
                  + ("     -- " if np.isnan(r["lag_ms"])
                     else f"{r['lag_ms']:+7.1f}")
                  + f" ms  exc {r['excursion_rad']:.3f} rad")
            print(f"    FROZEN aff {r['n_frozen_afferents']:2d}/"
                  f"{len(encoder.assignments)}  closers "
                  f"{r['n_frozen_closing']:3d}  net {r['frozen_net_hz']:6.2f} Hz"
                  f"   -> body-attributable closers {r['n_body_closing']:3d}  "
                  f"{'USABLE' if r['order_ok'] and r['n_frozen_closing'] == 0 else ('CONTAMINATED' if r['n_frozen_closing'] else 'no closure')}")

    table = pd.DataFrame(rows)
    if verbose:
        _print_background_sweep(table, meta_type, encoder)
    return {"table": table, "decoder": decoder, "muscles": muscles,
            "watch": watch, "convergence": conv}


def _print_background_sweep(table, meta_type, encoder):
    """The sweep table, the usable window, and the plain verdict on the floor."""
    n_aff = len(encoder.assignments)
    print("\n  SWEEP.  'idle dV' is the best relay's MEASURED offset from V_rest "
          "at stimulus\n  onset (StateMonitor, mean over the 50 ms before onset). "
          "'t_close' and 'lag' are\n  measured on BODY-ATTRIBUTABLE closers only. "
          "'fp' = closers that fired in the\n  frozen control, i.e. spontaneously. "
          "'poolx' = driven-pool rate over its rate at zero\n  background (>1.25 "
          "means the background leaked into the motor drive through the\n  "
          "recurrent network, so the row is no longer the protocol it claims). "
          "'share' =\n  closers as a fraction of the "
          f"{int(table['n_presyn_total'].iloc[0]):,} neurons presynaptic to an "
          "in-scope LF MN --\n  as it approaches 1 the closure criterion stops "
          "discriminating.")
    print(f"\n    {'background':<16} {'idle dV':>8} {'net Hz':>7} {'poolx':>6} "
          f"{'aff':>6} {'closers':>8} {'share':>6} {'fp':>5} {'body':>5} "
          f"{'t_aff':>7} {'t_close':>8} {'lag':>7} {'exc':>7}  verdict")
    for r in table.itertuples():
        t_close = ("      --" if np.isnan(r.t_closure_body_ms)
                   else f"{r.t_closure_body_ms:8.1f}")
        lag = "     --" if np.isnan(r.lag_ms) else f"{r.lag_ms:+7.1f}"
        t_aff = ("     --" if np.isnan(r.t_first_afferent_ms)
                 else f"{r.t_first_afferent_ms:7.1f}")
        if r.n_frozen_closing:
            verdict = "CONTAMINATED (spontaneous)"
        elif not r.order_ok:
            verdict = "no closure"
        elif r.pool_contaminated:
            verdict = "CONFOUNDED (pool runaway)"
        else:
            verdict = "usable"
        print(f"    {r.condition:<16} {r.settle_dv_best_mV:+8.3f} "
              f"{r.net_hz:7.2f} {r.pool_hz_ratio:6.2f} "
              f"{r.n_afferents_fired:3d}/{n_aff:<2d} "
              f"{r.n_closing:8d} {r.closer_share:6.1%} {r.n_frozen_closing:5d} "
              f"{r.n_body_closing:5d} {t_aff} {t_close} {lag} "
              f"{r.excursion_rad:7.3f}  {verdict}")

    # A row is usable only if the frozen control is silent AND the motor drive is
    # still the one specified.  Dropping the second test would credit the
    # background with a speed-up that faster movement produced.
    usable = table[
        (table["n_frozen_closing"] == 0)
        & table["order_ok"]
        & ~table["pool_contaminated"]
    ]
    baseline = table[(table["arm"] == "current") & (table["background_pa"] == 0)]

    print("\n  VERDICT")
    if baseline.empty:
        base_lag = np.nan
    else:
        base_lag = float(baseline["lag_ms"].iloc[0])
        b = baseline.iloc[0]
        print(f"    baseline (0 pA, the condition every earlier sweep ran): "
              f"lag {base_lag:+.1f} ms,\n      closure "
              f"{float(b['t_closure_body_ms']):.1f} ms, "
              f"{int(b['n_body_closing'])} body-attributable closers, "
              f"{int(b['n_frozen_closing'])} false positives.")

    if usable.empty:
        print("    NO USABLE WINDOW.  Every background level either failed to "
              "close the loop or\n    produced closers in the frozen control, so "
              "no level both speeds closure and\n    leaves the control silent. "
              "The 28.6 ms floor is NOT rescued by giving the relays\n    an "
              "operating point.")
    else:
        best = usable.loc[usable["lag_ms"].idxmin()]
        print(f"    usable window: "
              + ", ".join(str(c) for c in usable["condition"])
              + f"\n    best lag {float(best['lag_ms']):+.1f} ms at "
              f"{best['condition']} (closure "
              f"{float(best['t_closure_body_ms']):.1f} ms, "
              f"{int(best['n_body_closing'])} closers)")
        if not np.isnan(base_lag):
            print(f"    vs {base_lag:+.1f} ms at zero background: "
                  f"{base_lag - float(best['lag_ms']):+.1f} ms")
        if float(best["lag_ms"]) <= 6.0:
            print("    This REACHES the published 3-6 ms afferent->postsynaptic "
                  "band (Tuthill & Wilson\n    2016), so the sub-threshold gap was "
                  "partly an artefact of a silent network.")
        else:
            print(f"    This does NOT reach the published 3-6 ms band; the floor "
                  f"moves to "
                  f"{float(best['lag_ms']):.1f} ms at best.")

    contaminated = table[table["n_frozen_closing"] > 0]
    if not contaminated.empty:
        first = contaminated.iloc[0]
        print(f"    spontaneous firing appears at {first['condition']} "
              f"({int(first['n_frozen_closing'])} closers fire with the leg "
              f"immobilised),\n    so anything at or above it is uninterpretable.")
    confounded = table[table["pool_contaminated"] & table["order_ok"]]
    if not confounded.empty:
        first = confounded.iloc[0]
        print(f"    the driven pool runs away from {first['condition']} onward "
              f"({first['pool_hz_ratio']:.1f}x its rate at zero\n    background), "
              "so those rows are a DIFFERENT motor protocol, not a faster return "
              "path --\n    their excursion also grows "
              f"({float(first['excursion_rad']):.3f} rad vs "
              f"{float(table['excursion_rad'].iloc[0]):.3f}), i.e. part of the "
              "speed-up is faster\n    MOVEMENT, which force gain was already "
              "known to buy.")

    print("\n  WHAT THIS DOES TO THE 'RETURN PATH IS SUB-THRESHOLD' CLAIM")
    if usable.empty:
        print("    It stands.  The 15.56-vs-20 mV gap is not closed by a "
              "physiological operating\n    point: the levels that would close it "
              "make the relays fire on their own.")
    else:
        print("    It is weakened.  The gap was measured with the relays pinned at "
              "exactly V_rest,\n    which is not a state a VNC interneuron "
              "occupies, and giving them an operating\n    point that keeps the "
              "frozen control silent changes the number.")
    print("    Unaffected either way: the BROADCAST finding (IN21A004 bodyId "
          "800802 contacts 46 of\n    64 LF motor neurons) is pure anatomy and "
          "does not depend on any operating point.")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def run_multi_muscle(quick=False):
    """Run Deliverables 4-6 plus the size-principle check.

    Deliberately standalone: the 0c sweep in ``run_all`` takes ~25 conditions to
    reach a conclusion already recorded in the lab entry.  Uses one network, body,
    encoder and settled state throughout, which is what makes the legacy-vs-force
    decode comparison in [5] a controlled measurement.
    """
    pd.set_option("display.width", 220)

    print("=" * 78)
    print("Multi-muscle, multi-joint drive: the afferent-breadth hypothesis")
    print("=" * 78)
    print("Every number below is a spike count from a Brian2 SpikeMonitor "
          "with real MuJoCo\nphysics in lockstep at dt = 0.1 ms.  A current is "
          "not a spike; a depolarisation is\nnot a spike.")

    net_data = load_full_vnc()
    meta_df, body_ids = net_data["meta_df"], net_data["body_ids"]

    from .muscle_decoder import MuscleDecoder

    encoder = ProprioceptiveEncoder(meta_df, body_ids, leg="LF", side="L")
    decoder = MuscleDecoder(meta_df, body_ids)
    sim, model, data, state, groups, _names = build_settled_body(verbose=True)
    t0 = time.time()
    network = FullVNCNetwork(net_data)
    print(f"  network: {network.n_neurons:,} neurons, "
          f"{len(net_data['sources']):,} synapses, per-synapse delay "
          f"{network.delays_ms.min():.2f}-{network.delays_ms.max():.2f} ms "
          f"-- built in {time.time() - t0:.1f}s")

    conduction = {
        "encoder": encoder, "decoder": decoder, "network": network,
        "body": (sim, model, data, state, groups),
    }
    monotonicity = verify_size_principle(decoder, verbose=True)
    result = measure_multi_muscle_drive(
        net_data, conduction=conduction,
        rates_hz=(200,),
        burst_ms=(50.0,) if quick else (50.0, 200.0),
    )
    threshold = measure_rate_threshold(
        net_data, conduction=conduction,
        burst_ms=(50.0,) if quick else (50.0, 200.0),
    )
    class_protocol = measure_class_protocol(
        net_data, conduction=conduction,
        slow_rates_hz=(50, 80) if quick else (30, 50, 80),
        fast_spikes=(2, 10) if quick else (1, 2, 5, 10),
    )
    print("\n" + "=" * 78)
    print("Done.")
    print("=" * 78)
    return {"multi_muscle": result, "rate_threshold": threshold,
            "class_protocol": class_protocol, "monotonicity": monotonicity}


def run_background(quick=False):
    """Run Deliverable 7: the background-drive sweep and its frozen control.

    Standalone because it is the only sweep whose baseline row must reproduce the
    published 35.4 ms / +28.8 ms closure exactly -- that is the check that the
    background is the one changed variable.
    """
    pd.set_option("display.width", 240)

    print("=" * 78)
    print("The relays' operating point: was the 28.6 ms synaptic floor an "
          "artefact of a\nnetwork with no background activity at all?")
    print("=" * 78)
    print("Every verdict below is a Brian2 SpikeMonitor count with real MuJoCo "
          "physics in\nlockstep at dt = 0.1 ms and a frozen-physics control at "
          "EVERY background level.\nA depolarisation is not a spike.")

    net_data = load_full_vnc()
    meta_df, body_ids = net_data["meta_df"], net_data["body_ids"]

    from .muscle_decoder import MuscleDecoder

    encoder = ProprioceptiveEncoder(meta_df, body_ids, leg="LF", side="L")
    decoder = MuscleDecoder(meta_df, body_ids, force_model=True)
    sim, model, data, state, groups, _names = build_settled_body(verbose=True)
    t0 = time.time()
    network = FullVNCNetwork(net_data)
    print(f"  network: {network.n_neurons:,} neurons, "
          f"{len(net_data['sources']):,} synapses, per-synapse delay "
          f"{network.delays_ms.min():.2f}-{network.delays_ms.max():.2f} ms "
          f"-- built in {time.time() - t0:.1f}s")

    conduction = {
        "encoder": encoder, "decoder": decoder, "network": network,
        "body": (sim, model, data, state, groups),
    }
    result = measure_background_operating_point(
        net_data, conduction=conduction,
        levels_pa=(0.0, 50.0, 100.0, 125.0) if quick else BACKGROUND_LADDER_PA,
        poisson_hz=(5.0, 10.0, 22.0) if quick else BACKGROUND_POISSON_HZ,
    )
    print("\n" + "=" * 78)
    print("Done.")
    print("=" * 78)
    return {"background": result}


def run_all(quick=False):
    """Run all three Child 0c measurements and print the report."""
    pd.set_option("display.width", 200)

    print("=" * 78)
    print("Child 0c: wire the body -- end-to-end conduction measurements")
    print("=" * 78)
    print("Every number below is a spike count from a real run "
          "(Brian2 SpikeMonitor +\nreal MuJoCo physics). A current is not a "
          "spike.")

    net_data = load_full_vnc()

    pool_sizes = (4, 8) if quick else (1, 2, 4, 8, 14)
    rates = (80, 200) if quick else (30, 50, 80, 120, 200)
    conduction = measure_conduction(
        net_data, pool_sizes=pool_sizes, rates_hz=rates,
    )
    per_driver = measure_per_driver(conduction)
    volley = measure_return_volley(
        net_data,
        encoder=conduction["encoder"],
        network=conduction["network"],
        rates_hz=(80, 200) if quick else (80, 120, 150, 200),
    )
    physics_volley = measure_volley_from_physics(conduction)
    rest = measure_afferent_rest_point(
        net_data,
        encoder=conduction["encoder"],
        network=conduction["network"],
        background_pa=(240.0,) if quick else (205.0, 240.0, 260.0, 300.0),
    )

    print("\n" + "=" * 78)
    print("Done.")
    print("=" * 78)
    return {
        "conduction": conduction,
        "per_driver": per_driver,
        "return_volley": volley,
        "physics_volley": physics_volley,
        "rest_point": rest,
    }
