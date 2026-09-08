# Ideas

Hypothesis backlog and active working docs. Each file starts as a lightweight proposal
and grows into the execution reference when work begins.

**Naming:** `YYYY-MM-DD-<slug>.md`, dated when the idea was first written — same convention
as `docs/lab/` and `docs/issues/`, so `ls -t` orders by recency.

## Lifecycle

```
Proposed  →  Exploring  →  Adopted / Rejected
  (idea)      (working doc)    (archived)
```

- **Proposed**: A candidate approach. Cheap to write, no commitment.
- **Exploring**: Active work in progress. This file is the primary context an executing
  agent loads. It accumulates parameters, decisions, constraints, and intermediate findings.
- **Adopted**: Validated by experiment. Implementation lives in code; file is historical.
- **Rejected**: Disproved by experiment. Keeps its Execution Context (explains why it failed).

## Template

```markdown
# Idea: <title>

**Status:** Proposed | Exploring | Adopted | Rejected
**Date:** YYYY-MM-DD
**Motivation:** one-line link to the problem this addresses

## The Problem
## Proposed Approach
## Expected Outcome
## Trade-offs

## Execution Context
<!-- Added when Status → Exploring. The compact reference for executing agents. -->
- **Parameter:** value — why chosen
- **Constraint:** what can't be done — why
- **Decision:** what was decided — alternatives rejected

## Intermediate Findings
<!-- Added during execution. Partial results, gotchas, surprises. -->
- YYYY-MM-DD: finding — implication

## Resolution
<!-- Added when Status → Adopted/Rejected. -->
- **Lab entry:** [link to docs/lab/...]
- **Outcome:** one-sentence summary
```

## Current Ideas

- [2026-08-19-full-loop-descending-command.md](2026-08-19-full-loop-descending-command.md) — Skip Level 2, test the full descending-command loop: the ascending->DN return path is strong where Level 1's was not (Status: Proposed)
- [2026-08-18-motor-force-gradient.md](2026-08-18-motor-force-gradient.md) — Slow/intermediate/fast force-per-spike classes: the decode really was ~3× too weak, but the 200 Hz it was meant to explain was never required (Status: Implemented — partially confirmed, premise falsified)
- [2026-08-17-sensorimotor-babbling.md](2026-08-17-sensorimotor-babbling.md) — Let the body teach the network which connections move it, before any reward (Status: Exploring)
- [2026-08-15-functional-neuron-selection.md](2026-08-15-functional-neuron-selection.md) — Trace from motor neurons to find the real locomotor circuit (Status: Exploring)
- [2026-08-16-gpu-parallel-training.md](2026-08-16-gpu-parallel-training.md) — MJX batched physics, evolutionary search, or continuous reward signal
