# Local Mac Cutover Preflight

- Generated: 2026-05-03T04:08:43Z
- Manager root: `/Users/p/Desktop/dashboard`
- Planned manager port: `8010`
- Adaptive root: `/Users/p/Desktop/work/adaptivelearning`

## Read Back
- Pratik wanted the local Mac moved to the same one-manager-node model as `.47`.
- Adaptivelearning must be enrolled as a minion without overwriting existing app work.
- Cleanup must move or archive old node scaffolding; nothing should be deleted.

## Starting State
- No active Switchboard listener was found on `8010`, `870x`, `871x`, or `8720`.
- `/Users/p/Desktop/dashboard/switchboard/manager.manifest.json` did not exist before the cutover.
- Existing root manifests selected for registration:
  - `/Users/p/Desktop/dashboard`
  - `/Users/p/Desktop/main/statements`
  - `/Users/p/Desktop/main/statements/unionbank_service`
  - `/Users/p/Desktop/work/zapp/lambdalogger`
  - `/Users/p/Desktop/work/zapp/lambdascripts`
- Stale/downloaded manifests were intentionally ignored:
  - `/Users/p/Desktop/dashboard/downloads/**/switchboard/node.manifest.json`
  - `/Users/p/Desktop/main/statements/switchboard/switchboard/node.manifest.json`

## Protected Work
- Adaptivelearning had existing uncommitted app edits before enrollment:
  - `backend/content.py`
  - `backend/test_mapper_contract.py`
- Those files were not edited by the Switchboard cutover.
