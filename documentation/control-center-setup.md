# Control Center Setup

## Purpose

This document is the operator setup flow for a fresh Switchboard control-center install.

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

If you prefer `uv`, that is fine too. The package itself is still the product boundary.

## 3. Install Frontend Dependencies

```bash
npm install
```

## 4. Create `.env`

```bash
cp .env.example .env
```

Fill the server-specific values you want the control center to use locally.

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

## 5. Check Server And Workspace Definitions

Current v0.1.x behavior:

- servers are defined in `switchboard/manifests/servers.json`
- workspaces are defined in `switchboard/manifests/workspaces.json`
- services are stored in `switchboard/manifests/services.json`

The control-center UI can add services. Server and workspace registration is still manifest-driven in this version.

## 6. Start The Framework

Combined runner:

```bash
./run.sh
```

That prompt-driven entrypoint is the preferred v0.1.x startup path.

Direct control-center runner commands are still available:

```bash
./framework.sh start
./framework.sh status
./framework.sh logs
```

Direct commands:

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
3. choose one of that workspace’s servers
4. enter the project root path
5. browse the path tree
6. keep or uncheck paths
7. assign categories:
   - `repo`
   - `doc`
   - `log`
   - `exclude`
8. optionally add runtime config:
   - expected ports
   - health-check command
   - run-command hint
   - monitoring mode
   - notes
9. save the service

## 9. Collect, Pull, And Sync

- `Collect` refreshes service state, docs/log indices, repo summaries, and runtime evidence.
- `Pull Bundle` creates a new timestamped local bundle.
- `Run Runtime Check` checks configured ports and health commands.
- `Sync From Node` pulls node manifest and node evidence into the control center.
- `Sync To Node` writes selected control-center config back into the node files.

## 10. Important Direction Rule

Sync is manual and control-center initiated only.

- nodes do not call back into the control center
- nodes do not SSH into the control-center machine
- the control center pulls from or writes to nodes when the operator asks
