---
name: create-task
description: Create a task markdown file to capture a fully investigated work item. Use when the user says "create task" and the conversation already has full context — code read, root cause verified, fix approach validated. For quick thoughts, bugs, or ideas that haven't been investigated yet, use /create-issue instead.
---

# Create Task

Create a ready-to-execute task file from a conversation where the problem is already
understood and the fix approach has been verified against the codebase.

**Important:** Task files in `docs/tasks/` are "mature" — they have been investigated,
the approach is validated, and they can be picked up by an agent or human without
further analysis. If you haven't read the code and verified the approach yet, use
`/create-issue` to capture the problem for later triage instead.

## Repository Customization Guide

This skill is a **template**. Out of the box it produces well-structured task files,
but it becomes much more effective when customized with repository-specific knowledge.
Run `/onboard-skills` (or have an agent scan the codebase) to fill in the sections
marked with `<!-- CUSTOMIZE -->` comments throughout this file.

### What to extract from the codebase

An onboarding agent should scan the repository and populate the following. Each item
maps to one or more `<!-- CUSTOMIZE -->` blocks below.

| What to discover | Where it goes in this skill | How to find it |
|---|---|---|
| **Project structure** — top-level dirs, monorepo layout, service boundaries | Key Files template examples, Implementation Approach | `find . -maxdepth 2 -type d`, read README |
| **Tech stack** — languages, frameworks, ORMs, build tools | Implementation Approach guidance, Acceptance Criteria defaults | `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, etc. |
| **Test infrastructure** — frameworks, runners, how to run tests, test directories | Verification § Prerequisites, Implementation Approach | Grep for `pytest`, `jest`, `vitest`, `go test`; inspect CI config |
| **Dev environment setup** — how to start services, ports, env vars, Docker/compose | Verification § Prerequisites, Verification § Manual steps | `docker-compose.yml`, `Makefile`, `Justfile`, `scripts/` |
| **Auth & test users** — seed users, roles, credentials, login flow | Verification § Test user comment | Seed files, migration scripts, auth config |
| **API surface** — key endpoints, request schemas, auth headers | Canonical API Payloads | Route definitions, OpenAPI specs, schema files |
| **External services** — third-party APIs, sandbox/test keys, mock behavior | Verification § Mock vs Real guidance | Environment files, config modules, service adapters |
| **Code patterns** — how the project structures features, common abstractions | Implementation Approach examples, Suggested Approach guidance | Read a few recent PRs or feature modules end-to-end |
| **CI/CD** — pipeline config, required checks, deploy process | Acceptance Criteria defaults | `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile` |

### After customization

Once populated, this skill should contain enough context that a task-writing agent
(or `/triage-issue`) can produce task files that an implementer can pick up without
asking "how do I run the tests?" or "what port does the API listen on?". The inline
`<!-- CUSTOMIZE -->` comments can be removed once filled — they're scaffolding.

## When to Use

- The conversation has full context: code read, root cause verified, approach validated
- A sub-problem or dependency is identified that should be tracked as a separate work item
- `/triage-issue` has investigated an issue and is producing a task file
- `/task-planning` is breaking a design into implementation tasks
- Preparing work items for multi-agent parallel execution

**When NOT to use** — use `/create-issue` instead when:
- You have a quick thought or observation without deep investigation
- You've seen a symptom but haven't verified the root cause in the code
- The fix approach is speculative (not validated against the codebase)

### Step 1: Check Existing Tasks and Issues

Scan `docs/tasks/` and `docs/issues/` to:

- Find the next available task ID for today
- Identify potential dependency or relationship links to existing tasks
- Check if a similar task or issue already exists (avoid duplicates)

### Step 2: Gather Context

Extract from the conversation:

1. **What** — the problem or feature to implement
1. **Why** — why this matters, what's blocked or improved
1. **Desired behavior** — what the system should do after implementation. Describe at
   the right level for the task: **process-level** for workflow/orchestration features
   ("when X finishes, Y happens next"), **API-level** for endpoints ("POST returns 200"),
   or **user-level** for UI ("admin sees a button"). This is the most important section
   — it's what the tester will verify and the reviewer will check against.
1. **Relevant files** — every file path mentioned or relevant (be comprehensive)
1. **Approaches** — any solutions, options, or design decisions discussed.
   **Important:** Only include a detailed suggested approach if the solution was
   discussed with sufficient architectural context (e.g., during a technical design
   session, after reviewing the codebase). If you're reporting a bug or symptom
   without having reviewed the underlying architecture, either omit the approach
   or clearly mark it as speculative. A premature suggestion can mislead the
   implementer into building a workaround instead of using existing patterns.
1. **Implementation method** — how should the work be done? This is especially
   important for verification/testing tasks, refactoring, and tasks that extend
   existing infrastructure. Specify:
   - **What type of artifact to produce:** pytest tests, E2E shell scripts, new
     modules, config changes, etc.
   <!-- CUSTOMIZE: Replace these generic examples with your repo's actual patterns.
     e.g., "extend `tests/integration/test_*.py`", "follow the service pattern in
     `src/services/user_service.py`". An onboarding agent should scan for existing
     test files, scripts, and module patterns to produce concrete examples. -->
   - **What existing files/patterns to follow:** "extend `e2e-dispatch-task.sh`",
     "follow the pattern in `test_orchestrator.py`", etc.
   - **What NOT to do:** "do not add unit tests — this needs live E2E coverage",
     "do not create a new service — extend the existing one", etc.
     Without this, the implementer will choose the easiest interpretation, which may
     not be what you intended. "What to verify" is not enough — "how to verify" matters.
1. **Dependencies** — what other tasks must complete first
1. **Related tasks** — sibling tasks at the same level
1. **Branch context** — is this a follow-up to existing work on a branch? Check:
   - Does the conversation reference an open PR or existing branch?
   - Does a `related` task have a `pr:` or `branch:` field pointing to a branch?
   - Run `git worktree list` to check for existing worktrees that match
   - If yes, set the `branch` field so `/work-task` knows where to work

If the user hasn't provided enough detail for a task, ask clarifying questions or suggest creating an idea instead.

### Step 3: Draft and Confirm Desired Behavior

Before writing the task file, draft the **Desired Behavior** items — the observable,
testable statements of what the system should do after implementation. This section is
the most important part of the task file: it's the contract that the worker implements
against, the tester (`test-task`) verifies against, and the reviewer checks against.

**Draft first, confirm second:**

1. Extract behavioral expectations from the conversation context
1. Write them as numbered statements describing observable system behavior
1. Present them to the human for confirmation using `AskQuestion`
1. Incorporate feedback before writing the task file

**What to ask (process-level example):**

> "Here's what I captured as the expected behavior after implementation:
>
> 1. When a worker finishes coding, control passes to the supervisor (not directly to the reviewer)
> 1. The supervisor reviews the work and decides: send to reviewer, or request changes from the worker
> 1. If the supervisor requests changes, the task returns to the worker with the supervisor's feedback
> 1. Only the supervisor can submit the task for human review
>
> Does this capture the expected behavior? Anything missing, wrong, or that I should
> add for edge cases?"

**What to ask (API-level example):**

> "Here's what I captured as the expected behavior:
>
> 1. POST /tasks/{id}/start returns 200 and transitions a failed task to queued
> 1. POST /tasks/{id}/start returns 409 for completed/queued/running tasks
> 1. Error response includes a message explaining why the task cannot be restarted
>
> Anything missing or wrong?"

**When to confirm (always do at least one of these):**

| Situation                                          | Action                                                                                          |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Task will be **dispatched to cloud agent**         | **Always confirm** — no human in the loop to course-correct                                     |
| Behavior was **explicitly stated** in conversation | **Quick confirm** — present draft, ask "anything missing?"                                      |
| Behavior is **implied but not stated**             | **Detailed confirm** — present draft with edge cases, ask about each                            |
| Simple bug fix with **obvious correct behavior**   | **Skip** — the correct behavior is self-evident (e.g., "login returns 500 → should return 200") |
| User said **"just jot this down"** / idea mode     | **Skip** — they don't want a dialog                                                             |

**Why this matters:** Getting the desired behavior wrong at the task level cascades to
everything downstream. The worker builds the wrong thing, the tester verifies the wrong
criteria, the reviewer approves the wrong code. A 30-second confirmation here saves hours
of wasted agent runs.

### Step 4: Create the File

Save to: `docs/tasks/YYYY-MM-DD-<slug>.md`

> **CRITICAL: Task files are NEVER committed to git.** They are gitignored ephemeral
> work trackers that live in `.shared-tasks/` at the **main repo root**, symlinked via
> `docs/tasks/` → `<main-repo>/.shared-tasks/`. All worktrees share the same directory.
>
> **In a worktree:** Always write to the **main repo's** `docs/tasks/` path, NOT
> the worktree's `docs/tasks/`. If the
> worktree's symlink is set up correctly they're the same, but if the symlink is missing
> or broken, writing to the worktree path creates a file that only exists in that worktree
> and may get committed accidentally. When in doubt, resolve the real path first:
> `readlink -f docs/tasks/ || echo docs/tasks/`
>
> **NEVER use `git add -f` on task files.** If `git add` ignores them, that's correct
> behavior — task files belong in the shared directory, not in git history.

Use the **idea template** or **task template** below based on the mode chosen in Step 1.

### Step 5: Confirm

Show the user:

- The file path created
- The task title and status
- Dependencies and related tasks (if any)
- Suggest running the task board scanner

### Step 6: Suggest Suitability

Before writing the task file, assess whether the task is suitable for autonomous
auto-agent execution and suggest a `suitability` value. **Always verify with the
human before writing.**

**Heuristic signals:**

<!-- CUSTOMIZE: Tune these heuristics for your project. An onboarding agent should
  identify which parts of the codebase are safe for autonomous agents (CRUD endpoints,
  utility modules, tests) vs. which require human oversight (auth, billing, data
  migrations, infrastructure). Add project-specific signals like:
  - "touches `src/billing/` or `src/auth/`" → human_required
  - "only modifies test files under `tests/`" → auto_agent_ready
  - "requires running against staging environment" → human_required -->

| Signal in the task content | → Suggested suitability |
|---|---|
| Clear acceptance criteria, scoped key files (≤5), concrete approach, single service | `auto_agent_ready` |
| Words like "investigate", "debug", "explore", "why is", "look into", "figure out" | `exploration` |
| Mentions "production DB", "auth", "payments", "PII", "security", cross-service coordination | `human_required` |
| Not enough information to classify | `unknown` |

**How to verify** — present the suggestion to the human:

> "Based on the task content, I'd suggest suitability: **auto_agent_ready** because
> it has clear acceptance criteria, affects ≤5 files, and the approach is well-defined.
>
> Suitability options:
> - `auto_agent_ready` — Clear goal, scoped, verifiable. Good for autonomous execution.
> - `human_required` — Needs domain expertise, prod access, or security review.
> - `exploration` — Investigation without a clear definition of done.
> - `unknown` — Not enough info to classify.
>
> Does this look right?"

Use `AskQuestion` for structured selection when appropriate.

The chosen value is written to the `suitability` field in the task file frontmatter.
When dispatched via `/dispatch-task`, this value flows through to the auto-agent API
and triggers a warning dialog in the admin UI for `human_required` or `exploration` tasks.

### Step 7: Suggest Execution Mode

After creating a task file, consider whether it's a good fit for cloud agent dispatch: well-defined coding task, clear acceptance criteria, no local-only deps, all `depends_on` done. If so, suggest:

> "This task looks like a good candidate for cloud agent dispatch.
> Run `/dispatch-task docs/tasks/<file>.md` to send it to the auto-agent system."

For the full dispatch-vs-human decision criteria and configuration, see `.cursor/commands/dispatch-task.md`.

If not a good fit, skip this step — no need to comment on it.

## Task Sizing Guide

All tasks run on **Opus 4.6 with 1M context**. This model can hold large tasks
comfortably — prefer fewer, larger tasks over many small ones.

### Capacity

**Upper limit: ~20 acceptance criteria, ~2000 lines of changes, up to 25 files**

- 8-15 files touched is comfortable; up to 25 is feasible
- Multiple sub-deliverables in one feature are fine (e.g., mock server + integration
  test + fixture setup, or thinning two related prompts + inlining content into
  their corresponding skills)
- Example: building a custom mock server AND the integration tests that use it in
  one task, rather than splitting mock and tests into separate tasks

### Default: One Task per Coherent Change

**Start with one task. Only split when justified.**

A "coherent change" is work that a single developer would naturally do in one PR
and one review cycle. "Touches different files" is not a split reason. "Touches
different agents/services in the same layer" is not a split reason. "Feels tidier
as separate PRs" is not a split reason.

### When to Split

Split into multiple tasks **only** when at least one of these is true:

1. **Different environment/tooling** — e.g., pytest integration tests vs. browser
   E2E tests run in different runtimes and require different skills in context.
2. **Independent value** — each task produces a shippable artifact on its own;
   the other failing doesn't block this one's value.
3. **Different suitability** — one is `auto_agent_ready`, the other is
   `human_required`; merging would force both through human execution.
4. **Combined size exceeds capacity** — >20 ACs, >2000 lines, or >25 files.

If none of these apply, **do not split**.

**Forcing question (before creating 2+ tasks):** Look at every adjacent pair and
ask: *"Same layer? Same pattern? Adjacent files?"* If yes for any pair, merge
them. Examples of pairs that should be one task:
- Two "thin the prompt + inline content into the skill" tasks targeting different agents
- "Add a frontmatter field" + "update the template that generates it"
- "Backend logic change" + "the integration test that verifies it"

### When to Split: Common Patterns

When a split IS justified, use these natural boundaries:

- **Foundation + extension**: schema/infrastructure first, feature second
- **By concern**: backend logic vs. frontend display (different tooling)
- **By independence**: fully independent pieces become parallel tasks

Each sub-task should be independently testable and mergeable. Use the dependency
graph (`depends_on` field) to express ordering.

## Task Board Commands

After creating a task, suggest the relevant command:

```bash
python scripts/task-board.py                # Full board + dependency graph (requires PyYAML)
python scripts/task-board.py --graph        # Dependency graph only
python scripts/task-board.py --mermaid      # Mermaid diagram
python scripts/task-board.py --json         # Machine-readable JSON
python scripts/task-board.py --status open  # Filter by status
python scripts/task-board.py --status done  # Show completed tasks
python scripts/task-board.py --type task    # Show only tasks
```

> **Note:** The script requires PyYAML (`pip install pyyaml`). If PyYAML is not installed,
> it exits with a clear error message. The script auto-detects `docs/tasks/` (a symlink
> to `.shared-tasks/`) from the project root — run it from the repo root or any subdirectory.

## Task Template

**Manual test reference (`manual_test:`)** — if the task touches a service area covered
by an existing test case in `.claude/skills/manual-test/`, set `manual_test:` to that
path (e.g., `manual-test/mcp/db-tools`). The tester will read the referenced file and
follow its procedure. Accepts a single string or a list of strings for multiple test
cases. Leave blank when no existing procedure covers the change; the tester will design
ad-hoc probes or write a new E2E test.

```markdown
---
id: YYYY-MM-DD-<slug>
title: "<Human-readable title>"
created: YYYY-MM-DDTHH:MM
status: open
priority: high | medium | low
type: task
suitability: auto_agent_ready | human_required | exploration | unknown
depends_on:
  - <id-of-dependency-task>
related:
  - <id-of-related-task>
branch: ""
pr: ""
auto_agent_task_id: ""
manual_test: ""
---

# <Title>

## Context

<1-2 paragraphs: Why does this task exist? What was the user/agent doing when this was discovered?>

## Problem

<Clear description of the problem or feature need. Include evidence: logs, error messages, performance numbers.>

## Desired Behavior

<!-- REQUIRED for all tasks. This section defines what the system should do after
  implementation. Describe behaviors at the RIGHT LEVEL OF ABSTRACTION for the task:

  PROCESS-LEVEL — for workflow, orchestration, or multi-step features:
    ✅ "When a worker finishes coding, control passes to the supervisor for review"
    ✅ "The supervisor decides whether to send the work to a reviewer or request changes from the worker"
    ✅ "If the reviewer finds issues, the task returns to the worker — not to the supervisor"
    ✅ "A failed pipeline step can be restarted without re-running completed steps"

  API-LEVEL — for endpoints, services, or data features:
    ✅ "POST /tasks/{id}/start returns 200 and transitions a failed task to queued"
    ✅ "POST /tasks/{id}/start returns 409 with message 'cannot restart' for completed tasks"

  USER-LEVEL — for UI or user-facing features:
    ✅ "Admin UI shows a Restart button only when task status is failed"
    ✅ "After restart, the task progress indicator resets to 'queued'"

  BAD — implementation details (these belong in Suggested Approach / Key Files):
    ❌ "Update the start_task function in task_service.py"
    ❌ "Add failed to START_SOURCE_STATUSES"
    ❌ "Refactor the crew_router.py to call supervisor"

  The rule: describe WHAT HAPPENS from the outside, not HOW it's built on the inside.
  A tester should be able to verify each item without reading the source code.

  The `test-task` skill uses this section as its primary input. Each item becomes one
  test. The `pr-review` skill checks the implementation against these items.

  Include happy path, edge cases, AND error cases.
-->

1. <Process/user/API behavior — what the system does when the feature works correctly>
2. <Error/edge case — what happens when input is invalid or state is wrong>
3. <Additional behavior>

## Key Files

<!-- IMPORTANT: All file paths in this section (and throughout the task file) must be
  clickable markdown links using relative paths from docs/tasks/ (i.e. ../../ prefix).
  Include line numbers via #L<n> anchors where relevant. Examples:

  <!-- CUSTOMIZE: Replace these with real file paths from your repo so the agent
    learns the correct ../../ prefix depth and your naming conventions. An onboarding
    agent should pick 3-5 representative files (an API route, a service, a test). -->
  | [`api_handler.py:42`](../../src/api/api_handler.py#L42) | Request routing and validation |
  | [`task_service.py:87-95`](../../src/services/task_service.py#L87-L95) | Task state transition logic |
  | [`test_task_service.py`](../../tests/test_task_service.py) | Integration tests for task service |

  This applies everywhere a file is referenced: Key Files table, inline references in
  Problem/Root Cause/Approach sections, and the Files to Change table. The reader should
  be able to click any file reference and jump directly to the relevant code.
-->

| File | Purpose |
|------|---------|
| [`path/to/file.py`](../../path/to/file.py) | <what this file does and why it's relevant> |

## Suggested Approach

<!-- When to include this section:

  1. FROM A DESIGN DISCUSSION — You've already analyzed the codebase, discussed the
     architecture, and decided on an approach. Include it as a decision record — this
     is valuable context that saves the implementer from re-deriving what was already
     discussed. Use numbered options if multiple approaches were evaluated.

  2. FROM A BUG REPORT OR SYMPTOM OBSERVATION — You saw the symptom but didn't dig
     into the root cause or review the existing architecture. In this case, either:
     (a) OMIT this section entirely and let the implementer research the codebase, or
     (b) Include it but clearly mark it as speculative (see note below).

  The distinction matters: a premature suggested approach can lead the implementer
  to build a workaround instead of using the existing architecture's patterns. When
  in doubt, describe the problem thoroughly and let the implementer decide the approach.
-->

<Solution ideas from the conversation. Use numbered options if multiple approaches were discussed.>

### Option A: <Name>

<Description, pros, cons>

### Recommendation

<Which option and why>

<!-- If the suggested approach is speculative (reporter didn't review the codebase
  architecture), add this note: -->

> **Note:** This approach is based on the observed symptom, not a detailed review of
> the codebase architecture. The implementer should investigate the existing patterns
> and infrastructure before following this suggestion — there may be a better way that
> aligns with the existing design.

<!-- If the suggested approach includes a specific code diff, add this note: -->

> **Note:** The diff above shows the *core change* — treat it as a starting point, not
> a complete implementation. Before committing, verify that surrounding code is also
> consistent: callers of the changed function, related config, and (for React) hook
> dependency arrays. The task file describes the *objective*; the worker is responsible
> for finding all the code that needs to change to meet it.

## Implementation Approach

<!-- Always include this section — it tells the implementer HOW to do the work,
  not just WHAT the work is. This is the most common gap in task files: describing
  the desired outcome without specifying the method. Examples:

  Good: "Extend scripts/e2e-dispatch-task.sh with a --test-supervisor flag"
  Bad:  "Verify the supervisor works end-to-end" (implementer chose pytest instead of E2E scripts)

  Good: "Add a new MCP tool in mcp_tools.py following the submit_task pattern"
  Bad:  "Store the PR URL somewhere" (implementer scraped the transcript instead)

  For testing/verification tasks, specify: what kind of tests (unit, integration,
  E2E shell script, manual), which existing test files or scripts to extend, and
  what infrastructure is needed (local Docker, CI, etc.).

  <!-- CUSTOMIZE: Replace the Good/Bad examples above with examples from your actual
    repo. An onboarding agent should find 2-3 real test scripts, Makefiles, or
    existing patterns and write "Good" examples referencing them. This teaches
    task-writers to point implementers at the right infrastructure. -->
-->

- **Artifact type:** <what to produce — e.g., "pytest integration tests", "E2E shell script extension", "new Python module">
- **Extend existing:** <files/patterns to follow — e.g., "extend `scripts/e2e-dispatch-task.sh`", "follow `test_orchestrator.py` pattern">
- **Do not:** <anti-patterns to avoid — e.g., "do not add unit tests with mocks — this needs live E2E coverage">

## Acceptance Criteria

<!-- This is the worker's implementation checklist. It should reference the Desired
  Behavior items above and add implementation-specific checks.

  Structure:
  - First items: "All desired behaviors (1-N) are implemented and verified"
  - Then: implementation-specific checks (tests pass, migrations, config, etc.)
-->

- [ ] All desired behaviors (1-N above) are implemented and verified
- [ ] Existing tests still pass
- [ ] Integration tests cover each desired behavior item
- [ ] <Any implementation-specific criterion — e.g., "migration added for new column">

## Verification (for tester agent)

<!-- REQUIRED for all tasks. This section is handed to a tester agent who has
  never seen the codebase. Design it so they can execute without guesswork.

  Full guidelines: .claude/skills/manual-test/SKILL.md § "Verification Design Principles"

  Checklist for writing good verification steps:

  1. BE SPECIFIC AND RUNNABLE — every step is a concrete command or UI action.
     Bad: "Check the login page." Good: "Navigate to http://localhost:8080/admin/login,
     type 'testuser' in the username field, click Sign in."

  <!-- CUSTOMIZE: Replace this generic guidance with your project's actual test
    users, roles, and credential sources. An onboarding agent should scan seed
    files, auth config, and migration scripts to build a table like:
      - Protected routes/resources → test user with appropriate role (seeded in DB, config, or fixture)
      - Service-to-service auth → credentials from env config or test fixture
      - Hardware/device access → simulator profile or test certificate
    Include default credentials and how to override them. -->
  2. SPECIFY THE TEST USER AND REQUIRED ROLE — different routes require
     different user roles. The tester agent cannot guess this.
     State the user, role, and credentials needed for each verification step.
     If the project has a test user guide, reference it here.

  3. PROVIDE TEST DATA — what DB state must exist? How to set it up?
     Include setup commands or point to seed data docs.

  <!-- CUSTOMIZE: Replace with your project's actual startup commands. Examples
    from different project types:
      - Web app: `docker compose up -d && npm run dev`
      - Embedded/firmware: `./scripts/start-simulator.sh && make run`
      - Mobile (Flutter): `flutter run -d linux` or `flutter test integration_test/`
      - CLI tool: `cargo build && ./target/debug/mytool --test-mode`
    An onboarding agent should scan docker-compose.yml, Makefile, Justfile,
    CMakeLists.txt, and scripts/ to find the canonical way to start the test stack. -->
  4. DECLARE SERVICE DEPENDENCIES — which services must be running?
     State which services, databases, or infrastructure the tester needs
     to start and how to start them.

  <!-- CUSTOMIZE: List your project's actual external service integrations and
    their test behavior. An onboarding agent should scan for API client configs,
    env vars with API keys, and service adapters. Example output for different domains:
      - Payment provider (e.g., Stripe): test mode keys → charges succeed but are not real
      - Hardware simulator (e.g., JTAG/SWD): mock probe → firmware flashed to virtual target
      - Cloud API sandbox (e.g., S3, GCS): local emulator via docker-compose → no cloud credentials needed
    List each third-party service, its test/sandbox mode, and the expected behavior. -->
  5. MOCK VS REAL — if external services are involved, state expected behavior.
     Specify which services use test/sandbox keys and what behavior to expect
     (e.g., test payment keys return mock responses, not real charges).

  6. INCLUDE BOTH API AND BROWSER CHECKS when applicable — curl verifies the
     backend; browser verifies the UI. Both catch different bugs.

  7. INCLUDE CLEANUP — how to revert test data after the test.
     (When a "Human manual test" section is present, cleanup moves to
     the human's responsibility — see item 4 below.)

  Structure:
  1. Manual test skill — reference from manual-test library, or "N/A"
  2. Manual verification steps — concrete commands and expected outcomes
  3. What "working" looks like — observable outcomes that prove correctness
  4. Human manual test (optional) — when full verification requires interaction
     with external hosted services (Stripe onboarding, OAuth flows, third-party
     redirects) that the tester agent cannot navigate. When this section is
     present, the tester agent does NOT tear down the test stack after its
     automated checks. Instead it posts its verification report and escalates
     to the human with the exact instructions from this section.

  COMMON MISTAKE: Do NOT hardcode ports or assume the local dev stack is
  running. Specify the exact commands to start the test environment and
  use environment variables for dynamic ports when applicable.
-->

### Manual test skill
<manual-test/<service-area>/<slug> — or "N/A — design ad-hoc probes" if no existing procedure matches>

<!-- CUSTOMIZE: After onboarding, replace this comment with a concrete test user
  or credential reference block for this project. Example of what the onboarding
  agent should produce (varies by project type):

  For a web/API project:
  - Protected resources → use seeded test user with appropriate role
  - Service endpoints → use credentials from test environment config
  For an embedded/hardware project:
  - Device access → use simulator profile (e.g., `test-device-001`)
  - Debug interface → credentials in `test/fixtures/auth.json`
  For a CLI/SDK:
  - Auth-gated commands → use token from `./scripts/get-test-token.sh`
  - Full reference: docs/testing/credentials.md
-->

### Prerequisites

Start the test environment:

<!-- CUSTOMIZE: Replace this placeholder with the actual commands to start your
  test environment. The onboarding agent should discover:
  - Docker/compose commands for infrastructure (DB, cache, queues)
  - Application start commands (dev server, API server, workers)
  - Seed/migration commands (if not automatic)
  - Environment variable setup (test env config files, etc.)
  - Port or connection information (static or dynamic via env vars)
  Example output (varies by project type):
    Web app:
      `docker compose -f docker-compose.test.yml up -d && npm run migrate && npm run dev`
    Embedded/firmware:
      `./scripts/start-simulator.sh && make flash-test`
    Data pipeline:
      `docker compose up -d kafka zookeeper && python -m pytest --setup-show`
-->
```bash
# Add project-specific test environment setup commands here
```

<Add any task-specific prerequisites here, or remove this line if none>

### Manual verification steps
1. <Concrete step to exercise the feature — use test-env port vars ($TEST_API_PORT, $TEST_FRONTEND_PORT)>
2. <Expected observable outcome — API response, DB state, UI element>
3. <Additional verification step>

### What "working" looks like
- <Observable outcome 1 — e.g., "API returns 200 with `is_anonymous: false`">
- <Observable outcome 2 — e.g., "No duplicate rows in `users` table">
- <Observable outcome 3 — e.g., "Admin UI shows success message after restart">

### Human manual test
<!-- OPTIONAL — only include when full verification requires interaction with
  external hosted services that the tester agent cannot navigate (Stripe
  onboarding pages, OAuth consent screens, third-party redirect flows, etc.).

  When this section is present:
  - The tester agent does NOT run cleanup / tear down the test stack
  - The tester posts its automated verification report first
  - Then escalates to the human with the message below

  Write the escalation message as a blockquote (>) containing:
  1. A title line explaining what manual test is needed
  2. A note that automated checks are done and the stack is still running
  3. Numbered steps the human should follow (URLs, credentials, test data)
  4. What to observe at each step
  5. The cleanup command to run when done
-->

> **Manual test needed — <describe what needs human verification>**
>
> The automated checks are done. The test stack is still running.
> Please complete the following manually:
>
> 1. Open **<URL>** in your browser
> 2. <Step with specific credentials, test data, and expected observation>
> 3. <Additional steps>
>
> When done, tear down the test stack:
> ```bash
> # Add project-specific teardown command here
> ```

## Notes

<Additional context, gotchas, code snippets, or configuration values.>
```

## Frontmatter Field Reference

| Field                | Required | Values                                   | Notes                                                                                                                                                         |
| -------------------- | -------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`                 | Yes      | `YYYY-MM-DD-<slug>`                      | Must match filename (without `.md`)                                                                                                                           |
| `title`              | Yes      | String                                   | Short, descriptive                                                                                                                                            |
| `created`            | Yes      | `YYYY-MM-DDTHH:MM`                       | ISO datetime                                                                                                                                                  |
| `status`             | Yes      | `open`, `in-progress`, `done`, `blocked` | Scanner uses this                                                                                                                                             |
| `priority`           | Yes      | `high`, `medium`, `low`                  | For sorting                                                                                                                                                   |
| `type`               | Yes      | `task`                                   | Always `task` — ideas/bugs go to `docs/issues/` via `/create-issue`                                                                                           |
| `suitability`        | No       | `auto_agent_ready`, `human_required`, `exploration`, `unknown` | Task suitability for auto-agent dispatch. Set via Step 6 suggestion. Defaults to `unknown`. |
| `depends_on`         | No       | List of task IDs                         | Tasks that must complete first                                                                                                                                |
| `related`            | No       | List of task IDs                         | Sibling/related tasks (not blocking)                                                                                                                          |
| `branch`             | No       | Branch name string                       | Existing branch to work from (for follow-up tasks); used by `/work-task`                                                                                      |
| `pr`                 | No       | URL string                               | Link to PR when done                                                                                                                                          |
| `auto_agent_task_id` | No       | UUID string                              | Set by `/dispatch-task` script; links this file to the DB row in the auto-agent system. When set, `/work-task` will warn that the task is already dispatched. |
| `manual_test`        | No       | String or list of strings                | Path(s) into `manual-test/<service-area>/<id>` — the tester uses this to find the manual test procedure for this task. Leave blank if no existing procedure matches; the tester will design ad-hoc probes or write a new E2E test. |
| `skip_tester`        | No       | Boolean                                  | Set `true` to explicitly skip the tester (for PRs the tester cannot verify on a running stack — e.g., pure prompt/skill/doc changes). Set `false` to force tester routing even when the diff heuristic would skip. Leave unset to let the supervisor decide: if the task has `manual_test:` or a concrete Verification section, the tester runs; otherwise the supervisor applies a diff heuristic (skips tester if all paths are non-runtime — `.claude/**`, `prompts/**`, `docs/**`). |

**`skip_tester` reference** — you usually don't need to set this. The supervisor's default logic is: if you wrote explicit tester instructions (`manual_test:` or a real Verification section), the tester runs. If you didn't, and the diff is only skills/prompts/docs, the tester is skipped. Set `skip_tester: true` to force-skip (rare). Set `skip_tester: false` to force-run the tester even on a skills-only PR.


## Canonical API Payloads

<!-- CUSTOMIZE: This section should contain known-working curl/API examples that task
  writers copy into verification steps. Without these, every task writer re-derives
  the auth header, the correct field names, and the request shape from scratch — and
  gets it wrong half the time.

  An onboarding agent should scan for:
  - Service interface definitions (HTTP routes, gRPC/protobuf services, CLI command parsers, IPC channels, FFI bridges)
  - Request/response schemas (OpenAPI, Pydantic models, TypeScript interfaces, protobuf messages, JSON-RPC specs)
  - Auth mechanism (tokens, API keys, certificates, session headers, device credentials)
  - Common mistakes (e.g., field named `name` not `title`, UUID vs integer IDs, enum casing)

  Then produce 2-3 example blocks like:

  ### POST /api/widgets — Create a widget
  Source: `src/routes/widgets.ts` (`CreateWidgetSchema`)
  ```bash
  curl -s -X POST http://localhost:3000/api/widgets \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"name": "Test widget", "type": "standard"}'
  ```
  **Required:** `name` (string, 1-200 chars) — NOT `title`
  **Optional:** `type` (default: "standard"), `metadata` (JSON object)

  The goal: task writers paste these and modify, rather than guessing from scratch.
-->
