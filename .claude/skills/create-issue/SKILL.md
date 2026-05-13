---
name: create-issue
description: "Create a local issue file in docs/issues/ to capture a problem, bug, feature request, or idea for later triage. Use when the user says 'create issue', 'file an issue', 'log this bug', 'record this problem', or discovers something that needs investigation but doesn't have a fully verified fix approach yet. Also use when the user has a quick thought mid-conversation that should be captured for later."
---

# Create Issue

Capture a problem, bug, feature request, or idea as a local issue file for later
triage. Issues are the "immature" entry point — they describe **what's wrong or
what's needed**, not how to fix it. Later, `/triage-issue` investigates the
codebase and produces a ready-to-execute task file.

**Usage**: `/create-issue [description]`

Examples:
- `/create-issue gh pr checks returns stale data after a new commit push`
- `/create-issue we need webhook automation for PR merge → task completion`
- `/create-issue flaky E2E test in auto-agent integration suite`

## When to Use

- You discover a bug or problem but haven't investigated the codebase yet
- You have a feature idea or improvement to record for later
- Mid-conversation side-discovery that shouldn't derail current work
- Capturing a user report, log observation, or symptom

**When NOT to use** — use `/create-task` instead when:
- You've already read the code and verified the root cause
- The fix approach is known and validated against the codebase
- The conversation has full context (files, line numbers, tested approach)

## Process

### Step 1: Gather Context

Extract from the conversation or user input:

1. **What** — the problem, bug, or feature need (1-3 sentences)
2. **Evidence** — any logs, error messages, screenshots, SQL results, timeline
3. **Impact** — who/what is affected, severity
4. **Discovery context** — what you were doing when this was found
5. **Type** — bug, feature, idea, or exploration

If the user gives a one-liner, that's fine — issues can be lightweight. Don't
over-interview. The goal is to capture enough for someone to pick it up later.

### Step 2: Check for Duplicates

Scan `docs/issues/` for similar issues:
```bash
ls docs/issues/ 2>/dev/null
```

Also check if a task file already covers this:
```bash
ls docs/tasks/ 2>/dev/null
```

If a duplicate exists, tell the user and suggest updating the existing one instead.

### Step 3: Create the File

Save to: `docs/issues/YYYY-MM-DD-<slug>.md`

<!-- CUSTOMIZE: Describe how docs/issues/ is set up in your project.
  An onboarding agent should check:
    1. Whether docs/issues/ exists and is a symlink (readlink -f docs/issues/)
    2. Whether docs/issues/ is gitignored (grep -r 'docs/issues' .gitignore)
    3. Whether the project uses git worktrees (git worktree list)
  Example output for a project that shares issues across worktrees:
    The file goes in `docs/issues/` which symlinks to `.shared-issues/` at the repo
    root. Issue files are gitignored and local-only, shared across worktrees.
  Example output for a simpler project:
    The file goes in `docs/issues/` at the repo root. -->

<!-- CUSTOMIZE: If the project uses git worktrees, add a worktree-aware write path.
  An onboarding agent should run `git worktree list` and check whether docs/issues/
  is a symlink that resolves outside the worktree. If worktrees are not used, remove
  this block entirely.
  Example output for a worktree-based project:
    **In a worktree:** Always write to the **main repo's** `docs/issues/` path (e.g.,
    `/home/youruser/your-project/docs/issues/`), NOT the worktree's path. Resolve the
    real path first if unsure: `readlink -f docs/issues/ || echo docs/issues/` -->

**NEVER use `git add -f` on issue files.** They are local-only, like task files.

Use the appropriate template below based on how much context is available.

### Step 4: Confirm

Show the user:
- File path created
- Issue title and type
- Suggest: "Run `/triage-issue <id>` when you're ready to investigate and create a task."

## Lightweight Template

For quick captures — a thought, one-liner, or side-discovery.

```markdown
---
id: YYYY-MM-DD-<slug>
title: "<Short description>"
created: YYYY-MM-DDTHH:MM
status: open
priority: high | medium | low
type: bug | feature | idea | exploration
related_issues: []
related_tasks: []
github_issue: ""
---

# <Title>

<1-3 sentences describing the problem or need. What was observed, and why it matters.>
```

## Full Template

For issues with evidence, impact analysis, or detailed observations.

```markdown
---
id: YYYY-MM-DD-<slug>
title: "<Short description>"
created: YYYY-MM-DDTHH:MM
status: open
priority: high | medium | low
type: bug | feature | idea | exploration
related_issues: []
related_tasks: []
github_issue: ""
---

# <Title>

## Problem

<What was observed. Be specific: error messages, unexpected behavior, missing
functionality. Describe the symptom, not the diagnosis.>

## Evidence

<Logs, error messages, screenshots, SQL results, timeline of events.
Include enough for someone to reproduce or verify the issue.>

## Impact

<Who is affected? How severe? Is this blocking something?>

## Discovery Context

<What were you doing when this was found? Link to the conversation, PR, or task
that surfaced this issue.>

## Notes

<Any initial thoughts, related issues, or pointers that might help during triage.
Do NOT include a fix approach unless you've verified it against the codebase —
speculative fixes belong in the notes as "possible direction" at most.>
```

## Frontmatter Field Reference

| Field | Required | Values | Notes |
|---|---|---|---|
| `id` | Yes | `YYYY-MM-DD-<slug>` | Must match filename (without `.md`) |
| `title` | Yes | String | Short, descriptive |
| `created` | Yes | `YYYY-MM-DDTHH:MM` | ISO datetime |
| `status` | Yes | `open`, `triaged`, `closed` | `triaged` = task file created |
| `priority` | Yes | `high`, `medium`, `low` | For sorting |
| `type` | Yes | `bug`, `feature`, `idea`, `exploration` | What kind of work |
| `related_issues` | No | List of issue IDs | Related issues |
| `related_tasks` | No | List of task IDs | Task files created from this issue |
| `github_issue` | No | URL string | Link to GitHub issue if one was also created |

## Status Lifecycle

```
open → triaged → closed
         │
         └── related_tasks field links to the task file(s) created
```

- **open** — captured, not yet investigated
- **triaged** — investigated via `/triage-issue`, task file(s) created
- **closed** — resolved (task completed), duplicate, or not actionable
