# Sensorimotor Babbling: Developmental Loop Closure

A research idea for pre-training the VNC network through body-mediated
temporal correlation, inspired by fetal motor development.

## Biological Motivation

In vertebrate development, the motor cortex performs spontaneous twitches
before any goal-directed behavior. The sequence:

1. Motor cortex sends random signal → down spinal cord → motor neuron
2. Muscle twitches → joint moves
3. Proprioceptive sensory neuron fires (encoding the movement)
4. Signal travels back → up spinal cord → sensory cortex
5. Sensory cortex confirms to motor cortex: "that signal you just sent
   actually caused this movement"

If the round-trip timing falls within a plasticity window, the loop
strengthens. Loops that don't close (misconnections, wrong targets)
naturally weaken. **The body itself is the teacher** — no external
reward or supervision needed.

This is qualitatively different from goal-directed learning. It solves
a more fundamental problem: *which connections correspond to real
physical movements?* Only after this map is established does
goal-directed optimization make sense.

## Why We Need This

Our current training (reward-modulated three-factor STDP) asks the
network to simultaneously:
1. Discover which pathways produce real body movements
2. Coordinate those movements into forward locomotion

Evidence that this is too much to ask at once:
- Full VNC (25K neurons) with DNa02 stimulation produces negative
  displacement — the wiring is there but the weights are untuned
- Homeostatic plasticity fights STDP (performance declines over
  episodes) — the network hasn't established stable operating points
- 6-hop subset works better than full VNC — smaller network = less
  junk connectivity to sort through

Separating into two phases (developmental babbling → goal-directed
learning) is biologically accurate and may resolve all three issues.

## The Experiment: Three Levels of Loop Closure

We propose testing sensorimotor babbling at three levels, from simplest
to most complex. Each level asks: "does a signal that starts here,
travels through the body (physics), and returns via sensory feedback
make it back to the origin?"

### Level 1: Motor Neuron Loop

```
Motor neuron fires → joint moves → sensory neuron fires →
through VNC interneurons → back to same motor neuron?
```

**What it teaches the network:** Which motor pool controls which joint.
This is the most local loop — the pool learns its own effect.

**Twitch a MOTOR POOL, not a single neuron (revised 2026-08-17).**
The original premise was "one motor neuron learns its own effect." Two
things argue against it:

1. **Latency.** A single neuron moves the joint fast enough only at
   ~200 Hz, leaving almost no margin in the 20 ms window. A pool of
   **4 neurons at 80 Hz** moves it in 11.5 ms.
2. **Biology.** Spontaneous fetal twitches are not single-cell events.
   They recruit localized *synergies* / motor pools. Single-neuron
   stimulation is the less biologically faithful choice, not the purer one.
3. **Propagation (added 2026-08-18, and decisive).** A single synapse
   cannot fire a postsynaptic cell at all — max weight 3.98 mV against an
   11.8 mV requirement. See "The convergence floor" above. This makes
   pools a *hard requirement* rather than a margin-widening choice: the
   single-neuron protocol was not merely tight, it was below the floor for
   signal propagation.

So the shift from single neuron → small pool is a **correction toward
biology**, not a concession to a simulation limit. It does mean Level 1
tests pool-level rather than cell-level credit assignment; cell-level
specificity becomes a question for Level 2 — though reason 3 suggests
cell-level credit assignment may not be a well-posed question in a network
where single cells cannot signal to single cells.

**Protocol:**
- Pick a localized pool of **~4 motor neurons** targeting one muscle,
  drive them at **~80 Hz** for **30-50 ms** (a sustained twitch, NOT a
  5 ms pulse — see `13-motor-neuron-muscle-mapping.md` §8.1: with a brief
  pulse the motor neurons fire entirely *before* sensory feedback returns
  at ~10 ms, so asymmetric STDP reads the pairing as anti-causal and would
  depress the very reflex arcs we want to strengthen)
- Let physics respond (joint angle changes)
- Encode sensory feedback as **current injection** into local ProLN
  sensory neurons (not Poisson spike generation — that destroys the spike
  timing STDP depends on)
- Run STDP (no reward modulation — pure timing correlation)
- Repeat for different motor neurons, randomly
- Run for N episodes of random single-motor-neuron twitches

**What to measure:**
- Before vs after: when motor neuron M fires, does its corresponding
  sensory feedback propagate back to neurons that synapse onto M?
- Specificity: does the loop close ONLY for the correct motor→sensory
  pair, or does everything strengthen indiscriminately?

### Level 2: Interneuron/CPG Loop

```
Intrinsic interneuron fires → through VNC → motor neuron(s) →
joint(s) move → sensory neurons fire → back through VNC →
does signal reach the originating interneuron?
```

**What it teaches the network:** Which interneuron patterns produce
which movement patterns. This is where the CPG coordination lives —
76% of motor drive comes from intrinsic interneurons.

**Protocol:**
- Pick a small cluster of intrinsic interneurons (e.g., 5-10 nearby
  neurons in one segment)
- Inject random current patterns (varying which subset fires)
- Let the signal propagate through the network → motor neurons → body
- Encode all sensory feedback
- Run STDP on the full network
- Repeat with different clusters, random patterns

**What to measure:**
- Do interneuron groups that produce coherent movements (e.g., one
  leg extending) form strengthened loops?
- Does the network self-organize into functional groups that map onto
  specific body movements?
- Is there emergence of alternating patterns (left-right)?

### Level 3: Descending Neuron Loop (Command Level)

```
Descending neuron fires → through VNC circuitry → motor neurons →
body moves → sensory neurons → back through VNC →
does signal reach the descending neuron (or nearby command area)?
```

**What it teaches the network:** Which high-level commands produce which
whole-body sensations. This is the fly equivalent of the motor cortex
learning its body map.

**Protocol:**
- Stimulate individual descending neurons (we have 1,305 of them)
- Let the full VNC circuitry process the command → motor output → body
- Encode all sensory feedback
- Run STDP on the full network (or at least the descending→motor path)
- Focus especially on DNa02 (known walking command)

**What to measure:**
- Does DNa02 stimulation + babbling produce a closed loop that
  eventually generates coordinated leg movements?
- Do different descending neurons develop different sensory signatures?
- Does the network learn to distinguish "walk" from "turn" from "stop"
  based purely on sensorimotor correlation?

## Key Design Decisions

### STDP Without Reward Modulation

During babbling, we use **pure STDP** (two-factor, not three-factor):
- Pre-before-post → strengthen (the loop closed in time)
- Post-before-pre → weaken (spurious correlation)
- NO reward signal — no dopamine modulation

This is because babbling isn't optimizing for any behavior. It's
discovering the physical structure of the body through temporal
correlation. Reward comes later, in phase 2.

### Sustained bursts require bounded weights

The 30-50 ms burst that fixes anti-causality creates a second problem.
Over a 50 ms burst the sensory and motor neurons fire together **many
times**, so a purely additive rule (`w += Δw`) stacks dozens of
potentiation events in a single episode → runaway weights.

**Required:** a hard upper bound `w_max`, or multiplicative soft-bounding
(`Δw ∝ (w_max − w)`), so potentiation saturates instead of exploding.

**Implemented 2026-08-18 as multiplicative soft-bounding.** Potentiation
scales by `(1 − |w|/w_max)`, with `w_max` derived from the connectome's own
weight distribution (`log|w|` is near-Gaussian, so `exp(μ+3σ)` per
polarity): **3.56 mV excitatory, 1.66 mV inhibitory**. Split by polarity
because inhibition carries an extra 0.5 attenuation — one shared ceiling
would let inhibition grow to 2× anything in the connectome.

Verified over 400 × 40 ms unmodulated bursts: weights approach `w_max`
asymptotically with **zero crossings**, increments decaying geometrically.
The same input under the old additive rule reached **22× w_max** — the
runaway was real, not hypothetical.

Soft-bounding was preferred over a hard clip because a clip creates a
population of synapses pinned at exactly `w_max`, destroying the graded
weight differences Child 2 measures.

**Known wrinkle:** 77 real connectome synapses *start* above their own
`w_max` (they are distribution outliers). They cannot grow and depress
normally — but if an experiment reports "synapses at the ceiling," these
are initial values, not STDP growth.

**Still missing: a depression term.** The implemented rule is additive in
both directions — pre-spike adds `Apost` to eligibility, post-spike adds
`Apre`, both positive. Nothing decrements. So the rule cannot weaken a
pathway, and "closed loops strengthen relative to controls" may read flat
for reasons unrelated to biology. Note this also means **the anti-causality
trap described above does not currently exist in our implementation** —
that trap presumes an asymmetric rule with a depression term. The
sustained-burst protocol may still be right (temporal summation,
biological fidelity) but not for the reason originally given. This blocks
Child 2 only; Children 0 and 1 measure conduction and involve no
plasticity.

### What Counts as "Loop Closure"

A loop is closed if: the sensory response to a motor action arrives
back at the origin (or neurons synaptically connected to the origin)
within the STDP window (~20 ms).

**Revised neural delay budget (2026-08-17).** The earlier estimate of
~2 ms for the return path was too optimistic. From *Drosophila*
electrophysiology, each hop costs two separable delays:

- **Synaptic transmission:** ~0.8-1.5 ms per chemical synapse (hard delay)
- **Membrane integration:** the postsynaptic LIF must charge from rest to
  `V_th`, a further ~1-4 ms depending on drive and background activity

This gave rise to a per-hop budget — 2-4 ms direct, 5-8 ms via one
interneuron — which was used to argue that single-neuron babbling at
200 Hz lands at 19.8 ms, flush against the 20 ms window.

**That framing is withdrawn (2026-08-18). Latency is a function of
convergence, not hop count** — see the next section. A per-hop figure is
not well defined without stating how many neurons converge on the target,
because the same "one hop" ranges from 2.6 ms to 12 ms depending on it.

**Synaptic delay is now implemented** (per-synapse, 0.8-1.5 ms, seeded,
on both the Brian2 and PyGeNN paths). Measured cost: **+1.20 ms direct,
+2.40 ms via one interneuron**, identical on both backends. Timings taken
before 2026-08-18 lack this and are optimistic by 1-3 ms per hop.

### The convergence floor: one neuron cannot signal to one neuron

**Discovered 2026-08-18. This is a hard structural constraint on how
small any babbling experiment can be, at every level.**

A LIF neuron fires only if enough charge arrives before the membrane
leaks it away. For a presynaptic neuron firing at 2× rheobase (ISI
8.93 ms), a *single* PSP must exceed
`20 mV · (1 − e^(−0.893)) = 11.8 mV` to reach threshold on its own.

**The largest synaptic weight anywhere in the VNC connectome is 3.98 mV.**

So no single connectome synapse can fire a postsynaptic cell, at any
presynaptic firing rate. Propagation is inherently a **population**
phenomenon: charge must arrive from many presynaptic neurons within a
membrane time constant of each other.

Measured latency against convergent pool size (median |w| = 0.405 mV):

| converging neurons | latency for one hop |
|--------------------|---------------------|
| 60  | **12 ms** |
| 111 (median in-degree) | **4.4 ms** |
| 150 | **2.6 ms** |

A 4.6× spread across the same single hop. Median in-degree in the full
VNC is 111 (mean 160), so convergence of this order is the normal
operating regime rather than a special case.

**Three consequences for the babbling programme:**

1. **The smallest testable origin is a pool, not a cell** — at every
   level, not just Level 1. This is now a *floor*, not a preference:
   single-neuron stimulation tests a configuration that cannot propagate
   even in principle.
2. **Any latency figure must state its pool size** or it is meaningless.
3. **A structurally present pathway may still be unable to conduct.**
   Counting synapses in the connectome establishes that wiring exists;
   it does not establish that a signal crosses it. These are separate
   questions and the second is the one loop closure asks.

Point 3 has an immediate consequence for the Level 1 return path. A
static analysis (2026-08-18, unverified against the live code path)
found the **direct** sensory → motor route may be too thin to conduct:

| return path | convergence | summed PSP if all fire at once |
|-------------|-------------|-------------------------------|
| afferent → MN (121 syn) | median **2** afferents/MN, max 7 | median 1.32, max 8.36 mV |
| afferent → interneuron (1,339 relays) | — | median 1.08, **max 17.65 mV** |

Against the 11.8 mV bar the direct path fails even with every afferent
firing simultaneously, while **6 interneuron relays clear it**
(`IN23B024` strongest at 17.65 mV). If this holds, the return path runs
through a handful of high-convergence relays rather than the ~19,565
one-hop paths previously counted as the resource.

**Caveat: this is single-shot arithmetic.** It asks whether one
synchronous volley fires the target. Sustained 30-50 ms bursts deliver
repeated volleys, and temporal summation may cross threshold where one
volley cannot. "Too weak" here means *too weak for one volley*, not
impossible — which is precisely what needs measuring.

### Why firing rate cannot substitute for convergence

The obvious follow-up: if the problem is not enough charge, why not drive
the presynaptic neurons *faster* instead of recruiting more of them? Both
raise the postsynaptic voltage. They are not, however, interchangeable —
they scale differently, and only one of them is unbounded.

**More neurons firing together scales linearly.** Voltages sum. The median
excitatory weight is 0.638 mV, so ~32 simultaneous neurons reach the 20 mV
threshold (6 at the strongest weight in the connectome). Double the
neurons, double the charge. No ceiling.

**One neuron firing faster saturates.** Successive spikes arrive before the
previous PSP has fully leaked, so charge accumulates — but toward a limit
of `w / (1 − e^(−ISI/τ))`:

| presynaptic rate | ISI | gain over a single spike |
|------------------|-----|--------------------------|
| 50 Hz  | 20 ms | ×1.16 |
| 100 Hz | 10 ms | ×1.58 |
| 200 Hz |  5 ms | ×2.54 |
| 500 Hz |  2 ms | ×5.52 |

At 50 Hz the gain is negligible: 20 ms is 2τ, so the previous PSP has
decayed to 13% before the next arrives. And 500 Hz is a hard ceiling — the
2 ms refractory period means no neuron can fire faster.

**So rate buys at most ×5.52, ever.** Applied to the strongest synapse in
the connectome: 3.98 × 5.52 = **21.96 mV**, barely clearing threshold, and
that is one synapse out of 4.1 million driven at the physiological maximum.
The median excitatory synapse tops out at **3.52 mV — 18% of threshold, and
it can never get there.**

**Consequence: the two ends of the loop have different bottlenecks.**

| stage | integrator | rate ↔ numbers? |
|-------|-----------|-----------------|
| motor → muscle | Hill-type muscle, slow, non-leaky, size-weighted **sum** | **yes, near-interchangeable** — measured: 4 neurons @ 80 Hz ≈ 12 @ 30 Hz ≈ 11.5-16 ms to move |
| afferent → IN → MN | LIF membrane, leaky, τ = 10 ms | **no** — rate capped at ×5.52; numbers dominate |

This is why the thin return path cannot be fixed by driving harder. With a
median of 2 afferents converging on a motor neuron, even 500 Hz gives
`2 × 0.638 × 5.52 = 7.0 mV` against a 20 mV threshold. **The return path's
problem is anatomical, not a matter of drive.**

Raising the babbling drive rate is still worth doing — it moves the joint
sooner and buys physics latency — but it addresses only the outbound half.
The two bottlenecks are independent and have different remedies. There is
also a cost: sustained firing near the refractory ceiling is
unphysiological for fly motor neurons and would distort the spike-timing
statistics that Child 2's plasticity measurement depends on.

**Caveat.** The above is steady-state arithmetic for one synapse in
isolation. Real convergence is *stochastic* — spikes from many afferents
arrive jittered rather than in lockstep, which is **worse** than the linear
estimate, since jitter spreads charge across the leak. The ~32-neuron
figure is therefore a floor, and the true requirement is higher.

### Loop latency grows with loop scope — and what that does (not) imply

**Added 2026-08-18, prompted by external review.**

Measured Level 1 closure is **35-49 ms** for the *shortest possible* loop: one motor pool, one
leg, return via one local interneuron. Physical delays do not shrink as hops are added, so
larger loops are strictly slower. Level 3 would stack an ascending leg, a central stage, and a
descending leg on top of the same physics.

**The useful framing:** the mismatch is not between our model and biology, it is between
**neural and physical timescales**. Spikes propagate in ~1 ms; a joint accelerates against
inertia in 3-15 ms. Once a signal leaves the nervous system it runs on the world's clock. Any
loop routed through the body inherits that, at every level.

**But this does not mean our learning rule is too impatient.** It is tempting to conclude that
a 20 ms window cannot learn a 50 ms loop and that eligibility traces are the missing
ingredient. **We already have them.** `functional_training.py` implements three-factor STDP
with `tau_eligibility_s = 1.0` — a **1000 ms** trace:

```
deligibility/dt = -eligibility / tau_e     (clock-driven, tau_e = 1 s)
on pre:   eligibility += Apost
on post:  eligibility += Apre
```

So a pairing at 40 ms still deposits eligibility that survives a full second until a modulatory
signal arrives. This is the behavioural-timescale mechanism, and it has been present since
Epic 4.1.

**Our own wording invites the misreading.** "The 20 ms STDP window" appears throughout these
documents and sounds like a hard learning cutoff. It is not: `tau_stdp_ms = 20` is the
*pairing* time constant setting eligibility **magnitude**. A 40 ms pairing is weaker, not
excluded. Read "20 ms window" as "the interval over which pairing contributes strongly," never
as a deadline.

**What eligibility traces do not fix.** They solve *temporal* credit assignment — bridging the
gap between action and consequence. They do nothing for *spatial* credit assignment, which is
our actual blocker: the return relay `IN21A004` contacts 46 of 64 LF motor neurons, so the
returning signal cannot indicate *which* motor neuron caused the movement. A longer trace
cannot disambiguate a broadcast. See the Level 1 lab entries.

**Constraint on any Level 3 latency estimate.** The brain is not in our dataset —
`cb_intrinsic` has **4 neurons**. We have 1,305 descending and 1,843 ascending neurons at the
VNC boundary but nothing computing between them, so a "central processing" delay is not
something we can model or measure. "Back to the brain" can only mean "back to the descending
neuron that issued the command."

### Duration of Babbling

Unknown. In humans, fetal motor babbling occurs for months. In our
simulation, the equivalent might be 50-200 episodes of random twitching
before the sensorimotor map is established. This is a parameter to
explore.

## Two-Phase Training Plan

```
Phase 1: Sensorimotor Babbling (this document)
├── Random twitches, no goal
├── Pure STDP (timing only, no reward)
├── Network learns: which connections = real body movements
└── Outcome: refined connection weights, stable operating point

Phase 2: Goal-Directed Learning (existing reward-modulated STDP)
├── DNa02 stimulation for "walk" command
├── Three-factor STDP (timing + reward)
├── Network learns: coordinate movements for forward displacement
└── Outcome: locomotion behavior
```

The hypothesis: Phase 2 will converge faster and more reliably on a
network that has already completed Phase 1, because it's optimizing
over a pre-established sensorimotor map rather than discovering one
from scratch.

## Expected Outcomes

**If babbling works:**
- Specific motor→sensory loops strengthen, others weaken
- Network self-organizes into functional modules matching body segments
- Spontaneous rhythmic activity may emerge (proto-CPG)
- Subsequent reward-based training converges faster

**If babbling doesn't work (and what it would mean):**
- All connections strengthen indiscriminately → STDP window too wide,
  or network too densely connected for timing to discriminate
- No loop closure detected → physics latency exceeds STDP window, or
  sensory encoding doesn't propagate back far enough
- Network goes silent or saturates → homeostatic parameters wrong for
  this regime

## Relationship to Existing Work

- **Reservoir computing:** Babbling could be seen as "tuning the
  reservoir" — making the echo-state network's dynamics match the
  physical system it's embedded in.
- **Embodied cognition:** The body's physics provides the teaching
  signal. The network literally cannot learn this without a body.
- **Developmental robotics:** Similar to work on robot babbling
  (Kuniyoshi, Pfeifer) where random motor exploration builds
  sensorimotor maps before task learning.
