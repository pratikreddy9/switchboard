# Switchboard April 29 Gap Audit

## Read Back

Pratik wants Switchboard to become one low-context control layer: one manager node per machine, one canonical agent update path, clear pull authority, dependency composition, safe scoped operations, and GitHub backup readiness without deleting or hiding credentials.

## Requirement Check

| # | Requirement | State | Evidence |
|---:|---|---|---|
| 1 | Roadmap and design principles | Done | `documentation/switchboard-roadmap.md`, `documentation/switchboard-design-principles.md` |
| 2 | Dependency composition and model usage | Done | Bundle and environment dependency summaries include language %, AI %, LLM %, embedding %, and models |
| 3 | Sink pull authority clarity | Done in 1.12.5 | Pull bundle preflight requires explicit location and blocks stale remote node scope |
| 4 | Project grouping dropdown | Partial | Searchable service selection exists; next polish is reducing advanced environment chrome |
| 5 | One node, one port, manager/minion | Done | Manager node can register, snapshot, verify, inspect, and operate many roots |
| 6 | Manager install/release/update flow | Done | Manager CLI/API owns install, upgrade/release-update, status, snapshot, verify, and archive entrypoints |
| 7 | Safe scoped commands | Done | Manager safe action allowlist; archive moves old scaffolding only |
| 8 | Agent files for Codex, Claude, Gemini, Qwen, opencode | Done in 1.12.5 | Manager owns the common contract; only enabled root entrypoints are required |
| 9 | Task ledger colors | Done | Deterministic per-project label color |
| 10 | Agent habit discovery | Done | .47 evidence summary received and reflected |
| 11 | Read-back, low ceremony | Done | Agent contract and playbook hard rules |
| 12 | Global and project design principles | Done | Machine-readable principle layers in node manifest/contract |
| 13 | One canonical agent-edit file | Done | `switchboard/local/tasks-completed.md` remains the normal edit target; common rules are inherited from the manager |
| 14 | Sub-technologies for one node services | Done | Manager node plus allowlisted CLI/API surface |
| 15 | GitHub backup north star | Done for eligible repos | Readiness, dry-run, and push-eligible action added |

## Critique Notes

- The only deliberate non-final area is credential handling. Switchboard now uses existing git credentials and runtime passwords but does not store GitHub passwords.
- Manager release/install plumbing reuses existing node primitives behind manager-owned CLI/API entrypoints.
- Cleanup is intentionally conservative: old per-root scaffolding is moved to manager archives, while local/evidence/manifests and agent work are preserved.
- The audit is a status matrix, not a blanket completion claim. Anything marked partial needs visible follow-up before being called finished.

## Test Gate

- Frontend tests must pass.
- Frontend build must pass.
- Backend unittest discovery must pass.
- `switchboard node snapshot --project-root /Users/p/Desktop/dashboard` must run.
- `switchboard node verify-update --project-root /Users/p/Desktop/dashboard` must return `ok`.
