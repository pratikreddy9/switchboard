# Local Mac Cutover Postflight

- Generated: 2026-05-03T04:13:38Z
- Manager root: `/Users/p/Desktop/dashboard`
- Manager port: `8010`
- Manager PID after restart: `13908`
- Archive root: `switchboard/manager/archives/2026-05-03T04-13-24+00-00--old-node-scaffolding`

## Runtime
- One Switchboard manager is listening on `127.0.0.1:8010`.
- No old per-project Switchboard node listener was found on `870x`, `871x`, or `8720`.
- Project node scaffolding status after archive:
  - `switchboard/runtime`: absent for all six registered roots.
  - `switchboard/start.sh`: absent for all six registered roots.
  - `switchboard/run.sh`: absent for all six registered roots.

## Registered Roots
- `adaptive_learning`: ok
- `dashboard_core`: ok
- `finance`: ok
- `lambdalogger`: ok
- `lambdascripts`: ok
- `unionbank_service`: ok

## Verification
- `uv run --with pytest python -m pytest tests_backend/test_node_mode.py tests_backend/test_runtime_and_node_sync.py -q`: 16 passed.
- `switchboard node manager-verify-all --manager-root /Users/p/Desktop/dashboard`: ok.
- `curl http://127.0.0.1:8010/api/health`: ok, mode `manager`, root count 6.
- `uv tool install --force --reinstall --no-cache /Users/p/Desktop/dashboard`: completed, then manager restarted.

## Safety
- Old scaffold files were moved into the manager archive.
- `switchboard/core`, `switchboard/local`, `switchboard/evidence`, `switchboard/node.manifest.json`, and agent contract files were preserved.
- The incidental `uv.lock` created during test setup was moved into the ignored archive, not deleted.
