---
name: triage-issue
description: "Investigate an issue file against the codebase, determine its nature (easy fix, needs design, needs technical design), and either create a task file or route to the appropriate next step. Use when asked to 'triage', 'triage issue', 'investigate this issue', or when preparing an issue for execution."
---

# Triage Issue

Investigate an issue file from `docs/issues/` against the actual codebase, determine
what kind of work it requires, and route it to the right next step.

**Usage**: `/triage-issue <issue-file-or-id>`

Examples:
- `/triage-issue gh-pr-checks-stale-data`
- `/triage-issue docs/issues/2026-04-12-flaky-e2e-test.md`

## Why This Skill Exists

Issues capture problems and ideas without deep codebase verification. Before any
work begins, someone needs to read the code, verify the claims, and determine what
kind of effort is needed. This skill is that step — it turns a raw issue into either
a ready-to-execute task file or a routing decision for more complex work.

## Process

### Step 1: Resolve and Read the Issue

Search `docs/issues/` for a matching file:
```bash
ls docs/issues/*<argument>*
```

Read and parse the issue file. Extract:
- Title, id, status, priority, type
- Problem description and any evidence
- File paths or code areas mentioned
- Any initial thoughts or notes from the reporter

If `status` is not `open`, warn the user (it may already be triaged or closed).

### Step 2: Ensure Fresh Code

```bash
git fetch origin main
```

Read files from the main repo working directory. Triage is read-only analysis —
no worktree needed.

### Step 3: Deep Code Analysis

Read every file and code area referenced in the issue, plus surrounding context.

#### 3a. Verify the problem exists

- Read the code at the locations described in the issue
- Confirm the described behavior matches what the code actually does
- Check if the problem has already been fixed (recent commits may have addressed it)
- Look for related issues or tasks that overlap

#### 3b. Identify root cause

- Is the issue's description of the problem accurate?
- Is there a deeper root cause the reporter didn't see?
- Are there other code paths with the same problem?

#### 3c. Map the change surface

Use Grep/Explore to find:
- All callers of affected functions
- Related patterns elsewhere (is this bug repeated?)
- Test files covering the affected code
- Configuration or schema that might need updating

#### 3d. Assess complexity

Determine:
- How many files need to change?
- Does it cross service boundaries (backend + frontend)?
- Are there multiple valid approaches with trade-offs?
- Does it require new infrastructure or architectural decisions?

### Step 4: Classify and Route

Based on the analysis, classify the issue into one of four categories:

#### Route Q: Quick Fix (fix directly)

**Signals:**
- Root cause is clear and verified
- Fix approach is obvious (one way to do it, no decisions needed)
- Change surface is tiny: **≤3 files, ≤~30 lines** of actual code changes
- Single concern — one root cause, one fix
- No new infrastructure, no new dependencies, no new APIs
- Existing tests cover the affected code (or the fix is testable by running
  existing tests)

**Why this route exists:** When the triage analysis already identifies exactly which
lines to change, writing a task file for another agent to re-derive the same
understanding is pure overhead. The triage agent already has full context — it
should just do the fix.

**Action:** Propose fixing directly to the user:

> "This is a small fix (~N lines in M files). I can fix it directly and create
> a PR, or create a task file if you'd prefer to dispatch it. What would you like?"

If the user agrees to fix directly:
1. Create a worktree from `origin/main` (use `/worktree-mgmt` procedures)
2. Apply the fix
3. Run the relevant tests to verify
4. Commit, push, and create a PR via `gh pr create`
5. Update the issue file: set `status: triaged` and note the PR URL in the body

If the user prefers a task file, fall through to Route A.

#### Route A: Easy Fix (create task file)

**Signals:**
- Root cause is clear and verified
- Fix approach is straightforward (one obvious way to do it)
- Change surface fits within task capacity (~20 ACs, ~2000 lines, up to 25
  files — 8-15 files comfortable) but **too large for Route Q** (more than
  3 files or more than ~30 lines)
- No architectural decisions needed
- Existing patterns/helpers can be reused

See `/create-task` § "Task Sizing Guide" for the canonical capacity numbers.
Prefer one larger task over splitting when the work is a coherent change.

**Action:** Create a task file via `/create-task` with:
- Verified root cause and file paths
- Concrete fix approach using project patterns
- Acceptance criteria with test commands
- **Verification procedure** that reproduces the original issue scenario and
  confirms it no longer occurs (see below)
- Suitability assessment (`auto_agent_ready` or `human_required`)

Then update the issue file: set `status: triaged` and add the task ID to
`related_tasks`.

#### Route B: Needs Design Discussion

**Signals:**
- Multiple valid approaches with real trade-offs
- Cross-service changes that need coordination
- New abstractions or patterns to decide on
- The fix is clear but the *right* fix depends on priorities or constraints
  only the human knows

**Action:** Present the decision to the user:

> "After investigating, I found the root cause is [X]. There are two viable
> approaches:
>
> **Option A:** [description] — simpler, but [trade-off]
> **Option B:** [description] — more robust, but [cost]
>
> Which direction should I go? Once you decide, I'll create the task file."

Wait for the user's decision, then create the task file via Route A.

#### Route C: Needs Technical Design

**Signals:**
- The issue describes a feature or system change, not a bug
- Multiple components/services need to be designed together
- The scope exceeds single-task capacity (>25 files or >2000 lines), or
  introduces new APIs, new data models, or new services
- Architecture decisions that affect future work

**Action:** Tell the user:

> "This issue needs a technical design before implementation. It involves
> [scope description: new APIs, data model changes, multi-service coordination].
>
> I recommend running `/technical-design` to produce a design doc, then
> `/task-planning` to break it into implementation tasks.
>
> Want me to start the technical design now?"

If the user says yes, invoke `/technical-design`. If not, leave the issue as
`open` with a note about the recommendation.

### Step 5: Present Triage Report

Regardless of the route, always present a summary:

```
## Triage Report: <issue title>

### Problem Verified
<1-2 sentences confirming or correcting the issue description>

### Root Cause
<What the code actually does and why it's wrong / what's missing>

### Change Surface
- **Files:** N files, ~M lines of changes
- **Cross-layer:** backend only / frontend only / both
- **Tests:** existing coverage in [test files] / no existing coverage

### Classification: Route Q / A / B / C
<Rationale for the chosen route>

### Next Step
<What happens next — task created, decision needed, or design recommended>
```

### Step 6: Act Immediately (if user requests)

If the user says "triage and fix it", "triage and create the task", or "let's do it now":

- For **Route Q**: Create worktree, apply fix, run tests, create PR directly
- For **Route A**: Create the task file immediately, suggest dispatch
- For **Route B**: Present the options, get a decision, create the task
- For **Route C**: Start `/technical-design` directly

This "express" mode skips the report-and-wait step for users who want to move fast.

## Before Creating Any Task File

**IMPORTANT:** Before writing a task file (Route Q, A, or B), read the `/create-task`
skill (`SKILL.md`) in full. The create-task skill defines the canonical task template,
frontmatter fields, verification structure, and conventions (e.g., `test-env.sh` commands,
dynamic port variables, test user roles). Do not carry over the triage skill's simpler
verification format — use the create-task template.

## Quality Checklist for Created Task Files

When Route A produces a task file, verify it has:

- [ ] **Accurate line numbers** — verified against current `origin/main`
- [ ] **Correct file paths** — every referenced file exists
- [ ] **Clickable file links** — all file references use relative markdown links from `docs/tasks/` (e.g. `[`group_chat_loop.py:531`](../../apps/server/.../group_chat_loop.py#L531)`)
- [ ] **Project helpers used** — fix approach uses existing patterns, not reimplementations
- [ ] **Imports specified** — any new imports the fix needs are called out
- [ ] **All layers checked** — if the fix spans backend + frontend, both sides documented
- [ ] **Edge cases covered** — fallback behavior, error paths, race conditions
- [ ] **Test commands included** — acceptance criteria include specific test commands
- [ ] **Verification procedure** — reproduces the original issue and confirms it's fixed
- [ ] **Change surface bounded** — within task capacity (~20 ACs, ~2000 lines, up to 25 files; see `/create-task` § "Task Sizing Guide")
- [ ] **One clear approach** — no "choose between A and B" left in the task
- [ ] **Suitability set** — `auto_agent_ready` or `human_required` based on the work

## Writing a Good Verification Section

Every task file should include a **Verification** section that tells the tester agent
exactly how to confirm the original problem is fixed. This section should:

1. **Reproduce the original scenario** — mimic the steps from the issue's reproduction
   section as closely as possible. Use the same commands, data, and sequence.
2. **State what used to happen** — the error, crash, or wrong behavior before the fix.
3. **State what should happen now** — the expected correct behavior after the fix.
4. **Provide a runnable script** — concrete bash commands the tester can execute
   verbatim. No hand-waving like "verify it works" — give exact commands and expected output.

**Example:**

```markdown
## Verification (for tester agent)

Reproduce the original issue scenario and confirm the fix resolves it.

**Setup:**
```bash
# Add a non-null monthly_credit_period_end to a seed row
# (this is what triggered the original crash)
```

**Before this fix:** `just db-seed` crashed with:
```
asyncpg.exceptions.DataError: invalid input for query argument $189
```

**After this fix:** Run the seed and confirm no error:
```bash
just db-seed  # Should complete without errors
# Verify the value was stored correctly:
docker exec sb-postgres psql -U postgres -d sb \
  -c "SELECT monthly_credit_period_end FROM org_subscriptions WHERE id = '5eed0aa3-...';"
# Expected: 2026-05-11 00:00:00+00 (not null, not a string error)
```
```

The tester agent uses this section as its primary verification procedure. Without it,
the tester has to guess how to verify, which often leads to running unit tests (useless)
or inspecting code (not system-level verification).

## Lessons from Practice

### The issue description is often wrong about the cause
Issues capture symptoms, not root causes. The reporter saw an error but may not
have traced it through the code. Always verify — the real fix may be in a different
file entirely.

### Don't create a task for what needs a design
If you find yourself writing a task file with "TODO: decide between Option A and B"
or "this might also need changes to [other service]", stop. That's Route B or C,
not Route A. A task file with embedded decisions wastes agent cycles.

### Oversimplified fix snippets mislead agents
A snippet that uses `dict.get("key")` when the project has a
`_get_latest_session_id()` helper causes the agent to bypass existing
infrastructure. Always check for project-specific helpers.

### The auto-agent doesn't infer — it follows instructions
Be explicit in task files. "Follow the pattern in crew_router.py" is not enough —
specify which method, which lines, which helper functions.

### Don't create a task for what you can fix in 5 minutes
If the triage reveals a ≤30-line fix across ≤3 files with a clear root cause,
just fix it (Route Q). The task file, commit message template, acceptance
criteria, and verification section would take longer to write than the fix
itself. Reserve task files for work that benefits from the documentation —
multi-file changes, non-obvious approaches, or work that will be dispatched
to a cloud agent that lacks the triage context.

### Check if the issue is already fixed
Recent PRs may have resolved the issue. Before creating a task, check:
```bash
git log --oneline origin/main -20
```
If a recent commit addresses it, mark the issue as `closed` instead.
