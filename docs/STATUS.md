# Project Status

Last updated: 2026-08-18

## Active

**Sensorimotor babbling** — let the body teach the network which connections move it, before
any reward. Three levels: **L1 motor neuron (active)** → L2 interneuron/CPG → L3 descending
command. L1 first because its failure is the only interpretable one.

**Child 0 is complete. The loop conducts — but not in a form Level 1 can use.**

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

**The decision point: does Level 1 continue, or do we move to Level 2?**

Level 1's conduction question is answered. Its scientific question — *which motor neuron
controls which joint* — is not answerable at this level, because closure needs multi-joint
movement and the relays that carry it are wired onto 41-72% of motor neurons (anatomy, not a
measured signal — the discriminability test below is what would settle it).

**0. DONE — and it falsified its own premise.** The decoder defect was real: `max_rate ~ 200 Hz`
was unsourced, unreachable and *divides* activation, making it **3.0x too low at 50 Hz** and
5.7x at 30 Hz; and the decoder had no slow/intermediate/fast classes at all. Both fixed
(per-class force per spike from Azevedo et al. 2020, per-class rate ceilings, `baseline_hz = 15`
retired). The loop now closes under genuinely biological drive: **slow MNs tonic at 30 Hz plus
fast MNs firing 1 spike, closure 35.9 ms**, 12/12 conditions, and at <=80 Hz the leg moves
**0.99x** as far as it did at 200 Hz.

**But "the loop needs 200 Hz" was never true.** The *legacy* decode also closes at **20 Hz**
given a 200 ms burst. Drive was pinned at 200 Hz and rate never swept — which the previous entry
stated in its own Not Verified section. So the 200 Hz was a property of the protocol we chose,
not a requirement the loop imposed. **Third premise on this project to dissolve on measurement,
and ours again** — this time a never-swept parameter misread as a requirement rather than a
constant misread as a finding.

**A second bottleneck was found, and it is not force.** The afferent→closure lag floors at
**28.6 ms** in all 27 closing conditions under either decode, and force gain compresses only the
mechanical half (51.2 → 6.6 ms drive-to-first-afferent). The prediction that latency would
*drop with force* is falsified.
→ **[Lab: motor force classes](lab/2026-08-18-motor-force-classes.md)** ·
[Idea: motor force-per-spike gradient](ideas/2026-08-18-motor-force-gradient.md)

> **CORRECTION (2026-08-18): "~35 ms is a synaptic floor" is wrong, and it is our own choice
> again — the fifth.** All 27 of those conditions ran with `drive` zeroed for every neuron
> outside the driven motor pool, so relay interneurons sat at exactly `V_rest = −70 mV` and had
> to be pushed the full 20 mV by the afferent volley alone. No VNC interneuron is in that state,
> and `create_background_drive` has existed since Epic 1 — **the loop-closure sweeps were the
> outlier in having no background at all.**
>
> Giving the relays a sub-threshold operating point takes the lag from **+28.8 ms to +5.8 ms**
> (closure 35.4 → **12.4 ms**), which is **inside the published 3-6 ms band** our model
> previously missed by 5×. The frozen-physics control is **silent at every usable level** — 0
> closers, 0 afferent spikes, 0 downstream neurons — and the result replicates on a second drive
> protocol (slow30+fast1: 35.9 → 12.5 ms).
>
> **So "the return path is sub-threshold / too thin to conduct" is weakened.** The 15.56-vs-20 mV
> arithmetic is right about one volley; the inference that ~26 ms of integration is *structural*
> is not. It was a property of the operating point we never set.
>
> Usable window: **0-125 pA constant (0-12.5 mV idling), 0-11 Hz Poisson.** Two ceilings, both
> measured: at **poisson 20 Hz** the frozen network fires 1,952 of 1,980 possible closers
> spontaneously (and 22 Hz — `create_background_drive`'s own default — is *above* this); and from
> **130 pA** the recurrent network ignites the driven pool itself (34 → 351 Hz), so those rows are
> a different motor protocol, not a faster return path. Without that second check the headline
> would have read +0.9 ms.
>
> **Unaffected:** the broadcast (`IN21A004` → 46/64 LF MNs), the inhibitory return, the
> multi-joint requirement, the clean frozen control. Level 1's specificity problem is if anything
> slightly worse — 125 closers carry less origin information than 6.
> → **[Lab: the relays' operating point](lab/2026-08-18-relay-operating-point.md)**

**1. The measurement that would settle Level 1 (cheap, one run):** does the return path
*discriminate between origins* at all? Drive muscle set A vs set B and ask whether the closing
relays differ. If they do not, Child 2 has no measurable contrast and Level 1 is done. **This is
now the only open Level 1 question** — conduction, minimum rate and force are all measured.

**2. Every pre-2026-08-18 latency and behaviour number used the legacy decode.** The force model
is now the default for `functional_training` too, so training/STDP results and the Epic 5
benchmarks were produced under a decode 3-6x too weak at physiological rates. Whether that
changes any of them is **unmeasured**. The class assignment is also an **assumption** (size rank
+ Azevedo's pool proportions); `size` spans only 2.1x within the Ti flexor pool against a 1000x
force ratio, and Azevedo's Gal4-identified cells have no join key to MANC types.

**3. Child 2 should not run as written.** It needs (a) a control set genuinely disjoint from the
closing pathways — which may not exist, given the broadcast; (b) a decision about strengthening
an **inhibitory** arc; (c) an STDP depression term, which we still do not have.

**4. Level 2 is the better target.** Interneuron origins sit in far higher-convergence
positions, and "which interneuron *pattern* produces which movement" is a question a broadcast
return path can answer — it asks about patterns, not individual cells.

**Housekeeping:** apply 0b's +2-9% gain correction for in-network inhibition; regenerate the
retired scale table indexed by convergent pool size; add an unmodulated two-factor STDP mode.

**Nothing is committed.** Seven source files across 0a/0b/0c plus the multi-muscle follow-up,
including the shared learning path (`training.py`, `learning.py`) which affects existing
reward-modulated training, not just babbling. Worth a review pass before this grows further.

## Documentation

| Folder | Purpose |
|--------|---------|
| `lab/` | Dated experiment reports (what happened + what it means) |
| `ideas/` | Hypothesis backlog (proposed approaches, not yet committed) |
| `issues/` | Engineering specs (epic/issue definitions) |
| `tasks/` | Implementation breakdown (dispatchable work) |
| `neuroscience/` | Theory reference (connectome, LIF, learning strategies) |
