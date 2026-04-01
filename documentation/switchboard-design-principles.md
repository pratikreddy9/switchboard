# Switchboard Design Principles

Switchboard v1 is a control-center-first framework with an explicit node standard.
It exists to make server pulls, project visibility, agent handoff, and future node
rollout predictable without broad crawling or doc sprawl.

## Core Rules

- `docs/evidence/` is the dashboard-safe canonical lane for the control center.
- Node-owned project docs live under `switchboard/` inside each project root.
- Private path discoveries stay in `state/private/`.
- Passwords and tokens do not belong in tracked framework scaffolding.
- If VPN is needed, the operator turns it on manually. Switchboard does not store
  VPN requirements or VPN state.
- Collection is read-only. It does not mutate repos, services, or remote files.
- `git pull` is always manual, allowlist-only, and `--ff-only`.
- Secret handling is path-only. The framework records location metadata but never
  reads or stores secret file contents.
- A node should update one canonical runtime file and regenerate its derived docs.
- Broad local dump-folder crawling is out of scope for v1. Only explicitly seeded
  roots are managed.

## v1 Intent

- Keep the control center lightweight enough to seed fast.
- Make workspaces, services, and servers explicit through manifests.
- Give the dashboard and future project nodes stable filenames and evidence lanes.
- Standardize future project docs under `switchboard/` without overwriting local
  project docs like `README.md` or `api.md`.
