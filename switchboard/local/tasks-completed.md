# Tasks Completed

Use one entry per meaningful update.

Required fields:
- heading: `## <ISO timestamp> | <title>`
- `Tags:` using only `task`, `handoff`, `runbook`, `decision`, `scope`
- `Summary:`
- `Changed Paths:` comma-separated
- optional `Version:`
- optional `Readme:` markdown block
- optional `API:` markdown block
- optional `Changelog:` markdown block
- optional `Notes:` lines
- optional `Scope Entries:` lines in `kind | path_type | path` format
- optional `Runtime:` lines for ports, health check, and run command hint

Example format:

```md
    ## 2026-04-01T12:00:00+00:00 | Example update
    - Tags: task, handoff
    - Summary: Standardized the project docs.
    - Changed Paths: switchboard/core/README.md, switchboard/local/tasks-completed.md
    - Version: 1.1
    - Readme:
      ## Overview
      Standardized the project docs.
    - API:
      ## Surface
      Added `/health`.
    - Changelog:
      - Standardized the project docs.
    - Notes:
      - Added the first standard handoff.
    - Runtime:
      - expected_ports: 8010
      - healthcheck_command: curl http://127.0.0.1:8010/api/health
```

## 2026-04-06T15:30:38+00:00 | Fix self-conflicting sync and bundle locks
- Tags: task, handoff
- Summary: Removed duplicate client-side action locks that were causing sync and pull-bundle requests to report themselves as already running.
- Changed Paths: src/pages/ServiceDetailPage.tsx, src/components/PullBundlePanel.tsx, switchboard/api.py, switchboard/storage.py, tests_backend/test_backend_regressions.py, package.json, pyproject.toml, switchboard/__init__.py, README.md, CHANGELOG.md, switchboard/local/tasks-completed.md
- Version: 1.12.1
- Notes:
  - `sync_from_node` and `sync_to_node` now rely on the backend action guard instead of pre-acquiring the same lock in the browser.
  - Pull bundle creation now uses backend lock state for reconciliation instead of creating a second conflicting lock from the UI.
  - `action_in_progress` now maps to HTTP 409 so real lock conflicts surface as API errors instead of HTTP 200 responses.
  - Runtime cache writes now use atomic file replacement so `/action-locks` polling does not hit transient JSON decode failures during concurrent writes.
  - Verified the frontend production build and confirmed the backend now returns 409 for a forced `sync_from_node` lock collision after restart.

## 2026-04-07T04:01:16Z | Recenter service pages on the tracked project
- Tags: task, handoff, scope
- Summary: Shifted the control center back to project-first context by clarifying project-doc ownership, surfacing project history ahead of framework maintenance, and tightening exact node release checks.
- Changed Paths: src/pages/ServiceDetailPage.tsx, src/components/TaskLedgerPanel.tsx, src/components/ConfirmationModal.tsx, src/api/client.ts, src/types/switchboard.ts, src/App.tsx, switchboard/collectors.py, switchboard/models.py, switchboard/node.py, tests_backend/test_runtime_and_node_sync.py, documentation/switchboard-design-principles.md, package.json, pyproject.toml, switchboard/__init__.py, README.md, CHANGELOG.md, switchboard/local/tasks-completed.md
- Version: 1.12.2
- Notes:
  - Root project docs stay tracked in scope and quick review even when `managed_docs` leaves framework writes disabled for `README.md`, `API.md`, and `CHANGELOG.md`.
  - The service page now treats `managed_docs` as a write-policy control instead of implying that disabled project docs are missing or invalid.
  - Project Snapshot now prefers a real project ledger entry when the task list contains both project work and later Switchboard maintenance/bootstrap entries.
  - Node inspect and release-check payloads now carry GitHub release asset metadata so same-version installs can still be identified as exact-match or mismatch.
  - Remote runtime checks now fall back to `unverified` firewall state when a mocked or partial SSH object cannot execute commands, keeping the check resilient during tests.
  - Built the frontend bundle into `switchboard/static/app/` and produced the `dist/switchboard-1.12.2-py3-none-any.whl` package artifact.
