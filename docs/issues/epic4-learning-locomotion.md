# Learning & Locomotion Experiments

**Parent:** epic-phase1-implementation
**Depends on:** child3-sensorimotor-loop

## Desired Behavior

Implement Phase 1 learning rules and demonstrate that the biologically-constrained network can
learn locomotion through localized plasticity. Compare against a random-topology control to test
the core hypothesis: form follows function.

### Demo

Run a training experiment that:
1. Starts with the closed-loop simulation from Child 3 (fly initially twitches randomly)
2. Applies reward-modulated STDP with forward velocity as reward signal
3. After N training episodes, the fly produces coordinated forward locomotion
4. A control network (same neuron count, random connectivity, same learning rules) learns slower or fails to learn
5. Output: learning curve (reward vs. episode) for biological vs. random topology, plus before/after videos

### Tasks (estimated)

1. **STDP implementation** — Three-factor STDP in Brian2: pre-post timing → eligibility trace → dopamine gate. Parameters from doc 04 (tau_eligibility ~1-5s, causal window ~20ms) (~2 tasks)
2. **Reward signal** — Extract forward velocity from MuJoCo body state. Define reward function: `r = v_forward - penalty_for_falling`. Implement dopamine signal broadcast to eligible synapses (~1 task)
3. **Homeostatic plasticity** — Threshold adaptation: `dV_th/dt = eta_homeo * (firing_rate - target_rate)`. Prevents network silence or seizure during learning (~1 task)
4. **Synaptic decay** — Use-it-or-lose-it: inactive synapses fade toward zero with `lambda_decay`. Prunes unused connections (~1 task)
5. **Training loop** — Episode structure: reset fly position, run for T seconds, accumulate reward, update eligibility-gated weights. Log metrics per episode (~1-2 tasks)
6. **Random-topology control** — Generate a control network: same neuron count, same degree distribution, random wiring (destroying biological topology). Same learning rules. Provides the experimental comparison (~1 task)
7. **Analysis & visualization** — Learning curves, weight evolution histograms, gait analysis (leg coordination patterns), statistical comparison (biological vs. random, N runs) (~1-2 tasks)

### Key References

- `docs/neuroscience/04-learning-normal.md` — STDP, reward modulation, homeostasis, decay
- `docs/neuroscience/03-learning-strategies.md` — timescale hierarchy
- `docs/neuroscience/08-implementation-phases.md` — Phase 1 parameter matrix (what's learned vs. fixed)
- `docs/long-term-plan.md` — core hypothesis: biological topology learns faster

### Open Questions

- Episode length? Recommend: start with 5-10s simulated time, adjust based on whether anything emerges.
- How many episodes before we expect learning? Unknown — this is the experiment. Budget for hundreds, hope for tens.
- Should STF/STD (short-term facilitation/depression) be in this child or Phase 2? Doc 08 lists them as Phase 1. Recommend: include as they help CPG rhythm generation.
- Reward shaping? Pure forward velocity may be too sparse. Consider intermediate rewards (e.g., leg movement, not falling). Recommend: start simple, add shaping only if learning fails.

### Success Criteria

1. The biological-topology network produces recognizable forward locomotion (fly moves forward without falling, even if gait is imperfect)
2. Learning curve shows improvement over episodes (not flat)
3. Biological topology outperforms random topology on at least one metric (faster learning, higher final reward, or more stable gait)
