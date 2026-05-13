# Task File Template (Design-Derived)

Use this template for tasks created from design docs. These tasks are lightweight pointers —
the design docs contain the detailed context. Don't duplicate what's already there.

______________________________________________________________________

```markdown
---
id: YYYY-MM-DD-<feature>-<component>[-p<phase>]
title: "<Feature>: <Component> [Phase <N>] — <Brief description>"
created: YYYY-MM-DDTHH:MM
status: open
priority: high | medium | low
type: task
depends_on:
  - <id-of-dependency-task>
related:
  - <id-of-sibling-task>
branch: ""
pr: ""
---

# <Component> [Phase <N>]: <Brief Description>

## Context

This task implements the **<Component>** component [**Phase <N>**] from the
[<Feature> design](docs/design/<feature>/high-level-design.md). <1-2 sentences on what this
task delivers and why it matters. For single-phase components, omit the phase reference.>

## Design References

**Read these before starting — they contain the full context, data models, API specs, and
rationale for design decisions.**

| Document | Path | Sections to Read |
|----------|------|-----------------|
| High-Level Design | `docs/design/<feature>/high-level-design.md` | §<relevant sections> |
| <Component> Spec | `docs/design/<feature>/<component>.md` | Full document (focus on §Phase Breakdown, §Definition of Done) |
| <Related Component> | `docs/design/<feature>/<related>.md` | §<interface section> (for understanding the boundary) |

## Scope

**Included** (from <Component> spec §Phase Breakdown):

- <Scope item 1 from the phase>
- <Scope item 2>
- <Scope item 3>

**Not included** (handled by other tasks):

- <What's explicitly excluded — other phases or components>

## Implementation Guidance

> **Important:** Review the design docs listed above before starting. If anything doesn't
> make sense or seems wrong at the implementation level, raise it — don't silently comply.
> Design docs capture decisions made at a higher level of abstraction. Implementation often
> reveals issues that weren't visible during design.

- Use **scenario-driven-dev** (`.claude/skills/scenario-driven-dev/SKILL.md`) for the
  implementation workflow (requirements → design → implement → test → review).
- The design doc provides upstream context that narrows SDD Phase 1 (requirements) and
  accelerates SDD Phase 2 (design). See the "Working with Upstream Design Docs" section in
  the SDD skill.
- <Any specific guidance: mock boundaries, patterns to follow, existing code to reference>

## Deferred Integration Assumptions

- <If this task will mock or stub a dependency temporarily, record it here>
- <If none, say "None">

## Verification Follow-Ups

- <State whether this task fully proves its slice or whether later backend runtime /
  browser E2E / manual verification tasks are expected>
- <If a follow-up task already exists, link its task ID here>

## Acceptance Criteria

<Copied or summarized from the design doc's Definition of Done for this phase. Keep these
testable.>

- [ ] <Criterion 1>
- [ ] <Criterion 2>
- [ ] <Criterion N>
- [ ] Existing tests still pass
- [ ] New tests cover the change

## Notes

<Optional: gotchas, configuration values, or brief context that doesn't belong in the
design doc. Keep this short — most context should be in the design doc.>
```

______________________________________________________________________

## Usage Notes

- **Don't repeat the design doc.** The "Design References" table is the most important
  section — it tells the agent where to find the full context.
- **Acceptance criteria** should come from the design doc's Definition of Done. Copy the
  relevant items, don't invent new ones (unless the design doc is missing something).
- **Implementation Guidance** should be brief. A few bullet points on approach, mock
  boundaries, or patterns. The SDD skill handles the detailed implementation workflow.
- **Deferred Integration Assumptions** are how the plan preserves soft dependencies without
  losing track of real integration proof later.
- **Verification Follow-Ups** should make it obvious whether the task is fully proven or still
  depends on a later runtime / E2E / manual verification pass.
- **The "review before you build" note** in Implementation Guidance is intentional. Every
  task should remind the agent to critically evaluate the design, not follow it blindly.
