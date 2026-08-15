---
name: create-issue
description: "Create a local issue draft in docs/issues/ and register it to Multica (the shared system of record) to capture a problem, bug, feature request, or idea for later triage. Use when the user says 'create issue', 'file an issue', 'log this bug', 'record this problem', or discovers something that needs investigation but doesn't have a fully verified fix approach yet. Also use when the user has a quick thought mid-conversation that should be captured for later."
---

# Create Issue

Capture a problem, bug, feature request, or idea for later triage. Issues are the
"immature" entry point — they describe **what's happening now, why that's wrong, and what
we want instead** — not how to fix it. You write a local **draft** in `docs/issues/`, then
**register it to Multica** (Step 4) — the shared system of record every developer sees; the
local file is only the draft. Later, `/triage-issue` investigates the codebase, evaluates
the three dimensions (requirements · implementation · verification), and routes the work
(see [`docs/process/ctd-pipeline.md`](../../../docs/process/ctd-pipeline.md)).

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

The spine of every issue — bug OR feature, product OR engineering — is a
**behavior triplet**:

1. **Current behavior** — what happens now, observably (for a feature: what's absent).
2. **What's wrong with it** — why the current state is unacceptable (the problem / impact).
3. **Desired behavior** — what *should* happen, as an observable end-state on a named
   real surface. This becomes the issue's `## Desired Behavior` (the keystone triage and
   verification bind to). It is the *what*, not the *how* — no fix approach; the verify
   *procedure* is derived downstream. (A reporter who knows the trigger MAY add an
   optional, non-binding verification-hint — see Step 3b.)

Then capture:

4. **Evidence** — logs, error messages, screenshots, SQL results, timeline.
5. **For a `type: bug` — and for ANY issue citing production evidence — the
   trace-enabling detail** (so a developer can find it fast): **when it happened**
   (timestamp / time window), **where the records/logs live** (which service / table /
   log location / request id), and — for bugs — **reproduction steps**. Citing a prod
   record ("Alice's June 27 session recorded X") without naming where it lives costs the
   triager a hunt; name its home when you cite it.
6. **Impact** — who/what is affected, severity.
7. **Discovery context** — what you were doing when this was found.
8. **Type** — `bug`, `feature`, `exploration`, `tech_debt`, or `docs`.
9. **`reporter_side`** — `product | engineering | both`: which perspective this issue is
   written from. A non-gating **hint** for triage — it tells triage which stakeholder view
   is likely under-represented (a `product` issue under-states the engineering cost /
   trade-offs; an `engineering` issue under-states the product "why it matters"). Not a
   route or a priority; just a lens. Use `both` when the reporter wears both hats.
10. **`need_verify`?** — does this need a passing verify task to auto-close? **Defaults to
    `true`** for any real change (user OR internal). Set `false` only for a genuinely
    trivial item, and then add a `## Why verification is skipped` section (see Step 3b).
11. **Priority** — `urgent | high | medium | low`, set with the **concrete bar in
    [`docs/process/priority-rubric.md`](../../../docs/process/priority-rubric.md)**, not by reflex
    (the default is `medium`, and reflex-defaulting is exactly the inflation drift the backlog sweep
    keeps having to clean up). In short: **urgent** = live prod harm, **business bleed** (materially
    losing money / existing users / new-user capture), **or** blocked release / `main` red /
    dramatically-slowed engineering — *right now* · **high** = real bug users hit / near-term
    committed work · **medium** = real-but-bounded · **low** = cosmetic/nice-to-have. The issue body
    often self-rates; feature ≠ bug (size by demand). See the rubric for the full bar. (Propose it —
    confirmed in the Propose→Confirm Flow.)

**Keep it behavior-focused and lightweight.** Non-goals, invariants, rejected
alternatives, and open design decisions are **not** the reporter's job at creation —
triage elicits them (and, when contested, records them in a `decisions.md`). If the user
gives a one-liner, that's fine. Don't over-interview. The goal is to capture enough for
someone to pick it up later.

Do not infer policy from convenient code or configuration. Credits, pricing, trials,
entitlements, tiers, cohorts, backfills, partner access, and user-facing promises require
explicit confirmation or a verified policy source. Otherwise stop before implementation.

### Step 2: Check for Duplicates

Multica is the shared system of record — another developer may have already filed this, so
check **there first**, not just local files. Use the workspace-scoped search endpoint
(`GET /api/issues/search` — full-text over title / description / comments):

```bash
# URL + key from .env.development (dev) or .env (prod)
source <(grep -E "^MULTICA_API_URL=|^MULTICA_API_KEY=" .env.development | sed 's/^/export /')
curl -s -H "Authorization: Bearer $MULTICA_API_KEY" \
  "$MULTICA_API_URL/api/issues/search?q=<key+terms>&workspace_slug=soundingboard" | python3 -m json.tool
```

- `q` is required — use the distinctive nouns / error text, not a whole sentence.
- Add `&include_closed=true` to also catch an **already-fixed** issue.

Then scan local drafts not yet registered, and open tasks:

```bash
ls docs/issues/ 2>/dev/null   # local drafts on this machine
ls docs/tasks/ 2>/dev/null    # a task may already cover it
```

If a strong match exists, tell the user and suggest updating that issue instead of creating
a new one.

### Step 3: Create the File

Save to: `docs/issues/YYYY-MM-DD-<slug>.md`

The file goes in `docs/issues/` which symlinks to `.shared-issues/` at the repo
root. Like task files, issue files are gitignored and local-only, shared across
worktrees.

**In a worktree:** Always write to the **main repo's** `docs/issues/` path (e.g.,
`/home/jun/SoundingBoard/docs/issues/`), NOT the worktree's path. Resolve the
real path first if unsure: `readlink -f docs/issues/ || echo docs/issues/`

**NEVER use `git add -f` on issue files.** They are local-only, like task files.

Fill the **Template** (§ Template, at the end) — its inline comments carry each field's
required?/who-writes-it. Judge the depth: a **quick capture** (a one-liner / side-discovery)
fills just `title` + `## Desired Behavior`; a **detailed issue** (evidence / impact) fills
the rest. Same frontmatter either way — field values + meanings live in the Classification
sections below.

### Step 3b: Desired-Behavior Gate

Before finalizing the issue, enforce these checks:

1. **Set `need_verify`** — per "`need_verify` Classification" below: default `true`;
   `false` only for a genuinely trivial / no-behavior-change item, and then with its
   `## Why verification is skipped` section.

2. **If the issue changes any behavior (user OR internal): require `## Desired
   Behavior`.** The issue body MUST include a `## Desired Behavior` section with
   observable-behavior-altitude items on a named real surface. If the user hasn't
   provided one, draft it and ask for confirmation. Refuse to finalize a
   behavior-bearing issue without it. (Only a truly trivial / no-behavior-change item —
   a rename, a docs typo — is exempt; those rarely need an issue at all.)

3. **Altitude check** — if the `## Desired Behavior` items are code-level (satisfiable
   by a unit test), flag and rewrite to observable-behavior altitude (see
   "`## Desired Behavior` Section" below).

4. **Tension check — read the items as a SET, not one by one.** When one item promises a
   *capability* ("detects the page path automatically") and another constrains the *means*
   ("without an embed-code change" / no config / no migration / no downtime), that pair may
   be jointly unsatisfiable — the reporter doesn't have to know (feasibility is triage's
   job), but **don't let both stand as unqualified promises**: note the pair in `## Notes`
   as a question for triage ("path detection and no-embed-change may conflict — which gives?").
   The syntactic cue is enough: a fidelity/coverage promise + a no-change constraint in the
   same list is always worth the one-line flag. (Real miss this prevents: SOU-747 promised
   page-path detection AND zero embed change — likely incompatible under default browser
   referrer policies — and both shipped unqualified.)

5. **Precision check — no policy hiding in a single word.** If an item uses a
   merge/precedence/fallback verb (*supplements, overrides, replaces, falls back, takes
   priority*) or an open-ended boundary phrase (*"sensitive data", "as appropriate",
   "where relevant"*), either state the actual order/boundary in the item, or mark it
   explicitly **`(precedence TBD — triage)`** / **`(boundary TBD — triage)`**. The keystone
   is frozen at creation and downstream binds to it — a vague verb is where an implementer
   later picks the policy silently. (SOU-747: "supplements … instead of replacing" left the
   auto-detected vs `via` vs UTM precedence unstated; "other potentially sensitive URL
   data" left the PII boundary undefined.)

The issue holds `## Desired Behavior` (the keystone); the verify *procedure* (tests,
localhost, dev/prod checks) still moves downstream to the task / verification plan (the
How-first verification framework). BUT a reporter who **knows the trigger** MAY add an
optional, **non-binding verification-hint** (in `## Notes`: the trigger, the surface to
watch) that seeds the downstream procedure — PMs leave it empty; when absent, triage
derives the procedure from Desired Behavior, and triage may override the hint. The guard's
purpose is unchanged: the **implementer** still never defines verification to fit their
code. See [`ctd-pipeline.md`](../../../docs/process/ctd-pipeline.md) §"The keystone".

Do NOT skip this step.

### Step 4: Register (or update) in Multica

After the file is written, register the issue in Multica so it appears in the
web UI alongside tasks.

```bash
uv run scripts/create-issue.py docs/issues/<file>.md --env <env>
```

- Default `--env` is `development`; pass `local` for `http://localhost:8090`
  or `production` for the production backend.
- The script reads the frontmatter. If the file is not yet registered, it
  creates the issue via `POST /api/issues` with the `X-Workspace-Slug` header and
  writes `multica_issue_id` back into the file's frontmatter.
- Auth uses `MULTICA_API_KEY` from `.env.<env>` (same credential handling as
  `create-task.py`).
- Re-running is safe and is how you push edits: if the file already has a
  `multica_issue_id`, the local file is treated as the source of truth and its
  contents are pushed to Multica via `PUT /api/issues/{id}` (title, body, status,
  priority). So the workflow for updating an issue is: edit the local `.md`, then
  re-run the same command. Pass `--no-update` to skip the push and just print the
  link.
- **Registered file ⇒ targeted edits only (Edit), never a full-file rewrite (Write).**
  After registration, `multica_issue_id` / `multica_issue_identifier` live in the issue
  file's frontmatter; a full-file rewrite silently drops them — the next re-run then
  registers a **duplicate** issue instead of updating the existing one. Always edit a
  registered issue file with targeted edits.

Skip this step only when Multica is intentionally unavailable (e.g. fully offline
work) — note to the user that the issue exists only as a file until registered.

### Step 5: Confirm

Show the user:
- File path created
- Issue title and type
- Multica identifier (e.g. `SOU-87`) if registered
- Suggest: "Run `/triage-issue <id>` when you're ready to investigate and route it."

## Classification (propose → confirm)

When creating an issue, the agent **proposes** the classification fields — `area`, `type`,
`reporter_side`, and `priority` — from the issue content, then **confirms** with the user
before saving (`need_verify` has its own section below). This is the "capture is a
byproduct" invariant — classification happens at creation, not as a separate step. (`area`
and `type` feed F1 velocity rollups.)

### What each value means

**Type** — what *kind* of work it is:

- `bug` — something is broken / behaves differently from intended.
- `feature` — a new capability or enhancement that doesn't exist yet.
- `tech_debt` — internal quality (refactor, restructuring, DX, test debt) with **no new
  user-observable behavior**.
- `exploration` — an open question / spike / investigation with **no committed fix yet**
  ("figure out X", "why does Y happen").
- `docs` — a documentation-only change.

**Area** — which product domain (F1 velocity rollups group by this). Pick the *primary*
surface; if it genuinely crosses domains or is unclear, leave it empty (see When to Skip):

- `voice-call` — voice agent / call flow (ConvAI, voice-gateway, Twilio voice).
- `sms` — SMS agent, messaging, triggers.
- `memory` — user/session memory & coaching context.
- `enterprise` — B2B: orgs, partners, multi-seat, admin.
- `individual` — B2C: the individual-consumer counterpart to `enterprise`.
- `payment` — billing, Stripe, credits, subscriptions.
- `auto-agent` — the Multica / auto-agent / SoundingBot dev-automation platform itself.
- `mentor-onboarding` — mentor curation, onboarding, self-serve preview.
- `observability` — monitoring, Sentry, logging, metrics, alerting.

(These area definitions are the working set — the F1 design doc only *enumerates* the
domains; if the team formalizes them elsewhere, point there instead of duplicating.)

Two adjacent fields are **not** decided here:

- `out_of_plan_kind` defaults to `planned` and is only set to a non-`planned` value
  (`follow_up` / `bug_fix` / `out_of_scope` / `rework`) when work is added **after** a
  parent issue's baseline freeze — see `/triage-issue` §"out_of_plan_kind (F1)". `create-issue`
  does not set it.
- `labels` are free-form workspace labels (name + colour) applied ad hoc in the UI; there
  is no fixed taxonomy and the create flow leaves them empty. Don't invent labels at creation.

### Propose→Confirm Flow

1. After gathering context (Step 1), propose all four — **area** and **type** (values +
   meanings above), **`reporter_side`** (Step 1 item 9), and **priority** (the
   [`priority-rubric.md`](../../../docs/process/priority-rubric.md) bar — no reflex-default
   to `medium`; see Step 1 item 11).

2. Present the proposal to the user:
   > "I'd classify this as area=`auto-agent`, type=`bug`, reporter_side=`engineering`,
   > priority=`medium`. Confirm or override?"

3. Write the confirmed values into the frontmatter:

   ```yaml
   type: bug
   area: auto-agent
   reporter_side: engineering
   priority: medium
   ```

4. The `scripts/create-issue.py` script **always sends `status` and `priority`** — an
   unset `priority` defaults to `medium`, which is exactly why an un-chosen priority
   silently inflates the backlog — and sends `area`, `type`, `need_verify`, and
   `project_id` when present in the frontmatter. `reporter_side` is sent inside the
   issue's **`triage` JSONB** (`triage: {"reporter_side": ...}`, TASK-965) — triage later
   merges its verdicts into the same object via `get-issue.py --triage`.

### When to Skip

- **Quick captures** (mid-conversation side-discoveries): skip if the user is in a hurry.
  The issue will be classified later by the backfill script or during triage.
- **Uncertain classification**: if the issue crosses domains or the type is unclear, leave
  fields empty and note "needs classification" in the issue body.

## `need_verify` Classification

Every issue carries **`need_verify`** — does it need a passing verify task before it can
auto-close? **It defaults to `true`.** This is the single input to the backend closure gate
(it replaces the old `user_facing` field, which conflated "user-observable" with "must be
verified"). Verification *depth* is decided separately, by the How-first framework — see
[`ctd-pipeline.md`](../../../docs/process/ctd-pipeline.md).

### The rule

- **`need_verify: true` (the default)** — any change that alters behavior, **user OR
  internal**. The issue can't auto-close until an independent verify task passes. You don't
  set this explicitly; it's the default for every real change.
- **`need_verify: false`** — a genuinely **trivial / no-behavior-change** item (a rename, a
  docs typo, a pure refactor the regression suite already covers). Only then does the issue
  auto-close with no verify task. **Skipping is a deliberate, recorded choice:** when you set
  `need_verify: false`, the issue body MUST include a **`## Why verification is skipped`**
  section stating why it's trivial. No bare `false` — "looks fine" with no reason is exactly
  the SOU-217 (shipped-green-but-broken) failure the gate exists to stop.

### Propose→Confirm Flow

1. Default to `need_verify: true`. Propose `false` **only** if the change is genuinely
   trivial (no behavior change).
2. If proposing `false`, present the reason and draft the `## Why verification is skipped`
   section:
   > "This looks trivial (a docs typo — no behavior change), so I'd set `need_verify: false`
   > with a `## Why verification is skipped` section. Confirm or override?"
3. Write the frontmatter — leave the default, or set it explicitly when skipping:

   ```yaml
   need_verify: false   # ONLY for a trivial change — requires a ## Why verification is skipped section
   ```

The `scripts/create-issue.py` script sends `need_verify` to Multica when present (the
backend defaults it to `true`).

### The default is verify

There is no "skip because it's internal" — an internal behavior change is verified too.
The **only** exemption is `need_verify: false` for a genuinely trivial change, and it must
carry its `## Why verification is skipped` justification.

## `## Desired Behavior` Section (the keystone)

Every **behavior-bearing** issue MUST have a `## Desired Behavior` section. This freezes
the WHAT at creation — the observable end-state on a named real surface that constitutes
"this problem is gone" / "this feature works." It is the anchor triage, `/verify-coverage`,
and the verification plan all bind to. The *how to verify* (the procedure) is derived
downstream — at most an optional, non-binding reporter verification-hint seeds it
(see Step 3b); it is never binding here.

### Requirement

- **Behavior-bearing issues** (any user OR internal behavior change): a `## Desired
  Behavior` section is **mandatory**. Refuse to finalize the issue without one (the gate
  in Step 3b enforces this).
- **Trivial / no-behavior-change**: exempt — exactly the `need_verify: false` case (see
  "`need_verify` Classification"); those rarely warrant an issue at all.

### What Makes a Valid `## Desired Behavior`

Each entry must describe **observable behavior on a named real surface** — one line
per entry path. It answers: "What does the user/caller observe, on the real thing, once
this is resolved?"

**Valid examples:**
```markdown
## Desired Behavior

- On the real GitHub PR, the assignee field shows the issue owner's GitHub username
  (not empty, not a bot).
- On the Multica board, the issue card shows status "done" after the verify task passes.
- Calling `POST /api/issues/{id}` with a verify verdict returns 200 and the issue
  status transitions to done.
- (tech_debt/architecture, where the target surface doesn't exist yet — state the
  INVARIANT on surfaces that do:) On any dispatched journey task, no agent that edited
  adapter/spec code belongs to a task graded on the suite being green — however the
  crew is composed.
```

**Invalid (code-level — satisfiable by a unit test):**
```markdown
## Desired Behavior

- The `assignPrOwner()` function returns the correct username when given a valid email.
- The `DeriveExecutionStatus` function returns "done" when all verify tasks pass.
- The test `test_assign_pr_owner` passes.
```

### Altitude Check: Reject Code-Level AND Mechanism-Prescribing Items

The check is **two-sided** — an item can be mis-phrased in either direction.

**Too low (code-level).** If a `## Desired Behavior` item could be satisfied by a green
unit test on a synthetic/pre-resolved payload, it is **mis-phrased** and must be
rewritten. Flag it:

> "This desired-behavior item is code-level (satisfiable by a unit test). It needs to
> be rewritten to observable-behavior altitude — what does the user/caller see on
> the real surface?
>
> **Current (code-level):** 'The `assignPrOwner()` function returns the correct username'
> **Rewritten (observable):** 'On the real GitHub PR page, the assignee field shows
> the issue owner's GitHub username'
>
> Please confirm the rewrite or provide your own."

**Mechanism-prescribing (a HOW smuggled into the WHAT).** If an item names a **new
mechanism** — a new agent, flag, table, component, field — *as* the observable, it is a
fix approach dressed as behavior. It is concrete and real-surface, so the code-level
check passes it — but it freezes ONE embodiment of the intent, and triage and design
inherit the frame instead of examining it. The tell: **would a different mechanism
satisfying the same principle be acceptable to the reporter?** If yes — or you can't
tell — restate the item as the intent/invariant the mechanism must uphold. Flag it:

> "This desired-behavior item prescribes a mechanism (a new <agent/flag/component>)
> rather than the intent. What must be true regardless of which mechanism we choose?
>
> **Current (mechanism):** 'the run-late task's crew shows a dedicated journey-author
> agent id'
> **Rewritten (intent):** 'no agent that wires journey verbs is graded on the suite
> being green'
>
> Please confirm the rewrite or provide your own."

(Real cost of skipping this: SOU-802's capture encoded "add a journey-author agent to
the run-late crew"; the intent was "crew composition is selected by task type" — the
frame survived capture AND triage, and a full technical design was drafted before the
product owner caught it.) When the intended surface doesn't exist yet
(tech_debt/architecture), don't invent a mechanism to have something to point at —
write the observable as an invariant over existing surfaces (the last valid example
above).

Neither direction has a **size-based exemption** — a one-line fix still requires a
behavior-altitude desired-behavior statement.

### The `## Demo` sub-block (the human-facing spine — prompted, optional)

Under `## Desired Behavior`, add a `## Demo` sub-block: **the ONE concrete happy-path a human
could watch to see this work** — a short narrative, not a test. It is the human-readable ANCHOR
that the verification plan's ★ proving test and `/verify-capability`'s manual stage are the
executable forms *of* (one source, three renderings — NOT a third parallel spec). It also matches
`/epic-planning`, which decomposes an epic by defining each child as one **demoable** capability;
the `## Demo` block is that idea at the single-issue level.

**Prompt for it, but it's OPTIONAL with a fallback** — never force contrived theater:

- **Demoable (user-facing / observable flow):** write the watch-this scenario.
  ```markdown
  ## Demo
  Open the issues list → click Export → a CSV of the current filtered rows downloads and opens
  with the visible columns.
  ```
- **Not visually demoable (a log line, a refactor, an infra fence, an invariant):** degrade to
  **the observable signal** — the concrete thing that shows it worked.
  ```markdown
  ## Demo (observable signal)
  Trigger a stale-SHA condition on the daemon with SLACK_WEBHOOK unset → a WARNING line
  "Stale SHA detected …" appears in the daemon log (previously silent).
  ```

Ask: *"If a human were to watch this work, what's the one scenario they'd see? If it's not
visually demoable, what's the observable signal that proves it?"* If the reporter can't give one
and the work is genuinely non-demoable, it's fine to omit — do NOT block issue creation on it.
Downstream (`/create-requirements` → `/verification-plan` → `/verify-capability`) reads this block
as the anchor: the ★ proving test SHOULD equal the demo, and the human watches the demo at close.

### When to Write It

Author the `## Desired Behavior` section **during issue creation** (Step 3). If the
user provides enough context, draft it for them and present for confirmation. If not,
ask:

> "What observable behavior on what real surface tells us this is resolved? (e.g. 'On the
> board, the issue shows status X' or 'The API returns Y')"

## Status Lifecycle

```
open → triaged → closed
         │
         └── related_tasks field links to the task file(s) created
```

- **open** — captured, not yet investigated
- **triaged** — investigated + routed via `/triage-issue`, task file(s) created
- **closed** — resolved (task completed), duplicate, or not actionable

## Template

Copy into `docs/issues/YYYY-MM-DD-<slug>.md`. **Quick capture** fills `title` +
`## Desired Behavior` only; **detailed** fills the rest. Frontmatter is the same either way;
values + meanings live in the Classification sections above. (Routing verdicts
`requirements`/`impl`/`verify` are added by `/triage-issue`, not here.)

```markdown
---
id: YYYY-MM-DD-<slug>          # required — must match the filename (without .md)
title: "<Short description>"    # required
created: YYYY-MM-DDTHH:MM       # required — ISO datetime; the agent sets it
status: open                    # required — open | triaged | closed (see Status Lifecycle)
priority: medium                # required — urgent | high | medium | low (see Classification)
type: bug                       # required — bug | feature | exploration | tech_debt | docs
area: auto-agent                # optional — one of 9 F1 domains (see Classification)
reporter_side: engineering      # optional — product | engineering | both (see Classification)
need_verify: true               # required — defaults true; false only for a trivial change (see need_verify Classification)
related_issues: []              # optional — related issue ids
related_tasks: []               # optional — usually empty at creation (triage adds tasks)
github_issue: ""                # optional — URL, only if a GitHub issue was also created
multica_issue_id: ""            # LEAVE EMPTY — create-issue.py writes it back on registration
multica_issue_identifier: ""    # LEAVE EMPTY — create-issue.py writes it back (SOU-###)
---

# <Title>

<!-- Quick capture: a 1-3 sentence current → wrong → desired is enough, then just the
     Desired Behavior section. Skip the rest. -->

## Current Behavior       <!-- optional -->

<What the system does today, observably. For a feature: what is absent / the gap.>

## What's Wrong           <!-- optional -->

<Why the current state is unacceptable — the problem, the impact.>

## Desired Behavior       <!-- REQUIRED for any behavior-bearing issue -->

- <What *should* happen — observable end-state on a named real surface, one line per entry
  path. The keystone triage + verification bind to. The WHAT, not the HOW.>

## Evidence               <!-- optional -->

<Logs, errors, screenshots, SQL, timeline. For a bug: WHEN (timestamp), WHERE the logs live
(service / location / request id), and REPRODUCTION steps.>

## Impact                 <!-- optional -->

<Who is affected? How severe? Is this blocking something?>

## Discovery Context      <!-- optional -->

<What were you doing when this was found? Link the conversation, PR, or task.>

## Notes                  <!-- optional -->

<Initial thoughts / pointers for triage. No fix approach unless verified — "possible
direction" at most. If you know the trigger, an optional NON-BINDING verification-hint
(how you'd observe the fix, on what surface) is welcome — it seeds the downstream
procedure; triage may override it. PMs leave it out.>

## Why verification is skipped   <!-- ONLY if need_verify: false — why it's trivial -->

<Why this change is genuinely trivial / no behavior change, so it needs no verify task.>
```