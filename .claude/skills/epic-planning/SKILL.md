---
name: epic-planning
description: Decompose an epic (an issue too big to be one closeable capability) into child issues sliced BY VALUE — walking-skeleton first, then thicken (skateboard → bicycle → car), never by component/layer, so every slice is usable and you can stop when it's enough. Creates the parent epic + the child issues linked by parent_id. Invoked by /triage-issue's "epic — decompose first" exit, or when a human plans top-down (project → epic → issues). Multica-specific; uses the REST API directly. Does NOT build tasks — each child re-enters /triage-issue individually.
---

# Epic Planning (Multica)

Turn an **epic** — an issue that is really several closeable capabilities — into a parent epic + a set
of **child issues**, each of which is *one closeable capability with one demo*. This is the skill the
`epic — decompose first` triage exit routes to (canon: `docs/process/ctd-pipeline.md` §"The size
ladder: Task · Issue · Epic").

> **The per-child demo IS the single-issue `## Demo` block.** Each child's "one demo" is the same
> artifact create-issue captures as the `## Demo` sub-block under Desired Behavior — write it there
> when you author the child, so the demo threads through the child's own CTD pipeline
> (create-requirements → verification-plan's ★ proving test → verify-capability's happy-path watch).
> Epic-level "slice by demoable value" and issue-level `## Demo` are the same idea at two altitudes.

**What this skill does:** decompose → create the parent epic (`is_epic`) → create the child issues
(linked by `parent_id`) → hand each child to `/triage-issue`. **What it does NOT do:** author tasks,
build a pipeline, or execute anything. An epic is a **container, never executed**; only its leaf child
issues enter the build pipeline, one at a time.

> **Status (2026-08-10):** the `is_epic` column and a board-UI for epics are **planned, not yet built**
> (see ctd-pipeline.md). Until `is_epic` ships, an epic is detected by **`has_children`** — this skill
> still links children via `parent_id`, and marks the parent as an epic in its body + (when the column
> lands) sets `is_epic=true`. The `--epic`/`--parent` flags on `create-issue.py` are **planned** too;
> until they exist, create children with `create-issue.py` then set `parent_id` via the REST API
> (below). This skill's *procedure* is canonical now; two mechanics are stubbed on planned work.

## When to use

- `/triage-issue` returned the **epic — decompose first** exit.
- A human is planning **top-down**: a project → an epic → its issues, before any work exists.
- You have several already-created issues and realize they belong under one epic (regroup — the easy
  path: just set `parent_id`).
- NOT for: a single closeable capability (that's a normal issue → `/triage-issue`), or slicing an issue
  into *tasks* (that's `/task-planning` — tasks live under a leaf issue, never as child issues).

## The unit test — is this actually an epic?

Decompose only if the input trips the **epic test** (any one):

- **Multiple independently-demoable capabilities** — two-plus things that can *each* ship + be demoed
  on their own ("a start button **and** a chat sidebar **and** the gate flow" — each demoable alone).
  Each is a candidate child issue. **But not every "and" counts:** two things that must ship together to
  demo anything (e.g. a DB column *and* the CLI flag that depends on it) are **one** capability, not two
  — litmus: *can each half close + demo alone, with the other absent?* If no, it's one issue.
- **Spans >1 deploy target** — e.g. a backend service + a separate daemon + the frontend.
- **Would decompose into >~10 tasks.**

If none trip, it is **one issue** — stop, route it back to `/triage-issue`, do not create an epic.
A healthy child issue is **one capability, one demo, ~3–9 tasks, ideally ≤1 primary deploy target.**

## Step 1 — decompose by VALUE, walking-skeleton first (the judgment)

**THE GOVERNING PRINCIPLE: cut issues by the value they deliver, so every slice is something usable —
skateboard → bicycle → motorcycle → car, never chassis → wheels → engine.** Do NOT split by component
or layer ("the auth module", "the sidebar", "the engine"). Split so that **the first child is the
thinnest COMPLETE vertical that delivers the core value** — a walking skeleton the user can actually
use, even if it's ugly/unfancy — and each later child **thickens** that into more value. The car analogy
is exact: build a skateboard first (they can move *today*), then upgrade to a bike, a motorcycle, a car —
never build a chassis, then wheels, then a steering wheel (nothing is usable until the last piece).

Why this is the right cut (it serves three goals at once):

1. **Value early, and you can STOP early.** After each child, the user sees value increase — and they
   may be satisfied at the bicycle and never need the car. A value-slice epic lets you *stop when it's
   enough*; a component-slice epic delivers nothing until the last component. (For infra with no user
   scenario, "value" = business value — pick the low-hanging fruit that unlocks the most, build on it.)
2. **Integration bugs surface immediately, isolated.** A thin end-to-end slice exercises *every* seam
   (button → API → daemon → result → UI) at slice 1 — so integration bugs discharge at the first
   checkpoint, not piled onto a final demo. Component/layer-first *defers* integration until the layers
   stack, which is exactly how the flat SOU-928 got ~16 bug-fixes discovered serially at the end.
3. **Each slice is a real-path verification checkpoint.** The demo sentence for a value slice ("click
   the button → a round runs → you read its recommendation") is inherently a *whole-vertical* real-path
   check — you can't fake it with a layer test.

**How to cut:** list the **value scenarios** — "a user/operator does X end-to-end and gets value Y" —
ordered by *value delivered soonest*, not by component dependency. The **first** child is the walking
skeleton (thinnest complete path to core value; explicitly allowed to be skeletal — real seams, minimal
behavior). Each subsequent child is an independently-usable increment that thickens it. The demo sentence
IS that slice's checkpoint; estimate tasks (1 task ≈ 1 point).

**Worked example (a crew-round-style feature, value-sliced):** ① **skateboard** — "click the button on
the issue page → a round runs → you read its recommendation" (ugly sidebar, no gate, no polish, but a
complete usable vertical: automated triage without leaving the page); ② **bicycle** — "answer a gate →
the round acts on your answer" (human-in-the-loop value); ③ **motorcycle/car** — rich transcript,
polish, edge cases. Contrast the WRONG (component) cut — "the round engine (API-only, no UI)" delivers
*nothing usable* and defers every integration bug to when the UI stacks on top.

**Guardrails:**
- **Infra with no user scenario → don't force a scenario; fold it into the FIRST value slice that needs
  it** (the skeleton). Only carve it out as its own child when it passes **both** enabler gates below
  (≥2 consumers AND a standalone checkpoint) — a cross-cutting substrate provable only by running a
  value slice through it stays folded, even when many children touch it. Its "value" is business value —
  the low-hanging fruit that unlocks the most. (E.g. a provider abstraction folds into the first
  provider scenario that proves it — Kimi — not its own layer.)
- **The skeleton is THIN, not DISPOSABLE.** Build it to be *extended* (real seams, minimal behavior),
  not thrown away. If a later slice has to *rewrite* the skeleton rather than *thicken* it, you cut the
  seam wrong — re-cut. "Thicken ≠ rework" is the litmus.
- **Each slice's checkpoint must be a REAL-path gate** — scripted model OK, but real FE + real backend +
  real transport, never a scripted-adapter journey or a deferred `needs-human` demo (see
  `/verification-plan` §"Costly component ≠ defer the whole real path"). Value slices whose checkpoints
  all defer to one final human demo re-create the very problem. Slice by value **and** gate each slice.

**The bar for a good child issue:** independently demoable, independently verifiable, independently
closeable. If two "capabilities" can only be demoed together, they're one issue. If one "capability"
has two unrelated demos, it's two issues.

Litmus per child: *can this close and ship on its own, while its siblings are still open?* If no,
re-cut the seam.

**Right-size each child on THREE axes — don't over-split (canon: `ctd-pipeline.md` §"Right-sizing has a
FLOOR too").** "Independently demoable" *opens* a split; these three decide whether to *take* it:

1. **Size floor.** A healthy child is **~3–9 tasks**. **Below ~3 (mirrors an existing pattern, no seam
   of its own) → fold it**, don't file a sliver. More children = more connecting parts + same-file
   collisions for no isolation gain.
2. **Seam-sharing → merge.** Two candidate children that touch the **same files + same verify harness**
   are usually **one child with N tasks**, even if each demos alone. Litmus: *same 2–3 files, same
   abstraction re-established?* → merge. (Prefer: prove the shared abstraction with the **trivial**
   instance folded in, not one child per instance.)
3. **Certainty → split the spike out (overrides #2).** Do NOT merge a *certain* capability with an
   *uncertain* one (unknown auth/integration, `impl: design`, investigate-first) — even if they share a
   seam. The uncertain half holds the certain half hostage. Keep the spike its own child; fold the
   trivial/certain instance into the abstraction that proves the seam.

Then **place spikes off the critical path**: if a downstream child needs *N of something* and the
certain children already supply *N*, point its `depends_on` at those — not at the uncertain child — so
the spike blocks nothing. (Worked example — the multi-provider epic SOU-1102: Kimi (trivial) folded into
the provider-abstraction child as its proving provider; Codex (uncertain auth) kept a separate spike
child; per-agent routing depends on the abstraction-only, since Claude+Kimi = the 2 providers it needs.
Started as 5 children, right-sized to 3.)

**Shared enabler — a legitimate child even without a user demo.** Some epics have a piece that isn't a
user-demoable capability but that **multiple other children depend on** — a test-harness bypass, a
shared migration, a common client/SDK, a scaffolding endpoint. When exactly one child needs it, **fold
it in** (it's part of that capability — same as the "DB column + the flag that needs it = one capability"
rule). But when **one enabler blocks two-plus children**, it *may* be its **own child issue** — a spine
node — and if so it is **exempt from the user-demoable bar**: `verifiable + closeable` is enough (its
"demo" is "the thing it unblocks can now be built/tested"). Do NOT reject it as "not a real capability,"
and do NOT duplicate it into each consumer (that couples them + rebuilds it N times). Make it one child,
mark the consumers `depends_on` it.

**Two gates, BOTH required, for enabler-as-own-child (this resolves the tension with the infra guardrail
above — the guardrail wins unless BOTH gates pass):**

1. **Fan-out:** do **≥2** other children need it? (one → fold in.)
2. **Independent checkpoint:** can it be **built and verified on its own**, before any value slice runs
   *through* it? A shared SDK, a schema migration, a harness bypass — yes: "the client compiles + a
   contract test passes" is a real checkpoint standing alone. But a **cross-cutting substrate that can
   only be proven by exercising the first value slice** (the customer/subscription linkage a billing
   read proves; the `runs-on`/label plumbing the first migrated job proves) has **no checkpoint of its
   own** — carving it out makes a bare layer-node whose only "demo" is a component test, the exact
   anti-pattern Step 1 forbids. **Fold it into the skeleton** (the first slice already proves it
   end-to-end), even though ≥2 children touch it.

Litmus: *≥2 consumers **AND** a standalone build-and-verify checkpoint* → own child. *≥2 consumers but
only provable by running a value slice through it* → fold into the skeleton. One consumer → fold in.

## Step 2 — create the parent epic

- **Top-down** (no issue exists yet): create the parent issue — title = the feature, body = the
  capability list + the dependency spine. Mark it an epic: set `is_epic=true` **when the column exists**;
  until then, state **"EPIC — container issue, do not execute; work lives in child issues"** as the
  first line of the body so the marker is unambiguous.
- **Existing issue is the epic** (the too-big issue triage caught): keep it as the parent, prepend the
  same EPIC marker to its body, and **move any executable Desired Behavior out** into the appropriate
  child (the parent must carry no direct work — it's a container).

**These paths compose — a real epic often needs all three at once.** A single decomposition can:
keep an existing issue as the parent (path 2), **regroup** already-created issues in as children (the
regroup path below — link-only), **and** create the still-missing children fresh (Step 3). Don't treat
them as mutually exclusive — do whichever each child needs. (Example from testing: SOU-203 stayed the
parent, SOU-202 regrouped in as a child, and the enabler + registered-journey children were created
fresh — all one plan.)

## Step 3 — create + link the child issues

For each capability, create a child issue (its own `## Desired Behavior` = that one capability's demo),
then link it to the parent via `parent_id`.

```bash
# per child: create the issue file, then register + link. Until create-issue.py has --parent,
# create with the script, then set parent_id via the REST API.
uv run scripts/create-issue.py docs/issues/<child>.md --env <env>   # → prints SOU-### + uuid
```

```python
# link children to the epic (single or batch). parent_issue_id is the API field; batch-update
# sets it on many at once (field absent = untouched; explicit value = set).
import sys; sys.path.insert(0, "scripts")
import httpx
from lib import multica
from lib.dispatch_common import init_dispatch_config as _dc_init
_dc_init(explicit_env="<env>")
from lib import dispatch_common as _dc
tok = multica.resolve_token(None)
H = {"Authorization": f"Bearer {tok}", "X-Workspace-Slug": "soundingboard", "Content-Type": "application/json"}
with httpx.Client(timeout=30) as c:
    # single: PATCH one child
    c.patch(f"{_dc.MULTICA_API_URL}/api/issues/<child-uuid>", headers=H,
            json={"parent_issue_id": "<epic-uuid>"})
    # OR batch: link many children at once
    c.post(f"{_dc.MULTICA_API_URL}/api/issues/batch-update", headers=H,
           json={"issue_ids": ["<child1>", "<child2>"], "updates": {"parent_issue_id": "<epic-uuid>"}})
```

The API rejects a parent link that would form a **cycle** (it walks the ancestor chain) — so you can't
accidentally make an epic its own descendant.

## Step 4 — hand each child to triage (do NOT build here)

Each child issue is now a normal, closeable-capability issue. **Route each one to `/triage-issue`
individually** — it evaluates the three dimensions per child and picks that child's execution path
(direct fix / task / pipeline). The epic itself never goes to task-planning or a pipeline.

**Autonomy rule:** the auto-agent takes a **single leaf child issue** at a time. It must **flag +
refuse** the epic parent (`is_epic OR has_children`) — never auto-decompose it, never take multiple
issues in one run. This skill's decomposition is the *human-owned* split; the agent may propose a
breakdown but does not act on the epic.

## Regroup path (existing issues → one epic — the easy case)

If the children already exist (you realized mid-flight they belong together): create the parent epic
(Step 2), then `batch-update` the existing issues' `parent_issue_id` to the epic (Step 3, batch form).
No re-creation, no data migration — just the link. This mirrors `/project-management`'s batch-move, one
level down (issue→epic instead of issue→project).

**Not everything related is a child — a dependency ≠ a child.** An issue the epic's work *depends on*
or *verifies* but that is a **different kind of work** than the epic's capabilities stays an
**independent sibling**, linked as a `depends_on` (not `parent_id`). The test is the epic's own scope:
if the epic is scoped "journey coverage for X," a **product bug fix** that the journeys verify is not a
coverage capability — it's a prerequisite sibling, wired `child depends_on <the-fix>`, not pulled under
the epic. (Example: SOU-203 = journey coverage; SOU-201 = the add-phone product fix its journeys assert
— SOU-201 stays a sibling that Child B `depends_on`, NOT a child of SOU-203.) Litmus: *is this the same
KIND of deliverable as the epic's other children, or a different kind the epic merely needs?* Same kind
→ child; different kind it depends on → external sibling.

## Output

- The **parent epic** (marked EPIC in its body; `is_epic=true` when the column lands) + its capability
  list + dependency spine.
- The **child issues**, each `parent_id` → the epic, each carrying one capability's `## Desired
  Behavior`, each ready for its own `/triage-issue`.
- A one-line summary: `EPIC SOU-### → children SOU-A, SOU-B, … (spine: A → B,C → D)`.

## Principles

1. **An epic is a container, never a work item.** It holds child issues; it is never executed, never
   gets a pipeline. Its Desired Behavior is the *list of capabilities*, not a capability itself.
2. **One child = one closeable capability = one demo.** If it can't close/ship on its own, re-cut.
3. **Children re-enter triage individually.** This skill plans the split; each child gets its own
   three-dimension evaluation and execution path.
4. **The human owns the split for autonomous work.** The auto-agent flags + refuses an epic; it never
   decomposes-and-executes. Decomposition is judgment, not mechanics.
5. **Regroup is cheap — it's just `parent_id`.** Grouping existing issues under an epic is a batch link,
   not a rebuild.