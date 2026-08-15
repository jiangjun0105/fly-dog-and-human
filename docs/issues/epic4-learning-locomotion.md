# EPIC — Learning & Locomotion Experiments

**EPIC — container, do not execute; work lives in child issues.**

**Parent:** epic-phase1-implementation
**Depends on:** epic3-sensorimotor-loop

## Epic Demo

Run a training experiment: the fly starts twitching randomly (from Epic 3), applies
reward-modulated STDP with forward velocity as reward, and after N episodes produces
recognizable forward locomotion. A random-topology control learns slower, demonstrating
that biological connectivity structure accelerates learning.

## Children (value-sliced: skateboard → bicycle → car)

1. **[Skateboard — Reward-modulated STDP on closed loop](2026-08-15-learning-stdp-reward.md)**: Three-factor STDP (pre-post timing × eligibility × dopamine), reward = forward velocity. Fly learns *something* — any improvement over random baseline.
2. **[Bicycle — Full Phase 1 plasticity + training harness](2026-08-15-learning-full-plasticity.md)**: Add homeostatic plasticity (threshold adaptation), synaptic decay (use-it-or-lose-it), episode structure with logging. The fly produces recognizable forward movement.
3. **[Car — Controlled experiment: biological vs random topology](2026-08-15-learning-experiment.md)**: Random-topology control network (same parameters, scrambled wiring), statistical comparison, learning curves, gait analysis. Answers the research question.

## Dependency Spine

```
Issue 4.1 (STDP + reward) → Issue 4.2 (full plasticity + harness) → Issue 4.3 (experiment)
```

Linear — each thickens the learning capability. All depend on Epic 3 (closed loop) being functional.

## Key Design Decisions

- **Three-factor STDP**: pre-post timing → eligibility trace (tau ~1-5s) → dopamine gate. From doc 04.
- **Reward signal**: `r = v_forward - penalty_for_falling`. Start simple, add shaping only if learning fails.
- **Homeostatic plasticity**: `dV_th/dt = eta_homeo * (firing_rate - target_rate)`. Prevents runaway excitation or silence during learning.
- **Synaptic decay**: `dw/dt = -lambda_decay * w` for inactive synapses. Prunes unused connections.
- **Episode structure**: Reset fly position, run T seconds (start with 5-10s), accumulate reward, update eligibility-gated weights.
- **Control**: Same neuron count, same degree distribution, random wiring. Same learning rules. Only topology differs.

## Success Criteria

1. Biological-topology network produces recognizable forward locomotion (fly moves forward without falling)
2. Learning curve shows improvement over episodes (not flat)
3. Biological topology outperforms random topology on at least one metric (faster learning, higher final reward, or more stable gait)

## Key References

- `docs/neuroscience/04-learning-normal.md` — STDP, reward modulation, homeostasis, decay
- `docs/neuroscience/03-learning-strategies.md` — timescale hierarchy
- `docs/neuroscience/08-implementation-phases.md` — Phase 1 parameter matrix
- `docs/neuroscience/05-stf-std.md` — short-term facilitation/depression (include in Phase 1 per doc 08)

## Open Questions

- Episode length? Start with 5-10s, adjust based on emergence.
- How many episodes to learn? Budget for hundreds, hope for tens.
- Include STF/STD? Doc 08 lists them as Phase 1 — recommended, as they help CPG rhythm generation.
- Reward shaping? Start pure forward velocity; add shaping only if learning is too slow.
