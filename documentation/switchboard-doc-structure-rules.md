# Switchboard Doc Structure Rules

## Control Center Layout

- `documentation/` for framework-level rules and principles
- `docs/evidence/` for runtime-generated dashboard-safe machine-readable snapshots
- `docs/evidence/archive/<timestamp>/` for immutable run captures
- `docs/dashboard-agent-handoff.md` for append-only agent coordination
- `state/private/` for local-only private metadata
- `downloads/<workspace>/<service>/<bundle_id>/source_tree/` for mirrored pull bundles
- `src/data/` for checked-in offline fallback JSON used by the UI and repo tests

## Node Layout

- `switchboard/node.manifest.json` for node identity and config
- `switchboard/node.manifest.json` also mirrors runtime config for the node’s primary location
- `switchboard/core/` for package-owned standard files
- `switchboard/local/tasks-completed.md` as the canonical runtime input file
- `switchboard/local/control-center-handoff.md`, `runbook.md`, and `approach-history.md` as regenerated outputs
- `switchboard/evidence/` for machine-readable node evidence

## Rules

- Use full ISO 8601 timestamps.
- Keep file names stable so the dashboard and nodes can depend on them.
- Keep private state out of `docs/evidence/` and out of tracked node docs.
- Do not overwrite project-owned root docs like `README.md` or `api.md` when installing a node.
- New services should be added by manifest, not by ad hoc folder conventions.
- Sync is manual and control-center initiated. Nodes do not push back into the control center.
- If a dashboard label differs from a real path name, keep the user-facing label in
  the service manifest and preserve the raw path as an alias.
