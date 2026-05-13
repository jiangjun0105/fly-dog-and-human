---
name: work-task
description: Pick up a task from docs/tasks/, set up a worktree, implement it, and create a PR. Handles the full lifecycle from reading the task file to pushing code and opening a PR.
---

# Work Task

Pick up an existing task from `docs/tasks/`, set up an isolated worktree (or reuse one),
execute the task, and update its status.

**Usage**: `/work-task <task-file>`

If no task file is given, list available tasks with `ls docs/tasks/` and ask which one to work on.

## Process

### Step 1: Read the Task

Read and parse the task file (YAML frontmatter + markdown body).

Key frontmatter fields:
- `id`, `title`, `status`, `priority`, `type`
- `branch` — existing branch to work from (if any)
- `depends_on` — tasks that must complete first
- `auto_agent_task_id` — cloud agent dispatch ID (if dispatched)
- `suitability` — `auto_agent_ready`, `human_required`, `exploration`, `unknown`

### Step 2: Check Prerequisites

1. **Dependencies**: Check `depends_on` tasks — are they `status: done`? If not, warn.
2. **Cloud dispatch**: If `auto_agent_task_id` is set:
   - `status: in-progress` → warn: task is already running in the auto-agent system.
     Ask if the user wants to proceed (take over) or check the admin UI.
   - `status: done` → inform: task was completed by the auto-agent. PR may already exist.
     Proceeding lets the user do additional work on top.
3. **Design docs**: If the task references a design doc (e.g., `docs/design/...`), read it
   before starting.

### Step 3: Set Up Worktree

Follow the worktree-mgmt skill (`Skill("worktree-mgmt")`) for procedures:

- If the task has a `branch` field → use that branch (find or create worktree)
- If no branch → create a new worktree from `origin/main`
- Name the worktree based on the task slug

**In auto-agent mode** (headless, no human): skip worktree setup — the workspace is
already cloned and on the correct branch. Do NOT run `git worktree` commands.

### Step 4: Update Task Status

Set `status: in-progress` in the task file.

### Step 5: Choose Implementation Workflow

Based on the task:

- **Has a design doc reference** (`docs/design/...` or `docs/features/...`):
  Read the design doc first. Use it as your implementation guide alongside the
  task's Key Files and Suggested Approach.
- **Bug fix, small change, simple CRUD**: Implement directly following the
  task file.
- **All tasks**: follow Step 6a (Writing Tests) after implementation — not
  optional.

Read the task's **Desired Behavior** section carefully — this is the contract. Each item
should be true after implementation.

### Step 6: Implement

Execute the task inside the worktree. Follow the task's:

- **Key Files** — the files to read and modify
- **Suggested Approach** — the recommended implementation path (treat as a starting point,
  not a complete spec — verify surrounding code is consistent)
- **Acceptance Criteria** — your definition of done

### Step 6a: Writing Tests (MANDATORY)

<!-- CUSTOMIZE: Replace the paths below with your project's actual testing guidance docs.
  An onboarding agent should scan for:
  - Files matching docs/**/test*, docs/**/testing*, TESTING.md, CONTRIBUTING.md
  - README sections about testing conventions
  - Shared test fixtures, helpers, or setup files (conftest.py, testutil/, __tests__/helpers)
  Example output:
    Before writing any tests, read:
    - `docs/testing/anti-patterns.md`
    - `docs/testing/integration-guide.md` -->
Before writing any tests, read your project's testing guides (see paths above).

#### Integration Test Philosophy: Real Internals, Mock Externals

Feature tests MUST use real internal services. Only mock external services.

<!-- CUSTOMIZE: Replace the service table below with your project's actual internal vs
  external service boundaries. The principle: use real versions of services YOU own and
  control; mock services you DON'T own (third-party APIs, cloud vendor endpoints,
  hardware you can't run locally). An onboarding agent should scan for:
  - Internal service configs (docker-compose, local dev scripts, emulators)
  - Third-party API clients and their test/mock configurations
  - Hardware abstraction layers, simulator configs, or device stubs
  Example output (web app):
    | Use Real (NEVER Mock)  | Mock (External Only)          |
    | Your database          | Payment provider (test keys)  |
    | Your API server        | Email service (sandbox)       |
    | Your cache layer       | Cloud storage (local stub)    |
  Example output (embedded / IoT):
    | Use Real (NEVER Mock)  | Mock (External Only)          |
    | Your firmware logic    | Hardware sensors (simulator)  |
    | Your protocol stack    | Cloud telemetry endpoint      |
  Example output (CLI / SDK):
    | Use Real (NEVER Mock)  | Mock (External Only)          |
    | Your parser/core lib   | Remote registry API           |
    | Your file I/O layer    | Third-party auth service      | -->
| Use Real (NEVER Mock) | Mock (External Only)        |
| ---------------------- | --------------------------- |
| *your internal services* | *your external dependencies* |

**Why?** Mocking internal services hides integration bugs. A feature can have
passing tests but be completely broken because the test mocked
`db.session.create` instead of verifying actual data was persisted.

#### What the Reviewer Will Check

The Reviewer agent evaluates your test quality. PRs will be sent back for
revision if:

<!-- CUSTOMIZE: Replace the test markers and anti-pattern references below with your
  project's conventions. An onboarding agent should scan for:
  - Test markers/tags in config (pytest markers, Jest tags, test categories, build labels)
  - Test fixture or helper patterns (shared setup files, factory functions)
  - Any docs about forbidden test patterns (mock overuse, fake implementations)
  Example output (Python):
    - No integration tests for features touching core services (`@pytest.mark.integration`)
    - Internal services are mocked (database, service layer, cache)
    - Fake/dummy repository classes are used (see `no-fake-repositories.md`)
  Example output (embedded C):
    - No integration tests for features touching device drivers (`TEST_GROUP(HardwareIntegration)`)
    - HAL layer is mocked instead of using the simulator
  Example output (CLI tool):
    - No integration tests for commands that read/write files
    - Core parser is mocked instead of exercised end-to-end -->
- No integration tests for features touching core services
- Internal services are mocked instead of tested for real
- Assertions only check transport success (`status_code == 200`) without
  verifying business outcomes or durable side effects
- Tests match anti-patterns: encoding bugs as expected behavior, symmetric
  bugs in code and tests, mocks that erase the calling contract,
  change-detector tests
- No unit tests for standalone helper/utility functions that contain pure logic

#### Test Scope

- Write integration tests for the main flow + edge cases from Acceptance Criteria
- For standalone helper/utility functions with pure logic (no DB/API dependency),
  write unit tests (no marker needed). These are fast, require no services, and
  prevent review round-trips.
- Run ONLY the tests related to your changes — never run the full suite
- If a bug fix, write a regression test that reproduces the original bug first
- Assert semantic outcomes (DB rows, state transitions, events), not just HTTP status

### Step 6b: Complexity Check

Before committing, verify you haven't exceeded the task's scope. These checks
prevent you from spiraling into patch-on-patch when the real problem is a
missing design decision.

- **Unplanned files**: If you're modifying more than 2 files not mentioned in
  Key Files, the task may be under-scoped. Call `request_human_input` explaining
  what extra files need changes and why.
- **Stacking workarounds**: If you've added a second workaround for the same
  root cause (e.g., a guard that catches an error another guard should have
  prevented, or a special case that duplicates logic from another special case),
  the underlying design may need rethinking. Call `request_human_input`
  describing the pattern: "I'm adding workaround #N for [root cause]. This
  suggests [X] may need a design change. Should I continue or escalate?"
- **Diff size**: If your changes exceed ~800 lines (for auto-agent tasks) or
  ~1300 lines (for interactive tasks), commit what you have, create the PR as
  a partial implementation, and note what remains in the PR description.

The goal is to fail fast on scope creep rather than deliver a fragile solution.

### Step 7: Pre-commit + Commit

Use `Skill("pre-commit")` before committing:

1. Stage all changes: `git add .`
2. Run pre-commit: `pre-commit run --all-files --show-diff-on-failure --color always`
3. Fix any failures, re-stage, re-run until clean
4. Commit with a conventional-format message derived from the task title

### Step 8: Create PR

**Important:** The `<task-id>` in the PR body must be the exact `id:` value from the
task file's YAML frontmatter. Do not paraphrase, abbreviate, or reconstruct the ID
from memory — copy it verbatim.

Push and create a PR:

```bash
git push -u origin HEAD
gh pr create --title "<conventional commit title from task>" --body "$(cat <<'PREOF'
## Summary
<1-3 bullet points from the task>

## Task
`<task-id from frontmatter>` — <task title from frontmatter>

## Test plan
<checklist from acceptance criteria>
PREOF
)"
```

Update the task file:
- Set `pr:` field to the PR URL
- Set `status: done`
- Check off acceptance criteria items

### Step 9: Present Results

Show the user:
- PR URL
- What was implemented
- Any acceptance criteria that couldn't be verified (note gaps)
- Remind to run cleanup after merge

## In Auto-Agent Mode

When running as a cloud agent (headless, no human):

1. The workspace is already set up — do NOT create worktrees
2. Read `AGENTS.md` at the repo root for project conventions
3. Read the task file at `docs/tasks/<task-id>.md`
4. Follow steps 5-8 above
5. After creating the PR, call `report_result(pr_url="<PR URL>", branch="<branch>")`
6. Do NOT run PR reviews or call `submit_task` — the reviewer handles that

## Tips

- **Read before you write**: Always read the existing code in Key Files before modifying
- **Check the design doc**: If the task references `docs/design/...`, read it first
- **Verify completeness**: If the Suggested Approach has a code diff, treat it as a
  starting point — check hook dependency arrays, callers, related config
- **Don't over-scope**: Only implement what the task asks for. No extra refactoring.
<!-- CUSTOMIZE: Replace the test runner command and example path below with your project's
  conventions. An onboarding agent should scan for:
  - Build/project config for test runner setup (pyproject.toml, package.json, CMakeLists.txt, Cargo.toml, Makefile)
  - Makefile or scripts/ directory for test runner wrappers
  - Whether a toolchain wrapper is used (uv, poetry, npm, cargo, cmake, go test) or bare commands
  Example output (Python + uv):
    `uv run pytest tests/unit/test_parser.py -q --tb=short --timeout=30`
  Example output (Node + Jest):
    `npx jest --testPathPattern='src/parser/__tests__' --bail`
  Example output (Rust + Cargo):
    `cargo test --lib parser::tests -- --nocapture`
  Example output (Go):
    `go test ./internal/parser/... -run TestParseConfig -v -timeout 30s` -->
- **Run tests scoped to your changes**: Do NOT run the full test suite — it consumes too many resources and times out. Run only the test files related to your changes. Let CI run the full suite after you push. If a test command takes more than 2 minutes, kill it and push anyway — CI will catch failures.
- **Beware of Bash command timeouts**: Bash commands have a 2-minute default timeout. Long-running commands (test suites, builds) will be sent to background automatically, and you will NOT see their output inline. Do NOT retry the same command hoping for output — check the background task output file instead. If a command is expected to take more than 1 minute, run it in background explicitly with `run_in_background: true` and read the output file when notified.
- **Avoid test anti-patterns**: Before writing tests, review your project's testing guides (see Step 6a). Key pitfall: when mocking a function that calls your callback, simulate the *real* calling pattern (number of calls, argument sequence), not an idealized one — mocks that erase the calling contract hide integration bugs.
