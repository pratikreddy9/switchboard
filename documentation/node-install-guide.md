# Switchboard Node Install Guide

## Goal

Use one packaged Switchboard release for both:

- the control center on your main machine
- node installs inside project roots

In v1, the safest deployment shape is:

1. build a wheel in the control-center repo
2. upload that wheel to GitHub as a release asset
3. pull that wheel on the target machine
4. install it with `uv tool install`
5. run `switchboard node install --project-root ...`

This keeps node installs simple and avoids needing a live Node/Vite stack on every project machine.

## What Gets Installed

A node install creates one folder in the project root:

```text
<project-root>/
  switchboard/
    node.manifest.json
    core/
      README.md
      design-principles.md
      doc-structure-rules.md
      agent-instructions.md
      bootstrap-standardize-prompt.md
      runtime-update-prompt.md
    local/
      tasks-completed.md
      control-center-handoff.md
      runbook.md
      approach-history.md
    evidence/
      completed-tasks.json
      repo-safety-history.json
      pull-bundle-history.json
      scope.snapshot.json
```

Nothing in the project root like `README.md` or `api.md` is replaced.

## Release It Once From The Control Center Repo

Run this in the framework repo:

```bash
cd /Users/p/Desktop/dashboard
./.venv/bin/switchboard release build --wheel-out release
```

That does three things:

1. builds the React frontend
2. bundles the static UI into the Python package
3. builds a wheel in `release/`

Expected output:

```text
release/switchboard-0.1.0-py3-none-any.whl
```

## Upload The Wheel To GitHub

Recommended: attach the wheel to a GitHub Release.

Example:

```bash
cd /Users/p/Desktop/dashboard
gh release create v0.1.0 release/switchboard-0.1.0-py3-none-any.whl \
  --title "Switchboard v0.1.0" \
  --notes "Control-center and node-mode release."
```

If the repo is private, the node machine can still pull it with `gh` after GitHub auth is set up there.

## Install A Node On A Project Machine

### Prerequisites

- `uv` installed on the target machine
- Python available on the target machine
- Git available on the target machine
- access to the GitHub release asset or copied wheel file

### Step 1: Download The Wheel

Example using GitHub CLI:

```bash
mkdir -p /tmp/switchboard-release
gh release download v0.1.0 \
  -R <owner>/<repo> \
  -p "switchboard-0.1.0-py3-none-any.whl" \
  -D /tmp/switchboard-release
```

You can also copy the wheel manually to the target machine if needed.

### Step 2: Install The Tool And All Python Dependencies In One Shot

```bash
uv tool install /tmp/switchboard-release/switchboard-0.1.0-py3-none-any.whl --force
```

This is the one-shot install step.

It installs:

- the `switchboard` CLI
- all Python dependencies declared by the package

It does not require `npm` on the node machine.

### Step 3: Plant The Node In The Project Root

Example for the first local test node:

```bash
switchboard node install \
  --project-root /Users/p/Desktop/work/zapp/lambdascripts \
  --service-id lambdascripts \
  --display-name "Lambda Scripts"
```

This creates the `switchboard/` folder pack in that project.

### Step 4: Regenerate Derived Docs After Edits

Whenever `switchboard/local/tasks-completed.md` changes:

```bash
switchboard node snapshot --project-root /Users/p/Desktop/work/zapp/lambdascripts
```

This regenerates:

- `switchboard/local/control-center-handoff.md`
- `switchboard/local/runbook.md`
- `switchboard/local/approach-history.md`
- `switchboard/evidence/completed-tasks.json`
- `switchboard/evidence/scope.snapshot.json` when scope entries are present

### Step 5: Upgrade A Node Later

When a newer wheel is released:

```bash
uv tool install /tmp/switchboard-release/switchboard-0.1.1-py3-none-any.whl --force
switchboard node upgrade --project-root /Users/p/Desktop/work/zapp/lambdascripts
```

Upgrade behavior:

- `switchboard/core/*` is refreshed
- `switchboard/local/*` is preserved
- `switchboard/evidence/*` is preserved except when regenerated intentionally by snapshot commands

## Optional Local Node API

If you want a lightweight local node API or local static dashboard view:

```bash
switchboard node serve \
  --project-root /Users/p/Desktop/work/zapp/lambdascripts \
  --host 127.0.0.1 \
  --port 8010
```

Useful endpoints:

- `GET /api/health`
- `GET /api/node`
- `POST /api/node/snapshot`

## How The Control Center Sees A Node

In v1, node detection should be treated as **manual add with stable node files**.

Control-center flow:

1. open the workspace in the dashboard
2. add the project by its real project root
3. scan that root
4. include the project repo paths you want
5. include the node-owned files under `switchboard/`

Default node paths to include:

- `switchboard/core/`
- `switchboard/local/`
- `switchboard/evidence/`

The key file that marks the project as a Switchboard node is:

```text
switchboard/node.manifest.json
```

That manifest tells the control center:

- node identity
- service id
- display name
- repo paths
- doc paths
- log paths
- exclude patterns
- evidence file locations

## Recommended Agent Workflow On The Node

For first-time standardization:

1. read `switchboard/core/bootstrap-standardize-prompt.md`
2. inspect the available project docs
3. write the standardized first pass into the `switchboard/` files
4. record the work in `switchboard/local/tasks-completed.md`
5. run `switchboard node snapshot --project-root ...`

For normal day-to-day updates:

1. update only `switchboard/local/tasks-completed.md`
2. use the fixed routing tags
3. run `switchboard node snapshot --project-root ...`

This keeps the regular agent workload small.

## Git Usage

Use Git on both ends:

- the control-center repo tracks framework changes and pulled bundles
- the project repo tracks its own code plus the `switchboard/` node folder

Recommended rule:

- commit `switchboard/` in the project repo
- do not hand-edit `switchboard/core/*`
- do edit `switchboard/local/*`
- regenerate `switchboard/evidence/*` through snapshot commands

## Current v1 Constraint

Automatic node registration inside the control center is not the primary v1 path yet.

Current v1 behavior should be treated as:

- install the node in the project root
- add that project in the control center
- select the `switchboard/` files as first-class project docs/evidence

That gives you stable structure now without blocking on a full auto-discovery layer.
