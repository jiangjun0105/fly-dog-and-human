---
name: onboard-skills
description: Scan the repository and populate skill templates with repo-specific knowledge. Run this after adding template skills to a new repo — it reads the codebase and fills in the CUSTOMIZE markers so skills produce accurate, context-rich output without manual editing.
---

# Onboard Skills

Scan the current repository and fill in the `<!-- CUSTOMIZE -->` markers across all
skill templates with concrete, repo-specific knowledge. This turns generic skill
templates into skills that understand your project's structure, patterns, and tooling.

## When to Use

- After copying template skills (like `create-task`) into a new repository
- After significant structural changes to the repo (new services, changed test infra)
- When a skill's output is too generic — missing real file paths, wrong test commands, etc.
- When the user says "onboard", "set up skills", or "make skills repo-specific"

## How It Works

This skill does NOT guess or hallucinate. Every customization it writes must be
derived from files it actually read in the current repository **or from information
the user provides during the interview**. If it can't find the information for a
`<!-- CUSTOMIZE -->` marker, it leaves a `<!-- TODO: ... -->` note explaining what's
missing and how to provide it.

The process has two phases: **Interview** (understand the project and its users) and
**Discovery** (scan the codebase and populate markers).

---

## Phase 1: Interview

Before touching any files, interview the user to understand the project context that
cannot be derived from code alone. Use `AskQuestion` for structured questions.

### Step 1.1: Project Purpose and Development Work

Ask the user:

> "To set up these skills for your project, I need context that I can't get from
> reading the code alone.
>
> 1. **What is this project about?** (Describe the purpose and what it does — the
>    "why" behind the code)
> 2. **What are the main development tasks?** (e.g., building new frontend features,
>    adding backend API endpoints, full-stack feature work, writing integrations,
>    porting prototypes to production)
> 3. **What do developers in this repo usually work on day-to-day?** (e.g., feature
>    development across the whole stack, backend-only services, UI polish, writing
>    new packages that talk to external systems)
> 4. **Is there existing documentation I should read first?** (README, architecture
>    docs, onboarding guides — give me file paths)"

Read whatever docs the user points to. If they mention a README or architecture doc,
read it in full before proceeding.

**Do NOT ask about the tech stack, project type, or anything else that can be
inferred by reading the code.** Agents will discover those details in Phase 2.

### Step 1.2: Task Shape and Boundaries

Ask the user:

> "A couple more questions about how the skills will be used:
>
> 1. **What does a typical task look like?** (e.g., "add a new API endpoint and its
>    UI", "implement a feature from a design spec", "write a new package that talks
>    to an external service")
> 2. **Are there things the skills should NOT help with?** (e.g., infrastructure
>    changes, database migrations, deployment)"

This shapes which CUSTOMIZE markers matter most and how examples should be framed.

### Step 1.3: Sensitive Areas and Boundaries

Ask the user:

> "Which parts of the codebase need human oversight vs. are safe for autonomous agents?
>
> Examples of sensitive areas: auth/security, billing, data migrations, production
> config, hardware control logic, safety-critical code.
>
> Examples of safe areas: UI components, test files, documentation, utility modules,
> sample apps."

This directly populates the suitability heuristics in `create-task`.

### Step 1.4: Testing and Verification

Ask the user:

> "How does testing work in this project?
>
> 1. **How do developers run tests?** (commands, frameworks)
> 2. **Is there a dev environment setup?** (scripts, containers, simulators, mock
>    services, hardware emulators)
> 3. **What does verification look like?** (e.g., unit tests, integration tests,
>    golden/snapshot tests, manual testing on device, simulator runs)
> 4. **Any external services that need mocking or sandbox modes?** (third-party APIs,
>    hardware dependencies, cloud services)"

### Step 1.5: Confirm Understanding

Summarize what you learned and present it back:

> "Here's my understanding of the project:
>
> - **Purpose:** [what the project does and why]
> - **Main development work:** [what developers build day-to-day]
> - **Typical task:** [example]
> - **Sensitive areas:** [list]
> - **Safe areas:** [list]
> - **Test approach:** [how tests run, what frameworks]
> - **Dev environment:** [how to start, what's needed]
>
> Does this look right? Anything to add or correct?"

Incorporate feedback before proceeding to Phase 2.

---

## Phase 2: Discovery

Now scan the codebase to find concrete details. Use **sub-agents** for parallel
discovery — spawn them for independent concerns.

### Step 2.1: Spawn Discovery Agents

Launch sub-agents in parallel for each concern. Each agent should report back with
concrete findings (file paths, commands, patterns) — not summaries or guesses.

**Agent 1: Project Structure**
- Map top-level directories and their purposes
- Identify monorepo layout, service boundaries, or package structure
- Find build/config files (whatever is relevant for the stack discovered in Phase 1)
- Report: directory tree, key entry points, build system

**Agent 2: Service Interfaces / API Surface**
- Find the project's interface definitions (whatever form they take — REST routes,
  RPC schemas, GraphQL, CLI commands, SDK APIs, hardware protocols, etc.)
- Identify the primary communication patterns (HTTP, RPC, IPC, FFI, message bus, etc.)
- Report: list of interfaces, where they're defined, how they're consumed

**Agent 3: Test Infrastructure**
- Find test frameworks, test directories, test configuration
- Find how to run tests (Makefile targets, scripts, direct commands)
- Find mock/stub infrastructure (mock servers, test fixtures, simulators)
- Report: test commands, framework names, test directory paths, mock patterns

**Agent 4: Dev Environment & Build**
- Find how to build/start the project (scripts, containers, Makefiles, etc.)
- Find environment configuration (env files, config files, setup scripts)
- Find CI/CD configuration
- Report: build commands, start commands, required env vars, CI pipeline

**Agent 5: Code Patterns**
- Read 2-3 representative feature implementations end-to-end
- Identify the project's module/feature pattern (how features are structured)
- Find naming conventions, directory conventions
- Report: example feature paths, patterns to follow, naming conventions

The agents should look for whatever is actually in the repo — not assume any
specific tech stack. The interview context from Phase 1 tells them where to focus.

### Step 2.2: Collect and Verify

Collect results from all agents. For each finding:
- Verify file paths exist (`ls` or `find`)
- Verify commands work (or at least that the referenced scripts/configs exist)
- Cross-reference with what the user said in the interview

### Step 2.3: Find All CUSTOMIZE Markers

```bash
grep -rn "CUSTOMIZE" .claude/skills/ --include="*.md"
```

Group the markers by category:
- **File paths / project structure** — need real paths from the repo
- **Test infrastructure** — need real test commands, frameworks, directories
- **Dev environment** — need real startup commands, ports, env vars
- **Service interfaces** — need real interface definitions, communication patterns
- **Auth / access control** — need real auth mechanisms, test credentials
- **Code patterns** — need real module patterns, naming conventions
- **Suitability heuristics** — need real sensitive-area boundaries
- **Verification procedures** — need real test environment setup and commands

### Step 2.4: Populate Each Marker

For each `<!-- CUSTOMIZE -->` block, replace it with concrete content derived from
the interview and discovery. Follow these rules:

1. **Only write what you verified.** Every file path, command, and pattern must come
   from either the interview or a file you actually read. If you can't find the
   information, leave a `<!-- TODO: ... -->` note.

2. **Preserve the template structure.** The `<!-- CUSTOMIZE -->` comment explains what
   goes there. Replace the comment with the actual content, keeping the surrounding
   markdown structure intact.

3. **Use real file paths.** Every file you reference must exist — verify with `ls` or
   `find` before writing it into a skill.

4. **Include line numbers when useful.** If you reference a specific function or
   pattern, include `#L<n>` anchors so readers can jump directly to it.

5. **Match the project's domain language.** If the project uses "services" and "schemas",
   use those terms — not "endpoints" and "models". If it uses "packages" not "modules",
   say "packages". Mirror the vocabulary from the codebase and documentation.

6. **Keep examples concrete but minimal.** A 3-line example with the right commands
   beats a 20-line example with every optional flag.

### Step 2.5: Validate

After populating all markers, do a sanity check:

```bash
# Any CUSTOMIZE markers left?
grep -rn "CUSTOMIZE" .claude/skills/ --include="*.md"

# Any TODO markers added?
grep -rn "TODO" .claude/skills/ --include="*.md"
```

Present the results to the user:
- How many markers were filled vs. left as TODO
- Summary of what was discovered (stack, test framework, services, etc.)
- Any TODOs that need manual input

### Step 2.6: Suggest Infrastructure Setup

If the skill templates expect supporting infrastructure that doesn't exist yet,
suggest creating it:

| Expected by skills | What to create | Priority |
|---|---|---|
| `docs/tasks/` directory | `.shared-tasks/` + symlink + `.gitignore` entry | High — needed for `/create-task` |
| `docs/issues/` directory | Directory + `.gitignore` entry | High — needed for `/create-issue` |
| `scripts/task-board.py` | Task board scanner script | Medium — useful for task overview |
| `.claude/skills/manual-test/` | Manual test procedure library | Low — build as tests are written |

Ask the user which infrastructure items to set up, if any.

---

## What Makes a Good Customization

**Good** — derived from real files, verifiable, uses the project's own terms:
> Service interface reference:
> - Vehicle control APIs defined in `repos/arene-cockpit-api/*.capnp`
> - Flutter ↔ Rust bridge in `repos/dc-flutter/vehicle_interface/`
> - Mock services: set `MOCK_VEHICLE_APIS=true` (WebSocket-based, no hardware needed)

**Bad** — generic, not derived from the repo:
> API reference:
> - Check the API docs
> - Use test credentials from .env

**Good** — concrete commands that actually work:
> ```bash
> ./scripts/start-cockpit-runtime.sh        # Backend services
> cd repos/dc-flutter && flutter test        # Unit + golden tests
> cargo make codegen                         # Regenerate Dart FFI bindings
> ```

**Bad** — vague placeholders:
> ```bash
> # Start your services
> # Run tests
> # Build the project
> ```

## Incremental Updates

This skill can be re-run at any time. On subsequent runs:
- It should check which `<!-- CUSTOMIZE -->` markers still exist (unfilled)
- It should also check filled sections for staleness (referenced files that no longer
  exist, commands that no longer work)
- Present a diff of what it wants to change and ask before overwriting existing content
- Re-run the interview only if the user requests it or the project has changed
  significantly

## Scope

This skill only modifies files under `.claude/skills/`. It never modifies application
code, configuration, or documentation outside the skills directory.
