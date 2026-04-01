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
            f"- Service id: `{service_id}`\n"
        ),
        "design-principles.md": (
            "# Switchboard Node Design Principles\n\n"
            "- Keep project-owned docs untouched outside `switchboard/` unless explicitly asked.\n"
            "- Keep Git as the canonical change history.\n"
            "- Prefer deterministic, timestamped machine-readable evidence.\n"
            "- Update one canonical runtime file, then regenerate derived docs.\n"
            "- Never commit secrets, live passwords, or tokens into tracked docs.\n"
        ),
        "doc-structure-rules.md": (
            "# Switchboard Node Doc Structure Rules\n\n"
            "- `switchboard/core/` is package-owned and upgrade-safe.\n"
            "- `switchboard/local/tasks-completed.md` is the canonical runtime input file.\n"
            "- `switchboard/local/control-center-handoff.md`, `runbook.md`, and `approach-history.md` are regenerated outputs.\n"
            "- `switchboard/evidence/` is machine-readable and timestamped.\n"
            "- Use ISO timestamps in every generated JSON or markdown note.\n"
        ),
        "agent-instructions.md": (
            "# Agent Instructions\n\n"
            "- Read `switchboard/core/` first.\n"
            "- On regular updates, edit only `switchboard/local/tasks-completed.md` unless explicitly asked otherwise.\n"
            "- After editing `tasks-completed.md`, run `switchboard node snapshot --project-root <path>`.\n"
            "- Keep project docs outside `switchboard/` untouched unless explicitly requested.\n"
        ),
        "bootstrap-standardize-prompt.md": (
            "# Bootstrap Standardize Prompt\n\n"
            "Use everything you can safely inspect in the available project directories to standardize this project into the Switchboard format.\n\n"
            "Requirements:\n"
            "- Inspect the project root and known subpaths.\n"
            "- Find existing readmes, changelogs, runbooks, handoff notes, agent instructions, and operational docs.\n"
            "- Preserve useful information, but rewrite it into the Switchboard standard files under `switchboard/`.\n"
            "- Do not overwrite unrelated project docs outside `switchboard/` unless explicitly asked.\n"
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
        "- optional `Scope Entries:` lines in `kind | path_type | path` format\n\n"
        "Example format:\n\n"
        "```md\n"
        "    ## 2026-04-01T12:00:00+00:00 | Example update\n"
        "    - Tags: task, handoff\n"
        "    - Summary: Standardized the project docs.\n"
        "    - Changed Paths: switchboard/core/README.md, switchboard/local/tasks-completed.md\n"
        "    - Notes:\n"
        "      - Added the first standard handoff.\n"
        "```\n"
    )


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
            if current_section == "notes":
                notes.append(stripped[2:].strip() if stripped.startswith("- ") else stripped)
                continue
            if current_section == "scope":
                scope_lines.append(stripped)

        entries.append(
            {
                "timestamp": timestamp,
                "title": title,
                "tags": tags,
                "summary": summary or title,
                "changed_paths": changed_paths,
                "notes": notes,
                "scope_entries": _normalize_scope_lines(scope_lines),
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
