# Switchboard Doc Structure Rules

## Control Center Layout

- `documentation/` for framework-level public docs
- `docs/evidence/` for dashboard-safe machine-readable snapshots
- `docs/evidence/archive/<timestamp>/` for immutable run captures
- `state/private/` for local-only private metadata
- `downloads/<workspace>/<service>/<bundle_id>/source_tree/` for mirrored pull bundles
- `src/data/` for checked-in offline fallback JSON used by the UI and tests

## Node Layout

- `switchboard/node.manifest.json` for node identity, runtime mirror, managed-doc config, and doc-index mirror
- `switchboard/core/playbook.md` as the primary rulebook
- `switchboard/core/` for package-owned compatibility files and prompts
- `switchboard/local/tasks-completed.md` as the canonical runtime input file
- `switchboard/local/control-center-handoff.md`, `runbook.md`, `approach-history.md`, and `doc-index.md` as regenerated outputs
- `switchboard/evidence/` for machine-readable node evidence

## Rules

- use full ISO 8601 timestamps
- keep file names stable so the dashboard and nodes can depend on them
- keep private state out of `docs/evidence/` and out of tracked node docs
- do not overwrite project-owned root docs unless they are explicitly enabled in `managed_docs`
- new services should be added by manifest/UI, not by ad hoc folder conventions
- sync is manual and control-center initiated
