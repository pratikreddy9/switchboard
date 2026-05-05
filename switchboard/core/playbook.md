# switchboard Switchboard Playbook

This is the only primary instruction file agents should rely on for normal work in this project.

## Ownership Rules

- `switchboard/core/` is framework-owned and replaced by Switchboard upgrades.
- `switchboard/local/tasks-completed.md` is the single canonical file agents should edit during normal work.
- Derived docs and evidence are generated from that canonical file on `switchboard node snapshot`.
- Root project docs such as `README.md`, `API.md`, and `CHANGELOG.md` are only rewritten when they are enabled in `switchboard/node.manifest.json` under `managed_docs`.
- If a root doc is not enabled there, Switchboard must not edit it.

## Required Entry Shape

- Heading: `## <ISO timestamp> | <title>`
- `Tags:` with only `task`, `handoff`, `runbook`, `decision`, `scope`
- `Summary:` one concise sentence
- `Changed Paths:` comma-separated paths

- `Agent:` the agent or CLI that made the update
- `Tool:` the tool surface used, such as `codex-cli` or `claude-code`
- `Read Back:` one short sentence proving requirements were restated before work
- `Scope Check:` one short sentence saying scope changed and was updated, or did not change

## Hard Gate

- An update is incomplete until `switchboard node verify-update --project-root <path>` returns `ok`.
- `update Switchboard` means task ledger, scope/excludes check, snapshot, manifest/scope verification, and Control Center verification.
- Never delete for cleanup. Move or zip instead.
- Keep output short and do not add ceremony.

## Optional Blocks

- `Version:` single version string that becomes the canonical version source across derived docs
- `Readme:` markdown block for project overview/state
- `API:` markdown block for API-facing updates
- `Changelog:` markdown block for release-style deltas
- `Notes:` general details that do not belong in the other routed blocks
- `Scope Entries:` lines in `kind | path_type | path | enabled` format
- `Runtime:` lines for `expected_ports`, `healthcheck_command`, `run_command_hint`, `monitoring_mode`, and `notes`

## Canonical Workflow

1. Read this playbook.
2. Read back the request before changing files.
3. Edit only `switchboard/local/tasks-completed.md` for normal Switchboard updates.
4. Include `Read Back`, `Scope Check`, `Agent`, and `Tool` in the latest task entry.
5. Run `switchboard node snapshot --project-root <path>`.
6. Run `switchboard node verify-update --project-root <path>`.
7. Do not hand-edit derived docs unless explicitly instructed.

## Sync Rules

- Nodes do not call back into the control center.
- Nodes do not SSH into the control-center machine.
- Sync is always initiated from the control center.
- Control center may mirror scope, runtime, managed-doc configuration, and pull-bundle history into the node.
