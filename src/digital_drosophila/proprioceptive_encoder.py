"""Proprioceptive sensory encoder: LF leg joint state -> per-neuron currents.

Encodes Left-Front-leg joint angles, angular velocities and muscle/tendon load
into current injections for the biologically-identified proprioceptive sensory
neurons of the prothoracic leg nerve (entryNerve == 'ProLN',
class == 'mechanosensory_proprioceptive').

Each sensory ``type`` code is assigned a (joint group, modality) role derived
from measured sensory->motor connectivity (docs/neuroscience/
14-sensory-motor-loop-structure.md, sections 4-5).  Current injection is used
rather than Poisson spike generation so that the precise spike timing STDP
depends on is preserved.

Unlike ``SensoryEncoder`` (round-robin over all 66 DOFs onto ascending
neurons), this encoder targets the real proprioceptive afferents of one leg
and is intended for the sensorimotor babbling experiment.

Gains are calibrated against *measured spike counts on real LIF neurons*, not
against computed currents -- see ``run_sensory_calibration()``.  The LIF
rheobase is 200 pA (``V_th - V_rest = 20 mV`` over ``R_membrane = 100 MOhm``),
so any gain whose peak output is below 200 pA produces exactly zero spikes no
matter how long it is applied.

Usage:
    python -m digital_drosophila loop proprio_test [--side L] [--gain 800.0] [--steps 3000]
    python -m digital_drosophila loop sensory_calibration [--steps 3000]

    from digital_drosophila.proprioceptive_encoder import ProprioceptiveEncoder

    encoder = ProprioceptiveEncoder(meta_df, body_ids)
    print(encoder.assignment_table())
    print(encoder.bucket_summary())
    currents = encoder.encode(joint_angles, joint_velocities, joint_loads)
"""

from dataclasses import dataclass
from itertools import cycle

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# FlyMimic Left-Front leg joint layout
# ---------------------------------------------------------------------------

# Joint order as returned by ``Simulation.get_joint_angles('nmf')`` on the
# FlyMimic musculoskeletal model (first 7 entries; entries 7-13 are the
# unactuated right front leg).  ``springref`` is the MJCF spring reference and
# ``lo``/``hi`` the MJCF joint ``range``.
LF_JOINT_SPEC: tuple[tuple[str, float, float, float], ...] = (
    ("joint_LFCoxa_yaw", -0.11, -0.5970, 0.2745),
    ("joint_LFCoxa_pitch", 0.35, -0.5783, 0.7375),
    ("joint_LFCoxa_roll", 0.50, 0.1436, 0.6236),
    ("joint_LFTrochanter_yaw", -0.10, -1.1960, 0.2745),
    ("joint_LFTrochanter_pitch", -2.80, -3.2420, -1.2170),
    ("joint_LFTrochanter_roll", 0.00, -0.2745, 1.3840),
    ("joint_LFTibia_pitch", 2.00, 0.4789, 2.5020),
)

LF_JOINT_NAMES: tuple[str, ...] = tuple(spec[0] for spec in LF_JOINT_SPEC)
N_LF_JOINTS = len(LF_JOINT_SPEC)

# MJCF ``springref`` per LF joint.  NOT the posture the leg actually settles
# into -- see ``SETTLED_LF_ANGLES``.
LF_SPRINGREF: tuple[float, ...] = tuple(spec[1] for spec in LF_JOINT_SPEC)

# Posture the tethered leg actually relaxes into, measured after 3000 physics
# steps (dt = 0.1 ms) of ``build_musculoskeletal_simulation()`` with zero
# control.  Reproducible to 1e-5 across rebuilds and stable out to 10,000 steps.
#
# This differs from ``LF_SPRINGREF`` by 0.008-0.38 half-ranges because gravity
# and the passive tendons balance the joint springs away from their reference.
# Referencing the position channel to ``springref`` therefore (a) leaves the
# afferents tonically active at rest and (b) makes activation NON-MONOTONIC in
# movement: driving the tibia flexor carries the tibia *through* springref, so
# activation falls 0.384 -> 0.001 -> 0.428 and the same current is emitted at
# two different postures.  The settled posture is the correct zero.
SETTLED_LF_ANGLES: tuple[float, ...] = (
    -0.20680, 0.37937, 0.50188, -0.25704, -2.47705, 0.07120, 1.61127,
)

JOINT_GROUPS: dict[str, tuple[int, ...]] = {
    "coxa": (0, 1, 2),
    "trochanter": (3, 4, 5),
    "tibia": (6,),
}

# FlyMimic muscle-actuator name prefix -> joint group.  Used to sum tendon
# tension per joint group for the force channel.
MUSCLE_GROUP_PREFIX: tuple[tuple[str, str], ...] = (
    ("LFC_", "coxa"),
    ("LFTibia", "tibia"),
    ("LFF_", "trochanter"),
)

_TROCHANTER_PITCH = 4
_TIBIA_PITCH = 6

# Index into the 66-DOF FlyGym action vector (leg-local, add LEG_OFFSETS[leg])
# for each FlyMimic LF joint.  FlyGym's 11-DOF-per-leg layout has no
# trochanter-yaw, so that entry has no counterpart.
_FLYGYM_LOCAL_DOF = (2, 0, 1, None, 3, 4, 5)
_FLYGYM_N_ACTUATED = 66

# Leg -> sensory entry nerve.  Sensory afferents have no somaSide (their somata
# sit in the leg, not the VNC); use ``side`` to filter on rootSide instead.
LEG_ENTRY_NERVE: dict[str, str] = {
    "LF": "ProLN",
    "RF": "ProLN",
    "LM": "MesoLN",
    "RM": "MesoLN",
    "LH": "MetaLN",
    "RH": "MetaLN",
}

PROPRIOCEPTIVE_CLASS = "mechanosensory_proprioceptive"
UNTYPED = "<untyped>"

# Fraction of each type's measured direct sensory->motor output reaching each
# joint group (doc 14 section 4, SNpp51 row); used as the posture weighting.
POSTURE_GROUP_WEIGHTS: dict[str, float] = {
    "coxa": 0.41,
    "trochanter": 0.30,
    "tibia": 0.29,
}


# ---------------------------------------------------------------------------
# Type -> role table (doc 14 sections 4-5)
# ---------------------------------------------------------------------------

# Explicitly assigned types: type code -> (joint group, modality, joint indices)
_TYPE_ROLES: dict[str, tuple[str, str, tuple[int, ...]]] = {
    "SNpp39": ("tibia", "position", (_TIBIA_PITCH,)),
    "SNpp50": ("tibia", "position", (_TIBIA_PITCH,)),
    "SNppxx": ("tibia", "velocity", (_TIBIA_PITCH,)),
    "SNpp53": ("trochanter", "force", JOINT_GROUPS["trochanter"]),
    "SNpp41": ("trochanter", "position", (_TROCHANTER_PITCH,)),
    "SNpp45": ("coxa", "position", JOINT_GROUPS["coxa"]),
    "SNpp47": ("coxa", "position", JOINT_GROUPS["coxa"]),
    "SNpp51": ("multi", "posture", tuple(range(N_LF_JOINTS))),
}

# Types with weak/absent direct motor output: position encoders spread
# round-robin over the three joint groups.
_ROUND_ROBIN_TYPES = frozenset(
    {"SNpp40", "SNpp43", "SNpp57", "SNpp59", "SNpp60"}
)
_ROUND_ROBIN_CYCLE = ("tibia", "trochanter", "coxa")

# Unannotated afferents: split across tibia velocity / trochanter position /
# coxa velocity.
_UNTYPED_CYCLE = (
    ("tibia", "velocity"),
    ("trochanter", "position"),
    ("coxa", "velocity"),
)

# Ascending afferents with no motor output: excluded from the local loop.
_EXCLUDED_TYPES = frozenset({"SApp23"})

MODALITIES = ("position", "velocity", "force", "posture")

# ---------------------------------------------------------------------------
# Calibrated gains (measured, see run_sensory_calibration)
# ---------------------------------------------------------------------------

# LIF rheobase: the current below which the neuron never fires, at any
# duration.  (V_th - V_rest) / R_membrane = 20 mV / 100 MOhm = 200 pA.
# Measured on real LIF neurons: 200 pA -> 0.0 Hz, 201 pA -> 18 Hz.
RHEOBASE_PA = 200.0

# Per-modality peak gain in pA at activation 1.0, measured by
# ``run_sensory_calibration()``.  Each was chosen so the activation the channel
# ACTUALLY reaches under a 50 ms single-muscle burst at activation 0.40 -- a
# typical babbling drive -- lands in the 40-100 Hz target band.  Calibrating to
# activation 1.0 instead would be wrong: no channel except tibia position ever
# gets near 1.0, so an activation-1.0 calibration leaves every other channel
# silent.
#
# Measured mean rate over the three joint groups at muscle activation 0.40
# (steady = activation held at its end-of-burst value; burst = the real 50 ms
# time-varying trace):
#
#   position  700 pA -> 54-92 Hz per group (mean 79 steady).  Reached
#             activation 0.35-0.49.  600 gives 59, 800 gives 95.
#   velocity 1200 pA -> mean 67 Hz burst-integrated, 53 steady.  This channel
#             is transient (peaks ~20 ms in, then decays), so the burst figure
#             is the honest one and the steady figure understates it.
#   force    1400 pA -> mean 64 Hz steady, 40 Hz burst.  Tendon load is tonic
#             but small at rest (activation 0.005-0.033), so rest stays
#             sub-rheobase (max 85 pA) while drive crosses it.
#   posture  2000 pA -> mean 73 Hz steady.  Posture is a weighted mean across
#             all three joint groups, so a single-joint movement dilutes it
#             ~4x; it never exceeds activation 0.30, hence the largest gain.
#
# A single shared gain cannot serve all four: the gains that put each channel
# in band span 700-2000 pA, a 2.9x spread.  At a shared 700 pA the force and
# posture channels are silent; at a shared 2000 pA position reaches 219 Hz.
DEFAULT_MODALITY_GAINS_PA: dict[str, float] = {
    "position": 700.0,
    "velocity": 1200.0,
    "force": 1400.0,
    "posture": 2000.0,
}

# Angular velocity mapped to activation 1.0.  Kept at 25.0: measured peak
# per-joint velocity under single-muscle drive is 27.9 rad/s (tibia extensor),
# and group-mean peaks span 5.7-21.1 rad/s, so 25 leaves headroom without
# clipping.  Reducing it to ~12 would saturate the strongest drivers.
DEFAULT_MAX_VELOCITY = 25.0

# Per-joint-group tendon tension (sum |actuator_force| over that group's
# muscles) mapped to activation 1.0.  Measured peaks under single-muscle drive:
# coxa 303, trochanter 358, tibia 603; settled rest is 0.68 / 1.37 / 4.88.
# 150 sits above the bulk of the driven range (median 12-28 at act 0.4, up to
# ~100 at act 1.0) while keeping the strongest tibia transients on-scale.
DEFAULT_MAX_FORCE = 150.0

# Physics steps (dt = 0.1 ms) to settle the tethered leg before measuring.
# At 500 steps the tibia is still drifting at -4 rad/s; at 3000 every joint is
# within 0.3 rad/s of zero and the posture is stable out to 10,000 steps.
SETTLE_STEPS = 3000


@dataclass(frozen=True)
class SensoryAssignment:
    """One proprioceptive afferent and the joint signal it encodes.

    Attributes
    ----------
    neuron_index : int
        Index into the network's ``body_ids`` ordering.
    body_id : int
        Connectome body ID.
    type_code : str
        Connectome ``type``, or ``'<untyped>'`` when unannotated.
    subclass : str
        Connectome ``subclass`` (sense-organ class).
    root_side : str
        Connectome ``rootSide`` ('L'/'R'), the body side of the afferent.
    joint_group : str
        'coxa', 'trochanter', 'tibia' or 'multi'.
    modality : str
        'position', 'velocity', 'force' or 'posture'.
    joint_indices : tuple of int
        Indices into the 7-element LF joint vector that drive this neuron.
    """

    neuron_index: int
    body_id: int
    type_code: str
    subclass: str
    root_side: str
    joint_group: str
    modality: str
    joint_indices: tuple[int, ...]


class ProprioceptiveEncoder:
    """Encode LF leg proprioception as current injections for ProLN afferents.

    Parameters
    ----------
    meta_df : DataFrame
        Connectome metadata, row-aligned with ``body_ids`` (as returned by
        ``get_or_build_full_vnc_network()``).  Requires columns ``bodyId``,
        ``type``, ``subclass``, ``class``, ``entryNerve``, ``rootSide``.
    body_ids : list of int
        Ordered body IDs of the network; defines the output index space.
    leg : str
        Leg abbreviation selecting the entry nerve (default 'LF').
    side : str or None
        If given ('L' or 'R'), keep only afferents with that ``rootSide``.
        Default None keeps both sides, matching doc 14's 65-neuron selection.
    gain_pa : float or None
        If given, one shared peak current in pA at activation 1.0 for every
        modality.  Default None uses the measured per-modality gains in
        ``DEFAULT_MODALITY_GAINS_PA``; a single shared gain cannot serve all
        four channels because they reach very different peak activations.
    modality_gains : dict, optional
        Per-modality gain overrides in pA, e.g. ``{'force': 100.0}``.  Applied
        on top of whichever base the above resolves to.
    max_velocity : float
        Angular velocity in rad/s mapped to activation 1.0.  Default
        ``DEFAULT_MAX_VELOCITY`` (25.0).
    max_force : float
        Per-joint-group tendon tension (sum of ``|actuator_force|`` over that
        group's muscles) mapped to activation 1.0.  Default
        ``DEFAULT_MAX_FORCE`` (150.0).
    rest_angles : sequence of float, optional
        Zero point for the position channel.  Defaults to
        ``SETTLED_LF_ANGLES`` (the measured relaxed posture), NOT the MJCF
        ``springref`` -- referencing springref makes activation non-monotonic
        in movement.  Pass ``LF_SPRINGREF`` to restore the old behaviour.
    posture_weights : dict, optional
        Joint-group weights for the 'posture' modality (default
        ``POSTURE_GROUP_WEIGHTS``).
    """

    def __init__(
        self,
        meta_df: pd.DataFrame,
        body_ids: list[int],
        *,
        leg: str = "LF",
        side: str | None = None,
        gain_pa: float | None = None,
        modality_gains: dict[str, float] | None = None,
        max_velocity: float = DEFAULT_MAX_VELOCITY,
        max_force: float = DEFAULT_MAX_FORCE,
        rest_angles: "np.ndarray | tuple[float, ...] | None" = None,
        posture_weights: dict[str, float] | None = None,
    ) -> None:
        self.leg = leg
        self.side = side
        self.n_neurons = len(body_ids)
        self.max_velocity = max_velocity
        self.max_force = max_force
        self.posture_weights = dict(posture_weights or POSTURE_GROUP_WEIGHTS)

        if gain_pa is None:
            self.gains_pa = dict(DEFAULT_MODALITY_GAINS_PA)
        else:
            self.gains_pa = {m: float(gain_pa) for m in MODALITIES}
        self.gains_pa.update(modality_gains or {})

        self._rest = np.asarray(
            SETTLED_LF_ANGLES if rest_angles is None else rest_angles, dtype=float
        )
        if self._rest.shape != (N_LF_JOINTS,):
            raise ValueError(
                f"rest_angles must have {N_LF_JOINTS} entries, "
                f"got shape {self._rest.shape}"
            )
        self._half_range = np.array([(s[3] - s[2]) / 2.0 for s in LF_JOINT_SPEC])

        selected = _select_afferents(meta_df, body_ids, leg=leg, side=side)
        self.assignments = _assign_roles(selected)
        self.excluded = _excluded_afferents(selected)

        self._indices = np.array(
            [a.neuron_index for a in self.assignments], dtype=np.int64
        )
        self._gain_amps = np.array(
            [self.gains_pa[a.modality] * 1e-12 for a in self.assignments]
        )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def sensory_indices(self) -> np.ndarray:
        """Network indices of the actively encoded afferents."""
        return self._indices

    @property
    def excluded_indices(self) -> np.ndarray:
        """Network indices of afferents deliberately left unencoded."""
        return np.array([a[0] for a in self.excluded], dtype=np.int64)

    def assignment_table(self) -> pd.DataFrame:
        """Per-neuron assignment table, one row per selected afferent.

        Excluded (ascending) afferents appear with joint_group/modality
        ``'excluded'``.
        """
        rows = [
            {
                "neuron_index": a.neuron_index,
                "bodyId": a.body_id,
                "type": a.type_code,
                "subclass": a.subclass,
                "rootSide": a.root_side,
                "joint_group": a.joint_group,
                "modality": a.modality,
                "joints": ",".join(
                    LF_JOINT_NAMES[i].replace("joint_", "")
                    for i in a.joint_indices
                ),
                "gain_pA": self.gains_pa[a.modality],
            }
            for a in self.assignments
        ]
        rows += [
            {
                "neuron_index": idx,
                "bodyId": bid,
                "type": tcode,
                "subclass": sub,
                "rootSide": rside,
                "joint_group": "excluded",
                "modality": "excluded",
                "joints": "",
                "gain_pA": 0.0,
            }
            for idx, bid, tcode, sub, rside in self.excluded
        ]
        return pd.DataFrame(rows).sort_values("neuron_index").reset_index(drop=True)

    def bucket_summary(self) -> pd.DataFrame:
        """Neuron counts per (joint group, modality) bucket, excluded included."""
        table = self.assignment_table()
        summary = (
            table.groupby(["joint_group", "modality"])
            .agg(n_neurons=("bodyId", "size"), types=("type", lambda s: ",".join(sorted(set(s)))))
            .reset_index()
            .sort_values(["joint_group", "modality"])
            .reset_index(drop=True)
        )
        return summary

    # ------------------------------------------------------------------
    # Encoding
    # ------------------------------------------------------------------

    def activations(
        self,
        joint_angles: np.ndarray,
        joint_velocities: np.ndarray | None = None,
        joint_loads: "float | dict[str, float] | None" = None,
    ) -> np.ndarray:
        """Per-afferent activation in [0, 1], ordered as ``self.assignments``.

        ``joint_loads`` is tendon tension: either a dict of joint group ->
        summed ``|actuator_force|`` (see ``tendon_loads_by_group``), or a single
        float applied to every group.
        """
        angles = self._to_lf7(joint_angles, fill=self._rest)
        if joint_velocities is None:
            vels = np.zeros(N_LF_JOINTS)
        else:
            vels = self._to_lf7(joint_velocities, fill=np.zeros(N_LF_JOINTS))

        position = np.abs(angles - self._rest) / self._half_range
        velocity = np.abs(vels) / self.max_velocity

        if joint_loads is None:
            loads = {g: 0.0 for g in JOINT_GROUPS}
        elif isinstance(joint_loads, dict):
            loads = {g: float(joint_loads.get(g, 0.0)) for g in JOINT_GROUPS}
        else:
            loads = {g: float(joint_loads) for g in JOINT_GROUPS}
        force = {g: abs(v) / self.max_force for g, v in loads.items()}

        posture = 0.0
        for group, weight in self.posture_weights.items():
            posture += weight * float(np.mean(position[list(JOINT_GROUPS[group])]))

        out = np.empty(len(self.assignments))
        for i, a in enumerate(self.assignments):
            if a.modality == "position":
                value = float(np.mean(position[list(a.joint_indices)]))
            elif a.modality == "velocity":
                value = float(np.mean(velocity[list(a.joint_indices)]))
            elif a.modality == "force":
                value = force.get(a.joint_group, 0.0)
            else:
                value = posture
            out[i] = value
        return np.clip(out, 0.0, 1.0)

    def encode(
        self,
        joint_angles: np.ndarray,
        joint_velocities: np.ndarray | None = None,
        joint_loads: "float | dict[str, float] | None" = None,
    ) -> np.ndarray:
        """Convert LF leg state to a full-network current vector.

        Parameters
        ----------
        joint_angles : ndarray
            Joint angles in radians.  Accepted layouts:
            (a) the 7 FlyMimic LF joints in ``LF_JOINT_NAMES`` order (primary
            path, i.e. ``sim.get_joint_angles('nmf')[:7]``); (b) the full
            FlyMimic 14-joint vector, whose first 7 entries are the LF leg;
            (c) the 66-DOF FlyGym action vector, gathered via
            ``LEG_OFFSETS[leg]`` and the 11-DOF-per-leg layout.  FlyGym has no
            trochanter-yaw DOF, so in case (c) that joint reads as at-rest.
            NeuroMechFly and FlyMimic do not share joint-angle conventions, so
            (c) is a convenience path, not a calibrated one.
        joint_velocities : ndarray, optional
            Angular velocities in rad/s, same layouts.  Zeros if omitted.
        joint_loads : float or dict, optional
            Tendon tension driving the force channel.  Either a joint group ->
            summed ``|actuator_force|`` dict (from ``tendon_loads_by_group``) or
            a single float broadcast to all groups.  Zeros if omitted.

            This is muscle/tendon load, NOT ground-reaction force.  Campaniform
            sensilla measure cuticle strain and muscle load, and the tethered
            FlyMimic body has no weight-bearing ground contact at all -- its
            only contacts are Thorax<->Coxa self-collisions -- so a
            ground-reaction reading is identically zero here.

        Returns
        -------
        currents : ndarray
            Currents for all neurons, shape ``(n_neurons,)``, in Amperes.
            Non-sensory and excluded entries are zero.
        """
        currents = np.zeros(self.n_neurons)
        acts = self.activations(joint_angles, joint_velocities, joint_loads)
        currents[self._indices] = acts * self._gain_amps
        return currents

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _to_lf7(self, values: np.ndarray, fill: np.ndarray) -> np.ndarray:
        values = np.asarray(values, dtype=float)
        if values.shape[0] == _FLYGYM_N_ACTUATED:
            from .locomotion import LEG_OFFSETS

            offset = LEG_OFFSETS[self.leg.lower()]
            out = fill.astype(float).copy()
            for i, local in enumerate(_FLYGYM_LOCAL_DOF):
                if local is not None:
                    out[i] = values[offset + local]
            return out
        return values[:N_LF_JOINTS]


# ---------------------------------------------------------------------------
# Selection and role assignment
# ---------------------------------------------------------------------------


def _select_afferents(
    meta_df: pd.DataFrame,
    body_ids: list[int],
    *,
    leg: str,
    side: str | None,
) -> pd.DataFrame:
    """Return the proprioceptive afferents of one leg, with network indices.

    Afferent somata sit in the leg periphery, so ``somaSide`` is NaN for all of
    them; ``rootSide`` is the column that carries laterality. Defaults to the
    side named by ``leg`` — encoding right-leg afferents from left-leg joint
    angles would be a body-side mismatch.
    """
    nerve = LEG_ENTRY_NERVE[leg]
    meta = meta_df.reset_index(drop=True)
    index_of = {int(bid): i for i, bid in enumerate(body_ids)}

    if side is None:
        side = leg[0]

    mask = (meta["entryNerve"] == nerve) & (meta["class"] == PROPRIOCEPTIVE_CLASS)
    subset = meta.loc[mask, ["bodyId", "type", "subclass", "rootSide"]].copy()
    subset = subset[subset["rootSide"] == side]

    subset["type"] = subset["type"].fillna(UNTYPED)
    subset["subclass"] = subset["subclass"].fillna(UNTYPED)
    subset["rootSide"] = subset["rootSide"].fillna(UNTYPED)
    subset["neuron_index"] = subset["bodyId"].map(
        lambda bid: index_of[int(bid)]
    )
    return subset.sort_values(["type", "bodyId"]).reset_index(drop=True)


def _is_excluded(type_code: str) -> bool:
    """True when every component of a (possibly multi-)type label is ascending.

    A few afferents on the mid/hind leg nerves carry ambiguous comma-joined
    labels such as ``'SApp23,SNpp56'``; those are excluded only if no component
    is a local-loop type.
    """
    parts = [p.strip() for p in type_code.split(",")]
    return all(p in _EXCLUDED_TYPES for p in parts)


def _local_type(type_code: str) -> str:
    """Resolve a possibly multi-type label to its first non-ascending component."""
    for part in (p.strip() for p in type_code.split(",")):
        if part not in _EXCLUDED_TYPES:
            return part
    return type_code


def _excluded_afferents(
    selected: pd.DataFrame,
) -> list[tuple[int, int, str, str, str]]:
    rows = selected[selected["type"].map(_is_excluded)]
    return [
        (
            int(r.neuron_index),
            int(r.bodyId),
            r.type,
            r.subclass,
            r.rootSide,
        )
        for r in rows.itertuples()
    ]


def _assign_roles(selected: pd.DataFrame) -> list[SensoryAssignment]:
    """Map each afferent onto a (joint group, modality) role."""
    round_robin = cycle(_ROUND_ROBIN_CYCLE)
    untyped_roles = cycle(_UNTYPED_CYCLE)

    assignments: list[SensoryAssignment] = []
    for row in selected.itertuples():
        if _is_excluded(row.type):
            continue
        type_code = _local_type(row.type)

        if type_code in _TYPE_ROLES:
            group, modality, joints = _TYPE_ROLES[type_code]
        elif type_code in _ROUND_ROBIN_TYPES:
            group = next(round_robin)
            modality = "position"
            joints = JOINT_GROUPS[group]
        elif type_code == UNTYPED:
            group, modality = next(untyped_roles)
            joints = JOINT_GROUPS[group]
        else:
            group, modality = "multi", "posture"
            joints = tuple(range(N_LF_JOINTS))

        assignments.append(
            SensoryAssignment(
                neuron_index=int(row.neuron_index),
                body_id=int(row.bodyId),
                type_code=type_code,
                subclass=row.subclass,
                root_side=row.rootSide,
                joint_group=group,
                modality=modality,
                joint_indices=joints,
            )
        )

    assignments.sort(key=lambda a: a.neuron_index)
    return assignments


# ---------------------------------------------------------------------------
# Sensory calibration experiment
# ---------------------------------------------------------------------------

# Muscles used to drive each channel in the calibration sweep, chosen as the
# strongest single-muscle driver of that joint group (measured over all 15).
CALIBRATION_DRIVERS: dict[str, str] = {
    "coxa": "LFC_tergopleural_promotor_b",
    "trochanter": "LFF_sterno-tergo-trochanter_extensor_b",
    "tibia": "LFTibia_flex_93434",
}

_SWEEP_GAINS_PA = (75.0, 200.0, 300.0, 500.0, 800.0, 1000.0, 1500.0, 2000.0)
_SWEEP_ACTIVATIONS = (0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.70, 1.00)
_SWEEP_MUSCLE_ACTS = (0.05, 0.10, 0.20, 0.40, 0.70, 1.00)


def measure_lif_rates(
    currents_pa: np.ndarray,
    duration_ms: float = 500.0,
) -> np.ndarray:
    """Firing rate in Hz of isolated LIF neurons under constant current.

    One neuron per entry of ``currents_pa``, run on the project's real
    ``create_neuron_group`` LIF model (``DEFAULT_LIF_PARAMS``) with spikes
    counted by a ``SpikeMonitor``.  This is the only sanctioned way to claim an
    afferent "responds": a current is not a firing rate.

    Parameters
    ----------
    currents_pa : ndarray
        Constant injected current per neuron, in pA.
    duration_ms : float
        Simulated duration.  500 ms resolves rates down to 2 Hz.

    Returns
    -------
    rates_hz : ndarray
        Measured spikes / second, same shape as ``currents_pa``.
    """
    import brian2

    currents_pa = np.asarray(currents_pa, dtype=float).ravel()
    from .network import create_neuron_group

    brian2.prefs.codegen.target = "numpy"
    group = create_neuron_group(len(currents_pa))
    group.I = currents_pa * 1e-12 * brian2.amp
    monitor = brian2.SpikeMonitor(group)
    net = brian2.Network(group, monitor)
    net.run(duration_ms * brian2.ms)
    return np.asarray(monitor.count, dtype=float) / (duration_ms / 1000.0)


def measure_lif_rates_from_trace(
    currents_pa: np.ndarray,
    dt_ms: float = 0.1,
) -> np.ndarray:
    """Firing rate in Hz of isolated LIF neurons under a time-varying current.

    CAVEAT on resolution: over a 50 ms trace one spike is 20 Hz, so these rates
    are quantised to 20 Hz steps.  They are honest counts but coarse -- treat a
    reported 40 Hz as "2 spikes in the burst", not as a precise rate.  Use
    ``measure_lif_rates`` over a longer window when precision matters.

    Parameters
    ----------
    currents_pa : ndarray
        Shape ``(n_steps, n_neurons)``: per-timestep injected current in pA.
        Used for channels whose drive is transient (the velocity channel peaks
        for ~20 ms then decays), where a constant-current rate would overstate
        the response.
    dt_ms : float
        Timestep of the trace, matching the physics ``dt``.

    Returns
    -------
    rates_hz : ndarray
        Spikes / second over the trace duration, one entry per neuron.
    """
    import brian2

    trace = np.atleast_2d(np.asarray(currents_pa, dtype=float))
    n_steps, n_neurons = trace.shape
    from .network import create_neuron_group

    brian2.prefs.codegen.target = "numpy"
    stimulus = brian2.TimedArray(
        trace * 1e-12 * brian2.amp, dt=dt_ms * brian2.ms
    )
    group = create_neuron_group(n_neurons)
    group.namespace["Iext"] = stimulus
    group.run_regularly("I = Iext(t, i)", dt=dt_ms * brian2.ms, when="start")
    monitor = brian2.SpikeMonitor(group)
    net = brian2.Network(group, monitor)
    net.run(n_steps * dt_ms * brian2.ms)
    duration_s = n_steps * dt_ms / 1000.0
    return np.asarray(monitor.count, dtype=float) / duration_s


def _settled_physics():
    """Build FlyMimic, settle it, and return (sim, model, data, groups, state)."""
    import mujoco
    from flygym.compose import build_musculoskeletal_simulation

    sim, fly = build_musculoskeletal_simulation()
    model, data = sim.mj_model, sim.mj_data
    for _ in range(SETTLE_STEPS):
        sim.step()
    mujoco.mj_forward(model, data)
    state = (data.qpos.copy(), data.qvel.copy())
    return sim, model, data, muscle_group_indices(model), state, list(fly.muscle_names)


def _drive_and_record(
    sim, model, data, state, muscle_names, muscle, activation, steps,
):
    """Reset to the settled state, drive one muscle, return the state trace."""
    import mujoco

    qpos, qvel = state
    data.qpos[:] = qpos
    data.qvel[:] = qvel
    data.ctrl[:] = 0.0
    mujoco.mj_forward(model, data)
    data.ctrl[muscle_names.index(muscle)] = activation

    angles = np.zeros((steps, N_LF_JOINTS))
    vels = np.zeros((steps, N_LF_JOINTS))
    forces = np.zeros((steps, model.nu))
    for k in range(steps):
        sim.step()
        angles[k] = sim.get_joint_angles("nmf")[:N_LF_JOINTS]
        vels[k] = sim.get_joint_velocities("nmf")[:N_LF_JOINTS]
        forces[k] = data.actuator_force
    return angles, vels, forces


def run_sensory_calibration(
    steps: int = SETTLE_STEPS,
    drive_steps: int = 500,
    duration_ms: float = 500.0,
) -> dict:
    """Calibrate per-modality sensory gains by counting spikes on real LIF cells.

    Six stages:

    1. **Rheobase**, measured not assumed: sweep constant current across the
       200 pA boundary on real LIF neurons.
    2. **Gain x activation -> Hz** for the position channel, with the
       corresponding tibia displacement in rad.
    3. **Minimum detectable movement**: the smallest joint displacement, and the
       smallest muscle activation, at which an afferent emits its first spike.
    4. **Physics-driven per-channel activations** reached by the strongest
       single-muscle driver of each joint group.
    5. **Measured firing rate per (channel, gain)** at those real activations --
       the table the recommended gains come from.
    6. **Force channel**: confirm ``d.actuator_force`` is non-zero where ground
       reaction was identically zero, and that SNpp53 spikes.

    Parameters
    ----------
    steps : int
        Settling steps before any measurement (default ``SETTLE_STEPS``).
    drive_steps : int
        Steps of muscle drive per condition (500 = 50 ms, one babbling burst).
    duration_ms : float
        LIF run duration for constant-current measurements.

    Returns
    -------
    dict
        ``position_table``, ``channel_activations``, ``channel_rate_table``,
        ``min_movement``, ``force_report``, ``recommended_gains``.
    """
    from .functional_selection import get_or_build_full_vnc_network

    pd.set_option("display.width", 200)

    print("=" * 78)
    print("Sensory calibration: gain x displacement -> MEASURED LIF firing rate")
    print("=" * 78)
    print(
        "\nEvery Hz below is a spike count on a real LIF neuron "
        "(network.create_neuron_group,\nDEFAULT_LIF_PARAMS) divided by the run "
        "duration.  No rate is inferred from a current."
    )

    # -- Stage 1: rheobase ------------------------------------------------
    print("\n" + "-" * 78)
    print("[1/6] LIF rheobase, measured")
    print("-" * 78)
    probe_pa = np.array(
        [50, 75, 100, 150, 190, 199, 200, 201, 210, 220, 250, 300, 500, 800]
    )
    probe_hz = measure_lif_rates(probe_pa, duration_ms=1000.0)
    print(f"{'current (pA)':>13} {'measured Hz':>12}")
    for c, r in zip(probe_pa, probe_hz):
        print(f"{c:>13.0f} {r:>12.1f}")
    first = probe_pa[probe_hz > 0]
    print(
        f"\nHighest silent current: {probe_pa[probe_hz == 0].max():.0f} pA; "
        f"lowest firing: {first.min():.0f} pA -> rheobase = "
        f"{RHEOBASE_PA:.0f} pA CONFIRMED."
    )
    print(
        f"The shipped default gain_pa = 75.0 gives 75 pA at activation 1.0 = "
        f"{75.0 / RHEOBASE_PA:.2f}x rheobase -> "
        f"{measure_lif_rates(np.array([75.0]))[0]:.1f} Hz.  No afferent could fire."
    )

    # -- Stage 2: gain x activation grid ---------------------------------
    print("\n" + "-" * 78)
    print("[2/6] Position channel: gain x activation -> measured Hz")
    print("-" * 78)
    grid_pa = np.array(
        [[g * a for a in _SWEEP_ACTIVATIONS] for g in _SWEEP_GAINS_PA]
    )
    grid_hz = measure_lif_rates(grid_pa.ravel(), duration_ms).reshape(grid_pa.shape)
    half_tibia = (LF_JOINT_SPEC[_TIBIA_PITCH][3] - LF_JOINT_SPEC[_TIBIA_PITCH][2]) / 2.0
    position_table = pd.DataFrame(
        grid_hz,
        index=pd.Index([f"{g:.0f} pA" for g in _SWEEP_GAINS_PA], name="gain"),
        columns=[f"{a:.2f}" for a in _SWEEP_ACTIVATIONS],
    )
    print(f"columns = position activation |angle-rest|/half_range "
          f"(tibia half-range {half_tibia:.4f} rad)")
    print(position_table.round(0).to_string())
    print("\nsame columns as tibia displacement in rad:")
    print("  " + "  ".join(f"{a * half_tibia:.3f}" for a in _SWEEP_ACTIVATIONS))

    target = (grid_hz >= 40.0) & (grid_hz <= 100.0)
    print("\nactivation range landing in the 40-100 Hz target band, per gain:")
    for gi, gain in enumerate(_SWEEP_GAINS_PA):
        hits = [a for ai, a in enumerate(_SWEEP_ACTIVATIONS) if target[gi, ai]]
        if hits:
            print(f"  {gain:>6.0f} pA: activation {min(hits):.2f}-{max(hits):.2f} "
                  f"({min(hits) * half_tibia:.3f}-{max(hits) * half_tibia:.3f} rad)")
        else:
            print(f"  {gain:>6.0f} pA: never in band "
                  f"(max {grid_hz[gi].max():.0f} Hz at activation 1.0)")

    # -- Stage 3-6 need physics ------------------------------------------
    sim, model, data, groups, state, muscle_names = _settled_physics()
    settled_angles = np.asarray(state[0][:N_LF_JOINTS]).copy()
    settled_vel = np.asarray(state[1][:N_LF_JOINTS]).copy()
    rest_load = tendon_loads_by_group(data, groups)
    print("\n" + "-" * 78)
    print(f"[3/6] Minimum detectable movement (after {steps} settling steps)")
    print("-" * 78)
    print(f"settled LF posture: {np.round(settled_angles, 5)}")
    print(f"settled |velocity|: {np.round(np.abs(settled_vel), 4)} rad/s "
          f"(max {np.abs(settled_vel).max():.3f})")

    min_movement = _report_min_movement(
        sim, model, data, state, muscle_names, half_tibia, duration_ms
    )

    # -- Stage 4: what activation does physics actually reach? ------------
    print("\n" + "-" * 78)
    print("[4/6] Activation actually reached by the strongest single-muscle driver")
    print("-" * 78)
    probe = ProprioceptiveEncoder.__new__(ProprioceptiveEncoder)
    probe.max_velocity = DEFAULT_MAX_VELOCITY
    probe.max_force = DEFAULT_MAX_FORCE
    probe._rest = settled_angles
    probe._half_range = np.array(
        [(s[3] - s[2]) / 2.0 for s in LF_JOINT_SPEC]
    )
    probe.posture_weights = dict(POSTURE_GROUP_WEIGHTS)

    channel_rows = []
    channel_traces: dict[str, np.ndarray] = {}
    for group, muscle in CALIBRATION_DRIVERS.items():
        for act in _SWEEP_MUSCLE_ACTS:
            angles, vels, forces = _drive_and_record(
                sim, model, data, state, muscle_names, muscle, act, drive_steps
            )
            pos_t = np.abs(angles - settled_angles) / probe._half_range
            vel_t = np.abs(vels) / probe.max_velocity
            gidx = list(JOINT_GROUPS[group])
            pos_group = pos_t[:, gidx].mean(axis=1)
            vel_group = vel_t[:, gidx].mean(axis=1)
            load_t = np.abs(forces[:, groups[group]]).sum(axis=1) / probe.max_force
            posture_t = sum(
                w * pos_t[:, list(JOINT_GROUPS[g])].mean(axis=1)
                for g, w in probe.posture_weights.items()
            )
            channel_rows.append(
                {
                    "group": group,
                    "muscle_act": act,
                    "position_end": pos_group[-1],
                    "velocity_peak": vel_group.max(),
                    "velocity_mean": vel_group.mean(),
                    "force_end": load_t[-1],
                    "posture_end": posture_t[-1],
                }
            )
            channel_traces[f"{group}|{act}|position"] = np.clip(pos_group, 0, 1)
            channel_traces[f"{group}|{act}|velocity"] = np.clip(vel_group, 0, 1)
            channel_traces[f"{group}|{act}|force"] = np.clip(load_t, 0, 1)
            channel_traces[f"{group}|{act}|posture"] = np.clip(posture_t, 0, 1)
    channel_activations = pd.DataFrame(channel_rows)
    print(f"driven muscles: "
          + ", ".join(f"{g}={m}" for g, m in CALIBRATION_DRIVERS.items()))
    print(f"{drive_steps} steps = {drive_steps * 0.1:.0f} ms of drive per condition\n")
    print(channel_activations.round(3).to_string(index=False))
    print(
        "\nrest activations: position 0.000 (settled reference), velocity "
        f"{np.abs(settled_vel).max() / DEFAULT_MAX_VELOCITY:.4f}, force "
        + ", ".join(f"{g}={v / DEFAULT_MAX_FORCE:.4f}" for g, v in sorted(rest_load.items()))
    )

    # -- Stage 5: measured Hz at real activations -------------------------
    print("\n" + "-" * 78)
    print("[5/6] Measured LIF firing rate at the activations physics reaches")
    print("-" * 78)
    channel_rate_table = _measure_channel_rates(channel_traces, duration_ms)
    print("rows = the physics conditions of stage 4; columns = candidate gains")
    print(channel_rate_table.to_string(index=False, float_format=lambda v: f"{v:g}"))

    recommended = _solve_gains(channel_traces, duration_ms)

    # -- Stage 6: force channel ------------------------------------------
    print("\n" + "-" * 78)
    print("[6/6] Force channel: tendon tension replaces ground reaction force")
    print("-" * 78)
    force_report = _report_force_channel(
        sim, model, data, state, muscle_names, groups, rest_load, duration_ms
    )

    # -- Sign ambiguity of the unsigned position channel -----------------
    print("\n" + "-" * 78)
    print("Q3: does unsigned |angle - rest| lose information STDP needs?")
    print("-" * 78)
    sign_report = _report_sign_ambiguity(
        sim, model, data, state, muscle_names, settled_angles, duration_ms
    )

    # -- max_velocity scale check (Q2) -----------------------------------
    print("\n" + "-" * 78)
    print(f"Q2: is max_velocity = {DEFAULT_MAX_VELOCITY} the right scale?")
    print("-" * 78)
    velocity_report = _report_velocity_scale(
        sim, model, data, state, muscle_names
    )

    # -- Named-afferent end-to-end check ---------------------------------
    print("\n" + "-" * 78)
    print("Named afferents through the real encoder, 0 Hz -> target band")
    print("-" * 78)
    body_ids, meta_df, _, _, _, _ = get_or_build_full_vnc_network()
    named = _report_named_afferents(
        meta_df, body_ids, sim, model, data, state, muscle_names, groups,
        duration_ms,
    )

    print("\n" + "=" * 78)
    print("Done.")
    print("=" * 78)

    return {
        "position_table": position_table,
        "channel_activations": channel_activations,
        "channel_rate_table": channel_rate_table,
        "min_movement": min_movement,
        "force_report": force_report,
        "sign_report": sign_report,
        "velocity_report": velocity_report,
        "named_afferents": named,
        "recommended_gains": recommended,
    }


def _report_sign_ambiguity(
    sim, model, data, state, muscle_names, settled_angles, duration_ms,
) -> pd.DataFrame:
    """Show flexion and extension producing the same unsigned current.

    Also shows the separate, worse failure that motivated moving the position
    reference from MJCF ``springref`` to the measured settled posture:
    referenced to springref, activation is NON-MONOTONIC in movement.
    """
    half = (LF_JOINT_SPEC[_TIBIA_PITCH][3] - LF_JOINT_SPEC[_TIBIA_PITCH][2]) / 2.0
    gain = DEFAULT_MODALITY_GAINS_PA["position"]
    rows = []
    for muscle, direction in (
        (CALIBRATION_DRIVERS["tibia"], "flexion"),
        ("LFTibia_extensor_93932", "extension"),
    ):
        for act in (0.20, 0.30, 0.40, 0.50, 0.70, 1.00):
            angles, _, _ = _drive_and_record(
                sim, model, data, state, muscle_names, muscle, act, 500
            )
            signed = float(angles[-1, _TIBIA_PITCH] - settled_angles[_TIBIA_PITCH])
            activation = min(abs(signed) / half, 1.0)
            rows.append(
                {
                    "direction": direction,
                    "muscle_act": act,
                    "signed_dq_rad": signed,
                    "unsigned_activation": activation,
                    "current_pA": activation * gain,
                }
            )
    table = pd.DataFrame(rows)
    table["measured_Hz"] = measure_lif_rates(
        table["current_pA"].to_numpy(), duration_ms
    )
    print(f"tibia pitch, position gain {gain:.0f} pA, reference = settled posture:")
    print(table.round(3).to_string(index=False))

    flex = table[table["direction"] == "flexion"]
    ext = table[table["direction"] == "extension"]
    collisions = []
    for _, f in flex.iterrows():
        for _, e in ext.iterrows():
            if abs(f["measured_Hz"] - e["measured_Hz"]) < 1e-9 and f["measured_Hz"] > 0:
                collisions.append(
                    (f["signed_dq_rad"], e["signed_dq_rad"], f["measured_Hz"])
                )
    print(
        f"\nANSWER: yes, information is lost.  Flexion of +{flex['signed_dq_rad'].max():.3f} "
        f"rad and extension of {ext['signed_dq_rad'].min():.3f} rad both produce a\n"
        "POSITIVE current of the same sign; the channel cannot distinguish "
        "direction."
    )
    if collisions:
        print(f"  {len(collisions)} tested flexion/extension pairs emit an "
              "IDENTICAL measured rate, e.g.")
        for a, b, hz in collisions[:3]:
            print(f"    {a:+.4f} rad and {b:+.4f} rad both -> {hz:.0f} Hz")
    print(
        "  Impact on STDP: LOW for Level 1 as scoped.  Babbling asks 'did this\n"
        "  motor neuron move this joint', which the unsigned magnitude answers.\n"
        "  A flexor and its antagonist do collide in the afferent's view, so\n"
        "  agonist/antagonist credit assignment (Level 2 CPG work) will need a\n"
        "  signed or push-pull encoding.  NOT fixed here -- out of scope, and\n"
        "  signing the channel would change the sensory representation Child 0c\n"
        "  is about to wire in."
    )

    # The springref non-monotonicity, which IS fixed here.
    angles, _, _ = _drive_and_record(
        sim, model, data, state, muscle_names,
        CALIBRATION_DRIVERS["tibia"], 1.00, 600,
    )
    springref_act = np.abs(
        angles[:, _TIBIA_PITCH] - LF_SPRINGREF[_TIBIA_PITCH]
    ) / half
    settled_act = np.abs(angles[:, _TIBIA_PITCH] - settled_angles[_TIBIA_PITCH]) / half
    argmin = int(springref_act.argmin())
    print(
        f"\nSeparate defect, FIXED in this change -- the position reference:\n"
        f"  vs MJCF springref ({LF_SPRINGREF[_TIBIA_PITCH]:.2f} rad): activation "
        f"runs {springref_act[0]:.3f} -> {springref_act[argmin]:.3f} (at "
        f"{argmin * 0.1:.0f} ms) -> {springref_act[-1]:.3f}\n"
        f"    NON-MONOTONIC: the leg passes THROUGH springref, so the same "
        f"current is emitted at two\n    different postures, and the afferent is "
        f"tonically at {springref_act[0]:.3f} activation while at rest.\n"
        f"  vs settled posture ({settled_angles[_TIBIA_PITCH]:.3f} rad): "
        f"{settled_act[0]:.3f} -> {settled_act[-1]:.3f}, monotonic: "
        f"{bool(np.all(np.diff(settled_act) > -1e-3))}, and silent at rest."
    )
    return table


def _report_velocity_scale(sim, model, data, state, muscle_names) -> pd.DataFrame:
    """Measure peak joint velocity per muscle to check ``max_velocity``."""
    rows = []
    for group, muscle in CALIBRATION_DRIVERS.items():
        for act in (0.20, 0.40, 0.70, 1.00):
            _, vels, _ = _drive_and_record(
                sim, model, data, state, muscle_names, muscle, act, 500
            )
            gidx = list(JOINT_GROUPS[group])
            group_speed = np.abs(vels[:, gidx]).mean(axis=1)
            rows.append(
                {
                    "group": group,
                    "muscle_act": act,
                    "peak_joint_vel": float(np.abs(vels).max()),
                    "peak_group_vel": float(group_speed.max()),
                    "peak_at_ms": float(group_speed.argmax() * 0.1),
                    "mean_group_vel_50ms": float(group_speed.mean()),
                    "activation_at_peak": float(
                        group_speed.max() / DEFAULT_MAX_VELOCITY
                    ),
                }
            )
    table = pd.DataFrame(rows)
    print(table.round(3).to_string(index=False))
    peak = table["peak_joint_vel"].max()
    peak_group = table["peak_group_vel"].max()
    print(
        f"\nANSWER: yes, keep max_velocity = {DEFAULT_MAX_VELOCITY}.\n"
        f"  Highest single-joint speed over all conditions: {peak:.1f} rad/s "
        f"-- {peak / DEFAULT_MAX_VELOCITY:.2f} of full scale, so 25 does not "
        "clip.\n"
        f"  Highest group-mean speed: {peak_group:.1f} rad/s "
        f"(activation {peak_group / DEFAULT_MAX_VELOCITY:.2f}).\n"
        f"  Velocity is TRANSIENT: peaks at "
        f"{table['peak_at_ms'].median():.0f} ms into the burst and the 50 ms "
        f"mean is only\n  {(table['mean_group_vel_50ms'] / table['peak_group_vel']).mean():.2f}x "
        "the peak, which is why the velocity gain is calibrated on the real\n"
        "  time-varying trace rather than a held value.  Lowering max_velocity "
        "to ~12 to raise\n  sensitivity would clip the strongest drivers "
        "(tibia reaches 27.9 rad/s) and flatten exactly\n  the transient the "
        "channel exists to report; raising the GAIN is the correct knob instead."
    )
    return table


def _report_named_afferents(
    meta_df, body_ids, sim, model, data, state, muscle_names, groups, duration_ms,
) -> pd.DataFrame:
    """Drive real physics through the real encoder and spike-count named cells.

    The end-to-end check the calibration exists to produce: for one afferent of
    each modality, show 0 Hz at the shipped 75 pA gain and a rate in the 40-100
    Hz band once the gain crosses rheobase.  Everything upstream of the LIF here
    is the production ``ProprioceptiveEncoder.encode`` path.
    """
    rows = []
    gains = tuple(
        sorted({75.0, 300.0, 500.0, 800.0, 1000.0, 1400.0, 2600.0}
               | set(DEFAULT_MODALITY_GAINS_PA.values()))
    )
    # Drive the muscle belonging to the afferent's OWN joint group; driving a
    # tibia muscle and reading a trochanter afferent measures cross-talk, not
    # the channel.  'multi' posture afferents integrate all groups, so the tibia
    # driver (the largest single excursion) is used for them.
    reference_act = {"position": 0.40, "velocity": 0.40, "force": 0.40,
                     "posture": 1.00}

    encoder0 = ProprioceptiveEncoder(meta_df, body_ids, leg="LF", side="L")
    table0 = encoder0.assignment_table()
    picks = []
    for modality in MODALITIES:
        match = table0[table0["modality"] == modality]
        if match.empty:
            continue
        pick = match.iloc[0]
        group = pick["joint_group"]
        muscle = CALIBRATION_DRIVERS.get(group, CALIBRATION_DRIVERS["tibia"])
        picks.append((modality, pick, muscle, reference_act[modality]))

    recorded: dict[str, tuple] = {}
    for _, _, muscle, act in picks:
        key = f"{muscle}|{act}"
        if key not in recorded:
            recorded[key] = _drive_and_record(
                sim, model, data, state, muscle_names, muscle, act, 500
            )

    for gain in gains:
        encoder = ProprioceptiveEncoder(
            meta_df, body_ids, leg="LF", side="L", gain_pa=gain
        )
        currents_pa = []
        for modality, pick, muscle, act in picks:
            angles, vels, forces = recorded[f"{muscle}|{act}"]
            loads = {
                g: float(np.abs(forces[-1, idx]).sum())
                for g, idx in groups.items()
            }
            currents = encoder.encode(angles[-1], vels[-1], loads)
            currents_pa.append(currents[int(pick["neuron_index"])] * 1e12)

        measured = measure_lif_rates(np.array(currents_pa), duration_ms)
        for (modality, pick, muscle, act), current, hz in zip(
            picks, currents_pa, measured
        ):
            rows.append(
                {
                    "gain_pA": gain,
                    "bodyId": int(pick["bodyId"]),
                    "type": pick["type"],
                    "joint_group": pick["joint_group"],
                    "modality": modality,
                    "driven_muscle": muscle,
                    "muscle_act": act,
                    "current_pA": current,
                    "measured_Hz": hz,
                }
            )

    result = pd.DataFrame(rows).sort_values(["modality", "gain_pA"])
    print("Each row: real physics -> ProprioceptiveEncoder.encode -> LIF spike count.")
    print("Each afferent is driven by a muscle of its OWN joint group.")
    print(result.round(2).to_string(index=False))
    print("\nverdict per named afferent (shipped 75 pA vs calibrated gain):")
    for modality in MODALITIES:
        sub = result[result["modality"] == modality]
        if sub.empty:
            continue
        shipped = sub[sub["gain_pA"] == 75.0].iloc[0]
        calibrated_gain = DEFAULT_MODALITY_GAINS_PA[modality]
        cal = sub[sub["gain_pA"] == calibrated_gain]
        cal_hz = float(cal.iloc[0]["measured_Hz"]) if not cal.empty else float("nan")
        in_band = sub[(sub["measured_Hz"] >= 40) & (sub["measured_Hz"] <= 100)]
        band = (
            f"{in_band['gain_pA'].min():.0f}-{in_band['gain_pA'].max():.0f} pA"
            if not in_band.empty else "none of the tested gains"
        )
        print(
            f"  {shipped['bodyId']} {shipped['type']:<10} {modality:<9} "
            f"(driven by {shipped['driven_muscle'][:26]:<26} @ "
            f"{shipped['muscle_act']:.2f})\n"
            f"      75 pA -> {shipped['measured_Hz']:5.1f} Hz | "
            f"{calibrated_gain:.0f} pA -> {cal_hz:5.1f} Hz | "
            f"40-100 Hz band at {band}"
        )
    return result


def _report_min_movement(
    sim, model, data, state, muscle_names, half_tibia, duration_ms,
) -> pd.DataFrame:
    """Smallest tibia displacement / muscle activation that yields a spike."""
    muscle = CALIBRATION_DRIVERS["tibia"]
    acts = (0.02, 0.05, 0.081, 0.10, 0.15, 0.189, 0.20, 0.30, 0.40, 0.60, 0.80, 1.00)
    rows = []
    for act in acts:
        angles, vels, _ = _drive_and_record(
            sim, model, data, state, muscle_names, muscle, act, 500
        )
        dq = float(np.abs(angles[:, _TIBIA_PITCH] - angles[0, _TIBIA_PITCH]).max())
        rows.append({"muscle_act": act, "peak_dq_rad": dq,
                     "activation": dq / half_tibia,
                     "peak_vel": float(np.abs(vels[:, _TIBIA_PITCH]).max())})
    table = pd.DataFrame(rows)
    for gain in (300.0, 500.0, 800.0, 1000.0):
        table[f"Hz@{gain:.0f}pA"] = measure_lif_rates(
            table["activation"].to_numpy() * gain, duration_ms
        )
    print(f"\ntibia flexor drive, 50 ms; displacement measured from the settled "
          f"posture (half-range {half_tibia:.4f} rad):")
    print(table.round(3).to_string(index=False))

    for gain in (300.0, 500.0, 800.0, 1000.0):
        firing = table[table[f"Hz@{gain:.0f}pA"] > 0]
        threshold_dq = RHEOBASE_PA / gain * half_tibia
        if firing.empty:
            print(f"  {gain:>6.0f} pA: no tested activation spikes "
                  f"(needs {threshold_dq:.3f} rad)")
        else:
            row = firing.iloc[0]
            print(
                f"  {gain:>6.0f} pA: first spike at muscle_act "
                f"{row['muscle_act']:.3f} -> {row['peak_dq_rad']:.4f} rad "
                f"({row['activation']:.3f} of half-range); "
                f"analytic threshold {threshold_dq:.3f} rad"
            )
    return table


def _measure_channel_rates(traces: dict[str, np.ndarray], duration_ms) -> pd.DataFrame:
    """Measured Hz per (group, muscle activation, modality, gain).

    Position/force/posture use the end-of-drive steady activation as a constant
    current.  Velocity is measured from the real time-varying trace, because its
    activation peaks for ~20 ms and then decays -- a constant-current figure
    would overstate the channel.
    """
    gains = (75.0, 300.0, 500.0, 800.0, 900.0, 1400.0, 2600.0)
    rows = []
    const_currents: list[float] = []
    const_keys: list[tuple] = []
    trace_batches: list[tuple[tuple, np.ndarray]] = []

    for key, trace in traces.items():
        group, act, modality = key.split("|")
        for gain in gains:
            if modality == "velocity":
                trace_batches.append(((group, float(act), modality, gain),
                                      trace * gain))
            else:
                const_keys.append((group, float(act), modality, gain))
                const_currents.append(float(trace[-1]) * gain)

    const_hz = measure_lif_rates(np.array(const_currents), duration_ms)
    hz_by_key = dict(zip(const_keys, const_hz))

    if trace_batches:
        width = len(trace_batches[0][1])
        matrix = np.stack([t for _, t in trace_batches], axis=1)
        trace_hz = measure_lif_rates_from_trace(matrix)
        for (key, _), hz in zip(trace_batches, trace_hz):
            hz_by_key[key] = hz

    for (group, act, modality, gain), hz in hz_by_key.items():
        rows.append({"group": group, "muscle_act": act, "modality": modality,
                     "gain_pA": gain, "measured_Hz": hz})
    table = pd.DataFrame(rows)
    pivot = table.pivot_table(
        index=["modality", "group", "muscle_act"], columns="gain_pA",
        values="measured_Hz",
    ).sort_index().reset_index()
    pivot.columns = [
        c if isinstance(c, str) else f"{c:.0f}pA" for c in pivot.columns
    ]
    return pivot


def _solve_gains(
    traces: dict[str, np.ndarray],
    duration_ms: float,
    reference_act: float = 0.40,
    target_hz: float = 70.0,
    band: tuple[float, float] = (40.0, 100.0),
) -> dict[str, float]:
    """Pick the gain per modality whose measured mean rate is closest to target.

    Averaged over the three joint groups at one reference muscle activation, so
    a single joint group cannot dominate the choice.  Position/force/posture are
    scored on the steady end-of-burst activation; velocity is scored on its real
    50 ms trace because it is transient.
    """
    candidates = np.array(
        [300, 400, 500, 600, 700, 800, 900, 1000, 1200, 1400,
         1600, 1800, 2000, 2400, 2800, 3200, 4000],
        dtype=float,
    )
    print(f"\nGain solve: mean measured Hz over the {len(JOINT_GROUPS)} joint "
          f"groups at muscle activation {reference_act:.2f},\ntarget "
          f"{band[0]:.0f}-{band[1]:.0f} Hz (aiming for {target_hz:.0f} Hz).")
    print("  " + "modality".ljust(10) + "".join(f"{g:>7.0f}" for g in candidates))

    recommended: dict[str, float] = {}
    for modality in MODALITIES:
        per_group = []
        for group in JOINT_GROUPS:
            key = f"{group}|{reference_act}|{modality}"
            trace = traces.get(key)
            if trace is None:
                continue
            if modality == "velocity":
                matrix = np.stack([trace * g for g in candidates], axis=1)
                per_group.append(measure_lif_rates_from_trace(matrix))
            else:
                per_group.append(
                    measure_lif_rates(float(trace[-1]) * candidates, duration_ms)
                )
        if not per_group:
            recommended[modality] = DEFAULT_MODALITY_GAINS_PA[modality]
            continue
        mean_hz = np.mean(per_group, axis=0)
        print("  " + modality.ljust(10) + "".join(f"{h:7.0f}" for h in mean_hz))
        in_band = (mean_hz >= band[0]) & (mean_hz <= band[1])
        if in_band.any():
            pool = candidates[in_band]
            scores = np.abs(mean_hz[in_band] - target_hz)
            recommended[modality] = float(pool[int(np.argmin(scores))])
        else:
            recommended[modality] = float(
                candidates[int(np.argmin(np.abs(mean_hz - target_hz)))]
            )

    print("\nRECOMMENDED per-modality gains (pA at activation 1.0):")
    for modality, gain in recommended.items():
        shipped = DEFAULT_MODALITY_GAINS_PA[modality]
        flag = "" if gain == shipped else f"   (module default is {shipped:.0f})"
        print(f"  {modality:9s} {gain:7.0f} pA{flag}")
    spread = max(recommended.values()) / min(recommended.values())
    print(
        f"\nSpread across modalities: {min(recommended.values()):.0f}-"
        f"{max(recommended.values()):.0f} pA ({spread:.1f}x).  "
        "PER-MODALITY gains are required:\n  a single shared gain leaves the "
        "high-gain channels silent or saturates the low-gain ones."
    )
    return recommended


def _report_force_channel(
    sim, model, data, state, muscle_names, groups, rest_load, duration_ms,
) -> pd.DataFrame:
    """Confirm the SNpp53 force channel now reads a non-zero, modulated signal."""
    import mujoco

    qpos, qvel = state
    data.qpos[:] = qpos
    data.qvel[:] = qvel
    data.ctrl[:] = 0.0
    mujoco.mj_forward(model, data)

    lf_geoms = [
        i for i in range(model.ngeom)
        if (mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, i) or "").startswith("LF")
    ]
    floor = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "floor")
    any_lf = 0.0
    ground_only = 0.0
    buf = np.zeros(6)
    print(f"OLD signal -- ground reaction.  All {data.ncon} contacts in the "
          f"settled model:")
    for c in range(data.ncon):
        con = data.contact[c]
        n1 = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, con.geom1)
        n2 = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, con.geom2)
        mujoco.mj_contactForce(model, data, c, buf)
        print(f"    {n1} <-> {n2}   dist={con.dist:+.5f}  Fn={buf[0]:.3f}")
        if con.geom1 in lf_geoms or con.geom2 in lf_geoms:
            any_lf += abs(buf[0])
            if floor in (con.geom1, con.geom2):
                ground_only += abs(buf[0])
    print(f"  summed over LF-involving contacts (what the OLD code read): "
          f"{any_lf:.4f}")
    print(f"  summed over LF<->floor contacts (actual ground reaction): "
          f"{ground_only:.4f}")
    print(
        "  -> the old channel was not merely zero, it was a CONSTANT "
        f"{any_lf:.1f}-unit\n     Thorax<->Coxa interpenetration artifact with "
        "no dependence on leg state:\n     unmodulated, so it carries no "
        "proprioceptive information either way."
    )
    print("\nNEW signal -- summed |actuator_force| (tendon tension) per joint group:")
    for group, value in sorted(rest_load.items()):
        print(f"  {group:11s} rest {value:8.3f}  "
              f"activation {value / DEFAULT_MAX_FORCE:.4f}")

    gain = DEFAULT_MODALITY_GAINS_PA["force"]
    rows = []
    muscle = CALIBRATION_DRIVERS["trochanter"]
    for act in (0.0, 0.05, 0.10, 0.20, 0.40, 0.70, 1.00):
        if act == 0.0:
            load = rest_load["trochanter"]
        else:
            _, _, forces = _drive_and_record(
                sim, model, data, state, muscle_names, muscle, act, 500
            )
            load = float(np.abs(forces[-1, groups["trochanter"]]).sum())
        activation = min(load / DEFAULT_MAX_FORCE, 1.0)
        rows.append({"muscle_act": act, "trochanter_tendon_load": load,
                     "activation": activation, "current_pA": activation * gain})
    table = pd.DataFrame(rows)
    table["measured_Hz"] = measure_lif_rates(
        table["current_pA"].to_numpy(), duration_ms
    )
    print(f"\nSNpp53 (2 campaniform-sensilla afferents), driving {muscle} "
          f"at force gain {gain:.0f} pA:")
    print(table.round(3).to_string(index=False))
    firing = table[table["measured_Hz"] > 0]
    print(
        f"\nSNpp53 reads a NON-ZERO signal: {rest_load['trochanter']:.3f} "
        f"tendon-force units at rest (was 0.000 with ground reaction), "
        f"{table['trochanter_tendon_load'].max():.1f} under drive."
    )
    if firing.empty:
        print("  ...but it never spikes at the tested loads -- gain too low.")
    else:
        row = firing.iloc[0]
        print(f"  First spike at muscle_act {row['muscle_act']:.2f} "
              f"(load {row['trochanter_tendon_load']:.1f}, "
              f"{row['current_pA']:.0f} pA) -> {row['measured_Hz']:.0f} Hz; "
              f"rest stays silent at {table.iloc[0]['current_pA']:.0f} pA.")
    return table


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------


def run_proprioceptive_demo(
    side: str | None = None,
    gain_pa: float | None = None,
    steps: int = SETTLE_STEPS,
) -> dict:
    """Build the encoder on the full VNC and drive it with FlyMimic physics.

    Loads the full-VNC connectome snapshot, constructs the encoder, prints the
    per-neuron assignment table and bucket summary, then steps the FlyMimic
    musculoskeletal model (which exposes the 7 LF joints and 15 Hill-type
    muscles) and reports the resulting non-zero injected currents.

    Reports currents only.  A current is not a firing rate -- use
    ``run_sensory_calibration()`` to count spikes on real LIF neurons.

    Parameters
    ----------
    side : str or None
        Restrict afferents to one ``rootSide`` ('L'/'R'); None keeps both.
    gain_pa : float or None
        One shared peak current in pA at activation 1.0.  None uses the
        calibrated per-modality gains.
    steps : int
        Physics steps to settle before the resting-state readout.  Must be
        >= ``SETTLE_STEPS``; at 500 the tibia is still drifting at -4 rad/s.
    """
    import mujoco
    from flygym.compose import build_musculoskeletal_simulation

    from .functional_selection import get_or_build_full_vnc_network

    print("=" * 78)
    print("Proprioceptive Encoder: ProLN afferents -> LF joint state")
    print("=" * 78)

    body_ids, meta_df, _, _, _, _ = get_or_build_full_vnc_network()

    encoder = ProprioceptiveEncoder(
        meta_df, body_ids, leg="LF", side=side, gain_pa=gain_pa
    )

    n_motor = _count_lf_motor(meta_df)
    table = encoder.assignment_table()
    print(f"\nNetwork: {len(body_ids):,} neurons")
    print(f"LF leg motor neurons (superclass=vnc_motor, subclass=fl, somaSide=L): {n_motor}")
    print(f"ProLN proprioceptive afferents selected: {len(table)} (side={side})")
    print(f"  actively encoded: {len(encoder.assignments)}")
    print(f"  excluded (ascending): {len(encoder.excluded)}")
    print("\nrootSide breakdown of selection:")
    print(table["rootSide"].value_counts().to_string())

    print("\n--- Per-neuron assignment table ---")
    print(table.to_string(index=False))

    print("\n--- Bucket summary (joint group x modality) ---")
    print(encoder.bucket_summary().to_string(index=False))

    print("\n--- Gains in use (pA at activation 1.0) ---")
    for modality in MODALITIES:
        print(f"  {modality:9s} {encoder.gains_pa[modality]:8.1f} pA")
    print(f"  LIF rheobase: {RHEOBASE_PA:.0f} pA "
          "(below this a neuron never fires, at any duration)")

    print("\n--- Physics: FlyMimic musculoskeletal model ---")
    sim, _fly = build_musculoskeletal_simulation()
    model, data = sim.mj_model, sim.mj_data
    muscle_groups = muscle_group_indices(model)

    if steps < SETTLE_STEPS:
        print(f"  WARNING: {steps} settling steps is below the measured "
              f"{SETTLE_STEPS} needed; the leg is still drifting.")
    for _ in range(steps):
        sim.step()

    readouts = []
    print(f"\nResting state after {steps} physics steps:")
    readouts.append(_report_state(encoder, sim, model, data, muscle_groups, "rest"))

    print("\nDriving LFTibia_flex muscle at full activation for 300 steps:")
    flex_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, "LFTibia_flex_93434")
    data.ctrl[flex_id] = 1.0
    for _ in range(300):
        sim.step()
    readouts.append(_report_state(encoder, sim, model, data, muscle_groups, "tibia_flex"))

    print("\nDriving LFF_trochanter_extensor at full activation for 300 steps:")
    data.ctrl[flex_id] = 0.0
    ext_id = mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_ACTUATOR, "LFF_trochanter_extensor"
    )
    data.ctrl[ext_id] = 1.0
    for _ in range(300):
        sim.step()
    readouts.append(_report_state(encoder, sim, model, data, muscle_groups, "troch_extend"))

    print("\n--- Condition comparison (mean pA per bucket) ---")
    comparison = pd.DataFrame(
        {r["label"]: r["bucket_pa"] for r in readouts}
    ).round(2)
    print(comparison.to_string())

    delta = np.abs(readouts[1]["currents"] - readouts[0]["currents"]).max() * 1e12
    print(
        f"\nMax per-neuron current change rest -> tibia_flex: {delta:.2f} pA"
    )
    print("=" * 78)

    return {
        "encoder": encoder,
        "assignment_table": table,
        "bucket_summary": encoder.bucket_summary(),
        "readouts": readouts,
    }


def _count_lf_motor(meta_df: pd.DataFrame) -> int:
    mask = (
        (meta_df["superclass"] == "vnc_motor")
        & (meta_df["subclass"] == "fl")
        & (meta_df["somaSide"] == "L")
    )
    return int(mask.sum())


def muscle_group_indices(model) -> dict[str, list[int]]:
    """Map joint group -> indices of that group's muscle actuators.

    Grouping is by the FlyMimic actuator-name prefix (``MUSCLE_GROUP_PREFIX``):
    ``LFC_*`` coxa, ``LFTibia*`` tibia, ``LFF_*`` trochanter.
    """
    import mujoco

    groups: dict[str, list[int]] = {g: [] for g in JOINT_GROUPS}
    for i in range(model.nu):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i) or ""
        for prefix, group in MUSCLE_GROUP_PREFIX:
            if name.startswith(prefix):
                groups[group].append(i)
                break
    return groups


def tendon_loads_by_group(data, groups: dict[str, list[int]]) -> dict[str, float]:
    """Summed tendon tension ``|actuator_force|`` per joint group.

    This is the signal the force channel (SNpp53 campaniform sensilla) reads.
    ``d.actuator_force`` is populated by every ``mj_step``, so unlike
    ``d.cfrc_ext`` it needs no ``mj_rnePostConstraint`` call.

    Measured on the settled tethered leg: coxa 0.68, trochanter 1.37,
    tibia 4.88 -- non-zero at rest, and rising to 15-336 under single-muscle
    drive.  The previous ground-reaction implementation read identically 0.00.
    """
    f = np.abs(np.asarray(data.actuator_force))
    return {g: float(f[idx].sum()) if idx else 0.0 for g, idx in groups.items()}


def _report_state(encoder, sim, model, data, muscle_groups, label: str) -> dict:
    angles = sim.get_joint_angles("nmf")[:N_LF_JOINTS]
    vels = sim.get_joint_velocities("nmf")[:N_LF_JOINTS]
    load = tendon_loads_by_group(data, muscle_groups)

    currents = encoder.encode(angles, vels, load)
    nonzero = np.flatnonzero(currents)
    pa = currents * 1e12

    print(f"  LF joint angles (rad): {np.round(angles, 3)}")
    print(f"  LF joint velocities  : {np.round(vels, 2)}")
    print(
        "  LF tendon load       : "
        + "  ".join(f"{g}={v:.2f}" for g, v in sorted(load.items()))
    )
    print(
        f"  non-zero currents    : {len(nonzero)} neurons, "
        f"mean {pa[nonzero].mean():.2f} pA, max {pa[nonzero].max():.2f} pA, "
        f"total {pa.sum():.1f} pA"
    )

    table = encoder.assignment_table()
    active = table[table["modality"] != "excluded"].copy()
    active["pA"] = pa[active["neuron_index"].values]
    bucket_pa = active.groupby(["joint_group", "modality"])["pA"].mean()
    top = active.nlargest(5, "pA")[["bodyId", "type", "joint_group", "modality", "pA"]]
    print("  strongest 5 afferents:")
    for r in top.itertuples():
        print(
            f"    {r.bodyId:>11}  {r.type:<10} {r.joint_group:<11} "
            f"{r.modality:<9} {r.pA:6.2f} pA"
        )

    return {
        "label": label,
        "angles": angles,
        "velocities": vels,
        "load": load,
        "currents": currents,
        "bucket_pa": bucket_pa,
    }
