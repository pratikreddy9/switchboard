# Control Center Setup

## Purpose

This is the operator setup flow for a fresh Switchboard control-center install.

## 1. Clone The Repo

```bash
git clone https://github.com/pratikreddy9/switchboard.git
cd switchboard
```

## 2. Create The Python Environment

```bash
python3 -m venv .venv
./.venv/bin/pip install -e .
```

`uv` is also fine, but the product boundary is still the Python package.

## 3. Install Frontend Dependencies

```bash
npm install
```

## 4. Create `.env`

```bash
cp .env.example .env
```

Credential key pattern:

```text
SWITCHBOARD_SERVER_<SERVER_ID>_HOST
SWITCHBOARD_SERVER_<SERVER_ID>_USERNAME
SWITCHBOARD_SERVER_<SERVER_ID>_PORT
SWITCHBOARD_SERVER_<SERVER_ID>_PASSWORD
```

Example:

```dotenv
SWITCHBOARD_SERVER_ZAPP_TEST_114_HOST=148.66.152.114
SWITCHBOARD_SERVER_ZAPP_TEST_114_USERNAME=zappadmin
SWITCHBOARD_SERVER_ZAPP_TEST_114_PORT=22
SWITCHBOARD_SERVER_ZAPP_TEST_114_PASSWORD=
```

## 5. Check Manifest Definitions

Current `v0.1.x` behavior:

- servers are defined in `switchboard/manifests/servers.json`
- workspaces are defined in `switchboard/manifests/workspaces.json`
- services are stored in `switchboard/manifests/services.json`

Server/workspace registration is still manifest-driven in this version.

## 6. Start The Framework

Preferred prompt-driven entrypoint:

```bash
./run.sh
```

Direct runner:

```bash
./framework.sh start
./framework.sh status
./framework.sh logs
```

Direct processes:

```bash
./.venv/bin/python -m uvicorn switchboard.api:app --host 127.0.0.1 --port 8009
npm run dev -- --host 127.0.0.1 --port 5173
```

## 7. Open The Dashboard

- UI: `http://127.0.0.1:5173`
- API: `http://127.0.0.1:8009/api/health`

## 8. Add A Project

From the workspace page:

1. open `Add Project`
2. choose the workspace
3. choose a workspace server
4. enter the project root path
5. browse the path tree
6. keep or deselect paths
7. assign `repo`, `doc`, `log`, or `exclude`
8. save runtime config for the location
9. save the service

## 9. Configure Runtime And Docs

After a service exists, the service page lets you:

- edit per-location runtime config
- edit saved scope
- edit managed-doc configuration
- run runtime checks
- sync from node
- sync to node
- create pull bundles

## 10. Sync Direction Rule

Sync is manual and control-center initiated only.

- nodes do not call back into the control center
- nodes do not SSH into the control-center machine
- the control center pulls from or writes to nodes on demand

## 11. Canonical Doc Rule

The control center should assume node-side agents normally edit only:

```text
switchboard/local/tasks-completed.md
```

and then run:

```bash
switchboard node snapshot --project-root <path>
```

That is how derived docs and evidence stay aligned in `v0.1.7`.
