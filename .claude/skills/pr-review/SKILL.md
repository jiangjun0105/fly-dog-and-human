---
name: pr-review
description: Review any pull request (features, bug fixes, refactors, docs, CI config) by analyzing the diff, CI status, and source code. Small/focused PRs use a fast flat review; large multi-concern PRs group changes and optionally use parallel subagents. Use when asked to review a PR, examine a pull request, or check PR quality.
---

# PR Review

A structured workflow for reviewing any pull request. Unlike the SDD review (Phase 6), this skill works from the **diff + CI status** rather than pre-existing requirement/design docs, and handles any PR type.

## When to Use This Skill

**Use for:**

- Reviewing any open pull request (features, bug fixes, refactors, docs, infra/CI)
- Mixed PRs that span multiple concerns
- Pre-merge quality checks

**Do NOT use for:**

- SDD Phase 6 reviews (use the `scenario-driven-dev` skill instead — it reviews against requirements/design/test docs)
- Reviewing uncommitted local changes without a branch/PR intent (use `/code-quality` instead)

## Quick Start

- **By PR**: "Review PR #123" or "Review this PR: <url>"
- **By worktree/branch**: "Review the worktree at `~/.cursor/worktrees/sb/my-feature`" or "Review the `feat/my-feature` branch"

The review report will be saved to `docs/pr-reviews/pr-<number>-review.md`.

## Workflow Overview

The review follows one of two paths based on PR size and complexity:

```
Phase 0: Ensure PR       Phase 1: Triage          Phase 2: Review                Phase 3: Report & Post
(when given worktree/    (main agent)             (depends on PR size)           (main agent)
 branch instead of PR)
                                                  ┌─ FLAT (small PRs) ──────┐
Check local changes,     Worktree + metadata ──►  │  Main agent reviews all │──► Build flat report
push, find/create PR     CI + diff + classify     │  files inline, no       │    Save / post to PR
                         + decide review mode     │  grouping overhead      │
                                                  └─────────────────────────┘
                                                  ┌─ GROUPED (large PRs) ───┐
                                                  │  Group by concern, then │──► Verify subagent findings
                                                  │  subagent per group     │    Cross-group analysis
                                                  └─────────────────────────┘    Build grouped report
```

## Phase 0: Ensure PR Exists (when given a worktree or branch)

**Goal**: When the user provides a worktree path or branch name instead of a PR number/URL, ensure all local changes are committed and pushed, find or create the PR, then hand off the PR number to Phase 1.

**Skip this phase** if the user provides a PR number or URL directly — go straight to Phase 1.

### Step 0.1: Resolve the Worktree and Branch

If given a **worktree path**, determine the branch:

```bash
git -C <worktree_path> rev-parse --abbrev-ref HEAD
```

If given a **branch name**, find the worktree (if one exists):

```bash
git worktree list
```

Match the branch name against the worktree list. Record both the **worktree path** and the **branch name** for subsequent steps.

If a branch name is given but no worktree exists, check it out in a temporary worktree or work from the main repo — but this is unusual; the typical flow is worktree-based.

### Step 0.2: Check for Uncommitted Local Changes

From the worktree, check for any uncommitted or unstaged changes:

```bash
git -C <worktree_path> status --porcelain
```

If there are changes:

1. **Stage all changes**: `git -C <worktree_path> add -A`
1. **Commit** with a descriptive message based on the diff: `git -C <worktree_path> commit -m "<type>(scope): <description>"`
1. Follow the project's pre-commit conventions (run `pre-commit run --all-files --show-diff-on-failure` from the worktree first).

If there are no changes, proceed to the next step.

### Step 0.3: Check for Unpushed Commits

Check whether the local branch is ahead of the remote:

```bash
git -C <worktree_path> status -sb
```

Look for `ahead N` in the output. Alternatively:

```bash
git -C <worktree_path> log --oneline origin/<branch>..<branch>
```

If there are unpushed commits:

```bash
git -C <worktree_path> push -u origin <branch>
```

If the remote branch doesn't exist yet, the `-u` flag will create it and set up tracking.

### Step 0.4: Find or Create the PR

Check if a PR already exists for this branch:

```bash
gh pr list --head <branch> --json number,title,url,state --jq '.[] | select(.state == "OPEN")'
```

**If a PR exists**: Record the PR number and proceed to Phase 1.

**If no PR exists**: Create one:

```bash
gh pr create --head <branch> --fill
```

The `--fill` flag uses the branch's commit messages to auto-populate the title and body. If the branch has a single commit, its message becomes the PR title and body. For multi-commit branches, the branch name becomes the title and commit messages are listed in the body.

Record the new PR number and proceed to Phase 1.

### Step 0.5: Verify Remote is Up-to-Date

As a final sanity check, confirm the remote branch matches the local HEAD:

```bash
git -C <worktree_path> log --oneline -1 HEAD
gh api repos/{owner}/{repo}/branches/<branch> --jq '.commit.sha[:7]'
```

If the SHAs don't match, something went wrong with the push — investigate before proceeding.

After Phase 0 completes, you have a **PR number** and a **worktree path**. Proceed to Phase 1 — the worktree is already known, so Step 1.1 can skip the worktree search.

## Phase 1: Triage

**Goal**: Understand the PR scope, check CI, and group changes by logical concern.

**The main agent performs all of these steps (no subagents).**

**IMPORTANT**: All `gh` commands must use `required_permissions: ["all"]` because the GitHub CLI makes TLS calls that fail inside the default sandbox on macOS.

### Step 1.1: Locate Local Worktree

Before fetching remote metadata, check if the PR's branch is checked out in a local git worktree. This gives subagents fast, direct file access (no need to checkout or clone).

```bash
git worktree list
```

Match the PR's head branch (from the PR URL or metadata) against the branch names in the worktree list. If a match is found, record the **worktree path** — you'll pass it to every subagent so they can read full files locally.

**Why this matters:**

- Subagents can `Read` files directly from the worktree path instead of relying on `gh` API calls or the diff alone.
- Reading full files from a local worktree is faster and more reliable than fetching via GitHub API.
- The worktree contains the exact code the PR will merge, including any uncommitted local changes the author may still be working on.

If no matching worktree is found, the review proceeds normally — subagents will read files from the main workspace (which may be on a different branch). In that case, subagents must rely more heavily on the diff excerpts.

### Step 1.2: Fetch PR Metadata

```bash
gh pr view <number> --json title,body,author,baseRefName,headRefName,files,additions,deletions,changedFiles,state,reviews,labels
```

### Step 1.2b: Find the Task File (if available)

Look for the task `.md` file that originated this PR. The task file contains the original acceptance criteria, scope decisions, and context that the PR description may not fully repeat.

**In auto-agent context**: the task file is materialised at `docs/tasks/<task-id>.md` inside the cloned workspace by the dispatch pipeline (not committed to git, just present on disk):

```bash
ls docs/tasks/
```

**In local/Cursor context**: task files live in `docs/tasks/` which is a symlink to `.shared-tasks/` at the repo root. If a matching worktree was found in Step 1.1:

```bash
ls <worktree>/docs/tasks/
# Or from the main repo
ls <main_repo>/.shared-tasks/
```

Match the task file by the PR branch name or by the `pr:` field in the frontmatter. If found, read it and extract:

- **Title** (`title:` frontmatter) — verify the PR title/description references it
- **Desired Behavior** section — use as the primary review checklist (observable outcomes the implementation must produce)
- **Acceptance Criteria** section — secondary checklist (implementation-specific checks)
- **Scope / Key Files** — focus the review on the stated scope
- **`depends_on`** / **`related`** — note any dependency context

If no task file is found (e.g. the PR was opened manually, not from a task file), skip this step and proceed — the PR description and diff are your sole source of requirements.

### Step 1.3: Check CI Status

```bash
gh pr checks <number>
```

> **Warning**: Do NOT run `gh pr checks` in parallel with other `gh` commands
> or other tool calls. When checks are still pending, `gh pr checks` exits with
> code 8. In environments that run multiple tool calls concurrently, this
> non-zero exit code cancels all sibling parallel calls, causing lost work and
> requiring a full retry. Always run `gh pr checks` as a standalone sequential
> step.

Surface CI failures immediately — if critical checks fail, note them prominently before proceeding. The review should still continue (CI failures don't block review), but failures must appear at the top of the final report.

**Runner failure fast-path**: When a check shows `fail`, fetch job metadata via
`gh api repos/{owner}/{repo}/actions/runs/{run_id}/jobs --jq '.jobs[] | select(.conclusion == "failure") | {name, conclusion, started_at, completed_at, steps: (.steps | length)}'`.
If a failed job has **zero steps** and completed in **≤5 seconds**, it's a runner
provisioning failure (the GitHub Actions runner never started). Do NOT investigate
further — no logs exist. Note it in the report as "CI infrastructure failure
(runner never provisioned — 0 steps, completed in Ns)" and recommend a re-run.
Do NOT fetch run logs, parse step outputs, or make additional API calls for jobs
matching this pattern. Do NOT count runner failures as code-related CI failures
or let them block the review verdict.
This pattern typically indicates GitHub Actions billing limits, runner pool
exhaustion, or transient infrastructure issues.

**For infra/CI PRs that modify workflow files**: Check whether the jobs being added, renamed, or restructured were actually **triggered and executed** — not just skipped. A "skipping" status on the very jobs the PR modifies means the changes are **unverified**. This commonly happens when the change-detection filter (e.g., `dorny/paths-filter`) doesn't include the workflow file itself (`.github/workflows/ci.yml`). Flag as **critical** — the author must either update the change-detection filters to include the workflow file, or trigger a manual `workflow_dispatch` run to validate the modified jobs pass before merging.

### Step 1.4: Get the Full Diff

```bash
gh pr diff <number>
```

For large diffs (1000+ lines), save to a temp file and read in sections by using line offsets from `grep -n "^diff --git"` to find file boundaries.

Read the full diff to understand all changes. **Keep a mental map of which diff sections belong to which files** — you'll need this to provide relevant diff context to subagents in Phase 2.

### Step 1.5: Classify the PR

Determine the PR type based on the changes:

| PR Type      | Indicators                                            |
| ------------ | ----------------------------------------------------- |
| **feature**  | New endpoints, new models, new service functions      |
| **bugfix**   | Fixes to existing logic, issue references             |
| **refactor** | Restructuring without behavior change, renames, moves |
| **docs**     | Markdown, docstrings, comments only                   |
| **infra**    | CI/CD, Docker, config files, dev tooling              |
| **mixed**    | Multiple of the above (most common for large PRs)     |

### Step 1.5b: Choose Review Mode (flat vs grouped)

After classifying the PR, decide the review mode. This determines whether you group
files by concern or review them as a flat list.

| Condition                                                       | Review Mode             | What to do                                                    |
| --------------------------------------------------------------- | ----------------------- | ------------------------------------------------------------- |
| ≤ ~200 changed lines **and** ≤ ~10 files                        | **Flat**                | Skip Step 1.6 (grouping). Go straight to Phase 2 flat review. |
| Single logical concern (even if > 200 lines)                    | **Flat**                | Same — grouping adds no value when everything is one concern. |
| Test-only, docs-only, or config-only changes                    | **Flat**                | Lightweight review; grouping is overhead.                     |
| Follow-up review (delta since last review)                      | **Flat**                | Always flat — see [Follow-Up Reviews](#follow-up-reviews).    |
| > ~200 lines **and** 2+ distinct logical concerns               | **Grouped**             | Proceed to Step 1.6 to group files by concern.                |
| > ~500 lines **and** 3+ groups with different review checklists | **Grouped + subagents** | Group files, then spawn subagents in Phase 2.                 |

**Why flat is the default for small PRs:** Formal grouping is a thinking tool that pays
off when a PR spans unrelated domains (e.g., webhook handler + data-fix script + CI config).
For small, focused PRs, the grouping step and group-by-group report structure add ceremony
without improving review quality. A flat file-by-file pass with a single findings table is
faster to produce, easier to read, and equally thorough.

Record your decision (`flat` or `grouped`) — it determines which template and Phase 2 path
you follow.

### Step 1.5c: Check for Design Doc References

If the PR is classified as **feature** (or mixed with a feature component), check whether it
implements a feature with design docs in `docs/design/`:

```bash
ls docs/design/
```

Look for clues in the PR title, branch name, description, or changed file paths that match
a design folder. For example, a PR titled "Auto-Agent: Blob Storage Client" or branch
`feat/blob-client` would match `docs/design/cloud-agent-service/`.

If a matching design folder exists, record its path — you'll pass it to the relevant
subagent(s) in Phase 2 so they can verify the implementation matches the design.

### Step 1.6: Group Changed Files by Logical Concern

> **Skip this step entirely if you chose "flat" review mode in Step 1.5b.**
> Flat reviews don't need groups — proceed directly to Phase 2.

This step applies only to **grouped** reviews. Group files that belong to the same logical change together.

**Grouping heuristics (apply in order):**

1. **Shared domain**: Files in the same domain module (e.g., `payment_event/`, `credit_ledger/`) that are modified together
1. **Feature cohesion**: Files that implement the same feature (e.g., a handler + its schema + its tests)
1. **Change type**: If no domain grouping fits, group by change type (e.g., "dev tooling", "CI config", "documentation")
1. **Tests with their code**: Test files should be grouped with the code they test, not in a separate "tests" group

**For each group, document:**

- Group name (descriptive, e.g., "Refund webhook handler")
- List of files with full paths
- Summary of what changed (2-3 sentences)
- PR type classification for this group (feature/bugfix/refactor/docs/infra)
- Dependencies on other groups (if any)

**Aim for 2-5 groups.** If a PR has fewer than 5 files, a single group is fine. If a PR has 30+ files, aim for 4-5 groups max.

**Grouping tips learned from practice:**

- Scripts/tooling that mirror webhook/service logic should be grouped separately — they often have different quality concerns (safety, idempotency, hardcoded values).
- If the PR includes data-fix artifacts (for example `apps/server/api/scripts/data_fixes/**`, `scripts/data_fixes/**`, `migrations/**`, Alembic/Lembic files), create a dedicated group for them.
- Docs/infra changes can be combined into a single group even if they span many files, since the review checklist is lighter.
- When a group modifies a function, check if **sibling functions** in the same file need the same change — flag this in the group summary for the subagent.

### Step 1.7: Data-Fix / Migration Detection (MANDATORY)

Before launching subagents, check whether the PR touches any of these:

- `apps/server/api/scripts/data_fixes/**`
- `scripts/data_fixes/**`
- `**/migrations/**` (including Alembic/Lembic files)
- One-off DB scripts that execute DML/DDL (`UPDATE`, `DELETE`, `INSERT`, `ALTER`, etc.)

If yes:

1. Mark that group as `scripts/tooling` or `infra` (as appropriate)
1. In the subagent prompt, explicitly instruct review against:
   - `.claude/skills/prod-data-fix-script/SKILL.md`
   - `.claude/skills/prod-data-fix-script/report-template.md`
1. Require findings on:
   - dry-run defaults and explicit `--apply` behavior
   - env/DB URL resolution and active environment visibility
   - transaction safety, guardrails, idempotency, and verification output
   - report completeness (PR link/status/approver metadata when applicable)

### Step 1.8: Migration Scope & Startup Side-Effect Detection (MANDATORY)

Check whether the PR includes **database migration files** (Alembic/Lembic) or **application startup code** that seeds/updates DB data.

#### Migration Scope Violations

Migration files (`**/migrations/versions/**`, `**/alembic/versions/**`, `**/lembic/versions/**`) should **only** contain schema changes (DDL) and the minimal data modifications directly caused by those schema changes (e.g., populating a new non-nullable column with a computed default so the `ALTER` can succeed).

Migrations **must NOT** contain:

- Large-scale data corrections or backfills (e.g., fixing incorrect values across many rows)
- Business logic–driven data transformations (e.g., recalculating credits, normalizing strings)
- Batch `UPDATE`/`INSERT`/`DELETE` statements that are not structurally required by the schema change

**Why:** Migrations run automatically during deployment with no operator preview, no dry-run, no guardrails, and no rollback confirmation. Data-fix operations need the safety controls provided by the `prod-data-fix-script` skill (dry-run default, row-count guardrails, transaction safety, operator confirmation, idempotency checks).

If a migration contains data-fix operations that go beyond what the schema change structurally requires:

1. **Flag it as a critical finding** — the data-fix portion must be extracted into a separate data-fix script following `.claude/skills/prod-data-fix-script/SKILL.md`.
1. The migration should keep only the DDL (schema change) and any minimal DML tightly coupled to it.
1. Instruct the subagent reviewing the migration group to check for this separation.

#### Startup Data Seeding Violations

Application startup code (e.g., `on_startup` hooks, `lifespan` handlers, module-level initialization, `create_app()` setup) **must NOT** seed or upsert default values into the database.

Common anti-patterns to detect:

- Inserting default config rows, feature flags, or lookup data at app boot
- `get_or_create` / `upsert` calls during startup to ensure default records exist
- Module-level DB writes that run on import or app initialization

**Why:** Seeding at startup is an invisible side effect — it runs silently on every deploy, makes it hard to track what data was inserted and when, can overwrite intentional manual changes (stale-data risk), and bypasses the normal data management workflow. Default data should be managed through explicit migrations (for schema-coupled defaults) or data-fix scripts (for backfills/corrections).

If startup code seeds or upserts default values:

1. **Flag it as a warning** — suggest moving the seeding to an Alembic migration (if it's a one-time schema-coupled default) or a data-fix script (if it's a backfill/correction).
1. Include this in the subagent prompt for the relevant group.

### Step 1.9: System Prompt Change Detection (MANDATORY)

Check whether the PR modifies any **agent system prompt** strings or templates. These are typically found in:

- Files containing `system_prompt`, `instruction`, or `system_message` variables/constants used for LLM agent configuration
- Files matching patterns like `**/prompts/**`, `**/instructions/**`, `**/system_prompt*`
- Changes to prompt-related config in service modules (e.g., session summary, thought generation, session evaluation)

**Why this matters:** In our architecture, the system prompts defined in code are **default values only**. In real environments (preview and production), prompts are read from the **database config table** (the `system_prompts` admin page). If code changes a prompt but the DB is not updated, the change has **no effect** in deployed environments.

**Known system prompt keys in the DB config table:**

| DB Config Key                                 | Description                                        |
| --------------------------------------------- | -------------------------------------------------- |
| `session_summary.system_prompt`               | Session Summary system prompt                      |
| `thoughts.thought_generation.instruction`     | Thought generation instruction                     |
| `session_evaluation.system_prompt`            | Session Evaluation system prompt (Batch mode)      |
| `session_evaluation.sequential_system_prompt` | Session Evaluation system prompt (Sequential mode) |

If the PR modifies any system prompt content:

1. **Flag it as a warning** in the review — the developer must also update the prompt in the DB config table after merge.
1. Add a **Post-Merge Action Items** section to the review report with explicit instructions:
   <!-- CUSTOMIZE: Replace these instructions with your project's process for updating
     deployed configuration after merge. This could be an admin dashboard, a CLI tool,
     a config-management API, a deployment script, a GitOps config repo, or a DB migration —
     whatever mechanism your project uses to manage runtime configuration in staging/production.
     An onboarding agent should check for:
     - Config management tools (dashboards, CLI utilities, deployment scripts, GitOps repos)
     - Environment-specific update procedures (staging vs. production)
     - Runtime configuration stores (DB tables, config services, key-value stores, config files)
     Example: "Update the prompt value using: `./scripts/update-config.sh --env staging --key <key>`" -->
   - **After merging to staging**: Update the prompt value in the staging environment's configuration store and verify the new version is active.
   - **After release to production**: Update the prompt value in the production environment's configuration store and verify the new version is active.
1. Include the specific DB config key(s) that need updating, so the developer knows exactly which rows to modify.
1. In the subagent prompt for the group containing prompt changes, explicitly instruct the reviewer to check for this code-vs-DB drift risk.

## Phase 2: Review

**Goal**: Review all changed code for correctness, completeness, edge cases, and adherence to project conventions.

The approach depends on the review mode chosen in Step 1.5b.

### Path A: Flat Review (small / focused PRs)

This is the default for most PRs. The main agent reviews all files directly — no grouping,
no subagents.

**Steps:**

1. For each changed file, read the **full file** (not just the diff) to understand context.
1. Use the diff to identify exactly what changed.
1. Apply the review checklist (see below) to each file's changes.
1. Look for bugs, missing edge cases, regressions, and missing tests.
1. Collect all findings in a single flat list.

Skip directly to Phase 3 when done. Use the **flat report template** at
`.claude/skills/pr-review/review-template-flat.md`.

### Path B: Grouped Review (large / multi-concern PRs)

For PRs with 2+ distinct logical groups identified in Step 1.6.

**Inline grouped review** (no subagents): When the groups exist but the total diff is
manageable (≤ ~500 lines), the main agent reviews each group sequentially, applying the
relevant checklist to each group. Use the **grouped report template** at
`.claude/skills/pr-review/review-template.md`.

**Subagent grouped review**: When the diff is large (> ~500 lines) and groups have
**different review concerns** (e.g., backend logic vs. frontend UX vs. infra config),
spawn one `generalPurpose` subagent per group (max 4 concurrent). Use the subagent
prompt template below. Trivial groups (e.g., a single docs file change) can still be
reviewed inline even when other groups use subagents.

### Subagent Prompt Template

Use this template for each group's subagent. Replace all `<placeholders>`.

```
Task tool parameters:
  subagent_type: generalPurpose
  description: "Review <group_name>"
  readonly: true
```

**Prompt:**

```
You are reviewing a group of changes from PR #<number> titled "<pr_title>".

## Group: <group_name>

**Summary**: <group_summary>
**PR type for this group**: <feature|bugfix|refactor|docs|infra>

## Local Worktree

<If a worktree was found in Step 1.1, include this section:>

The PR branch is checked out locally at: `<worktree_path>`

Use this path as the base when reading files. For example, to read
`apps/server/api/src/foo.py`, read `<worktree_path>/apps/server/api/src/foo.py`.

<If no worktree was found, omit this section entirely.>

## Files to Review

<list each file with full path — if a worktree exists, provide ABSOLUTE paths
rooted at the worktree, e.g. /Users/me/.cursor/worktrees/sb/my-branch/apps/server/api/src/foo.py>

## What Changed (diff excerpts)

<Paste the relevant diff sections for this group's files. This tells the subagent
exactly what lines were added/removed so it can focus its review. For large diffs,
include at minimum the function/class-level hunks. Omit trivial changes like
import reordering if they are not the focus.>

## Project Coding Guidelines

Read the project coding guidelines at: AGENTS.md
<If a worktree exists, provide the absolute path: <worktree_path>/AGENTS.md>

## Design Doc Alignment (when applicable)

If this feature has design docs, read and check implementation against:
- <design_folder>/high-level-design.md — overall architecture and key decisions
- <design_folder>/<component-spec>.md — detailed spec for this component

Verify: data models match spec, API endpoints match contracts, state transitions match
design, and key architectural decisions are followed. Flag any deviations.

## Data-Fix Script Standards (when applicable)

If this group includes data-fix scripts or DB migrations, also read and enforce:
- .claude/skills/prod-data-fix-script/SKILL.md
- .claude/skills/prod-data-fix-script/report-template.md

## Your Task

For each file listed above:

1. Read the FULL file (not just the diff) to understand complete context
2. Use the diff excerpts above to understand exactly what changed
3. Check the changes against the review checklist below
4. Look for bugs, missing edge cases, and regressions

## Review Checklist

### Core Checks (all PR types)

- **Correctness**: Does the logic do what it claims? Off-by-one errors, wrong comparisons, missing null checks
- **Completeness**: Are all cases handled? Missing enum values, unhandled error paths
- **Edge cases**: Empty inputs, boundary values, concurrent access
- **Error handling**: Silent failures, generic catches, missing rollback
- **Security**: Input validation, no hardcoded secrets, auth checks
- **Tests**: Do tests exist for the changes? Do they test the right things? Apply the full **Test Quality Review (MANDATORY)** checklist from this skill — coverage sufficiency, integration test presence, anti-pattern detection, mock appropriateness, and assertion depth. Common red flags: fake/dummy repository classes (`DummyRepo`, `FakeRepo`), internal service mocking (`db.x = AsyncMock()`), smoke-only assertions (`assert status_code == 200` with no data checks), mocks without `spec`/`autospec`, skipping ASGI lifespan. If tests have significant gaps for acceptance criteria, flag as warning.

### Additional Checks for features/bugfixes

- **API contracts**: Request/response schemas match, function signatures correct
- **Data consistency**: Normalization, case sensitivity, FK constraints
- **Performance**: N+1 queries, unnecessary loops, missing indexes
- **Design doc alignment**: If this feature has design docs in `docs/design/`, read the relevant high-level design and component spec. Verify the implementation matches the architecture, data models, API contracts, and key decisions in the design. Flag deviations — they may be intentional improvements or accidental drift.
- **Config vs code drift**: If the service already has a dedicated configuration mechanism (e.g., agent `append_prompt`, a config table, a YAML file, feature flags), behaviour that belongs in config must NOT be hardcoded in Python/TypeScript. Flag as a **warning** when logic that is already expressible via the existing config layer is instead embedded in code — this creates a second source of truth that gets out of sync and requires a code deploy to change. Suggest moving the logic to the appropriate config location.

### Additional Checks for refactors

- **Behavioral equivalence**: Does the refactored code produce the same results?
- **No regressions**: Are existing tests still passing? Were tests updated?

### Additional Checks for infra/CI

- **Config correctness**: Valid YAML/JSON, correct key names
- **Security**: No secrets committed, no overly permissive permissions
- **Idempotency**: Can the config be applied multiple times safely?
- **Inline scripts**: If a workflow step contains an inline shell or Python script longer than ~20 lines (e.g., `run: python3 << 'PYEOF'` heredocs or multi-line `run:` blocks), flag it as a **warning** — the script should be extracted into a standalone file under `scripts/` and called from the workflow step instead. Inline scripts are hard to lint, test, and reuse.
- **Modified jobs must be verified**: If the PR adds, renames, or restructures CI jobs, verify that those specific jobs were actually triggered and executed (not skipped). A "skipping" status on the jobs the PR modifies means the changes are unverified — flag as **critical**. Common cause: the change-detection filter (e.g., `dorny/paths-filter`) doesn't include `.github/workflows/ci.yml`, so workflow-only PRs don't trigger the affected jobs. The fix is to add the workflow file to the filter or run a manual `workflow_dispatch`.

### Additional Checks for scripts/tooling

- **Safety defaults**: Dry-run should be the default; destructive actions require explicit opt-in
- **Hardcoded values**: No production IDs, PII, org-specific values, or secrets as defaults
- **Idempotency**: Can the script be run multiple times without creating duplicates?
- **Environment**: Does it load env vars consistently with other scripts?
- **Consistency with service logic**: If the script mirrors service-layer logic (e.g., creating the same records a webhook creates), flag duplication risk

### Additional Checks for system prompt changes

- **Code-vs-DB drift**: The prompts in code are defaults only; deployed environments read from the DB config table. Flag that the DB must be updated post-merge.
- **Key mapping**: Identify which DB config key(s) correspond to the changed prompt(s). Known keys: `session_summary.system_prompt`, `thoughts.thought_generation.instruction`, `session_evaluation.system_prompt`, `session_evaluation.sequential_system_prompt`.
- **Completeness**: If the PR changes a prompt used in multiple modes (e.g., batch vs sequential evaluation), verify all related prompts are updated consistently.
- **Post-merge action**: The review must include explicit action items to update prompts in the staging environment after merge and in the production environment after release (see admin URLs in the CUSTOMIZE block above).

### Additional Checks for data-fix scripts / DB migrations

- **Execution gate**: For production apply paths, does process require PR approval before running `--apply`?
- **DB selection clarity**: Is DB target/source explicit (`--db-url` vs environment settings) and visible in preview output?
- **Transactionality**: Are write operations wrapped in a safe transaction boundary?
- **Guardrails**: Are max-update or equivalent guardrails present before destructive updates?
- **Verification**: Are pre/post checks and idempotency rerun clearly supported?
- **Reporting**: Is there a report/checklist artifact with PR link/status/approver metadata when expected?
- **Migration scope**: Migration files must only contain schema changes (DDL) and the minimal DML structurally required by those changes (e.g., populating a new non-nullable column). Large-scale data corrections, backfills, or business-logic-driven transformations must NOT live in migration files — they belong in a separate data-fix script (see `.claude/skills/prod-data-fix-script/SKILL.md`). Flag any migration that embeds data-fix operations as **critical**.
- **No startup data seeding**: Application startup/lifespan code must NOT seed, upsert, or `get_or_create` default values in the database. This is an invisible side effect that silently runs on every deploy, risks overwriting intentional manual changes, and bypasses normal data management. Flag as **warning** and suggest using a migration (for schema-coupled defaults) or a data-fix script (for backfills).

## Clarification Step (IMPORTANT)

After reading the files and understanding the changes, BEFORE providing your review findings, identify any aspects of the changes where the intended behavior is unclear or where you have questions. Use the `AskQuestion` tool to ask the human developer clarifying questions.

**Ask clarification questions when:**
- The change's purpose or expected behavior is not obvious from the diff
- You're unsure if something is intentional or an oversight
- You notice potential inconsistencies with other parts of the codebase and need context
- The PR description doesn't fully explain the "why" behind a specific change
- You want to confirm assumptions about edge cases or error handling

**Do NOT ask clarification questions for:**
- Things you can verify by reading more code
- Obvious issues that are clear from the code alone
- Questions that are already answered in the PR description or commit messages

If you have questions, ask them now using the AskQuestion tool. Wait for the human's response before finalizing your review findings.

## Output Format

Return your findings as a structured list. For each finding:

- **Severity**: critical (blocks merge), warning (should fix), nit (minor suggestion)
- **File**: full file path
- **Line(s)**: line number or range (if applicable)
- **Finding**: clear description of the issue
- **Evidence**: quote the actual code snippet (2-5 lines) that demonstrates the issue (required for critical/warning)
- **Suggestion**: how to fix it (if applicable)

At the end, provide:
- **Group verdict**: APPROVE / NEEDS WORK
- **Summary**: 1-2 sentence summary of the group's quality

If you find no issues, say so explicitly — an empty findings list with APPROVE is a valid response.

IMPORTANT: When reviewing a method/function that was changed, also check SIBLING methods in the same
class or module that do similar work. If the change fixes a bug or adds handling for a new case,
the same fix may need to be applied to sibling methods. Flag any inconsistencies.

IMPORTANT: For every critical or warning finding, you MUST include EVIDENCE — quote the actual
code snippet (2-5 lines) that demonstrates the issue. The main agent will verify your findings
against the real code. Findings without evidence will be discarded.
```

### Handling Group Dependencies

If Group B depends on Group A (e.g., Group A defines a schema that Group B uses), include a note in Group B's subagent prompt:

```
## Dependencies
This group depends on changes in "<Group A name>". Key changes from that group:
- <brief description of relevant changes>
```

## Phase 3: Synthesis & Verification

**Goal**: Build the final report and post to the PR. For grouped reviews with subagents,
also verify subagent findings for correctness.

**For flat reviews**: Skip Steps 3.1-3.3 (no subagents, no groups). Go directly to
Step 3.4 (Build the Report) with your findings from Phase 2.

**For grouped reviews**: This is the most important phase. Subagents can make mistakes —
they may misread code, flag non-issues, miss the actual bug, or cite wrong line numbers.
The main agent must **verify every critical and warning finding** before including it in
the report.

### Step 3.1: Collect Results (grouped reviews only)

Gather findings from all subagents. If any subagent failed or timed out, note it in the report.

### Step 3.2: Verify Subagent Findings (grouped reviews only)

**The main agent MUST verify each finding before including it.** This is the quality gate that separates a useful review from a misleading one.

**For each critical finding:**

1. **Read the cited file and line numbers** — Does the code actually look like what the subagent claims?
1. **Check the logic** — Is the subagent's reasoning correct? Could there be context it missed (e.g., the function is called differently than assumed, or there's a fallback path)?
1. **Verify the severity** — Is this truly a bug/blocker, or is the subagent being overly cautious? Downgrade if needed.
1. **Check for false positives** — Subagents sometimes flag intentional design choices as bugs. If the PR description or commit messages explain the choice, it's not a bug.

**For each warning finding:**

1. **Spot-check the claim** — Read the relevant code to confirm the issue exists.
1. **Assess impact** — Is this a real concern in practice, or theoretical?
1. **Deduplicate** — Multiple subagents may flag the same issue from different angles. Merge them.

**For nits:** Accept as-is unless obviously wrong (wrong file/line reference).

**Drop or downgrade findings** that don't hold up after verification. A shorter, accurate report is far more valuable than a long report with false positives. False positives erode trust in the review process.

### Step 3.3: Cross-Group Analysis

> **Skip this step for flat reviews** — there are no groups to cross-reference.

After verifying individual findings, consider cross-group interactions:

- Do schema changes in Group A break usage in Group B?
- Do multiple groups create the same records using different code paths (duplication risk)?
- Are there shared conventions (e.g., "refunds are stored as negative amounts") that both groups must agree on?

Add any cross-group findings to the report.

### Step 3.4: Build the Report

Choose the template that matches the review mode from Step 1.5b:

- **Flat review** → `.claude/skills/pr-review/review-template-flat.md`
- **Grouped review** → `.claude/skills/pr-review/review-template.md`

**Flat report organization:**

1. **PR Overview** — title, author, stats, CI status
1. **Critical/Blocking Issues** — surface these FIRST, before anything else
1. **Findings** — single flat table, all files together
1. **Overall Verdict** — `## Verdict: ✅ APPROVE` or `## Verdict: ❌ NEEDS WORK`

**Grouped report organization:**

1. **PR Overview** — title, author, stats, CI status
1. **Critical/Blocking Issues** — surface these FIRST, before anything else
1. **Group-by-Group Findings** — organized by group with severity tags
1. **Cross-Group Concerns** — interactions between groups
1. **Overall Verdict** — `## Verdict: APPROVE` or `## Verdict: NEEDS WORK`

<!-- CUSTOMIZE: Replace the bot name below with your project's CI bot or review automation
  name. If your project doesn't have a bot that parses review verdicts, you can simplify
  this note to just describe the format convention. An onboarding agent should check for:
  - GitHub Actions that parse PR comments for verdict keywords
  - Bot accounts configured in the repo (e.g., in .github/ or CI config)
  - CI integrations that act on review status
  Example: "Verdict format is machine-parsed by my-ci-bot." -->
> **⚠️ Verdict format may be machine-parsed by CI/bot integrations.** Always use `## Verdict:` as the heading
> (not `### Verdict:` or `**Verdict**:`). The text after the colon must contain `APPROVE` or
> `NEEDS WORK`.
>
> **Do NOT place GitHub emoji shortcodes** (`:white_check_mark:`, `:x:`, etc.) between
> `Verdict:` and the keyword — bots that use regex parsing (e.g., `[^A-Z]*?` with `re.IGNORECASE`)
> will break on ASCII letters within shortcodes. Unicode
> emoji characters (✅ / ❌) are safe because they contain no ASCII letters, but shortcodes
> like `:white_check_mark:` contain `w`, `h`, `i`, `t`, `e`... which block the regex.
>
> - ✅ `## Verdict: APPROVE` — works
> - ✅ `## Verdict: ✅ APPROVE` — works (Unicode emoji, no ASCII letters)
> - ❌ `## Verdict: :white_check_mark: APPROVE` — **breaks** (shortcode has letters)

### Step 3.5: Determine Verdict

| Verdict        | Criteria                                                                        |
| -------------- | ------------------------------------------------------------------------------- |
| **APPROVE**    | Zero critical findings AND zero warning findings. Nits are acceptable.          |
| **NEEDS WORK** | One or more critical **or** warning findings that should be fixed before merge. |

### Step 3.6: Save and Present

Save the report to `docs/pr-reviews/pr-<number>-review.md` and display it to the user.

### Step 3.7: Post to PR

**After completing the review, always post the final review markdown file to the PR as a comment.**

Use the GitHub CLI:

```bash
# Post as a PR review comment (required_permissions: ["all"])
gh pr review <number> --comment --body "$(cat docs/pr-reviews/pr-<number>-review.md)"
```

This ensures the review is visible to the PR author and other reviewers directly in the GitHub UI.

### Step 3.8: Invoke Review Bot (when verdict is APPROVE)

<!-- CUSTOMIZE: Replace the bot name and command below with your project's review automation.
  If your project doesn't have a bot that processes review verdicts, you can remove this step
  entirely. An onboarding agent should check for:
  - GitHub Actions that parse PR comments (e.g., @my-bot approve)
  - Bot accounts configured in the repo
  - CI integrations that act on review approval status
  - Webhook handlers that listen for PR comment events
  Example: gh pr comment <number> --body "@my-ci-bot approve" -->

If the review verdict is **APPROVE** (zero critical findings AND zero warning findings),
trigger the review bot to run its own verification and submit the formal GitHub approval:

```bash
# Post bot approval command as a PR comment (required_permissions: ["all"])
gh pr comment <number> --body "@<review-bot> approve"
```

> **⚠️ The comment body must be the exact literal string expected by the bot.**
> Do NOT wrap it in backticks, bold (`**`), code blocks, or add emoji prefixes.
> Bots typically use regex to parse the command (e.g., `@bot-name\s+(\w+)`) — any markdown
> formatting around the mention will prevent the command from being recognized.

The bot will then run its pipeline (CI checks, criteria, AI review) and, if all stages
pass, submit a GitHub APPROVE review on the PR.

**CI still running is NOT a blocker** — if your bot handles in-flight CI gracefully,
you can trigger it as soon as the review verdict is APPROVE, even if some CI
checks are still pending. The bot will wait for CI to complete before making its final
approval decision, so there is no risk of approving over a failing build.

**Do NOT invoke the bot when the verdict is NEEDS WORK** — the review comment itself
is sufficient in that case. The developer or `/pr-fix` skill will address the findings
and re-trigger the bot after fixes are pushed.

**IMPORTANT**: The presence of any warning (even a minor one like an outdated docstring
or missing test) means the verdict is NEEDS WORK and the bot must NOT be triggered.
Only nit-level findings are acceptable for an APPROVE verdict.

## Follow-Up Reviews

When asked to re-review a PR that was already reviewed in the current conversation, use this streamlined flow instead of repeating the full Phase 0-3 workflow.

### When This Applies

- The user says "review again", "PR got updated", "can you check the latest push", etc.
- You have a **previous review** of the same PR in the current conversation (with a known last-reviewed commit SHA)

### Streamlined Flow

1. **Identify the delta**: Compare the current PR head against the last reviewed commit:

   ```bash
   git diff <last_reviewed_sha>..<current_head> --stat
   git diff <last_reviewed_sha>..<current_head>
   ```

1. **Check CI**: Fetch the latest check status with `gh pr checks <number>`.

1. **Assess delta size**:

   - **Small delta (\<= ~200 lines, \<= ~5 files)**: Review inline. The main agent reads the changed files and diff directly. Do NOT spawn subagents. This is the common case for follow-up fixes.
   - **Large delta (> ~200 lines or many files across multiple concerns)**: Fall back to the full Phase 1-3 workflow, but scope the diff to only the delta since last review.

1. **Focus the review on prior findings**: The primary question in a follow-up review is: *"Did this update fix the issues from the last review, and did it introduce anything new?"* Structure findings as:

   - Previously flagged issues that are now **resolved**.
   - Previously flagged issues that are **still open**.
   - **New issues** introduced by the delta.

1. **Run targeted tests**: Only run the test suites relevant to the changed files, not the full suite.

1. **Update the existing review artifact**: Overwrite `docs/pr-reviews/pr-<number>-review.md` with the new review (update the reviewed head SHA, CI status, findings, and verdict). Post the updated review to the PR.

### Key Principle

Follow-up reviews should be **fast and focused**. The goal is to verify the fix, not re-review the entire PR from scratch. Avoid re-reading unchanged files or re-analyzing previously approved code unless the delta touches them.

## Severity Definitions

| Severity     | Meaning                                                              | Examples                                                          |
| ------------ | -------------------------------------------------------------------- | ----------------------------------------------------------------- |
| **critical** | Bug, security issue, or logic error that will cause problems in prod | Missing null check that causes crash, hardcoded secret, data loss |
| **warning**  | Should be fixed but won't cause immediate harm                       | Missing error handling, poor performance, incomplete validation   |
| **nit**      | Style, naming, or minor improvement suggestion                       | Variable naming, comment clarity, import ordering                 |

## Test Quality Review (MANDATORY)

In addition to code quality, evaluate the tests the worker wrote. This is as
important as code correctness — bad tests hide bugs.

### Coverage Sufficiency

- Every acceptance criterion has a corresponding test?
- Behavioral paths (error cases, edge cases) without coverage?
- For bug fixes: a regression test that reproduces the original bug?
- For new standalone helper/utility functions with pure logic: unit tests?

### Integration Test Presence

- DB/API feature has `@pytest.mark.db` or `@pytest.mark.api` tests?
- If only unit tests exist for a feature that hits the database → WARNING.
- If only mocked tests exist for behavior that can use real services → WARNING.

### Anti-Pattern Detection

(Condensed from `docs/knowledge/testing/test-anti-patterns.md`.)

1. **Tests encoding bugs as expected behavior** — asserting the wrong value
   because the developer copied buggy output into the assertion
2. **Symmetric bugs** — same wrong assumption in code and test, so the test
   passes but behavior is incorrect
3. **Incomplete test setup** — entity created but not its required
   relationships; test passes in isolation, fails in real data graphs
4. **No cross-validation** — related calculations (total vs. sum of parts)
   tested in isolation but never compared
5. **No lifespan smoke test** — service has `lifespan()` but no test boots it
   to catch import errors, missing env vars, DI failures
6. **Mocks erasing the calling contract** — mock simulates an idealized call
   pattern that doesn't match the real dependency's behavior
7. **Change-detector tests** — asserts implementation details (exact SQL, mock
   call counts) instead of behavioral outcomes; breaks on every refactor

### Mock Appropriateness

| NEVER Mock (Internal)  | ALWAYS Mock (External)          |
| ---------------------- | ------------------------------- |
| Database               | OpenAI, Anthropic               |
| API Server             | ElevenLabs                      |
| Voice Gateway          | Twilio (use docker mock)        |
| Redis                  | Stripe (use StripeMockSDK)      |
| Service Layer          | ConvAI (use mock server)        |

No fake/dummy repository classes — use real DB or `AsyncMock(spec=...)` with
`assert_called_with` to verify signatures.

### Assertion Depth

- Tests assert semantic business outcomes (not just `status_code == 200`)
- Integration tests verify durable side effects (DB rows created/changed,
  events emitted)
- State proof boundaries honestly — call out what the test does NOT prove

### Severity for Test Issues

- **CRITICAL**: no integration tests for DB/API feature; fake repository
  classes; tests encoding bugs as expected behavior
- **WARNING**: insufficient assertion depth; missing edge case coverage;
  mocks for internal services; change-detector tests; missing unit tests
  for standalone helper/utility functions with pure logic
- **NIT**: style issues in tests; missing comments showing expected
  calculations

## Tips for Effective Reviews

- **Read full files, not just diffs**: The diff shows what changed, but bugs often lurk in the interaction between changed and unchanged code.
- **Check test coverage**: If new logic was added but no tests were added, that's at minimum a warning.
- **Look for what's missing**: The hardest bugs to catch are things that should exist but don't (missing validation, missing error handling, missing DB migration).
- **Consider the PR as a whole**: After reviewing individual groups, consider cross-group interactions. Does Group A's schema change break Group B's usage?
- **Be specific**: "This might have issues" is not helpful. "Line 42: `amount` can be negative but `process_refund()` assumes positive values" is helpful.
- **Verify before publishing**: The synthesis phase exists to catch subagent mistakes. Read the actual code for every critical finding before including it. A false positive in a critical finding destroys reviewer credibility.
- **Check for code-vs-DB prompt drift**: If a PR changes system prompt text, remember the code values are just defaults — deployed environments read from the DB config table. Always flag the need to update prompts in preview (post-merge) and production (post-release).
- **Migrations are for schema, not data fixes**: If a migration file contains large `UPDATE`/`INSERT`/`DELETE` operations that go beyond what the schema change structurally requires, flag it as critical. Data corrections belong in a dedicated data-fix script with dry-run, guardrails, and operator confirmation (see `prod-data-fix-script` skill).
- **Watch for invisible startup side effects**: Seeding default values into the DB during app startup (`on_startup`, `lifespan`, `create_app()`) is an anti-pattern — it runs silently on every deploy, can overwrite intentional changes, and produces stale data. Default data should be managed through explicit migrations or data-fix scripts.
- **Extract long inline workflow scripts**: If a CI workflow step embeds an inline script longer than ~20 lines (e.g., `python3 << 'PYEOF'` heredocs or lengthy `run:` blocks), flag it as a warning. The script should live in `scripts/` and be invoked from the workflow — inline scripts are impossible to lint, test locally, or reuse.
- **Config vs code drift**: If the service has a dedicated configuration mechanism (e.g., agent `append_prompt`, a DB config table, YAML files, feature flags), behaviour that belongs in config must NOT be hardcoded in code. When logic is already expressible via the existing config layer but is instead embedded in Python/TypeScript, flag it as a **warning** — it creates a second source of truth that drifts over time and requires a code deploy to change. Suggest moving the logic to the appropriate config location.
- **Verify modified CI jobs actually ran**: For infra PRs that add, rename, or restructure CI jobs, don't just check that CI is green — check that the *specific jobs being modified* were triggered and executed. "Skipping" on the modified jobs means the changes are completely unverified. This is critical-level: a green CI run where the relevant jobs were skipped gives false confidence. Common cause: the change-detection filter doesn't include the workflow file itself.

## Environment-Specific Behaviour

This skill is used in two environments. Follow the section that matches where you are running.

### In Cursor / Claude Code (local, interactive)

- Use the **`Task` tool** to spawn parallel `generalPurpose` subagents for each logical group
  (Phase 2 parallel review as described in the Subagent Prompt Template above).
- Use **`AskQuestion`** when the intended behaviour is unclear before finalising findings.
- All `gh` commands require **`required_permissions: ["all"]`** (macOS sandbox TLS restriction).

### In auto-agent (server / headless container)

- Run the review **sequentially** in this session — do NOT use the `Task` tool or `AskQuestion`.
- When something is ambiguous, **log the ambiguity** as a note in your findings and proceed with
  best judgment. If blocking clarification is truly needed, use the `request_human_input` MCP tool
  instead of `AskQuestion`.
- No `required_permissions` needed — the container has no macOS sandbox.
- Save the review report to `docs/pr-reviews/pr-<number>-review.md` and post it to the PR.
- **Before reviewing, read the original task file** to understand the intended scope and acceptance criteria. The task file is materialised into the workspace at `docs/tasks/<task-id>.md` by the dispatch pipeline — it is not committed to git, just present on disk:
  ```bash
  ls docs/tasks/
  ```
  Use the task file's **Acceptance Criteria** section as your primary review checklist. Also verify the PR description includes the task **title** and **id** so the change is traceable. If `docs/tasks/` is empty or missing (e.g. the PR was opened manually), fall back to the PR description and diff alone.
- **Verdict rules (strictly enforced)**:
  - **APPROVE** only when there are zero critical findings AND zero warning findings. Nits alone are acceptable.
  - **NEEDS WORK** if there is any critical or warning finding — even a single minor warning like an outdated docstring blocks approval.
  - After posting the review:
    <!-- CUSTOMIZE: Replace the bot command below with your project's review bot trigger.
      If your project doesn't have a review bot, remove the bot invocation line.
      An onboarding agent should check for bot accounts and CI comment triggers in the repo.
      Example: "post `@my-ci-bot approve` as a PR comment" -->
    - If APPROVE: call `submit_task`, then post the review bot approval command as a PR comment.
    - If NEEDS WORK: call `update_checklist` with all findings. Do NOT call `submit_task` or post the bot approval command. The worker must fix all warnings before the reviewer can approve.

## Operational Notes

### Sandbox / Permissions (Cursor / macOS only)

- All `gh` CLI commands require `required_permissions: ["all"]` — the GitHub CLI makes TLS calls that fail under the default macOS sandbox with error: `tls: failed to verify certificate: x509: OSStatus -26276`.
- Subagents run as `readonly: true` which is correct — they should never modify code during review.

### Local Worktree Usage

When a matching worktree is found (Step 1.1), **always use it**:

- **Main agent**: Use the worktree path when verifying subagent findings in Phase 3 (reading cited files/line numbers).
- **Subagents**: Provide absolute file paths rooted at the worktree so subagents can `Read` files directly. This is faster and more reliable than relying on the diff alone.
- **Fallback**: If no worktree exists, subagents can still read files from the main workspace — but they may be on a different branch. In that case, the diff excerpts become the primary source of truth for what changed.

### Subagent Performance Notes

Observations from test runs against real PRs:

- **Include diff excerpts in the prompt.** Without the diff, subagents read full files but don't know *what changed*. They waste time re-reading unchanged code and may miss the actual change. Pasting the relevant diff hunks (even summarized) dramatically improves focus and accuracy.
- **19 files is too many for one subagent.** The docs/infra group with 19 files worked but produced shallow findings (mostly "file X references non-existent file Y"). For large doc groups, consider splitting or reviewing inline.
- **Dependency context helps.** The payout group subagent found the sibling method inconsistency specifically because it was told about the schema changes in the webhook group. Always include dependency notes.
- **Subagents sometimes flag design choices as bugs.** E.g., "partial refund reclaims all credits" was an intentional design choice documented in the PR. The synthesis/verification step should check the PR description before promoting these to critical.
- **Require evidence quotes.** Early subagent prompts without the "quote the actual code" instruction produced findings that were harder to verify. The evidence requirement makes verification fast and catches hallucinated line numbers.
- **Small deltas don't need subagents.** When a follow-up commit is \<= ~200 lines across \<= ~5 files targeting specific review findings, the main agent reviewing inline is faster, cheaper, and produces equally accurate results. Spawning multiple subagents for a small delta adds latency without improving quality.
- **Small PRs don't need groups either.** For PRs under ~200 lines with a single dominant concern, skip formal grouping and review flat — file by file with a single findings table. The group-by-group report structure adds ceremony without improving review quality. Grouping pays off only when a PR spans 2+ unrelated domains with different review checklists.
