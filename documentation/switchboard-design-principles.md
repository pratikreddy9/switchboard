# Switchboard Design Principles

Switchboard is Pratik's project control layer. It keeps projects, nodes, agents, handoffs, dependencies, and future GitHub backup in one understandable system.

## Core Intent

- One clean entrypoint for project management and handoff.
- One manager node per machine, one port, many logical project roots.
- One canonical agent update path.
- One future backup path to GitHub.

## Agent Principles

- Read back Pratik's requirement before acting.
- If intent is unclear, ask in simple English.
- Keep output short and dense.
- Do not create extra handoff markdown unless explicitly asked.
- Prefer one canonical file for agent edits: `switchboard/local/tasks-completed.md`.
- Do not treat "Update Switchboard" as only a task note.

## Canonical Update Discipline

An update is complete only when all relevant parts are handled:

- Task ledger entry.
- Runtime or service changes.
- Docs path changes.
- Scope entries and excludes.
- Snapshot.
- Verify-update.
- Control Center view check when UI state matters.

Agents must update pull scope when project shape changes. Source, config, docs, UI, and backend files belong in scope when relevant. Secrets, virtual environments, logs, runtime files, caches, and removed tech do not.

## Safety Principles

- Never delete cleanup targets.
- Move or zip old data.
- Write preflight and postflight reports for risky transitions.
- Stop when a safety check fails.
- Keep rollback visible.
- Do not hide credential handling inside Switchboard.

## Node Principles

- Each machine should run one Switchboard manager node.
- Each manager owns many logical project or minion roots.
- Old per-project nodes can exist during migration, but they are not the target architecture.
- Install, update, release, snapshot, verify, and cleanup should become manager-managed.
- A manager must make authority clear: manager, node-local, or control center.

## Project Principles

- Company to project hierarchy should stay simple.
- Project grouping should select from already tracked services.
- Task ledger UI should stay recognizable.
- Project colors should help scanning without redesigning the ledger.
- Each project can have its own principles, layered under the global principles.

## Dependency Principles

- Show direct dependencies and cross-dependencies together.
- Show composition plainly: language %, AI %, LLM %, embedding %, and actual model names.
- Prefer declared evidence and lightweight scans first.
- Do not invent precise numbers when evidence is incomplete.

## GitHub Backup Principles

- GitHub backup is the north star.
- Backup must be one or two clicks only after safety checks exist.
- Dirty repos, missing remotes, and missing credentials must be visible.
- Passwords and tokens do not belong in tracked framework scaffolding.

## Build And Test Principles

- Every changed line should trace to the request.
- Match existing style.
- Avoid speculative abstraction.
- Verify with build, focused tests, snapshot, and verify-update.
- Report known unrelated failures instead of hiding them.
