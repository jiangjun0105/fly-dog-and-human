"""Motor decoder: full-VNC motor neuron firing rates -> muscle / joint commands.

Maps the 368 leg motor neurons of the full VNC connectome (25,635 neurons) onto
either the 15 FlyMimic Hill-type muscles of the left-front leg or the 66-DOF
position-actuator vector of the standard NeuroMechFly body.

The mapping is driven off the connectome annotations, not a heuristic: MANC's
``type`` column literally names the target muscle ("Ti flexor MN",
"Tergopleural/Pleural promotor MN"), ``subclass`` gives the leg segment
(fl/ml/hl) and ``somaSide`` the side.  The type -> muscle table is transcribed
from ``docs/neuroscience/13-motor-neuron-muscle-mapping.md`` §3 and the type ->
DOF table from §2/§5.

Activation follows doc 13 §4: a size-principle weighted sum in which a silent
neuron contributes exactly zero, so recruiting more neurons is monotonically
stronger.  This replaces the earlier per-neuron-offset-then-average scheme, in
which a silent neuron contributed a large *negative* offset and could cancel an
active one.

Since 2026-08-18 the rate -> activation step is a **per-class force model**
rather than a size-weighted fraction of a flat 200 Hz ceiling.  See
``FORCE_PER_SPIKE_UN`` below and doc 13 §4 for the two defects that forced the
change: ``max_rate = 200 Hz`` was unsourced and unreachable, and the decoder had
no motor-neuron classes at all, so a 1000x biological force-per-spike gradient
was represented as a 14x spread in the wrong variable (drive, not force).

Usage:
    from digital_drosophila.muscle_decoder import run_muscle_decoder_demo
    run_muscle_decoder_demo()
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Legacy decode constants.  Retained ONLY so the corrected model can be measured
# against the one that produced the 200 Hz loop-closure result; not the default.
BASELINE_HZ = 15.0
MAX_RATE_HZ = 200.0
DEFAULT_MOTOR_GAIN = 0.3

# ---------------------------------------------------------------------------
# Motor neuron force classes
# ---------------------------------------------------------------------------
#
# EVERY number in this block is fixed from the literature and was fixed BEFORE
# any loop-closure run.  Force gain is exactly the dial that could manufacture a
# desired latency, so none of it is tuned to an outcome.
#
# Primary source: Azevedo, Dickinson, Gurung, Venkatasubramanian, Mann & Tuthill
# (2020), "A size principle for recruitment of Drosophila leg motor neurons",
# eLife 9:e56754 (PMC7347388).  In vivo whole-cell recordings from *identified*
# femur/tibia-flexor motor neurons of the **front leg** -- the same pool this
# decoder drives.  Three classes, each labelled by its own Gal4 line
# (fast R81A07, intermediate R22A08, slow R35C09), spanning three orders of
# magnitude in force per spike.

# Force per spike, micronewtons.  Azevedo reports fast ~10 uN (~= the fly's body
# weight), intermediate ~1 uN, slow <0.1 uN.  The slow figure is the 0.013 uN
# read off Azevedo's force axis; treat as +/-20% (axis read, not stated in text).
FORCE_PER_SPIKE_UN: dict[str, float] = {
    "fast": 10.0,
    "intermediate": 1.0,
    "slow": 0.013,
}

# Per-class rate ceiling, replacing the single unsourced ``max_rate = 200 Hz``.
#
# slow  150 Hz -- Azevedo's ceiling under direct current injection (~30 Hz at
#                 rest, ~100 Hz under natural proprioceptive drive).
# fast / intermediate 250 Hz -- these classes are silent at rest and phasic;
#                 Azevedo gives no rate, only a spike count (force saturates by
#                 ~10 spikes).  250 Hz is the rate that puts 10 spikes inside one
#                 fusion window, so the ceiling is where the force function has
#                 already saturated and is therefore NOT a force gain: raising it
#                 changes the class's maximum force by <1%.
CLASS_MAX_RATE_HZ: dict[str, float] = {
    "fast": 250.0,
    "intermediate": 250.0,
    "slow": 150.0,
}

# Per-class deadband.  All zero, which RETIRES the flat ``baseline_hz = 15``.
#
# The old 15 Hz deadband is indefensible for both ends of the gradient:
#   * fast/intermediate MNs are SILENT at rest, so every spike they fire is
#     signal.  A single fast spike inside a 50 ms rate window reads as 20 Hz, and
#     a 15 Hz deadband deletes three quarters of it -- exactly the class whose one
#     spike is supposed to move the tibia.
#   * slow MNs *idle* at ~30 Hz and that idle IS a real resting force (Azevedo:
#     the slow MN holds "constant force on the probe" at rest).  Subtracting a
#     baseline models the tonic class's own operating point as zero output.
# Posture is instead held by the muscle's ``ctrlrange`` floor (1e-4) and the
# model's passive joint stiffness, which is where it belongs.
CLASS_BASELINE_HZ: dict[str, float] = {
    "fast": 0.0,
    "intermediate": 0.0,
    "slow": 0.0,
}

# Twitch summation ratio.  Azevedo: "the force produced by two spikes was ~1.6X
# the force produced by a single spike", and "the force-per-spike curves
# saturated at ~10 spikes".  For F(n) = F_sat * (1 - x**n), F(2)/F(1) = 1 + x, so
# x = 0.6 exactly, and F(10)/F_sat = 0.994 -- i.e. the 1.6x ratio and the ~10
# spike saturation are the SAME number, which is a consistency check on the read.
TWITCH_SUMMATION_RATIO = 0.6

# How long one twitch keeps contributing force, seconds.  Harischandra et al.
# (2019), PLoS Comput Biol (PMC6812852): locust extensor tibiae reaches tetanic
# fusion above ~20-25 Hz, so tau ~= 1/25 s.  CROSS-SPECIES IMPORT -- locust, not
# Drosophila -- and the one constant here with no fly source.  It is not
# load-bearing for the headline: for fast/intermediate the force function has
# saturated, and the slow class contributes a few percent of any pool's maximum
# either way.  ``MuscleDecoder`` takes it as a parameter so it can be varied.
FUSION_TAU_S = 0.040

# Class proportions within one motor pool, from Azevedo's anatomical count of the
# tibia flexor pool: ~15 motor neurons made up of 1 fast, 2-5 intermediate and
# 8-9 slow.  Midpoints give 1 / 3.5 / rest.
CLASS_POOL_FRACTION: dict[str, float] = {
    "fast": 1.0 / 15.0,
    "intermediate": 3.5 / 15.0,
}

FORCE_CLASSES: tuple[str, ...] = ("fast", "intermediate", "slow")


def class_force_un(force_class: str, rate_hz, fusion_tau_s: float = FUSION_TAU_S):
    """Force in micronewtons produced by one motor neuron firing at ``rate_hz``.

    Two regimes, because the classes differ in kind and not only in magnitude:

    * **fast / intermediate** are phasic and their muscle fibres fatigue, which is
      what Azevedo attributes the ~10 spike saturation to.  Force is a function of
      the number of twitches currently summing, ``n = rate * fusion_tau``:
      ``F = F_sat * (1 - x**n)`` with ``x = 0.6`` and
      ``F_sat = force_per_spike / (1 - x)``, so that a single spike delivers
      exactly the measured per-spike force and 10 spikes saturate.
    * **slow** is tonic and fatigue-RESISTANT, so it must not inherit fast-fibre
      fatigue.  Force is linear in rate, ``F = force_per_spike * rate * tau``,
      which is what "integrates over rate" means, clipped at the class ceiling.

    Zero rate gives exactly zero force in both regimes, which is what keeps the
    size principle intact: a silent neuron contributes nothing at all.
    """
    rate = np.clip(
        np.asarray(rate_hz, dtype=float) - CLASS_BASELINE_HZ[force_class],
        0.0,
        CLASS_MAX_RATE_HZ[force_class] - CLASS_BASELINE_HZ[force_class],
    )
    per_spike = FORCE_PER_SPIKE_UN[force_class]
    n_live = rate * fusion_tau_s
    if force_class == "slow":
        return per_spike * n_live
    f_sat = per_spike / (1.0 - TWITCH_SUMMATION_RATIO)
    return f_sat * (1.0 - TWITCH_SUMMATION_RATIO ** n_live)

# The 15 FlyMimic Hill-type muscles, in MuJoCo actuator order (verified against
# MusculoskeletalFly.muscle_names).  All are left-front leg.
MUSCLE_NAMES: tuple[str, ...] = (
    "LFC_tergopleural_promotor_a",
    "LFC_tergopleural_promotor_b",
    "LFC_pleural_remotor_and_abductor",
    "LFC_pleural_promotor",
    "LFC_sternal_anterior_rotator",
    "LFC_sternal_posterior_rotator",
    "LFC_sternal_adductor",
    "LFF_trochanter_flexor_b",
    "LFF_sterno-tergo-trochanter_extensor_a",
    "LFF_sterno-tergo-trochanter_extensor_b",
    "LFF_accesory_trochanter_flexor",
    "LFF_trochanter_extensor",
    "LFF_trochanter_flexor_a",
    "LFTibia_flex_93434",
    "LFTibia_extensor_93932",
)

# Connectome motor-neuron ``type`` -> FlyMimic muscle(s), from doc 13 §3.
# A type may drive several muscles (anatomical _a/_b variants of one muscle) and
# a muscle may be driven by several types (e.g. the tibia flexor pool).
TYPE_TO_MUSCLES: dict[str, tuple[str, ...]] = {
    "Tergopleural/Pleural promotor MN": (
        "LFC_tergopleural_promotor_a",
        "LFC_tergopleural_promotor_b",
        "LFC_pleural_promotor",
    ),
    "Pleural remotor/abductor MN": ("LFC_pleural_remotor_and_abductor",),
    "Sternal anterior rotator MN": ("LFC_sternal_anterior_rotator",),
    "Sternal posterior rotator MN": ("LFC_sternal_posterior_rotator",),
    "Sternal adductor MN": ("LFC_sternal_adductor",),
    "Fe reductor MN": ("LFC_sternal_adductor",),
    "Tr flexor MN": ("LFF_trochanter_flexor_a", "LFF_trochanter_flexor_b"),
    "Sternotrochanter MN": ("LFF_trochanter_flexor_a",),
    "ltm MN": ("LFF_trochanter_flexor_a",),
    "ltm2-femur MN": ("LFF_trochanter_flexor_a",),
    "Acc. tr flexor MN": ("LFF_accesory_trochanter_flexor",),
    "Tr extensor MN": (
        "LFF_sterno-tergo-trochanter_extensor_a",
        "LFF_sterno-tergo-trochanter_extensor_b",
    ),
    "Tergotr. MN": ("LFF_trochanter_extensor",),
    "Ti flexor MN": ("LFTibia_flex_93434",),
    "Acc. ti flexor MN": ("LFTibia_flex_93434",),
    "ltm1-tibia MN": ("LFTibia_flex_93434",),
    "Ti extensor MN": ("LFTibia_extensor_93932",),
}

# Doc 13 §3 flags LFC_pleural_promotor as having no clear connectome match and
# guesses it shares the tergopleural promotor pool.  Recorded so the coverage
# report can surface it rather than hiding it inside the table above.
AMBIGUOUS_ASSIGNMENTS: tuple[tuple[str, str], ...] = (
    ("Tergopleural/Pleural promotor MN", "LFC_pleural_promotor"),
)

# Connectome motor-neuron ``type`` -> (66-DOF leg-relative index, sign).
# DOF indices follow locomotion.LEG_DOF_NAMES: 0 coxa-pitch, 1 coxa-roll,
# 2 coxa-yaw, 3 trochanterfemur-pitch, 4 trochanterfemur-roll, 5 tibia-pitch,
# 6..10 tarsus1..5-pitch.  Directions from doc 13 §2 (muscle -> joint ->
# direction), cross-checked against the measured single-muscle joint
# displacements in §5.
TYPE_TO_DOF: dict[str, tuple[int, int]] = {
    "Tergopleural/Pleural promotor MN": (2, -1),
    "Pleural remotor/abductor MN": (2, +1),
    "Sternal anterior rotator MN": (1, -1),
    "Sternal posterior rotator MN": (1, +1),
    "Sternal adductor MN": (1, -1),
    "Fe reductor MN": (1, -1),
    "Tr flexor MN": (3, +1),
    "Acc. tr flexor MN": (3, +1),
    "ltm MN": (3, +1),
    "ltm2-femur MN": (3, +1),
    "Sternotrochanter MN": (3, -1),
    "Tergotr. MN": (3, -1),
    "Tr extensor MN": (3, -1),
    "Ti flexor MN": (5, +1),
    "Acc. ti flexor MN": (5, +1),
    "ltm1-tibia MN": (5, +1),
    "Ti extensor MN": (5, -1),
    "Ta depressor MN": (6, -1),
    "Ta levator MN": (6, +1),
}

# MANC subclass -> FlyGym leg segment letter
_SUBCLASS_TO_SEGMENT = {"fl": "F", "ml": "M", "hl": "H"}

# The one leg FlyMimic gives Hill-type muscles
MUSCLE_LEG = "LF"

LEGS = ("LF", "RF", "LM", "RM", "LH", "RH")


# ---------------------------------------------------------------------------
# Assignment records
# ---------------------------------------------------------------------------


@dataclass
class MotorAssignment:
    """One leg motor neuron and everything it drives.

    Attributes
    ----------
    body_id : int
        MANC bodyId.
    net_index : int
        Position in the network's ``body_ids`` ordering (the key used in
        ``rates_hz``).
    mn_type : str
        MANC ``type`` value, which names the target muscle.
    leg : str
        FlyGym leg abbreviation ('LF', 'RF', 'LM', 'RM', 'LH', 'RH').
    size : float
        Segmented volume from the connectome, used as the force-capacity proxy.
    muscles : tuple of str
        FlyMimic muscles driven (empty unless this is an LF neuron with a
        muscle-mapped type).
    dof : int or None
        Leg-relative DOF index in the 66-vector, or None if the type has no
        DOF assignment.
    dof_sign : int
        +1 or -1: which way this neuron pushes ``dof``. 0 when dof is None.
    force_class : str
        'fast', 'intermediate' or 'slow'.  **An assumption, not a connectome
        annotation** -- see ``assign_force_classes``.
    class_rank : int
        Rank within the neuron's own anatomical pool, 0 = largest.
    """

    body_id: int
    net_index: int
    mn_type: str
    leg: str
    size: float
    muscles: tuple[str, ...] = ()
    dof: int | None = None
    dof_sign: int = 0
    force_class: str = "slow"
    class_rank: int = 0


@dataclass
class _Pool:
    """A population of motor neurons acting on one output.

    ``weights`` is retained for the legacy rate-fraction decode and for
    reporting; the force decode uses ``force_classes`` instead, because a
    connectome ``size`` ratio and a force-per-spike class are different
    quantities and multiplying by both would double-count the size principle.
    """

    indices: np.ndarray
    weights: np.ndarray
    force_classes: tuple[str, ...] = ()
    sum_weights: float = field(init=False)

    def __post_init__(self):
        self.sum_weights = float(self.weights.sum())


# ---------------------------------------------------------------------------
# Class assignment
# ---------------------------------------------------------------------------


def assign_force_classes(
    sizes,
    fast_fraction: float = CLASS_POOL_FRACTION["fast"],
    intermediate_fraction: float = CLASS_POOL_FRACTION["intermediate"],
) -> list[str]:
    """Assign slow / intermediate / fast by SIZE RANK within one anatomical pool.

    **This is an assumption, clearly labelled.  It is not read from the data.**

    What the connectome can and cannot support, measured rather than asserted:

    * `size` **cannot** encode the force gradient by magnitude.  Azevedo's
      classes are distinguished *within a single muscle pool*, and our Ti flexor
      pool spans only **2.1x** in ``size`` across its 5 neurons (Ti extensor 1.4x
      across 2).  A 2.1x anatomical spread cannot carry a 1000x force ratio.  The
      14x figure quoted elsewhere is the spread across all 64 LF MNs of
      *different muscles*, which is a different quantity.
    * `synweight` is no better as a *class* variable.  It spans more (122x within
      the trochanter-flexor DOF pool) but it counts synapses, and doc 13 §4
      already records that it tracks connectivity rather than contractile
      capacity.  It also correlates strongly with ``size`` anyway
      (Spearman rho = 0.83 over the 64 LF MNs, p = 4e-17), so it would reproduce
      much the same ordering while being harder to defend.
    * Azevedo's identified cells **cannot** be matched to MANC types by name.
      His classes are Gal4 lines (R81A07 / R22A08 / R35C09); MANC's ``type`` for
      every one of the 64 LF MNs names only the *muscle* ("Ti flexor MN"), and the
      columns that might carry a finer identity are empty for this population
      (``flywireType``, ``hemibrainType``, ``synonyms``, ``class``, ``supertype``
      all NaN; ``mancType`` merely repeats ``type``).  There is no join key.

    So no principled assignment exists, and this is the most defensible
    fallback.  What it does use from the data is **rank**, not magnitude:

    * the size principle predicts recruitment order correlates with motor neuron
      size, and Azevedo's own title is that principle -- his fast cell has "an
      exceptionally large soma", his slow cell "the smallest cell body, dendrites,
      and axon".  So the *ordering* by ``size`` is expected to track class even
      where the connectome's dynamic range understates the force ratio.
    * the *proportions* come from Azevedo's anatomical count of the tibia flexor
      pool -- ~15 MNs made up of 1 fast, 2-5 intermediate, 8-9 slow -- applied by
      rank.  Pool fractions, not absolute counts, so it generalises to the 2-16
      neuron pools this connectome actually has.

    Guaranteed properties, both asserted in the demo rather than assumed:

    * every pool of >= 1 neuron has exactly one fast neuron (its largest), so no
      pool is left unable to produce a phasic movement;
    * the assignment is monotone in ``size`` -- no smaller neuron is ever given a
      faster class than a larger one.

    Parameters
    ----------
    sizes : array-like
        Connectome ``size`` for each neuron of one pool, in any order.
    fast_fraction, intermediate_fraction : float
        Fraction of the pool assigned to each class, largest first.

    Returns
    -------
    list of str
        Class per input neuron, in the order ``sizes`` was given.
    """
    sizes = np.asarray(sizes, dtype=float)
    n = len(sizes)
    if n == 0:
        return []
    # Largest first.  Ties broken by original position so the result is
    # deterministic regardless of DataFrame row order.
    order = np.argsort(-sizes, kind="stable")
    n_fast = max(1, int(round(n * fast_fraction)))
    n_inter = int(round(n * intermediate_fraction))
    # A 2-neuron pool would otherwise be all-phasic with no tonic class at all.
    n_inter = min(n_inter, max(0, n - n_fast - 1)) if n > 1 else 0
    out = ["slow"] * n
    for rank, i in enumerate(order):
        if rank < n_fast:
            out[i] = "fast"
        elif rank < n_fast + n_inter:
            out[i] = "intermediate"
    return out


def _pool_key(a: "MotorAssignment") -> tuple:
    """The anatomical pool a neuron's class rank is assigned within.

    The MANC ``type`` is the pool: it names one muscle, and Azevedo's classes are
    a within-muscle distinction.  Using a FlyMimic muscle instead would be wrong
    where several types share one actuator -- ``LFTibia_flex_93434`` pools
    Ti flexor + Acc. ti flexor + ltm1-tibia, three anatomically distinct muscles,
    and ranking across them would compare a large neuron of one muscle against a
    small neuron of another.
    """
    return (a.leg, a.mn_type)


# ---------------------------------------------------------------------------
# Decoder
# ---------------------------------------------------------------------------


class MuscleDecoder:
    """Decode full-VNC motor neuron rates to muscle activations and joint commands.

    Parameters
    ----------
    meta_df : DataFrame
        Full-VNC neuron metadata (needs ``bodyId``, ``superclass``, ``subclass``,
        ``somaSide``, ``type``, ``size``).
    body_ids : list of int
        Network body-ID ordering; ``rates_hz`` keys index into this.
    force_model : bool
        ``True`` (default) uses the per-class force-per-spike decode.  ``False``
        restores the legacy ``sum(w_i * rate_i) / (sum(w_i) * 200 Hz)`` decode, so
        the two can be measured against each other in one run.  It exists only
        for that comparison and should not be used for new measurements.
    baseline_hz, max_rate_hz : float
        Legacy decode only, ignored when ``force_model`` is ``True`` (which has
        per-class baselines and ceilings instead).
    fusion_tau_s : float
        Twitch duration used by the force model.
    motor_gain : float
        Peak joint offset in radians for the position-actuator path.
    """

    def __init__(
        self,
        meta_df: pd.DataFrame,
        body_ids: list[int],
        force_model: bool = True,
        baseline_hz: float = BASELINE_HZ,
        max_rate_hz: float = MAX_RATE_HZ,
        motor_gain: float = DEFAULT_MOTOR_GAIN,
        fusion_tau_s: float = FUSION_TAU_S,
    ):
        self.force_model = bool(force_model)
        self.baseline_hz = float(baseline_hz)
        self.max_rate_hz = float(max_rate_hz)
        self.motor_gain = float(motor_gain)
        self.fusion_tau_s = float(fusion_tau_s)
        self.n_neurons = len(body_ids)
        self.assignments = _build_assignments(meta_df, body_ids)
        self._muscle_pools = _build_muscle_pools(self.assignments)
        self._dof_pools = _build_dof_pools(self.assignments)
        self._rate_span = self.max_rate_hz - self.baseline_hz

    # -- activation -------------------------------------------------------

    def pool_max_force_un(self, pool: _Pool) -> float:
        """Force in uN the pool delivers with every neuron at its class ceiling.

        This is what ``activation = 1.0`` means under the force model, and it is
        the replacement for ``activation_scale = sum(w_i) * 200 Hz``.  It is
        derived from the per-class maxima of the neurons actually in the pool, so
        it no longer references any single shared rate.
        """
        return float(sum(
            class_force_un(c, CLASS_MAX_RATE_HZ[c], self.fusion_tau_s)
            for c in pool.force_classes
        ))

    def _pool_force_un(self, pool: _Pool, rates: np.ndarray) -> float:
        """Total force in uN from a pool, summed over its neurons' own classes.

        A **sum over neurons**, so recruiting more neurons strictly increases
        force and a silent neuron contributes exactly zero (``class_force_un(c, 0)
        == 0`` for every class).  A mean once drove a joint backwards by
        -0.225 rad when 1 of 8 neurons fired; that failure mode is structurally
        impossible here.
        """
        r = rates[pool.indices]
        return float(sum(
            class_force_un(c, r[j], self.fusion_tau_s)
            for j, c in enumerate(pool.force_classes)
        ))

    def _pool_drive(self, pool: _Pool, rates: np.ndarray) -> float:
        """Pool drive in [0, 1], by the force model or the legacy rate fraction."""
        if self.force_model:
            scale = self.pool_max_force_un(pool)
            if scale <= 0.0:
                return 0.0
            return min(self._pool_force_un(pool, rates) / scale, 1.0)
        excess = np.maximum(rates[pool.indices] - self.baseline_hz, 0.0)
        drive = float(pool.weights @ excess) / (pool.sum_weights * self._rate_span)
        return min(drive, 1.0)

    def _rate_vector(self, rates_hz: dict[int, float]) -> np.ndarray:
        vec = np.zeros(self.n_neurons, dtype=float)
        for idx, rate in rates_hz.items():
            vec[idx] = rate
        return vec

    def muscle_activations(self, rates_hz: dict[int, float]) -> np.ndarray:
        """Activation in [0, 1] for each FlyMimic muscle, in actuator order.

        Parameters
        ----------
        rates_hz : dict
            Network index -> firing rate in Hz.

        Returns
        -------
        ndarray, shape (15,)
            Muscle activations ordered as ``MUSCLE_NAMES``.
        """
        rates = self._rate_vector(rates_hz)
        out = np.zeros(len(MUSCLE_NAMES), dtype=float)
        for i, name in enumerate(MUSCLE_NAMES):
            pool = self._muscle_pools.get(name)
            if pool is not None:
                out[i] = self._pool_drive(pool, rates)
        return out

    def joint_offsets(self, rates_hz: dict[int, float]) -> np.ndarray:
        """Joint-angle offsets in radians for the 66-DOF position actuators.

        Each (leg, DOF) is driven by two antagonist populations. Both are
        decoded with the same unipolar weighted sum as the muscles, then
        differenced, so a bidirectional command emerges from antagonist
        balance rather than from a bipolar per-neuron offset.

        Parameters
        ----------
        rates_hz : dict
            Network index -> firing rate in Hz.

        Returns
        -------
        ndarray, shape (66,)
            Offsets to add to the neutral pose.
        """
        from .locomotion import LEG_OFFSETS

        rates = self._rate_vector(rates_hz)
        offsets = np.zeros(66, dtype=float)
        for (leg, dof), (pos_pool, neg_pool) in self._dof_pools.items():
            drive = 0.0
            if pos_pool is not None:
                drive += self._pool_drive(pos_pool, rates)
            if neg_pool is not None:
                drive -= self._pool_drive(neg_pool, rates)
            offsets[LEG_OFFSETS[leg.lower()] + dof] = self.motor_gain * drive
        return offsets

    def decode(
        self, rates_hz: dict[int, float], neutral_ctrl: np.ndarray
    ) -> np.ndarray:
        """Full 66-DOF position command: neutral pose plus decoded offsets."""
        return neutral_ctrl + self.joint_offsets(rates_hz)

    # -- introspection ----------------------------------------------------

    def assignment_table(self) -> pd.DataFrame:
        """Per-neuron assignment table (one row per leg motor neuron)."""
        from .locomotion import LEG_DOF_NAMES

        rows = []
        for a in self.assignments:
            rows.append({
                "bodyId": a.body_id,
                "net_index": a.net_index,
                "leg": a.leg,
                "type": a.mn_type,
                "size": a.size,
                "force_class": a.force_class,
                "rank": a.class_rank,
                "muscles": ", ".join(a.muscles) if a.muscles else "",
                "dof": "" if a.dof is None else LEG_DOF_NAMES[a.dof],
                "dof_sign": a.dof_sign,
            })
        return pd.DataFrame(rows).sort_values(["leg", "type", "bodyId"])

    def leg_coverage(self) -> pd.DataFrame:
        """Per-leg counts of motor neurons mapped to muscles / DOFs / neither."""
        rows = []
        for leg in LEGS:
            group = [a for a in self.assignments if a.leg == leg]
            n_muscle = sum(1 for a in group if a.muscles)
            n_dof = sum(1 for a in group if a.dof is not None)
            rows.append({
                "leg": leg,
                "n_motor": len(group),
                "n_muscle_mapped": n_muscle,
                "n_dof_mapped": n_dof,
                "n_unmapped": sum(
                    1 for a in group if not a.muscles and a.dof is None
                ),
            })
        return pd.DataFrame(rows)

    def muscle_coverage(self) -> pd.DataFrame:
        """Per-muscle motor neuron counts, contributing types and weight spread."""
        rows = []
        for name in MUSCLE_NAMES:
            pool = self._muscle_pools.get(name)
            members = [a for a in self.assignments if name in a.muscles]
            types = sorted({a.mn_type for a in members})
            rows.append({
                "muscle": name,
                "n_motor": len(members),
                "n_types": len(types),
                "n_fast": sum(1 for a in members if a.force_class == "fast"),
                "n_inter": sum(
                    1 for a in members if a.force_class == "intermediate"
                ),
                "n_slow": sum(1 for a in members if a.force_class == "slow"),
                "max_force_uN": self.pool_max_force_un(pool) if pool else 0.0,
                "types": "; ".join(types),
            })
        return pd.DataFrame(rows)

    def class_summary(self) -> pd.DataFrame:
        """Per-class neuron count, force per spike and rate ceiling."""
        rows = []
        for c in FORCE_CLASSES:
            members = [a for a in self.assignments if a.force_class == c]
            lf = [a for a in members if a.leg == MUSCLE_LEG]
            rows.append({
                "class": c,
                "n_all_legs": len(members),
                "n_LF": len(lf),
                "force_per_spike_uN": FORCE_PER_SPIKE_UN[c],
                "baseline_hz": CLASS_BASELINE_HZ[c],
                "max_rate_hz": CLASS_MAX_RATE_HZ[c],
                "force_at_max_uN": float(
                    class_force_un(c, CLASS_MAX_RATE_HZ[c], self.fusion_tau_s)
                ),
                "size_min": min((a.size for a in lf), default=np.nan),
                "size_max": max((a.size for a in lf), default=np.nan),
            })
        return pd.DataFrame(rows)

    def unmapped_types(self) -> pd.DataFrame:
        """Motor neuron types with neither a muscle nor a DOF assignment."""
        rows = [
            {"leg": a.leg, "type": a.mn_type}
            for a in self.assignments
            if not a.muscles and a.dof is None
        ]
        if not rows:
            return pd.DataFrame(columns=["type", "n_motor", "legs"])
        df = pd.DataFrame(rows)
        return (
            df.groupby("type")
            .agg(n_motor=("leg", "size"), legs=("leg", lambda s: ",".join(sorted(set(s)))))
            .reset_index()
            .sort_values("n_motor", ascending=False)
        )

    def muscle_pool_members(self, muscle: str) -> list[MotorAssignment]:
        """Motor neurons driving one muscle, ordered by descending size."""
        members = [a for a in self.assignments if muscle in a.muscles]
        return sorted(members, key=lambda a: -a.size)


def _build_assignments(
    meta_df: pd.DataFrame, body_ids: list[int]
) -> list[MotorAssignment]:
    """Select leg motor neurons from the connectome and assign their targets."""
    bid_to_idx = {int(bid): i for i, bid in enumerate(body_ids)}

    leg_motor = meta_df[
        (meta_df["superclass"] == "vnc_motor")
        & (meta_df["subclass"].isin(_SUBCLASS_TO_SEGMENT))
    ]

    assignments = []
    for row in leg_motor.itertuples(index=False):
        body_id = int(row.bodyId)
        if body_id not in bid_to_idx:
            continue
        side = "L" if row.somaSide == "L" else "R"
        leg = side + _SUBCLASS_TO_SEGMENT[row.subclass]
        mn_type = "" if pd.isna(row.type) else str(row.type)
        muscles = (
            TYPE_TO_MUSCLES.get(mn_type, ()) if leg == MUSCLE_LEG else ()
        )
        dof_spec = TYPE_TO_DOF.get(mn_type)
        assignments.append(MotorAssignment(
            body_id=body_id,
            net_index=bid_to_idx[body_id],
            mn_type=mn_type,
            leg=leg,
            size=float(row.size),
            muscles=muscles,
            dof=None if dof_spec is None else dof_spec[0],
            dof_sign=0 if dof_spec is None else dof_spec[1],
        ))

    # Force class by size rank WITHIN each anatomical (leg, type) pool.  An
    # assumption -- see ``assign_force_classes`` for what the connectome can and
    # cannot support.
    by_pool: dict[tuple, list[MotorAssignment]] = {}
    for a in assignments:
        by_pool.setdefault(_pool_key(a), []).append(a)
    for members in by_pool.values():
        classes = assign_force_classes([a.size for a in members])
        order = np.argsort([-a.size for a in members], kind="stable")
        rank_of = {int(i): r for r, i in enumerate(order)}
        for j, a in enumerate(members):
            a.force_class = classes[j]
            a.class_rank = rank_of[j]
    return assignments


def _make_pool(members: list[MotorAssignment]) -> _Pool:
    """Build a pool with size weights normalised to mean 1 within the pool."""
    sizes = np.array([a.size for a in members], dtype=float)
    weights = sizes / sizes.mean()
    indices = np.array([a.net_index for a in members], dtype=int)
    return _Pool(
        indices=indices,
        weights=weights,
        force_classes=tuple(a.force_class for a in members),
    )


def _build_muscle_pools(
    assignments: list[MotorAssignment],
) -> dict[str, _Pool]:
    pools: dict[str, _Pool] = {}
    for name in MUSCLE_NAMES:
        members = [a for a in assignments if name in a.muscles]
        if members:
            pools[name] = _make_pool(members)
    return pools


def _build_dof_pools(
    assignments: list[MotorAssignment],
) -> dict[tuple[str, int], tuple[_Pool | None, _Pool | None]]:
    pools: dict[tuple[str, int], tuple[_Pool | None, _Pool | None]] = {}
    keys = {(a.leg, a.dof) for a in assignments if a.dof is not None}
    for leg, dof in sorted(keys):
        pos = [a for a in assignments
               if a.leg == leg and a.dof == dof and a.dof_sign > 0]
        neg = [a for a in assignments
               if a.leg == leg and a.dof == dof and a.dof_sign < 0]
        pools[(leg, dof)] = (
            _make_pool(pos) if pos else None,
            _make_pool(neg) if neg else None,
        )
    return pools


# ---------------------------------------------------------------------------
# Model introspection
# ---------------------------------------------------------------------------


def muscle_actuator_names() -> list[str]:
    """Load the FlyMimic musculoskeletal model and return its muscle names.

    FlyGym's ``MusculoskeletalFly`` already resolves the MJCF's relative mesh
    paths against the downloaded asset cache, so no XML staging is needed.

    Returns
    -------
    list of str
        Muscle actuator names in MuJoCo actuator order.
    """
    import os

    os.environ.setdefault("MUJOCO_GL", "egl")
    from flygym.compose.fly.musculoskeletal import MusculoskeletalFly

    return list(MusculoskeletalFly().muscle_names)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------


def run_muscle_decoder_demo(recruit_muscle: str = "LFTibia_flex_93434") -> None:
    """Demonstrate the full-VNC motor decoder on real connectome data.

    Loads the full VNC (25,635 neurons), builds the connectome-driven
    motor-neuron -> muscle mapping, prints the coverage summary and assignment
    table, then feeds synthetic firing-rate patterns to show that recruitment
    is monotonic and that a single firing neuron produces positive activation.

    Parameters
    ----------
    recruit_muscle : str
        Muscle whose pool is used for the recruitment sweep. Defaults to the
        tibia flexor, which has the largest motor pool (16 neurons).
    """
    from .functional_selection import get_or_build_full_vnc_network

    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 90)

    print("=" * 78)
    print("Full-VNC motor decoder: connectome motor neurons -> FlyMimic muscles")
    print("=" * 78)

    body_ids, meta_df, _motor_leg_map, _s, _t, _w = get_or_build_full_vnc_network()
    decoder = MuscleDecoder(meta_df, body_ids)

    print(f"\nNetwork: {len(body_ids):,} neurons, "
          f"{len(decoder.assignments)} leg motor neurons")

    print("\n--- Model actuator order check ---")
    model_names = muscle_actuator_names()
    match = list(MUSCLE_NAMES) == model_names
    print(f"MUSCLE_NAMES matches MusculoskeletalFly.muscle_names: {match}")
    if not match:
        print(f"  model: {model_names}")

    print("\n--- Per-leg coverage ---")
    print(decoder.leg_coverage().to_string(index=False))

    print("\n--- Per-muscle coverage (LF only; FlyMimic has no other-leg muscles) ---")
    print(decoder.muscle_coverage().to_string(index=False))

    print("\n--- Assignments doc 13 §3 flags as uncertain ---")
    for mn_type, muscle in AMBIGUOUS_ASSIGNMENTS:
        n = sum(1 for a in decoder.assignments
                if a.leg == MUSCLE_LEG and a.mn_type == mn_type)
        print(f"  {muscle} <- {mn_type} ({n} neurons, no direct connectome match)")

    print("\n--- Motor neuron types with no muscle and no DOF assignment ---")
    unmapped = decoder.unmapped_types()
    if unmapped.empty:
        print("(none)")
    else:
        print(unmapped.to_string(index=False))

    print("\n--- Motor neuron force classes ---")
    print("ASSUMPTION, not a connectome annotation: class is assigned by size RANK")
    print("within each (leg, type) pool, with Azevedo's pool proportions "
          "(1 fast : 3.5\nintermediate : rest slow of 15).  `size` cannot carry "
          "the gradient by magnitude --\nthe 5 Ti flexor MNs span only 2.1x, "
          "against a 1000x force ratio -- and Azevedo's\nGal4-identified cells "
          "have no join key to MANC types.  See assign_force_classes.")
    print(decoder.class_summary().to_string(index=False))

    print("\n--- Assignment table (LF leg, all 64 neurons) ---")
    table = decoder.assignment_table()
    print(table[table["leg"] == "LF"].to_string(index=False))

    # ------------------------------------------------------------------
    # Recruitment sweep: does adding neurons monotonically raise activation?
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print(f"Recruitment sweep on {recruit_muscle}")
    print("=" * 78)

    pool = decoder.muscle_pool_members(recruit_muscle)
    muscle_idx = MUSCLE_NAMES.index(recruit_muscle)
    legacy = MuscleDecoder(meta_df, body_ids, force_model=False)
    print(f"Pool: {len(pool)} motor neurons, sizes "
          f"{pool[-1].size:.2e} .. {pool[0].size:.2e}")

    print(f"\nRecruiting largest-first at a PHYSIOLOGICAL 50 Hz "
          f"(slow-MN operating range):")
    print(f"{'n firing':>9} {'class added':>13} {'force act':>10} "
          f"{'legacy act':>11} {'strictly up':>12}")
    prev = -1.0
    for n in range(1, len(pool) + 1):
        rates = {a.net_index: 50.0 for a in pool[:n]}
        activation = float(decoder.muscle_activations(rates)[muscle_idx])
        old = float(legacy.muscle_activations(rates)[muscle_idx])
        print(f"{n:>9} {pool[n - 1].force_class:>13} {activation:>10.4f} "
              f"{old:>11.4f} {'yes' if activation > prev else 'NO':>12}")
        prev = activation

    print("\nSingle-neuron check (each pool member alone at 50 Hz):")
    activations = []
    for a in pool:
        rates = {a.net_index: 50.0}
        activations.append(decoder.muscle_activations(rates)[muscle_idx])
    print(f"  min {min(activations):.6f}  max {max(activations):.6f}  "
          f"all > 0: {all(v > 0 for v in activations)}")

    print("\nWhat one FAST motor neuron delivers per spike count "
          "(saturating by ~10 spikes):")
    fast = next((a for a in pool if a.force_class == "fast"), None)
    if fast is not None:
        print(f"  {'spikes in a 40 ms twitch':>25} {'force (uN)':>11} "
              f"{'muscle activation':>18}")
        for n_spikes in (1, 2, 3, 5, 10, 20):
            rate = n_spikes / FUSION_TAU_S
            act = float(
                decoder.muscle_activations({fast.net_index: rate})[muscle_idx]
            )
            print(f"  {n_spikes:>25} "
                  f"{class_force_un('fast', rate, decoder.fusion_tau_s):>11.3f} "
                  f"{act:>18.4f}")
        print("  2 spikes / 1 spike force ratio: "
              f"{class_force_un('fast', 2 / FUSION_TAU_S) / class_force_un('fast', 1 / FUSION_TAU_S):.3f}"
              "  (Azevedo measured ~1.6x)")

    # ------------------------------------------------------------------
    # Graded rate sweep and the 66-DOF path
    # ------------------------------------------------------------------
    print("\n--- Graded rate sweep (whole pool firing together) ---")
    print(f"{'rate (Hz)':>10} {'force act':>11} {'legacy act':>12} "
          f"{'ratio':>7}")
    for rate in [0.0, 15.0, 30.0, 50.0, 80.0, 100.0, 150.0, 200.0, 400.0]:
        rates = {a.net_index: rate for a in pool}
        new = float(decoder.muscle_activations(rates)[muscle_idx])
        old = float(legacy.muscle_activations(rates)[muscle_idx])
        ratio = f"{new / old:7.2f}" if old > 0 else f"{'inf':>7}"
        print(f"{rate:>10.0f} {new:>11.4f} {old:>12.4f} {ratio}")

    from .locomotion import LEG_DOF_NAMES, LEG_OFFSETS

    print("\n--- 66-DOF position path ---")
    print("Flexors only (every 'Ti flexor MN' + 'Tr flexor MN' at 80 Hz):")
    flexor_rates = {
        a.net_index: 80.0
        for a in decoder.assignments
        if a.mn_type in ("Ti flexor MN", "Tr flexor MN")
    }
    _print_leg_offsets(decoder.joint_offsets(flexor_rates), LEG_OFFSETS, LEG_DOF_NAMES)

    print("\nAll 368 leg motor neurons at 80 Hz (antagonists balance out):")
    all_rates = {a.net_index: 80.0 for a in decoder.assignments}
    _print_leg_offsets(decoder.joint_offsets(all_rates), LEG_OFFSETS, LEG_DOF_NAMES)

    print("\n--- Silence check ---")
    silent = decoder.muscle_activations({})
    print(f"  max muscle activation with no spikes: {silent.max():.6f}")
    print(f"  max |joint offset| with no spikes:    "
          f"{np.abs(decoder.joint_offsets({})).max():.6f}")

    print("\n" + "=" * 78)
    print("Done.")
    print("=" * 78)


def _print_leg_offsets(offsets, leg_offsets, dof_names) -> None:
    for leg in LEGS:
        base = leg_offsets[leg.lower()]
        active = [
            f"{dof_names[d]}={offsets[base + d]:+.3f}"
            for d in range(11)
            if abs(offsets[base + d]) > 1e-9
        ]
        print(f"  {leg}: {'  '.join(active) if active else '(all zero)'}")
