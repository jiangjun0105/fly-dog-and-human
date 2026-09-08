# Epic: GPU-Accelerated Physics via MJX

**Date:** 2026-08-17
**Status:** proposed
**Type:** epic
**Motivation:** MuJoCo CPU physics is the primary bottleneck (~60-70% of wall time). Moving to MJX enables single-episode speedup AND parallel batching.

EPIC — container issue, do not execute; work lives in child issues.

## Problem

The coupling loop runs 1000 steps per episode. Each step:
- GPU neural sim: ~0.1 ms (fast, not the bottleneck)
- Python loop overhead: ~0.1 ms
- **MuJoCo CPU physics: ~0.5-0.8 ms** (THE bottleneck)
- Sensory encode/motor decode: negligible

This means:
- Full VNC (25K neurons): ~17 min/episode
- 6-hop (648 neurons): ~8 s/episode
- Only 1 of 32 CPU cores utilized (sequential loop)
- GPU utilization near 0% (network too small, waits for CPU)

## Desired Outcome

Move the physics simulation to GPU via MJX (MuJoCo XLA/JAX), enabling:
1. **Single-episode speedup:** 5-8× (eliminate CPU physics bottleneck)
2. **Batch parallelism:** Run 8-32 fly bodies simultaneously on GPU
3. **End-to-end GPU pipeline:** Neural sim + physics + encode/decode all on GPU

### Expected speedups

| Scenario | Current | With MJX | Speedup |
|----------|---------|----------|---------|
| Single episode (full VNC) | ~17 min | ~2-3 min | 5-8× |
| Single episode (6-hop) | ~8 s | ~1-2 s | 4-6× |
| Batched 8 episodes (6-hop) | ~64 s | ~3-4 s | 16-20× |
| Batched 32 episodes (full VNC) | ~9 hrs | ~5-10 min | 50-100× |

## Architecture Decision: Neural Sim Backend

**Critical trade-off:** PyGeNN (our current neural sim) uses CUDA directly.
MJX uses JAX/XLA. They cannot share GPU memory without CPU round-trips.

| Option | Description | Speedup | Effort |
|--------|------------|---------|--------|
| A: MJX only, keep PyGeNN | Physics on GPU, neural on GPU (separate), bridge via CPU | 3-5× | Medium |
| B: MJX + JAX neural sim | Replace PyGeNN with JAX spiking network. Entire loop on GPU. | 20-100× | Large |
| C: MJX + batched PyGeNN | MJX batches physics, PyGeNN handles all neural sims in one call | 5-10× | Medium-Large |

**Recommendation:** Start with Option A (quick win, validates MJX integration).
Then Option B as the full investment (everything in JAX = maximum throughput).

## Capabilities (child issues)

### Child 1: MJX Integration — Single Fly (walking skeleton)
**Demo:** Run one 2-second episode with MJX physics on GPU, showing same
behavior as CPU MuJoCo but 5× faster wall time.

- Install `mujoco-mjx` + `jax[cuda12]`
- Verify FlyGym's NeuroMechFly model loads in MJX
- Build `MJXPhysicsBackend` that replaces the MuJoCo step loop
- Handle the PyGeNN↔MJX bridge (GPU→CPU→GPU transfer per step)
- Validate: same forward displacement ±5% vs CPU baseline
- Benchmark: wall time per episode

### Child 2: Batched Physics — Multiple Flies in Parallel
**Demo:** Run 8 flies simultaneously in MJX, each with independent neural
state, showing 8× throughput vs sequential.

- Vectorize the fly body across a batch dimension
- Each fly gets independent joint state but shares the model
- Neural sim runs once with batched currents (or 8× sequential PyGeNN calls)
- Return 8 independent reward signals
- Validate: batch results match sequential results
- Benchmark: 8 parallel vs 8 sequential

### Child 3: JAX Neural Sim (full GPU pipeline)
**Demo:** Entire coupling loop on GPU (no CPU in the hot path). Show 50×+
speedup for batched training.

- Implement LIF neurons with adaptive thresholds in JAX
- Implement STDP eligibility traces in JAX
- Sparse connectivity via JAX sparse ops or dense-with-mask
- Fuse with MJX physics: `jax.lax.scan` over coupling steps
- Validate: same spike rates and eligibility traces vs PyGeNN ±5%
- Benchmark: full training run (50 episodes) wall time

### Child 4: Batched STDP Training
**Demo:** Train with mini-batch STDP (8 parallel episodes, averaged reward).
Show faster convergence AND faster wall time.

- Run K flies per batch, each with same weights but different random seed
- Average the K rewards → single dopamine signal
- Apply averaged eligibility × dopamine → weight update
- Compare learning curve vs sequential (should converge faster due to
  variance reduction + more episodes/hour)

## Dependencies

```
Child 1 (MJX single) → Child 2 (batched physics)
                     → Child 3 (JAX neural) → Child 4 (batched STDP)
```

Child 3 is the largest and most uncertain — JAX sparse spiking networks
are less mature than PyGeNN. May need a spike: "can JAX handle 25K neurons
with 4M sparse connections efficiently?"

## Spike Results (2026-08-17)

Installed `mujoco-mjx` 3.11.0 and tested FlyGym model compatibility.

**Two blockers found:**

1. **Contact sensors (subtree matching):** The 6 ground-contact sensors use
   subtree matching semantics not implemented in MJX. **Workaround:** disable
   them (`add_ground_contact_sensors=False`) — we don't use them in training.

2. **Plane↔Mesh collisions:** The fly model has 69 mesh geometries (body
   segments) and 1 ground plane, with 55 contact pairs. MJX does NOT support
   `(mjGEOM_PLANE, mjGEOM_MESH)` collisions. **No simple workaround** —
   ground contact is essential for locomotion.

**Options to unblock:**

| Option | Description | Feasibility |
|--------|------------|-------------|
| Replace meshes with capsules/spheres | Simplified collision geometry | Medium — changes physics behavior, needs validation |
| Use `mujoco_warp` (NVIDIA Warp backend) | Alternative GPU backend, may support meshes | Unknown — newer, less documented |
| Wait for MJX mesh support | Active development by DeepMind | Unknown timeline |
| FlyGym convex decomposition | Replace meshes with convex hulls (MJX supports convex↔plane) | Medium — FlyGym may have this option |

**Recommendation:** Investigate whether FlyGym can export with convex hull
or capsule approximation geoms. Also evaluate `mujoco_warp` as alternative.
The mesh↔plane limitation makes MJX a medium-term investment, not an
immediate quick win.

**Also:** JAX CUDA not yet installed (`jax[cuda12]`). The test ran on CPU JAX.
Need CUDA jaxlib for actual GPU speedup.

## Risks

1. **FlyGym model compatibility:** ~~FlyGym may use MuJoCo features not yet
   supported by MJX.~~ CONFIRMED: plane↔mesh collisions not supported.
   Contact sensors also unsupported but can be disabled.
2. **JAX sparse performance:** 4.1M sparse synapses in JAX may not outperform
   PyGeNN's optimized CUDA kernels for small networks (648 neurons).
3. **Precision:** MJX defaults to float32; physics stability may differ from
   float64 CPU MuJoCo. Need validation.
4. **Memory:** Batching 32 flies + 25K-neuron networks on a single A10G
   (24 GB) may exceed VRAM.

## Success Criteria

- [ ] Single episode (6-hop) runs in <2s (vs current 8s)
- [ ] 8 parallel episodes complete in <10s total (vs current 64s)
- [ ] Forward displacement matches CPU baseline ±5%
- [ ] Training produces same or better learning curves
- [ ] Full VNC single episode in <5 min (vs current 17 min)
