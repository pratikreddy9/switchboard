# Changelog

## 1.12.1

- fixed self-conflicting control-center action locks that made `sync-from-node` and pull bundles report themselves as already running
- changed action-lock API conflicts to return HTTP `409` instead of a misleading success response
- made runtime-cache writes atomic so lock polling does not intermittently fail with JSON decode errors under concurrent reads and writes

## 0.1.7

- made `switchboard/local/tasks-completed.md` the single canonical node update file for normal agent work
- added `switchboard/core/playbook.md` as the only primary node rulebook
- changed the older node instruction files into compatibility stubs that point back to the playbook
- added managed-doc config for opt-in framework-owned root docs:
  - `README.md`
  - `API.md`
  - `CHANGELOG.md`
- added managed-doc defaults and doc-index metadata to `switchboard/node.manifest.json`
- made `switchboard node snapshot` regenerate:
  - handoff
  - runbook
  - approach history
  - doc index markdown
  - completed tasks json
  - scope snapshot json
  - doc index json
  - any enabled root derived docs
- added node/control-center sync support for managed-doc configuration and doc-index metadata
- added managed-doc and doc-index visibility to the control-center service page and the node dashboard
- updated the public docs to describe the canonical-file model and the explicit `v2` boundary for broader project-management views

## 0.1.6

- fixed explicit exclude handling for bundle pulls so exact paths like `.DS_Store` are not copied when excluded
- added collapsible bundle history cards in the control center
- added per-bundle copied-file and missed-scope detail in history views
- added resolved-file preview under saved scope entries using the latest bundle detail

## 0.1.5

- fixed node/control-center scope sync so seed-only node scope does not overwrite explicit control-center scope choices
- added runtime parsing from `switchboard/local/tasks-completed.md` `Runtime:` blocks into node manifest snapshots
- added pulled-file and missed-scope detail to bundle records
- added mirrored pull-bundle history and latest pulled bundle detail to the node dashboard
- changed scope suggestions so code files default to `repo` and plain directories default to `doc` unless they contain repo markers

## 0.1.4

- fixed the node root HTML page crash caused by a local variable shadowing the `html` module
- keeps `/` working for the minimal node dashboard while `/api/health` and `/api/node` continue to work

## 0.1.3

- fixed background node startup in installed wheels by making `python -m switchboard.cli ...` execute the Typer app
- keeps `switchboard node start` aligned with the direct `switchboard node serve` foreground path

## 0.1.2

- added a single interactive startup entrypoint with `run.sh` / `start.sh`
- added package-level node runtime commands:
  - `switchboard node start`
  - `switchboard node stop`
  - `switchboard node status`
  - `switchboard node logs`
- added generated `switchboard/start.sh` and `switchboard/run.sh` inside node installs
- changed node startup so background runtime state is stored under `switchboard/runtime/`
- kept foreground `switchboard node serve` available only for direct terminal use

## 0.1.1

- added per-location runtime config for expected ports, health-check commands, run-command hints, monitoring mode, and notes
- added runtime-check API and UI actions
- added manual node sync actions:
  - `sync-from-node`
  - `sync-to-node`
- extended node manifest support to mirror runtime config
- added minimal node UI/API status view for runtime, docs pack, and snapshot state
- rewrote the public docs for:
  - control-center setup
  - runtime monitoring
  - node install and sync rules
- documented the v1 control-center-only sync model explicitly

## 0.1.0

- established the first control-center backend and React UI
- added workspace and service manifests
- added path-first project onboarding
- added editable scope entries
- added pull bundles with preserved source-tree layout
- added repo actions and basic evidence/history files
- packaged initial node install, upgrade, snapshot, and serve commands

## Planned For v2

- day-wise task views across projects
- project and workspace task calendars
- richer agent-management and multi-project reporting
- broader project-management dashboard features across nodes and the control center
- more advanced deploy-readiness, safety, and operational views
