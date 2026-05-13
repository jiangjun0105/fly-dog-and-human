<!-- Grouped review template — use for PRs with 2+ distinct logical groups.
     For small/focused PRs, use review-template-flat.md instead. -->

# PR Review: #<number> — <title>

**Date**: YYYY-MM-DD
**Author**: <author>
**Reviewer**: AI PR Review
**Base**: `<base_branch>` ← `<head_branch>`
**Stats**: +<additions> / -<deletions> across \<changed_files> files
**PR Type**: \<feature|bugfix|refactor|docs|infra|mixed>

______________________________________________________________________

## CI Status

| Check        | Status                         |
| ------------ | ------------------------------ |
| [Check name] | ✅ pass / ❌ fail / ⏳ pending |

**CI Summary**: All checks pass / X of Y checks failing

> ⚠️ **CI Failures** (if any):
>
> - \[Check name\]: [Brief description of failure]

______________________________________________________________________

## Critical / Blocking Issues

> If none, write: "No critical issues found."
>
> Every critical finding below has been **verified by reading the actual source code** — not just taken from subagent output.

| #   | Severity | File   | Line(s) | Finding       | Suggestion |
| --- | -------- | ------ | ------- | ------------- | ---------- |
| 1   | critical | [path] | [lines] | [description] | [fix]      |

______________________________________________________________________

## Review by Group

### Group 1: \<group_name>

**Files**: `<file1>`, `<file2>`, ...
**Type**: \<feature|bugfix|refactor|docs|infra>
**Verdict**: APPROVE / NEEDS WORK

| #   | Severity | File   | Line(s) | Finding       | Suggestion |
| --- | -------- | ------ | ------- | ------------- | ---------- |
| 1   | warning  | [path] | [lines] | [description] | [fix]      |
| 2   | nit      | [path] | [lines] | [description] | [fix]      |

**Summary**: [1-2 sentences on this group's quality]

______________________________________________________________________

### Group 2: \<group_name>

**Files**: `<file1>`, `<file2>`, ...
**Type**: \<feature|bugfix|refactor|docs|infra>
**Verdict**: APPROVE / NEEDS WORK

| #   | Severity | File   | Line(s) | Finding       | Suggestion |
| --- | -------- | ------ | ------- | ------------- | ---------- |
| 1   | warning  | [path] | [lines] | [description] | [fix]      |

**Summary**: [1-2 sentences on this group's quality]

______________________________________________________________________

<!-- Repeat for additional groups as needed -->

## Cross-Group Concerns

> Issues that span multiple groups or emerge from their interaction. If none, write: "No cross-group concerns identified."

| #   | Severity | Groups Involved | Finding       | Suggestion |
| --- | -------- | --------------- | ------------- | ---------- |
| 1   | [level]  | [Group A, B]    | [description] | [fix]      |

______________________________________________________________________

## Test Quality

> Summarize test quality findings. If tests were not part of this PR's changes, write: "No test changes to review."

- **Coverage**: [Are all acceptance criteria covered by tests?]
- **Integration tests**: [Present for DB/API features? Markers used?]
- **Anti-patterns**: [Any test anti-patterns detected?]
- **Mock usage**: [Appropriate? Internal services not mocked?]
- **Assertion depth**: [Business outcomes asserted, not just transport success?]

______________________________________________________________________

## Verification

> Findings from subagent reviews are verified by the main agent before inclusion.

| Metric                                  | Value |
| --------------------------------------- | ----- |
| Subagent findings received              | X     |
| Verified and included                   | X     |
| Downgraded (severity reduced)           | X     |
| Dropped (false positive / not verified) | X     |

______________________________________________________________________

## Summary

| Metric          | Value                      |
| --------------- | -------------------------- |
| Groups reviewed | X                          |
| Critical issues | X                          |
| Warnings        | X                          |
| Nits            | X                          |
| CI status       | ✅ all pass / ❌ X failing |

<!-- CUSTOMIZE: Replace the bot name below with your project's CI bot or review automation
     name. If no bot parses this verdict, you can simplify to just describe the format convention.
     An onboarding agent should check for GitHub Actions or bots that parse PR comments.
     Example: "MACHINE-PARSED by my-ci-bot." -->
<!-- ⚠️ MACHINE-PARSED by CI/bot integrations. Use "## Verdict: APPROVE" or "## Verdict: NEEDS WORK".
     Do NOT insert emoji shortcodes (:white_check_mark:, :x:) — they break the regex.
     Unicode emoji (✅/❌) are OK but optional. -->

## Verdict: APPROVE / NEEDS WORK

[1-3 sentence summary explaining the verdict. Reference the most important findings.]

______________________________________________________________________

## Post-Merge Action Items

> Required follow-up actions after the PR is merged. If none, omit this section entirely.

### System Prompt DB Updates

> Include this subsection only if the PR modifies agent system prompt content.

The following system prompts were changed in code. Since deployed environments read prompts from the **DB config table** (not code defaults), these must be manually updated:

| DB Config Key  | Action                                           | Status                     |
| -------------- | ------------------------------------------------ | -------------------------- |
| `<config_key>` | Update prompt text to match the new code version | ⬜ Staging / ⬜ Production |

<!-- CUSTOMIZE: Replace these instructions with your project's process for updating
  deployed configuration after merge. This could be an admin dashboard, a CLI tool,
  a config-management API, a deployment script, a GitOps config repo, or a DB migration —
  whatever mechanism your project uses to manage runtime configuration in staging/production.
  An onboarding agent should check for:
  - Config management tools (dashboards, CLI utilities, deployment scripts, GitOps repos)
  - Environment-specific update procedures (staging vs. production)
  - Runtime configuration stores (DB tables, config services, key-value stores, config files)
  Example: "Update the prompt using: `./scripts/update-config.sh --env staging --key <key>`" -->
**Steps:**

1. **After merge → update staging**: Update the key(s) above in the staging environment's configuration store to match the new code. Verify the new version is active.
1. **After release → update production**: Update the key(s) above in the production environment's configuration store to match the new code. Verify the new version is active.

> ⚠️ **If the DB is not updated, the code change will have no effect in deployed environments.**

______________________________________________________________________

## Blocking Issues (if NEEDS WORK)

> Must be resolved before merge:

1. [Issue description with file:line reference]
1. [Issue description with suggested fix]
