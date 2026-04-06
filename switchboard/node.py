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
MANAGED_DOC_DEFAULTS: tuple[tuple[str, str, bool], ...] = (
    ("readme", "README.md", False),
    ("api", "API.md", False),
    ("changelog", "CHANGELOG.md", False),
    ("handoff", "switchboard/local/control-center-handoff.md", True),
    ("runbook", "switchboard/local/runbook.md", True),
    ("approach_history", "switchboard/local/approach-history.md", True),
    ("doc_index_md", "switchboard/local/doc-index.md", True),
    ("doc_index_json", "switchboard/evidence/doc-index.json", True),
)


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
        "playbook": root / CORE_DIR_NAME / "playbook.md",
        "design_principles": root / CORE_DIR_NAME / "design-principles.md",
        "doc_structure_rules": root / CORE_DIR_NAME / "doc-structure-rules.md",
        "agent_instructions": root / CORE_DIR_NAME / "agent-instructions.md",
        "bootstrap_prompt": root / CORE_DIR_NAME / "bootstrap-standardize-prompt.md",
        "runtime_prompt": root / CORE_DIR_NAME / "runtime-update-prompt.md",
        "tasks_completed": root / LOCAL_DIR_NAME / "tasks-completed.md",
        "handoff": root / LOCAL_DIR_NAME / "control-center-handoff.md",
        "runbook": root / LOCAL_DIR_NAME / "runbook.md",
        "approach_history": root / LOCAL_DIR_NAME / "approach-history.md",
        "doc_index_md": root / LOCAL_DIR_NAME / "doc-index.md",
        "completed_tasks_json": root / EVIDENCE_DIR_NAME / "completed-tasks.json",
        "doc_index_json": root / EVIDENCE_DIR_NAME / "doc-index.json",
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


def _managed_doc_defaults() -> list[dict[str, Any]]:
    return [
        {
            "doc_id": doc_id,
            "path": path,
            "enabled": enabled,
            "generated_from": "switchboard/local/tasks-completed.md",
            "last_generated_at": None,
        }
        for doc_id, path, enabled in MANAGED_DOC_DEFAULTS
    ]


def _normalize_managed_docs(existing: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    defaults = {entry["doc_id"]: entry for entry in _managed_doc_defaults()}
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for entry in existing or []:
        doc_id = str(entry.get("doc_id", "")).strip()
        if not doc_id or doc_id in seen:
            continue
        default = defaults.get(doc_id, {})
        seen.add(doc_id)
        normalized.append(
            {
                "doc_id": doc_id,
                "path": str(entry.get("path") or default.get("path") or "").strip(),
                "enabled": bool(entry.get("enabled", default.get("enabled", False))),
                "generated_from": str(entry.get("generated_from") or "switchboard/local/tasks-completed.md"),
                "last_generated_at": entry.get("last_generated_at"),
            }
        )
    for doc_id, default in defaults.items():
        if doc_id in seen:
            continue
        normalized.append(default)
    return normalized


def _managed_doc_by_id(managed_docs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(entry["doc_id"]): entry for entry in managed_docs}


def _managed_doc_path(project_root: Path, entry: dict[str, Any]) -> Path:
    return project_root / str(entry["path"])


def _managed_doc_label(doc_id: str) -> str:
    labels = {
        "readme": "README",
        "api": "API",
        "changelog": "CHANGELOG",
        "handoff": "Control Center Handoff",
        "runbook": "Runbook",
        "approach_history": "Approach History",
        "doc_index_md": "Doc Index Markdown",
        "doc_index_json": "Doc Index JSON",
    }
    return labels.get(doc_id, doc_id)


def _core_templates(service_id: str, display_name: str) -> dict[str, str]:
    return {
        "README.md": (
            f"# {display_name} Switchboard Node\n\n"
            "- This folder is owned by the Switchboard package.\n"
            "- Core files in `switchboard/core/` are standardized and may be replaced on upgrade.\n"
            "- Agents should read `switchboard/core/playbook.md` first.\n"
            "- Agents should maintain project-specific updates through `switchboard/local/tasks-completed.md`.\n"
            "- Snapshot regeneration rebuilds derived docs and evidence deterministically from the canonical file.\n"
            "- Node sync is manual and initiated from the control center.\n"
            f"- Service id: `{service_id}`\n"
        ),
        "playbook.md": (
            f"# {display_name} Switchboard Playbook\n\n"
            "This is the only primary instruction file agents should rely on for normal work in this project.\n\n"
            "## Ownership Rules\n\n"
            "- `switchboard/core/` is framework-owned and replaced by Switchboard upgrades.\n"
            "- `switchboard/local/tasks-completed.md` is the single canonical file agents should edit during normal work.\n"
            "- Derived docs and evidence are generated from that canonical file on `switchboard node snapshot`.\n"
            "- Root project docs such as `README.md`, `API.md`, and `CHANGELOG.md` are only rewritten when they are enabled in `switchboard/node.manifest.json` under `managed_docs`.\n"
            "- If a root doc is not enabled there, Switchboard must not edit it.\n\n"
            "## Required Entry Shape\n\n"
            "- Heading: `## <ISO timestamp> | <title>`\n"
            "- `Tags:` with only `task`, `handoff`, `runbook`, `decision`, `scope`\n"
            "- `Summary:` one concise sentence\n"
            "- `Changed Paths:` comma-separated paths\n\n"
            "## Optional Blocks\n\n"
            "- `Version:` single version string that becomes the canonical version source across derived docs\n"
            "- `Readme:` markdown block for project overview/state\n"
            "- `API:` markdown block for API-facing updates\n"
            "- `Changelog:` markdown block for release-style deltas\n"
            "- `Notes:` general details that do not belong in the other routed blocks\n"
            "- `Scope Entries:` lines in `kind | path_type | path | enabled` format\n"
            "- `Runtime:` lines for `expected_ports`, `healthcheck_command`, `run_command_hint`, `monitoring_mode`, and `notes`\n\n"
            "## Canonical Workflow\n\n"
            "1. Read this playbook.\n"
            "2. Edit only `switchboard/local/tasks-completed.md` for normal updates.\n"
            "3. Run `switchboard node snapshot --project-root <path>`.\n"
            "4. Do not hand-edit derived docs unless explicitly instructed.\n\n"
            "## Sync Rules\n\n"
            "- Nodes do not call back into the control center.\n"
            "- Nodes do not SSH into the control-center machine.\n"
            "- Sync is always initiated from the control center.\n"
            "- Control center may mirror scope, runtime, managed-doc configuration, and pull-bundle history into the node.\n"
        ),
        "design-principles.md": (
            "# Switchboard Node Design Principles\n\n"
            "This file is a compatibility stub.\n\n"
            "Read `switchboard/core/playbook.md` for the authoritative rules.\n"
        ),
        "doc-structure-rules.md": (
            "# Switchboard Node Doc Structure Rules\n\n"
            "This file is a compatibility stub.\n\n"
            "Read `switchboard/core/playbook.md` for the authoritative rules.\n"
        ),
        "agent-instructions.md": (
            "# Agent Instructions\n\n"
            "This file is a compatibility stub.\n\n"
            "Read `switchboard/core/playbook.md` first. It is the only primary rulebook.\n"
        ),
        "bootstrap-standardize-prompt.md": (
            "# Bootstrap Standardize Prompt\n\n"
            "Use everything you can safely inspect in the available project directories to standardize this project into the Switchboard format.\n\n"
            "Requirements:\n"
            "- Read `switchboard/core/playbook.md` first.\n"
            "- Inspect the project root and known subpaths.\n"
            "- Find existing readmes, changelogs, runbooks, handoff notes, agent instructions, and operational docs.\n"
            "- Preserve useful information, but rewrite it into the Switchboard standard files under `switchboard/`.\n"
            "- Do not overwrite unrelated project docs outside `switchboard/` unless explicitly asked.\n"
            "- Put the actual structured update in `switchboard/local/tasks-completed.md`, not directly into derived docs.\n"
            "- If the project has known ports, health checks, or run command hints, include them in the latest `tasks-completed.md` entry under a `Runtime:` block.\n"
            "- If project root docs should be framework-owned, record the needed `Readme`, `API`, `Changelog`, and `Version` blocks in `tasks-completed.md` and enable those docs through the node managed-doc config.\n"
            "- Record the standardization work in `switchboard/local/tasks-completed.md` using the required entry format.\n"
            "- Finish by running `switchboard node snapshot --project-root <path>`.\n"
        ),
        "runtime-update-prompt.md": (
            "# Runtime Update Prompt\n\n"
            "For regular maintenance work:\n"
            "- Read `switchboard/core/playbook.md` first.\n"
            "- Inspect system docs for dependencies and record agent/tool used.\n"
            "- Update only `switchboard/local/tasks-completed.md`.\n"
            "- Use one entry per meaningful update.\n"
            "- Include timestamp, title, summary, changed paths, and routing tags.\n"
            "- Use only these routing tags: `task`, `handoff`, `runbook`, `decision`, `scope`.\n"
            "- If project-facing docs changed, add `Version`, `Readme`, `API`, and `Changelog` blocks as needed.\n"
            "- If scope changed, include a `Scope Entries` block in the entry.\n"
            "- If runtime config changed, include a `Runtime:` block in the entry.\n"
            "- Finish by running `switchboard node snapshot --project-root <path>` so derived docs and JSON stay synchronized.\n\n"
            "Entry format:\n"
            "## 2026-04-01T12:00:00+00:00 | Example title\n"
            "- Tags: task, handoff\n"
            "- Summary: Short summary.\n"
            "- Changed Paths: src/app.py, switchboard/local/tasks-completed.md\n"
            "- Version: 1.1\n"
            "- Readme:\n"
            "  ## Overview\n"
            "  Updated high-level project notes.\n"
            "- API:\n"
            "  ## Endpoints\n"
            "  Added `/health`.\n"
            "- Changelog:\n"
            "  - Added health endpoint.\n"
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
        "- optional `Version:`\n"
        "- optional `Readme:` markdown block\n"
        "- optional `API:` markdown block\n"
        "- optional `Changelog:` markdown block\n"
        "- optional `Notes:` lines\n"
        "- optional `Scope Entries:` lines in `kind | path_type | path` format\n"
        "- optional `Runtime:` lines for ports, health check, and run command hint\n\n"
        "Example format:\n\n"
        "```md\n"
        "    ## 2026-04-01T12:00:00+00:00 | Example update\n"
        "    - Tags: task, handoff\n"
        "    - Summary: Standardized the project docs.\n"
        "    - Changed Paths: switchboard/core/README.md, switchboard/local/tasks-completed.md\n"
        "    - Version: 1.1\n"
        "    - Readme:\n"
        "      ## Overview\n"
        "      Standardized the project docs.\n"
        "    - API:\n"
        "      ## Surface\n"
        "      Added `/health`.\n"
        "    - Changelog:\n"
        "      - Standardized the project docs.\n"
        "    - Notes:\n"
        "      - Added the first standard handoff.\n"
        "    - Runtime:\n"
        "      - expected_ports: 8010\n"
        "      - healthcheck_command: curl http://127.0.0.1:8010/api/health\n"
        "```\n"
    )


def _node_start_script(project_root: Path) -> str:
    return f"""#!/bin/bash
set -euo pipefail

PROJECT_ROOT="{project_root}"
DEFAULT_HOST="127.0.0.1"
DEFAULT_PORT="$(python3 - <<'PY'
import json
from pathlib import Path

manifest_path = Path(r"{project_root}") / "switchboard" / "node.manifest.json"
default_port = 8010
try:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    value = payload.get("runtime_port", default_port)
    print(int(value))
except Exception:
    print(default_port)
PY
)"

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
        "runtime_port": int(existing.get("runtime_port", 8010) or 8010),
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
        "managed_docs": _normalize_managed_docs(existing.get("managed_docs")),
        "bootstrap_version": existing.get("bootstrap_version", ""),
        "runtime_services": existing.get("runtime_services", []),
        "dependencies": existing.get("dependencies", []),
        "cross_dependencies": existing.get("cross_dependencies", []),
        "diagram": existing.get("diagram", ""),
        "doc_index": existing.get("doc_index", {"generated": "", "docs": []}),
        "evidence_paths": {
            "completed_tasks": str(paths["completed_tasks_json"].relative_to(project_root)),
            "doc_index": str(paths["doc_index_json"].relative_to(project_root)),
            "repo_safety_history": str(paths["repo_safety_history"].relative_to(project_root)),
            "pull_bundle_history": str(paths["pull_bundle_history"].relative_to(project_root)),
            "scope_snapshot": str(paths["scope_snapshot"].relative_to(project_root)),
        },
        "updated_at": utc_now_iso(),
    }


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _strip_continuation_prefix(raw_line: str) -> str:
    if raw_line.startswith("  "):
        return raw_line[2:]
    return raw_line.strip()


def _join_markdown_lines(lines: list[str]) -> str:
    return "\n".join(lines).strip()


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


def _normalize_runtime_service_lines(lines: list[str]) -> list[dict[str, Any]]:
    """Parse pipe-delimited runtime service lines: kind | name | host | port | purpose | health_path"""
    services: list[dict[str, Any]] = []
    for raw in lines:
        payload = raw.strip()
        if payload.startswith("- "):
            payload = payload[2:].strip()
        parts = [part.strip() for part in payload.split("|")]
        if len(parts) < 2:
            continue
        port_str = parts[3].strip() if len(parts) > 3 else ""
        port = int(port_str) if port_str.isdigit() else None
        services.append({
            "name": parts[1] if len(parts) > 1 else parts[0],
            "host": parts[2] if len(parts) > 2 else "",
            "port": port,
            "purpose": parts[4] if len(parts) > 4 else "",
            "health_path": parts[5] if len(parts) > 5 else "",
            "owner": parts[6] if len(parts) > 6 else "",
        })
    return services


def _normalize_dependency_lines(lines: list[str]) -> list[dict[str, Any]]:
    """Parse pipe-delimited dependency lines: kind | name | host | port | notes"""
    deps: list[dict[str, Any]] = []
    for raw in lines:
        payload = raw.strip()
        if payload.startswith("- "):
            payload = payload[2:].strip()
        parts = [part.strip() for part in payload.split("|")]
        if len(parts) < 2:
            continue
        port_str = parts[3].strip() if len(parts) > 3 else ""
        port = int(port_str) if port_str.isdigit() else None
        if port_str.lower() in ("null", "none", ""):
            port = None
        deps.append({
            "kind": parts[0] if len(parts) > 0 else "service",
            "name": parts[1] if len(parts) > 1 else "",
            "host": parts[2] if len(parts) > 2 else "",
            "port": port,
            "notes": parts[4] if len(parts) > 4 else "",
        })
    return deps


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
        version = ""
        changed_paths: list[str] = []
        task_id = ""
        agent = ""
        tool = ""
        bootstrap_version = ""
        sections: dict[str, list[str]] = {
            "notes": [],
            "scope": [],
            "runtime": [],
            "readme": [],
            "api": [],
            "changelog": [],
            "runtime_services": [],
            "dependencies": [],
            "cross_dependencies": [],
            "diagram": [],
        }
        current_section: str | None = None

        for raw_line in block.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped and current_section in {"notes", "readme", "api", "changelog", "diagram"}:
                sections[current_section].append("")
                continue
            if not stripped:
                continue

            if line.startswith("- Tags:"):
                tags = [tag for tag in (item.strip().lower() for item in _split_csv(line.split(":", 1)[1])) if tag in ROUTING_TAGS]
                current_section = None
                continue
            if line.startswith("- Summary:"):
                summary = line.split(":", 1)[1].strip()
                current_section = None
                continue
            if line.startswith("- Changed Paths:"):
                changed_paths = _split_csv(line.split(":", 1)[1])
                current_section = None
                continue
            if line.startswith("- Version:"):
                version = line.split(":", 1)[1].strip()
                current_section = None
                continue
            if line.startswith("- Task ID:"):
                task_id = line.split(":", 1)[1].strip()
                current_section = None
                continue
            if line.startswith("- Agent:"):
                agent = line.split(":", 1)[1].strip()
                current_section = None
                continue
            if line.startswith("- Tool:"):
                tool = line.split(":", 1)[1].strip()
                current_section = None
                continue
            if line.startswith("- Bootstrap Version:"):
                bootstrap_version = line.split(":", 1)[1].strip()
                current_section = None
                continue

            next_section = None
            payload = ""
            if line.startswith("- Notes:"):
                next_section = "notes"
            elif line.startswith("- Scope Entries:"):
                next_section = "scope"
            elif line.startswith("- Runtime:"):
                next_section = "runtime"
            elif line.startswith("- Readme:"):
                next_section = "readme"
            elif line.startswith("- API:"):
                next_section = "api"
            elif line.startswith("- Changelog:"):
                next_section = "changelog"
            elif line.startswith("- Runtime Services:"):
                next_section = "runtime_services"
            elif line.startswith("- Dependencies:"):
                next_section = "dependencies"
            elif line.startswith("- Cross Dependencies:"):
                next_section = "cross_dependencies"
            elif line.startswith("- Diagram:"):
                next_section = "diagram"

            if next_section is not None:
                current_section = next_section
                payload = line.split(":", 1)[1].strip()
                if payload:
                    sections[current_section].append(payload)
                continue

            if current_section in sections:
                sections[current_section].append(_strip_continuation_prefix(raw_line))

        entries.append(
            {
                "timestamp": timestamp,
                "title": title,
                "tags": tags,
                "version": version,
                "summary": summary or title,
                "changed_paths": changed_paths,
                "task_id": task_id or None,
                "agent": agent,
                "tool": tool,
                "bootstrap_version": bootstrap_version,
                "notes": [line for line in sections["notes"] if line.strip()],
                "scope_entries": _normalize_scope_lines(sections["scope"]),
                "runtime": _normalize_runtime_lines(sections["runtime"]),
                "runtime_services": _normalize_runtime_service_lines(sections["runtime_services"]),
                "dependencies": _normalize_dependency_lines(sections["dependencies"]),
                "cross_dependencies": _normalize_dependency_lines(sections["cross_dependencies"]),
                "diagram": _join_markdown_lines(sections["diagram"]),
                "readme": _join_markdown_lines(sections["readme"]),
                "api": _join_markdown_lines(sections["api"]),
                "changelog": _join_markdown_lines(sections["changelog"]),
            }
        )
    return entries


def _render_multiline_block(label: str, content: str) -> list[str]:
    if not content.strip():
        return []
    lines = [f"- {label}:"]
    lines.extend(f"  {line}" if line else "" for line in content.splitlines())
    return lines


def _render_entry(entry: dict[str, Any]) -> str:
    lines = [
        f"## {entry['timestamp']} | {entry['title']}",
    ]
    if entry.get("task_id"):
        lines.append(f"- Task ID: {entry['task_id']}")
    lines.append(f"- Tags: {', '.join(entry['tags'])}" if entry.get("tags") else "- Tags: task")
    lines.append(f"- Summary: {entry['summary']}")
    lines.append(f"- Changed Paths: {', '.join(entry['changed_paths'])}" if entry.get("changed_paths") else "- Changed Paths:")
    if entry.get("agent"):
        lines.append(f"- Agent: {entry['agent']}")
    if entry.get("tool"):
        lines.append(f"- Tool: {entry['tool']}")
    if entry.get("version"):
        lines.append(f"- Version: {entry['version']}")
    if entry.get("bootstrap_version"):
        lines.append(f"- Bootstrap Version: {entry['bootstrap_version']}")
    lines.extend(_render_multiline_block("Readme", entry.get("readme", "")))
    lines.extend(_render_multiline_block("API", entry.get("api", "")))
    lines.extend(_render_multiline_block("Changelog", entry.get("changelog", "")))
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
    if entry.get("runtime_services"):
        lines.append("- Runtime Services:")
        for svc in entry["runtime_services"]:
            port_str = str(svc.get("port", "")) if svc.get("port") is not None else ""
            lines.append(f"  - service | {svc['name']} | {svc.get('host', '')} | {port_str} | {svc.get('purpose', '')} | {svc.get('health_path', '')}")
    if entry.get("dependencies"):
        lines.append("- Dependencies:")
        for dep in entry["dependencies"]:
            port_str = str(dep.get("port", "")) if dep.get("port") is not None else "null"
            lines.append(f"  - {dep.get('kind', 'service')} | {dep['name']} | {dep.get('host', '')} | {port_str} | {dep.get('notes', '')}")
    if entry.get("cross_dependencies"):
        lines.append("- Cross Dependencies:")
        for dep in entry["cross_dependencies"]:
            port_str = str(dep.get("port", "")) if dep.get("port") is not None else "null"
            lines.append(f"  - {dep.get('kind', 'service')} | {dep['name']} | {dep.get('host', '')} | {port_str} | {dep.get('notes', '')}")
    if entry.get("diagram"):
        lines.append("- Diagram:")
        for diagram_line in entry["diagram"].splitlines():
            lines.append(f"  {diagram_line}" if diagram_line else "")
    return "\n".join(lines)


def _render_section(title: str, entries: list[dict[str, Any]], empty_message: str) -> str:
    if not entries:
        return f"# {title}\n\n{empty_message}\n"
    body = "\n\n".join(_render_entry(entry) for entry in entries)
    return f"# {title}\n\n{body}\n"


def _latest_version(tasks: list[dict[str, Any]]) -> str:
    for entry in reversed(tasks):
        if entry.get("version"):
            return str(entry["version"])
    return ""


def _render_root_readme(manifest: dict[str, Any], runtime: dict[str, Any], tasks: list[dict[str, Any]]) -> str:
    version = _latest_version(tasks)
    latest_blocks = [entry for entry in tasks if entry.get("readme")]
    latest_block = latest_blocks[-1]["readme"] if latest_blocks else ""
    ports = ", ".join(str(port) for port in runtime.get("expected_ports", [])) or "none"
    health = runtime.get("healthcheck_command") or "Not configured"
    run_command = runtime.get("run_command_hint") or "Not configured"
    title = manifest.get("display_name") or manifest.get("service_id") or "Project"
    return (
        f"# {title}\n\n"
        "This file is framework-managed by Switchboard.\n\n"
        "## Identity\n\n"
        f"- Service id: `{manifest.get('service_id', '')}`\n"
        f"- Node id: `{manifest.get('node_id', '')}`\n"
        f"- Project root: `{manifest.get('project_root', '')}`\n"
        f"- Version: `{version or 'unversioned'}`\n\n"
        "## Runtime\n\n"
        f"- Monitoring mode: `{runtime.get('monitoring_mode', 'manual')}`\n"
        f"- Expected ports: `{ports}`\n"
        f"- Health check: `{health}`\n"
        f"- Run command hint: `{run_command}`\n\n"
        "## Project Notes\n\n"
        f"{latest_block or 'No `Readme` block has been recorded in `switchboard/local/tasks-completed.md` yet.'}\n"
    )


def _render_root_api(manifest: dict[str, Any], runtime: dict[str, Any], scope_snapshot: dict[str, Any], tasks: list[dict[str, Any]]) -> str:
    version = _latest_version(tasks)
    api_blocks = [entry for entry in tasks if entry.get("api")]
    latest_block = api_blocks[-1]["api"] if api_blocks else ""
    scope_count = len(scope_snapshot.get("scope_entries", []))
    return (
        f"# API\n\n"
        "This file is framework-managed by Switchboard.\n\n"
        "## Metadata\n\n"
        f"- Service id: `{manifest.get('service_id', '')}`\n"
        f"- Version: `{version or 'unversioned'}`\n"
        f"- Scope entries: `{scope_count}`\n"
        f"- Monitoring mode: `{runtime.get('monitoring_mode', 'manual')}`\n"
        f"- Health check: `{runtime.get('healthcheck_command') or 'Not configured'}`\n"
        f"- Run command hint: `{runtime.get('run_command_hint') or 'Not configured'}`\n\n"
        "## API Notes\n\n"
        f"{latest_block or 'No `API` block has been recorded in `switchboard/local/tasks-completed.md` yet.'}\n"
    )


def _render_root_changelog(tasks: list[dict[str, Any]]) -> str:
    if not tasks:
        return "# CHANGELOG\n\nNo entries captured yet.\n"
    lines = ["# CHANGELOG", ""]
    for entry in reversed(tasks):
        heading = entry.get("version") or entry["timestamp"]
        lines.append(f"## {heading} | {entry['title']}")
        lines.append("")
        lines.append(f"- Timestamp: {entry['timestamp']}")
        lines.append(f"- Summary: {entry['summary']}")
        if entry.get("changed_paths"):
            lines.append(f"- Changed Paths: {', '.join(entry['changed_paths'])}")
        changelog_block = str(entry.get("changelog") or "").strip()
        if changelog_block:
            lines.append("- Details:")
            for line in changelog_block.splitlines():
                lines.append(f"  {line}" if line else "")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _contributors_for_doc(doc_id: str, tasks: list[dict[str, Any]]) -> list[str]:
    contributors: list[str] = []
    for entry in tasks:
        if doc_id == "handoff" and "handoff" in entry.get("tags", []):
            contributors.append(entry["timestamp"])
        elif doc_id == "runbook" and "runbook" in entry.get("tags", []):
            contributors.append(entry["timestamp"])
        elif doc_id == "approach_history" and "decision" in entry.get("tags", []):
            contributors.append(entry["timestamp"])
        elif doc_id == "readme" and entry.get("readme"):
            contributors.append(entry["timestamp"])
        elif doc_id == "api" and entry.get("api"):
            contributors.append(entry["timestamp"])
        elif doc_id == "changelog":
            contributors.append(entry["timestamp"])
        elif doc_id in {"doc_index_md", "doc_index_json"}:
            contributors.append(entry["timestamp"])
    return contributors


def _render_doc_index_markdown(doc_index: dict[str, Any]) -> str:
    lines = [
        "# Doc Index",
        "",
        f"- Generated: `{doc_index.get('generated', '')}`",
        "",
        "| Doc | Path | Enabled | Generated | Contributors |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in doc_index.get("docs", []):
        contributors = ", ".join(entry.get("contributor_timestamps", [])) or "none"
        lines.append(
            f"| `{entry.get('doc_id', '')}` | `{entry.get('path', '')}` | "
            f"{'yes' if entry.get('enabled') else 'no'} | "
            f"`{entry.get('generated_at') or ''}` | {contributors} |"
        )
    lines.append("")
    return "\n".join(lines)


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
    _write_text_if_missing(paths["doc_index_md"], "# Doc Index\n\nNo managed-doc index generated yet.\n")

    if not paths["completed_tasks_json"].exists():
        _write_json(paths["completed_tasks_json"], {"generated": "", "service_id": service_id, "project_root": str(project_root), "tasks": []})
    if not paths["doc_index_json"].exists():
        _write_json(paths["doc_index_json"], {"generated": "", "service_id": service_id, "project_root": str(project_root), "docs": []})
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

    managed_docs = _normalize_managed_docs(manifest.get("managed_docs"))
    managed_docs_by_id = _managed_doc_by_id(managed_docs)
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

    # Extract new 0.1.8 fields from latest task entries
    runtime_services_entries = [entry for entry in tasks if entry.get("runtime_services")]
    if runtime_services_entries:
        manifest["runtime_services"] = runtime_services_entries[-1]["runtime_services"]

    dependency_entries = [entry for entry in tasks if entry.get("dependencies")]
    if dependency_entries:
        manifest["dependencies"] = dependency_entries[-1]["dependencies"]

    cross_dep_entries = [entry for entry in tasks if entry.get("cross_dependencies")]
    if cross_dep_entries:
        manifest["cross_dependencies"] = cross_dep_entries[-1]["cross_dependencies"]

    bootstrap_version_entries = [entry for entry in tasks if entry.get("bootstrap_version")]
    if bootstrap_version_entries:
        manifest["bootstrap_version"] = bootstrap_version_entries[-1]["bootstrap_version"]

    diagram_entries = [entry for entry in tasks if entry.get("diagram")]
    if diagram_entries:
        manifest["diagram"] = diagram_entries[-1]["diagram"]

    generated_at = utc_now_iso()
    if managed_docs_by_id.get("doc_index_md", {}).get("enabled", False):
        _write_text(paths["doc_index_md"], "# Doc Index\n\nGenerating...\n")

    derived_outputs: dict[str, str] = {
        "handoff": paths["handoff"].read_text(encoding="utf-8"),
        "runbook": paths["runbook"].read_text(encoding="utf-8"),
        "approach_history": paths["approach_history"].read_text(encoding="utf-8"),
        "readme": _render_root_readme(manifest, manifest.get("runtime", {}), tasks),
        "api": _render_root_api(manifest, manifest.get("runtime", {}), scope_snapshot, tasks),
        "changelog": _render_root_changelog(tasks),
    }

    for entry in managed_docs:
        doc_id = str(entry["doc_id"])
        target_path = _managed_doc_path(project_root, entry)
        if entry.get("enabled"):
            if doc_id in derived_outputs:
                _write_text(target_path, derived_outputs[doc_id])
            elif doc_id == "doc_index_json":
                # filled after the first doc-index pass
                pass
            elif doc_id == "doc_index_md":
                # filled after the first doc-index pass
                pass
            entry["last_generated_at"] = generated_at
    def _current_doc_index() -> dict[str, Any]:
        return {
            "generated": generated_at,
            "service_id": manifest["service_id"],
            "project_root": str(project_root),
            "docs": [
                {
                    "doc_id": str(item["doc_id"]),
                    "label": _managed_doc_label(str(item["doc_id"])),
                    "path": item["path"],
                    "enabled": bool(item.get("enabled")),
                    "generated_at": item.get("last_generated_at"),
                    "generated_from": item.get("generated_from", "switchboard/local/tasks-completed.md"),
                    "contributor_timestamps": _contributors_for_doc(str(item["doc_id"]), tasks),
                }
                for item in managed_docs
            ],
        }

    doc_index = _current_doc_index()

    if managed_docs_by_id.get("doc_index_json", {}).get("enabled", False):
        _write_json(paths["doc_index_json"], doc_index)
        managed_docs_by_id["doc_index_json"]["last_generated_at"] = generated_at
    elif not paths["doc_index_json"].exists():
        _write_json(paths["doc_index_json"], doc_index)

    if managed_docs_by_id.get("doc_index_md", {}).get("enabled", False):
        _write_text(paths["doc_index_md"], _render_doc_index_markdown(doc_index))
        managed_docs_by_id["doc_index_md"]["last_generated_at"] = generated_at
    elif not paths["doc_index_md"].exists():
        _write_text(paths["doc_index_md"], _render_doc_index_markdown(doc_index))

    doc_index = _current_doc_index()
    if managed_docs_by_id.get("doc_index_json", {}).get("enabled", False):
        _write_json(paths["doc_index_json"], doc_index)
    if managed_docs_by_id.get("doc_index_md", {}).get("enabled", False):
        _write_text(paths["doc_index_md"], _render_doc_index_markdown(doc_index))

    manifest["managed_docs"] = managed_docs
    manifest["doc_index"] = doc_index
    manifest["updated_at"] = utc_now_iso()
    _write_json(paths["manifest"], manifest)
    return {
        "manifest": manifest,
        "tasks": tasks,
        "scope_snapshot": scope_snapshot,
        "doc_index": doc_index,
    }


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
