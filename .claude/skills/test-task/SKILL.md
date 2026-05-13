---
name: test-task
description: Verify that a completed feature actually works by running it end-to-end against real services — not by reviewing or re-running unit tests. Start real services, run E2E scripts, hit real endpoints, check real DB state, open a real browser. Reports pass/fail per criterion with evidence. Fixes easy issues inline; escalates design problems.
---

# Task Test — System-Level Verification

> **This skill is NOT about reviewing or running unit tests.**
> Unit tests are the worker's job. By the time you're here, unit tests already pass.
> Your job is to prove the feature works **in the real system** — real services, real DB,
> real browser, real scripts. If you find yourself running `pytest` on existing test files,
> you are doing the wrong thing.

Verify that a completed implementation **actually fixes the original problem** or **delivers the new feature**
by testing it the way a human developer would: start a real service, hit real endpoints, check real DB state,
open a real browser.

**The problem this solves:** A worker says "done," unit tests are green, but the actual user-visible behavior
is broken. Unit tests only prove that individual functions behave in isolation. System-level verification
proves the whole thing works together — the right data is persisted, the right UI element appears,
the right API response comes back from a live server.

## Absolute Rules

- NEVER run `pytest` on existing test files — worker and CI handle that
<!-- CUSTOMIZE: Replace with your project's CI/test-suite commands that should NOT be run here.
  An onboarding agent should check the Makefile, justfile, package.json scripts, or CI config
  to find the full-suite commands.
  Example: - NEVER run `make test-all`, `npm run test:ci`, or any full test suite -->
- NEVER run the project's full CI or test suite commands
- NEVER count "all tests pass" as verification evidence
- NEVER write mocked tests — if you need a mock, it's not system-level
- NEVER use source inspection as a substitute for running the code

The ONLY permitted pytest usage is within P4 (see Testing Priority Stack below):
running a single new test you wrote yourself, e.g.,
`uv run pytest path/to/new_test.py -k "test_name" --timeout=120`.

## Phase 0: Discover Manual Tests

Before planning probes, discover whether pre-built manual test procedures exist
for this feature. This phase determines your testing priority level (P1-P4).

### Step 0.1: Read the Task File

```bash
ls docs/tasks/
cat docs/tasks/*.md
```

Extract:
- **`manual_test:` frontmatter** — if present, this is your P1 test procedure
- **`## Verification` section** — your primary testing procedure (if present)
- **Desired Behavior** — each item becomes a probe
- **Acceptance Criteria** — your verification checklist

**If the Verification section contains only `pytest` or `uv run pytest` commands**
(no curl, no browser steps, no DB checks), treat it as insufficient. Design manual
probes from the Desired Behavior and Acceptance Criteria sections instead.

### Step 0.2: Check the Test Case Index

Scan the index below. If a test case matches the service area or feature being
tested, that's your P2 test procedure.

#### Test Case Index

<!-- CUSTOMIZE: Replace this table with your project's actual manual test procedures.
  An onboarding agent should scan `.claude/skills/manual-test/` for existing test
  procedure files and build a table mapping service areas to test procedures.
  Example:
    | `api/auth-flow` | auth | Login, token refresh, logout | After changes to auth middleware |
    | `cli/export-cmd` | cli | Export command with various formats | After changes to export logic |
    | `integration/data-sync` | pipeline | End-to-end data sync with real store | After changes to sync service |
    | `e2e/config-validation` | config | Validates config parsing and error handling | After changes to config schema | -->

| ID | Service Area | What It Verifies | When to Use |
|----|-------------|-----------------|-------------|
| *(populate from `.claude/skills/manual-test/`)* | | | |

### Step 0.3: Determine Priority Level

Based on what you found in steps 0.1 and 0.2, follow the Testing Priority Stack.

## Testing Priority Stack

Follow this order. Stop at the first level that applies.

| Priority | When | What to Do |
|----------|------|------------|
| **P1** | Task file has `manual_test:` frontmatter | Read the referenced test case file: `cat .claude/skills/manual-test/<id>.md`. Follow its steps exactly against the live system. |
| **P2** | Test Case Index (above) has a matching entry | Read the matching test case file: `cat .claude/skills/manual-test/<id>.md`. Follow its steps exactly against the live system. |
| **P3** | No P1 or P2 match | Design ad-hoc manual probes: curl endpoints, open browser pages, inspect DB state. Use the task's Desired Behavior and Acceptance Criteria as your probe spec. |
| **P4** | Backend-only change, no existing test coverage, no feasible manual probe | Write ONE new E2E integration test (real DB, no mocks). Run it with `uv run pytest path/to/new_test.py -k "test_name" --timeout=120`. This is the ONLY scenario where pytest is allowed. |

**NEVER load the manual-test skill via the Skill tool** — read test case files directly with
`cat .claude/skills/manual-test/<id>.md`.

**Division of responsibilities:**

| Role                       | Focus                             | Tools                                    |
| -------------------------- | --------------------------------- | ---------------------------------------- |
| **Tester** (this skill)    | Does the original problem go away? | Real services, E2E scripts, browser      |
| **Reviewer** (`pr-review`) | Is the code correct and clean?    | Diff + code analysis                     |
| **Worker**                 | Build the feature + unit tests    | Task file + design docs                  |

## Quick Start

- **By task file**: "Test the feature in `docs/tasks/2026-03-29-my-feature.md`"
- **By PR**: "Verify PR #625 actually works"
- **By issue**: "Test the fix for #618"

## Core Principle: Think Like a Human Developer

Before writing any test, ask yourself: **"How would I personally verify this is fixed if I had 10 minutes?"**

A human developer testing a bug doesn't grep through mocked test output. They:
1. Set up a test account with the right state
2. Trigger the action (make the API call, submit the form, use the feature)
3. Check the outcome (correct data in the DB, page shows the right UI, API returns the right response)

That's the template. Every criterion gets tested the same way.

**The golden rule: if you can see the outcome in the browser, use the browser first.
If it's only visible in API responses or DB state, hit the live service. Unit tests are not verification.**

## Workflow Overview

```
Phase 0                  Phase 1                  Phase 2                    Phase 3              Phase 4
Discover Manual Tests    Understand the Problem   Find & Plan Probes         Execute & Observe    Triage & Report

Check task file for      Read task/issue           Search for existing E2E    Start real services  Easy fix? fix + rerun
  manual_test: field     Understand what           If exists: use it          Run E2E scripts      Use targeted test to
Check inlined index        broke or what's new     If not: plan live probes   Hit real endpoints     isolate the bug
Determine P1/P2/P3/P4    Think: how would a        For each criterion         Use browser if       Re-run E2E after fix
                           human verify this?      - what to run end-to-end     UI can confirm     Produce report with
                                                   - what evidence proves it                         evidence
```

---

## Phase 0.5: Verify Branch HEAD

**Before any testing, confirm you are testing the correct commit.**

If you are testing a PR, compare your local HEAD against the PR's head commit:

```bash
# Get local HEAD
LOCAL_SHA=$(git rev-parse HEAD)

# Get PR head SHA (replace <number> with the PR number)
PR_SHA=$(gh pr view <number> --json headRefOid -q .headRefOid)

echo "Local:  $LOCAL_SHA"
echo "PR:     $PR_SHA"

if [ "$LOCAL_SHA" != "$PR_SHA" ]; then
  echo "WARNING: Local HEAD does not match PR head!"
  echo "You may be testing stale code. Run: git pull origin <branch>"
fi
```

**Why this matters**: If the workspace was set up before the latest push, you
may be probing code that is several commits behind the PR head. This wastes
time diagnosing "missing" changes that actually exist on a newer commit.

## Phase 1: Understand the Problem

**Goal**: Know the original problem (or new feature) well enough to know when it is truly solved.

### Step 1.1: Read the Task or Issue

The task file (or GitHub issue) is the **sole source of truth** for what needs to be verified.

<!-- CUSTOMIZE: Replace the task file locations with your project's conventions.
  An onboarding agent should check for docs/tasks/, .github/ISSUE_TEMPLATE/, or
  project management tool integrations to find where task specs live.
  Example:
    | Task file    | `docs/tasks/` or `issues/`                                        |
    | PR           | `gh pr view <N>` — match by branch name or PR description         |
    | GitHub issue | `gh issue view <N>` — read the full description                   | -->

| Context         | Where to look                                              |
| --------------- | ---------------------------------------------------------- |
| Task file       | *(your project's task file directory)*                     |
| PR              | `gh pr view <N>` — read the PR description                 |
| GitHub issue    | `gh issue view <N>` — read the full description            |

**Focus on:**

- **What problem did this fix, or what behavior did it add?** — this becomes your top-level verification goal
- **What did "broken" look like?** — this tells you the regression test: put the system in that state, confirm the bad behavior is gone
- **What does "working" look like from the outside?** — the observable evidence you'll collect
- **Desired Behavior / Acceptance Criteria** — each item becomes a probe you'll run

If no task file exists, use the PR description or issue as the spec.

### Step 1.2: Search for Existing E2E Tests and Manual Walkthroughs

**Do this BEFORE reading the diff or planning probes.** Existing test infrastructure is always
the fastest path to verification.

If Phase 0 already identified a P1 or P2 test case, skip this step — you already know
which test to run.

<!-- CUSTOMIZE: Replace with your project's E2E script locations.
  An onboarding agent should search for e2e scripts: find . -name 'e2e-*' -o -name '*e2e*'
  and identify where integration/E2E test scripts live in the repo structure.
  Example:
    ls tests/e2e/scripts/
    ls scripts/integration-test-*.sh -->

```bash
# Check for E2E scripts in the relevant service/module
find . -name 'e2e-*' -o -name '*e2e*' | head -20
ls .claude/skills/manual-test/
```

If an existing E2E test or walkthrough covers the feature — **use it**. Read it, understand
what it verifies, and run it against the branch. Skip Phase 2 (planning probes) entirely.

### Step 1.3: Read the Changed Code (to learn HOW to exercise it)

Only read the diff if no existing E2E test covers the feature, or if you need to understand
what the E2E test should be exercising.

```bash
git diff origin/main...HEAD --name-only   # or: gh pr view <N> --json files
```

- Which endpoints were changed → what URL to hit
- Which DB tables are affected → what rows to inspect after the action
- Which external services are called → what to seed before the action
- Whether the frontend changed → what page to open in the browser

**The code tells you HOW to probe. The task tells you WHAT to prove.**

**Gap analysis:** Cross-reference the changed files against the task's acceptance criteria
and "Key Files" list. If an acceptance criterion implies a file should have been changed
but that file is NOT in the diff, flag it — the most common bugs in PRs are files that
*should* have been updated but weren't (e.g., a validation layer that doesn't know about
a new config format, or a dispatch method that still uses the old API).

### Step 1.4: Ask Clarification Questions (if needed)

Ask before probing if:
- The expected observable outcome is ambiguous (e.g., "data updated" — which table/field exactly?)
- You can't tell from the task/code what "success" looks like at the system level
- The problem description conflicts with the implementation

Use `AskQuestion` in Cursor/Claude Code. In automated contexts, proceed with best judgment and note the ambiguity.

---

## Phase 2: Plan the Probes

**Skip this phase if Phase 0 identified a P1 or P2 test, or if you found an existing E2E test in Step 1.2.** Go straight to Phase 3.

### Build the Probe Plan

For each criterion, define a **system-level probe** — a concrete sequence of actions and observations on a live system.

<!-- CUSTOMIZE: Replace with examples relevant to your project's domain.
  Example probe plans:
    | 1 | API returns filtered results | POST /api/search with test query → verify response fields | JSON response matches expected schema |
    | 2 | UI reflects new state | Open relevant page → trigger action → verify element updated | screenshot |
    | 3 | CLI command produces correct output | Run command with test args → check stdout and exit code | command output matches expected format |
    | 4 | Service integration round-trips | Send event to service → poll/query downstream → verify propagation | downstream record created with correct data |
  An onboarding agent should look at recent task files for typical acceptance criteria. -->

```
| # | Criterion (from task/issue)          | Probe                                                                 | Evidence to collect             |
|---|--------------------------------------|-----------------------------------------------------------------------|---------------------------------|
| 1 | Feature X works end-to-end           | Seed test data → call API → check DB                                 | DB row updated as expected      |
| 2 | API returns correct response         | POST /api/endpoint with test payload → assert response fields        | JSON response matches spec      |
| 3 | UI shows new element                 | Log in → open /page → verify element visible                         | screenshot                      |
| 4 | Edge case handled correctly          | Seed invalid state → trigger action → assert rejected/handled        | Error response or fallback UI   |
```

**Always ask: can I verify this through the browser or a live API?** If yes, that's the probe. DB inspection is corroborating evidence, not the primary proof.

### No Mocks

This skill does not write mocked tests. Every probe uses:

<!-- CUSTOMIZE: Replace with your project's service start commands and external API examples.
  An onboarding agent should check the justfile/Makefile/package.json for dev server commands,
  and .env.example for which external services are used.
  Example: - Real running service with a real Postgres DB (local `make dev` or `docker compose up`) -->
- **Real running service** with a **real database** (local dev server or integration environment)
- **Real external APIs** where possible (test/sandbox modes of third-party services)
- **Real browser** via `agent-browser` when the UI can confirm the behavior

The only exception: genuinely unavailable external services (production-only webhooks, hardware-dependent flows).
When you can't reach the external service, fall back to the deepest real layer you can reach,
and flag the gap explicitly.

### Probe Types

There are three probe types, in order of preference:

**Type E — Existing E2E script or walkthrough**

The best probe is one that already exists. Run the E2E script or follow the manual walkthrough
documented in `.claude/skills/manual-test/` test case files or service `scripts/` directories.

<!-- CUSTOMIZE: Replace with an example E2E script from your project.
  An onboarding agent should find E2E scripts: find . -name 'e2e-*' -o -name '*integration*'
  Example: ./scripts/e2e-checkout-flow.sh --cleanup -->

```bash
# Example: run an existing E2E script
./path/to/e2e-script.sh --cleanup
```

**Type A — Live Service probe**

Drive the system through its real entry points: HTTP endpoints, service-layer functions called
in-process, or direct DB queries. The service is running, the DB is real, no mocking anywhere.

Choose your entry point based on what's most realistic:
- HTTP endpoint exists → hit it with `curl` or an HTTP client
- Logic lives deeper than HTTP (service layer, scheduled job, WebSocket event) → call it
  directly with the real `db` fixture; still no mocks
- Scripts that exercise the feature → run the script

<!-- CUSTOMIZE: Replace with your project's service start command, typical interaction,
  and a representative state query.
  An onboarding agent should check the justfile/Makefile for dev-run commands,
  look at the service entry points for a representative interaction, and check data stores for key tables/collections.
  Example:
    <your-start-command> &
    curl -s -X POST "http://localhost:$PORT/api/resource" | jq .
    psql $DATABASE_URL -c "SELECT * FROM table WHERE ..." -->

```bash
# Example: curl against the running service
# Start your dev server, then hit an endpoint and check DB
curl -s -X POST "http://localhost:$PORT/api/..." | jq .
psql $DATABASE_URL -c "SELECT ... FROM ... WHERE ..."
```

**Type B — Browser probe**

Drive the system through the real UI using `agent-browser`. Use this whenever a human could
open a page and see whether it works — even for purely backend fixes.

```bash
# Read agent-browser SKILL.md first for session and auth patterns
agent-browser open http://localhost:$FRONTEND_PORT/your-page
agent-browser set viewport 1280 720   # ensure consistent viewport (Chrome default is ~800x600)
agent-browser wait --load networkidle
agent-browser snapshot -i          # inspect elements
agent-browser screenshot before.png
agent-browser click @<button-ref>
agent-browser wait --load networkidle
agent-browser screenshot after.png
```

Always ask whether a browser probe can confirm or corroborate a backend fix:
- Data fix → admin dashboard shows correct values
- API fix → detail page shows correct state
- Permission fix → certain buttons appear/disappear for different user roles

Read `.claude/skills/agent-browser/SKILL.md` before running browser probes.

### Deciding which probe to use

Start from the observable outcome and work backward:

1. **Does an existing E2E script or walkthrough cover it?** → Type E (run it)
2. **Can a human see the outcome in the browser?** → Type B (browser) first, Type A as corroboration
3. **Is the outcome only visible in API responses or DB state?** → Type A (live service)
4. **Is it only verifiable with mocks?** → Flag as coverage gap, don't count as verified

---

## Phase 3: Execute and Observe

### Step 3.1: Start the Real Environment

**Use the isolated test environment** to avoid polluting the dev database and
avoid port conflicts with running dev servers.

> **After restarting the test environment** (or re-seeding the database), clear
> browser state before the first login probe. Stale auth tokens from a previous
> session cause "No user found" 401 errors that look like login bugs:
>
> ```bash
> agent-browser eval "localStorage.clear(); sessionStorage.clear();"
> ```
>
> Alternatively, launch Chrome with a fresh profile (`--user-data-dir=/tmp/chrome-$(date +%s)`)
> to guarantee no stale state. See `.claude/skills/manual-test/guides/agent-browser-workarounds.md`
> for details.

<!-- CUSTOMIZE: Replace with your project's test environment setup commands.
  An onboarding agent should check for:
  - Docker Compose files (docker-compose.test.yml, docker-compose.yml)
  - Test environment scripts (scripts/test-env.sh, scripts/start-test.sh)
  - Justfile/Makefile targets for starting services
  - Environment config files (.env.test, .env.example, config/test.yaml, etc.) for port configuration
  Example:
    docker compose -f docker-compose.test.yml up -d
    make start-test-env
    just test-env-up -->

```bash
# Option 1 (preferred): Isolated test environment
# <your-test-env-start-command>

# Option 2: Dev environment (only when explicitly testing against dev)
# <your-dev-server-start-command>
```

<!-- CUSTOMIZE: Replace with your project's service ports.
  An onboarding agent should check docker-compose.yml, environment config files, or the
  test-env script for port assignments.
  Example:
    | Main service  | $SERVICE_PORT | `curl -sf http://localhost:$SERVICE_PORT/health` or `nc -z localhost $SERVICE_PORT` |
    | Database      | $DB_PORT      | `nc -z localhost $DB_PORT`                       |
    | Dependency    | $DEP_PORT     | `nc -z localhost $DEP_PORT`                      | -->

**Test environment ports** — check the service is alive before probing:

| Service     | Port / Var        | Health Check                        |
|-------------|-------------------|-------------------------------------|
| *(fill in)* | *(fill in)*       | *(fill in)*                         |

```bash
# Health checks — verify services are running before probing
curl -sf http://localhost:$PORT/health && echo "service OK" || echo "service DOWN"
```

### Step 3.2: Execute Each Probe

**Maintain a verification timeline as you work.** After each significant action (environment
setup, probe execution, failure, retry, fix), append a one-line log entry:

```
HH:MM:SS  <action> — <what happened, what you observed, outcome>
```

Tag each entry with the criterion it relates to using `(C#)`. Include difficulties and
retries inline — don't filter them out. This timeline goes into the report before the
verification matrix. See the report template in Step 4.4 for the full format.

Run probes one at a time. Capture evidence as you go:

**For E2E scripts:** run the script and save the output
```bash
./path/to/e2e-script.sh --cleanup 2>&1 | tee e2e-output.txt
```

**For API probes:** save the full request + response
```bash
curl -v -X POST ... 2>&1 | tee probe-1-output.txt
```

**For DB probes:** capture before and after state
```bash
psql $DATABASE_URL -c "SELECT ..." > before.txt
# ... action ...
psql $DATABASE_URL -c "SELECT ..." > after.txt
diff before.txt after.txt
```

**For browser probes:** take screenshots at each key state
```bash
agent-browser screenshot output/criterion-1-before.png
# ... action ...
agent-browser screenshot output/criterion-1-after.png
```

**Screenshot requirement:** Any criterion that involves UI, a web page, or visual output
**MUST** have a screenshot as evidence. Upload it and embed the image URL directly in the
verification matrix and report. "screenshot attached" or "badge visible" without an actual
image link is not acceptable — the reviewer cannot verify what they cannot see.

<!-- CUSTOMIZE: Replace with your project's screenshot upload method.
  An onboarding agent should check for:
  - scripts/upload-pr-screenshot.sh or similar helpers
  - CI artifacts upload configuration
  - Or fall back to `gh release upload` with per-PR tags
  Example:
    scripts/upload-pr-screenshot.sh 123 output/criterion-1.png "Description"
  If no helper exists, use gh CLI directly:
    gh release create pr-123-screenshots --title "PR #123 Screenshots" --notes ""
    gh release upload pr-123-screenshots output/criterion-*.png -->

Upload screenshots using a per-PR release tag (or your project's screenshot upload helper):

```bash
PR_NUM=123

# Create a per-PR release tag and upload screenshots
gh release create "pr-${PR_NUM}-screenshots" --title "PR #${PR_NUM} Screenshots" --notes "" 2>/dev/null || true
gh release upload "pr-${PR_NUM}-screenshots" output/criterion-*.png

# Reference in markdown:
# ![description](https://github.com/OWNER/REPO/releases/download/pr-<N>-screenshots/file.png)
```

Always include a fallback link to the release page in your report:

```markdown
> View all screenshots: [PR #<N> Screenshots](https://github.com/OWNER/REPO/releases/tag/pr-<N>-screenshots)
```

**Do NOT** use a shared `screenshots` release tag — it causes asset name collisions
across PRs and makes cleanup impossible. Always use per-PR tags (`pr-<N>-screenshots`).

### Step 3.3: Build the Verification Matrix

```
| # | Criterion                          | Probe                              | Result   | Evidence                                        |
|---|------------------------------------|------------------------------------|----------|-------------------------------------------------|
| 1 | Feature works end-to-end           | Type A — curl + DB check           | ✅ PASS  | DB row updated correctly; API returns 200       |
| 2 | E2E script passes                  | Type E — e2e script                | ✅ PASS  | script output: all steps completed              |
| 3 | UI shows correct state             | Type B — browser screenshot        | ✅ PASS  | ![element visible](https://github.com/.../releases/download/pr-N-screenshots/criterion-3.png) |
| 4 | Edge case handled                  | Type A — curl, real DB             | ✅ PASS  | Request rejected with correct error             |
| 5 | External service integration       | Not testable (no test account)     | ⚠️ GAP  | Covered by Type A proxy; gap noted              |
```

---

## Phase 4: Triage and Report

### Step 4.1: Triage Failures

| Situation | Action |
|-----------|--------|
| **Probe returns wrong result** — behavior doesn't match expected | Write a targeted test to isolate the bug (see 4.2), fix it, re-run E2E |
| **Environment issue** — service won't start, DB not seeded | Fix the environment, re-run |
| **Design gap** — the fix doesn't reach far enough (e.g., only fixes one code path) | **Stop.** Report with evidence and escalate |
| **Genuinely untestable** — requires prod credentials, live hardware, 3rd-party webhook | Flag as ⚠️ GAP with explicit explanation; don't mark as PASS |
| **Ambiguous outcome** — can't tell if the result is correct | Note it; escalate for clarification |

### Step 4.2: Write Targeted Tests to Isolate Failures

**This is the only time you write tests in this skill** — when an E2E
probe has already failed and you need a faster feedback loop to debug and fix the problem.

E2E tests are slow (minutes to tens of minutes). When one fails, writing a focused test that
reproduces the specific broken behavior lets you iterate quickly:

1. **Identify the failure** — which criterion failed in the E2E?
2. **Write a targeted test** — a unit or integration test that exercises just the broken path
3. **Fix the implementation** — use the fast test to iterate until it passes
4. **Re-run the E2E** — confirm the fix works in the full system

```python
# Example: E2E test failed because a validation function rejected valid input.
# Write a focused test to isolate and fix the validation logic:
async def test_validator_accepts_known_input(self) -> None:
    context = create_test_context()
    result = await validate_input(context, name="Valid Name")
    assert "Error" not in result
```

The targeted test stays in the codebase as a regression guard. But it is a **byproduct** of
E2E failure triage, not the primary verification method.

### Step 4.3: Fix Easy Issues

When a probe fails for a small, obvious reason:

1. Write a targeted test if the fix isn't trivial (optional)
2. Edit the implementation
3. Re-run the targeted test (fast feedback)
4. Re-run the E2E probe (confirm system-level fix)
5. Note the fix in the report

Keep fixes minimal — fix the specific broken behavior, don't refactor.

### Step 4.4: Produce the Verification Report

Save to `docs/test-reports/<task-slug>-verification.md`:

````markdown
# Verification Report: <task title>

**Task / Issue**: `<path or #number>`
**PR**: #<number>
**Branch**: `<branch>`
**Tested at**: <commit SHA>
**Date**: YYYY-MM-DD

## Summary

| Metric | Value |
|--------|-------|
| Criteria | X |
| ✅ Verified (system-level probe passed) | Y |
| ⚠️ Gap (probe not runnable — coverage gap) | G |
| ❌ Failed | Z |
| Fixed inline | W |

## Verdict: ✅ VERIFIED / ⚠️ VERIFIED WITH GAPS / ❌ NOT VERIFIED

> - **✅ VERIFIED** — every criterion was exercised by a system-level probe (real service/DB/browser)
>   and passed. The original problem is gone.
> - **⚠️ VERIFIED WITH GAPS** — criteria passed but one or more required an environment or
>   external service that wasn't available (e.g., live third-party API). The deepest available
>   proxy was used; gaps are documented.
> - **❌ NOT VERIFIED** — any criterion was not exercised at the system level, or a probe failed.

## Verification Timeline

Chronological log of the tester's process. Each line = one significant action.
Format: `HH:MM:SS  <action> — <observation, difficulty, outcome>`. Tag with `(C#)` for criterion.

```text
07:28:30  Setup — started test environment, all services healthy in 12s
07:29:15  Probe #1 (C1) — POST /api/endpoint → 200. DB row updated correctly ✅
07:31:40  Probe #2 (C2) — ran e2e script → failed step 3, 500 on /api/create. Missing validation ❌
07:35:10  Fix (C2) — patched service.py:123 to add validation. Restarted service
07:36:20  Retry (C2) — re-ran e2e script → all steps completed ✅
07:41:00  Probe #3 (C3) — opened /admin/page in browser. Frontend stale → restarted dev server → element visible ✅
07:43:30  Probe #4 (C4) — curl with invalid state → request rejected as expected ✅
07:44:00  Cleanup — deleted test rows, removed temp files
```

Include everything: setup, probes, failures, retries, fixes, cleanup.
Difficulties and blockers go inline — don't omit them.

## Verification Matrix

| # | Criterion | Probe | Result | Evidence |
|---|-----------|-------|--------|----------|
| 1 | ... | Type A — curl + DB check | ✅ PASS | DB field: expected_value confirmed |
| 2 | ... | Type B — browser | ✅ PASS | ![element](https://github.com/.../releases/download/pr-N-screenshots/criterion-2.png) |

**Screenshot rule:** Every criterion verified via browser or involving UI/visual output
**MUST** have an uploaded screenshot with the image URL embedded in the Evidence column
using `![description](url)`. Text-only descriptions like "screenshot attached" are not
acceptable — the reviewer cannot verify what they cannot see.

## Failures and Escalations

### Criterion #N: <description>

**Status**: ❌ FAIL
**Probe**: <what was run>
**Evidence**: <output, error, screenshot>
**Root cause**: <analysis>
**Recommendation**: <what needs to change>

## Inline Fixes Applied

| File | Change | Criterion |
|------|--------|-----------|
| `path/to/file.py:151` | Fixed missing parameter in handler | AC #1 |

## Coverage Gaps

| Criterion | Why not fully testable | Deepest probe used | Follow-up needed? |
|-----------|------------------------|--------------------|-------------------|
| External service integration | No test account available | Type A — real DB proxy | Low — proxy is high-confidence |
````

---

## Phase 5: Clean Up Test Data

After the verification report is produced, clean up any test data you
created **during your probes** — test rows in the database, temporary
files you generated, SSE log files, etc.

**CRITICAL: Do NOT delete your current workspace directory.** The
workspace (your `cwd`) may be managed by an orchestration system.
Deleting it could crash downstream processes. Only clean up data you
explicitly created during testing.

<!-- CUSTOMIZE: Replace with your project's DB cleanup commands and workspace paths.
  An onboarding agent should check docker-compose.yml for the DB container name and
  database name, and check if there's an orchestration system managing workspaces.
  Example:
    | Test rows in DB | `docker exec my-postgres psql -U postgres -d mydb -c "DELETE FROM ..."` |
    | Temp files | `rm -f /tmp/test-*.txt` | -->

| Resource | Cleanup command |
|----------|----------------|
| Test rows in DB | `psql $DATABASE_URL -c "DELETE FROM ... WHERE id IN ('...');"` |
| Temporary test files | `rm -f /tmp/test-*.txt` |
| Test output artifacts | Keep in `output/` — may be collected by orchestration systems |

**What NOT to clean up:**
- Your current workspace directory (`cwd`)
- The verification report (`docs/test-reports/`) — this is the deliverable
- Existing (non-test) tasks, PRs, or branches
- Git worktrees

---

## Isolated Test Environment

<!-- CUSTOMIZE: Replace this entire section with your project's test environment setup.
  An onboarding agent should discover:
  - Test environment scripts (find . -name 'test-env*' -o -name 'docker-compose.test*')
  - Service ports from docker-compose.yml, environment config files, or build scripts
  - Health check methods from the codebase (HTTP endpoints, TCP checks, CLI status commands)
  Example:
    **Start:** `docker compose -f docker-compose.test.yml up -d` or `make test-env-up`
    **Status:** `docker compose ps` or `<your-status-command>`
    **Ports:** service=$SERVICE_PORT, db=$DB_PORT
    **Health:** `curl -sf http://localhost:$SERVICE_PORT/health` or `nc -z localhost $SERVICE_PORT` -->

**CRITICAL: Always use an isolated test environment. Never test against shared dev servers.**

Before running any probes, start the isolated test stack:

```bash
# Start the test environment (replace with your project's command)
# <your-test-env-start-command>
```

Check that services are healthy before probing:

```bash
# Health checks (replace with your project's endpoints)
# curl -sf http://localhost:$PORT/health
```

**All probes must target test ports, NOT dev ports.**

**After testing:** Leave the test environment running unless resources are constrained:

```bash
# Tear down (replace with your project's command)
# <your-test-env-stop-command>
```

## Workspace Environment

**`agent-browser` is pre-installed** at `/usr/bin/agent-browser`. Before using it, load the skill for the full command reference:

```
Skill("agent-browser")
```

**`google-chrome` is pre-installed** at `/usr/bin/google-chrome`. agent-browser will use it automatically.

**Always set the viewport after connecting.** When Chrome is launched manually (e.g., `--headless=new` in containers) and agent-browser connects via `--cdp`, the default viewport is ~800x600 instead of 1280x720. Run `agent-browser set viewport 1280 720` after your first `open` command to ensure screenshots match desktop layout.

**Frontend deps may need installing.** If the task requires running a frontend dev server for browser verification, run `pnpm install` in the relevant app directory first. This is expected for tester agents.

### Operational Guides

<!-- CUSTOMIZE: Replace with your project's operational guides.
  An onboarding agent should check .claude/skills/manual-test/guides/ for existing guides,
  and identify common testing gotchas from the project's documentation.
  Example:
    cat .claude/skills/manual-test/guides/auth-and-test-users.md
    cat docs/testing/browser-workarounds.md -->

When you hit problems during testing, check for operational guides in
`.claude/skills/manual-test/guides/` or your project's documentation directory.

Common gotchas to watch for: authentication methods (form-encoded vs JSON), React form input handling, stale browser sessions, missing dependencies, and container-specific Chrome flags.

## Verification Timeline

As you work, maintain a chronological log of every significant action. After each
step (environment setup, probe, failure, retry, fix), append a one-line entry:

```
HH:MM:SS  <action> — <observation, difficulty, outcome>
```

Tag entries with `(C#)` for the criterion they relate to. Include difficulties and
retries inline. This timeline goes into the report before the verification matrix.
It reveals your process, not just your results.

## Evidence Collection

Save all screenshots and evidence to the `output/` directory:

- Screenshots: `output/criterion-N-description.png`
- API responses: `output/probe-N-response.json`
- Verification report: `output/verification-report.md`

The `output/` directory should be made available for human review (e.g., collected by an orchestration system or attached to the PR).

**NEVER commit screenshots or binary files to the git repo.** Do not `git add` anything in `output/` or `docs/screenshots/`. Evidence stays local in `output/` only.

**Screenshot requirement:** Any criterion involving UI or visual output **MUST** have a
screenshot. Upload it via the per-PR helper script (see Step 3.2) and embed the image URL in the
verification report using `![description](url)`. Text-only evidence like "badge visible"
is not acceptable for UI criteria — the reviewer needs to see the actual screenshot.

## Post Evidence to the PR (REQUIRED)

This step is **mandatory** — do NOT skip it. After building the verification report,
you MUST upload screenshots and post the report as a PR comment before reporting results.

### Step 1: Upload screenshots

Use the per-PR helper script (same one referenced in Step 3.2):

```bash
PR_NUM=$(gh pr list --head "$(git rev-parse --abbrev-ref HEAD)" --json number -q '.[0].number')

# Upload all screenshots at once using per-PR release tag
gh release create "pr-${PR_NUM}-screenshots" --title "PR #${PR_NUM} Screenshots" --notes "" 2>/dev/null || true
gh release upload "pr-${PR_NUM}-screenshots" output/criterion-*.png
```

This creates a per-PR release tag (`pr-<N>-screenshots`) and uploads assets.
Embed `![description](url)` markdown into your verification report.

**Do NOT** use a shared `screenshots` release tag — it causes asset name collisions
across PRs. Always use per-PR tags (`pr-<N>-screenshots`).

**Do NOT use `raw.githubusercontent.com` URLs for images** — branch names with slashes break these URLs. Always use release asset URLs.

### Step 2: Post the verification report as a PR comment

```bash
gh pr comment "$PR_NUM" --body "$(cat output/verification-report.md)"
```

Include a fallback link to the release page so reviewers can view all screenshots:

```markdown
> View all screenshots: [PR #<N> Screenshots](https://github.com/OWNER/REPO/releases/tag/pr-<N>-screenshots)
```

## Verdict

<!-- CUSTOMIZE: Replace the reporting mechanism with your project's method.
  If using auto-agent or an orchestration system, reference the correct MCP tool or
  reporting API. If manual, just posting the PR comment may be sufficient.
  Example:
    After testing, call `mcp__my_system__report_result(pr_url="...", branch="...")` -->

**GATE: Do NOT report results until screenshots are uploaded and the verification report is posted as a PR comment.** The PR comment is how reviewers and humans see your evidence — without it, your verification is invisible.

After testing all criteria, report the verdict:

- **VERIFIED** — all criteria passed with system-level evidence
- **VERIFIED WITH GAPS** — criteria passed but some couldn't be fully tested (document gaps)
- **NOT VERIFIED** — one or more criteria failed (include evidence of failures)

If you find easy issues (obvious one-line bugs), fix them, re-run the probe, and note the fix. For design-level problems, do NOT fix — report and escalate.

## CRITICAL: Do NOT delete your workspace

Your current working directory may be managed by an orchestration system. NEVER run `rm -rf` on it or delete git worktrees. Only clean up test data you explicitly created (temp files, test DB rows). Deleting the workspace could crash downstream processes.

---

## Environment Reference

### Starting services locally

<!-- CUSTOMIZE: Replace with your project's service start commands.
  An onboarding agent should check the justfile, Makefile, docker-compose.yml,
  and package.json for available start/status commands.
  Example:
    docker compose up -d
    docker compose ps
    make start-all
    make start-api  # skip frontend for API-only probes -->

Start the test environment using your project's commands:

```bash
# All services
# <your-start-all-command>

# API-only (faster for API-only probes)
# <your-start-api-command>

# Check what's running
# <your-status-command>
```

### Running Type A probes (live service)

```bash
# Hit the running service directly
curl -s -X POST "http://localhost:$PORT/api/..." | jq .
psql $DATABASE_URL -c "SELECT ..."
```

### Running Type B probes (browser)

Read `.claude/skills/agent-browser/SKILL.md` first for:
- Session management and authentication patterns
- Snapshot / click / wait / screenshot commands
- Headed vs headless mode

```bash
# Open with visible browser for debugging
agent-browser --headed open http://localhost:5173
```

### Browser Setup in Containers

<!-- CUSTOMIZE: Replace with your project's browser setup process.
  An onboarding agent should check for:
  - Browser setup scripts (find . -name 'browser-setup*')
  - Auth token injection methods in test helpers
  - Agent-browser configuration in .claude/skills/
  Example:
    source scripts/browser-setup.sh up --route /admin
    source scripts/browser-setup.sh down -->

For automated Chrome launch and auth token injection, use your project's browser
setup script (if available). Otherwise, launch Chrome manually:

```bash
# Manual Chrome setup (fallback)
agent-browser open http://localhost:$FRONTEND_PORT
agent-browser set viewport 1280 720
```

For common browser testing gotchas, check `.claude/skills/manual-test/guides/`
for agent-browser workaround guides.

---

<!-- CUSTOMIZE: If your project uses a test slot or workspace system, document the
  filesystem layout here. An onboarding agent should check test-env scripts for
  workspace directory patterns.
  Example:
    ## Test Workspace Layout
    ~/test-data/slot-0/
      .pids/           # PID files for running services
      .browser-env     # Browser session env vars
      logs/            # Service log files
  If your project doesn't use test slots, remove this section entirely. -->

## Tips

- **E2E first, always.** Before writing anything, check if an existing E2E script or manual
  walkthrough already covers the feature. Running an E2E script takes minutes but
  proves more than 100 unit tests ever could.
- **Unit tests are for debugging, not verifying.** Only write a unit/integration test when
  an E2E probe has failed and you need a faster feedback loop to isolate the bug. The targeted
  test is a debugging tool, not the verification itself.
- **"All unit tests pass" is not a finding.** If the worker already said tests pass, re-running
  them adds zero value. Your job is to prove the feature works at the system level.
- **Start from the original problem, not the code.** Ask: "What did the user see before this fix?
  What should they see now?" That question drives the probe.
- **The browser is your friend even for backend fixes.** If an admin page, a session detail,
  or a status display can show you the right outcome — use it. It's the most honest
  form of verification.
- **Real DB, real service, real API.** If you're thinking about mocking something, stop and
  ask if there's a way to use the real thing. Usually there is.
- **Evidence matters.** A screenshot, a DB diff, a JSON response, an E2E script output — something
  a human can look at and say "yes, that's right." Assertions in test output alone aren't enough.
- **Gaps are honest.** If a criterion genuinely can't be probed end-to-end (production-only
  webhook, hardware-dependent flow), say so explicitly. Use the deepest available proxy and document the gap.
- **One criterion = one probe.** Keep them independent so a failure pinpoints exactly what broke.
- **Fix what you find.** If a probe fails for an obvious small reason, fix it and re-run.
  Don't just report and move on.
