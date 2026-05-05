# Control Center Handoff

## 2026-04-06T15:30:38+00:00 | Fix self-conflicting sync and bundle locks
- Tags: task, handoff
- Summary: Removed duplicate client-side action locks that were causing sync and pull-bundle requests to report themselves as already running.
- Changed Paths: src/pages/ServiceDetailPage.tsx, src/components/PullBundlePanel.tsx, switchboard/api.py, switchboard/storage.py, tests_backend/test_backend_regressions.py, package.json, pyproject.toml, switchboard/__init__.py, README.md, CHANGELOG.md, switchboard/local/tasks-completed.md
- Version: 1.12.1
- Notes:
  - - `sync_from_node` and `sync_to_node` now rely on the backend action guard instead of pre-acquiring the same lock in the browser.
  - - Pull bundle creation now uses backend lock state for reconciliation instead of creating a second conflicting lock from the UI.
  - - `action_in_progress` now maps to HTTP 409 so real lock conflicts surface as API errors instead of HTTP 200 responses.
  - - Runtime cache writes now use atomic file replacement so `/action-locks` polling does not hit transient JSON decode failures during concurrent writes.
  - - Verified the frontend production build and confirmed the backend now returns 409 for a forced `sync_from_node` lock collision after restart.

## 2026-04-07T04:01:16Z | Recenter service pages on the tracked project
- Tags: task, handoff, scope
- Summary: Shifted the control center back to project-first context by clarifying project-doc ownership, surfacing project history ahead of framework maintenance, and tightening exact node release checks.
- Changed Paths: src/pages/ServiceDetailPage.tsx, src/components/TaskLedgerPanel.tsx, src/components/ConfirmationModal.tsx, src/api/client.ts, src/types/switchboard.ts, src/App.tsx, switchboard/collectors.py, switchboard/models.py, switchboard/node.py, tests_backend/test_runtime_and_node_sync.py, documentation/switchboard-design-principles.md, package.json, pyproject.toml, switchboard/__init__.py, README.md, CHANGELOG.md, switchboard/local/tasks-completed.md
- Version: 1.12.2
- Notes:
  - - Root project docs stay tracked in scope and quick review even when `managed_docs` leaves framework writes disabled for `README.md`, `API.md`, and `CHANGELOG.md`.
  - - The service page now treats `managed_docs` as a write-policy control instead of implying that disabled project docs are missing or invalid.
  - - Project Snapshot now prefers a real project ledger entry when the task list contains both project work and later Switchboard maintenance/bootstrap entries.
  - - Node inspect and release-check payloads now carry GitHub release asset metadata so same-version installs can still be identified as exact-match or mismatch.
  - - Remote runtime checks now fall back to `unverified` firewall state when a mocked or partial SSH object cannot execute commands, keeping the check resilient during tests.
  - - Built the frontend bundle into `switchboard/static/app/` and produced the `dist/switchboard-1.12.2-py3-none-any.whl` package artifact.

## 2026-04-29T08:57:34Z | Add Switchboard agent update gate
- Tags: task, handoff, scope
- Summary: Added the shared agent contract and verify-update gate so Switchboard updates require read-back, scope check, snapshot, and verification.
- Changed Paths: switchboard/node.py, switchboard/cli.py, tests_backend/test_node_mode.py, documentation/switchboard-roadmap.md, switchboard/local/tasks-completed.md
- Agent: Codex
- Tool: codex-cli
- Read Back: Confirmed this is the foundation normalization slice, not the full roadmap.
- Scope Check: Normalized the local Switchboard pull scope so generated/cache/secret paths are excluded.
- Notes:
  - - Generated agent instructions cover Codex, Claude Code, Gemini CLI, Qwen Code, opencode, and generic agents.
  - - Local build, wheel build, focused backend tests, commit, push, and service restart were completed.
  - - The .47 server was not reachable over SSH from this machine, so remote normalization remains blocked on network/VPN access.
- Scope Entries:
  - repo | dir | /Users/p/Desktop/dashboard | true
  - doc | dir | /Users/p/Desktop/dashboard/docs | true
  - doc | dir | /Users/p/Desktop/dashboard/documentation | true
  - doc | dir | /Users/p/Desktop/dashboard/scripts | true
  - doc | dir | /Users/p/Desktop/dashboard/src | true
  - doc | dir | /Users/p/Desktop/dashboard/switchboard | true
  - doc | dir | /Users/p/Desktop/dashboard/tests | true
  - doc | dir | /Users/p/Desktop/dashboard/tests_backend | true
  - doc | file | /Users/p/Desktop/dashboard/README.md | true
  - doc | file | /Users/p/Desktop/dashboard/CHANGELOG.md | true
  - doc | file | /Users/p/Desktop/dashboard/MANIFEST.in | true
  - doc | file | /Users/p/Desktop/dashboard/package-lock.json | true
  - doc | file | /Users/p/Desktop/dashboard/package.json | true
  - doc | file | /Users/p/Desktop/dashboard/pyproject.toml | true
  - doc | file | /Users/p/Desktop/dashboard/tsconfig.json | true
  - doc | file | /Users/p/Desktop/dashboard/tsconfig.test.json | true
  - exclude | dir | /Users/p/Desktop/dashboard/.git | true
  - exclude | dir | /Users/p/Desktop/dashboard/.venv | true
  - exclude | dir | /Users/p/Desktop/dashboard/.claude | true
  - exclude | dir | /Users/p/Desktop/dashboard/.npm-cache | true
  - exclude | dir | /Users/p/Desktop/dashboard/.pytest_cache | true
  - exclude | dir | /Users/p/Desktop/dashboard/build | true
  - exclude | dir | /Users/p/Desktop/dashboard/dist | true
  - exclude | dir | /Users/p/Desktop/dashboard/downloads | true
  - exclude | dir | /Users/p/Desktop/dashboard/logs | true
  - exclude | dir | /Users/p/Desktop/dashboard/node_modules | true
  - exclude | dir | /Users/p/Desktop/dashboard/release | true
  - exclude | dir | /Users/p/Desktop/dashboard/state | true
  - exclude | dir | /Users/p/Desktop/dashboard/switchboard.egg-info | true
  - exclude | file | /Users/p/Desktop/dashboard/.DS_Store | true
  - exclude | file | /Users/p/Desktop/dashboard/.env | true
  - exclude | file | /Users/p/Desktop/dashboard/.npmrc | true

## 2026-04-30T06:13:45Z | Add manager-node cutover foundation
- Tags: task, handoff
- Summary: Added backend manager-node support so one Switchboard process can register, inspect, snapshot, and verify many project roots.
- Changed Paths: switchboard/node.py, switchboard/node_api.py, switchboard/node_runtime.py, switchboard/cli.py, tests_backend/test_node_mode.py, switchboard/local/tasks-completed.md
- Agent: Codex
- Tool: codex-cli
- Read Back: Confirmed the next completion step is a clean .47 manager-node cutover, not UI polish or GitHub backup.
- Scope Check: Project shape did not add new pull roots; existing Switchboard source and tests scope remains valid.
- Notes:
  - - Added manager manifest support with one manager root and many minion project roots.
  - - Added manager API routes for root list, health, manifest, snapshot, and verify-update.
  - - Fixed node status to infer the real node port from process args or manifest instead of defaulting to 8010.
  - - Added machine-readable global and per-project design principle layers to node manifests and generated agent contracts.

## 2026-04-30T09:04:05Z | Repair roadmap and project UX
- Tags: task, handoff
- Summary: Updated the roadmap/design principles to reflect real completion state, fixed Project Grouping service selection, and added deterministic task-ledger project colors.
- Changed Paths: documentation/switchboard-roadmap.md, documentation/switchboard-design-principles.md, src/components/ProjectsPanel.tsx, src/components/TaskLedgerPanel.tsx, switchboard/local/tasks-completed.md
- Agent: Codex
- Tool: codex-cli
- Read Back: Confirmed the next local builder lane is roadmap/design cleanup plus Project Grouping selection and task ledger colors, not .47 migration work.
- Scope Check: No new project roots or pull-bundle scope entries were added; existing documentation and source scopes cover these changes.
- Notes:
  - - Roadmap now marks each original requirement as done, partial, or open.
  - - Project Grouping now exposes an actual available-project selector instead of only a bulk add button.
  - - Task ledger project labels now use stable hash-based color classes so the same project stays visually consistent.

## 2026-05-01T05:57:30Z | Close April 29 Switchboard gaps
- Tags: task, handoff
- Summary: Added pull authority, dependency composition, manager-safe scoped actions, GitHub backup readiness/run support, and an April 29 gap audit.
- Changed Paths: switchboard/collectors.py, switchboard/api.py, switchboard/node.py, switchboard/node_api.py, switchboard/cli.py, switchboard/models.py, switchboard/storage.py, src/api/client.ts, src/components/GitHubBackupPanel.tsx, src/components/PullBundlePanel.tsx, src/components/ProjectsPanel.tsx, src/pages/ControlCenterPage.tsx, src/pages/EnvironmentApiLabPage.tsx, src/types/switchboard.ts, documentation/switchboard-roadmap.md, documentation/switchboard-april29-gap-audit.md, tests_backend/test_backend_regressions.py, tests_backend/test_node_mode.py, switchboard/local/tasks-completed.md
- Agent: Codex
- Tool: codex-cli
- Read Back: Restated that Pratik wants all April 29 requirements closed, with design principles echoed through plan, build, and test.
- Scope Check: Project shape added one UI component and one audit doc; existing source and documentation pull scopes cover them, with no new roots needed.
- Notes:
  - - Pull bundles now record whether authority came from node-local sync or the Control Center.
  - - Dependency views now show language mix, AI %, LLM %, embedding %, and model names from bundle/task evidence.
  - - Manager actions are allowlisted for install, upgrade/release-update, status, snapshot, verify-update, and old-scaffold archive; cleanup moves files instead of deleting.
  - - GitHub backup now has readiness, recorded dry-run, and push-eligible flow for repos with existing credentials.
  - - Verified with frontend tests, frontend build, and backend unittest discovery.

## 2026-05-03T04:10:18Z | Normalize local Mac manager node
- Tags: task, handoff
- Summary: Added manager runtime lifecycle commands and normalized this Mac to one Switchboard manager on port 8010 with six registered roots.
- Changed Paths: .gitignore, switchboard/cli.py, switchboard/node_runtime.py, tests_backend/test_runtime_and_node_sync.py, switchboard/manager.manifest.json, switchboard/manager/reports/20260503-040843-local-mac-cutover/preflight.md, switchboard/manager/reports/20260503-040843-local-mac-cutover/postflight.md, switchboard/manager/reports/20260503-040843-local-mac-cutover/critic.md, switchboard/local/tasks-completed.md
- Agent: Codex
- Tool: codex-cli
- Read Back: Confirmed Pratik wants the local Mac cutover too, not only the .47 server, with adaptivelearning registered safely.
- Scope Check: Project shape stayed within the existing Switchboard source and local metadata scope; no new pull-bundle root was added to dashboard.
- Notes:
  - - Registered dashboard_core, finance, unionbank_service, lambdalogger, lambdascripts, and adaptive_learning under the local manager.
  - - Manager runtime uses switchboard/manager/runtime so old per-project switchboard/runtime folders can be archived without touching the active manager.
  - - Preflight, postflight, and critic reports are stored under switchboard/manager/reports/20260503-040843-local-mac-cutover.

## 2026-05-05T07:01:00Z | Release manager normalization path
- Tags: task, handoff, scope
- Summary: Converted Control Center node actions to the manager-owned normalize path and prepared the 1.12.3 Switchboard release.
- Changed Paths: switchboard/node.py, switchboard/cli.py, switchboard/collectors.py, switchboard/models.py, switchboard/local/tasks-completed.md, switchboard/evidence/update-gate.json, switchboard/manager.manifest.json, switchboard/manifests/services.json, switchboard/manifests/workspaces.json, switchboard/manager/reports/20260505-071500-normalization-release/postflight.md, switchboard/manager/reports/20260505-071500-normalization-release/handoff-47.md, src/pages/ServiceDetailPage.tsx, src/components/ConfirmationModal.tsx, src/api/client.ts, src/types/switchboard.ts, tests_backend/test_node_mode.py, tests_backend/test_runtime_and_node_sync.py, tests_backend/test_backend_regressions.py, README.md, CHANGELOG.md, pyproject.toml, package.json, package-lock.json
- Agent: Codex
- Tool: codex-desktop
- Read Back: Confirmed Pratik wants build, commit, and safe GitHub backup for Switchboard first while keeping one manager port per machine.
- Scope Check: Project shape stayed within existing Switchboard source, UI, tests, manifests, and evidence scope; no new project root was added.
- Version: 1.12.3
- Notes:
  - - Added `switchboard node normalize-root` as the one canonical manager gateway for registration, snapshot, verify-update, manager refresh, and safe archive.
  - - Service-level local install/update/restart now maps to manager register, refresh, and status check instead of creating per-project node runtimes.
  - - Remote service-level node deploy, upgrade, and restart actions are blocked so remote work must happen through the remote manager workflow.
  - - Control Center labels and command previews now match the one-port manager behavior instead of advertising latest GitHub release installs.
- Scope Entries:
  - repo | dir | /Users/p/Desktop/dashboard | true
  - doc | dir | /Users/p/Desktop/dashboard/documentation | true
  - doc | dir | /Users/p/Desktop/dashboard/src | true
  - doc | dir | /Users/p/Desktop/dashboard/switchboard | true
  - doc | dir | /Users/p/Desktop/dashboard/tests_backend | true
  - doc | file | /Users/p/Desktop/dashboard/README.md | true
  - doc | file | /Users/p/Desktop/dashboard/CHANGELOG.md | true
  - doc | file | /Users/p/Desktop/dashboard/package.json | true
  - doc | file | /Users/p/Desktop/dashboard/package-lock.json | true
  - doc | file | /Users/p/Desktop/dashboard/pyproject.toml | true
  - exclude | dir | /Users/p/Desktop/dashboard/.git | true
  - exclude | dir | /Users/p/Desktop/dashboard/.venv | true
  - exclude | dir | /Users/p/Desktop/dashboard/build | true
  - exclude | dir | /Users/p/Desktop/dashboard/dist | true
  - exclude | dir | /Users/p/Desktop/dashboard/downloads | true
  - exclude | dir | /Users/p/Desktop/dashboard/logs | true
  - exclude | dir | /Users/p/Desktop/dashboard/node_modules | true
  - exclude | dir | /Users/p/Desktop/dashboard/release | true
  - exclude | dir | /Users/p/Desktop/dashboard/state | true
