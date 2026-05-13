---
name: dispatch-task
description: Dispatch a task file to the auto-agent system for autonomous execution. Use when the user says "dispatch", "send to auto-agent", "run this task", or wants to send a docs/tasks/ file to the auto-agent API.
---

# Dispatch Task

Send a task markdown file from `docs/tasks/` to the auto-agent system for autonomous execution.

**Usage**: `/dispatch-task <task-file-or-id> [options]`

Examples:
- `/dispatch-task ci-fix-auto-agent-e2e-trigger`
- `/dispatch-task docs/tasks/2026-04-07-ci-fix-auto-agent-e2e-trigger.md --env production`
- `/dispatch-task ci-fix --watch`
- `/dispatch-task ci-fix --env development --token $MY_TOKEN`

## Process

### Step 1: Resolve the Task File

If the argument is not a full path, search `docs/tasks/` for a matching file:
```bash
ls docs/tasks/*<argument>*
```

Read the task file and confirm with the user:
- Task title, id, status, suitability
- Whether `auto_agent_task_id` is already set (previous dispatch)

### Step 2: Choose Environment

Ask the user which environment if not specified:
- `local` — `http://localhost:8103` (local auto-agent server)
- `development` — requires `AUTO_AGENT_API_URL` env var
- `production` — requires `AUTO_AGENT_API_URL` env var

Default: `local`

### Step 2.5: Pre-Dispatch Checklist

Before dispatching, verify:

- **Referenced files exist on the base branch.** If the task references design docs,
  config files, or other files that only exist on a feature branch (not `main`), either:
  1. Merge the feature branch to `main` first, or
  2. Use `--base-branch <feature-branch>` so the worker starts from that branch.
  The worker checks out from the base branch (`main` by default) and cannot see files
  that aren't there. A common mistake is using `--target-branch` thinking it changes
  the starting point — it only sets where the PR merges into.
- **Task file is complete.** All acceptance criteria, design references, and scope items
  should be finalized before dispatch.

### Step 3: Credentials

<!-- CUSTOMIZE: Replace credential env var names with your project's API credentials.
  An onboarding agent should check .env.local, .env, and the dispatch script source
  to find the expected variable names.
  Example:
    - MYAPP_API_EMAIL + MYAPP_API_PASSWORD
    - API_KEY (single token) -->
The dispatch script needs either a `--token` or `API_EMAIL` + `API_PASSWORD` env vars.

**Option A — Pre-existing JWT token (bypasses API login):**
```bash
uv run scripts/dispatch-task.py <task-file> --env <env> --token <JWT>
```
When `--token` is provided, API credential env vars are not required
and no login request is made.

**Option B — Credential-based login (default):**
Check `.env.local` first, then `.env`:
```bash
grep -E '^API_(EMAIL|PASSWORD)' .env.local 2>/dev/null || grep -E '^API_(EMAIL|PASSWORD)' .env 2>/dev/null
```

If found, the script picks them up automatically (no need to pass as env vars).
If not found, ask the user for credentials and pass them as env vars on the command line.

**NEVER store credentials in skill files, task files, or commit them to git.**

### Step 4: Dispatch

Use `uv run` to execute the script — it resolves the project venv automatically:

```bash
uv run scripts/dispatch-task.py <task-file> --env <env> [--watch] [--force] [--token <JWT>]
```

If credentials are not in `.env.local`, prefix with env vars:
```bash
API_EMAIL=<email> API_PASSWORD=<password> uv run scripts/dispatch-task.py ...
```

**Important flags:**
- `--token <JWT>` — use a pre-existing JWT token directly, bypassing API login.
  Useful when the auth service is unavailable or credentials don't match the local DB.
- `--watch` — poll every 30s and update the task file on status changes. Always recommended.
- `--force` — bypass duplicate dispatch check. **Always use when `auto_agent_task_id` is already set**, because the interactive confirmation prompt does not work in agent mode.
- `--base-branch <branch>` — branch the worker clones and starts from (default: main).
  Use this when design docs or prerequisite code only exist on a feature branch, not main.
- `--target-branch <branch>` — branch the PR will merge into (default: auto-generated).
  This does NOT affect the worker's starting point — use `--base-branch` for that.

**Run in background** so the conversation isn't blocked while watching:
```bash
# run_in_background: true
uv run scripts/dispatch-task.py <task-file> --env <env> --watch --force
```

### Step 5: Show Results

After dispatch, always show the user:
- **Task ID** from the script output
- **Admin UI link**: `<auto-agent-url>/admin/auto-agent/<task-id>`
- **API link**: `<auto-agent-url>/api/tasks/<task-id>`

<!-- CUSTOMIZE: Replace these URLs with your project's auto-agent admin UI URLs.
  An onboarding agent should check deployment configuration files, environment
  variables, or infrastructure docs to find the correct URLs.
  Example:
    - local: http://localhost:8888/admin/auto-agent/<task-id>
    - staging: https://staging.example.com/admin/auto-agent/<task-id>
    - production: https://app.example.com/admin/auto-agent/<task-id> -->
The admin UI URLs by environment:
- local: `http://localhost:8888/admin/auto-agent/<task-id>`
- development: `https://<your-dev-domain>/admin/auto-agent/<task-id>`
- production: `https://<your-prod-domain>/admin/auto-agent/<task-id>`

### Step 6: Monitor

If `--watch` is running in the background, you'll be notified when it completes.
Read the output file to see the final status.

If not watching, remind the user they can sync status later:
```bash
uv run scripts/sync-task-status.py
```

## Starting Agent Override

By default, tasks start with the worker. The dispatch script supports starting with
a different agent via `config.start_with` in the task frontmatter:

```yaml
config:
  start_with: tester    # start with the tester agent (e.g., E2E verification tasks)
```

### Auto-detection for review tasks

If the task file has a non-empty `pr:` field in its frontmatter and no explicit
`start_with`, the script automatically sets `start_with: reviewer` and routes
the task to the reviewer agent first (the PR already exists, so the worker
doesn't need to code).

```yaml
<!-- CUSTOMIZE: Replace with your project's GitHub repository URL.
  An onboarding agent should run `git remote -v` to discover the correct URL.
  Example: pr: "https://github.com/your-org/your-repo/pull/123" -->
pr: "https://github.com/<your-org>/<your-repo>/pull/123"
```

To override this behavior, add an explicit `config:` block:
```yaml
config:
  start_with: worker  # force worker-first even with a pr: set
```

## Sending Messages to Running Tasks

You can send messages to a running (or paused) task's worker/agent via the REST API.
This is useful for correcting course, giving instructions, or answering agent questions.

### Authentication

<!-- CUSTOMIZE: Replace the auth endpoint and credential env var names with your
  project's authentication service. An onboarding agent should check the dispatch
  script source, .env files, and API docs for the correct login endpoint and
  credential variable names.
  Example:
    - Auth endpoint: http://localhost:8000/api/auth/login
    - Credential vars: MYAPP_API_EMAIL, MYAPP_API_PASSWORD -->
Authenticate via your project's auth/login endpoint to get a JWT token. The auto-agent
API uses the same tokens as the main API — do NOT try to generate JWTs manually with `JWT_SECRET`.

```bash
# Get credentials (check .env.local first, then .env)
API_EMAIL=$(grep '^API_EMAIL=' .env.local 2>/dev/null || grep '^API_EMAIL=' .env | head -1 | cut -d= -f2)
API_PASSWORD=$(grep '^API_PASSWORD=' .env.local 2>/dev/null || grep '^API_PASSWORD=' .env | head -1 | cut -d= -f2)

# Login to auth service (form-encoded, not JSON)
TOKEN=$(curl -s -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=${API_EMAIL}&password=${API_PASSWORD}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

For non-local environments, replace `http://localhost:8000` with the appropriate API URL.

### Send Message Endpoint

```bash
curl -s -X POST "http://localhost:8103/api/tasks/<task-id>/message" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Your instruction here", "target_agent": "Coding Worker"}'
```

**Parameters:**
- `message` (string, required): The instruction text (1–100,000 chars)
- `target_agent` (string, optional): Agent display name. Must match exactly:
  `"Coding Worker"`, `"Coding Reviewer"`, `"Coding Tester"`, `"Coding Crew Supervisor"`

**Status transitions on message send:**
| Current status | Transitions to |
|---|---|
| `paused` | `human_interacting` |
| `human_interacting` | stays `human_interacting` |
| `waiting_human` | `agent_reviewing` |
| `completed` / `failed` / `timed_out` | `worker_running` (resumes) |

### Other Lifecycle Endpoints

```bash
# Pause
curl -X POST "http://localhost:8103/api/tasks/<task-id>/pause" -H "Authorization: Bearer <token>"

# Resume
curl -X POST "http://localhost:8103/api/tasks/<task-id>/resume" -H "Authorization: Bearer <token>"

# Submit feedback (during human_reviewing)
curl -X POST "http://localhost:8103/api/tasks/<task-id>/submit" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"action": "request_changes", "feedback": "Please fix X"}'
```

### Admin UI Links (by environment)

- local: `http://localhost:8888/admin/auto-agent/<task-id>`
- development: `https://<your-dev-domain>/admin/auto-agent/<task-id>`
- production: `https://<your-prod-domain>/admin/auto-agent/<task-id>`

## Tips

- Check suitability before dispatching: `auto_agent_ready` tasks are best suited
- `human_required` tasks may fail or produce incomplete results — warn the user
- For re-dispatches, always use `--force` to avoid the interactive prompt
- The watch loop exits on `human_reviewing`, `completed`, `failed`, or `timed_out`
