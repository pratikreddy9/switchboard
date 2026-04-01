# Runtime Monitoring

## Purpose

Runtime config in `v0.1.x` is a per-location operator-managed layer. It is not a full monitoring platform.

## Runtime Config Fields

Each service location can store:

- `expected_ports`
- `healthcheck_command`
- `run_command_hint`
- `monitoring_mode`
- `notes`

## Monitoring Modes

- `manual`
  Use configured data only. Best when you mainly want reminders and a manual health command.
- `detect`
  Switchboard will try to detect live listeners and process commands from the control center.
- `node_managed`
  Use when the node is expected to mirror and maintain runtime details locally, with manual sync back to the control center.

## Health Check Commands

Health checks are raw operator-managed commands in `v0.1.x`.

Typical pattern:

```bash
curl -fsS http://127.0.0.1:8000/health
```

Important:

- the command is stored as configuration
- the command is executed from the selected location context
- Switchboard does not attempt to interpret every command shape

## Run Command Hints

Run-command detection is best effort only.

Switchboard may be able to infer a process command from a detected PID, but this is not guaranteed.

That is why `run_command_hint` remains a first-class field. Use it to record the operator-known command or startup hint.

Examples:

```text
uvicorn main:app --host 0.0.0.0 --port 8000
python logging_service.py
streamlit run app.py --server.port 8503
```

## Control Center Checks vs Node Data

Two sources can inform runtime status:

### Control-center runtime check

- runs from the control center
- uses local or SSH access
- checks open ports
- runs the configured health command
- may detect a process command

### Node-reported runtime config

- stored in `switchboard/node.manifest.json`
- synced manually into or out of the control center
- useful when the local project node is treated as the more accurate runtime owner

## Conflict Rule In v0.1.x

- sync is manual
- last write wins
- timestamp and direction are recorded
- there is no automatic merge logic yet

## What The Service Page Shows

For each location, the UI shows:

- configured ports
- detected live ports
- missing configured ports
- health-check status
- detected process command if available
- saved run-command hint
- node presence
- latest node sync record

## What This Is Not Yet

This is not a full daemonized monitor with alerting, historical charts, or automatic remediation.

Those broader operational views belong in later versions.
