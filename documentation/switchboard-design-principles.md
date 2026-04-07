# Switchboard Design Principles

Switchboard `v1` is a project-first control center with an explicit node standard.

It exists to make server pulls, project visibility, node docs, and future agent coordination predictable without broad crawling or doc sprawl.

## Core Rules

- `docs/evidence/` is the dashboard-safe canonical lane for the control center.
- checked-in fallback data lives in `src/data/`
- private path discoveries stay in `state/private/`
- passwords and tokens do not belong in tracked framework scaffolding
- if VPN is needed, the operator turns it on manually
- collection is read-only
- `git pull` is manual, allowlist-only, and `--ff-only`
- node sync is manual and always initiated from the control center
- broad local dump-folder crawling is out of scope for `v1`

## Node Doc Rules

- node-owned project docs live under `switchboard/`
- `switchboard/core/playbook.md` is the only primary instruction doc
- agents should normally edit only `switchboard/local/tasks-completed.md`
- `switchboard node snapshot` rebuilds derived docs deterministically from that canonical file
- root `README.md`, `API.md`, and `CHANGELOG.md` remain first-class project docs in scope even when Switchboard does not own them
- `managed_docs` only controls whether Switchboard may rewrite those root docs
- if a root doc is not enabled in `managed_docs`, Switchboard must not edit it

## Runtime Rules

- runtime config belongs to each service location, not to the service as a whole
- run-command detection is best effort only
- manual runtime hints remain first-class

## v1 Intent

- keep the control center lightweight enough to seed fast
- make services, servers, and workspaces explicit through manifests
- standardize future project docs under `switchboard/`
- make the control-center/node contract stable enough for `v2` project-management views later
