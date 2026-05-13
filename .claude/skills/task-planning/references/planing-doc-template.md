# Planning Document Template

Use this template for the implementation plan saved to
`docs/design/<feature-name>/implementation-plan.md`.

______________________________________________________________________

````markdown
# <Feature Name> — Implementation Plan

> **Design docs:** `docs/design/<feature-name>/`
> **Created:** YYYY-MM-DD
> **Total tasks:** N
> **Parallel waves:** M

______________________________________________________________________

## 1. Summary

<One paragraph: what the feature does, how many components and phases are involved, the
overall shape of the dependency graph (e.g., "3 leaf components can start in parallel,
converging into a central component which has 3 sequential phases"), and how many
parallel waves the plan produces.>

______________________________________________________________________

## 2. Design Doc Inventory

| # | Document | Path | Scope | Phases |
|---|----------|------|-------|--------|
| 1 | High-Level Design | `docs/design/<feature>/high-level-design.md` | System architecture, component inventory, key decisions | — |
| 2 | <Component A> | `docs/design/<feature>/<component-a>.md` | <Brief scope> | N |
| 3 | <Component B> | `docs/design/<feature>/<component-b>.md` | <Brief scope> | N |
| ... | ... | ... | ... | ... |

______________________________________________________________________

## 3. Dependency Graph

### Wave Table

| Wave | Tasks (can run in parallel) | Blocked by |
|------|---------------------------|------------|
| 1 | <Task A>, <Task B>, <Task C> | — (no dependencies) |
| 2 | <Task D>, <Task E> | Wave 1: <Task A> |
| 3 | <Task F> | Wave 2: <Task D>, <Task E> |
| ... | ... | ... |

### Dependency Diagram

<!-- Replace with actual dependencies -->
```mermaid
graph TD
    A[Task A<br/>Component · Phase] --> D[Task D<br/>Component · Phase]
    B[Task B<br/>Component · Phase] --> D
    C[Task C<br/>Component · Phase] --> E[Task E<br/>Component · Phase]
    D --> F[Task F<br/>Component · Phase]
    E --> F
````

______________________________________________________________________

## 4. Task List

| #   | Task              | Component   | Phase                  | Priority     | Dependencies | Est. Scope | Design Doc          |
| --- | ----------------- | ----------- | ---------------------- | ------------ | ------------ | ---------- | ------------------- |
| 1   | <Short task name> | <Component> | \<Phase # or "single"> | high/med/low | —            | ~N files   | `<path>` §<section> |
| 2   | <Short task name> | <Component> | \<Phase #>             | high/med/low | #1           | ~N files   | `<path>` §<section> |
| ... | ...               | ...         | ...                    | ...          | ...          | ...        | ...                 |

______________________________________________________________________

## 5. Parallelization Notes

### What Can Run in Parallel

<Explain which tasks in each wave are truly independent and can be worked on simultaneously
in separate worktrees. Call out any soft dependencies that allow early starts with mocks.>

### Sequential Chains

\<Identify the longest dependency chain (critical path) and explain why it must be
sequential. This helps the user understand the minimum number of waves regardless of
parallelism.>

### Mock Boundaries

\<For tasks with soft dependencies, describe what should be mocked:>

| Task     | Soft Dependency             | What to Mock                                                                           |
| -------- | --------------------------- | -------------------------------------------------------------------------------------- |
| <Task X> | <Depends on Y but can mock> | \<Interface to mock, e.g., "Service B interface — mock create(), update()"> |

______________________________________________________________________

## 6. Risk Notes

<Any concerns spotted during analysis. Examples:>

- \<Component X's spec seems under-specified for the pause/resume flow — the agent may need
  to ask questions during SDD Phase 1.>
- \<The dependency chain from Task 1 → 4 → 8 → 9 → 10 is 5 waves long — this is the
  critical path and can't be parallelized further.>
- \<Task Y touches ~30 files, which exceeds the ~25 file guideline for a single Opus 4.6 1M
  session. Consider splitting only if the files span unrelated concerns.>

______________________________________________________________________

## 7. Getting Started

**Immediate next steps (Wave 1 tasks — no blockers):**

1. <Task A> — <one sentence on what to do first>
1. <Task B> — <one sentence>
1. <Task C> — <one sentence>

**Workflow per task:**

1. Create a worktree: use the worktree-mgmt skill (`.claude/skills/worktree-mgmt/SKILL.md`)
1. Read the design docs referenced in the task file — review them critically
1. Run scenario-driven-dev (`.claude/skills/scenario-driven-dev/SKILL.md`) for implementation
1. Create a PR when done

```

______________________________________________________________________

## Usage Notes

- The wave table and mermaid diagram should reflect the same dependencies — keep them in sync.
- Phase-level granularity: one row per phase per component, not one row per component.
- The "Est. Scope" column is approximate — use the design doc's file lists as a guide.
- Update this plan if tasks are added, split, or reordered during implementation.
```
