# Switchboard

Switchboard is a control-center-first framework for managing project workspaces, server pulls, runtime checks, repo actions, versioned pull bundles, and standardized per-project node docs.

`v0.1.7` keeps the product simple:

- the control center is the main product
- node mode is installable and usable
- sync is manual and control-center initiated
- project/task dashboards across all nodes are deferred to `v2`

## What v0.1.7 Adds

- one canonical node update file: `switchboard/local/tasks-completed.md`
- one primary rulebook: `switchboard/core/playbook.md`
- deterministic snapshot regeneration of:
  - `switchboard/local/control-center-handoff.md`
  - `switchboard/local/runbook.md`
  - `switchboard/local/approach-history.md`
  - `switchboard/local/doc-index.md`
  - `switchboard/evidence/completed-tasks.json`
  - `switchboard/evidence/scope.snapshot.json`
  - `switchboard/evidence/doc-index.json`
  - runtime/doc-index mirrors in `switchboard/node.manifest.json`
- opt-in framework-managed root docs:
  - `README.md`
  - `API.md`
  - `CHANGELOG.md`

## Stack

- Python 3.12+
- FastAPI
- Paramiko for SSH/SFTP
- Typer CLI
- React 19
- Vite
- TypeScript
- Tailwind
- `uv` for wheel-based node installs
- Git for repo state and version metadata

## Repo Layout

```text
switchboard/           Python backend, CLI, node mode, snapshot logic
src/                   React control-center UI
src/data/              checked-in offline fallback data for the UI
documentation/         public framework docs
tests/                 frontend tests
tests_backend/         backend tests
framework.sh           combined control-center process runner
run.sh                 simple interactive launcher
pyproject.toml         Python package metadata
package.json           frontend package metadata
```

## Control Center Setup

Fresh clone:

```bash
git clone https://github.com/pratikreddy9/switchboard.git
cd switchboard
python3 -m venv .venv
./.venv/bin/pip install -e .
npm install
```

Create local env:

```bash
cp .env.example .env
```

Use this key pattern:

```text
SWITCHBOARD_SERVER_<SERVER_ID>_HOST
SWITCHBOARD_SERVER_<SERVER_ID>_USERNAME
SWITCHBOARD_SERVER_<SERVER_ID>_PORT
SWITCHBOARD_SERVER_<SERVER_ID>_PASSWORD
```

Example:

```dotenv
SWITCHBOARD_SERVER_PESU_DEV_47_HOST=192.168.3.47
SWITCHBOARD_SERVER_PESU_DEV_47_USERNAME=pesu
SWITCHBOARD_SERVER_PESU_DEV_47_PORT=22
SWITCHBOARD_SERVER_PESU_DEV_47_PASSWORD=
```

Current server/workspace manifests:

- `switchboard/manifests/servers.json`
- `switchboard/manifests/workspaces.json`
- `switchboard/manifests/services.json`

Start the framework:

```bash
./run.sh
```

Direct runner:

```bash
./framework.sh start
./framework.sh status
./framework.sh logs
```

Default local URLs:

- UI: `http://127.0.0.1:5173`
- API: `http://127.0.0.1:8009/api/health`

Detailed operator flow:

- [documentation/control-center-setup.md](documentation/control-center-setup.md)

## Control Center Configuration Model

### Servers

- server identity lives in `switchboard/manifests/servers.json`
- credentials resolve from `.env`, `.env.local`, or runtime overrides
- passwords stay local and untracked

### Workspaces

- workspaces group servers and services
- the workspace list is still manifest-driven in `v0.1.x`

### Services

Services are added in the control center by:

1. choosing a workspace
2. choosing a server/location
3. entering a root path
4. selecting scope
5. saving runtime config

Scope categories are:

- `repo`
- `doc`
- `log`
- `exclude`

Each service also carries:

- per-location runtime config
- managed-doc config
- repo policies
- bundle history

## Runtime Config

Runtime config is stored per location.

Each location can carry:

- expected ports
- health-check command
- run-command hint
- monitoring mode
- runtime notes

The control center can:

- run runtime checks
- sync runtime config from node
- sync runtime config to node

See:

- [documentation/runtime-monitoring.md](documentation/runtime-monitoring.md)

## Canonical Node Doc Flow

Normal agent work should update only:

```text
switchboard/local/tasks-completed.md
```

Then run:

```bash
switchboard node snapshot --project-root <path>
```

That snapshot regenerates the framework-owned derived docs and evidence.

The primary agent rulebook is:

```text
switchboard/core/playbook.md
```

Compatibility files like:

- `design-principles.md`
- `doc-structure-rules.md`
- `agent-instructions.md`
- bootstrap/runtime prompt files

remain present, but the playbook is the primary authority.

## Managed Root Docs

Root project docs can be framework-managed, but only when enabled in:

```text
switchboard/node.manifest.json
```

Managed doc ids:

- `readme`
- `api`
- `changelog`
- `handoff`
- `runbook`
- `approach_history`
- `doc_index_md`
- `doc_index_json`

Default:

- enabled:
  - `handoff`
  - `runbook`
  - `approach_history`
  - `doc_index_md`
  - `doc_index_json`
- disabled:
  - `readme`
  - `api`
  - `changelog`

If a root doc is disabled, Switchboard must not rewrite it.

## Node Mode

Node mode installs a standard `switchboard/` folder into a project root.

Important rules:

- node install does not replace existing project root docs by default
- node never pushes into the control center
- node never SSHs into the control-center machine
- sync is always initiated from the control center

Node install/update details:

- [documentation/node-install-guide.md](documentation/node-install-guide.md)

## Pull Bundles

Every pull is a new bundle.

Bundle behavior:

- starts from saved scope
- supports one-run extra includes and excludes
- preserves the original relative source tree
- writes a bundle manifest with file metadata and checksums
- keeps history for later comparison

Local layout:

```text
downloads/<workspace>/<service>/<bundle_id>/
  source_tree/
  bundle-manifest.json
```

## Release Flow

Build a wheel:

```bash
./.venv/bin/switchboard release build --wheel-out release
```

That release build:

- runs the React production build
- bundles the static frontend into the Python package
- builds a wheel for `uv tool install`

## Tests

Backend:

```bash
python3 -m compileall switchboard tests_backend
./.venv/bin/python -m unittest discover -s tests_backend -p '*.py'
```

Frontend:

```bash
npm run build
npm test
```

## v0.1.x Limits

- server and workspace registration are still manifest-driven
- sync is manual and control-center initiated only
- runtime checks are best-effort, not full monitoring
- repo safety/deploy readiness is still incomplete
- cross-project task dashboards, day-wise task calendars, and broader project-management views are `v2` work

## v2 Direction

Switchboard is ultimately meant to become a project-management dashboard across agents, tasks, and projects.

That broader common-view layer is intentionally out of scope for `v0.1.x`. The goal here is to make the control center and node contract clean enough that `v2` can build on reliable pulled data instead of ad hoc docs.
