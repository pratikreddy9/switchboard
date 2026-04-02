# Runtime Monitoring

## Purpose

Runtime config in `v0.1.x` is a per-location operator-managed layer. It is not a full monitoring platform.

## Runtime Config Fields

Each location stores:

- `expected_ports`
- `healthcheck_command`
- `run_command_hint`
- `monitoring_mode`
- `notes`

Runtime config belongs to a specific service location, not to the service as a whole.

## Monitoring Modes

- `manual`
  Use saved data only.
- `detect`
  Let the control center try to detect live listeners and process commands.
- `node_managed`
  Use when the node is expected to mirror runtime details locally and the control center syncs them when needed.

## Health Check Commands

Health checks are raw operator-managed commands in `v0.1.x`.

Typical pattern:

```bash
curl -fsS http://127.0.0.1:8000/health
```

Important:

- the command is stored as configuration
- the command is executed from the selected location context
- Switchboard does not try to normalize every command shape

## Run Command Hints

Run-command detection is best effort only.

That is why `run_command_hint` remains first-class. Use it for the operator-known startup hint when process detection is missing or ambiguous.

Examples:

```text
uvicorn main:app --host 0.0.0.0 --port 8000
python logging_service.py
streamlit run app.py --server.port 8503
```

## Control Center Checks vs Node Data

### Control-center runtime check

- runs from the control center
- uses local access or SSH
- checks open ports
- runs the configured health command
- may detect a process command

### Node-reported runtime config

- stored in `switchboard/node.manifest.json`
- updated by `switchboard node snapshot`
- synced manually into or out of the control center

## Conflict Rule In `v0.1.x`

- sync is manual
- last write wins
- timestamps are preserved
- there is no automatic merge logic

## Related Canonical Doc Rule

Runtime config may also be mirrored from the canonical node file flow.

Normal node-side agent work should update:

```text
switchboard/local/tasks-completed.md
```

with a `Runtime:` block, then run:

```bash
switchboard node snapshot --project-root <path>
```

That snapshot mirrors runtime into `switchboard/node.manifest.json`.

## What The Service Page Shows

Per location, the control center can show:

- configured ports
- detected live ports
- missing configured ports
- health-check status
- detected process command
- saved run-command hint
- node presence
- latest node sync result

## What This Is Not Yet

This is not a daemonized monitoring system with alerting, charts, or automatic remediation.

Those views belong in later versions.
