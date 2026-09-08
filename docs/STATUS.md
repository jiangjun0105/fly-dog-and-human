# Project Status

Last updated: 2026-08-19

## Active

**Sensorimotor babbling** — let the body teach the network which connections move it, before
any reward. Three levels: L1 motor neuron → L2 interneuron/CPG → **L3 descending command
(now active)**.

**Direction change 2026-08-19: L1 is closed, L2 is skipped, we go to the full loop.** The ladder
assumed the shortest loop is the easiest. It is the hardest — every L1 obstacle was a consequence
of being *small* (single synapses cannot fire cells; single-muscle drive recruits too few
afferents; the return relay is wired onto 72% of motor neurons). The broadcast fan-out that
**disqualified** L1 is **correct semantics** for a whole-body command.

And the blocker we assumed was there is not. "The brain is not in our dataset"
(`cb_intrinsic` = 4 neurons) is true but irrelevant — the loop closes inside the VNC:

| return path | convergence | summed PSP | clears 20 mV? |
|-------------|-------------|-----------|---------------|
| L1: afferent → relay | up to 16 | max **15.56 mV** | **never** |
| L3: ascending → DN | median 33, max 321 | **median 28.0 mV** | **841 of 1,305 DNs** |

65,788 ascending→descending synapses reach all 1,305 DNs. `DNa02` (the known walking command)
receives 58-59 ascending neurons delivering ~68-70 mV — 3.4× threshold.

**The bottleneck moved to outbound.** DNa02 is only 2 cells: its 1-hop targets receive median
0.83 / max 4.32 mV, so **0 of 918 reach threshold on one volley**. But DNa02 → X → LF motor
reaches **64 of 64** LF MNs (median 16.9, max 115.7 mV, 30 ≥ 20). So hop 2 and the return are
strong; hop 1 is weak. Likely fix is DN **co-activation** — the same multi-source correction that
rescued L1, one level up.

→ **[Idea: full loop / descending command](ideas/2026-08-19-full-loop-descending-command.md)**

### L3 Child A outbound exit gate — PASSED, and co-activation was the answer

**A descending command fires up to 50 of the 52 in-scope LF motor neurons**, DN → relay
→ MN in **1.6 ms** at best, all four controls clean. **Level 3 is not blocked.**

**But DNa02 does not conduct at any physiological rate.** At 50 Hz it fires **0 of 52**
LF MNs at every background level (0, 75, 100, 115, 125 pA). It conducts only at 500 Hz,
which is this LIF's refractory ceiling and 3.3× above any recorded fly rate.

**DN co-activation is the only physiological route** — 12 cells (6 types) at **50 Hz**
fire **29/52 at 100 pA and 50/52 at 115 pA**. Predicted by the idea doc; the same
multi-source correction that rescued L1, one level up.

**No single resolution sufficed; any two of the three did.** summation+background 49/52 ·
summation+co-activation 39/52 · **background+co-activation 50/52 (the only physiological
combination)**. All three at their minimum: 0/52.

**Controls.** Frozen physics: **0 afferent spikes in all 63 conditions** (asserted).
No-stimulus: **0/52 at every background**. **Cut projection** (same stimulus, the DNs'
outgoing synapses zeroed): **0/52 and 0 relays in all 63**. **Sham DN** (0 mV onto
LF-reaching relays, 121-126 mV elsewhere): **0/52 at all 9 settings**. The cut and sham
controls were added after a first pass that lacked them read as a clean pass in
conditions where the DN's projection could not have been responsible.

**The spec's strong-DN table is retracted** — it used the unsigned `network.py`-comment
formula. On the live path 3 of its 6 types deliver **exactly 0 mV** (all `consensusNt =
unclear` → sign 0), 2 are net **inhibitory**, and only `DNg100` is strong. Live-path
top6 (DNg101/11527, DNg100/10056, aSP22/10090, DNge073/11737, pIP1/10030, DNg37/10506)
fires 39/52 where the spec's set fires **0/52**.

**Candidate artefact #6 tested and NOT confirmed.** L1 withheld the background from its
*driven* pool; here the pool is the *readout* and we left it in. Run both ways, the
command still fires **44/52** with the readout at `V_rest` — worth ~5 MNs and ~4 ms, not
the result.

**The specificity problem changed scale rather than disappearing** (Open Question 3): the
conducting conditions fire 96% of the motor pool, Jaccard overlap between DN sets up to
1.000. **The outbound path is a broadcast too.** The full-loop experiment should ask a
pattern-level question, not a per-cell one.

→ **[Lab: L3 outbound exit gate](lab/2026-08-19-l3-outbound-exit-gate.md)** ·
`python -m digital_drosophila check l3_outbound`

### Sign-policy sensitivity — L1 survives; the L3 DN ranking does not

**The first candidate artefact on this project that was swept and SURVIVED.** The `unclear`
neurotransmitter sign (0 in `constants.NT_SIGN_MAP`, deleting the entire output of 2,931
neurons including 658 motor neurons) was varied 0 / +1 / −1 with everything else held —
serotonin/octopamine/dopamine at 0, histamine at −1, map **imported and overridden**, never
reimplemented.

**Level 1 is identical in all three arms**: 35.4 ms closure, 6 closers, 41/41 afferents,
**0 frozen false positives**, 1.173 rad at 0 pA; 12.4 ms / +5.8 ms at 125 pA. `IN21A004`
800802 holds **46 of 64 LF MNs at +33.17 mV** in every arm. Mechanism: the closing path
contains no `unclear` cell, so the policy cannot reach it. **Not a licence to generalise** —
at 125 pA, 37 neurons switch on under B.

**Spontaneity ceiling re-measured per policy, not assumed.** The 0-125 pA / 0-11 Hz window
transfers to all three; policy B's Poisson headroom *above* it shrinks 20 → **14 Hz**.

**The L3 outbound top-6 IS policy-dependent.** Policy B inserts `DNg34` (10295, +404 mV) and
`DNge149` (11466, +378) at #2 and #3 — both exactly 0.0 mV under A, and `DNg34` is the cell
the L3 spec explicitly retired as silent. **But both have `predictedNt = octopamine`**, so
policy B overrides a modulatory prediction its own rule protects; holding those 101 cells at
0 restores A's list exactly.

**`unclear` is not one class** — 276 of 2,952 have a specific `predictedNt`. Recommendation is
to split by evidence, not pick a blanket sign. Also: the issue's census reads `predictedNt`
(3,377/668); the **live path reads `consensusNt`** (2,931/658, 4.97% of synapses).

→ **[Lab: sign-policy sensitivity](lab/2026-08-19-sign-policy-sensitivity.md)** ·
`python -m digital_drosophila check sign_policy`

### L1 outcome (closed)

**Child 0 complete. The loop conducts — but not in a form Level 1 can use.**

**It closes with multi-joint drive.** Three muscles spanning coxa + trochanter + tibia fire all
41 afferents and wake **7 neurons presynaptic to in-scope LF motor neurons**. Single-muscle
drive fires nothing (0 of 8 conditions) despite the same motor rate and *larger* single-joint
excursions — so **breadth**, not drive strength, was the missing variable, exactly as predicted.
The frozen-physics control is clean: 0 afferent spikes with the leg immobilised, so the signal
genuinely travels through the body rather than via the 34 motor→X→afferent shortcut paths.

**But two measured properties disqualify it from Level 1's actual question:**

1. **The return path is a broadcast.** Its strongest excitatory relay (`IN21A004`) contacts
   **46 of 64 LF motor neurons (72%)**. "The signal returned to a neuron presynaptic to the
   origin" is then nearly guaranteed by anatomy, for *any* origin.
2. **It returns as inhibition.** `IN13A006` −18.24 mV (GABA), `IN21A006` −13.86 (glutamate),
   `IN13A002` −12.76 (GABA), against `IN21A004` +33.17. Our loop diagram assumed excitation.
*(A third property — closure at 35-49 ms — was listed here as disqualifying and is
**withdrawn**. `tau_stdp_ms = 20` sets eligibility *magnitude*, not a deadline; the credit is
carried by `tau_eligibility_s = 1.0` = **1000 ms**, so 35-49 ms is ~5% of its lifetime. Timing
was never the barrier. The 200 ms figure is a stimulus duration, not a plasticity constraint.)

**Level 1 answered its physical question (does a signal return?) but cannot answer its
scientific one (which motor neuron controls which joint)** — the feedback reports *that the leg
moved*, not *which muscle moved it*.

→ **[Lab: multi-muscle loop closure](lab/2026-08-18-multi-muscle-loop-closure.md)** ·
[Lab: the single-muscle return limb fails](lab/2026-08-18-babbling-child0-return-limb-fails.md)

| | scope | status |
|---|-------|--------|
| [0a](issues/2026-08-17-babbling-child0a-neural-model.md) | synaptic delay + STDP soft-bounding | **done** |
| [0b](issues/2026-08-17-babbling-child0b-sensory-calibration.md) | sensory gain calibration + tendon-force channel | **done** |
| [0c](issues/2026-08-17-babbling-child0c-wire-body.md) | `MusculoskeletalFly` wired + exit gate | **done** |
| follow-up | multi-muscle recruitment test | **done — loop closes, but broadcast** |

### The three findings that change the programme

**1. One neuron cannot signal to one neuron.** A single PSP needs >11.8 mV to fire a
postsynaptic cell; the largest weight in the connectome is **3.98 mV**. Propagation is a
population phenomenon, so latency depends on *convergence*, not hop count (12 ms at pool 60,
4.4 ms at 111, 2.6 ms at 150). Rate cannot substitute — accumulation is capped at **×5.52** by
the refractory period, so the median excitatory synapse can *never* reach threshold.

**2. The planned protocol does not conduct.** ~4 neurons at 80 Hz → activation 0.162, **zero
afferent spikes**. Nothing conducts at 30 or 50 Hz at any pool size. Earliest conduction is
pool 2 @ 200 Hz (27.1 ms) — and observed latencies of 6.7-48.3 ms are **mostly outside the
20 ms STDP window**.

**3. Velocity leads on the tibia only.** Tibia flexor: velocity 11.6 ms → position 35.0 →
posture 37.5. But the trochanter closes on **force (17.3 ms) with velocity never firing**, and
one coxa driver closes on position. Child 1 babbles all three groups.

### Retired

- The `recruited × rate → round-trip` scale table — flat 2 ms neural term (wrong variable) and
  a physics term measuring joint-onset rather than afferent spiking (wrong event).
- "2-4 ms direct / 5-8 ms via one interneuron" — ill-defined without a pool size.
- "~4-neuron pools at ~80 Hz" — measured not to conduct.
- The **tonic bias** idea: afferents are 68.1% GABAergic and rest **net-inhibited**
  (−6.3 to −19.4 pA). An excitatory bias would fight the connectome's own gain control.
- The **anti-causality trap** — our STDP rule is additive in both directions and has no
  depression term, so the trap cannot occur. Sustained bursts are still right, but for a
  different reason (temporal summation is load-bearing). Blocks Child 2 only.

- **The 6-hop subnet is retired — the full VNC (25,635 neurons) is the network.** Only 2.7%
  (20/736) of the sensory→motor relay interneurons were in the 6-hop net, so it cannot
  express the reflex loop.
- **Body is `MusculoskeletalFly` + `MusculoskeletalWorld`** — 15 Hill-type muscles (all LF),
  14 joints, no free joint → tethered by construction. `dt = 0.1 ms`.
- See [idea](ideas/2026-08-17-sensorimotor-babbling.md) | [lab result](lab/2026-08-17-babbling-loop-latency.md) | [epic](issues/2026-08-17-sensorimotor-babbling-level1.md)

### The return limb — why single-muscle drive fails, in numbers

*(Superseded by the multi-muscle result above, but kept because it explains the mechanism.)*

| return path | convergence | summed PSP if all fire at once |
|-------------|-------------|-------------------------------|
| afferent → MN (direct) | median 3, max 7 | median 1.70, max **7.97** mV |
| afferent → interneuron (1,339 relays) | up to 16 | median 1.02, max **15.56** mV |

Against the ~11.8 mV single-shot bar only 5 targets clear it, and **nothing reaches 20 mV**.
Forcing all 41 afferents into one synchronous volley fires **nothing**.

**Sustained bursting does work where a single volley cannot** — 200 Hz forced drive fires 13
relays, 5 of them presynaptic to in-scope LF motor neurons (`IN23B024`, `IN21A004`,
`IN13A002`, `IN13B010`, `IN13A006`). Burst duration is load-bearing.

**But physics never delivers it.** Best reachable condition: 22 of 41 afferents fire,
delivering **4.63 of 15.56 mV**. Zero downstream neurons fire.

**Why — the relays are multi-joint integrators.** No single joint group supplies more than
~47% of any top relay's input:

| relay | total | coxa | tibia | trochanter |
|-------|-------|------|-------|------------|
| IN23B024 | 17.65 mV (16 aff) | 4.28 (5) | 5.14 (4) | 8.22 (7) |
| INXXX007 | 14.40 mV (10 aff) | 4.36 (3) | 4.64 (4) | 5.41 (3) |
| IN09A022 | 14.38 mV (14 aff) | 4.54 (5) | 4.06 (3) | 5.78 (6) |

A single-joint twitch recruits ~4 of ~16 inputs — a one-group share of a three-group
requirement. This is why 4.63 mV, and why the fix is breadth rather than drive.

### Calibrated parameters (measured, in place)

- **Gains:** position 700, velocity 1200, force 1400, posture 2000 pA (per-modality — channels
  never reach comparable activations). `max_velocity` 25.0, `max_force` 150.0.
- **Rheobase measured:** 200 pA → 0.0 Hz, 201 pA → 18 Hz.
- **Synaptic delay:** 0.8-1.5 ms, both backends, costing +1.20 ms direct / +2.40 ms 1-hop.
- **STDP soft-bounding:** `w_max` 3.56 mV excitatory / 1.66 mV inhibitory, from the
  connectome's own `exp(mu+3sigma)` per polarity. Zero crossings over 400 bursts; the old
  additive rule hit 22x w_max.
- Position is referenced to measured `SETTLED_LF_ANGLES` — against MJCF `springref` the channel
  was **non-monotonic** (same current at two postures).
- Position is **unsigned**: flexion +0.778 and extension -0.769 rad both give exactly 152 Hz.
  Fine for L1; blocks L2 agonist/antagonist work.
- The old "ground reaction force" channel was a constant **116.2** (Thorax<->Coxa
  interpenetration), not zero — non-zero but unmodulated. Now tendon tension: 1.373 rest ->
  76.7 driven.

### Open — needed before Child 2

- **"20 ms STDP window" is our own misleading shorthand.** `tau_stdp_ms = 20` is the *pairing*
  time constant that sets eligibility **magnitude**, not a learning deadline. We already run
  three-factor STDP with `tau_eligibility_s = 1.0` — a **1000 ms** trace — so a 40 ms pairing
  still deposits eligibility that survives until a modulatory signal arrives. Latencies above
  20 ms are therefore weaker, **not excluded**. Eligibility traces solve *temporal* credit
  assignment; they do nothing for the *spatial* problem (a relay wired to 72% of motor neurons),
  which is the actual blocker.
- **STDP has no depression term.** The rule is additive both directions (pre adds `Apost`, post
  adds `Apre`, both positive); nothing decrements. "Loop weights increased" is near
  uninformative without it, and there is no unmodulated two-factor mode to run at all.
- **No negative control for the neural shortcut.** 0 direct motor->afferent synapses, but **34
  relays** form motor->X->afferent paths reaching 27 of 41 afferents (max 5.10 mV). Sub-threshold
  alone, but the encoder parks afferents near threshold. Control: stimulate with physics frozen,
  confirm no afferent spikes. Not yet run.

## Done

- 2026-09-08: DendSNN prototype (`dendritic.py`) — neuPrint *does* serve skeletons + per-synapse coords, so compartmental models are buildable; but the 4x compartmental/point difference is not separable from unmeasured diameter and leak (sweep spans 0–465 Hz). Not scaled up ([lab entry](lab/2026-09-08-dendritic-compartmental-prototype.md))

- 2026-08-17: Proprioceptive encoder (41 LF afferents) + muscle decoder (58 MN → 15 Hill-type muscles), size-principle weighted sum — fixed a decoding bug where 1 of 8 neurons firing drove joints backwards ([lab entry](lab/2026-08-17-babbling-loop-latency.md))

- 2026-08-15: Functional neuron selection (248n) — 1.49mm mean reward (1.4× over hub-neuron baseline)
- 2026-08-15: GPU backend (Epic 6.1+6.2) — PyGeNN CUDA, 4s/episode vs 118s CPU (30x speedup)
- 2026-08-15: Training harness (Epic 4.2) — homeostatic plasticity + synaptic decay + 50-episode runs
- 2026-08-15: 50-episode CPU training — no behavior change ([lab entry](lab/2026-08-15-stdp-training-no-behavior-change.md))
- 2026-08-15: 10-episode GPU training — homeostasis converges, same non-learning
- 2026-08-15: Video rendering for trained checkpoints (`demo trained --checkpoint PATH`)
- 2026-08-15: Behavioral benchmarks (Epic 5) — framework + baselines ([lab entry](lab/2026-08-15-epic5-behavioral-benchmarks.md))
- 2026-08-15: Three-factor STDP learning (Epic 4.1) — eligibility traces + reward modulation
- 2026-08-15: Sensorimotor loop (Epic 3) — closed-loop Brian2 + FlyGym co-simulation
- 2026-08-15: MuJoCo body (Epic 2) — FlyGym verified, 66 leg actuators, tripod gait
- 2026-08-15: Brian2 network (Epic 1) — connectome → LIF spiking network (100n + 15K full VNC)

## Next

**Level 3 — the full descending-command loop.** Decision made 2026-08-19; rationale and measured
connectome figures in [the idea doc](ideas/2026-08-19-full-loop-descending-command.md).

**1. Outbound exit gate (the L3 analogue of Child 0c).** Stimulate `DNa02` and measure whether LF
motor neurons fire. Hop 1 is the weak link — DNa02's 918 targets get max 4.32 mV against a 20 mV
threshold, so **0 reach it on a single volley**. Three candidate resolutions, and distinguishing
them *is* the experiment:
   - temporal summation (bounded at ×5.52 by refractory → 4.32 mV becomes ~23.8 mV, barely viable)
   - background operating point (the L1 lesson — must be set *before* the first measurement)
   - **DN co-activation** — real walking recruits many DNs, not DNa02 alone. This is the
     biologically faithful option and mirrors L1's multi-muscle correction exactly.

**2. Full loop.** DN → motor → muscle → joint → afferent → ascending → back to the originating DN.
Per-stage latency, frozen-physics control at every step.

**3. Plasticity last.** Child 2's problems are unresolved and should not gate conduction: no STDP
depression term, no unmodulated two-factor mode, and no control set disjoint from the closing
pathways.

**The specificity question does not go away by moving up a level.** With 65,788 ascending→DN
synapses the return may be as broadcast as L1's was — it just changes scale. Worth asking early
whether the loop returns to the *originating* DN or merely to *some* DN.

### Carried-over debt

- **Prior training/benchmark numbers used a decode 3-6× too weak.** `force_model` is now on by
  default in `MuscleDecoder`; whether Epic 4/5/6 conclusions move is **unmeasured**. Recorded in
  commit `1abf33f`.
- **`create_background_drive` defaults to 22 Hz — above the spontaneity ceiling** we measured
  (98.6% of "closers" fire with the leg frozen). The existing training harness may be running in
  a spontaneously-active regime.
- **The unsigned position channel** — flexion +0.778 and extension −0.769 rad both give exactly
  152 Hz. Was acceptable for L1; still unfixed.
- **The L1 epic file is stale** — still specifies "~4-neuron pools at ~80 Hz" and "within 20 ms"
  for Child 1, both retired.
- Untracked and deliberately left alone: `.claude/skills/`, `scripts/`, `docs/process/`,
  `uv.lock`, `demo-task*.md`.

## Documentation

| Folder | Purpose |
|--------|---------|
| `lab/` | Dated experiment reports (what happened + what it means) |
| `ideas/` | Hypothesis backlog (proposed approaches, not yet committed) |
| `issues/` | Engineering specs (epic/issue definitions) |
| `tasks/` | Implementation breakdown (dispatchable work) |
| `neuroscience/` | Theory reference (connectome, LIF, learning strategies) |

**Neuron census:** [`neuroscience/15-lf-leg-neuron-census.md`](neuroscience/15-lf-leg-neuron-census.md)
— how many LF-leg neurons exist vs how many we model (**motor 52/64 = 81%, sensory 41/504 = 8%**),
what is presynaptic to the motor pool (2,047 neurons, 36% of them multi-leg), and why only 7 fire
in our experiments.
