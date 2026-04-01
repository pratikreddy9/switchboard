# Changelog

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
