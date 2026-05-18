---
name: technical-design
description: Create or update technical designs for features, services, or system changes. This skill sits upstream of scenario-driven-dev — it produces the system-level architecture, component specs, and verification plan that coding agents then implement via the scenario-driven-dev skill. Use this skill whenever the user wants to design a new feature, plan a new service, architect a system change, create a technical spec, update an existing design after a refactor, or when a feature requirement document needs to be turned into an actionable engineering plan. Also trigger when the user says things like "let's design this", "make a tech spec", "how should we build this", "let's plan the architecture", "create a technical design", or "update the design". Trigger proactively when you see a feature requirement that's complex enough to warrant design before implementation.
---

# Technical Design

A structured, interactive workflow for turning feature requirements into actionable technical
designs. The output feeds directly into the **scenario-driven-dev** skill (located at
`.claude/skills/scenario-driven-dev/SKILL.md`) for implementation. That skill handles the
coding workflow: requirements clarification → design → implement → test → review.

## How This Skill Fits the Development Pipeline

```
Feature Requirement
  │
  ▼
technical-design (THIS SKILL)
  → Produces: high-level architecture + component specs + verification plan
  → Each component spec has clear scope, definition of done, phase breakdown, and verification notes
  │
  ▼
scenario-driven-dev (implementation skill)
  → Takes each component spec as input
  → Runs: requirements → design → implement → test → review
```

The goal is to do the thinking _before_ coding agents start working. A good technical design
means each implementation phase starts with clear context and doesn't waste tokens rediscovering
decisions.

______________________________________________________________________

## Step 0: Understand the Input

Before anything else, figure out what you're working with:

1. **Read the source material.** If the user points to a ticket, fetch it. If it's a
   document, read it. If it's a conversation, synthesize what's been discussed so far.

1. **Check for existing design docs.** Before creating anything new, check whether
   `docs/design/<feature-name>/` or `docs/design/<feature-name>.md` already exists. If it
   does, switch to **update mode** — see Step 0.5 below. Design docs are living documents
   with one source of truth per feature. Never create a second design folder for the same
   feature or subsystem.

1. **Estimate project size.** This determines the entire workflow:

   | Size       | Signal                                                                  | Workflow                                                                        |
   | ---------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
   | **Small**  | Single feature, touches 1-3 files, clear scope                          | Write the full design directly in one pass. No rounds needed.                   |
   | **Medium** | Multiple components, touches 5-10 files, some ambiguity                 | Discuss approach with the user, write design together interactively.            |
   | **Large**  | New service, cross-cutting changes, multiple subsystems, open questions | Multi-round: high-level architecture first, then component-by-component detail. |

   Tell the user your size estimate and proposed approach. They may disagree — that's fine.

1. **Explore the repository and identify what already exists.** This is critical and where most
   design mistakes happen. You need to understand the existing codebase landscape before
   proposing anything.

   **Use the Explore agent** to survey the repo structure first, then read specific files for
   detail. Check these areas:

   - **Repository structure** — What services exist? What frontend apps are there? What shared
     libraries or packages are available?
   - **Shared libraries** — What common utilities, base classes, or shared modules exist?
     Don't reinvent what's already shared.
   - **Auth system** — How does the frontend authenticate? What middleware do existing
     services use? Don't propose a new auth mechanism if one already works.
   - **Database patterns** — What ORM base classes exist? How are migrations managed? What's
     the session/engine pattern?
   - **Service layer patterns** — Are endpoints thin with logic in services? What naming
     conventions are used?
   - **Deployment infrastructure** — How are services deployed? What containerization or
     platform configs exist? Are there Docker Compose configs for local dev?
   - **Coding conventions** — Check for convention files (e.g., `CLAUDE.md`, `AGENTS.md`,
     `.editorconfig`) in the repo root. Note file naming, import style, and annotation
     preferences.
   - **Existing features** — Find a feature module similar to what you're designing. Read
     its structure (routes, services, models, schemas) so you can follow the same patterns.

   **The principle: never assume when you can inspect.** Read actual code before proposing
   solutions. If you can't find something, ask the user — they know their system better than
   you do.

1. **Decide where the feature lives in the repository.** This is a key architectural decision
   that should be made early and confirmed with the user. There are two main cases:

   **Case A: Feature fits inside an existing service.**
   Most features belong here. Signs: the feature uses the same database, shares auth with
   existing endpoints, or is a natural extension of an existing domain.

   When this is the case:

   - Identify which service it belongs to
   - Find the feature module pattern in that service
   - Note what shared code it should use
   - Note if any frontend changes are needed

   **Case B: Feature requires a new service.**
   Signs: the feature has a fundamentally different runtime requirement (e.g., long-running
   processes that don't fit in a request-response service), needs its own deployment scaling,
   or has an isolated domain that would clutter an existing service.

   When this is the case:

   - Find an existing service to use as the structural template (copy its Dockerfile,
     config, and dependency patterns)
   - Decide how it connects to the rest of the system (shared database? API calls? message
     queue?)
   - Note which shared libraries it will depend on

   **Present your placement decision to the user** with your reasoning. For example:

   - "This feature needs long-running agent processes, so it doesn't fit the request-response
     model of the existing API service. I'd create a new service. I'll base its structure on
     [existing service] since it has a similar async pattern."
   - "This is a standard REST API extension. It fits naturally in the existing API service as
     a new feature module. No new service needed."

______________________________________________________________________

## Step 0.5: Update Mode (When Design Docs Already Exist)

If Step 0 found existing design docs, **do not start from scratch.** Instead, follow this
workflow to update the existing design in place. The goal is to maintain a single source of
truth — one design folder per feature — so that any agent working on any task always sees
the current desired state.

### Why Update Mode Matters

When a feature is redesigned or refactored, creating a second set of design docs causes
problems downstream:

- Agents working on small tasks only see their slice. If the "desired state" is split
  across old and new docs, they miss code that should be removed.
- The old design docs still describe the previous implementation. Agents may read them and
  assume that code is still desired.
- Cleanup work (removing legacy code, renaming modules, deleting dead paths) doesn't happen
  because no document says "this old thing should no longer exist."

Updating in place solves all three: the design docs always describe the target state, and
a migration section explicitly lists what to remove.

### Workflow

1. **Read the existing design docs.** Read every file in `docs/design/<feature>/`. Understand
   the current design — components, interfaces, key decisions.

1. **Read the current implementation.** Use the Explore agent to survey the actual code that
   was built from the original design. Note what was implemented, what diverged from the
   design, and what is still pending.

1. **Identify the delta.** Compare the existing design + implementation against the new
   requirements. Categorize changes:

   | Category        | Example                                                     |
   | --------------- | ----------------------------------------------------------- |
   | **Modified**    | Component exists but its behavior, API, or data model changes |
   | **New**         | Entirely new component or capability                         |
   | **Removed**     | Component or module that should no longer exist              |
   | **Unchanged**   | Component that stays as-is                                   |

1. **Present the delta to the user.** Before editing any docs, show the user what you plan
   to change and why. Get confirmation.

1. **Update the design docs in place.**

   - **High-level design:** Update the architecture diagram, component inventory, interface
     contracts, and key decisions to reflect the new desired state. Do not leave stale
     descriptions of removed components.
   - **Component specs:** Update modified components. Create new specs for new components.
     Delete specs for removed components (or mark them as removed with a note about what
     replaces them, if the git history is important for context).
   - **Add a "Migration from Previous Design" section** to the high-level design (see
     template in `references/high-level-template.md`, Section 12). This section is what
     enables agents to find and remove legacy code.

1. **Proceed to Step 1 or Step 2 as needed.** If the update is large enough to warrant
   re-doing the high-level design, go to Step 1. If it only touches specific components,
   go directly to Step 2 for those components.

### The Migration Section

The "Migration from Previous Design" section is the critical addition. It must contain:

- **What changed** — a summary of the design evolution (what was the old approach, what is
  the new approach, why the change).
- **Code to remove** — explicit file paths of modules, classes, functions, routes, tests,
  and configuration that should be deleted or replaced. Be as specific as possible. The
  more specific this list is, the more reliably agents will clean up legacy code.
- **Code to keep** — if some old code is still valid and used by other features, call it
  out explicitly so agents don't accidentally remove it.
- **Migration steps** — ordered list of what needs to happen: "first deploy new X, then
  remove old Y, then update references in Z." This ordering prevents breaking changes.

This section is consumed by the **task-planning** skill to generate explicit cleanup tasks.

______________________________________________________________________

## Step 1: High-Level Design (Large Projects Only)

For large projects, start with a system-level view before diving into any component. The
high-level design answers: _what are the major pieces and how do they connect?_

### What to Cover

1. **System overview** — One paragraph explaining what the system does and why.

1. **Architecture diagram** — Use mermaid for the primary diagram. This should show:

   - Major components (services, databases, queues, external APIs)
   - Data flow between them (arrows with labels)
   - User-facing interfaces (frontend, API, CLI)

   ```mermaid
   graph LR
     Frontend -->|REST + SSE| Backend[Backend Service]
     Backend -->|read/write| Storage[Object Storage]
     Backend -->|metadata| Postgres[(PostgreSQL)]
     Backend -->|subprocess| Agent[Agent Runtime]
   ```

   Add sequence diagrams for complex flows if they help:

   ```mermaid
   sequenceDiagram
     participant F as Frontend
     participant S as Server
     participant W as Worker
     F->>S: POST /tasks/{id}/start
     S->>W: Launch worker
     W-->>S: Stream events
     S-->>F: SSE stream
   ```

1. **Component inventory** — List every major component with a one-line description. Each of
   these becomes a component spec in Step 2.

1. **Interface contracts** — Define the boundaries between components:

   - API endpoints (method, path, request/response shape)
   - Database tables (name, key columns, relationships)
   - Message formats (SSE events, queue messages)
   - External service integrations

1. **Key decisions** — Capture architectural choices with rationale. Format as a decision table:

   | Decision      | Choice                             | Rationale                                |
   | ------------- | ---------------------------------- | ---------------------------------------- |
   | Agent runtime | Claude Agent SDK `ClaudeSDKClient` | Supports session continuity + interrupts |

1. **Open questions** — If the source material has open questions, take a position on each one.
   Explain your reasoning and ask the user to confirm or override.

1. **Verification plan** — Define how the feature will be proven correct after implementation:

   - The key user-visible or system-critical scenarios from the high-level design
   - The important integration seams, contracts, or recovery paths between components
   - The expected proof layers: component-local tests, backend runtime/integration verification,
     browser E2E, and any manual verification needed for infrastructure-heavy paths
   - The proof boundaries for each layer: what task-local tests can prove, and what they still
     cannot prove while components are built separately or seams are mocked
   - The concrete verification tasks likely needed after assembly, including what each task proves
     and why that proof cannot be closed inside a single implementation task

   For **large features** (4+ components or multiple waves), write the verification plan as a
   separate file: `docs/design/<feature-name>/verification-plan.md`. For smaller features,
   inline it in the high-level design.

   The verification plan is **not just documentation** — task planning will use it to create
   executable verification tasks up front. Those tasks are planned early but executed after
   implementation waves finish and after the mandatory overall review and proof-coverage review.

1. **Acceptance scenarios (Gherkin)** — Produce `docs/design/<feature-name>/acceptance-scenarios.md`
   as a **required** deliverable for any feature with user-visible behavior. This is the upstream
   source of truth that `task-planning` distributes into each task's `satisfies:` field, that
   workers write tests against, and that the Test Auditor uses to verify coverage.

   **Why this is a hard requirement, not a nice-to-have:** without scenarios authored at design
   time, downstream tasks have nothing concrete to satisfy. A common failure mode is writing
   scenarios that are endpoint-centric (every API endpoint has a `@security` scenario) but no
   scenario covers the *frontend route guard*. The scenario doc must include rows for **every
   authenticated route/page**, not just every endpoint.

   See the template in §"Acceptance Scenarios Template" below.

### How to Work Through This

This is interactive. Don't write the entire high-level design in silence and then present it.
Instead:

1. Read the codebase to understand existing patterns (use the Explore agent for this).
1. Draft the architecture diagram and component inventory.
1. **Present it to the user and ask for feedback.** Especially:
   - "Does this component breakdown match how you think about the system?"
   - "I found X in the codebase — should we use it or build something new?"
   - "For [decision], I'm leaning toward [option] because [reason]. Does that sound right?"
1. Iterate until the user confirms the high-level is solid.

### CRITICAL: Gate — User Must Approve High-Level Before Moving On

**Do NOT proceed to component design until the user explicitly approves the high-level design.**
This is a hard gate, not a soft suggestion. The user may need multiple rounds of feedback to
get the architecture right. Signs the user has approved:

- They say something like "looks good", "let's move on", "approved", "now let's do components"
- They explicitly ask to start on a specific component

If the user gives feedback or asks questions, iterate on the high-level design until they
are satisfied. Never assume silence means approval — ask directly:
"Are you happy with the high-level design? Ready to move to component specs?"

### Output

Save to `docs/design/<feature-name>/high-level-design.md`. If the feature is simple enough
for a single file, save to `docs/design/<feature-name>.md`.

The high-level design should leave downstream agents with:

- A component inventory and clear boundaries
- The key user-visible or system-critical scenarios the feature must satisfy
- The major integration seams that need explicit verification later
- A verification plan (inline or in a separate `verification-plan.md`) that states proof
  boundaries and the deferred verification tasks the task planner must create during planning
- **`acceptance-scenarios.md`** — Gherkin scenarios with stable `@id` slugs and layer tags,
  covering every user-visible behavior including frontend route guards, ownership, and rate
  limits. Without this file, `task-planning` cannot run its coverage-matrix gate and the Test
  Auditor has no source of truth to check against.

______________________________________________________________________

## Step 2: Component Design

After the high-level design is confirmed, drill into each component. This is where you produce
the specs that coding agents will actually implement.

### CRITICAL: One Component at a Time

**Work on exactly ONE component spec per round.** Do not batch multiple component specs
into a single pass. The workflow is:

1. **Ask the user which component to work on next.** You should suggest an order based on
   dependencies (e.g., "I'd recommend starting with Task API since other components depend
   on the data models"), but the user decides.
1. **Write that one component spec.** Draft it, present it, iterate with the user.
1. **Get user approval** on that component spec before moving to the next one.
1. **Ask which component is next.** Repeat until all components are done.

This ensures the user stays in control and each component gets proper attention. Don't
rush through components — each one is the blueprint a coding agent will follow.

### Sizing Components for Coding Agents

Each component spec should be scoped so that a coding agent (Claude Opus 4.6 with 1M context)
can complete it in a single session. Rules of thumb:

- **One component = one clear responsibility.** If you're describing two unrelated things,
  split them.
- **Up to ~25 files modified or created.** Opus 1M can handle substantially more context
  than earlier models. Prefer fewer, larger components over many small ones — splitting
  creates artificial integration seams that often cost more effort than they save.
- **Clear entry and exit criteria.** The agent should know exactly when it's done.
- **Explicit dependencies.** If this component needs something from another component, say so.
  If it needs an existing module, provide the file path.
- **Prefer single-phase components.** Only split into phases when the phases are truly
  independent (different domains, different services, or genuinely separable concerns).
  Do not split a single linear flow (e.g., auth → bridge → cleanup in a handler) into
  phases — the integration overhead exceeds the benefit.

If a component is genuinely too large for a single session, break it into phases. Each
phase should be independently deployable or at least independently testable.

### Relationship to scenario-driven-dev's Design Phase

Both this skill and the **scenario-driven-dev** skill (`.claude/skills/scenario-driven-dev/SKILL.md`)
have a design step, but they serve different purposes and should not overlap:

- **Component spec (this skill):** System-level context. _Why_ does this component exist? How
  does it interact with other components? What existing services and interfaces should it use?
  What decisions were made and why? Conceptual data model (entities, relationships, key fields).
  Clear definition of done.
- **SDD design phase:** Implementation-level detail. Actual models and schemas, exact function
  signatures, internal class structure, error handling strategy, test scaffolding. The SDD
  design phase picks up where the component spec leaves off.

The component spec gives the coding agent enough context to make good decisions during
implementation. The SDD design phase turns that context into a concrete implementation plan.

### Two Tiers of Component Depth

Not every component needs the same level of design detail. Match the depth to the complexity:

**Straightforward components** (e.g., standard REST APIs, CRUD modules, data pipelines with
known patterns):

1. **Overview** — What it does and _why it exists_. 2-3 sentences.

1. **Context and reasoning** — Why this component was designed this way. What alternatives
   were considered. What constraints shaped the approach. This helps the coding agent make
   good judgment calls during implementation.

1. **Interactions with other components** — How this component connects to the rest of the
   system. What it consumes, what it produces, what events it listens to or emits.

1. **Existing code to use** — File paths and descriptions of existing modules to build on.
   Be specific so the coding agent doesn't reinvent what already exists.

   ```
   ## Existing Code
   - `src/common/database/base_repository.py` — Base repository with generic CRUD. Extend this.
   - `src/features/chat/` — Example of a feature module. Follow this structure.
   ```

1. **Conceptual data model** — What entities exist, their key fields, and how they relate to
   each other. Describe them in plain language or a simple table — _not_ as implementation code.
   The actual code (column types, constraints, indexes, validation rules) is implementation
   detail that the scenario-driven-dev design phase will produce. Example:

   ```
   ## Data Model
   - **Task** — Represents a unit of work. Key fields: status (drives the state machine),
     owner (user who created it), agent_config (which model/tools to use). Relates to
     ConversationEntry (one-to-many).
   - **ConversationEntry** — A single message in the task's agent conversation. Key fields:
     role (user/assistant/tool), content, timestamp.
   ```

   Exception: if the data model _is_ the design (e.g., a status enum that defines a state
   machine), include enough detail that the reader understands the logic — but still describe
   it conceptually rather than as implementation code.

1. **API endpoints** (if applicable) — Method, path, request/response shapes, error cases.
   Describe the shape conceptually (field names and types) rather than writing full schema
   code — SDD will produce the exact schemas.

1. **Definition of done** — Unambiguous exit criteria for each phase.

1. **Phase breakdown** (if needed) — Each phase becomes a separate scenario-driven-dev
   invocation.

1. **Testing notes** — What task-local tests must prove, what to mock, what needs real services,
   what remains unproven at task scope, and whether the component requires deferred feature-level
   runtime / E2E verification once multiple components are merged.

1. **Deployment data requirements** — Does this component need data to exist in the DB
   before the code runs? If yes, specify:

   - What data must exist (config entries, seed rows, backfills)
   - How it gets there: code defaults/fallbacks, data migration scripts, or schema migrations
     with DML (only when tightly coupled to a schema change)
   - The data change artifact must be created during implementation and included in the same PR

   This is critical to avoid deployment failures where new code expects data that hasn't
   been populated yet.

For straightforward components, _don't_ go deep into logic and flow — the SDD design phase
will handle that. Focus on giving the coding agent the system-level context it needs.

**Complex components** (e.g., orchestration engines, multi-agent coordination, state machines,
novel algorithms):

Everything above, _plus_:

10. **Logic and algorithm design** — The core of what makes this component complex. This is
    where you describe things like:

    - How multiple agents interact: who initiates, who responds, what messages they exchange
    - Role definitions: what is the main responsibility of each actor (e.g., the worker
      builds, the reviewer evaluates against a checklist)
    - Decision logic: what happens in each case (e.g., reviewer approves → complete;
      reviewer finds issues → loop back to worker with feedback; timeout → escalate)
    - State transitions: what triggers each state change, what invariants must hold

    Use mermaid diagrams (state diagrams, sequence diagrams, flowcharts) to make complex
    flows visual. Pseudocode is fine for decision trees.

For complex components, the logic design is essential because the SDD design phase alone
won't have enough context to get the algorithm right. The coding agent needs to understand
the _reasoning_ behind the design, not just the structure.

### State Machine Design & Component Boundaries

If the component involves a **state machine** or has **tight coupling with another component**,
read `references/complex-component-patterns.md` before drafting. It covers:

- State glossary tables (define states before drawing diagrams)
- Splitting diagrams by scenario (happy path, loops, interruptions, errors)
- Separating user-initiated vs system-driven transitions
- Questioning each state's necessity
- Component boundary responsibility tables and interface contracts

### The "Why" Principle

Every section of a component spec should explain _why_, not just _what_. Examples:

- **Bad:** "Use JWT auth middleware on all endpoints."

- **Good:** "Use JWT auth middleware on all endpoints. The frontend already issues JWTs via
  the existing auth flow, so this service can validate them without building its own auth
  system."

- **Bad:** "The reviewer agent checks the worker's output."

- **Good:** "The reviewer agent checks the worker's output against the task's checklist.
  This two-agent pattern exists because a single agent reviewing its own work tends to
  be uncritical — a separate agent with fresh context catches issues the worker misses."

When coding agents understand _why_ a decision was made, they make better choices in the
edge cases the spec didn't explicitly cover.

### How to Work Through This

Again, interactive — **one component at a time.** For each component:

1. **Ask the user which component to tackle next.** Suggest a recommended order based on
   the dependency graph (e.g., "I'd recommend starting with Task API since the data models
   are needed by Orchestration Engine and Agent Runtime"), but let the user choose. The agent
   is encouraged to explain its suggested order and reasoning.
1. **Check the codebase** for existing patterns that apply. Read actual files, don't guess.
1. **Draft the component spec** — data models, APIs, logic.
1. **Present to the user.** Key questions:
   - "This component touches [existing module]. I've read the code — here's how I think we
     should extend it. Does this match your expectations?"
   - "I'm splitting this into N phases. Does the scoping feel right?"
   - "The definition of done for Phase 1 is [X]. Is that the right milestone?"
1. **Iterate** until the user confirms this component spec.
1. **After major iterations, do a consistency review.** When the design goes through multiple
   rounds of feedback, earlier sections often become stale. Before presenting the "final"
   version, run through the checklist in `references/complex-component-patterns.md` §Consistency
   Review Checklist — it covers section numbering, name consistency, diagram-table alignment,
   and stale references.
1. **Then ask which component is next.** Do not auto-proceed to the next component.

### Output

Save each component spec to `docs/design/<feature-name>/<component-name>.md`.

For a large system, the design folder might look like:

```
docs/design/cloud-agent-service/
├── high-level-design.md          # Step 1 output
├── task-api.md                   # Component: REST API
├── orchestration-engine.md       # Component: state machine + agent loop
├── agent-runtime.md              # Component: SDK integration + tools
├── streaming.md                  # Component: SSE event bus
└── storage.md                    # Component: blob + local disk
```

______________________________________________________________________

## Step 3: Handoff to Implementation

Once component specs are done, the next step is to organize the work. There are two paths:

**Path A: Use the task-planning skill (recommended for large projects).**
The **task-planning** skill (`.claude/skills/task-planning/SKILL.md`) analyzes the design
docs, builds a dependency graph, identifies which phases can run in parallel, and creates
individual task files in `docs/tasks/`. It should also reserve the feature-level verification
work that cannot be fully proven inside a single component task, preserving each task's proof
goal from the verification plan. Each task points back to the design docs and is scoped for a
single agent session. This is the recommended path when the design has 4+ components or multiple
phases — it makes the work visible on the task board and enables multi-agent parallel execution
via worktrees.

**Path B: Go directly to scenario-driven-dev (fine for small designs).**
For small designs (1-2 components, no parallelism needed), the user or coding agent can
pick up each phase and run it through the **scenario-driven-dev** skill
(`.claude/skills/scenario-driven-dev/SKILL.md`) directly.

Either way, the component specs produced by this skill serve as **upstream design docs** for
SDD. SDD's "Working with Upstream Design Docs" section describes how its phases adapt when
design docs exist. In short:

- **SDD Phase 1 (Requirements):** The component spec provides architectural context. SDD
  still produces concrete behavioral scenarios with the human, but the conversation is
  narrower — you're not discovering the feature from scratch. The human revalidates key
  decisions from the component spec.
- **SDD Phase 2 (Design):** The component spec provides the conceptual data model, API
  shape, and existing code references. SDD turns these into implementation-level detail:
  actual models, schemas, file paths, method signatures. The human confirms each
  translation — the component spec is a starting point, not gospel.
- **SDD Phases 3-6:** No change inside the task itself — implement, test (subagent), review
  (subagent). But completing one task does not automatically prove the entire feature. If the
  design identified cross-component seams, plan for an overall review plus dedicated runtime /
  E2E verification work before calling the feature closed.

### What Makes a Good Handoff

A component spec is ready for implementation when a developer or coding agent can read it
and understand:

- _Why_ this component exists and what problem it solves
- Where it lives in the repository and how it interacts with other components
- What entities and relationships exist conceptually
- What the API surface looks like (endpoints and their purpose)
- What existing code and patterns to build on
- The reasoning behind key design decisions
- When it's done (definition of done is unambiguous)

The component spec should _not_ contain implementation-level detail (ORM classes, schema
definitions, function signatures, exact file paths to create). That's the job of whoever
picks it up — either through the scenario-driven-dev skill or a human developer — working
collaboratively to turn the conceptual design into concrete code.

If the reader can't answer "why are we building this, and what does it connect to?" the
spec isn't done yet.

______________________________________________________________________

## Step 4: Update Design Doc Index

After saving the design doc(s), update `docs/design/README.md` so agents and developers
can discover the design by topic name.

If `docs/design/README.md` exists, add or update the entry for this feature. If it doesn't
exist, create it:

```markdown
# Design Documentation

Forward-looking design docs for planned features and integrations.
For documentation of existing code, see `docs/architecture/`.

| Topic | Folder | Status |
|-------|--------|--------|
| <feature-name> | <folder-name>/ | Active |
```

**Why this matters:** Design doc folders often have abbreviated or hyphenated names that
don't match the topic keywords agents or developers search for. The index provides a
keyword-searchable topic name mapped to the actual folder.

Skip this step only if the design doc is a single-file update to an existing entry that
already appears in the index.

______________________________________________________________________

## Principles

> **Formatting note:** When adding a new principle, append it at the end with the next
> number. Do **not** renumber existing principles — other documents and conversations
> reference them by number (e.g., "Principle 5"). For ordered lists elsewhere in this
> document, use `1.` for every item — Markdown auto-numbers them, so insertions don't
> require renumbering.

### 1. Read Before You Write

Always inspect the existing codebase before proposing solutions. Use the Explore agent
for broad surveys, use Read/Grep for specific files. Your job is to understand what exists
and extend the established patterns, not replace them.

Things to always check:

- **Repository structure** — What services exist? What frontend apps are there? What shared
  libraries or packages are available?
- **Where does this feature belong?** — Does it fit in an existing service, or does it
  need a new one? Find a similar feature module and follow its structure.
- **Auth patterns** — Don't propose a new auth mechanism if one already exists. Check what
  middleware existing services use.
- **Database access patterns** — Use existing base classes and repositories, don't write raw
  SQL or invent a new data layer.
- **Shared libraries** — What common utilities exist? Don't reinvent these.
- **Service layer patterns** — Thin endpoints, logic in services. Check file naming
  conventions in any project convention files.
- **Deployment infrastructure** — How are services deployed? What containerization or
  orchestration patterns exist? What Docker Compose configs exist for local dev?
- **Existing feature modules** — Find one similar to what you're building. Read its
  routes, services, models, and schemas to follow the same patterns.

### 2. Discuss, Don't Dictate

Technical design is collaborative. Present your thinking, explain your reasoning, and ask
for the user's input — especially on decisions that affect the existing system. The user
knows things about the system that aren't in the code (business constraints, team preferences,
upcoming changes).

### 3. Diagrams Over Prose for Architecture

A mermaid diagram communicates system structure faster than paragraphs of text. Use:

- `graph LR/TD` for component relationships and data flow
- `sequenceDiagram` for multi-step interactions
- `stateDiagram-v2` for state machines
- `flowchart` for decision logic

ASCII art is acceptable for quick inline sketches when mermaid would be overkill.

### 4. Size Phases for Agent Context Windows

Each implementation phase should be completable by a coding agent (Opus 4.6 1M) in a
single session. This means:

- Clear, bounded scope (not "implement the whole service")
- All dependencies are either completed in a previous phase or are existing code
- Definition of done is testable
- Touches no more than ~25 files

Avoid splitting a component into phases when the phases share the same handler flow or
linear pipeline. Integration between phases often costs more than the phase itself.
Only split when phases are truly independent (different domains, different services,
or genuinely separable concerns).

### 5. Resolve Open Questions, Don't Defer Them

When the source material has open questions, take a position. Explain your reasoning.
Present it to the user for confirmation. Unresolved questions become blockers for the
coding agent — they'll either guess (badly) or stall.

### 6. Final Consistency Check Before Finalizing

Before presenting a component spec as "done", run these two checks:

1. **DoD, Testing, and verification-task sections match the design.** After iterating on a
   design through multiple rounds of feedback, the Definition of Done, Testing Notes, and
   verification-plan sections often become stale. Re-read them against the final design and
   update any references to removed features, renamed tools, changed interfaces, or modified
   behavior. Every DoD item, test scenario, and deferred verification task should correspond
   to something that actually exists in the current design.

1. **Cross-document consistency.** When a design change in one component affects other
   components or the high-level design, update all related documents in the same pass.
   Common things that drift: tool names in agent configs, callback signatures, component
   inventory descriptions, architecture diagrams, directory structures, and phase dependency
   lists. After updating, do a quick grep for the old name/term across all design docs to
   catch stragglers.

These checks catch the most common class of design doc bugs: sections that were correct
when first written but became stale after later iterations.

### 7. Challenge Earlier Design Docs, Don't Inherit Blindly

When designing a component, **do not treat the high-level design or other component specs as
gospel.** Earlier documents were written with less context — they made reasonable first-pass
decisions, but those decisions may not hold up under detailed scrutiny.

For every design choice you carry forward from an earlier doc, ask: _"Is this still the best
approach now that I understand this component's specific constraints?"_ Examples of things
that commonly deserve re-evaluation:

- **Data storage choices.** The HLD may propose a database table for data that's better suited
  to an in-memory buffer, Redis, or no persistence at all. Evaluate the actual access pattern
  (write volume, read frequency, durability requirements, query needs) before committing.
- **Infrastructure dependencies.** The HLD may include Redis, a message queue, or an external
  service that seemed necessary at the system level but isn't justified for V1's actual scale
  and usage patterns.
- **Entity/table definitions.** A data model sketched in the HLD may turn out to duplicate
  information already captured elsewhere (e.g., audit logs that duplicate session transcripts,
  or status tables that duplicate what the primary record already tracks).
- **Interface shapes.** An API contract defined in the HLD may be over- or under-specified
  once you understand the real consumer needs.

When you identify a mismatch, **call it out explicitly** to the user: _"The HLD proposes X,
but now that I've looked at this in detail, I think Y is better because [reason]. Should we
update the HLD?"_ Don't silently diverge and don't silently comply — either creates
inconsistency or waste.

This principle complements "Read Before You Write" (Principle 1) — that principle says to
understand what exists in the codebase; this one says to critically evaluate what exists in
the design docs.

### 8. Name Existing Modules Explicitly

When the component should use an existing module, provide the file path and explain what
to use from it. "Use the base repository" is not enough. Say:
"Extend `src/common/database/base_repository.py`. Specifically, use the
`BaseRepository.create()`, `get_by_id()`, and `update()` methods. See
`src/features/users/user_repository.py` for an example of how another entity extends
this base."

### 9. When Updating a Design, Audit What Must Be Removed

When working in update mode (Step 0.5), the most common failure is focusing only on what's
new and forgetting to document what's old. For every new component or changed interface, ask:

- _"What existing code does this replace?"_
- _"Where else in the codebase does the old interface get called?"_
- _"Are there tests, seeds, scripts, or configs that reference the old approach?"_

Use Grep/Explore to find all references to the old module, function, route, or schema name.
List every file path in the "Code to Remove" section of the migration plan. The downstream
task-planning skill will turn these into explicit cleanup tasks — but only if you list them.

If you're unsure whether something should be removed, list it in the "Code to Keep" section
with a note explaining why it might still be needed. It's better to flag something for human
review than to silently leave dead code behind.

______________________________________________________________________

## Acceptance Scenarios Template

Save to `docs/design/<feature-name>/acceptance-scenarios.md`.

### Required structure

```markdown
# <Feature> — Acceptance Scenarios (Gherkin)

> Companion to `high-level-design.md`. Captures user-visible behavior as Given/When/Then
> so we have a single source of truth between design intent, implementation tasks, integration
> tests, E2E tests, and UAT.

These scenarios map to:
- **Feature tasks** — each task's `satisfies:` field cites scenarios by `@id`. The worker
  writes a test for every claimed `@id` (layer determined by tag — see below).
- **Test Auditor** — for every claimed `@id`, verifies a test exists at the right layer.
- **UAT** — pilot users walk each scenario to confirm observable behavior.

## Tags (REQUIRED on every scenario)

Choose one **layer tag** + zero-or-more **classifier tags** + the **stable id**.

**Layer tags** (mutually exclusive — picks where the test lives):

| Tag             | Worker must produce                                          | Test file location                          |
| --------------- | ------------------------------------------------------------ | ------------------------------------------- |
| `@e2e`          | E2E spec (real browser, real backend)                        | `tests/e2e/<feature>.spec.ts`               |
| `@integration`  | Integration test (real DB, real HTTP, no UI)                 | `tests/integration/test_<feature>.py`       |
| `@unit`         | Unit/component test                                          | adjacent to source                          |
| `@contract`     | Contract test between two modules (FE↔BE shape, queue payload) | wherever the contract lives               |

**Classifier tags** (composable with layer tag):

| Tag                 | Meaning                                                              | Auditor implication                                                                         |
| ------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `@security`         | Auth/authorization/permission boundary                               | **Must have BOTH** a frontend route-guard test AND a backend handler test. Endpoint-only fails. |
| `@ownership-<slug>` | Cross-user data access boundary                                      | Same as `@security`.                                                                        |
| `@route-guard`      | Frontend route requires auth or specific role                        | Must have a component test asserting the guard wraps the route.                             |
| `@rate-limit`       | Abuse / cost-ceiling guard                                           | `@integration` test must exercise the real limiter, not a mock.                             |
| `@async`            | Polling, long-running job, eventually-consistent state               | Test must exercise the lifecycle (start → polling → terminal), not just the start endpoint. |
| `@external`         | Touches an external service that cannot be CI-tested                 | No automated test required, but a `Human manual test` block in the task is.                 |

**Stable id** (REQUIRED, exactly one per scenario):

- `@id:<feature-slug>-NN-<short-slug>` — once assigned, never reused. NN is monotonic within
  a feature but doesn't have to be gapless if a scenario is dropped. The test name MUST mirror
  the id (e.g. `@id:voice-04-approve-clone` → `test_voice_04_approve_clone` or
  `it("[voice-04-approve-clone] approves the clone")`).

## Glossary (REQUIRED for any feature with non-trivial preconditions)

Define shared preconditions once, then reference them via `Given I am a "<role>"` in
scenarios. Prevents drift between scenarios that use slightly different wording for the
same precondition.

## Coverage requirements (the planner enforces these)

For every authed feature, the scenario doc MUST include:

1. **At least one `@route-guard` scenario per protected frontend route.** Not "the API endpoint
   returns 401" — the route itself, in a browser.
2. **An empty-state scenario for any page that fetches data.** What does the user see when no
   row exists? Infinite spinner is a bug.
3. **An `@ownership-*` scenario per resource that has owners.** User A cannot see/modify user
   B's data. Tested at both layers (FE guard + BE handler) per `@security` rules above.
4. **A negative-path scenario per @rate-limit / @async / @security tag.** Happy paths alone
   produce green-badge illusions.

## Feature: <Capability Name>

\`\`\`gherkin
Feature: <Capability>
  As a <role>
  I want <capability>
  So that <outcome>

  Background:
    Given <shared precondition from Glossary>
\`\`\`

### <Sub-area>

\`\`\`gherkin
@e2e @id:<feature-slug>-01-<short-slug>
Scenario: <Imperative description>
  Given <state>
  When <action>
  Then <observable outcome>
  And <additional assertion>
\`\`\`

### <Sub-area: route guards>

\`\`\`gherkin
@e2e @route-guard @id:<feature-slug>-NN-route-protected
Scenario: Unauthenticated visit redirects to sign-in
  Given I have no session
  When I open /<feature-route>
  Then I am redirected to /<signin-path>?next=<url-encoded /<feature-route>>
  And the protected content never renders for an unauthenticated visitor

@unit @route-guard @id:<feature-slug>-NN-guard-wrapper
Scenario: Route registration includes the guard wrapper
  Given the application router
  Then the route /<feature-route> is rendered through <ProtectedRoute wrapper>
  And a test that mounts the route without the wrapper fails
\`\`\`

## Coverage map — scenarios vs. tasks

| @id                              | Tag(s)            | Claimed by task          | Test file                                                  |
| -------------------------------- | ----------------- | ------------------------ | ---------------------------------------------------------- |
| `<feature>-01-<slug>`            | `@e2e`            | T<NN> <task-name>        | `<test-file-path>`                                         |
| `<feature>-NN-route-protected`   | `@e2e @route-guard` | T<NN> <task-name>      | `<test-file-path>`                                         |

This table is **the source of truth for `task-planning`'s coverage matrix**. Every row must
have a claimed task and an intended test file path before planning is approved.
```

## Templates

### High-Level Design Template

See `references/high-level-template.md` for the full template.

### Component Spec Template

See `references/component-template.md` for the full template.
