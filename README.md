# Switchboard

Switchboard is a framework-first control center for managing project workspaces, servers, pull bundles, and standardized node documentation.

Version 1 is centered on the control center. Node mode is defined and packaged, but rollout into project roots is intentionally secondary until the control center workflow is stable.

## What It Does

- tracks workspaces, services, and servers from explicit manifests
- browses project paths and saves editable scope entries
- pulls versioned bundles while preserving the source tree
- exposes repo actions such as status and guarded pull flows
- standardizes future project nodes under a dedicated `switchboard/` folder
- packages the React UI into the Python release for node-mode serving

## Modes

### Control Center

Runs on the main machine and provides:

- the dashboard UI
- the FastAPI backend
- workspace and service manifests
- pull bundle history
- dashboard-safe evidence snapshots

### Node

Installs inside a project root and creates:

- `switchboard/node.manifest.json`
- `switchboard/core/` for package-owned docs and prompts
- `switchboard/local/` for project-maintained runtime notes
- `switchboard/evidence/` for machine-readable node outputs

## Stack

- Python 3.12+
- FastAPI
- Paramiko
- Typer
- React
- Vite
- TypeScript
- `uv` for packaging and tool installation

## Repo Layout

```text
switchboard/         Python backend, CLI, collectors, node mode
src/                 React control-center UI
documentation/       Framework docs
tests/               Frontend tests
tests_backend/       Backend tests
framework.sh         Runner for backend + frontend
pyproject.toml       Python package definition
package.json         Frontend build definition
```

## Local Development

Backend:

```bash
./.venv/bin/python -m uvicorn switchboard.api:app --host 127.0.0.1 --port 8009
```

Frontend:

```bash
npm run dev -- --host 127.0.0.1 --port 5173
```

Combined runner:

```bash
./framework.sh start
./framework.sh status
./framework.sh logs
```

## Tests

Backend:

```bash
./.venv/bin/python -m unittest discover -s tests_backend -p '*.py'
```

Frontend:

```bash
npm test
npm run build
```

## Build A Release

```bash
./.venv/bin/switchboard release build --wheel-out release
```

This builds the React app, bundles the static UI into the Python package, and writes a wheel into `release/`.

## Install A Node

After downloading a release wheel onto a target machine:

```bash
uv tool install /path/to/switchboard-0.1.0-py3-none-any.whl --force

switchboard node install \
  --project-root /path/to/project \
  --service-id my-service \
  --display-name "My Service"
```

More detail is in [documentation/node-install-guide.md](documentation/node-install-guide.md).

## Current v1 Constraints

- control-center first, node rollout second
- workspace and service discovery is manifest-driven, not broad filesystem crawling
- automatic node registration back into the control center is not the primary v1 path yet
- sensitive files are tracked by path metadata only, not by content
