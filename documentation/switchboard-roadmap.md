# Switchboard Roadmap

## North Star

One- or two-click GitHub backup for every tracked project, with safe credentials, visible repo status, and no hidden destructive actions.

Everything before that is plumbing: canonical updates, low-context agent handoff, one manager node per machine, safe scoped operations, dependency visibility, and clear project grouping.

## Current State

Done:

- `tasks-completed.md` is the canonical task ledger.
- `switchboard node snapshot` builds node manifests, scope snapshots, task JSON, docs index, and agent contracts.
- `switchboard node verify-update` enforces the update gate.
- Agent contract files exist for Codex, Claude Code, Gemini CLI, Qwen Code, opencode, and generic agents.
- Manager-node foundation exists: one manager root can register, inspect, snapshot, and verify many project roots.
- `.47` proved the manager model with `sys_docs` as the core root and 10 verified roots behind one manager port.
- Roadmap and design principles now record current state, open work, and operating rules.
- Project Grouping service selection uses an explicit available-project selector.
- Task ledger project labels use deterministic colors.

Partial:

- GitHub backup pushes only repos that are clean, allowlisted, and already credentialed; credential storage is intentionally out of tracked scaffolding.

Open:

- Add a richer manager release UI around the manager-owned CLI/API.
- Add credential-handling UX for GitHub only after Pratik approves the credential model.

## Requirement Status

| # | Requirement | State |
|---:|---|---|
| 1 | Future plan, roadmap, design principles | Done |
| 2 | Dependencies, cross-dependencies, composition, model usage | Done |
| 3 | Sink pull authority clarity | Done |
| 4 | Project Grouping Add Available selection | Done |
| 5 | One node per machine, one port, manager/minion | Done |
| 6 | Manager-managed install, release, update | Done |
| 7 | Safe scoped commands, move/zip only | Done |
| 8 | Agent files for Codex, Claude, Gemini, Qwen, opencode | Done |
| 9 | Task ledger project colors | Done |
| 10 | Agent habit discovery and token diet | Done, ongoing |
| 11 | Read-back and low-ceremony principles | Done, ongoing |
| 12 | Global and per-project design principles | Done |
| 13 | One canonical agent-edit file | Done |
| 14 | One node as multiple logical services | Done |
| 15 | GitHub backup north star | Done for eligible repos |

## Execution Phases

1. Agent Contract Gate
   - Keep generated tool-native agent files small.
   - Enforce read-back, scope check, snapshot, and verify-update.
   - Treat output size as a design constraint.

2. Project UX Repair
   - Fix Project Grouping service selection.
   - Keep company to project hierarchy simple.
   - Add deterministic project colors in task views.

3. Pull And Dependency Intelligence
   - Show pull authority source: manager, node-local, or control center.
   - Present direct dependencies, cross-dependencies, composition, and model usage together.
   - Use evidence-based detection and declared project data.

4. Manager Operations
   - Manager is the entrypoint for install, upgrade/release-update, snapshot, verify, status, and old-scaffold archive.
   - Safe scoped commands use an explicit allowlist.
   - Cleanup moves old scaffolding into manager archives; it does not delete.

5. GitHub Backup
   - Repo readiness checks are visible.
   - Dry-run is recorded.
   - Push eligible repos in one action when existing git credentials work.

## Operating Rules

- Read back before acting.
- Ask in simple English when intent is unclear.
- Make small, surgical changes.
- Do not add ceremony.
- Do not delete cleanup targets.
- Verify with observable checks.
- A Switchboard update is incomplete until ledger, scope, snapshot, and verify-update pass.
