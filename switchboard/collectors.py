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
    CollectRequest,
    DiscoveryTreeRequest,
    DownloadRequest,
    GitPushRequest,
    GitPullRequest,
    PullBundleRequest,
    RepoActionRequest,
    ResolvedServer,
    ScanRootRequest,
    ServiceManifest,
)
from .storage import SnapshotStore, utc_now_iso

SECRET_CONTENT_PATTERNS = [
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("credential_assignment", re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd|client[_-]?secret)\s*[:=]\s*['\"][^'\"]{4,}['\"]")),
    ("mongodb_uri", re.compile(r"mongodb(?:\+srv)?://[^/\s:@]+:[^/\s:@]+@")),
]


class CollectionCoordinator:
    def __init__(self, settings: Settings, manifests: ManifestStore, snapshots: SnapshotStore) -> None:
        self.settings = settings
        self.manifests = manifests
        self.snapshots = snapshots

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
        } | set(workspace.servers)
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

    def pull_bundle(self, service_id: str, request: PullBundleRequest) -> dict[str, Any]:
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
        if server.connection_type == "local":
            copied_files.extend(self._copy_bundle_local(service, location.root, scope_entries, exclude_patterns, mirrored_root))
        else:
            with self._open_ssh(server) as connection:
                if connection is None:
                    return {"status": "unreachable", "message": "SSH connection failed."}
                _, sftp = connection
                copied_files.extend(self._copy_bundle_remote(service, sftp, location.root, scope_entries, exclude_patterns, mirrored_root))

        repo_metadata = []
        for repo_path in service.repo_paths:
            if repo_path.startswith(location.root):
                repo_metadata.append(self._repo_status(server, repo_path))

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
            "repo_metadata": repo_metadata,
            "files": copied_files,
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
        }
        self.snapshots.append_pull_bundle(history_record)
        return {
            "status": "ok" if copied_files else "partial",
            **history_record,
            "files": copied_files,
            "repo_metadata": repo_metadata,
        }

    def _collect_server_summary(self, server_id: str, server: ResolvedServer) -> dict[str, Any]:
        if server.connection_type == "local":
            return self._collect_local_server_summary(server_id, server)
        return self._collect_ssh_server_summary(server_id, server)

    def _select_location(self, service: ServiceManifest, server_id: str | None) -> Any | None:
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
                location_result = self._collect_local_location(service, location.root, excludes, secret_patterns)
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
        root: str,
        excludes: list[str],
        secret_patterns: list[str],
    ) -> dict[str, Any]:
        root_path = Path(root)
        if not root_path.exists():
            return {"status": "path_missing", "repos": [], "docs": [], "logs": [], "secrets": []}
        repos = [self._repo_status(self.manifests.resolve_server("local_mac"), path) for path in service.repo_paths if path.startswith(root)]
        docs = self._inventory_paths_local(service, service.docs_paths, "doc", excludes)
        logs = self._inventory_paths_local(service, service.log_paths, "log", excludes)
        secrets = self._scan_secret_paths_local(service, root_path, excludes, secret_patterns)
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
                entries.append(self._file_record(service, "local_mac", path, kind))
                continue
            for file_path in self._walk_local_files(path, excludes):
                entries.append(self._file_record(service, "local_mac", file_path, kind))
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
                        "server_id": "local_mac",
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
    ) -> list[dict[str, Any]]:
        copied: list[dict[str, Any]] = []
        for entry in scope_entries:
            if entry.kind == "exclude":
                continue
            if not entry.path.startswith(location_root):
                continue
            for source in self._expand_local_entry(entry.path, exclude_patterns):
                relative = self._bundle_relative_path(source, location_root)
                target = mirrored_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                copied.append(self._copied_file_record(str(source), str(target), entry.kind, relative_path=str(relative)))
        return copied

    def _copy_bundle_remote(
        self,
        service: ServiceManifest,
        sftp: Any,
        location_root: str,
        scope_entries: list[Any],
        exclude_patterns: list[str],
        mirrored_root: Path,
    ) -> list[dict[str, Any]]:
        copied: list[dict[str, Any]] = []
        for entry in scope_entries:
            if entry.kind == "exclude":
                continue
            if not entry.path.startswith(location_root):
                continue
            for source_path, attrs in self._expand_remote_entry(sftp, entry.path, exclude_patterns):
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
        return copied

    def _expand_local_entry(self, path: str, exclude_patterns: list[str]) -> list[Path]:
        source = Path(path)
        if not source.exists():
            return []
        if source.is_file():
            return [] if self._matches_exclude(source.name, str(source), exclude_patterns) else [source]
        return list(self._walk_local_files(source, exclude_patterns))

    def _expand_remote_entry(self, sftp: Any, path: str, exclude_patterns: list[str]) -> list[tuple[str, Any]]:
        if not self._remote_exists(sftp, path):
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
        spec = self._compile_pathspec(tuple(excludes))
        return any(spec.match_file(candidate) for candidate in self._candidate_match_paths(name, full_path))

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
        if lowered in {"readme.md", "runbook.md", "approach-history.md", "agents.md"}:
            return "doc"
        if "/docs" in path_lower or "/documentation" in path_lower or lowered.endswith(".md"):
            return "doc"
        if entry_type == "dir" and any(token in path_lower for token in (".git", "src", "app", "backend", "frontend", "project")):
            return "repo"
        if entry_type == "dir" and os.path.exists(full_path):
            if any((Path(full_path) / marker).exists() for marker in ("pyproject.toml", "requirements.txt", "package.json")):
                return "repo"
        if entry_type == "file":
            if lowered.endswith((".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env", ".example")):
                return "doc"
            if lowered.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".sh")):
                return "doc"
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
