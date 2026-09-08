"""Sign-policy sensitivity sweep: does Level 1 depend on how we sign ``unclear``?

The shared weight formula multiplies every synapse by the presynaptic neuron's
``sign``, and ``constants.NT_SIGN_MAP`` maps ``unclear`` to ``None`` -> 0.  A zero
sign does not attenuate, it **deletes**: the presynaptic cell still integrates and
fires and nothing downstream hears it.  Measured on the full VNC, that removes the
entire output of ~2,900-3,300 neurons (13%), including 658 of 702 motor neurons.

``unclear`` is a *prediction-confidence* failure, not a biological fact.  So this
module does **not** pick a sign for it.  It runs the cheapest well-characterised
Level 1 probe -- the multi-muscle closure measurement with its frozen-physics
control and its background ladder -- under three policies that differ in exactly
one value:

===========  ==================================================================
policy       ``unclear``
===========  ==================================================================
**A**        0   -- silenced (the shipped default)
**B**        +1  -- excitatory, the 56% majority class
**C**        -1  -- inhibitory
===========  ==================================================================

``serotonin`` / ``octopamine`` / ``dopamine`` stay at 0 in **all three** arms (they
are genuinely neuromodulatory and arguably not fast PSPs at all) and ``histamine``
stays at -1, so the sweep isolates one variable.  Every policy map is built by
**copying the imported** ``constants.NT_SIGN_MAP`` and overriding one key -- never
by reimplementing the sign logic.  An earlier draft of the sign issue wrongly
called ``histamine`` a defect precisely because it was reimplemented from memory.

Everything measured here reuses ``body_wiring``: ``load_full_vnc`` (with the
sign-map override threaded through ``build_live_weights``), ``build_settled_body``
(3000-step settle, ``data.act`` in the restored state), ``FullVNCNetwork``, and
``measure_background_operating_point``, which already runs the class-specific
drive (slow MNs tonic 50 Hz, fast/intermediate 2 spikes then silent), a 200 ms
background settle, the frozen-physics control at **every** level, and the
pool-runaway confound check.  Nothing is rebuilt.

Two anatomical questions are computed from the live weight array rather than run,
because they are properties of the wiring and not of any stimulus:

* whether ``IN21A004`` bodyId 800802 remains the dominant broadcast relay -- the
  cell that closes Level 1 by contacting 46 of 64 LF motor neurons;
* the Level 3 outbound DN ranking (DNa02's rank among the DNs, and the top-6 by
  summed signed PSP onto interneurons that reach LF motor neurons).

Usage
-----
    python -m digital_drosophila check sign_policy            # all three arms
    python -m digital_drosophila check sign_policy --quick    # coarser ladder
    python -m digital_drosophila check sign_policy --policy B
"""

import time

import numpy as np
import pandas as pd

from .body_wiring import (
    BACKGROUND_LADDER_PA,
    BACKGROUND_POISSON_HZ,
    STRONGEST_BY_GROUP,
    FullVNCNetwork,
    build_settled_body,
    lf_motor_in_scope,
    load_full_vnc,
    measure_background_operating_point,
)
from .constants import NT_SIGN_MAP
from .proprioceptive_encoder import JOINT_GROUPS, ProprioceptiveEncoder

# The one cell Level 1's closing conclusion rests on: left-T1 IN21A004.  Five
# other cells share the type name and contact zero LF motor neurons, so this is
# resolved by bodyId and reported per-cell.
IN21A004_BODYID = 800802

# The DNs the L3 issue lists as the corrected top-6, by summed signed PSP onto
# interneurons reaching LF motor neurons.  Checked for reordering, not assumed.
L3_TOP6 = [
    ("DNg100", 10056),
    ("pIP1", 10030),
    ("DNg37", 10506),
    ("DNg101", 11527),
    ("DNge073", 11737),
    ("aSP22", 10090),
]
DNA02_BODYIDS = (10360, 523769)

POLICY_UNCLEAR = {"A": None, "B": +1, "C": -1}
POLICY_LABEL = {
    "A": "A: unclear = 0 (silenced, shipped default)",
    "B": "B: unclear = +1 (excitatory, 56% majority class)",
    "C": "C: unclear = -1 (inhibitory)",
}


def policy_sign_map(policy):
    """``constants.NT_SIGN_MAP`` with only ``unclear`` overridden.

    Built by copying the imported map so ``histamine`` (-1), ``serotonin``,
    ``octopamine`` and ``dopamine`` are whatever ``constants.py`` says, not what
    this module remembers.
    """
    if policy not in POLICY_UNCLEAR:
        raise ValueError(f"unknown policy {policy!r}; choose from {sorted(POLICY_UNCLEAR)}")
    sign_map = dict(NT_SIGN_MAP)
    sign_map["unclear"] = POLICY_UNCLEAR[policy]
    # The sweep is only interpretable if nothing else moved.
    for nt in ("serotonin", "octopamine", "dopamine"):
        if sign_map.get(nt) is not None:
            raise RuntimeError(
                f"{nt} is not None in constants.NT_SIGN_MAP; the sweep would vary "
                "more than one value."
            )
    if sign_map.get("histamine") != -1:
        raise RuntimeError(
            "histamine is not -1 in constants.NT_SIGN_MAP; the sweep assumed the "
            "shipped map already had it right."
        )
    return sign_map


# ---------------------------------------------------------------------------
# Anatomy: what the sign policy does to the wiring, before anything is run
# ---------------------------------------------------------------------------


def silencing_census(net_data):
    """How many neurons have their entire output deleted under this policy."""
    meta_df = net_data["meta_df"]
    sources = net_data["sources"]
    weights = net_data["weights_mV"]
    n = len(meta_df)

    has_out = np.zeros(n, dtype=bool)
    has_out[np.unique(sources)] = True
    # "Silenced" is measured on the WEIGHTS, not on the sign vector, so an
    # inhibitory-but-transmitting neuron is never counted as absent.
    live_out = np.zeros(n, dtype=bool)
    live_out[np.unique(sources[weights != 0.0])] = True
    silenced = has_out & ~live_out

    return {
        "n_neurons": int(n),
        "n_with_outputs": int(has_out.sum()),
        "n_silenced": int(silenced.sum()),
        "n_silenced_motor": int((silenced & (meta_df["superclass"] == "vnc_motor").values).sum()),
        "n_silenced_dn": int(
            (silenced & meta_df["superclass"].astype(str).str.startswith("descending").values).sum()
        ),
        "syn_zero_share": float((weights == 0.0).mean()),
        "n_syn_zero": int((weights == 0.0).sum()),
        "by_superclass": meta_df.loc[silenced, "superclass"].value_counts(),
    }


def broadcast_ranking(net_data, top=8):
    """Per-cell fan-out onto the 64 LF motor neurons, ranked.

    Two rankings, because they answer different questions:

    * ``n_lf_mn`` -- how many of the 64 LF MNs the cell contacts with a
      **non-zero** weight.  This is the "broadcast" figure: Level 1's closing
      conclusion is that ``IN21A004`` 800802 reaches 46 of 64, so per-neuron
      attribution is impossible.
    * ``psp_mV`` -- summed signed weight onto the 52 in-scope LF MNs, which is
      what decides whether the broadcast is excitatory or inhibitory.

    Both are computed from the live ``weights_mV`` array, so they change with the
    sign policy exactly as the simulation does.
    """
    meta_df = net_data["meta_df"]
    sources, targets = net_data["sources"], net_data["targets"]
    weights = net_data["weights_mV"]

    lf64 = meta_df[
        (meta_df["superclass"] == "vnc_motor")
        & (meta_df["subclass"] == "fl")
        & (meta_df["somaSide"] == "L")
    ]
    lf64_idx = set(lf64.index.values.tolist())
    in_scope_idx = set(lf_motor_in_scope(meta_df).index.values.tolist())

    onto64 = np.isin(targets, list(lf64_idx)) & (weights != 0.0)
    df64 = pd.DataFrame({"pre": sources[onto64], "post": targets[onto64]})
    n_lf_mn = df64.groupby("pre").post.nunique()

    onto52 = np.isin(targets, list(in_scope_idx))
    df52 = pd.DataFrame({"pre": sources[onto52], "w": weights[onto52]})
    psp = df52.groupby("pre").w.sum()

    table = pd.DataFrame({"n_lf_mn": n_lf_mn}).join(psp.rename("psp_mV"), how="outer")
    table["n_lf_mn"] = table["n_lf_mn"].fillna(0).astype(int)
    table["psp_mV"] = table["psp_mV"].fillna(0.0)
    table["bodyId"] = meta_df["bodyId"].values[table.index.values]
    table["type"] = meta_df["type"].fillna("<untyped>").values[table.index.values]
    table["nt"] = meta_df["consensusNt"].fillna("<none>").values[table.index.values]
    table = table.sort_values(["n_lf_mn", "psp_mV"], ascending=[False, False])

    # Rank of the load-bearing cell, ties counted as "how many strictly beat it".
    row = table[table["bodyId"] == IN21A004_BODYID]
    if row.empty:
        target = {"present": False}
    else:
        r = row.iloc[0]
        target = {
            "present": True,
            "n_lf_mn": int(r["n_lf_mn"]),
            "psp_mV": float(r["psp_mV"]),
            "rank_breadth": int((table["n_lf_mn"] > r["n_lf_mn"]).sum()) + 1,
            "rank_exc_psp": int((table["psp_mV"] > r["psp_mV"]).sum()) + 1,
            "n_ranked": int(len(table)),
        }
    return {"table": table, "top": table.head(top), "in21a004": target,
            "n_lf64": len(lf64_idx), "n_in_scope": len(in_scope_idx)}


def closer_broadcast_table(net_data, closer_idx, verbose=True):
    """Level 1's closing table, recomputed for the closers a run actually produced.

    The multi-muscle lab entry ranks the **six measured closers** by how many of
    the 64 LF motor neurons each contacts, and concludes that ``IN21A004`` at
    46 of 64 makes per-neuron attribution impossible.  That claim is about the
    closers, not about the whole VNC, so it has to be re-asked over whatever set
    of closers each policy produces -- a policy that recruits 200 closers could
    dethrone ``IN21A004`` without changing a single one of its own synapses.
    """
    meta_df = net_data["meta_df"]
    br = broadcast_ranking(net_data)["table"]
    rows = []
    for idx in closer_idx:
        if idx not in br.index:
            rows.append({"idx": int(idx),
                         "bodyId": int(meta_df["bodyId"].values[idx]),
                         "type": str(meta_df["type"].fillna("<untyped>").values[idx]),
                         "nt": str(meta_df["consensusNt"].fillna("<none>").values[idx]),
                         "n_lf_mn": 0, "psp_mV": 0.0})
            continue
        r = br.loc[idx]
        rows.append({"idx": int(idx), "bodyId": int(r["bodyId"]), "type": str(r["type"]),
                     "nt": str(r["nt"]), "n_lf_mn": int(r["n_lf_mn"]),
                     "psp_mV": float(r["psp_mV"])})
    table = pd.DataFrame(rows).sort_values("n_lf_mn", ascending=False)
    if verbose and not table.empty:
        print(f"    {'closer':<24} {'bodyId':>9} {'LF MNs':>7} {'share':>6} "
              f"{'PSP onto 52':>12}  nt")
        for r in table.head(12).itertuples():
            print(f"    {r.type:<24} {r.bodyId:9d} {r.n_lf_mn:7d} "
                  f"{r.n_lf_mn / 64:5.0%} {r.psp_mV:+11.2f} mV  {r.nt}")
        if len(table) > 12:
            print(f"    ... {len(table) - 12} more closers")
    return table


def dn_outbound_ranking(net_data, top=8):
    """L3 outbound: DNs by summed signed PSP onto interneurons reaching LF MNs.

    Reproduces the L3 issue's corrected ranking inside the harness where the
    weights are actually built (the issue's own table came from a reimplementation
    of the formula, and its predecessor was sign-blind and therefore inverted).
    ``inter`` is the presynaptic set of the 64 LF MNs *including* the motor neurons
    themselves, which is the definition that reproduces the issue's numbers; the
    52-in-scope / MN-excluded variant is also returned because the choice moves
    the mV values by a few percent and one rank.
    """
    meta_df = net_data["meta_df"]
    sources, targets = net_data["sources"], net_data["targets"]
    weights = net_data["weights_mV"]

    lf64 = meta_df[
        (meta_df["superclass"] == "vnc_motor")
        & (meta_df["subclass"] == "fl")
        & (meta_df["somaSide"] == "L")
    ]
    dn_idx = np.flatnonzero((meta_df["superclass"] == "descending_neuron").values)

    out = {}
    for name, mn_idx in (("lf64", set(lf64.index.values.tolist())),
                         ("in52", set(lf_motor_in_scope(meta_df).index.values.tolist()))):
        presyn = set(np.unique(sources[np.isin(targets, list(mn_idx))]).tolist())
        inter = presyn if name == "lf64" else presyn - mn_idx
        mask = np.isin(sources, dn_idx) & np.isin(targets, list(inter))
        ranked = (
            pd.DataFrame({"pre": sources[mask], "w": weights[mask]})
            .groupby("pre").w.sum().sort_values(ascending=False)
        )
        rows = []
        for i, v in ranked.head(top).items():
            rows.append({
                "bodyId": int(meta_df["bodyId"].values[i]),
                "type": str(meta_df["type"].fillna("<untyped>").values[i]),
                "psp_mV": float(v),
                "rank": int((ranked.values > v).sum()) + 1,
            })
        named = {}
        for label, bid in L3_TOP6 + [("DNa02", b) for b in DNA02_BODYIDS]:
            hit = np.flatnonzero(meta_df["bodyId"].values == bid)
            if len(hit) == 0 or int(hit[0]) not in ranked.index:
                named[(label, bid)] = None
                continue
            i = int(hit[0])
            v = float(ranked.loc[i])
            named[(label, bid)] = {
                "psp_mV": v, "rank": int((ranked.values > v).sum()) + 1,
            }
        out[name] = {"ranked": ranked, "top": rows, "named": named,
                     "n_ranked": int(len(ranked))}
    return out


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------


def run_policy(policy, body=None, quick=False, verbose=True):
    """Build the VNC under ``policy`` and run the Level 1 closure + ladder.

    ``body`` lets the settled MuJoCo body be reused across policies -- it is
    independent of the sign map, and ``reset_body`` restores ``qpos``/``qvel``/
    ``act`` before every condition, so sharing it changes nothing and saves a
    3000-step settle per arm.
    """
    from .muscle_decoder import MuscleDecoder

    sign_map = policy_sign_map(policy)
    if verbose:
        print("\n" + "#" * 78)
        print(f"# POLICY {POLICY_LABEL[policy]}")
        print("#" * 78)
        print("  sign map (imported from constants.NT_SIGN_MAP, one key overridden): "
              + ", ".join(f"{k}={'0' if v is None else v:>2}"
                          for k, v in sign_map.items()))

    net_data = load_full_vnc(nt_sign_map=sign_map)
    census = silencing_census(net_data)
    broadcast = broadcast_ranking(net_data)
    dns = dn_outbound_ranking(net_data)

    if verbose:
        w = net_data["weights_mV"]
        print(f"  weights: {len(w):,} synapses, "
              f"{census['n_syn_zero']:,} exactly zero ({census['syn_zero_share']:.2%}), "
              f"{int((w > 0).sum()):,} excitatory, {int((w < 0).sum()):,} inhibitory")
        print(f"  neurons whose ENTIRE output is deleted: {census['n_silenced']:,} of "
              f"{census['n_with_outputs']:,} with any outgoing synapse "
              f"({census['n_silenced'] / census['n_with_outputs']:.1%}) -- "
              f"{census['n_silenced_motor']} motor, {census['n_silenced_dn']} descending")

    meta_df, body_ids = net_data["meta_df"], net_data["body_ids"]
    encoder = ProprioceptiveEncoder(meta_df, body_ids, leg="LF", side="L")
    decoder = MuscleDecoder(meta_df, body_ids, force_model=True)
    if body is None:
        body = build_settled_body(verbose=verbose)[:5]
    sim, model, data, state, groups = body

    t0 = time.time()
    network = FullVNCNetwork(net_data)
    if verbose:
        print(f"  network: {network.n_neurons:,} neurons, "
              f"{len(net_data['sources']):,} synapses, delay "
              f"{network.delays_ms.min():.2f}-{network.delays_ms.max():.2f} ms "
              f"(seeded, identical across policies) -- {time.time() - t0:.1f}s")

    conduction = {
        "encoder": encoder, "decoder": decoder, "network": network,
        "body": (sim, model, data, state, groups),
    }
    result = measure_background_operating_point(
        net_data, conduction=conduction,
        muscles=tuple(STRONGEST_BY_GROUP[g] for g in JOINT_GROUPS),
        burst_ms=200.0, slow_hz=50, fast_spikes=2,
        levels_pa=(0.0, 50.0, 100.0, 125.0) if quick else BACKGROUND_LADDER_PA,
        poisson_hz=(5.0, 11.0, 22.0) if quick else BACKGROUND_POISSON_HZ,
        verbose=verbose,
    )

    # Level 1's closing table, re-asked over the closers THIS policy produced.
    closers = {}
    for arm, level in (("current", 0.0), ("current", 125.0)):
        row = _row(result["table"], arm, level)
        if row is None:
            continue
        tag = f"{arm} {level:.0f}"
        if verbose:
            print(f"\n  closers at {tag}, by how many of the 64 LF MNs each "
                  f"contacts (Level 1's closing table):")
        closers[tag] = closer_broadcast_table(
            net_data, list(row["closing_idx"]), verbose=verbose
        )

    del network
    return {
        "policy": policy, "sign_map": sign_map, "net_data_census": census,
        "broadcast": broadcast, "dns": dns, "table": result["table"],
        "closers": closers, "body": body,
    }


def refine_ceiling_and_population(
    policies=("A", "B", "C"),
    poisson_hz=(11.0, 12.0, 13.0, 14.0, 15.0),
    current_pa=(125.0, 130.0, 135.0, 140.0),
    verbose=True,
):
    """Two follow-ups the three-arm sweep leaves coarse.

    1. **The spontaneity ceiling between ladder rungs.** The shipped ladder jumps
       11 -> 15 Hz on the Poisson arm and 135 -> 150 pA on the constant arm.
       Policy B went spontaneous at 15 Hz where A and C did not, so where B's
       ceiling actually sits is unresolved by the coarse ladder.  Frozen control at
       every point, as always.
    2. **Newly active / newly silent, measured where the network fires.** At 0 pA
       only 7 neurons fire downstream at all, so "newly active" there is bounded
       near zero by the operating point rather than by the sign policy.  The
       population comparison is therefore also taken at 125 pA, over EVERY neuron
       that fired (the driven pool and the 41 afferents excluded, since they fire
       by construction).
    """
    from .muscle_decoder import MuscleDecoder
    from .body_wiring import (
        DRIVE_PA_FOR_HZ, BACKGROUND_SETTLE_MS, run_lockstep_multi,
    )

    body = None
    out = {}
    for policy in policies:
        sign_map = policy_sign_map(policy)
        net_data = load_full_vnc(nt_sign_map=sign_map)
        meta_df, body_ids = net_data["meta_df"], net_data["body_ids"]
        encoder = ProprioceptiveEncoder(meta_df, body_ids, leg="LF", side="L")
        decoder = MuscleDecoder(meta_df, body_ids, force_model=True)
        if body is None:
            body = build_settled_body(verbose=False)[:5]
        sim, model, data, state, groups = body
        network = FullVNCNetwork(net_data)
        muscles = tuple(STRONGEST_BY_GROUP[g] for g in JOINT_GROUPS)

        in_scope_idx = set(lf_motor_in_scope(meta_df).index.values.tolist())
        presyn_idx = set(np.unique(
            net_data["sources"][np.isin(net_data["targets"], list(in_scope_idx))]
        ).tolist())

        def one(bg_pa=0.0, bg_hz=None, frozen=False):
            times, indices, tr = run_lockstep_multi(
                network, sim, model, data, state, groups, decoder, encoder,
                muscles, DRIVE_PA_FOR_HZ[50], burst_ms=200.0,
                freeze_physics=frozen,
                drive_pa_by_class={"slow": DRIVE_PA_FOR_HZ[50],
                                   "intermediate": DRIVE_PA_FOR_HZ[200],
                                   "fast": DRIVE_PA_FOR_HZ[200]},
                drive_ms_by_class={"slow": 200.0, "intermediate": 10.0,
                                   "fast": 10.0},
                background_pa=bg_pa, background_poisson_hz=bg_hz,
                background_settle_ms=BACKGROUND_SETTLE_MS,
            )
            excluded = set(tr["pool_idx"].tolist()) | set(tr["afferent_idx"].tolist())
            fired = set(int(x) for x in np.unique(indices)) - excluded
            return {
                "fired": fired,
                "closers": fired & presyn_idx,
                "pool_hz": float(tr["pool_rate_hz"]),
                "excursion": float(np.abs(tr["angles"] - tr["angles"][0]).max()),
            }

        rows = []
        for hz in poisson_hz:
            live, froz = one(bg_hz=hz), one(bg_hz=hz, frozen=True)
            rows.append({"arm": "poisson", "level": hz, "live_closers": len(live["closers"]),
                         "frozen_closers": len(froz["closers"]),
                         "pool_hz": live["pool_hz"], "excursion": live["excursion"]})
        for pa in current_pa:
            live, froz = one(bg_pa=pa), one(bg_pa=pa, frozen=True)
            rows.append({"arm": "current", "level": pa, "live_closers": len(live["closers"]),
                         "frozen_closers": len(froz["closers"]),
                         "pool_hz": live["pool_hz"], "excursion": live["excursion"]})
        pop = {level: one(bg_pa=level)["fired"] for level in (0.0, 125.0)}
        out[policy] = {"ceiling": pd.DataFrame(rows), "population": pop}
        del network

        if verbose:
            print(f"\n  policy {policy} -- finer spontaneity ladder "
                  f"(frozen control at every point):")
            print(f"    {'arm':>8} {'level':>7} {'live closers':>13} "
                  f"{'FROZEN closers':>15} {'poolHz':>8} {'exc':>7}  verdict")
            for r in out[policy]["ceiling"].itertuples():
                verdict = ("CONTAMINATED" if r.frozen_closers else "clean-frozen")
                print(f"    {r.arm:>8} {r.level:7.0f} {r.live_closers:13d} "
                      f"{r.frozen_closers:15d} {r.pool_hz:8.1f} "
                      f"{r.excursion:7.3f}  {verdict}")

    if verbose and "A" in out:
        print("\n  newly active / newly silent vs policy A, over EVERY neuron that "
              "fired\n  (driven pool and afferents excluded):")
        for level in (0.0, 125.0):
            base = out["A"]["population"][level]
            print(f"    at {level:.0f} pA background:")
            for p in policies:
                s = out[p]["population"][level]
                print(f"      policy {p}: {len(s):5d} fired  "
                      f"+{len(s - base):5d} newly active  "
                      f"-{len(base - s):5d} newly silent")
    return out


def _usable(table):
    return table[
        (table["n_frozen_closing"] == 0)
        & table["order_ok"]
        & ~table["pool_contaminated"]
    ]


def _ceiling(table, arm):
    """Highest background level in ``arm`` that is still usable, and what breaks."""
    sub = table[table["arm"] == arm]
    key = "background_pa" if arm == "current" else "background_hz"
    usable = _usable(sub)
    top = float(usable[key].max()) if not usable.empty else np.nan
    spont = sub[sub["n_frozen_closing"] > 0]
    runaway = sub[sub["pool_contaminated"]]
    return {
        "usable_max": top,
        "first_spontaneous": float(spont[key].iloc[0]) if not spont.empty else np.nan,
        "first_runaway": float(runaway[key].iloc[0]) if not runaway.empty else np.nan,
        "n_usable": int(len(usable)),
    }


def _row(table, arm, level):
    key = "background_pa" if arm == "current" else "background_hz"
    sub = table[(table["arm"] == arm) & (np.isclose(table[key], level))]
    return None if sub.empty else sub.iloc[0]


def compare(results, verbose=True):
    """Three-column comparison of every measurement in the spec."""
    order = [p for p in ("A", "B", "C") if p in results]
    cols = {p: results[p] for p in order}

    def line(label, fn, width=26):
        cells = []
        for p in order:
            try:
                cells.append(fn(cols[p]))
            except Exception as exc:  # surfaced, never silently blanked
                cells.append(f"<err {type(exc).__name__}>")
        print(f"  {label:<{width}}" + "".join(f"{c:>21}" for c in cells))

    if not verbose:
        return

    print("\n" + "=" * 92)
    print("SIGN-POLICY SENSITIVITY: three columns, one changed value")
    print("=" * 92)
    print(f"  {'measurement':<26}" + "".join(f"{'policy ' + p:>21}" for p in order))
    print("  " + "-" * 88)

    print("\n  -- the wiring --")
    line("unclear sign", lambda r: str(POLICY_UNCLEAR[r["policy"]] or 0))
    line("synapses exactly 0", lambda r: f"{r['net_data_census']['n_syn_zero']:,}")
    line("  as share", lambda r: f"{r['net_data_census']['syn_zero_share']:.2%}")
    line("neurons fully silenced", lambda r: f"{r['net_data_census']['n_silenced']:,}")
    line("  of which motor", lambda r: f"{r['net_data_census']['n_silenced_motor']}")
    line("  of which descending", lambda r: f"{r['net_data_census']['n_silenced_dn']}")

    print("\n  -- loop closure, 0 pA background (Level 1 baseline: 35.4 ms, 6 closers) --")
    for arm, level, tag in (("current", 0.0, "0 pA"), ("current", 125.0, "125 pA")):
        print(f"\n    [{tag}]")
        def g(field, fmt="{:.1f}", level=level, arm=arm):
            def inner(r):
                row = _row(r["table"], arm, level)
                if row is None:
                    return "not run"
                v = row[field]
                if isinstance(v, float) and np.isnan(v):
                    return "--"
                return fmt.format(v)
            return inner
        line("  afferents fired /41", g("n_afferents_fired", "{:.0f}"))
        line("  closers (presyn to MN)", g("n_closing", "{:.0f}"))
        line("  neurons fired downstream", g("n_downstream", "{:.0f}"))
        line("  in-scope MNs fired", g("n_downstream_motor", "{:.0f}"))
        line("  FROZEN false positives", g("n_frozen_closing", "{:.0f}"))
        line("  body-attributable closers", g("n_body_closing", "{:.0f}"))
        line("  closure t (ms)", g("t_closure_body_ms"))
        line("  afferent->closure lag (ms)", g("lag_ms", "{:+.1f}"))
        line("  excursion (rad)", g("excursion_rad", "{:.3f}"))
        line("  closes?", lambda r, arm=arm, level=level: (
            "n/a" if _row(r["table"], arm, level) is None
            else ("YES" if bool(_row(r["table"], arm, level)["order_ok"])
                  and int(_row(r["table"], arm, level)["n_frozen_closing"]) == 0
                  else "NO")))

    print("\n  -- spontaneity ceiling (highest level with 0 frozen closers, pool intact) --")
    line("constant: usable max (pA)", lambda r: f"{_ceiling(r['table'], 'current')['usable_max']:.0f}")
    line("constant: 1st spontaneous", lambda r: (
        "none in ladder" if np.isnan(_ceiling(r["table"], "current")["first_spontaneous"])
        else f"{_ceiling(r['table'], 'current')['first_spontaneous']:.0f} pA"))
    line("constant: 1st pool runaway", lambda r: (
        "none in ladder" if np.isnan(_ceiling(r["table"], "current")["first_runaway"])
        else f"{_ceiling(r['table'], 'current')['first_runaway']:.0f} pA"))
    line("poisson: usable max (Hz)", lambda r: f"{_ceiling(r['table'], 'poisson')['usable_max']:.0f}")
    line("poisson: 1st spontaneous", lambda r: (
        "none in ladder" if np.isnan(_ceiling(r["table"], "poisson")["first_spontaneous"])
        else f"{_ceiling(r['table'], 'poisson')['first_spontaneous']:.0f} Hz"))

    print("\n  -- IN21A004 bodyId 800802: is it still the dominant broadcast relay? --")
    line("LF MNs contacted / 64", lambda r: (
        "absent" if not r["broadcast"]["in21a004"]["present"]
        else f"{r['broadcast']['in21a004']['n_lf_mn']}"))
    line("rank by breadth", lambda r: (
        "absent" if not r["broadcast"]["in21a004"]["present"]
        else f"{r['broadcast']['in21a004']['rank_breadth']} of "
             f"{r['broadcast']['in21a004']['n_ranked']:,}"))
    line("summed PSP onto 52 (mV)", lambda r: (
        "absent" if not r["broadcast"]["in21a004"]["present"]
        else f"{r['broadcast']['in21a004']['psp_mV']:+.2f}"))
    line("rank by excitatory PSP", lambda r: (
        "absent" if not r["broadcast"]["in21a004"]["present"]
        else f"{r['broadcast']['in21a004']['rank_exc_psp']} of "
             f"{r['broadcast']['in21a004']['n_ranked']:,}"))

    print("\n  -- is IN21A004 the broadest CLOSER in the run? (its own synapses never "
          "change;\n     what can change is whether a broader closer joins it) --")
    for tag in ("current 0", "current 125"):
        def broadest(r, tag=tag):
            t = r.get("closers", {}).get(tag)
            if t is None or t.empty:
                return "no closers"
            top = t.iloc[0]
            return f"{top['type']} {int(top['n_lf_mn'])}/64"
        def in21_rank(r, tag=tag):
            t = r.get("closers", {}).get(tag)
            if t is None or t.empty:
                return "no closers"
            hit = t[t["bodyId"] == IN21A004_BODYID]
            if hit.empty:
                return "did not fire"
            n = int(hit.iloc[0]["n_lf_mn"])
            return f"#{int((t['n_lf_mn'] > n).sum()) + 1} of {len(t)}"
        line(f"[{tag}] broadest closer", broadest)
        line(f"[{tag}] IN21A004 rank", in21_rank)
        line(f"[{tag}] broadest EXC closer", lambda r, tag=tag: (
            "no closers" if (t := r.get("closers", {}).get(tag)) is None or t.empty
            else ("none excitatory" if (e := t[t["psp_mV"] > 0]).empty
                  else f"{e.iloc[0]['type']} {int(e.iloc[0]['n_lf_mn'])}/64")))

    print("\n  -- L3 outbound: DNa02's rank among the DNs (signed PSP onto interneurons) --")
    for bid in DNA02_BODYIDS:
        line(f"DNa02 {bid} rank", lambda r, bid=bid: (
            "absent" if r["dns"]["lf64"]["named"][("DNa02", bid)] is None
            else f"{r['dns']['lf64']['named'][('DNa02', bid)]['rank']} of "
                 f"{r['dns']['lf64']['n_ranked']:,}"))
        line(f"DNa02 {bid} PSP (mV)", lambda r, bid=bid: (
            "absent" if r["dns"]["lf64"]["named"][("DNa02", bid)] is None
            else f"{r['dns']['lf64']['named'][('DNa02', bid)]['psp_mV']:+.1f}"))

    print("\n  -- L3 outbound: the issue's top-6, re-ranked per policy --")
    for label, bid in L3_TOP6:
        line(f"{label} {bid}", lambda r, bid=bid: (
            "absent" if r["dns"]["lf64"]["named"][(label, bid)] is None
            else f"#{r['dns']['lf64']['named'][(label, bid)]['rank']} "
                 f"{r['dns']['lf64']['named'][(label, bid)]['psp_mV']:+.0f} mV"))

    print("\n  -- L3 outbound: top-6 as measured under each policy --")
    for p in order:
        top = cols[p]["dns"]["lf64"]["top"][:6]
        print(f"    policy {p}: " + ", ".join(
            f"{t['type']} {t['bodyId']} {t['psp_mV']:+.0f}" for t in top
        ))

    print("\n  -- who fires: newly active / newly silent vs policy A, 0 pA live run --")
    if "A" in results:
        base = _row(results["A"]["table"], "current", 0.0)
        base_set = set(base["downstream_idx"]) if base is not None else set()
        for p in order:
            row = _row(cols[p]["table"], "current", 0.0)
            if row is None:
                print(f"    policy {p}: 0 pA row missing")
                continue
            s = set(row["downstream_idx"])
            print(f"    policy {p}: {len(s):5d} neurons fired downstream  "
                  f"(+{len(s - base_set)} newly active, -{len(base_set - s)} newly silent "
                  f"vs policy A)")
        print("    (driven pool and 41 afferents excluded -- they fire by construction.)")


def run_sign_policy(quick=False, policies=("A", "B", "C")):
    """Run the three-arm sweep and print the comparison."""
    pd.set_option("display.width", 240)

    print("=" * 92)
    print("Does Level 1 depend on how we sign `unclear`?  Three policies, one "
          "changed value.")
    print("=" * 92)
    print("Every verdict is a Brian2 SpikeMonitor count with real MuJoCo physics in "
          "lockstep at\ndt = 0.1 ms, a 3000-step settle, `data.act` restored between "
          "conditions, and a\nfrozen-physics control at EVERY background level.  A "
          "current is not a spike.")
    print("The sign map is IMPORTED from constants.NT_SIGN_MAP and one key is "
          "overridden;\nserotonin/octopamine/dopamine stay 0 and histamine stays -1 "
          "in all three arms.")

    results = {}
    body = None
    for policy in policies:
        out = run_policy(policy, body=body, quick=quick, verbose=True)
        body = out["body"]
        results[policy] = out

    compare(results)
    print("\n" + "=" * 92)
    print("Done.")
    print("=" * 92)
    return results
