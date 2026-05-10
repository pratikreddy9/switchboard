# Node Install Guide

## Purpose

This guide explains how to install a Switchboard node into a project root and how that node interacts with the control center.

Node mode is now manager-first. A machine should run one manager, and project roots should act as thin minion roots.

## Direction Rule

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
    local/
    evidence/
```

Standalone nodes may still have `switchboard/core/`, but manager-owned minion roots inherit common rules from the manager and do not need every CLI-specific agent file.

## Core Node Files

Manager-owned common rulebook:

```text
<manager-root>/switchboard/core/playbook.md
```

Canonical editable file:

```text
switchboard/local/tasks-completed.md
```

Derived files:

- `switchboard/local/control-center-handoff.md`
- `switchboard/local/runbook.md`
- `switchboard/local/approach-history.md`
- `switchboard/local/doc-index.md`
- `switchboard/evidence/completed-tasks.json`
- `switchboard/evidence/scope.snapshot.json`
- `switchboard/evidence/doc-index.json`

## Release The Package

From the control-center repo:

```bash
cd /Users/p/Desktop/dashboard
./.venv/bin/switchboard release build --wheel-out release
```

That build:

1. builds the React UI
2. bundles static frontend assets into the Python package
3. builds a Python wheel for node installation

## Publish The Release

Example:

```bash
gh release create v1.12.5 release/switchboard-1.12.5-py3-none-any.whl \
  --title "Switchboard v1.12.5" \
  --notes "Product normalization, manager-owned contracts, and pull-bundle preflight."
```

## Install The Node Tool

Prerequisites:

- Python available
- `uv` installed
- Git available
- access to the release wheel

Install:

```bash
uv tool install /path/to/switchboard-1.12.5-py3-none-any.whl --force
```

No `npm install` is needed on the node machine.

## Plant The Node

Example:

```bash
switchboard node normalize-root \
  --manager-root /Users/p/Desktop/dashboard \
  --project-root /Users/p/Desktop/work/zapp/lambdascripts \
  --root-id lambdascripts \
  --service-id lambdascripts \
  --display-name "Lambda Scripts"
```

## Normal Agent Workflow

Agents should:

1. read `switchboard/core/playbook.md`
2. edit only `switchboard/local/tasks-completed.md` during normal work
3. run:

```bash
switchboard node snapshot --project-root /Users/p/Desktop/work/zapp/lambdascripts
```

Agents should not hand-edit derived docs unless explicitly instructed.

## Managed Root Docs

Framework-managed root docs are configured in:

```text
switchboard/node.manifest.json
```

Supported doc ids:

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

If a root doc is disabled, snapshot must not rewrite it.

## Start The Node

Simple startup path:

```bash
./switchboard/start.sh
```

That asks for host and port, starts the node in the background, and writes:

- `switchboard/runtime/node.pid`
- `switchboard/runtime/node.log`

Direct commands are also available:

```bash
switchboard node start --project-root /Users/p/Desktop/work/zapp/lambdascripts --host 127.0.0.1 --port 8010
switchboard node status --project-root /Users/p/Desktop/work/zapp/lambdascripts --port 8010
switchboard node logs --project-root /Users/p/Desktop/work/zapp/lambdascripts
switchboard node stop --project-root /Users/p/Desktop/work/zapp/lambdascripts --port 8010
```

## Local Node UI/API

Useful endpoints:

- `GET /`
- `GET /api/health`
- `GET /api/node`
- `POST /api/node/snapshot`

The node view shows:

- node identity
- runtime config
- scope snapshot status
- managed docs status
- doc-index status
- mirrored pull-bundle history

## Control Center Detection Flow

Manager registration is explicit:

1. run `switchboard node normalize-root` from the manager context
2. open the control center
3. confirm the project root appears as a manager-owned service location
4. run `Sync From Node` before pull-bundle creation
5. use:
   - `Sync From Node`
   - `Run Runtime Check`

Primary node marker file:

```text
switchboard/node.manifest.json
```
