"""Collection, download, and git actions."""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

from pathspec import PathSpec

from .config import Settings
from .defaults import DEFAULT_EXCLUDE_GLOBS, DEFAULT_SECRET_PATTERNS, GIT_STATUS_COMMANDS, SAFE_REMOTE_COMMANDS
from .manifests import ManifestStore
from .models import (
    ApiFlowCreateRequest,
    ApiFlowPatchRequest,
    ApiFlowRunRequest,
    CollectRequest,
    DiscoveryTreeRequest,
    DownloadRequest,
    EnvironmentRuntimeSnapshotRequest,
    GitPushRequest,
    GitPullRequest,
    NodeActionRequest,
    NodeSyncRequest,
    ProjectEnvironmentManifest,
    PullBundleRequest,
    RepoActionRequest,
    ResolvedServer,
    RuntimeActionRequest,
    ScanRootRequest,
    ServicePatchRequest,
    ServiceManifest,
)
from .node_runtime import node_status, start_node_runtime, stop_node_runtime
from .storage import SnapshotStore, utc_now_iso

SECRET_CONTENT_PATTERNS = [
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("credential_assignment", re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd|client[_-]?secret)\s*[:=]\s*['\"][^'\"]{4,}['\"]")),
    ("mongodb_uri", re.compile(r"mongodb(?:\+srv)?://[^/\s:@]+:[^/\s:@]+@")),
]
EXPOSURE_LINE_PATTERNS = [
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{20,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("generic_token", re.compile(r"(?i)\b(api[_-]?key|secret|token|client[_-]?secret|password)\b")),
]
GITHUB_REPO = "pratikreddy9/switchboard"
GITHUB_LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


class CollectionCoordinator:
    def __init__(self, settings: Settings, manifests: ManifestStore, snapshots: SnapshotStore) -> None:
        self.settings = settings
        self.manifests = manifests
        self.snapshots = snapshots

    @contextmanager
    def _action_guard(self, action_key: str, service_id: str, ttl_seconds: int = 900) -> Iterator[dict[str, Any] | None]:
        lock = self.snapshots.acquire_action_lock(action_key, service_id, ttl_seconds=ttl_seconds)
        if lock is None:
            yield {
                "status": "action_in_progress",
                "message": f"{action_key} is already running for {service_id}.",
                "service_id": service_id,
                "action_key": action_key,
            }
            return
        try:
            yield None
            self.snapshots.release_action_lock(action_key, service_id, status="completed")
        except Exception:
            self.snapshots.release_action_lock(action_key, service_id, status="failed")
            raise

    def collect_workspace(self, workspace_id: str, request: CollectRequest) -> dict[str, Any]:
        workspace = self.manifests.get_workspace(workspace_id)
        services = self.manifests.get_workspace_services(workspace_id)
        if request.service_ids:
            requested = set(request.service_ids)
            services = [service for service in services if service.service_id in requested]

        server_ids = {
            location.server_id
            for service in services
            for location in service.locations
        }
        if request.service_ids:
            if not server_ids:
                server_ids = set(workspace.servers)
        else:
            server_ids |= set(workspace.servers)
        resolved_servers: dict[str, ResolvedServer] = {}
        server_results = []
        for server_id in sorted(server_ids):
            server_manifest = self.manifests.get_server(server_id)
            try:
                server = self.manifests.resolve_server(server_id, request.runtime_passwords)
                resolved_servers[server_id] = server
                server_results.append(self._collect_server_summary(server_id, server))
            except Exception as exc:
                server_results.append(self._server_failure_result(server_manifest, "unreachable", str(exc)))

        service_results: list[dict[str, Any]] = []
        repo_inventory: list[dict[str, Any]] = []
        docs_index: list[dict[str, Any]] = []
        logs_index: list[dict[str, Any]] = []
        secret_paths: list[dict[str, Any]] = []

        for service in services:
            try:
                result = self._collect_service(service, resolved_servers)
            except Exception as exc:
                result = self._service_failure_result(service, "unreachable", str(exc))
            service_results.append(result["service"])
            repo_inventory.extend(result["repos"])
            docs_index.extend(result["docs"])
            logs_index.extend(result["logs"])
            secret_paths.extend(result["secrets"])

        statuses = [entry["status"] for entry in server_results + service_results]
        summary_status = "ok" if statuses and all(status == "ok" for status in statuses) else "partial"
        if not statuses:
            summary_status = "unverified"

        snapshot = {
            "generated": utc_now_iso(),
            "workspace": workspace.model_dump(mode="json"),
            "servers": server_results,
            "services": service_results,
            "repo_inventory": repo_inventory,
            "docs_index": docs_index,
            "logs_index": logs_index,
            "secret_path_index": secret_paths,
            "summary": {
                "status": summary_status,
                "server_count": len(server_results),
                "service_count": len(service_results),
            },
        }
        self.snapshots.persist_collect_snapshot(snapshot)
        return snapshot

    def scan_root(self, request: ScanRootRequest) -> dict[str, Any]:
        server = self.manifests.resolve_server(
            request.server_id,
            {request.server_id: request.runtime_password} if request.runtime_password else {},
        )
        excludes = list(DEFAULT_EXCLUDE_GLOBS)
        if server.connection_type == "local":
            root = Path(request.root)
            if not root.exists():
                return {"status": "path_missing", "server_id": request.server_id, "root": request.root, "entries": []}
            entries = self._scan_local_root(root, excludes, request.max_depth)
        else:
            with self._open_ssh(server) as connection:
                if connection is None:
                    return {"status": "unreachable", "server_id": request.server_id, "root": request.root, "entries": []}
                _, sftp = connection
                if not self._remote_exists(sftp, request.root):
                    return {"status": "path_missing", "server_id": request.server_id, "root": request.root, "entries": []}
                entries = self._scan_remote_root(sftp, request.root, excludes, request.max_depth)
        return {
            "status": "ok",
            "generated": utc_now_iso(),
            "server_id": request.server_id,
            "root": request.root,
            "entries": entries,
        }

    def browse_tree(self, request: DiscoveryTreeRequest) -> dict[str, Any]:
        server = self.manifests.resolve_server(
            request.server_id,
            {request.server_id: request.runtime_password} if request.runtime_password else {},
        )
        target_path = request.node_path or request.root
        if server.connection_type == "local":
            root = Path(request.root)
            target = Path(target_path)
            if not root.exists() or not target.exists():
                return {
                    "status": "path_missing",
                    "server_id": request.server_id,
                    "root": request.root,
                    "node_path": target_path,
                    "message": "Path not found on the selected host.",
                    "current_node": None,
                    "entries": [],
                }
            try:
                target.resolve().relative_to(root.resolve())
            except ValueError:
                return {
                    "status": "path_missing",
                    "server_id": request.server_id,
                    "root": request.root,
                    "node_path": target_path,
                    "message": "Requested path is outside the selected root.",
                    "current_node": None,
                    "entries": [],
                }
            current_node, entries = self._browse_local_tree(target)
        else:
            with self._open_ssh(server) as connection:
                if connection is None:
                    return {
                        "status": "unreachable",
                        "server_id": request.server_id,
                        "root": request.root,
                        "node_path": target_path,
                        "message": "Could not reach the server over SSH.",
                        "current_node": None,
                        "entries": [],
                    }
                _, sftp = connection
                if not self._remote_exists(sftp, request.root) or not self._remote_exists(sftp, target_path):
                    return {
                        "status": "path_missing",
                        "server_id": request.server_id,
                        "root": request.root,
                        "node_path": target_path,
                        "message": "Path not found on the selected server.",
                        "current_node": None,
                        "entries": [],
                    }
                if not target_path.startswith(request.root):
                    return {
                        "status": "path_missing",
                        "server_id": request.server_id,
                        "root": request.root,
                        "node_path": target_path,
                        "message": "Requested path is outside the selected root.",
                        "current_node": None,
                        "entries": [],
                    }
                current_node, entries = self._browse_remote_tree(sftp, target_path)
        return {
            "status": "ok",
            "generated": utc_now_iso(),
            "server_id": request.server_id,
            "root": request.root,
            "node_path": target_path,
            "current_node": current_node,
            "entries": entries,
        }

    def _server_failure_result(
        self,
        server: ResolvedServer,
        status: str,
        message: str,
    ) -> dict[str, Any]:
        return {
            "server_id": server.server_id,
            "name": server.name,
            "status": status,
            "connection_type": server.connection_type,
            "host": server.host,
            "username": server.username,
            "hostname": server.host,
            "ports": [],
            "firewall": "unverified",
            "services": [],
            "docker": [],
            "message": message,
        }

    def _service_failure_result(
        self,
        service: ServiceManifest,
        status: str,
        message: str,
    ) -> dict[str, Any]:
        return {
            "service": {
                "service_id": service.service_id,
                "workspace_id": service.workspace_id,
                "display_name": service.display_name,
                "status": status,
                "location_count": len(service.locations),
                "doc_count": 0,
                "log_count": 0,
                "secret_path_count": 0,
                "path_aliases": service.path_aliases,
                "notes": service.notes,
                "message": message,
            },
            "repos": [],
            "docs": [],
            "logs": [],
            "secrets": [],
        }

    def download_files(self, service_id: str, request: DownloadRequest) -> dict[str, Any]:
        service = self.manifests.get_service(service_id)
        server_id = request.server_id
        if server_id is None:
            primary = next((location for location in service.locations if location.is_primary), None)
            if primary is None and service.locations:
                primary = service.locations[0]
            if primary is None:
                return {"status": "path_missing", "copied": [], "destination": None}
            server_id = primary.server_id
        server = self.manifests.resolve_server(
            server_id,
            {server_id: request.runtime_password} if request.runtime_password else {},
        )
        timestamp = utc_now_iso().replace(":", "-")
        location_root = self._download_location_root(service, server_id, request.files)
        destination = self.settings.downloads_dir / service.workspace_id / service.service_id / timestamp
        destination.mkdir(parents=True, exist_ok=True)

        copied = []
        if server.connection_type == "local":
            for file_path in request.files:
                source = Path(file_path)
                if not source.exists():
                    continue
                relative = self._bundle_relative_path(source, location_root)
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                copied.append({"source": str(source), "target": str(target)})
        else:
            with self._open_ssh(server) as connection:
                if connection is None:
                    return {"status": "unreachable", "copied": copied, "destination": str(destination), "path": str(destination), "files": []}
                ssh, sftp = connection
                del ssh
                for file_path in request.files:
                    try:
                        relative = self._bundle_relative_path(file_path, location_root)
                        target = destination / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        sftp.get(file_path, str(target))
                        copied.append({"source": file_path, "target": str(target)})
                    except OSError:
                        continue
        return {
            "status": "ok" if copied else "partial",
            "copied": copied,
            "destination": str(destination),
            "path": str(destination),
            "files": [item["target"] for item in copied],
        }

    def git_status(self, service_id: str, request: RepoActionRequest) -> dict[str, Any]:
        service = self.manifests.get_service(service_id)
        server_id = self._resolve_server_id_for_repo(service, request.repo_path, request.server_id)
        if server_id is None:
            return {"status": "path_missing", "message": "No server mapping for repo path.", "repo_path": request.repo_path}
        server = self.manifests.resolve_server(
            server_id,
            {server_id: request.runtime_password} if request.runtime_password else {},
        )
        result = self._repo_status(server, request.repo_path)
        policy = self.manifests.get_repo_policy(service_id, request.repo_path)
        result["push_mode"] = policy.push_mode if policy else "blocked"
        result["safety_profile"] = policy.safety_profile if policy else "generic_python"
        result["push_eligible"] = bool(policy and policy.push_mode == "allowed" and result.get("status") == "ok" and not result.get("dirty"))
        return result

    def safety_check(self, service_id: str, request: RepoActionRequest) -> dict[str, Any]:
        service = self.manifests.get_service(service_id)
        policy = self.manifests.get_repo_policy(service_id, request.repo_path)
        server_id = self._resolve_server_id_for_repo(service, request.repo_path, request.server_id)
        if server_id is None:
            return {"status": "path_missing", "message": "No server mapping for repo path.", "repo_path": request.repo_path}
        server = self.manifests.resolve_server(
            server_id,
            {server_id: request.runtime_password} if request.runtime_password else {},
        )
        repo_state = self._repo_status(server, request.repo_path)
        findings, blocking_reasons = self._run_repo_safety_scan(service_id, server, request.repo_path, repo_state, policy)
        summary = {
            "generated": utc_now_iso(),
            "service_id": service_id,
            "repo_path": request.repo_path,
            "server_id": server_id,
            "scanner": "builtin_patterns",
            "push_mode": policy.push_mode if policy else "blocked",
            "safety_profile": policy.safety_profile if policy else "generic_python",
            "finding_count": len(findings),
            "blocking_reason_count": len(blocking_reasons),
            "blocking_reasons": blocking_reasons,
            "safe_to_push": len(blocking_reasons) == 0,
            "safe_to_deploy": len(blocking_reasons) == 0,
            "status": "ok" if len(blocking_reasons) == 0 else "permission_limited",
        }
        self.snapshots.append_repo_safety_check(summary, findings)
        return {
            **summary,
            "repo_state": repo_state,
        }

    def git_pull(self, service_id: str, request: GitPullRequest) -> dict[str, Any]:
        service = self.manifests.get_service(service_id)
        if request.repo_path not in service.allowed_git_pull_paths:
            return {"status": "permission_limited", "message": "Repo path is not allowlisted.", "repo_path": request.repo_path, "output": ""}

        target_server_id = request.server_id
        if target_server_id is None:
            for location in service.locations:
                if request.repo_path.startswith(location.root):
                    target_server_id = location.server_id
                    break
        if target_server_id is None:
            return {"status": "path_missing", "message": "No server mapping for repo path.", "repo_path": request.repo_path, "output": ""}

        server = self.manifests.resolve_server(
            target_server_id,
            {target_server_id: request.runtime_password} if request.runtime_password else {},
        )
        status_result = self._repo_status(server, request.repo_path)
        if status_result["status"] != "ok":
            return status_result
        if status_result["dirty"]:
            return {"status": "dirty_repo", "message": "Repo is dirty. Refusing git pull.", "repo_path": request.repo_path, "output": "", **status_result}

        if server.connection_type == "local":
            result = self._run_local(["git", "-C", request.repo_path, "pull", "--ff-only"])
            return {
                "status": "ok" if result["returncode"] == 0 else "partial",
                "repo_path": request.repo_path,
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "output": (result["stdout"] or result["stderr"]).strip(),
            }

        with self._open_ssh(server) as connection:
            if connection is None:
                return {"status": "unreachable", "message": "SSH connection failed.", "repo_path": request.repo_path, "output": ""}
            ssh, _ = connection
            command = f"git -C {self._quote(request.repo_path)} pull --ff-only"
            result = self._run_remote(ssh, command)
            return {
                "status": "ok" if result["returncode"] == 0 else "partial",
                "repo_path": request.repo_path,
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "output": (result["stdout"] or result["stderr"]).strip(),
            }

    def git_push(self, service_id: str, request: GitPushRequest) -> dict[str, Any]:
        safety = self.safety_check(
            service_id,
            RepoActionRequest(
                repo_path=request.repo_path,
                server_id=request.server_id,
                runtime_password=request.runtime_password,
            ),
        )
        if not safety.get("safe_to_push"):
            return {
                "status": "permission_limited",
                "repo_path": request.repo_path,
                "message": "Repo failed safety check.",
                "output": "; ".join(safety.get("blocking_reasons", [])),
                "safety": safety,
            }

        service = self.manifests.get_service(service_id)
        server_id = self._resolve_server_id_for_repo(service, request.repo_path, request.server_id)
        if server_id is None:
            return {"status": "path_missing", "message": "No server mapping for repo path.", "repo_path": request.repo_path, "output": ""}
        server = self.manifests.resolve_server(
            server_id,
            {server_id: request.runtime_password} if request.runtime_password else {},
        )
        repo_state = self._repo_status(server, request.repo_path)
        remote = request.remote or "origin"
        branch = request.branch or repo_state.get("branch") or "HEAD"

        if server.connection_type == "local":
            result = self._run_local(["git", "-C", request.repo_path, "push", remote, branch])
        else:
            with self._open_ssh(server) as connection:
                if connection is None:
                    return {"status": "unreachable", "message": "SSH connection failed.", "repo_path": request.repo_path, "output": ""}
                ssh, _ = connection
                command = f"git -C {self._quote(request.repo_path)} push {self._quote(remote)} {self._quote(branch)}"
                result = self._run_remote(ssh, command)
        return {
            "status": "ok" if result["returncode"] == 0 else "partial",
            "repo_path": request.repo_path,
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "output": (result["stdout"] or result["stderr"]).strip(),
        }

    def runtime_check(self, service_id: str, request: RuntimeActionRequest) -> dict[str, Any]:
        service = self.manifests.get_service(service_id)
        location = self._select_location(service, location_id=request.location_id)
        if location is None:
            return {"status": "path_missing", "message": "No service location available."}

        server = self.manifests.resolve_server(
            location.server_id,
            {location.server_id: request.runtime_password} if request.runtime_password else {},
        )
        details = self._runtime_snapshot_for_location(service, location, server)
        detected_ports = [self._port_info_from_listener(listener) for listener in details["listeners"]]
        detected_process_command = self._lookup_process_command(
            server,
            details["listeners"][0].get("pid") if details["listeners"] else None,
        )
        result = {
            "service_id": service_id,
            "location_id": location.location_id,
            "server_id": location.server_id,
            "root": location.root,
            "status": details["status"],
            "checked_at": details["checked_at"],
            "configured_ports": details["configured_ports"],
            "detected_ports": detected_ports,
            "missing_ports": details["missing_ports"],
            "healthcheck_command": details["healthcheck_command"],
            "healthcheck_status": details["healthcheck_status"],
            "healthcheck_output": details["healthcheck_output"],
            "detected_process_command": detected_process_command,
            "run_command_hint": details["run_command_hint"],
            "monitoring_mode": details["monitoring_mode"],
            "notes": details["notes"],
            "node_present": details["node_present"],
            "execution_mode": details["execution_mode"],
            "source": "runtime_snapshot",
            "firewall_status": details["firewall_status"],
            "unexpected_ports": details["unexpected_ports"],
            "process_findings": self._runtime_process_findings(location.server_id, details["listeners"]),
            "exposed_ports": details["exposed_ports"],
            "operator_commands": details["operator_commands"],
        }
        self.snapshots.persist_runtime_check(service_id, location.location_id, result)
        return result

    def _runtime_snapshot_for_location(
        self,
        service: ServiceManifest,
        location: Any,
        server: ResolvedServer,
    ) -> dict[str, Any]:
        runtime = location.runtime
        configured_ports = runtime.expected_ports
        execution_mode = getattr(service, "execution_mode", "networked")
        inspect_ports = execution_mode == "networked" or bool(configured_ports)
        run_healthcheck = execution_mode != "docs_only" and bool(runtime.healthcheck_command.strip())
        checked_at = utc_now_iso()

        if server.connection_type == "local":
            listeners = self._collect_local_listener_details() if inspect_ports else []
            listeners = self._filter_listeners_for_location(service, location, server, listeners)
            firewall_status = self._local_firewall_status()
            node_present = self._local_node_manifest_path(location.root).exists()
            health_result = self._run_healthcheck_local(runtime.healthcheck_command) if run_healthcheck else {"status": "skipped", "output": ""}
        else:
            with self._open_ssh(server) as connection:
                if connection is None:
                    return {
                        "service_id": service.service_id,
                        "location_id": location.location_id,
                        "server_id": location.server_id,
                        "root": location.root,
                        "status": "unreachable",
                        "checked_at": checked_at,
                        "configured_ports": configured_ports,
                        "listeners": [],
                        "missing_ports": configured_ports,
                        "unexpected_ports": [],
                        "firewall_status": "unverified",
                        "healthcheck_command": runtime.healthcheck_command,
                        "healthcheck_status": "skipped",
                        "healthcheck_output": "",
                        "run_command_hint": runtime.run_command_hint,
                        "monitoring_mode": runtime.monitoring_mode,
                        "notes": runtime.notes,
                        "node_present": False,
                        "execution_mode": execution_mode,
                        "exposed_ports": [],
                        "operator_commands": self._operator_commands_for_findings(server, location, [], "unverified", runtime.healthcheck_command),
                    }
                ssh, sftp = connection
                listeners = self._collect_remote_listener_details(ssh) if inspect_ports else []
                firewall_status = self._remote_firewall_status(ssh)
                node_present = self._remote_exists(sftp, self._remote_node_manifest_path(location.root))
                health_result = self._run_healthcheck_remote(ssh, runtime.healthcheck_command) if run_healthcheck else {"status": "skipped", "output": ""}

        matched_ports = [entry for entry in listeners if entry["port"] in configured_ports] if configured_ports else listeners
        missing_ports = [port for port in configured_ports if port not in {entry["port"] for entry in listeners}] if inspect_ports else []
        unexpected_ports = sorted(
            [entry["port"] for entry in listeners if configured_ports and entry["port"] not in configured_ports]
        )
        exposed_ports = self._classify_port_exposure(server, listeners, configured_ports)
        operator_commands = self._operator_commands_for_findings(
            server,
            location,
            exposed_ports,
            firewall_status,
            runtime.healthcheck_command,
        )

        status = "ok"
        if execution_mode == "networked" and configured_ports and missing_ports:
            status = "partial"
        if health_result["status"] == "failed":
            status = "partial"
        if exposed_ports and any(item.get("exposure") == "public" and not item.get("expected") for item in exposed_ports):
            status = "partial"
        if execution_mode == "networked" and not configured_ports and not runtime.healthcheck_command and not listeners:
            status = "unverified"

        return {
            "service_id": service.service_id,
            "location_id": location.location_id,
            "server_id": location.server_id,
            "root": location.root,
            "status": status,
            "checked_at": checked_at,
            "configured_ports": configured_ports,
            "listeners": listeners,
            "missing_ports": missing_ports,
            "unexpected_ports": unexpected_ports,
            "firewall_status": firewall_status,
            "healthcheck_command": runtime.healthcheck_command,
            "healthcheck_status": health_result["status"],
            "healthcheck_output": health_result["output"],
            "run_command_hint": runtime.run_command_hint,
            "monitoring_mode": runtime.monitoring_mode,
            "notes": runtime.notes,
            "node_present": node_present,
            "execution_mode": execution_mode,
            "exposed_ports": exposed_ports,
            "operator_commands": operator_commands,
            "matched_ports": matched_ports,
        }

    def _filter_listeners_for_location(
        self,
        service: ServiceManifest,
        location: Any,
        server: ResolvedServer,
        listeners: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if server.connection_type != "local":
            return listeners
        owned: list[dict[str, Any]] = []
        configured_ports = set(getattr(location.runtime, "expected_ports", []) or [])
        for listener in listeners:
            owner = self._tracked_owner_for_listener(location.server_id, listener)
            if owner and owner.get("service_id") == service.service_id and owner.get("location_id") == location.location_id:
                owned.append(listener)
                continue
            pid = listener.get("pid")
            command = self._lookup_process_command(server, pid) if isinstance(pid, int) else ""
            if location.root and location.root in command:
                owned.append(listener)
                continue
            port = listener.get("port")
            if isinstance(port, int) and port in configured_ports:
                owned.append(listener)
        return owned

    def workspace_health_check(self, workspace_id: str, runtime_passwords: dict[str, str] | None = None) -> dict[str, Any]:
        results = []
        services = self.manifests.get_workspace_services(workspace_id)
        passwords = runtime_passwords or {}
        for service in services:
            for location in service.locations:
                req = RuntimeActionRequest(
                    location_id=location.location_id,
                    runtime_password=passwords.get(location.server_id, "")
                )
                try:
                    res = self.runtime_check(service.service_id, req)
                    results.append(res)
                except Exception as e:
                    results.append({"service_id": service.service_id, "location_id": location.location_id, "status": "error", "error": str(e)})
        return {"workspace_id": workspace_id, "results": results, "timestamp": utc_now_iso()}

    def environment_runtime_snapshot(
        self,
        environment_id: str,
        request: EnvironmentRuntimeSnapshotRequest | None = None,
    ) -> dict[str, Any]:
        environment = self.manifests.get_project_environment(environment_id)
        services = {service.service_id: service for service in self.manifests.load_services()}
        passwords = request.runtime_passwords if request else {}
        snapshot = self._build_environment_runtime_snapshot(environment, services, passwords)
        self.snapshots.persist_environment_runtime_snapshot(environment_id, snapshot)
        return snapshot

    def get_environment_lab(self, environment_id: str) -> dict[str, Any]:
        environment = self.manifests.get_project_environment(environment_id)
        project = self.manifests.get_project(environment.project_id)
        services = {service.service_id: service for service in self.manifests.load_services()}
        bundles = self.snapshots.list_all_pull_bundles()
        environment_view = self._project_environment_view(environment, services, bundles)
        snapshot = self.snapshots.get_environment_runtime_snapshot(environment_id)
        flows = [flow.model_dump(mode="json") for flow in self.manifests.get_environment_api_flows(environment_id)]
        runs = {
            flow["flow_id"]: self.snapshots.get_api_flow_runs(environment_id, flow["flow_id"])
            for flow in flows
        }
        return {
            "project": project.model_dump(mode="json"),
            "environment": environment_view,
            "runtime_snapshot": snapshot,
            "api_flows": flows,
            "api_runs": runs,
        }

    def list_api_flows(self, environment_id: str) -> dict[str, Any]:
        self.manifests.get_project_environment(environment_id)
        flows = [flow.model_dump(mode="json") for flow in self.manifests.get_environment_api_flows(environment_id)]
        return {"environment_id": environment_id, "flows": flows}

    def create_api_flow(self, environment_id: str, request: ApiFlowCreateRequest) -> dict[str, Any]:
        flow = self.manifests.create_api_flow(environment_id, request)
        return {"status": "ok", "flow": flow.model_dump(mode="json")}

    def patch_api_flow(self, environment_id: str, flow_id: str, request: ApiFlowPatchRequest) -> dict[str, Any]:
        flow = self.manifests.patch_api_flow(environment_id, flow_id, request)
        return {"status": "ok", "flow": flow.model_dump(mode="json")}

    def delete_api_flow(self, environment_id: str, flow_id: str) -> dict[str, Any]:
        flow = self.manifests.delete_api_flow(environment_id, flow_id)
        return {"status": "ok", "flow": flow.model_dump(mode="json")}

    def run_api_flow(self, environment_id: str, flow_id: str, _request: ApiFlowRunRequest | None = None) -> dict[str, Any]:
        environment = self.manifests.get_project_environment(environment_id)
        flow = self.manifests.get_api_flow(environment_id, flow_id)
        run_record = self._execute_api_flow(environment, flow)
        self.snapshots.append_api_flow_run(environment_id, flow_id, run_record)
        return {"status": run_record["status"], "run": run_record}

    def get_api_flow_runs(self, environment_id: str, flow_id: str) -> dict[str, Any]:
        self.manifests.get_api_flow(environment_id, flow_id)
        return {"environment_id": environment_id, "flow_id": flow_id, "runs": self.snapshots.get_api_flow_runs(environment_id, flow_id)}

    def get_environment_pull_rollup(self, environment_id: str) -> dict[str, Any]:
        environment = self.manifests.get_project_environment(environment_id)
        services = {service.service_id: service for service in self.manifests.load_services()}
        bundles = self.snapshots.list_all_pull_bundles()
        view = self._project_environment_view(environment, services, bundles)
        return {"environment_id": environment_id, "pull_rollup": view["pull_summary"]}

    def list_workspace_project_context(self, workspace_id: str) -> dict[str, Any]:
        self.manifests.get_workspace(workspace_id)
        projects = self.manifests.get_workspace_projects(workspace_id)
        environments = self.manifests.get_workspace_project_environments(workspace_id)
        services = {
            service.service_id: service
            for service in self.manifests.get_workspace_services(workspace_id)
        }
        bundles = self.snapshots.list_all_pull_bundles()

        enriched_environments: list[dict[str, Any]] = []
        rollups: list[dict[str, Any]] = []
        for environment in environments:
            enriched = self._project_environment_view(environment, services, bundles)
            enriched_environments.append(enriched)
            rollups.append(enriched["pull_summary"])

        return {
            "projects": [project.model_dump(mode="json") for project in projects],
            "environments": enriched_environments,
            "rollups": rollups,
        }

    def _build_environment_runtime_snapshot(
        self,
        environment: ProjectEnvironmentManifest,
        services: dict[str, ServiceManifest],
        runtime_passwords: dict[str, str],
    ) -> dict[str, Any]:
        captured_at = utc_now_iso()
        location_rows: list[dict[str, Any]] = []
        open_ports: set[int] = set()
        expected_ports: set[int] = set()
        unexpected_ports: set[int] = set()
        exposed_ports: list[dict[str, Any]] = []
        process_findings: list[dict[str, Any]] = []
        operator_commands: list[dict[str, Any]] = []
        node_findings: list[dict[str, Any]] = []
        firewall_states: list[str] = []

        for deployment in environment.deployments:
            service = services.get(deployment.service_id)
            if service is None:
                continue
            location = self._select_location(service, location_id=deployment.location_id)
            if location is None and service.locations:
                location = service.locations[0]
            if location is None:
                continue
            server = self.manifests.resolve_server(location.server_id, runtime_passwords)
            details = self._runtime_snapshot_for_location(service, location, server)
            for listener in details["listeners"]:
                open_ports.add(int(listener["port"]))
                process_findings.append(
                    self._process_finding_from_listener(
                        listener,
                        self._tracked_owner_for_listener(location.server_id, listener),
                    )
                )
            for port in details["configured_ports"]:
                expected_ports.add(int(port))
            for port in details["unexpected_ports"]:
                unexpected_ports.add(int(port))
            exposed_ports = self._merge_port_exposure(exposed_ports, details["exposed_ports"])
            operator_commands = self._merge_operator_commands(operator_commands, details["operator_commands"])
            firewall_states.append(details["firewall_status"])
            node_findings.append(
                {
                    "service_id": service.service_id,
                    "location_id": location.location_id,
                    "server_id": location.server_id,
                    "node_present": details["node_present"],
                }
            )
            location_rows.append(
                {
                    "service_id": service.service_id,
                    "service_name": service.display_name,
                    "execution_mode": getattr(service, "execution_mode", "networked"),
                    "location_id": location.location_id,
                    "server_id": location.server_id,
                    "root": location.root,
                    "host": server.host,
                    "firewall_status": details["firewall_status"],
                    "node_status": "present" if details["node_present"] else "missing",
                    "expected_ports": details["configured_ports"],
                    "open_ports": [listener["port"] for listener in details["listeners"]],
                    "unexpected_ports": details["unexpected_ports"],
                    "exposed_ports": details["exposed_ports"],
                    "process_findings": self._runtime_process_findings(location.server_id, details["listeners"]),
                    "operator_commands": details["operator_commands"],
                    "runtime_hint": details["run_command_hint"],
                    "healthcheck_command": details["healthcheck_command"],
                    "healthcheck_status": details["healthcheck_status"],
                    "healthcheck_output": details["healthcheck_output"],
                }
            )

        firewall_status = firewall_states[0] if firewall_states and all(state == firewall_states[0] for state in firewall_states) else "mixed"
        return {
            "environment_id": environment.environment_id,
            "captured_at": captured_at,
            "locations": location_rows,
            "open_ports": sorted(open_ports),
            "expected_ports": sorted(expected_ports),
            "unexpected_ports": sorted(unexpected_ports),
            "exposed_ports": exposed_ports,
            "firewall_status": firewall_status if firewall_states else "unverified",
            "process_findings": process_findings,
            "node_findings": node_findings,
            "operator_commands": operator_commands,
        }

    def _merge_port_exposure(self, current: list[dict[str, Any]], additions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen = {
            f"{entry.get('host','')}|{entry.get('port','')}|{entry.get('bind_address','')}"
            for entry in current
        }
        merged = list(current)
        for entry in additions:
            key = f"{entry.get('host','')}|{entry.get('port','')}|{entry.get('bind_address','')}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(entry)
        return merged

    def _merge_operator_commands(self, current: list[dict[str, Any]], additions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen = {f"{entry.get('category','')}|{entry.get('command','')}" for entry in current}
        merged = list(current)
        for entry in additions:
            key = f"{entry.get('category','')}|{entry.get('command','')}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(entry)
        return merged

    def _runtime_process_findings(self, server_id: str, listeners: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            self._process_finding_from_listener(listener, self._tracked_owner_for_listener(server_id, listener))
            for listener in listeners
        ]

    def _process_finding_from_listener(self, listener: dict[str, Any], owner: dict[str, Any] | None = None) -> dict[str, Any]:
        owner = owner or {}
        return {
            "port": listener.get("port"),
            "bind_address": listener.get("bind_address", ""),
            "process_name": listener.get("process", ""),
            "pid": listener.get("pid"),
            "state": listener.get("state", ""),
            "raw": listener.get("raw", ""),
            "owner_service_id": owner.get("service_id", ""),
            "owner_display_name": owner.get("display_name", ""),
            "owner_location_id": owner.get("location_id", ""),
            "owner_root": owner.get("root", ""),
        }

    def _tracked_port_owners(self, server_id: str) -> dict[int, dict[str, Any]]:
        cache = self.snapshots._read_runtime_cache()
        node_viewers = cache.get("node_viewer", {})
        owners: dict[int, dict[str, Any]] = {}
        for service in self.manifests.load_services():
            task_ledger = self.snapshots.get_service_task_ledger(service.service_id)
            tasks = task_ledger.get("tasks", [])
            latest_task = tasks[0] if tasks else {}
            runtime_services = latest_task.get("runtime_services", []) if isinstance(latest_task, dict) else []
            for location in service.locations:
                if location.server_id != server_id:
                    continue
                owner = {
                    "service_id": service.service_id,
                    "display_name": service.display_name,
                    "location_id": location.location_id,
                    "root": location.root,
                }
                tracked_ports: set[int] = set()
                for port in getattr(location.runtime, "expected_ports", []) or []:
                    if isinstance(port, int) and port > 0:
                        tracked_ports.add(port)
                for runtime_service in runtime_services or []:
                    port = runtime_service.get("port") if isinstance(runtime_service, dict) else getattr(runtime_service, "port", None)
                    if isinstance(port, int) and port > 0:
                        tracked_ports.add(port)
                cached_node = node_viewers.get(service.service_id, {}).get(location.location_id, {})
                cached_port = cached_node.get("runtime_port")
                if isinstance(cached_port, int) and cached_port > 0:
                    tracked_ports.add(cached_port)
                for port in tracked_ports:
                    owners.setdefault(port, owner)
        return owners

    def _tracked_owner_for_listener(self, server_id: str, listener: dict[str, Any]) -> dict[str, Any] | None:
        port = listener.get("port")
        if not isinstance(port, int):
            return None
        return self._tracked_port_owners(server_id).get(port)

    def _port_info_from_listener(self, listener: dict[str, Any]) -> dict[str, Any]:
        return {
            "port": listener.get("port"),
            "protocol": listener.get("protocol", "tcp"),
            "process": listener.get("process", ""),
            "pid": listener.get("pid"),
            "state": listener.get("state", ""),
            "bind_address": listener.get("bind_address", ""),
        }

    def _local_firewall_status(self) -> str:
        result = self._run_local(["sh", "-lc", SAFE_REMOTE_COMMANDS["firewall"]])
        return (result["stdout"] or result["stderr"]).strip() or "unverified"

    def _remote_firewall_status(self, ssh: Any) -> str:
        result = self._run_remote(ssh, SAFE_REMOTE_COMMANDS["firewall"])
        return (result["stdout"] or result["stderr"]).strip() or "unverified"

    def _classify_port_exposure(
        self,
        server: ResolvedServer,
        listeners: list[dict[str, Any]],
        configured_ports: list[int],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for listener in listeners:
            bind = str(listener.get("bind_address", "") or "")
            exposure = "unknown"
            notes = ""
            if bind.startswith("127.") or bind in {"::1", "localhost"}:
                exposure = "local_only"
                notes = "Bound to loopback only."
            elif bind in {"0.0.0.0", "*", "::", "[::]"} or bind.startswith("0.0.0.0"):
                exposure = "public"
                notes = "Bound on all interfaces."
            rows.append(
                {
                    "host": server.host,
                    "port": listener.get("port"),
                    "bind_address": bind,
                    "process_name": listener.get("process", ""),
                    "expected": listener.get("port") in configured_ports,
                    "exposure": exposure,
                    "notes": notes,
                }
            )
        return rows

    def _operator_commands_for_findings(
        self,
        server: ResolvedServer,
        location: Any,
        exposed_ports: list[dict[str, Any]],
        firewall_status: str,
        healthcheck_command: str,
    ) -> list[dict[str, Any]]:
        host_prefix = "" if server.connection_type == "local" else f"ssh {server.username}@{server.host} "
        commands: list[dict[str, Any]] = [
            {
                "category": "inspect_only",
                "label": "List listening ports",
                "command": f"{host_prefix}ss -ltnp",
                "notes": f"Verify listeners for {location.root}.",
            },
            {
                "category": "verify_node",
                "label": "Check Switchboard node",
                "command": f"{host_prefix}switchboard node status --project-root {location.root}",
                "notes": "Confirms node runtime without changing it.",
            },
        ]
        if firewall_status and firewall_status != "unverified":
            commands.append(
                {
                    "category": "verify_firewall",
                    "label": "Inspect firewall",
                    "command": f"{host_prefix}{SAFE_REMOTE_COMMANDS['firewall']}",
                    "notes": "Read-only firewall inspection.",
                }
            )
        if healthcheck_command.strip():
            commands.append(
                {
                    "category": "verify_health",
                    "label": "Replay health check",
                    "command": healthcheck_command,
                    "notes": "Operator-run verification only.",
                }
            )
        for port in exposed_ports:
            if port.get("exposure") != "public":
                continue
            commands.append(
                {
                    "category": "verify_listener",
                    "label": f"Inspect port {port.get('port')}",
                    "command": f"{host_prefix}lsof -nP -iTCP:{port.get('port')} -sTCP:LISTEN",
                    "notes": "Verify whether this public listener is intentional.",
                }
            )
        return commands

    def sync_from_node(self, service_id: str, request: NodeSyncRequest) -> dict[str, Any]:
        with self._action_guard("sync_from_node", service_id) as lock_error:
            if lock_error is not None:
                return lock_error
            service = self.manifests.get_service(service_id)
            location = self._select_location(service, location_id=request.location_id)
            if location is None:
                return {"status": "path_missing", "message": "No service location available."}

            node_manifest: dict[str, Any] | None = None
            scope_snapshot: dict[str, Any] | None = None
            doc_index: dict[str, Any] | None = None
            server_id = location.server_id
            server = self.manifests.resolve_server(
                server_id,
                {server_id: request.runtime_password} if request.runtime_password else {},
            )

            completed_tasks: dict[str, Any] | None = None

            if server.connection_type == "local":
                node_manifest_path = self._local_node_manifest_path(location.root)
                scope_snapshot_path = self._local_scope_snapshot_path(location.root)
                doc_index_path = self._local_doc_index_path(location.root)
                node_manifest = self._read_local_json(node_manifest_path)
                scope_snapshot = self._read_local_json(scope_snapshot_path)
                doc_index = self._read_local_json(doc_index_path)
                if request.include_task_ledger:
                    completed_tasks = self._read_local_json(self._local_completed_tasks_path(location.root))
            else:
                with self._open_ssh(server) as connection:
                    if connection is None:
                        return {"status": "unreachable", "message": "SSH connection failed."}
                    _, sftp = connection
                    node_manifest = self._read_remote_json(sftp, self._remote_node_manifest_path(location.root))
                    scope_snapshot = self._read_remote_json(sftp, self._remote_scope_snapshot_path(location.root))
                    doc_index = self._read_remote_json(sftp, self._remote_doc_index_path(location.root))
                    if request.include_task_ledger:
                        completed_tasks = self._read_remote_json(sftp, self._remote_completed_tasks_path(location.root))

            if not node_manifest:
                return {"status": "path_missing", "message": "Node manifest not found at selected location."}
            if request.include_task_ledger and completed_tasks and completed_tasks.get("tasks"):
                self.snapshots.persist_task_ledger(service_id, location.location_id, completed_tasks["tasks"])

            updated_locations = [item.model_dump(mode="json") for item in service.locations]
            for item in updated_locations:
                if item["location_id"] == location.location_id and request.include_runtime_config:
                    item["runtime"] = node_manifest.get("runtime", item.get("runtime", {}))

            patch_payload: dict[str, Any] = {"locations": updated_locations}
            if node_manifest.get("managed_docs"):
                patch_payload["managed_docs"] = node_manifest["managed_docs"]
            should_import_scope = (
                request.include_scope_snapshot
                and scope_snapshot is not None
                and scope_snapshot.get("scope_entries")
                and (
                    scope_snapshot.get("scope_updates")
                    or any(
                        entry.get("source") not in {"node_manifest", "seeded"}
                        for entry in scope_snapshot.get("scope_entries", [])
                    )
                )
            )
            if should_import_scope:
                scope_entries = scope_snapshot["scope_entries"]
                flattened = self._flatten_scope_entries(scope_entries)
                patch_payload.update(
                    {
                        "scope_entries": scope_entries,
                        "repo_paths": flattened["repo_paths"],
                        "docs_paths": flattened["docs_paths"],
                        "log_paths": flattened["log_paths"],
                        "exclude_globs": flattened["exclude_globs"],
                        "allowed_git_pull_paths": flattened["repo_paths"],
                        "repo_policies": self._repo_policies_for_paths(flattened["repo_paths"]),
                    }
                )

            updated_service = self.manifests.patch_service(service_id, ServicePatchRequest(**patch_payload))
            task_ledger_count = len(completed_tasks.get("tasks", [])) if completed_tasks else 0
            record = {
                "service_id": service_id,
                "location_id": location.location_id,
                "direction": "from_node",
                "timestamp": utc_now_iso(),
                "status": "ok",
                "source": "node",
                "target": "control_center",
                "include_scope_snapshot": request.include_scope_snapshot,
                "include_runtime_config": request.include_runtime_config,
                "managed_docs": node_manifest.get("managed_docs", []),
                "doc_index": doc_index or node_manifest.get("doc_index", {}),
                "task_ledger_count": task_ledger_count,
                "bootstrap_version": node_manifest.get("bootstrap_version", ""),
                "runtime_services": node_manifest.get("runtime_services", []),
                "dependencies": node_manifest.get("dependencies", []),
                "cross_dependencies": node_manifest.get("cross_dependencies", []),
            }
            self.snapshots.persist_node_sync(service_id, location.location_id, record)
            return {
                "status": "ok",
                "service": updated_service.model_dump(mode="json"),
                "sync": record,
            }

    def sync_to_node(self, service_id: str, request: NodeSyncRequest) -> dict[str, Any]:
        with self._action_guard("sync_to_node", service_id) as lock_error:
            if lock_error is not None:
                return lock_error
            service = self.manifests.get_service(service_id)
            location = self._select_location(service, location_id=request.location_id)
            if location is None:
                return {"status": "path_missing", "message": "No service location available."}

            server_id = location.server_id
            server = self.manifests.resolve_server(
                server_id,
                {server_id: request.runtime_password} if request.runtime_password else {},
            )
            location_scope_entries = self._scope_entries_for_location(service, location.root)
            flattened = self._flatten_scope_entries(location_scope_entries)

            if server.connection_type == "local":
                manifest_path = self._local_node_manifest_path(location.root)
                scope_path = self._local_scope_snapshot_path(location.root)
                bundle_history_path = self._local_pull_bundle_history_path(location.root)
                doc_index_path = self._local_doc_index_path(location.root)
                existing_manifest = self._read_local_json(manifest_path)
                if not existing_manifest:
                    return {"status": "path_missing", "message": "Node manifest not found at selected location."}
                updated_manifest = self._updated_node_manifest(
                    existing_manifest,
                    service,
                    location,
                    flattened,
                    request.include_runtime_config,
                )
                self._write_local_json(manifest_path, updated_manifest)
                if request.include_scope_snapshot:
                    scope_payload = self._updated_scope_snapshot(
                        self._read_local_json(scope_path),
                        service,
                        location.root,
                        location_scope_entries,
                    )
                    self._write_local_json(scope_path, scope_payload)
                self._write_local_json(bundle_history_path, self._node_pull_bundle_history_payload(service_id))
                existing_doc_index = self._read_local_json(doc_index_path) or updated_manifest.get("doc_index", {})
            else:
                with self._open_ssh(server) as connection:
                    if connection is None:
                        return {"status": "unreachable", "message": "SSH connection failed."}
                    ssh, sftp = connection
                    manifest_path = self._remote_node_manifest_path(location.root)
                    scope_path = self._remote_scope_snapshot_path(location.root)
                    bundle_history_path = self._remote_pull_bundle_history_path(location.root)
                    doc_index_path = self._remote_doc_index_path(location.root)
                    existing_manifest = self._read_remote_json(sftp, manifest_path)
                    if not existing_manifest:
                        return {"status": "path_missing", "message": "Node manifest not found at selected location."}
                    updated_manifest = self._updated_node_manifest(
                        existing_manifest,
                        service,
                        location,
                        flattened,
                        request.include_runtime_config,
                    )
                    self._write_remote_json(ssh, sftp, manifest_path, updated_manifest)
                    if request.include_scope_snapshot:
                        scope_payload = self._updated_scope_snapshot(
                            self._read_remote_json(sftp, scope_path),
                            service,
                            location.root,
                            location_scope_entries,
                        )
                        self._write_remote_json(ssh, sftp, scope_path, scope_payload)
                    self._write_remote_json(ssh, sftp, bundle_history_path, self._node_pull_bundle_history_payload(service_id))
                    existing_doc_index = self._read_remote_json(sftp, doc_index_path) or updated_manifest.get("doc_index", {})

            record = {
                "service_id": service_id,
                "location_id": location.location_id,
                "direction": "to_node",
                "timestamp": utc_now_iso(),
                "status": "ok",
                "source": "control_center",
                "target": "node",
                "include_scope_snapshot": request.include_scope_snapshot,
                "include_runtime_config": request.include_runtime_config,
                "managed_docs": [entry.model_dump(mode="json") for entry in service.managed_docs],
                "doc_index": existing_doc_index,
            }
            self.snapshots.persist_node_sync(service_id, location.location_id, record)
            return {
                "status": "ok",
                "sync": record,
                "node_manifest_path": self._remote_node_manifest_path(location.root)
                if server.connection_type == "ssh"
                else str(self._local_node_manifest_path(location.root)),
            }

    def pull_bundle(self, service_id: str, request: PullBundleRequest) -> dict[str, Any]:
        with self._action_guard("pull_bundle", service_id) as lock_error:
            if lock_error is not None:
                return lock_error
            service = self.manifests.get_service(service_id)
            location = self._select_location(service, request.server_id)
            if location is None:
                return {"status": "path_missing", "message": "No service location available."}
            server_id = location.server_id
            server = self.manifests.resolve_server(
                server_id,
                {server_id: request.runtime_password} if request.runtime_password else {},
            )
            timestamp = utc_now_iso().replace(":", "").replace("-", "")
            bundle_id = f"{service.workspace_id}__{service.service_id}__{server_id}__{timestamp}".replace("+0000", "Z")
            bundle_root = self.settings.downloads_dir / service.workspace_id / service.service_id / bundle_id
            mirrored_root = bundle_root / "source_tree"
            mirrored_root.mkdir(parents=True, exist_ok=True)

            scope_entries = [entry for entry in service.scope_entries if entry.enabled]
            scope_entries.extend(request.extra_includes)
            exclude_patterns = list(dict.fromkeys(DEFAULT_EXCLUDE_GLOBS + [entry.path for entry in service.scope_entries if entry.enabled and entry.kind == "exclude"] + request.extra_excludes))

            copied_files: list[dict[str, Any]] = []
            skipped_entries: list[dict[str, Any]] = []
            if server.connection_type == "local":
                copied_files, skipped_entries = self._copy_bundle_local(service, location.root, scope_entries, exclude_patterns, mirrored_root)
            else:
                with self._open_ssh(server) as connection:
                    if connection is None:
                        return {"status": "unreachable", "message": "SSH connection failed."}
                    _, sftp = connection
                    copied_files, skipped_entries = self._copy_bundle_remote(service, sftp, location.root, scope_entries, exclude_patterns, mirrored_root)

            repo_metadata = []
            for repo_path in service.repo_paths:
                if repo_path.startswith(location.root):
                    repo_metadata.append(self._repo_status(server, repo_path))

            previous_bundle = next((bundle for bundle in self.snapshots.list_pull_bundles(service_id) if bundle.get("server_id") == server_id), None)
            diff_summary, diff_entries = self._bundle_diff(previous_bundle, copied_files)
            exposure_findings = self._bundle_exposure_findings(bundle_root / "source_tree", copied_files)
            dependency_context = self._bundle_dependency_context(service)
            manifest = {
                "bundle_id": bundle_id,
                "created_at": utc_now_iso(),
                "workspace_id": service.workspace_id,
                "service_id": service.service_id,
                "server_id": server_id,
                "location_root": location.root,
                "saved_scope": [entry.model_dump(mode="json") for entry in service.scope_entries if entry.enabled],
                "extra_includes": [entry.model_dump(mode="json") for entry in request.extra_includes],
                "extra_excludes": request.extra_excludes,
                "note": request.note,
                "compared_to_bundle_id": previous_bundle.get("bundle_id") if previous_bundle else "",
                "diff_summary": diff_summary,
                "diff_entries": diff_entries,
                "exposure_findings": exposure_findings,
                "dependency_context": dependency_context,
                "repo_metadata": repo_metadata,
                "files": copied_files,
                "skipped_entries": skipped_entries,
            }
            manifest_path = bundle_root / "bundle-manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            history_record = {
                "bundle_id": bundle_id,
                "created_at": manifest["created_at"],
                "workspace_id": service.workspace_id,
                "service_id": service.service_id,
                "server_id": server_id,
                "file_count": len(copied_files),
                "docs_count": len([item for item in copied_files if item["kind"] == "doc"]),
                "logs_count": len([item for item in copied_files if item["kind"] == "log"]),
                "bundle_path": str(bundle_root),
                "source_tree_path": str(mirrored_root),
                "manifest_path": str(manifest_path),
                "repo_commits": [item.get("last_commit", "") for item in repo_metadata if item.get("status") == "ok"],
                "note": request.note,
                "compared_to_bundle_id": previous_bundle.get("bundle_id") if previous_bundle else "",
                "diff_summary": diff_summary,
                "diff_entries": diff_entries,
                "exposure_findings": exposure_findings,
                "dependency_context": dependency_context,
                "skipped_entry_count": len(skipped_entries),
                "skipped_entries": skipped_entries,
                "files": copied_files,
            }
            self.snapshots.append_pull_bundle(history_record)
            return {
                "status": "ok" if copied_files else "partial",
                **history_record,
                "files": copied_files,
                "repo_metadata": repo_metadata,
                "skipped_entries": skipped_entries,
            }

    def get_node_viewer(self, service_id: str) -> dict[str, Any]:
        return {"service_id": service_id, "locations": self.snapshots.get_service_node_viewer(service_id)}

    def _project_environment_view(
        self,
        environment: ProjectEnvironmentManifest,
        services: dict[str, ServiceManifest],
        bundles: list[dict[str, Any]],
    ) -> dict[str, Any]:
        added_count = 0
        removed_count = 0
        changed_count = 0
        unchanged_count = 0
        latest_created_at = ""
        service_summaries: list[dict[str, Any]] = []
        dependencies: list[dict[str, Any]] = []
        cross_dependencies: list[dict[str, Any]] = []
        snapshot = self.snapshots.get_environment_runtime_snapshot(environment.environment_id)
        snapshot_locations = {
            str(location.get("location_id", "")): location
            for location in (snapshot or {}).get("locations", [])
            if isinstance(location, dict)
        }

        for deployment in environment.deployments:
            service = services.get(deployment.service_id)
            latest_task = self._latest_service_task_context(deployment.service_id)
            runtime_services = (
                [item.model_dump(mode="json") for item in deployment.runtime_services]
                if deployment.runtime_services
                else latest_task.get("runtime_services", [])
            )
            deployment_dependencies = (
                [item.model_dump(mode="json") for item in deployment.dependencies]
                if deployment.dependencies
                else latest_task.get("dependencies", [])
            )
            deployment_cross_dependencies = (
                [item.model_dump(mode="json") for item in deployment.cross_dependencies]
                if deployment.cross_dependencies
                else latest_task.get("cross_dependencies", [])
            )
            dependencies = self._merge_dependency_entries(dependencies, deployment_dependencies)
            cross_dependencies = self._merge_dependency_entries(cross_dependencies, deployment_cross_dependencies)

            matched_bundle = self._latest_bundle_for_deployment(bundles, deployment)
            summary = matched_bundle.get("diff_summary", {}) if matched_bundle else {}
            added_count += int(summary.get("added_count", 0) or 0)
            removed_count += int(summary.get("removed_count", 0) or 0)
            changed_count += int(summary.get("changed_count", 0) or 0)
            unchanged_count += int(summary.get("unchanged_count", 0) or 0)
            created_at = str(matched_bundle.get("created_at", "") if matched_bundle else "")
            if created_at and created_at > latest_created_at:
                latest_created_at = created_at
            runtime_state = self.snapshots.get_service_runtime_state(deployment.service_id)
            runtime_checks = [
                entry for entry in runtime_state.get("runtime_checks", [])
                if not deployment.location_id or entry.get("location_id") == deployment.location_id
            ]
            node_viewer = [
                entry for entry in self.snapshots.get_service_node_viewer(deployment.service_id)
                if not deployment.location_id or entry.get("location_id") == deployment.location_id
            ]
            latest_runtime_check = runtime_checks[0] if runtime_checks else {}
            latest_node_viewer = node_viewer[0] if node_viewer else {}
            node_health = {
                "status": latest_node_viewer.get("runtime_status", "missing"),
                "runtime_ready": bool(latest_node_viewer.get("runtime_ready")),
                "bootstrap_ready": bool(latest_node_viewer.get("bootstrap_ready")),
                "runtime_port": latest_node_viewer.get("runtime_port"),
                "checked_at": latest_node_viewer.get("manifest_updated_at", ""),
            }
            service_health = {
                "status": latest_runtime_check.get("status", "unverified"),
                "healthcheck_status": latest_runtime_check.get("healthcheck_status", "skipped"),
                "checked_at": latest_runtime_check.get("checked_at", ""),
                "healthcheck_command": latest_runtime_check.get("healthcheck_command", ""),
                "healthcheck_output": latest_runtime_check.get("healthcheck_output", ""),
            }

            service_summaries.append(
                {
                    "service_id": deployment.service_id,
                    "display_name": service.display_name if service else deployment.service_id,
                    "execution_mode": getattr(service, "execution_mode", "networked") if service else "networked",
                    "location_id": deployment.location_id,
                    "server_id": deployment.server_id
                    or self._deployment_server_id(service, deployment.location_id),
                    "root": deployment.root or self._deployment_root(service, deployment.location_id),
                    "version": deployment.version or latest_task.get("bootstrap_version", ""),
                    "runtime_services": runtime_services,
                    "dependencies": deployment_dependencies,
                    "cross_dependencies": deployment_cross_dependencies,
                    "runtime_snapshot": snapshot_locations.get(str(deployment.location_id or "")),
                    "runtime_checks": runtime_checks,
                    "node_viewer": node_viewer,
                    "node_health": node_health,
                    "service_health": service_health,
                    "pull_summary": {
                        "added_count": int(summary.get("added_count", 0) or 0),
                        "removed_count": int(summary.get("removed_count", 0) or 0),
                        "changed_count": int(summary.get("changed_count", 0) or 0),
                        "unchanged_count": int(summary.get("unchanged_count", 0) or 0),
                        "summary": summary.get("summary", "No pull bundles yet."),
                        "latest_created_at": created_at,
                    },
                    "notes": deployment.notes,
                }
            )

        pull_summary = {
            "project_id": environment.project_id,
            "environment_id": environment.environment_id,
            "added_count": added_count,
            "removed_count": removed_count,
            "changed_count": changed_count,
            "unchanged_count": unchanged_count,
            "latest_created_at": latest_created_at,
            "service_count": len(environment.deployments),
            "summary": f"{added_count} added, {removed_count} removed, {changed_count} changed",
        }
        snapshot = self.snapshots.get_environment_runtime_snapshot(environment.environment_id)
        latest_flow_run_at = ""
        for flow in self.manifests.get_environment_api_flows(environment.environment_id):
            runs = self.snapshots.get_api_flow_runs(environment.environment_id, flow.flow_id)
            if runs and str(runs[0].get("finished_at", "")) > latest_flow_run_at:
                latest_flow_run_at = str(runs[0].get("finished_at", ""))
        return {
            **environment.model_dump(mode="json"),
            "pull_summary": pull_summary,
            "dependency_summary": {
                "dependencies": dependencies,
                "cross_dependencies": cross_dependencies,
            },
            "service_summaries": service_summaries,
            "runtime_snapshot": snapshot,
            "runtime_snapshot_summary": {
                "captured_at": snapshot.get("captured_at", "") if snapshot else "",
                "open_port_count": len(snapshot.get("open_ports", [])) if snapshot else 0,
                "exposed_port_count": len(snapshot.get("exposed_ports", [])) if snapshot else 0,
                "firewall_status": snapshot.get("firewall_status", "unverified") if snapshot else "unverified",
            },
            "api_flow_count": len(self.manifests.get_environment_api_flows(environment.environment_id)),
            "latest_flow_run_at": latest_flow_run_at,
        }

    def _latest_service_task_context(self, service_id: str) -> dict[str, Any]:
        ledger = self.snapshots.get_service_task_ledger(service_id)
        tasks = ledger.get("tasks", [])
        return tasks[0] if tasks else {}

    def _merge_dependency_entries(
        self,
        current: list[dict[str, Any]],
        additions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        seen = {
            f"{entry.get('kind','')}|{entry.get('name','')}|{entry.get('host','')}|{entry.get('port','')}"
            for entry in current
        }
        merged = list(current)
        for entry in additions:
            key = f"{entry.get('kind','')}|{entry.get('name','')}|{entry.get('host','')}|{entry.get('port','')}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(entry)
        return merged

    def _latest_bundle_for_deployment(
        self,
        bundles: list[dict[str, Any]],
        deployment: Any,
    ) -> dict[str, Any] | None:
        matched = [bundle for bundle in bundles if bundle.get("service_id") == deployment.service_id]
        if deployment.server_id:
            matched = [bundle for bundle in matched if bundle.get("server_id") == deployment.server_id] or matched
        if deployment.root:
            matched = [bundle for bundle in matched if bundle.get("location_root") == deployment.root] or matched
        return matched[0] if matched else None

    def _deployment_server_id(self, service: ServiceManifest | None, location_id: str | None) -> str:
        if service is None or location_id is None:
            return ""
        location = self._select_location(service, location_id=location_id)
        return location.server_id if location is not None else ""

    def _deployment_root(self, service: ServiceManifest | None, location_id: str | None) -> str:
        if service is None or location_id is None:
            return ""
        location = self._select_location(service, location_id=location_id)
        return location.root if location is not None else ""

    def node_inspect(self, service_id: str, request: NodeActionRequest) -> dict[str, Any]:
        service = self.manifests.get_service(service_id)
        location = self._select_location(service, location_id=request.location_id)
        if location is None:
            return {"status": "path_missing", "message": "No service location available."}
        server = self.manifests.resolve_server(
            location.server_id,
            {location.server_id: request.runtime_password} if request.runtime_password else {},
        )
        record = self._node_inspect_record(service, location, server)
        self.snapshots.persist_node_viewer(service_id, location.location_id, record)
        return {"status": "ok", "node": record}

    def node_release_check(self, service_id: str, request: NodeActionRequest) -> dict[str, Any]:
        service = self.manifests.get_service(service_id)
        location = self._select_location(service, location_id=request.location_id)
        if location is None:
            return {"status": "path_missing", "message": "No service location available."}
        server = self.manifests.resolve_server(
            location.server_id,
            {location.server_id: request.runtime_password} if request.runtime_password else {},
        )
        node = self._node_inspect_record(service, location, server)
        release = self._fetch_latest_node_release()
        status = release.get("status", "unverified")
        latest_version = str(release.get("version", ""))
        current_version = str(node.get("installed_version", ""))
        return {
            "status": status,
            "current_version": current_version,
            "latest_version": latest_version,
            "update_available": bool(node.get("node_present") and latest_version and latest_version != current_version),
            "published_at": release.get("published_at", ""),
            "release_url": release.get("html_url", ""),
            "asset_url": release.get("asset_url", ""),
            "notes": release.get("notes", ""),
            "message": release.get("message", ""),
        }

    def node_deploy(self, service_id: str, request: NodeActionRequest) -> dict[str, Any]:
        with self._action_guard("node_deploy", service_id) as lock_error:
            if lock_error is not None:
                return lock_error
            service = self.manifests.get_service(service_id)
            location = self._select_location(service, location_id=request.location_id)
            if location is None:
                return {"status": "path_missing", "message": "No service location available."}
            server = self.manifests.resolve_server(
                location.server_id,
                {location.server_id: request.runtime_password} if request.runtime_password else {},
            )
            before = self._node_inspect_record(service, location, server)
            release = self._fetch_latest_node_release()
            if release.get("status") != "ok" or not release.get("asset_url"):
                return {
                    "status": "partial",
                    "message": release.get("message") or "GitHub release wheel was not available.",
                    "before": before,
                    "node": before,
                    "after": before,
                    "release": self._release_check_payload(before, release),
                }
            if server.connection_type == "local":
                result = self._install_local_node_release(
                    location.root,
                    service.service_id,
                    service.display_name,
                    str(release["asset_url"]),
                )
            else:
                result = self._install_remote_node_release(
                    server,
                    location.root,
                    service.service_id,
                    service.display_name,
                    str(release["asset_url"]),
                )
            if result["status"] != "ok":
                return {
                    **result,
                    "before": before,
                    "node": before,
                    "after": before,
                    "release": self._release_check_payload(before, release),
                }

            after = self._node_inspect_record(service, location, server)
            self.snapshots.persist_node_viewer(service_id, location.location_id, after)
            status = "ok" if after["installed_version"] == str(release.get("version", "")) or not after["node_present"] else "partial"
            message = (
                "Node deployed from the latest GitHub release."
                if not before["node_present"]
                else "Node reinstalled from the latest GitHub release."
            )
            return {
                "status": status,
                "message": message,
                "before": before,
                "node": after,
                "after": after,
                "release": self._release_check_payload(after, release),
            }

    def node_upgrade(self, service_id: str, request: NodeActionRequest) -> dict[str, Any]:
        with self._action_guard("node_upgrade", service_id) as lock_error:
            if lock_error is not None:
                return lock_error
            service = self.manifests.get_service(service_id)
            location = self._select_location(service, location_id=request.location_id)
            if location is None:
                return {"status": "path_missing", "message": "No service location available."}
            server = self.manifests.resolve_server(
                location.server_id,
                {location.server_id: request.runtime_password} if request.runtime_password else {},
            )
            before = self._node_inspect_record(service, location, server)
            if not before["node_present"]:
                return {"status": "path_missing", "message": "Node manifest not found at selected location."}
            release = self._fetch_latest_node_release()
            if release.get("status") != "ok" or not release.get("asset_url"):
                return {
                    "status": "partial",
                    "message": release.get("message") or "GitHub release wheel was not available.",
                    "before": before,
                    "node": before,
                    "after": before,
                    "release": self._release_check_payload(before, release),
                }
            if server.connection_type == "local":
                result = self._install_local_node_release(
                    location.root,
                    service.service_id,
                    service.display_name,
                    str(release["asset_url"]),
                )
            else:
                result = self._install_remote_node_release(
                    server,
                    location.root,
                    service.service_id,
                    service.display_name,
                    str(release["asset_url"]),
                )
            if result["status"] != "ok":
                return {
                    **result,
                    "before": before,
                    "node": before,
                    "after": before,
                    "release": self._release_check_payload(before, release),
                }
            runtime_port = int(before.get("runtime_port") or 8010)
            if server.connection_type == "local":
                stop_node_runtime(location.root, port=runtime_port)
                start_node_runtime(location.root, host="127.0.0.1", port=runtime_port)
            else:
                restart_result = self._restart_remote_node(server, location.root, runtime_port)
                if restart_result["status"] != "ok":
                    return {
                        **restart_result,
                        "before": before,
                        "node": before,
                        "after": before,
                        "release": self._release_check_payload(before, release),
                    }

            after = self._node_inspect_record(service, location, server)
            self.snapshots.persist_node_viewer(service_id, location.location_id, after)
            return {
                "status": "ok",
                "message": "Node updated from GitHub and runtime restarted.",
                "before": before,
                "node": after,
                "after": after,
                "release": self._release_check_payload(after, release),
            }

    def node_restart(self, service_id: str, request: NodeActionRequest) -> dict[str, Any]:
        with self._action_guard("node_restart", service_id) as lock_error:
            if lock_error is not None:
                return lock_error
            service = self.manifests.get_service(service_id)
            location = self._select_location(service, location_id=request.location_id)
            if location is None:
                return {"status": "path_missing", "message": "No service location available."}
            server = self.manifests.resolve_server(
                location.server_id,
                {location.server_id: request.runtime_password} if request.runtime_password else {},
            )
            before = self._node_inspect_record(service, location, server)
            runtime_port = int(before.get("runtime_port") or 8010)
            if server.connection_type == "local":
                stop_node_runtime(location.root, port=runtime_port)
                start_node_runtime(location.root, host="127.0.0.1", port=runtime_port)
            else:
                result = self._restart_remote_node(server, location.root, runtime_port)
                if result["status"] != "ok":
                    return result

            after = self._node_inspect_record(service, location, server)
            self.snapshots.persist_node_viewer(service_id, location.location_id, after)
            return {"status": "ok", "message": "Node runtime restarted.", "before": before, "node": after, "after": after}

    def _collect_server_summary(self, server_id: str, server: ResolvedServer) -> dict[str, Any]:
        if server.connection_type == "local":
            return self._collect_local_server_summary(server_id, server)
        return self._collect_ssh_server_summary(server_id, server)

    def _select_location(
        self,
        service: ServiceManifest,
        server_id: str | None = None,
        location_id: str | None = None,
    ) -> Any | None:
        if location_id is not None:
            return next((location for location in service.locations if location.location_id == location_id), None)
        if server_id is not None:
            return next((location for location in service.locations if location.server_id == server_id), None)
        primary = next((location for location in service.locations if location.is_primary), None)
        if primary is not None:
            return primary
        return service.locations[0] if service.locations else None

    def _resolve_server_id_for_repo(self, service: ServiceManifest, repo_path: str, explicit_server_id: str | None) -> str | None:
        if explicit_server_id is not None:
            return explicit_server_id
        for location in service.locations:
            if repo_path.startswith(location.root):
                return location.server_id
        return None

    def _flatten_scope_entries(self, scope_entries: list[dict[str, Any]]) -> dict[str, list[str]]:
        repo_paths = [entry["path"] for entry in scope_entries if entry.get("enabled", True) and entry.get("kind") == "repo"]
        docs_paths = [entry["path"] for entry in scope_entries if entry.get("enabled", True) and entry.get("kind") == "doc"]
        log_paths = [entry["path"] for entry in scope_entries if entry.get("enabled", True) and entry.get("kind") == "log"]
        exclude_globs = [entry["path"] for entry in scope_entries if entry.get("enabled", True) and entry.get("kind") == "exclude"]
        return {
            "repo_paths": repo_paths,
            "docs_paths": docs_paths,
            "log_paths": log_paths,
            "exclude_globs": exclude_globs,
        }

    def _repo_policies_for_paths(self, repo_paths: list[str]) -> list[dict[str, Any]]:
        policies: list[dict[str, Any]] = []
        seen: set[str] = set()
        for repo_path in repo_paths:
            if repo_path in seen:
                continue
            seen.add(repo_path)
            token = repo_path.lower()
            secret_heavy = "lambda" in token or "secret" in token or "credential" in token
            policies.append(
                {
                    "repo_path": repo_path,
                    "push_mode": "blocked" if secret_heavy else "allowed",
                    "safety_profile": "secret_heavy" if secret_heavy else "generic_python",
                    "allowed_branches": [],
                    "allowed_remotes": [],
                }
            )
        return policies

    def _scope_entries_for_location(self, service: ServiceManifest, root: str) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for entry in service.scope_entries:
            if not entry.enabled:
                continue
            if entry.path.startswith(root):
                entries.append(entry.model_dump(mode="json"))
        return entries

    def _local_node_manifest_path(self, root: str) -> Path:
        return Path(root) / "switchboard" / "node.manifest.json"

    def _local_scope_snapshot_path(self, root: str) -> Path:
        return Path(root) / "switchboard" / "evidence" / "scope.snapshot.json"

    def _local_pull_bundle_history_path(self, root: str) -> Path:
        return Path(root) / "switchboard" / "evidence" / "pull-bundle-history.json"

    def _local_doc_index_path(self, root: str) -> Path:
        return Path(root) / "switchboard" / "evidence" / "doc-index.json"

    def _local_completed_tasks_path(self, root: str) -> Path:
        return Path(root) / "switchboard" / "evidence" / "completed-tasks.json"

    def _remote_node_manifest_path(self, root: str) -> str:
        return posixpath.join(root.rstrip("/"), "switchboard", "node.manifest.json")

    def _remote_scope_snapshot_path(self, root: str) -> str:
        return posixpath.join(root.rstrip("/"), "switchboard", "evidence", "scope.snapshot.json")

    def _remote_pull_bundle_history_path(self, root: str) -> str:
        return posixpath.join(root.rstrip("/"), "switchboard", "evidence", "pull-bundle-history.json")

    def _remote_doc_index_path(self, root: str) -> str:
        return posixpath.join(root.rstrip("/"), "switchboard", "evidence", "doc-index.json")

    def _remote_completed_tasks_path(self, root: str) -> str:
        return posixpath.join(root.rstrip("/"), "switchboard", "evidence", "completed-tasks.json")

    def _collect_service(
        self,
        service: ServiceManifest,
        resolved_servers: dict[str, ResolvedServer],
    ) -> dict[str, Any]:
        repo_entries: list[dict[str, Any]] = []
        doc_entries: list[dict[str, Any]] = []
        log_entries: list[dict[str, Any]] = []
        secret_entries: list[dict[str, Any]] = []
        location_statuses: list[str] = []
        excludes = list(dict.fromkeys(DEFAULT_EXCLUDE_GLOBS + service.exclude_globs))
        secret_patterns = list(dict.fromkeys(DEFAULT_SECRET_PATTERNS + [".env", ".env.*"]))

        for location in service.locations:
            server = resolved_servers[location.server_id]
            if server.connection_type == "local":
                location_result = self._collect_local_location(service, location, excludes, secret_patterns)
            else:
                location_result = self._collect_remote_location(service, server, location.root, excludes, secret_patterns)
            location_statuses.append(location_result["status"])
            repo_entries.extend(location_result["repos"])
            doc_entries.extend(location_result["docs"])
            log_entries.extend(location_result["logs"])
            secret_entries.extend(location_result["secrets"])

        if location_statuses and all(status == "ok" for status in location_statuses):
            status = "ok"
        elif any(status == "ok" for status in location_statuses):
            status = "partial"
        else:
            status = location_statuses[0] if location_statuses else "unverified"

        return {
            "service": {
                "service_id": service.service_id,
                "workspace_id": service.workspace_id,
                "display_name": service.display_name,
                "status": status,
                "location_count": len(service.locations),
                "doc_count": len(doc_entries),
                "log_count": len(log_entries),
                "secret_path_count": len(secret_entries),
                "path_aliases": service.path_aliases,
                "notes": service.notes,
            },
            "repos": repo_entries,
            "docs": doc_entries,
            "logs": log_entries,
            "secrets": secret_entries,
        }

    def _collect_local_server_summary(self, server_id: str, server: ResolvedServer) -> dict[str, Any]:
        ports = self._run_local(["sh", "-lc", SAFE_REMOTE_COMMANDS["ports"]])
        firewall = self._run_local(["sh", "-lc", SAFE_REMOTE_COMMANDS["firewall"]])
        services = self._run_local(["sh", "-lc", SAFE_REMOTE_COMMANDS["services"]])
        docker = self._run_local(["sh", "-lc", SAFE_REMOTE_COMMANDS["docker"]])
        hostname = socket.gethostname()
        return {
            "server_id": server_id,
            "name": server.name,
            "status": "ok",
            "connection_type": server.connection_type,
            "host": server.host,
            "username": server.username,
            "hostname": hostname,
            "ports": self._split_lines(ports["stdout"]),
            "firewall": firewall["stdout"].strip() or firewall["stderr"].strip() or "unverified",
            "services": self._split_lines(services["stdout"]),
            "docker": self._split_lines(docker["stdout"]),
        }

    def _collect_ssh_server_summary(self, server_id: str, server: ResolvedServer) -> dict[str, Any]:
        with self._open_ssh(server) as connection:
            if connection is None:
                return {
                    "server_id": server_id,
                    "name": server.name,
                    "status": "unreachable",
                    "connection_type": server.connection_type,
                    "host": server.host,
                    "username": server.username,
                    "hostname": server.host,
                    "ports": [],
                    "firewall": "unverified",
                    "services": [],
                    "docker": [],
                }

            ssh, _ = connection
            hostname = self._run_remote(ssh, SAFE_REMOTE_COMMANDS["hostname"])
            ports = self._run_remote(ssh, SAFE_REMOTE_COMMANDS["ports"])
            firewall = self._run_remote(ssh, SAFE_REMOTE_COMMANDS["firewall"])
            services = self._run_remote(ssh, SAFE_REMOTE_COMMANDS["services"])
            docker = self._run_remote(ssh, SAFE_REMOTE_COMMANDS["docker"])
            return {
                "server_id": server_id,
                "name": server.name,
                "status": "ok",
                "connection_type": server.connection_type,
                "host": server.host,
                "username": server.username,
                "hostname": hostname["stdout"].strip() or server.host,
                "ports": self._split_lines(ports["stdout"]),
                "firewall": firewall["stdout"].strip() or firewall["stderr"].strip() or "unverified",
                "services": self._split_lines(services["stdout"]),
                "docker": self._split_lines(docker["stdout"]),
            }

    def _collect_local_location(
        self,
        service: ServiceManifest,
        location: Any,
        excludes: list[str],
        secret_patterns: list[str],
    ) -> dict[str, Any]:
        root = location.root
        root_path = Path(root)
        if not root_path.exists():
            return {"status": "path_missing", "repos": [], "docs": [], "logs": [], "secrets": []}
        server = self.manifests.resolve_server(location.server_id)
        repos = [self._repo_status(server, path) for path in service.repo_paths if path.startswith(root)]
        docs = self._inventory_paths_local(service, location.server_id, service.docs_paths, "doc", excludes)
        logs = self._inventory_paths_local(service, location.server_id, service.log_paths, "log", excludes)
        secrets = self._scan_secret_paths_local(service, location.server_id, root_path, excludes, secret_patterns)
        return {"status": "ok", "repos": repos, "docs": docs, "logs": logs, "secrets": secrets}

    def _collect_remote_location(
        self,
        service: ServiceManifest,
        server: ResolvedServer,
        root: str,
        excludes: list[str],
        secret_patterns: list[str],
    ) -> dict[str, Any]:
        with self._open_ssh(server) as connection:
            if connection is None:
                return {"status": "unreachable", "repos": [], "docs": [], "logs": [], "secrets": []}
            ssh, sftp = connection
            if not self._remote_exists(sftp, root):
                return {"status": "path_missing", "repos": [], "docs": [], "logs": [], "secrets": []}
            repos = [
                self._repo_status(server, path, ssh=ssh)
                for path in service.repo_paths
                if path.startswith(root)
            ]
            docs = self._inventory_paths_remote(service, server, sftp, service.docs_paths, "doc", excludes)
            logs = self._inventory_paths_remote(service, server, sftp, service.log_paths, "log", excludes)
            secrets = self._scan_secret_paths_remote(service, server, sftp, root, excludes, secret_patterns)
            return {"status": "ok", "repos": repos, "docs": docs, "logs": logs, "secrets": secrets}

    def _scan_local_root(self, root: Path, excludes: list[str], max_depth: int) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        stack: list[tuple[Path, int]] = [(root, 0)]
        seen = 0
        while stack and seen < self.settings.max_files_per_path:
            current, depth = stack.pop()
            try:
                children = sorted(current.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))
            except OSError:
                continue
            for child in children:
                if self._matches_exclude(child.name, str(child), excludes):
                    continue
                entry_type = "dir" if child.is_dir() else "file"
                entries.append(
                    {
                        "path": str(child),
                        "name": child.name,
                        "entry_type": entry_type,
                        "depth": depth + 1,
                        "suggested_kind": self._suggest_scope_kind(child.name, str(child), entry_type),
                    }
                )
                seen += 1
                if child.is_dir() and depth + 1 < max_depth:
                    stack.append((child, depth + 1))
                if seen >= self.settings.max_files_per_path:
                    break
        return entries

    def _browse_local_tree(self, target: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        current = self._local_tree_node(target, children_loaded=True)
        if not target.is_dir():
            return current, []
        entries: list[dict[str, Any]] = []
        try:
            children = sorted(target.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))
        except OSError:
            return current, entries
        for child in children[: self.settings.max_files_per_path]:
            entries.append(self._local_tree_node(child))
        return current, entries

    def _scan_remote_root(self, sftp: Any, root: str, excludes: list[str], max_depth: int) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        stack: list[tuple[str, int]] = [(root, 0)]
        seen = 0
        while stack and seen < self.settings.max_files_per_path:
            current, depth = stack.pop()
            try:
                children = sorted(sftp.listdir_attr(current), key=lambda item: (not stat.S_ISDIR(item.st_mode), item.filename.lower()))
            except OSError:
                continue
            for child in children:
                path = posixpath.join(current, child.filename)
                if self._matches_exclude(child.filename, path, excludes):
                    continue
                entry_type = "dir" if stat.S_ISDIR(child.st_mode) else "file"
                entries.append(
                    {
                        "path": path,
                        "name": child.filename,
                        "entry_type": entry_type,
                        "depth": depth + 1,
                        "suggested_kind": self._suggest_scope_kind(child.filename, path, entry_type),
                    }
                )
                seen += 1
                if entry_type == "dir" and depth + 1 < max_depth:
                    stack.append((path, depth + 1))
                if seen >= self.settings.max_files_per_path:
                    break
        return entries

    def _browse_remote_tree(self, sftp: Any, target: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        current = self._remote_tree_node(sftp, target, children_loaded=True)
        if current["node_type"] != "dir":
            return current, []
        entries: list[dict[str, Any]] = []
        try:
            children = sorted(
                sftp.listdir_attr(target),
                key=lambda item: (not stat.S_ISDIR(item.st_mode), item.filename.lower()),
            )
        except OSError:
            return current, entries
        for child in children[: self.settings.max_files_per_path]:
            child_path = posixpath.join(target, child.filename)
            entries.append(self._remote_tree_node(sftp, child_path, attrs=child))
        return current, entries

    def _local_tree_node(self, path: Path, children_loaded: bool = False) -> dict[str, Any]:
        is_dir = path.is_dir()
        has_children = False
        if is_dir:
            try:
                next(path.iterdir())
                has_children = True
            except (OSError, StopIteration):
                has_children = False
        entry_type = "dir" if is_dir else "file"
        return {
            "path": str(path),
            "name": path.name or str(path),
            "node_type": entry_type,
            "entry_type": entry_type,
            "has_children": has_children,
            "children_loaded": children_loaded,
            "suggested_kind": self._suggest_scope_kind(path.name or str(path), str(path), entry_type),
            "default_selected": True,
        }

    def _remote_tree_node(
        self,
        sftp: Any,
        path: str,
        attrs: Any | None = None,
        children_loaded: bool = False,
    ) -> dict[str, Any]:
        attrs = attrs or sftp.stat(path)
        is_dir = stat.S_ISDIR(attrs.st_mode)
        has_children = False
        if is_dir:
            try:
                has_children = len(sftp.listdir(path)) > 0
            except OSError:
                has_children = False
        entry_type = "dir" if is_dir else "file"
        return {
            "path": path,
            "name": posixpath.basename(path) or path,
            "node_type": entry_type,
            "entry_type": entry_type,
            "has_children": has_children,
            "children_loaded": children_loaded,
            "suggested_kind": self._suggest_scope_kind(posixpath.basename(path) or path, path, entry_type),
            "default_selected": True,
        }

    def _inventory_paths_local(
        self,
        service: ServiceManifest,
        server_id: str,
        paths: list[str],
        kind: str,
        excludes: list[str],
    ) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for raw_path in paths:
            path = Path(raw_path)
            if not path.exists():
                continue
            if path.is_file():
                entries.append(self._file_record(service, server_id, path, kind))
                continue
            for file_path in self._walk_local_files(path, excludes):
                entries.append(self._file_record(service, server_id, file_path, kind))
        return entries

    def _inventory_paths_remote(
        self,
        service: ServiceManifest,
        server: ResolvedServer,
        sftp: Any,
        paths: list[str],
        kind: str,
        excludes: list[str],
    ) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for raw_path in paths:
            if not self._remote_exists(sftp, raw_path):
                continue
            attrs = sftp.stat(raw_path)
            if stat.S_ISDIR(attrs.st_mode):
                for item in self._walk_remote_files(sftp, raw_path, excludes):
                    entries.append(self._remote_file_record(service, server.server_id, item, kind))
                continue
            entries.append(self._remote_file_record(service, server.server_id, (raw_path, attrs), kind))
        return entries

    def _scan_secret_paths_local(
        self,
        service: ServiceManifest,
        server_id: str,
        root: Path,
        excludes: list[str],
        secret_patterns: list[str],
    ) -> list[dict[str, Any]]:
        entries = []
        for file_path in self._walk_local_files(root, excludes):
            if self._matches_secret_pattern(file_path.name, str(file_path), secret_patterns):
                stats = file_path.stat()
                entries.append(
                    {
                        "service_id": service.service_id,
                        "server_id": server_id,
                        "path": str(file_path),
                        "category": "secret_path",
                        "size": stats.st_size,
                        "mtime": self._format_mtime(stats.st_mtime),
                        "matched_pattern": self._matched_pattern(file_path.name, str(file_path), secret_patterns),
                    }
                )
        return entries

    def _scan_secret_paths_remote(
        self,
        service: ServiceManifest,
        server: ResolvedServer,
        sftp: Any,
        root: str,
        excludes: list[str],
        secret_patterns: list[str],
    ) -> list[dict[str, Any]]:
        entries = []
        for path, attrs in self._walk_remote_files(sftp, root, excludes):
            if self._matches_secret_pattern(posixpath.basename(path), path, secret_patterns):
                entries.append(
                    {
                        "service_id": service.service_id,
                        "server_id": server.server_id,
                        "path": path,
                        "category": "secret_path",
                        "size": attrs.st_size,
                        "mtime": self._format_mtime(attrs.st_mtime),
                        "matched_pattern": self._matched_pattern(posixpath.basename(path), path, secret_patterns),
                    }
                )
        return entries

    def _run_repo_safety_scan(
        self,
        service_id: str,
        server: ResolvedServer,
        repo_path: str,
        repo_state: dict[str, Any],
        policy: Any | None,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        findings: list[dict[str, Any]] = []
        blocking_reasons: list[str] = []
        if policy is None:
            blocking_reasons.append("Repo policy is missing.")
        elif policy.push_mode != "allowed":
            blocking_reasons.append("Repo policy blocks push for this path.")

        if repo_state.get("status") != "ok":
            blocking_reasons.append(f"Repo state is {repo_state.get('status', 'unknown')}.")
            return findings, blocking_reasons
        if repo_state.get("dirty"):
            blocking_reasons.append("Repo has uncommitted changes.")

        if server.connection_type == "local":
            findings.extend(self._scan_repo_files_local(repo_path))
        else:
            with self._open_ssh(server) as connection:
                if connection is None:
                    blocking_reasons.append("SSH connection failed.")
                    return findings, blocking_reasons
                ssh, sftp = connection
                findings.extend(self._scan_repo_files_remote(ssh, sftp, repo_path))

        if findings:
            blocking_reasons.append(f"Secret or credential findings detected: {len(findings)}.")
        return findings, blocking_reasons

    def _repo_status(
        self,
        server: ResolvedServer,
        repo_path: str,
        ssh: Any | None = None,
    ) -> dict[str, Any]:
        if server.connection_type == "local":
            top_level = self._run_local(["git", "-C", repo_path, "rev-parse", "--show-toplevel"])
            if top_level["returncode"] != 0:
                return {"status": "not_git_repo", "repo_path": repo_path, "dirty": False}
            branch = self._run_local(["git", "-C", repo_path, "branch", "--show-current"])
            dirty = self._run_local(["git", "-C", repo_path, "status", "--short"])
            commit = self._run_local(["git", "-C", repo_path, "log", "-1", "--format=%H%x09%cI%x09%s"])
            remotes = self._run_local(["git", "-C", repo_path, "remote", "-v"])
            return {
                "status": "ok",
                "server_id": server.server_id,
                "repo_path": repo_path,
                "branch": branch["stdout"].strip(),
                "dirty": bool(dirty["stdout"].strip()),
                "last_commit": commit["stdout"].strip(),
                "remotes": self._split_lines(remotes["stdout"]),
            }

        if ssh is None:
            with self._open_ssh(server) as connection:
                if connection is None:
                    return {"status": "unreachable", "repo_path": repo_path, "dirty": False}
                ssh, _ = connection
                return self._repo_status(server, repo_path, ssh=ssh)

        top_level = self._run_remote(ssh, GIT_STATUS_COMMANDS["rev_parse"].format(path=self._quote(repo_path)))
        if top_level["returncode"] != 0:
            return {"status": "not_git_repo", "repo_path": repo_path, "dirty": False}
        branch = self._run_remote(ssh, GIT_STATUS_COMMANDS["branch"].format(path=self._quote(repo_path)))
        dirty = self._run_remote(ssh, GIT_STATUS_COMMANDS["status"].format(path=self._quote(repo_path)))
        commit = self._run_remote(ssh, GIT_STATUS_COMMANDS["last_commit"].format(path=self._quote(repo_path)))
        remotes = self._run_remote(ssh, GIT_STATUS_COMMANDS["remotes"].format(path=self._quote(repo_path)))
        return {
            "status": "ok",
            "server_id": server.server_id,
            "repo_path": repo_path,
            "branch": branch["stdout"].strip(),
            "dirty": bool(dirty["stdout"].strip()),
            "last_commit": commit["stdout"].strip(),
            "remotes": self._split_lines(remotes["stdout"]),
        }

    def _scan_repo_files_local(self, repo_path: str) -> list[dict[str, Any]]:
        files = self._split_lines(self._run_local(["git", "-C", repo_path, "ls-files", "-co", "--exclude-standard"])["stdout"])
        findings: list[dict[str, Any]] = []
        for relative in files[: self.settings.max_files_per_path]:
            full_path = Path(repo_path) / relative
            try:
                findings.extend(self._scan_file_for_secrets(str(full_path), full_path.read_bytes() if full_path.is_file() else b""))
            except OSError:
                continue
        return findings

    def _scan_repo_files_remote(self, ssh: Any, sftp: Any, repo_path: str) -> list[dict[str, Any]]:
        files_result = self._run_remote(ssh, f"git -C {self._quote(repo_path)} ls-files -co --exclude-standard")
        files = self._split_lines(files_result["stdout"])
        findings: list[dict[str, Any]] = []
        for relative in files[: self.settings.max_files_per_path]:
            remote_path = posixpath.join(repo_path, relative)
            try:
                with sftp.open(remote_path, "rb") as handle:
                    findings.extend(self._scan_file_for_secrets(remote_path, handle.read()))
            except OSError:
                continue
        return findings

    def _scan_file_for_secrets(self, file_path: str, content: bytes) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        name = os.path.basename(file_path)
        if self._matches_secret_pattern(name, file_path, DEFAULT_SECRET_PATTERNS):
            findings.append({"path": file_path, "type": "secret_filename", "reason": f"Matched protected filename pattern: {name}"})
        if not content or len(content) > 1_000_000:
            return findings
        if b"\x00" in content:
            return findings
        try:
            text = content.decode("utf-8", errors="ignore")
        except Exception:
            return findings
        for finding_type, pattern in SECRET_CONTENT_PATTERNS:
            if pattern.search(text):
                findings.append({"path": file_path, "type": finding_type, "reason": f"Matched {finding_type} pattern"})
        return findings

    def _copy_bundle_local(
        self,
        service: ServiceManifest,
        location_root: str,
        scope_entries: list[Any],
        exclude_patterns: list[str],
        mirrored_root: Path,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        copied: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for entry in scope_entries:
            if entry.kind == "exclude":
                continue
            if not entry.path.startswith(location_root):
                skipped.append(
                    {
                        "path": entry.path,
                        "kind": entry.kind,
                        "path_type": entry.path_type,
                        "reason": "outside_location_root",
                    }
                )
                continue
            matched = list(self._expand_local_entry(entry.path, exclude_patterns))
            if not matched:
                skipped.append(
                    {
                        "path": entry.path,
                        "kind": entry.kind,
                        "path_type": entry.path_type,
                        "reason": "no_files_matched",
                    }
                )
                continue
            for source in matched:
                relative = self._bundle_relative_path(source, location_root)
                target = mirrored_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                copied.append(self._copied_file_record(str(source), str(target), entry.kind, relative_path=str(relative)))
        return copied, skipped

    def _copy_bundle_remote(
        self,
        service: ServiceManifest,
        sftp: Any,
        location_root: str,
        scope_entries: list[Any],
        exclude_patterns: list[str],
        mirrored_root: Path,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        copied: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for entry in scope_entries:
            if entry.kind == "exclude":
                continue
            if not entry.path.startswith(location_root):
                skipped.append(
                    {
                        "path": entry.path,
                        "kind": entry.kind,
                        "path_type": entry.path_type,
                        "reason": "outside_location_root",
                    }
                )
                continue
            matched = list(self._expand_remote_entry(sftp, entry.path, exclude_patterns))
            if not matched:
                skipped.append(
                    {
                        "path": entry.path,
                        "kind": entry.kind,
                        "path_type": entry.path_type,
                        "reason": "no_files_matched",
                    }
                )
                continue
            for source_path, attrs in matched:
                relative = self._bundle_relative_path(source_path, location_root)
                target = mirrored_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    sftp.get(source_path, str(target))
                    copied.append(
                        self._copied_file_record(
                            source_path,
                            str(target),
                            entry.kind,
                            attrs.st_size,
                            attrs.st_mtime,
                            relative_path=str(relative),
                        )
                    )
                except OSError:
                    continue
        return copied, skipped

    def _expand_local_entry(self, path: str, exclude_patterns: list[str]) -> list[Path]:
        source = Path(path)
        if not source.exists():
            return []
        if self._is_explicitly_excluded(str(source), exclude_patterns):
            return []
        if source.is_file():
            return [] if self._matches_exclude(source.name, str(source), exclude_patterns) else [source]
        return list(self._walk_local_files(source, exclude_patterns))

    def _expand_remote_entry(self, sftp: Any, path: str, exclude_patterns: list[str]) -> list[tuple[str, Any]]:
        if not self._remote_exists(sftp, path):
            return []
        if self._is_explicitly_excluded(path, exclude_patterns):
            return []
        attrs = sftp.stat(path)
        if stat.S_ISDIR(attrs.st_mode):
            return list(self._walk_remote_files(sftp, path, exclude_patterns))
        if self._matches_exclude(posixpath.basename(path), path, exclude_patterns):
            return []
        return [(path, attrs)]

    def _bundle_relative_path(self, path: Any, root: str) -> Path:
        raw = str(path)
        try:
            if raw.startswith(root):
                rel = raw[len(root):].lstrip("/\\")
                return Path(rel or Path(raw).name)
        except Exception:
            pass
        return Path(Path(raw).name)

    def _download_location_root(self, service: ServiceManifest, server_id: str, files: list[str]) -> str:
        locations = [location for location in service.locations if location.server_id == server_id]
        if not locations:
            return "/"
        if not files:
            return locations[0].root
        best_root = locations[0].root
        best_score = -1
        for location in locations:
            score = sum(1 for file_path in files if str(file_path).startswith(location.root))
            if score > best_score:
                best_root = location.root
                best_score = score
        return best_root

    def _copied_file_record(
        self,
        source_path: str,
        target_path: str,
        kind: str,
        size: int | None = None,
        mtime: float | None = None,
        relative_path: str | None = None,
    ) -> dict[str, Any]:
        target = Path(target_path)
        stats = target.stat()
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        return {
            "kind": kind,
            "source_path": source_path,
            "target_path": target_path,
            "relative_path": relative_path or target.name,
            "size": size if size is not None else stats.st_size,
            "mtime": self._format_mtime(mtime if mtime is not None else stats.st_mtime),
            "sha256": digest,
        }

    def _read_local_json(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _write_local_json(self, path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def _read_remote_json(self, sftp: Any, path: str) -> dict[str, Any] | None:
        try:
            with sftp.open(path, "r") as handle:
                return json.loads(handle.read().decode("utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return None

    def _write_remote_json(self, ssh: Any, sftp: Any, path: str, value: dict[str, Any]) -> None:
        parent = posixpath.dirname(path)
        self._run_remote(ssh, f"mkdir -p {self._quote(parent)}")
        with sftp.open(path, "w") as handle:
            handle.write(json.dumps(value, indent=2) + "\n")

    def _execute_api_flow(self, environment: ProjectEnvironmentManifest, flow: Any) -> dict[str, Any]:
        started_at = utc_now_iso()
        variables: dict[str, str] = {}
        step_results: list[dict[str, Any]] = []
        failures = 0

        ordered_steps = sorted(flow.steps, key=lambda step: (step.order, step.step_id))
        for step in ordered_steps:
            started = time.perf_counter()
            headers = {key: self._template_string(value, variables) for key, value in (step.headers or {}).items()}
            path = self._template_string(step.path or "", variables)
            base_url = self._template_string(flow.base_url or "", variables).rstrip("/")
            query = {
                key: self._template_string(value, variables)
                for key, value in (step.query or {}).items()
                if value is not None
            }
            body = self._template_string(step.body or "", variables)
            query_string = urllib.parse.urlencode(query)
            resolved_url = f"{base_url}{path}"
            if query_string:
                resolved_url = f"{resolved_url}?{query_string}"
            generated_curl = self._curl_for_step(step.method, resolved_url, headers, body)

            request_body: bytes | None = body.encode("utf-8") if body and step.method in {"POST", "PUT", "PATCH", "DELETE"} else None
            request = urllib.request.Request(resolved_url, data=request_body, method=step.method)
            for key, value in headers.items():
                request.add_header(key, value)

            try:
                with urllib.request.urlopen(request, timeout=step.timeout_seconds) as response:
                    duration_ms = int((time.perf_counter() - started) * 1000)
                    response_headers = {key: value for key, value in response.headers.items()}
                    response_body = response.read().decode("utf-8", errors="replace")
                    response_status = int(getattr(response, "status", 200) or 200)
                    extracted = self._extract_step_captures(step.captures, response_headers, response_body)
                    variables.update(extracted)
                    status = "ok" if response_status == step.expected_status else "failed"
                    if status == "failed":
                        failures += 1
                    step_results.append(
                        {
                            "step_id": step.step_id,
                            "status": status,
                            "resolved_url": resolved_url,
                            "duration_ms": duration_ms,
                            "request_preview": self._sanitize_request_preview(step.method, resolved_url, headers, body),
                            "response_status": response_status,
                            "response_headers": self._sanitize_response_headers(response_headers),
                            "response_body_preview": self._sanitize_body_preview(response_body),
                            "extracted_variables": extracted,
                            "generated_curl": generated_curl,
                            "error": "" if status == "ok" else f"Expected {step.expected_status}, got {response_status}",
                        }
                    )
                    if status != "ok" and not step.continue_on_failure:
                        break
            except urllib.error.HTTPError as exc:
                duration_ms = int((time.perf_counter() - started) * 1000)
                body_preview = exc.read().decode("utf-8", errors="replace")
                failures += 1
                step_results.append(
                    {
                        "step_id": step.step_id,
                        "status": "failed",
                        "resolved_url": resolved_url,
                        "duration_ms": duration_ms,
                        "request_preview": self._sanitize_request_preview(step.method, resolved_url, headers, body),
                        "response_status": exc.code,
                        "response_headers": self._sanitize_response_headers(dict(exc.headers.items())),
                        "response_body_preview": self._sanitize_body_preview(body_preview),
                        "extracted_variables": {},
                        "generated_curl": generated_curl,
                        "error": str(exc),
                    }
                )
                if not step.continue_on_failure:
                    break
            except Exception as exc:
                duration_ms = int((time.perf_counter() - started) * 1000)
                failures += 1
                step_results.append(
                    {
                        "step_id": step.step_id,
                        "status": "failed",
                        "resolved_url": resolved_url,
                        "duration_ms": duration_ms,
                        "request_preview": self._sanitize_request_preview(step.method, resolved_url, headers, body),
                        "response_status": 0,
                        "response_headers": {},
                        "response_body_preview": "",
                        "extracted_variables": {},
                        "generated_curl": generated_curl,
                        "error": str(exc),
                    }
                )
                if not step.continue_on_failure:
                    break

        finished_at = utc_now_iso()
        status = "ok" if failures == 0 else ("partial" if failures < len(step_results) else "failed")
        return {
            "run_id": f"{flow.flow_id}-{uuid.uuid4().hex[:10]}",
            "flow_id": flow.flow_id,
            "environment_id": environment.environment_id,
            "started_at": started_at,
            "finished_at": finished_at,
            "status": status,
            "step_results": step_results,
            "summary": f"{len(step_results) - failures} of {len(step_results)} steps matched expectations",
        }

    def _template_string(self, value: str, variables: dict[str, str]) -> str:
        result = value
        for key, token in variables.items():
            result = result.replace(f"{{{{{key}}}}}", token)
        return result

    def _extract_step_captures(self, captures: list[Any], response_headers: dict[str, str], response_body: str) -> dict[str, str]:
        if not captures:
            return {}
        extracted: dict[str, str] = {}
        parsed_json: Any = None
        for capture in captures:
            value = ""
            if capture.source == "header":
                target = capture.selector.lower()
                for key, header_value in response_headers.items():
                    if key.lower() == target:
                        value = str(header_value)
                        break
            else:
                if parsed_json is None:
                    try:
                        parsed_json = json.loads(response_body)
                    except Exception:
                        parsed_json = {}
                value = str(self._json_selector(parsed_json, capture.selector) or "")
            if value:
                extracted[capture.variable_name] = value
        return extracted

    def _json_selector(self, payload: Any, selector: str) -> Any:
        current = payload
        for part in [token for token in selector.split(".") if token]:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list) and part.isdigit():
                index = int(part)
                current = current[index] if 0 <= index < len(current) else None
            else:
                return None
        return current

    def _sanitize_request_preview(self, method: str, url: str, headers: dict[str, str], body: str) -> dict[str, Any]:
        return {
            "method": method,
            "url": url,
            "headers": self._sanitize_response_headers(headers),
            "body_preview": self._sanitize_body_preview(body),
        }

    def _sanitize_response_headers(self, headers: dict[str, str]) -> dict[str, str]:
        sanitized: dict[str, str] = {}
        for key, value in headers.items():
            if key.lower() in {"authorization", "cookie", "set-cookie", "x-api-key"}:
                sanitized[key] = "[redacted]"
            else:
                sanitized[key] = value[:300]
        return sanitized

    def _sanitize_body_preview(self, body: str) -> str:
        preview = body[:2000]
        preview = re.sub(r'("?(?:token|secret|password|api[_-]?key|client[_-]?secret)"?\s*:\s*")[^"]+(")', r'\1[redacted]\2', preview, flags=re.IGNORECASE)
        preview = re.sub(r"(Bearer\s+)[A-Za-z0-9\-\._~\+/=]+", r"\1[redacted]", preview, flags=re.IGNORECASE)
        return preview

    def _curl_for_step(self, method: str, url: str, headers: dict[str, str], body: str) -> str:
        parts = [f"curl -X {method}", f"'{url}'"]
        for key, value in headers.items():
            safe_value = value.replace("'", "'\"'\"'")
            parts.append(f"-H '{key}: {safe_value}'")
        if body:
            safe_body = body.replace("'", "'\"'\"'")
            parts.append(f"--data '{safe_body}'")
        return " ".join(parts)

    def _collect_local_listener_details(self) -> list[dict[str, Any]]:
        result = self._run_local(["sh", "-lc", "ss -ltnp 2>/dev/null || lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null"])
        return self._parse_listener_output(result["stdout"])

    def _collect_remote_listener_details(self, ssh: Any) -> list[dict[str, Any]]:
        result = self._run_remote(ssh, "ss -ltnp 2>/dev/null || lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null")
        return self._parse_listener_output(result["stdout"])

    def _parse_listener_output(self, output: str) -> list[dict[str, Any]]:
        listeners: list[dict[str, Any]] = []
        seen: set[tuple[int, int | None, str]] = set()
        for raw_line in self._split_lines(output):
            line = raw_line.strip()
            if not line or line.lower().startswith(("state", "netid", "command")):
                continue
            port_match = re.search(r":(\d+)(?:\s|\(|$)", line)
            if not port_match:
                continue
            port = int(port_match.group(1))
            state = "LISTEN" if "LISTEN" in line.upper() else ""
            bind_address = ""
            process = ""
            pid: int | None = None

            ss_bind_match = re.search(r"\b(?:LISTEN|UNCONN)\s+\d+\s+\d+\s+(\S+):\d+", line)
            if ss_bind_match:
                bind_address = ss_bind_match.group(1)
            else:
                lsof_bind_match = re.search(r"(TCP|UDP)\s+(\S+):\d+", line)
                if lsof_bind_match:
                    bind_address = lsof_bind_match.group(2)

            ss_match = re.search(r'users:\(\("([^"]+)",pid=(\d+)', line)
            if ss_match:
                process = ss_match.group(1)
                pid = int(ss_match.group(2))
            else:
                lsof_match = re.match(r"(\S+)\s+(\d+)\s+", line)
                if lsof_match:
                    process = lsof_match.group(1)
                    pid = int(lsof_match.group(2))

            key = (port, pid, process)
            if key in seen:
                continue
            seen.add(key)
            listeners.append(
                {
                    "port": port,
                    "protocol": "tcp",
                    "process": process,
                    "pid": pid,
                    "state": state,
                    "bind_address": bind_address.strip("[]"),
                    "raw": line,
                }
            )
        listeners.sort(key=lambda item: item["port"])
        return listeners

    def _run_healthcheck_local(self, command: str) -> dict[str, str]:
        if not command.strip():
            return {"status": "skipped", "output": ""}
        result = self._run_local(["sh", "-lc", command])
        return {
            "status": "ok" if result["returncode"] == 0 else "failed",
            "output": (result["stdout"] or result["stderr"]).strip(),
        }

    def _run_healthcheck_remote(self, ssh: Any, command: str) -> dict[str, str]:
        if not command.strip():
            return {"status": "skipped", "output": ""}
        result = self._run_remote(ssh, command)
        return {
            "status": "ok" if result["returncode"] == 0 else "failed",
            "output": (result["stdout"] or result["stderr"]).strip(),
        }

    def _lookup_process_command(self, server: ResolvedServer, pid: int | None) -> str:
        if pid is None:
            return ""
        command = ["ps", "-p", str(pid), "-o", "command="]
        if server.connection_type == "local":
            result = self._run_local(command)
        else:
            with self._open_ssh(server) as connection:
                if connection is None:
                    return ""
                ssh, _ = connection
                result = self._run_remote(ssh, f"ps -p {pid} -o command=")
        return result["stdout"].strip()

    def _updated_node_manifest(
        self,
        existing_manifest: dict[str, Any],
        service: ServiceManifest,
        location: Any,
        flattened_scope: dict[str, list[str]],
        include_runtime_config: bool,
    ) -> dict[str, Any]:
        updated = dict(existing_manifest)
        updated["service_id"] = service.service_id
        updated["display_name"] = service.display_name
        updated["project_root"] = location.root
        updated["mode"] = "node"
        updated["repo_paths"] = flattened_scope["repo_paths"] or updated.get("repo_paths", [location.root])
        updated["docs_paths"] = flattened_scope["docs_paths"] or updated.get("docs_paths", [])
        updated["log_paths"] = flattened_scope["log_paths"] or updated.get("log_paths", [])
        updated["exclude_patterns"] = flattened_scope["exclude_globs"] or updated.get("exclude_patterns", [])
        updated["managed_docs"] = [entry.model_dump(mode="json") for entry in service.managed_docs]
        if include_runtime_config:
            updated["runtime"] = location.runtime.model_dump(mode="json")
        
        task_ledger = self.snapshots.get_service_task_ledger(service.service_id)
        tasks = task_ledger.get("tasks", [])
        latest_task = tasks[0] if tasks else {}
        if latest_task:
            updated["bootstrap_version"] = latest_task.get("bootstrap_version", "")
            updated["runtime_services"] = latest_task.get("runtime_services", [])
            updated["dependencies"] = latest_task.get("dependencies", [])
            updated["cross_dependencies"] = latest_task.get("cross_dependencies", [])
            if "diagram" in latest_task:
                updated["diagram"] = latest_task.get("diagram", "")

        updated["updated_at"] = utc_now_iso()
        return updated

    def _updated_scope_snapshot(
        self,
        existing_snapshot: dict[str, Any] | None,
        service: ServiceManifest,
        project_root: str,
        scope_entries: list[dict[str, Any]],
    ) -> dict[str, Any]:
        current = existing_snapshot or {}
        updates = list(current.get("scope_updates", []))
        updates.insert(
            0,
            {
                "timestamp": utc_now_iso(),
                "title": "Sync from control center",
                "summary": "Updated scope snapshot from control-center service configuration.",
                "changed_paths": [project_root],
                "scope_entries": scope_entries,
            },
        )
        return {
            "generated": utc_now_iso(),
            "service_id": service.service_id,
            "project_root": project_root,
            "scope_entries": scope_entries,
            "scope_updates": updates[:20],
        }

    def _node_pull_bundle_history_payload(self, service_id: str) -> dict[str, Any]:
        bundles = self.snapshots.list_pull_bundles(service_id)
        return {
            "generated": utc_now_iso(),
            "service_id": service_id,
            "bundles": bundles,
        }

    def _bundle_diff(
        self,
        previous_bundle: dict[str, Any] | None,
        copied_files: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        previous_files = {item.get("relative_path", ""): item for item in (previous_bundle or {}).get("files", [])}
        current_files = {item.get("relative_path", ""): item for item in copied_files}
        added = sorted(path for path in current_files if path not in previous_files)
        removed = sorted(path for path in previous_files if path not in current_files)
        changed = sorted(
            path for path in current_files
            if path in previous_files and current_files[path].get("sha256") != previous_files[path].get("sha256")
        )
        unchanged_count = max(0, len(current_files) - len(added) - len(changed))
        entries: list[dict[str, Any]] = []
        for change, paths, source in (
            ("added", added, current_files),
            ("removed", removed, previous_files),
            ("changed", changed, current_files),
        ):
            for path in paths:
                entries.append(
                    {
                        "change": change,
                        "relative_path": path,
                        "kind": source.get(path, {}).get("kind", "doc"),
                    }
                )
        summary = {
            "added_count": len(added),
            "removed_count": len(removed),
            "changed_count": len(changed),
            "unchanged_count": unchanged_count,
            "summary": (
                "Initial bundle snapshot."
                if previous_bundle is None
                else f"{len(added)} added, {len(removed)} removed, {len(changed)} changed, {unchanged_count} unchanged."
            ),
        }
        return summary, entries

    def _bundle_exposure_findings(self, mirrored_root: Path, copied_files: list[dict[str, Any]]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for copied in copied_files:
            relative_path = copied.get("relative_path", "")
            target = mirrored_root / relative_path
            if not target.exists() or target.is_dir():
                continue
            try:
                content = target.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for line_number, line in enumerate(content.splitlines(), start=1):
                for finding_kind, pattern in EXPOSURE_LINE_PATTERNS:
                    match = pattern.search(line)
                    if not match:
                        continue
                    variable_name = match.group(1) if finding_kind == "generic_token" and match.lastindex else ""
                    findings.append(
                        {
                            "relative_path": relative_path,
                            "finding_kind": finding_kind,
                            "variable_name": variable_name or "",
                            "line_number": line_number,
                            "redacted": True,
                        }
                    )
        unique: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in findings:
            key = f"{item['relative_path']}|{item['finding_kind']}|{item['variable_name']}|{item['line_number']}"
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    def _bundle_dependency_context(self, service: ServiceManifest) -> dict[str, Any]:
        ledger = self.snapshots.get_service_task_ledger(service.service_id)
        latest_task = ledger.get("tasks", [{}])[0] if ledger.get("tasks") else {}
        return {
            "dependencies": latest_task.get("dependencies", []),
            "cross_dependencies": latest_task.get("cross_dependencies", []),
            "notes": latest_task.get("notes", []),
            "diagram": latest_task.get("diagram", ""),
        }

    def _normalize_port(self, value: Any, default: int = 8010) -> int:
        try:
            port = int(value)
        except (TypeError, ValueError):
            return default
        return port if port > 0 else default

    def _extract_port_from_command(self, command: str) -> int | None:
        if not command:
            return None
        match = re.search(r"--port(?:=|\s+)(\d+)\b", command)
        if not match:
            return None
        return self._normalize_port(match.group(1), default=0) or None

    def _manifest_runtime_port(self, manifest: dict[str, Any] | None) -> int:
        return self._normalize_port((manifest or {}).get("runtime_port"), default=8010)

    def _cached_node_runtime_port(self, service_id: str, location_id: str) -> int | None:
        cache = self.snapshots._read_runtime_cache()
        record = cache.get("node_viewer", {}).get(service_id, {}).get(location_id, {})
        port = record.get("runtime_port")
        if isinstance(port, int) and port > 0:
            return port
        return None

    def _detect_node_runtime_port(self, service: ServiceManifest, location: Any, server: ResolvedServer, manifest: dict[str, Any] | None) -> int:
        manifest_port = self._manifest_runtime_port(manifest)
        cached_port = self._cached_node_runtime_port(service.service_id, location.location_id)
        project_root = location.root
        listeners = self._collect_local_listener_details() if server.connection_type == "local" else []
        if server.connection_type == "ssh":
            with self._open_ssh(server) as connection:
                if connection is not None:
                    ssh, _ = connection
                    listeners = self._collect_remote_listener_details(ssh)
        for listener in listeners:
            pid = listener.get("pid")
            if not isinstance(pid, int):
                continue
            command = self._lookup_process_command(server, pid)
            if "switchboard.cli" not in command or "node serve" not in command or project_root not in command:
                continue
            detected_port = self._extract_port_from_command(command)
            if detected_port:
                return detected_port
        return cached_port or manifest_port

    def _persist_manifest_runtime_port(
        self,
        server: ResolvedServer,
        project_root: str,
        manifest: dict[str, Any] | None,
        runtime_port: int,
    ) -> dict[str, Any] | None:
        if manifest is None:
            return None
        current_port = self._manifest_runtime_port(manifest)
        if current_port == runtime_port:
            return manifest
        updated_manifest = dict(manifest)
        updated_manifest["runtime_port"] = runtime_port
        if server.connection_type == "local":
            self._write_local_json(self._local_node_manifest_path(project_root), updated_manifest)
        else:
            with self._open_ssh(server) as connection:
                if connection is None:
                    return updated_manifest
                ssh, sftp = connection
                self._write_remote_json(ssh, sftp, self._remote_node_manifest_path(project_root), updated_manifest)
        return updated_manifest

    def _node_inspect_record(self, service: ServiceManifest, location: Any, server: ResolvedServer) -> dict[str, Any]:
        manifest_path = self._remote_node_manifest_path(location.root) if server.connection_type == "ssh" else str(self._local_node_manifest_path(location.root))
        manifest: dict[str, Any] | None = None
        tasks: dict[str, Any] | None = None
        runtime_state: dict[str, Any] = {"status": "missing", "pid": None, "runtime_dir": "", "log_file": ""}
        last_error = ""

        if server.connection_type == "local":
            root_path = Path(location.root)
            if not root_path.exists():
                return self._node_missing_record(service, location, manifest_path, "Location root does not exist.")
            manifest = self._read_local_json(self._local_node_manifest_path(location.root))
            tasks = self._read_local_json(self._local_completed_tasks_path(location.root))
            if manifest:
                runtime_port = self._detect_node_runtime_port(service, location, server, manifest)
                manifest = self._persist_manifest_runtime_port(server, location.root, manifest, runtime_port)
                runtime_state = node_status(location.root, port=runtime_port)
            else:
                runtime_port = self._cached_node_runtime_port(service.service_id, location.location_id) or 8010
        else:
            with self._open_ssh(server) as connection:
                if connection is None:
                    return self._node_missing_record(service, location, manifest_path, "SSH connection failed.")
                ssh, sftp = connection
                if not self._remote_exists(sftp, location.root):
                    return self._node_missing_record(service, location, manifest_path, "Location root does not exist.")
                manifest = self._read_remote_json(sftp, self._remote_node_manifest_path(location.root))
                tasks = self._read_remote_json(sftp, self._remote_completed_tasks_path(location.root))
                if manifest:
                    runtime_port = self._detect_node_runtime_port(service, location, server, manifest)
                    manifest = self._persist_manifest_runtime_port(server, location.root, manifest, runtime_port)
                    runtime_state = self._remote_node_status(ssh, location.root, runtime_port)
                else:
                    runtime_port = self._cached_node_runtime_port(service.service_id, location.location_id) or 8010

        node_present = manifest is not None
        bootstrap_ready = bool(tasks and tasks.get("tasks"))
        installed_version = str((manifest or {}).get("installed_version", ""))
        bootstrap_version = str((manifest or {}).get("bootstrap_version", ""))
        runtime_status = runtime_state.get("status", "missing")
        record = {
            "service_id": service.service_id,
            "location_id": location.location_id,
            "server_id": location.server_id,
            "root": location.root,
            "node_present": node_present,
            "bootstrap_ready": bootstrap_ready,
            "runtime_ready": runtime_status == "running",
            "installed_version": installed_version,
            "bootstrap_version": bootstrap_version,
            "manifest_updated_at": str((manifest or {}).get("updated_at", "")),
            "runtime_status": runtime_status,
            "runtime_pid": runtime_state.get("pid"),
            "runtime_port": runtime_port,
            "needs_install": not node_present,
            "needs_upgrade": False,
            "needs_bootstrap": bool(node_present and not bootstrap_ready),
            "attention_reason": self._node_attention_reason(node_present, bootstrap_ready),
            "manifest_path": manifest_path,
            "runtime_dir": runtime_state.get("runtime_dir", ""),
            "log_file": runtime_state.get("log_file", ""),
            "last_error": last_error,
        }
        return record

    def _node_missing_record(self, service: ServiceManifest, location: Any, manifest_path: str, reason: str) -> dict[str, Any]:
        runtime_port = self._cached_node_runtime_port(service.service_id, location.location_id) or 8010
        return {
            "service_id": service.service_id,
            "location_id": location.location_id,
            "server_id": location.server_id,
            "root": location.root,
            "node_present": False,
            "bootstrap_ready": False,
            "runtime_ready": False,
            "installed_version": "",
            "bootstrap_version": "",
            "manifest_updated_at": "",
            "runtime_status": "missing",
            "runtime_pid": None,
            "runtime_port": runtime_port,
            "needs_install": True,
            "needs_upgrade": False,
            "needs_bootstrap": False,
            "attention_reason": "deploy",
            "manifest_path": manifest_path,
            "runtime_dir": "",
            "log_file": "",
            "last_error": reason,
        }

    def _node_attention_reason(self, node_present: bool, bootstrap_ready: bool) -> str:
        if not node_present:
            return "deploy"
        if not bootstrap_ready:
            return "bootstrap"
        return ""

    def _ensure_local_node_runtime(self, project_root: str) -> None:
        runtime_root = Path(project_root) / "switchboard" / "runtime"
        venv_path = runtime_root / ".venv"
        venv_python = venv_path / "bin" / "python"
        if not venv_python.exists():
            subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=False)
        wheel_path = self._build_local_wheel()
        if wheel_path and venv_python.exists():
            subprocess.run([str(venv_python), "-m", "pip", "install", "--upgrade", str(wheel_path)], check=False)

    def _fetch_latest_node_release(self) -> dict[str, Any]:
        request = urllib.request.Request(
            GITHUB_LATEST_RELEASE_API,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "switchboard-control-center",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return {
                "status": "unreachable",
                "message": f"Failed to reach GitHub latest release: {exc}",
                "version": "",
                "asset_url": "",
                "html_url": f"https://github.com/{GITHUB_REPO}/releases",
                "published_at": "",
                "notes": "",
            }
        assets = payload.get("assets", []) or []
        wheel_asset = next((asset for asset in assets if str(asset.get("name", "")).endswith(".whl")), None)
        tag_name = str(payload.get("tag_name", ""))
        version = tag_name[1:] if tag_name.startswith("v") else tag_name
        return {
            "status": "ok" if wheel_asset else "partial",
            "message": "" if wheel_asset else "Latest GitHub release does not contain a wheel asset.",
            "version": version,
            "asset_url": str((wheel_asset or {}).get("browser_download_url", "")),
            "html_url": str(payload.get("html_url", "")),
            "published_at": str(payload.get("published_at", "")),
            "notes": str(payload.get("body", "")),
        }

    def _release_check_payload(self, node: dict[str, Any], release: dict[str, Any]) -> dict[str, Any]:
        current_version = str(node.get("installed_version", ""))
        latest_version = str(release.get("version", ""))
        return {
            "status": release.get("status", "unverified"),
            "current_version": current_version,
            "latest_version": latest_version,
            "update_available": bool(node.get("node_present") and latest_version and latest_version != current_version),
            "published_at": release.get("published_at", ""),
            "release_url": release.get("html_url", ""),
            "asset_url": release.get("asset_url", ""),
            "notes": release.get("notes", ""),
            "message": release.get("message", ""),
        }

    def _install_local_node_release(
        self,
        project_root: str,
        service_id: str,
        display_name: str,
        wheel_url: str,
    ) -> dict[str, Any]:
        runtime_root = Path(project_root) / "switchboard" / "runtime"
        venv_path = runtime_root / ".venv"
        venv_python = venv_path / "bin" / "python"
        runtime_root.mkdir(parents=True, exist_ok=True)
        if not venv_python.exists():
            subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=False)
        install_result = subprocess.run(
            [str(venv_python), "-m", "pip", "install", "--upgrade", wheel_url],
            capture_output=True,
            text=True,
            check=False,
        )
        if install_result.returncode != 0:
            return {"status": "partial", "message": (install_result.stderr or install_result.stdout).strip()}
        scaffold_result = subprocess.run(
            [
                str(venv_python),
                "-m",
                "switchboard.cli",
                "node",
                "install",
                "--project-root",
                str(Path(project_root).resolve()),
                "--service-id",
                service_id,
                "--display-name",
                display_name,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if scaffold_result.returncode != 0:
            return {"status": "partial", "message": (scaffold_result.stderr or scaffold_result.stdout).strip()}
        return {"status": "ok", "message": "Installed latest GitHub release locally."}

    def _build_local_wheel(self) -> Path | None:
        dist_dir = Path(tempfile.mkdtemp(prefix="switchboard-wheel-"))
        result = subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "--no-deps", ".", "-w", str(dist_dir)],
            cwd=Path(__file__).resolve().parent.parent,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        wheels = sorted(dist_dir.glob("switchboard-*.whl"))
        return wheels[-1] if wheels else None

    def _install_remote_node_release(
        self,
        server: ResolvedServer,
        project_root: str,
        service_id: str,
        display_name: str,
        wheel_url: str,
    ) -> dict[str, Any]:
        with self._open_ssh(server) as connection:
            if connection is None:
                return {"status": "unreachable", "message": "SSH connection failed."}
            ssh, _ = connection
            runtime_root = posixpath.join(project_root, "switchboard", "runtime")
            venv_dir = posixpath.join(runtime_root, ".venv")
            venv_python = posixpath.join(venv_dir, "bin", "python")
            command = (
                f"mkdir -p {self._quote(runtime_root)} && "
                f"python3 -m venv {self._quote(venv_dir)} && "
                f"{self._quote(venv_python)} -m pip install --upgrade pip && "
                f"{self._quote(venv_python)} -m pip install --upgrade {self._quote(wheel_url)} && "
                f"{self._quote(venv_python)} -m switchboard.cli node install "
                f"--project-root {self._quote(project_root)} "
                f"--service-id {self._quote(service_id)} "
                f"--display-name {self._quote(display_name)}"
            )
            result = self._run_remote(ssh, command)
            if result["returncode"] != 0:
                return {"status": "partial", "message": (result["stderr"] or result["stdout"]).strip()}
            return {"status": "ok", "message": "Installed latest GitHub release remotely."}

    def _upload_tree(self, sftp: Any, local_root: Path, remote_root: str, force: bool = False) -> None:
        protected_force_paths = {
            ("local", "tasks-completed.md"),
            ("local", "control-center-handoff.md"),
            ("local", "runbook.md"),
            ("local", "approach-history.md"),
            ("evidence", "completed-tasks.json"),
            ("evidence", "doc-index.json"),
            ("evidence", "repo-safety-history.json"),
            ("evidence", "pull-bundle-history.json"),
            ("evidence", "scope.snapshot.json"),
        }
        for path in sorted(local_root.rglob("*")):
            relative = path.relative_to(local_root)
            remote_path = posixpath.join(remote_root, str(relative).replace(os.sep, "/"))
            if path.is_dir():
                try:
                    sftp.mkdir(remote_path)
                except OSError:
                    pass
                continue
            parent = posixpath.dirname(remote_path)
            current = ""
            for part in [p for p in parent.split("/") if p]:
                current = f"{current}/{part}" if current else f"/{part}"
                try:
                    sftp.mkdir(current)
                except OSError:
                    pass
            if relative.parts[:2] in protected_force_paths and self._remote_exists(sftp, remote_path):
                continue
            sftp.put(str(path), remote_path)

    def _remote_node_status(self, ssh: Any, project_root: str, port: int) -> dict[str, Any]:
        runtime_dir = posixpath.join(project_root, "switchboard", "runtime")
        pid_file = posixpath.join(runtime_dir, "node.pid")
        log_file = posixpath.join(runtime_dir, "node.log")
        command = (
            f"PID=''; test -f {self._quote(pid_file)} && PID=$(cat {self._quote(pid_file)}); "
            f"STATUS=stopped; "
            f"if [ -n \"$PID\" ] && kill -0 \"$PID\" 2>/dev/null; then STATUS=running; fi; "
            f"PORT_PID=$(lsof -tiTCP:{port} -sTCP:LISTEN 2>/dev/null | head -n1); "
            f"if [ \"$STATUS\" = stopped ] && [ -n \"$PORT_PID\" ]; then STATUS=running_unmanaged; fi; "
            f"printf '%s|%s|%s|%s' \"$STATUS\" \"$PID\" \"$PORT_PID\" {self._quote(runtime_dir)}"
        )
        result = self._run_remote(ssh, command)
        raw = result["stdout"].strip().split("|")
        status = raw[0] if raw and raw[0] else "missing"
        pid = int(raw[1]) if len(raw) > 1 and raw[1].isdigit() else None
        return {"status": status, "pid": pid, "runtime_dir": runtime_dir, "log_file": log_file}

    def _restart_remote_node(self, server: ResolvedServer, project_root: str, runtime_port: int) -> dict[str, Any]:
        with self._open_ssh(server) as connection:
            if connection is None:
                return {"status": "unreachable", "message": "SSH connection failed."}
            ssh, _ = connection
            runtime_root = posixpath.join(project_root, "switchboard", "runtime")
            venv_python = posixpath.join(runtime_root, ".venv", "bin", "python")
            pid_file = posixpath.join(runtime_root, "node.pid")
            log_file = posixpath.join(runtime_root, "node.log")
            command = (
                f"mkdir -p {self._quote(runtime_root)}; "
                f"if [ -f {self._quote(pid_file)} ]; then PID=$(cat {self._quote(pid_file)}); kill \"$PID\" 2>/dev/null || true; rm -f {self._quote(pid_file)}; fi; "
                f"nohup {self._quote(venv_python)} -m switchboard.cli node serve --project-root {self._quote(project_root)} --host 127.0.0.1 --port {runtime_port} "
                f">> {self._quote(log_file)} 2>&1 < /dev/null & echo $! > {self._quote(pid_file)}"
            )
            result = self._run_remote(ssh, command)
            if result["returncode"] != 0:
                return {"status": "partial", "message": (result["stderr"] or result["stdout"]).strip()}
            verify_command = (
                f"sleep 2; "
                f"PID=''; test -f {self._quote(pid_file)} && PID=$(cat {self._quote(pid_file)}); "
                f"STATUS=stopped; "
                f"if [ -n \"$PID\" ] && kill -0 \"$PID\" 2>/dev/null; then STATUS=running; fi; "
                f"PORT_PID=$(lsof -tiTCP:{runtime_port} -sTCP:LISTEN 2>/dev/null | head -n1); "
                f"if [ \"$STATUS\" = stopped ] && [ -n \"$PORT_PID\" ]; then STATUS=running_unmanaged; fi; "
                f"if [ \"$STATUS\" = stopped ]; then tail -n 40 {self._quote(log_file)} 2>/dev/null || true; fi; "
                f"printf '\\n__STATUS__=%s\\n__PID__=%s\\n__PORT_PID__=%s\\n' \"$STATUS\" \"$PID\" \"$PORT_PID\""
            )
            verification = self._run_remote(ssh, verify_command)
            output = verification["stdout"]
            status_line = next((line for line in output.splitlines() if line.startswith("__STATUS__=")), "__STATUS__=stopped")
            runtime_status = status_line.split("=", 1)[1].strip() or "stopped"
            if runtime_status == "stopped":
                log_excerpt = output.split("__STATUS__=", 1)[0].strip()
                message = "Node runtime failed to start."
                if log_excerpt:
                    message = f"{message} {log_excerpt}"
                return {"status": "partial", "message": message}
            return {"status": "ok", "message": f"Node runtime {runtime_status}."}

    @contextmanager
    def _open_ssh(self, server: ResolvedServer) -> Iterator[tuple[Any, Any] | None]:
        if server.connection_type != "ssh":
            yield None
            return
        try:
            import paramiko

            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                hostname=server.host,
                port=server.port,
                username=server.username,
                password=server.password,
                timeout=self.settings.ssh_timeout_seconds,
                banner_timeout=self.settings.ssh_timeout_seconds,
                auth_timeout=self.settings.ssh_timeout_seconds,
            )
            sftp = client.open_sftp()
            try:
                yield (client, sftp)
            finally:
                sftp.close()
                client.close()
        except Exception:
            yield None

    def _run_local(self, command: list[str]) -> dict[str, Any]:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}

    def _run_remote(self, ssh: Any, command: str) -> dict[str, Any]:
        stdin, stdout, stderr = ssh.exec_command(command, timeout=self.settings.ssh_timeout_seconds)
        del stdin
        return {
            "stdout": stdout.read().decode("utf-8", errors="replace"),
            "stderr": stderr.read().decode("utf-8", errors="replace"),
            "returncode": stdout.channel.recv_exit_status(),
        }

    def _walk_local_files(self, root: Path, excludes: list[str]) -> Iterator[Path]:
        count = 0
        for current_root, dirnames, filenames in os.walk(root):
            current_path = Path(current_root)
            dirnames[:] = [
                dirname
                for dirname in dirnames
                if not self._matches_exclude(dirname, str(current_path / dirname), excludes)
            ]
            for filename in filenames:
                file_path = current_path / filename
                if self._matches_exclude(filename, str(file_path), excludes):
                    continue
                yield file_path
                count += 1
                if count >= self.settings.max_files_per_path:
                    return

    def _walk_remote_files(self, sftp: Any, root: str, excludes: list[str]) -> Iterator[tuple[str, Any]]:
        stack = [root]
        count = 0
        while stack:
            current = stack.pop()
            try:
                for attrs in sftp.listdir_attr(current):
                    path = posixpath.join(current, attrs.filename)
                    if self._matches_exclude(attrs.filename, path, excludes):
                        continue
                    if stat.S_ISDIR(attrs.st_mode):
                        stack.append(path)
                        continue
                    yield path, attrs
                    count += 1
                    if count >= self.settings.max_files_per_path:
                        return
            except OSError:
                continue

    def _remote_exists(self, sftp: Any, path: str) -> bool:
        try:
            sftp.stat(path)
            return True
        except OSError:
            return False

    @lru_cache(maxsize=64)
    def _compile_pathspec(self, patterns: tuple[str, ...]) -> PathSpec:
        normalized = []
        for pattern in patterns:
            token = str(pattern).strip().replace("\\", "/")
            if not token:
                continue
            normalized.append(token.lstrip("/"))
        return PathSpec.from_lines("gitignore", normalized)

    def _candidate_match_paths(self, name: str, full_path: str) -> list[str]:
        normalized_full = str(full_path).replace("\\", "/").lstrip("/")
        basename = str(name).replace("\\", "/")
        candidates = [normalized_full, basename]
        parts = [part for part in normalized_full.split("/") if part]
        for index in range(len(parts)):
            candidates.append("/".join(parts[index:]))
        deduped: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate and candidate not in seen:
                seen.add(candidate)
                deduped.append(candidate)
        return deduped

    def _matches_exclude(self, name: str, full_path: str, excludes: list[str]) -> bool:
        if self._is_explicitly_excluded(full_path, excludes):
            return True
        spec = self._compile_pathspec(tuple(excludes))
        return any(spec.match_file(candidate) for candidate in self._candidate_match_paths(name, full_path))

    def _is_explicitly_excluded(self, full_path: str, excludes: list[str]) -> bool:
        normalized_full = str(full_path).replace("\\", "/").rstrip("/")
        for pattern in excludes:
            token = str(pattern).strip().replace("\\", "/").rstrip("/")
            if not token or any(char in token for char in "*?["):
                continue
            normalized_token = token.lstrip("/")
            normalized_full_cmp = normalized_full.lstrip("/")
            if normalized_full_cmp == normalized_token:
                return True
            if normalized_full_cmp.startswith(normalized_token + "/"):
                return True
        return False

    def _matches_secret_pattern(self, name: str, full_path: str, patterns: list[str]) -> bool:
        spec = self._compile_pathspec(tuple(patterns))
        return any(spec.match_file(candidate) for candidate in self._candidate_match_paths(name, full_path))

    def _matched_pattern(self, name: str, full_path: str, patterns: list[str]) -> str:
        candidates = self._candidate_match_paths(name, full_path)
        for pattern in patterns:
            spec = self._compile_pathspec((pattern,))
            if any(spec.match_file(candidate) for candidate in candidates):
                return pattern
        return ""

    def _suggest_scope_kind(self, name: str, full_path: str, entry_type: str) -> str:
        lowered = name.lower()
        path_lower = full_path.lower()
        if self._matches_exclude(name, full_path, DEFAULT_EXCLUDE_GLOBS):
            return "exclude"
        if lowered.endswith(".log") or "/logs" in path_lower or "\\logs" in path_lower:
            return "log"
        if "/switchboard/core" in path_lower or "/switchboard/local" in path_lower or "/switchboard/evidence" in path_lower:
            return "doc"
        if lowered in {"readme.md", "runbook.md", "approach-history.md", "agents.md"}:
            return "doc"
        if "/docs" in path_lower or "/documentation" in path_lower or lowered.endswith(".md"):
            return "doc"
        if entry_type == "dir" and os.path.exists(full_path):
            if any((Path(full_path) / marker).exists() for marker in ("pyproject.toml", "requirements.txt", "package.json")):
                return "repo"
            return "doc"
        if entry_type == "file":
            if lowered.endswith((".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env", ".example")):
                return "doc"
            if lowered.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".sh")):
                return "repo"
            return "doc"
        return "doc"

    def _file_record(self, service: ServiceManifest, server_id: str, file_path: Path, kind: str) -> dict[str, Any]:
        stats = file_path.stat()
        return {
            "service_id": service.service_id,
            "server_id": server_id,
            "kind": kind,
            "path": str(file_path),
            "name": file_path.name,
            "size": stats.st_size,
            "modified_at": self._format_mtime(stats.st_mtime),
        }

    def _remote_file_record(
        self,
        service: ServiceManifest,
        server_id: str,
        item: tuple[str, Any],
        kind: str,
    ) -> dict[str, Any]:
        path, attrs = item
        return {
            "service_id": service.service_id,
            "server_id": server_id,
            "kind": kind,
            "path": path,
            "name": posixpath.basename(path),
            "size": attrs.st_size,
            "modified_at": self._format_mtime(attrs.st_mtime),
        }

    def _format_mtime(self, timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(microsecond=0).isoformat()

    def _split_lines(self, value: str) -> list[str]:
        return [line for line in value.splitlines() if line.strip()]

    def _quote(self, path: str) -> str:
        return "'" + path.replace("'", "'\"'\"'") + "'"
