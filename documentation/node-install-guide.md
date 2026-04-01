# Node Install Guide

## Purpose

This guide explains how to install a Switchboard node into a project root and how that node interacts with the control center.

In `v0.1.x`, node mode is real and installable, but still secondary to the control center.

## Important Direction Rule

Node sync is manual and control-center initiated.

- the node does not push back into the control center
- the node does not SSH into the control-center machine
- the control center pulls from or writes to the node when needed

## What A Node Installs

A node install creates only one top-level folder inside the project root:

```text
<project-root>/
  switchboard/
    node.manifest.json
    core/
    local/
    evidence/
```

It does not replace project-owned root files like:

- `README.md`
- `api.md`
- existing local docs outside `switchboard/`

## Release The Package From The Control Center Repo

From the framework repo:

```bash
cd /Users/p/Desktop/dashboard
./.venv/bin/switchboard release build --wheel-out release
```

That build:

1. builds the React UI
2. bundles static frontend assets into the Python package
3. builds a Python wheel for node installation

Example output:

```text
release/switchboard-0.1.2-py3-none-any.whl
```

## Publish The Release

Recommended path:

1. push the repo to GitHub
2. create a GitHub Release
3. attach the wheel asset

Example:

```bash
gh release create v0.1.2 release/switchboard-0.1.2-py3-none-any.whl \
  --title "Switchboard v0.1.2" \
  --notes "Simple startup launcher and node runtime commands."
```

## Install A Node Tool On The Target Machine

Prerequisites:

- Python available
- `uv` installed
- Git available
- access to the wheel asset

Install in one step:

```bash
uv tool install /path/to/switchboard-0.1.2-py3-none-any.whl --force
```

That installs the `switchboard` CLI and all Python dependencies. No `npm` install is needed on the node machine.

## Plant The Node In A Project Root

Example:

```bash
switchboard node install \
  --project-root /Users/p/Desktop/work/zapp/lambdascripts \
  --service-id lambdascripts \
  --display-name "Lambda Scripts"
```

This creates the standard node pack.

## Update Node Docs After Work

The canonical runtime-edited file is:

```text
switchboard/local/tasks-completed.md
```

After updates, regenerate derived files:

```bash
switchboard node snapshot --project-root /Users/p/Desktop/work/zapp/lambdascripts
```

That regenerates local derived docs and evidence JSON.

## Start The Node

The simple startup path is the generated node script:

```bash
./switchboard/start.sh
```

It asks only for host and port, then starts the node in the background and writes:

- `switchboard/runtime/node.pid`
- `switchboard/runtime/node.log`

You can also use the package commands directly:

```bash
switchboard node start --project-root /Users/p/Desktop/work/zapp/lambdascripts --host 127.0.0.1 --port 8010
switchboard node status --project-root /Users/p/Desktop/work/zapp/lambdascripts --port 8010
switchboard node logs --project-root /Users/p/Desktop/work/zapp/lambdascripts
switchboard node stop --project-root /Users/p/Desktop/work/zapp/lambdascripts --port 8010
```

## Optional Foreground Node UI/API

If you want the node’s minimal local status view:

```bash
switchboard node serve \
  --project-root /Users/p/Desktop/work/zapp/lambdascripts \
  --host 127.0.0.1 \
  --port 8010
```

Use `node serve` only when you explicitly want foreground mode in the terminal.

Useful endpoints:

- `GET /api/health`
- `GET /api/node`
- `POST /api/node/snapshot`

The root page exposes a minimal local dashboard for:

- node identity
- docs pack presence
- current scope snapshot
- runtime config
- last snapshot timestamp

## Control Center Detection Flow

In `v0.1.x`, node pickup is still manual:

1. install the node into the real project root
2. open the control center
3. add that project root as a service location
4. include the relevant project files plus the `switchboard/` folder
5. use:
   - `Sync From Node`
   - `Sync To Node`
   - `Run Runtime Check`

Primary node marker file:

```text
switchboard/node.manifest.json
```

## First Test Deployment Flow

For the first real test:

1. build the wheel from the control-center repo
2. install the tool on the target machine
3. plant a node into the chosen project root
4. optionally run the node UI/API locally
5. add that project in the control center
6. confirm the node manifest is visible in scope
7. run `Sync From Node`
8. edit runtime config in the control center
9. run `Sync To Node`
10. verify both sides reflect the change
