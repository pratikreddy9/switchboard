# Switchboard 1.12.3 Normalization Release Postflight

## Read Back

- Pratik wants Switchboard itself backed up first.
- One machine should have one manager node and one port.
- Local node actions must not recreate per-project runtimes.
- Remote work must happen through the remote manager workflow.
- Cleanup is archive-only; do not delete work.

## Local Result

- Local manager root: `/Users/p/Desktop/dashboard`
- Local manager port: `8010`
- API port: `8009`
- UI port: `5173`
- Registered roots verified: `adaptive_learning`, `dashboard_core`, `finance`, `lambdalogger`, `lambdascripts`, `syspriv`, `unionbank_service`
- `switchboard node manager-verify-all --manager-root /Users/p/Desktop/dashboard` returned `ok`.

## Code Result

- Added `switchboard node normalize-root`.
- Local deploy/update/restart actions now map to manager normalize/refresh/status.
- Remote service-level deploy/update/restart actions return `permission_limited`.
- Control Center command previews now show manager-safe commands.
- Version bumped to `1.12.3`.

## Verification

- Backend focused suite: `31` tests passed.
- Frontend build: `npm run build` passed.
- Dashboard core normalize: `status=ok`, `verify_update=ok`, `archive_status=ok`.

## GitHub Account Routing

- Remote authority: `https://github.com/pratikreddy9/switchboard.git`
- Push target for this release: `pratikreddy9/switchboard`
- Shared attribution can be represented with a `Co-authored-by:` line if Pratik gives the exact second GitHub email.
