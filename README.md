# Switchboard

Switchboard is a control-center-first framework for managing project workspaces, service roots, server pulls, runtime checks, repo actions, and standardized node documentation.

`v0.1.x` keeps the product focused on the control center. Node mode is packaged and documented now so the first real node can be deployed cleanly, but node rollout is still secondary to the control-center workflow.

## What v0.1.x Includes

- a FastAPI backend for service discovery, pulls, runtime checks, repo actions, and manual node sync
- a React control-center UI for workspaces, services, scope editing, bundle pulls, runtime config, and node sync actions
- a Python CLI for control-center tasks, node install/snapshot/serve, and release builds
- a standardized `switchboard/` node pack for future project roots
- control-center-only sync: nodes never call back into the control center on their own

## Stack

- Python 3.12+
- FastAPI
- Pydantic Settings
- Paramiko for SSH/SFTP
- Typer CLI
- React 19
- Vite
- TypeScript
- Tailwind
- `uv` for packaging and node installation
- Git for repo status and version metadata

## Repo Layout

```text
switchboard/           Python backend, CLI, collectors, node mode
src/                   React control-center UI
src/data/              checked-in offline fallback data for the UI
documentation/         public framework docs
tests/                 frontend tests
tests_backend/         backend tests
framework.sh           combined start/stop/status/logs runner
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

Create `.env` from `.env.example`:

```bash
cp .env.example .env
```

Add server credentials using the `SWITCHBOARD_SERVER_<SERVER_ID>_*` naming pattern.

Example:

```dotenv
SWITCHBOARD_SERVER_PESU_DEV_47_HOST=192.168.3.47
SWITCHBOARD_SERVER_PESU_DEV_47_USERNAME=pesu
SWITCHBOARD_SERVER_PESU_DEV_47_PORT=22
SWITCHBOARD_SERVER_PESU_DEV_47_PASSWORD=
```

Current server definitions live in:

- `switchboard/manifests/servers.json`
- `switchboard/manifests/workspaces.json`

In `v0.1.x`, servers and workspaces are still manifest-driven. Services are added from the control-center UI.

Start the framework:

```bash
./run.sh
```

`run.sh` / `start.sh` is the simple entrypoint. It asks which mode to start and then runs the correct control-center or node command.

If you want the direct control-center runner without prompts:

```bash
./framework.sh start
./framework.sh status
./framework.sh logs
```

Default local URLs:

- UI: `http://127.0.0.1:5173`
- API: `http://127.0.0.1:8009/api/health`

More detail is in [documentation/control-center-setup.md](documentation/control-center-setup.md).

## How Control Center Configuration Works

### Servers

- server identity is defined in `switchboard/manifests/servers.json`
- credentials are resolved from `.env`, `.env.local`, or runtime password overrides
- Switchboard stores host, username, and port in manifests
- passwords stay local in env files or request payloads

### Workspaces

- workspaces are umbrella groups defined in `switchboard/manifests/workspaces.json`
- each workspace lists its allowed server ids
- service cards in the UI are scoped by workspace

### Services and Project Roots

- services are stored in `switchboard/manifests/services.json`
- the control center can add services from the UI by choosing:
  - workspace
  - server
  - root path
  - selected scope entries
- scope entries define what is treated as:
  - `repo`
  - `doc`
  - `log`
  - `exclude`

## Runtime Config

Runtime config lives per location, not per service.

Each location can store:

- expected ports
- a raw health-check command
- a run-command hint
- monitoring mode: `manual`, `detect`, or `node_managed`
- runtime notes

In `v0.1.x`:

- process-command detection is best effort only
- the manual run-command hint remains first-class
- health checks are operator-managed raw commands, usually `curl ...`

The UI exposes runtime config in two places:

- service creation flow
- service detail page

The service detail page also exposes:

- `Run Runtime Check`
- `Sync From Node`
- `Sync To Node`

More detail is in [documentation/runtime-monitoring.md](documentation/runtime-monitoring.md).

## Pull Bundles

Pull bundles create a new timestamped local copy every time.

Bundle behavior:

- starts from the saved scope
- allows one-run extra includes and excludes
- preserves the original relative source tree under the bundle root
- records file metadata and checksums
- records repo metadata when the pulled paths overlap a tracked repo

Local bundle layout:

```text
downloads/<workspace>/<service>/<bundle_id>/
  source_tree/
  bundle-manifest.json
```

## Node Mode

Node mode installs a standardized `switchboard/` folder into a project root.

That folder contains:

- `switchboard/node.manifest.json`
- `switchboard/core/`
- `switchboard/local/`
- `switchboard/evidence/`

Important rules:

- node install does not replace project-owned root docs like `README.md`
- node sync is manual
- node never pushes into the control center
- node never SSHs back to the control-center machine
- sync is always initiated from the control center

See [documentation/node-install-guide.md](documentation/node-install-guide.md).

## Release Flow

Build a wheel from the control-center repo:

```bash
./.venv/bin/switchboard release build --wheel-out release
```

That build:

- runs the React production build
- bundles the static app into the Python package
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

- servers and workspaces are still manifest-driven
- node registration back into the control center is manual
- secret scanning before push/deploy is deferred to a later sub-version
- runtime checks are manual or best-effort, not a full monitoring system
- task management and multi-project reporting are not in the dashboard yet

## Planned for v2

- day-wise task views across projects
- project and workspace task calendar views
- richer agent activity dashboards
- broader project-management reporting across nodes and control center
- stronger deploy-readiness and cross-project workflow views

## Public Docs

- [documentation/control-center-setup.md](documentation/control-center-setup.md)
- [documentation/runtime-monitoring.md](documentation/runtime-monitoring.md)
- [documentation/node-install-guide.md](documentation/node-install-guide.md)
- [documentation/switchboard-design-principles.md](documentation/switchboard-design-principles.md)
- [documentation/switchboard-doc-structure-rules.md](documentation/switchboard-doc-structure-rules.md)
- [CHANGELOG.md](CHANGELOG.md)
