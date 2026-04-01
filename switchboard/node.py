"""Node-mode install, upgrade, snapshot, and asset helpers."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .config import ROOT_DIR


NODE_DIR_NAME = "switchboard"
CORE_DIR_NAME = "core"
LOCAL_DIR_NAME = "local"
EVIDENCE_DIR_NAME = "evidence"
ROUTING_TAGS = ("task", "handoff", "runbook", "decision", "scope")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    token = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return token or "switchboard-node"


def node_paths(project_root: Path) -> dict[str, Path]:
    root = project_root / NODE_DIR_NAME
    return {
        "project_root": project_root,
        "node_root": root,
        "core": root / CORE_DIR_NAME,
        "local": root / LOCAL_DIR_NAME,
        "evidence": root / EVIDENCE_DIR_NAME,
        "manifest": root / "node.manifest.json",
        "core_readme": root / CORE_DIR_NAME / "README.md",
        "design_principles": root / CORE_DIR_NAME / "design-principles.md",
        "doc_structure_rules": root / CORE_DIR_NAME / "doc-structure-rules.md",
        "agent_instructions": root / CORE_DIR_NAME / "agent-instructions.md",
        "bootstrap_prompt": root / CORE_DIR_NAME / "bootstrap-standardize-prompt.md",
        "runtime_prompt": root / CORE_DIR_NAME / "runtime-update-prompt.md",
        "tasks_completed": root / LOCAL_DIR_NAME / "tasks-completed.md",
        "handoff": root / LOCAL_DIR_NAME / "control-center-handoff.md",
        "runbook": root / LOCAL_DIR_NAME / "runbook.md",
        "approach_history": root / LOCAL_DIR_NAME / "approach-history.md",
        "completed_tasks_json": root / EVIDENCE_DIR_NAME / "completed-tasks.json",
        "repo_safety_history": root / EVIDENCE_DIR_NAME / "repo-safety-history.json",
        "pull_bundle_history": root / EVIDENCE_DIR_NAME / "pull-bundle-history.json",
        "scope_snapshot": root / EVIDENCE_DIR_NAME / "scope.snapshot.json",
        "runtime": root / "runtime",
        "start_script": root / "start.sh",
        "run_script": root / "run.sh",
    }


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_text_if_missing(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_executable(path: Path, content: str) -> None:
    _write_text(path, content)
    path.chmod(0o755)


def load_node_manifest(project_root: str | Path) -> dict[str, Any]:
    paths = node_paths(Path(project_root).resolve())
    if not paths["manifest"].exists():
        raise FileNotFoundError(f"Node manifest not found: {paths['manifest']}")
    return _read_json(paths["manifest"], {})


def _default_display_name(service_id: str) -> str:
    return service_id.replace("-", " ").replace("_", " ").title()


def _node_id(service_id: str, project_root: Path) -> str:
    digest = hashlib.sha1(str(project_root).encode("utf-8")).hexdigest()[:10]
    return f"{service_id}-{digest}"


def _core_templates(service_id: str, display_name: str) -> dict[str, str]:
    return {
        "README.md": (
            f"# {display_name} Switchboard Node\n\n"
            "- This folder is owned by the Switchboard package.\n"
            "- Core files in `switchboard/core/` are standardized and may be replaced on upgrade.\n"
            "- Agents should maintain project-specific updates through `switchboard/local/tasks-completed.md`.\n"
            "- Snapshot regeneration updates the other local and evidence files deterministically.\n"
            "- Node sync is manual and initiated from the control center.\n"
            f"- Service id: `{service_id}`\n"
        ),
        "design-principles.md": (
            "# Switchboard Node Design Principles\n\n"
            "- Keep project-owned docs untouched outside `switchboard/` unless explicitly asked.\n"
            "- Keep Git as the canonical change history.\n"
            "- Prefer deterministic, timestamped machine-readable evidence.\n"
            "- Update one canonical runtime file, then regenerate derived docs.\n"
            "- Keep runtime config mirrored per location through the node manifest.\n"
            "- Never commit secrets, live passwords, or tokens into tracked docs.\n"
        ),
        "doc-structure-rules.md": (
            "# Switchboard Node Doc Structure Rules\n\n"
            "- `switchboard/core/` is package-owned and upgrade-safe.\n"
            "- `switchboard/local/tasks-completed.md` is the canonical runtime input file.\n"
            "- `switchboard/local/control-center-handoff.md`, `runbook.md`, and `approach-history.md` are regenerated outputs.\n"
            "- `switchboard/evidence/` is machine-readable and timestamped.\n"
            "- `switchboard/node.manifest.json` is the node identity and runtime-config mirror.\n"
            "- Use ISO timestamps in every generated JSON or markdown note.\n"
        ),
        "agent-instructions.md": (
            "# Agent Instructions\n\n"
            "- Read `switchboard/core/` first.\n"
            "- On regular updates, edit only `switchboard/local/tasks-completed.md` unless explicitly asked otherwise.\n"
            "- After editing `tasks-completed.md`, run `switchboard node snapshot --project-root <path>`.\n"
            "- Do not assume the node can push into the control center. Sync is manual and control-center initiated.\n"
            "- Keep project docs outside `switchboard/` untouched unless explicitly requested.\n"
            "- If runtime config is known, record it in a `Runtime:` block in `switchboard/local/tasks-completed.md` so snapshot can mirror it into `switchboard/node.manifest.json`.\n"
        ),
        "bootstrap-standardize-prompt.md": (
            "# Bootstrap Standardize Prompt\n\n"
            "Use everything you can safely inspect in the available project directories to standardize this project into the Switchboard format.\n\n"
            "Requirements:\n"
            "- Inspect the project root and known subpaths.\n"
            "- Find existing readmes, changelogs, runbooks, handoff notes, agent instructions, and operational docs.\n"
            "- Preserve useful information, but rewrite it into the Switchboard standard files under `switchboard/`.\n"
            "- Do not overwrite unrelated project docs outside `switchboard/` unless explicitly asked.\n"
            "- If the project has known ports, health checks, or run command hints, include them in the latest `tasks-completed.md` entry under a `Runtime:` block.\n"
            "- Record the standardization work in `switchboard/local/tasks-completed.md` using the required entry format.\n"
            "- Finish by running `switchboard node snapshot --project-root <path>`.\n"
        ),
        "runtime-update-prompt.md": (
            "# Runtime Update Prompt\n\n"
            "For regular maintenance work:\n"
            "- Update only `switchboard/local/tasks-completed.md`.\n"
            "- Use one entry per meaningful update.\n"
            "- Include timestamp, title, summary, changed paths, and routing tags.\n"
            "- Use only these routing tags: `task`, `handoff`, `runbook`, `decision`, `scope`.\n"
            "- If scope changed, include a `Scope Entries` block in the entry.\n"
            "- If runtime config changed, include a `Runtime:` block in the entry.\n"
            "- Finish by running `switchboard node snapshot --project-root <path>` so derived docs and JSON stay synchronized.\n\n"
            "Entry format:\n"
            "## 2026-04-01T12:00:00+00:00 | Example title\n"
            "- Tags: task, handoff\n"
            "- Summary: Short summary.\n"
            "- Changed Paths: src/app.py, switchboard/local/tasks-completed.md\n"
            "- Notes:\n"
            "  - Optional detail line.\n"
            "- Scope Entries:\n"
            "  - doc | file | /abs/path/to/file.md\n"
            "  - exclude | glob | venv\n"
            "- Runtime:\n"
            "  - expected_ports: 8010, 8000\n"
            "  - healthcheck_command: curl http://127.0.0.1:8010/api/health\n"
            "  - run_command_hint: uvicorn main:app --port 8010\n"
            "  - monitoring_mode: manual\n"
        ),
    }


def _tasks_completed_template() -> str:
    return (
        "# Tasks Completed\n\n"
        "Use one entry per meaningful update.\n\n"
        "Required fields:\n"
        "- heading: `## <ISO timestamp> | <title>`\n"
        "- `Tags:` using only `task`, `handoff`, `runbook`, `decision`, `scope`\n"
        "- `Summary:`\n"
        "- `Changed Paths:` comma-separated\n"
        "- optional `Notes:` lines\n"
        "- optional `Scope Entries:` lines in `kind | path_type | path` format\n"
        "- optional `Runtime:` lines for ports, health check, and run command hint\n\n"
        "Example format:\n\n"
        "```md\n"
        "    ## 2026-04-01T12:00:00+00:00 | Example update\n"
        "    - Tags: task, handoff\n"
        "    - Summary: Standardized the project docs.\n"
        "    - Changed Paths: switchboard/core/README.md, switchboard/local/tasks-completed.md\n"
        "    - Notes:\n"
        "      - Added the first standard handoff.\n"
        "    - Runtime:\n"
        "      - expected_ports: 8010\n"
        "      - healthcheck_command: curl http://127.0.0.1:8010/api/health\n"
        "```\n"
    )


def _node_start_script(project_root: Path) -> str:
    default_port = "8010"
    return f"""#!/bin/bash
set -euo pipefail

PROJECT_ROOT="{project_root}"
DEFAULT_HOST="127.0.0.1"
DEFAULT_PORT="{default_port}"

echo "Switchboard Node"
echo "Project root: $PROJECT_ROOT"
printf "Port [$DEFAULT_PORT]: "
read -r PORT_INPUT
PORT="${{PORT_INPUT:-$DEFAULT_PORT}}"
printf "Host [$DEFAULT_HOST]: "
read -r HOST_INPUT
HOST="${{HOST_INPUT:-$DEFAULT_HOST}}"

switchboard node start --project-root "$PROJECT_ROOT" --host "$HOST" --port "$PORT"
switchboard node status --project-root "$PROJECT_ROOT" --port "$PORT"
echo "Logs: $PROJECT_ROOT/switchboard/runtime/node.log"
"""


def _scope_entry_defaults(path: str, kind: str) -> dict[str, Any]:
    candidate = Path(path)
    path_type = "glob" if any(token in path for token in ("*", "?", "[")) else ("dir" if candidate.suffix == "" else "file")
    return {
        "kind": kind,
        "path": path,
        "path_type": path_type,
        "source": "node_manifest",
        "enabled": True,
    }


def _evidence_defaults(service_id: str, project_root: Path, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = manifest or {}
    repo_paths = manifest.get("repo_paths", [str(project_root)])
    docs_paths = manifest.get("docs_paths", [])
    log_paths = manifest.get("log_paths", [])
    exclude_patterns = manifest.get("exclude_patterns", [])

    scope_entries = [_scope_entry_defaults(path, "repo") for path in repo_paths]
    scope_entries.extend(_scope_entry_defaults(path, "doc") for path in docs_paths)
    scope_entries.extend(_scope_entry_defaults(path, "log") for path in log_paths)
    scope_entries.extend(
        {
            "kind": "exclude",
            "path": path,
            "path_type": "glob",
            "source": "node_manifest",
            "enabled": True,
        }
        for path in exclude_patterns
    )
    return {
        "generated": utc_now_iso(),
        "service_id": manifest.get("service_id", service_id),
        "project_root": str(project_root),
        "scope_entries": scope_entries,
        "scope_updates": [],
    }


def load_pull_bundle_history(project_root: str | Path) -> dict[str, Any]:
    paths = node_paths(Path(project_root).resolve())
    return _read_json(paths["pull_bundle_history"], {"generated": "", "bundles": []})


def _manifest_payload(project_root: Path, service_id: str, display_name: str, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = existing or {}
    paths = node_paths(project_root)
    docs_paths = existing.get(
        "docs_paths",
        [
            str(paths["core"]),
            str(paths["local"]),
            str(paths["evidence"]),
        ],
    )
    return {
        "node_id": existing.get("node_id", _node_id(service_id, project_root)),
        "service_id": service_id,
        "display_name": display_name,
        "project_root": str(project_root),
        "mode": "node",
        "installed_version": __version__,
        "repo_paths": existing.get("repo_paths", [str(project_root)]),
        "docs_paths": docs_paths,
        "log_paths": existing.get("log_paths", []),
        "exclude_patterns": existing.get("exclude_patterns", []),
        "runtime": existing.get(
            "runtime",
            {
                "expected_ports": [],
                "healthcheck_command": "",
                "run_command_hint": "",
                "monitoring_mode": "manual",
                "notes": "",
            },
        ),
        "evidence_paths": {
            "completed_tasks": str(paths["completed_tasks_json"].relative_to(project_root)),
            "repo_safety_history": str(paths["repo_safety_history"].relative_to(project_root)),
            "pull_bundle_history": str(paths["pull_bundle_history"].relative_to(project_root)),
            "scope_snapshot": str(paths["scope_snapshot"].relative_to(project_root)),
        },
        "updated_at": utc_now_iso(),
    }


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _normalize_scope_lines(lines: list[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for line in lines:
        payload = line.strip()
        if payload.startswith("- "):
            payload = payload[2:].strip()
        parts = [part.strip() for part in payload.split("|")]
        if len(parts) < 3:
            continue
        kind, path_type, path = parts[:3]
        enabled = True
        if len(parts) >= 4:
            enabled = parts[3].lower() not in {"false", "0", "no", "disabled"}
        entries.append(
            {
                "kind": kind,
                "path_type": path_type,
                "path": path,
                "enabled": enabled,
                "source": "tasks_completed",
            }
        )
    return entries


def _normalize_runtime_lines(lines: list[str]) -> dict[str, Any]:
    runtime = {
        "expected_ports": [],
        "healthcheck_command": "",
        "run_command_hint": "",
        "monitoring_mode": "manual",
        "notes": "",
    }
    notes: list[str] = []
    for raw in lines:
        payload = raw.strip()
        if payload.startswith("- "):
            payload = payload[2:].strip()
        if ":" not in payload:
            if payload:
                notes.append(payload)
            continue
        key, value = payload.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "expected_ports":
            runtime["expected_ports"] = [int(token.strip()) for token in value.split(",") if token.strip().isdigit()]
        elif key == "healthcheck_command":
            runtime["healthcheck_command"] = value
        elif key == "run_command_hint":
            runtime["run_command_hint"] = value
        elif key == "monitoring_mode" and value in {"manual", "detect", "node_managed"}:
            runtime["monitoring_mode"] = value
        elif key == "notes":
            notes.append(value)
    runtime["notes"] = "\n".join(note for note in notes if note).strip()
    return runtime


def parse_tasks_completed(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    matches = list(re.finditer(r"^##\s+(.+?)\s*\|\s*(.+)$", text, flags=re.MULTILINE))
    entries: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[start:end]
        timestamp = match.group(1).strip()
        title = match.group(2).strip()
        tags: list[str] = []
        summary = ""
        changed_paths: list[str] = []
        notes: list[str] = []
        scope_lines: list[str] = []
        runtime_lines: list[str] = []
        current_section: str | None = None

        for raw_line in block.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("- Tags:"):
                tags = [tag for tag in (item.strip().lower() for item in _split_csv(stripped.split(":", 1)[1])) if tag in ROUTING_TAGS]
                current_section = None
                continue
            if stripped.startswith("- Summary:"):
                summary = stripped.split(":", 1)[1].strip()
                current_section = None
                continue
            if stripped.startswith("- Changed Paths:"):
                changed_paths = _split_csv(stripped.split(":", 1)[1])
                current_section = None
                continue
            if stripped.startswith("- Notes:"):
                current_section = "notes"
                payload = stripped.split(":", 1)[1].strip()
                if payload:
                    notes.append(payload)
                continue
            if stripped.startswith("- Scope Entries:"):
                current_section = "scope"
                payload = stripped.split(":", 1)[1].strip()
                if payload:
                    scope_lines.append(payload)
                continue
            if stripped.startswith("- Runtime:"):
                current_section = "runtime"
                payload = stripped.split(":", 1)[1].strip()
                if payload:
                    runtime_lines.append(payload)
                continue
            if current_section == "notes":
                notes.append(stripped[2:].strip() if stripped.startswith("- ") else stripped)
                continue
            if current_section == "scope":
                scope_lines.append(stripped)
                continue
            if current_section == "runtime":
                runtime_lines.append(stripped)

        entries.append(
            {
                "timestamp": timestamp,
                "title": title,
                "tags": tags,
                "summary": summary or title,
                "changed_paths": changed_paths,
                "notes": notes,
                "scope_entries": _normalize_scope_lines(scope_lines),
                "runtime": _normalize_runtime_lines(runtime_lines),
            }
        )
    return entries


def _render_entry(entry: dict[str, Any]) -> str:
    lines = [
        f"## {entry['timestamp']} | {entry['title']}",
        f"- Tags: {', '.join(entry['tags'])}" if entry.get("tags") else "- Tags: task",
        f"- Summary: {entry['summary']}",
        f"- Changed Paths: {', '.join(entry['changed_paths'])}" if entry.get("changed_paths") else "- Changed Paths:",
    ]
    if entry.get("notes"):
        lines.append("- Notes:")
        for note in entry["notes"]:
            lines.append(f"  - {note}")
    if entry.get("scope_entries"):
        lines.append("- Scope Entries:")
        for scope_entry in entry["scope_entries"]:
            enabled = "true" if scope_entry.get("enabled", True) else "false"
            lines.append(
                f"  - {scope_entry['kind']} | {scope_entry['path_type']} | {scope_entry['path']} | {enabled}"
            )
    runtime = entry.get("runtime") or {}
    if any(runtime.get(key) for key in ("expected_ports", "healthcheck_command", "run_command_hint", "notes")):
        lines.append("- Runtime:")
        if runtime.get("expected_ports"):
            lines.append(f"  - expected_ports: {', '.join(str(port) for port in runtime['expected_ports'])}")
        if runtime.get("healthcheck_command"):
            lines.append(f"  - healthcheck_command: {runtime['healthcheck_command']}")
        if runtime.get("run_command_hint"):
            lines.append(f"  - run_command_hint: {runtime['run_command_hint']}")
        lines.append(f"  - monitoring_mode: {runtime.get('monitoring_mode', 'manual')}")
        if runtime.get("notes"):
            lines.append(f"  - notes: {runtime['notes']}")
    return "\n".join(lines)


def _render_section(title: str, entries: list[dict[str, Any]], empty_message: str) -> str:
    if not entries:
        return f"# {title}\n\n{empty_message}\n"
    body = "\n\n".join(_render_entry(entry) for entry in entries)
    return f"# {title}\n\n{body}\n"


def install_node(project_root: str | Path, service_id: str | None = None, display_name: str | None = None) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    project_root.mkdir(parents=True, exist_ok=True)
    paths = node_paths(project_root)
    existing = _read_json(paths["manifest"], {}) if paths["manifest"].exists() else {}
    service_id = service_id or existing.get("service_id") or slugify(project_root.name)
    display_name = display_name or existing.get("display_name") or _default_display_name(service_id)

    for key in ("node_root", "core", "local", "evidence"):
        paths[key].mkdir(parents=True, exist_ok=True)

    manifest = _manifest_payload(project_root, service_id, display_name, existing)
    _write_json(paths["manifest"], manifest)

    for filename, content in _core_templates(service_id, display_name).items():
        _write_text(paths["core"] / filename, content)

    _write_executable(paths["start_script"], _node_start_script(project_root))
    _write_executable(paths["run_script"], _node_start_script(project_root))

    _write_text_if_missing(paths["tasks_completed"], _tasks_completed_template())
    _write_text_if_missing(paths["handoff"], "# Control Center Handoff\n\nNo handoff entries yet.\n")
    _write_text_if_missing(paths["runbook"], "# Runbook\n\nNo runbook entries yet.\n")
    _write_text_if_missing(paths["approach_history"], "# Approach History\n\nNo decision entries yet.\n")

    if not paths["completed_tasks_json"].exists():
        _write_json(paths["completed_tasks_json"], {"generated": "", "service_id": service_id, "project_root": str(project_root), "tasks": []})
    if not paths["repo_safety_history"].exists():
        _write_json(paths["repo_safety_history"], {"generated": "", "checks": []})
    if not paths["pull_bundle_history"].exists():
        _write_json(paths["pull_bundle_history"], {"generated": "", "bundles": []})
    if not paths["scope_snapshot"].exists():
        _write_json(paths["scope_snapshot"], _evidence_defaults(service_id, project_root, manifest))

    snapshot = snapshot_node(project_root)
    return {"project_root": str(project_root), "node_root": str(paths["node_root"]), "manifest": snapshot["manifest"]}


def upgrade_node(project_root: str | Path) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    paths = node_paths(project_root)
    existing = _read_json(paths["manifest"], {})
    if not existing:
        return install_node(project_root)
    return install_node(project_root, existing.get("service_id"), existing.get("display_name"))


def snapshot_node(project_root: str | Path) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    paths = node_paths(project_root)
    if not paths["manifest"].exists():
        install_node(project_root)

    manifest = load_node_manifest(project_root)
    tasks = parse_tasks_completed(paths["tasks_completed"])
    tasks_json = {
        "generated": utc_now_iso(),
        "service_id": manifest["service_id"],
        "project_root": str(project_root),
        "tasks": tasks,
    }
    _write_json(paths["completed_tasks_json"], tasks_json)

    handoff_entries = [entry for entry in tasks if "handoff" in entry.get("tags", [])]
    runbook_entries = [entry for entry in tasks if "runbook" in entry.get("tags", [])]
    decision_entries = [entry for entry in tasks if "decision" in entry.get("tags", [])]
    scope_entries_from_tasks = [entry for entry in tasks if entry.get("scope_entries")]
    runtime_entries_from_tasks = [
        entry for entry in tasks if any(entry.get("runtime", {}).get(key) for key in ("expected_ports", "healthcheck_command", "run_command_hint", "notes"))
    ]

    _write_text(
        paths["handoff"],
        _render_section(
            "Control Center Handoff",
            handoff_entries,
            "No handoff-tagged entries yet. Add entries to `tasks-completed.md` with the `handoff` tag and rerun snapshot.",
        ),
    )
    _write_text(
        paths["runbook"],
        _render_section(
            "Runbook",
            runbook_entries,
            "No runbook-tagged entries yet. Add entries to `tasks-completed.md` with the `runbook` tag and rerun snapshot.",
        ),
    )
    _write_text(
        paths["approach_history"],
        _render_section(
            "Approach History",
            decision_entries,
            "No decision-tagged entries yet. Add entries to `tasks-completed.md` with the `decision` tag and rerun snapshot.",
        ),
    )

    scope_snapshot = _read_json(paths["scope_snapshot"], _evidence_defaults(manifest["service_id"], project_root, manifest))
    scope_snapshot["generated"] = utc_now_iso()
    scope_snapshot["service_id"] = manifest["service_id"]
    scope_snapshot["project_root"] = str(project_root)
    if scope_entries_from_tasks:
        scope_snapshot["scope_entries"] = scope_entries_from_tasks[-1]["scope_entries"]
    elif not scope_snapshot.get("scope_entries"):
        scope_snapshot = _evidence_defaults(manifest["service_id"], project_root, manifest)
    scope_snapshot["scope_updates"] = [
        {
            "timestamp": entry["timestamp"],
            "title": entry["title"],
            "summary": entry["summary"],
            "changed_paths": entry["changed_paths"],
            "scope_entries": entry["scope_entries"],
        }
        for entry in scope_entries_from_tasks
    ]
    _write_json(paths["scope_snapshot"], scope_snapshot)

    if runtime_entries_from_tasks:
        manifest["runtime"] = runtime_entries_from_tasks[-1]["runtime"]

    manifest["updated_at"] = utc_now_iso()
    _write_json(paths["manifest"], manifest)
    return {"manifest": manifest, "tasks": tasks, "scope_snapshot": scope_snapshot}


def resolve_static_app_dir() -> Path | None:
    package_static = ROOT_DIR / "switchboard" / "static" / "app"
    if package_static.exists() and (package_static / "index.html").exists():
        return package_static
    dist_static = ROOT_DIR / "dist"
    if dist_static.exists() and (dist_static / "index.html").exists():
        return dist_static
    return None


def list_node_files(project_root: str | Path) -> list[str]:
    project_root = Path(project_root).resolve()
    paths = node_paths(project_root)
    if not paths["node_root"].exists():
        return []
    files: list[str] = []
    for path in sorted(paths["node_root"].rglob("*")):
        if path.is_file():
            files.append(str(path.relative_to(project_root)))
    return files
