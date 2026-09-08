# Idea: Functional Neuron Selection via Motor Tracing

**Status:** Exploring  
**Date:** 2026-08-15  
**Motivation:** 50-episode STDP training on 100 connectivity-ranked neurons produced no behavior change

## The Problem

Our current 100-neuron sample is selected by connectivity rank (`nlargest(100, "post")`).
This gives hub neurons (49 descending, 18 motor, 18 intrinsic, 15 ascending) — not the
locomotor circuit. The CPG premotor interneurons that create alternating gait patterns are
mid-connectivity neurons that didn't make the cut.

Without the right circuit structure (sensory → interneuron → premotor → motor), STDP has
no gradient to follow and can't discover coordinated locomotion.

## Proposed Approach

Trace backward from identified motor neurons to find the actual locomotor circuit:

1. **Start from motor neurons** — identify them via `exitNerve` column in the connectome
   (neurons whose axons exit through leg nerves). This gives biologically correct motor
   mapping (not round-robin).

2. **Trace upstream** — follow presynaptic connections 2-3 hops back:
   - Motor neurons ← premotor interneurons ← pattern generators ← descending command
   - Use `superclass` annotations (DN = descending, MN = motor, IN = interneuron, AN = ascending)

3. **Target 200-500 neurons** — enough to include the CPG pattern generators but small
   enough for tractable simulation (Brian2 ~30x real-time at 100n, ~5x at 500n estimated).

4. **Preserve biological topology** — the connectivity between these neurons is the actual
   VNC locomotor circuit, giving STDP the structure it needs.

## Expected Outcome

- Motor mapping matches biology (specific motor neurons → specific leg muscles)
- Network already has feedforward structure (the gradient STDP needs)
- Training should fine-tune timing/coordination rather than discover locomotion from scratch
- Expect visible improvement within 10-50 episodes if the circuit is correct

## Key Data Sources

- `exitNerve` column: identifies motor neurons and which leg they innervate
- `superclass` column: neuron type (DN, MN, IN, AN, SN)
- `pre`/`post` columns: synaptic connectivity for tracing
- FlyWire/MANC connectome datasets

## Trade-offs

- **More neurons = slower simulation** — 500n at ~5x real-time means 20s wall-clock per
  2s episode (vs 3s for 100n). GPU backend mitigates this.
- **Circuit completeness vs tractability** — too few neurons misses critical interneurons;
  too many includes irrelevant pathways and dilutes learning signal.
- **Annotation quality** — connectome annotations may be incomplete; some neurons may lack
  `exitNerve` or `superclass` labels.

## Alternatives Considered

- **Full VNC (15K neurons)**: Too slow for iterative training even on GPU
- **Random selection**: No better than connectivity rank — tested and failed
- **Evolutionary/RL approach**: Replace STDP entirely — possible fallback if functional selection still fails

## Execution Context

- **Current neuron selection**: `nlargest(100, "post")` in `network.py` — selects by inbound synapse count
- **Current motor mapping**: round-robin `motor_neuron[i] → leg[i % 6]` — biologically wrong
- **GPU backend**: PyGeNN 5.x working (`gpu_backend.py`), 30x faster than Brian2 CPU. Key API notes:
  - `create_neuron_model` (not `_class`), `params=`/`vars=` (not `param_names`/`var_name_types`)
  - Sparse synapse vars use `.values` not `.view[:]`
  - Reset via `model.timestep = 0` (not `model.t = 0`)
  - Needs 180 pA tonic background current (replaces Brian2's Poisson drive)
- **Training harness**: `training.py` supports `backend="cpu"|"gpu"`, homeostatic plasticity (η=0.01, target=25Hz), synaptic decay (λ=1e-4)
- **Why 100n failed** (4 reasons from lab entry):
  1. Wrong neurons — hub neurons, not locomotor circuit
  2. Impossible credit assignment — 1275 synapses, 1 scalar reward, 2s delay
  3. Arbitrary motor mapping — round-robin instead of exitNerve
  4. No feedforward structure — no gradient for STDP to follow
- **Connectome data**: loaded via neuPrint API (key in `.env` as `NEU_PRINT_API_KEY`). Columns: `bodyId`, `pre`, `post`, `exitNerve`, `superclass`, `somaSide`
- **FlyGym body**: 66 leg DOFs via `LEGS_ONLY` preset. Wings exist geometrically but need aerodynamic plugin — not relevant now.
- **Constraint**: Brian2 simulation speed scales ~linearly with neuron count. At 500n estimate ~20s/episode on CPU; GPU should bring this to ~1-2s/episode.

## Intermediate Findings

- 2026-08-15: 50-episode training (CPU) produced 1.03→1.05mm forward distance — no learning. Confirms wrong-substrate hypothesis.
- 2026-08-15: 10-episode GPU training — homeostasis converges (firing rates reach 25Hz target in ~5 episodes), but same non-learning. Confirms the problem is neuron selection, not the training infrastructure.
- 2026-08-15: Behavioral benchmarks show the untrained network produces 0.46mm/s forward (non-random, consistent) but zero stepping gait (duty factor=1.0, all legs grounded). The structure provides a scaffold but not a solution.
- 2026-08-15: **Functional selection implemented and trained (248 neurons).** Results:
  - Mean reward: 1.49mm per 2s episode (1.4× improvement over 1.04mm hub-neuron baseline)
  - Best episode: 2.50mm
  - The biological motor mapping alone (before STDP) already gives ~1.5× better locomotion
  - STDP training is fighting homeostatic plasticity — reward declines over time (2.15mm early → 1.13mm late)
  - Videos: `reports/functional_baseline_demo.mp4` (untrained) and `reports/functional_trained_demo.mp4` (ep50)
  - Network: 48 motor neurons (8/leg) + 200 premotor interneurons = 248 total
  - Training took ~97 min (50 eps × ~117s/ep on CPU)
- 2026-08-15: **Key insight — homeostatic plasticity is counteracting STDP.** The threshold adaptation + synaptic decay are stronger than the reward signal. Next experiment should reduce/disable these during initial training, or use a stronger reward signal.

## Next Experiments (2026-08-16)

### 1. Improve tooling
- (a) GPU by default — no reason to use CPU anymore (30× speedup, 4s/ep vs 117s)
- (b) Make hop count configurable in functional_selection.py (currently hardcoded to 1)

### 2. Hop count experiments
- (a) Current 1 hop (248n) is too shallow — misses CPG pattern generators at 2 hops
- (b) Implement 2-hop and 3-hop selection in parallel, compare results
- (c) Evaluate using existing STDP algorithm — which network topology learns better?
- Rationale: CPG interneurons (oscillators) are at 2 hops; descending command neurons at 3 hops. More hops = richer internal dynamics for STDP to tune, but slower simulation.

### 3. Homeostatic plasticity tuning
- (a) Current η=0.01 is too strong — erases STDP faster than reward reinforces it
- (b) Try: η=0 (fully off), η=0.005 (half), compare against current η=0.01
- Binary search approach: get a feel for the general effect before fine-tuning
- Also consider removing synaptic decay (λ=0) in the same sweep

### Experiment matrix (6 runs)
| Hops | Homeostasis η | Expected neurons | Expected time/ep (GPU) |
|------|--------------|-----------------|----------------------|
| 2    | 0.0          | ~400-500        | ~8-10s               |
| 2    | 0.005        | ~400-500        | ~8-10s               |
| 3    | 0.0          | ~600-800        | ~12-15s              |
| 3    | 0.005        | ~600-800        | ~12-15s              |

Skip η=0.01 (already shown to fight STDP). Skip 1-hop (already shown too shallow).

### Results (2026-08-16)

| Config | Hops | η | Neurons | Mean reward | Last-10 | Trend |
|--------|------|---|---------|-------------|---------|-------|
| A | 2 | 0.005 | 398 | +0.423 mm | +0.775 mm | Improving |
| B | 3 | 0.005 | 498 | +0.723 mm | +0.934 mm | **Improving (best)** |
| C | 3 | 0.0 | 498 | -0.050 mm | -0.048 mm | Flat (dead) |

**Winner: 3-hop, η=0.005.** Homeostasis is required (η=0 → dead network at 86Hz).
η=0.005 is the sweet spot — stabilizes without fighting STDP.
