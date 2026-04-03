"""Manifest loading and mutation."""

from __future__ import annotations

import hashlib
import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import Settings
from .models import (
    ManagedDocConfig,
    RepoPolicy,
    ResolvedServer,
    ScopeEntry,
    ServerManifest,
    ServiceCreateRequest,
    ServiceManifest,
    ServicePatchRequest,
    WorkspaceManifest,
)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=False)
        handle.write("\n")


@lru_cache(maxsize=1)
def _load_local_env_files() -> dict[str, str]:
    values: dict[str, str] = {}
    for name in (".env", ".env.local"):
        path = Path.cwd() / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def server_env_key(server_id: str, suffix: str) -> str:
    token = re.sub(r"[^A-Z0-9]+", "_", server_id.upper())
    return f"SWITCHBOARD_SERVER_{token}_{suffix}"


def _has_glob(path: str) -> bool:
    return any(token in path for token in ("*", "?", "["))


def _guess_path_type(path: str, kind: str) -> str:
    if kind == "exclude" or _has_glob(path):
        return "glob"
    if path.endswith("/"):
        return "dir"
    return "file" if Path(path).suffix else "dir"


def _scope_entry_id(kind: str, path: str) -> str:
    digest = hashlib.sha1(f"{kind}:{path}".encode("utf-8")).hexdigest()[:12]
    return f"{kind}-{digest}"


def _default_safety_profile(service_id: str, repo_path: str) -> str:
    token = f"{service_id}:{repo_path}".lower()
    return "secret_heavy" if "lambda" in token else "generic_python"


def _default_push_mode(service_id: str, repo_path: str) -> str:
    return "blocked" if _default_safety_profile(service_id, repo_path) == "secret_heavy" else "allowed"


def _scope_entries_from_record(item: dict[str, Any]) -> list[ScopeEntry]:
    if item.get("scope_entries"):
        entries = [ScopeEntry.model_validate(entry) for entry in item["scope_entries"]]
    else:
        entries = []
        for kind, source_field in (
            ("repo", "repo_paths"),
            ("doc", "docs_paths"),
            ("log", "log_paths"),
            ("exclude", "exclude_globs"),
        ):
            for path in item.get(source_field, []):
                entries.append(
                    ScopeEntry(
                        entry_id=_scope_entry_id(kind, path),
                        kind=kind,
                        path=path,
                        path_type=_guess_path_type(path, kind),
                        source="seeded",
                        enabled=True,
                    )
                )

    deduped: list[ScopeEntry] = []
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        key = (entry.kind, entry.path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(
            ScopeEntry(
                entry_id=entry.entry_id or _scope_entry_id(entry.kind, entry.path),
                kind=entry.kind,
                path=entry.path,
                path_type=entry.path_type,
                source=entry.source,
                enabled=entry.enabled,
            )
        )
    return deduped


def _flatten_scope(entries: list[ScopeEntry]) -> dict[str, list[str]]:
    repo_paths = [entry.path for entry in entries if entry.enabled and entry.kind == "repo"]
    docs_paths = [entry.path for entry in entries if entry.enabled and entry.kind == "doc"]
    log_paths = [entry.path for entry in entries if entry.enabled and entry.kind == "log"]
    exclude_globs = [entry.path for entry in entries if entry.enabled and entry.kind == "exclude"]
    return {
        "repo_paths": repo_paths,
        "docs_paths": docs_paths,
        "log_paths": log_paths,
        "exclude_globs": exclude_globs,
        "allowed_git_pull_paths": repo_paths,
    }


def _repo_policies_from_record(item: dict[str, Any], scope_entries: list[ScopeEntry]) -> list[RepoPolicy]:
    if item.get("repo_policies"):
        policies = [RepoPolicy.model_validate(policy) for policy in item["repo_policies"]]
    else:
        repo_paths = [entry.path for entry in scope_entries if entry.enabled and entry.kind == "repo"]
        policies = [
            RepoPolicy(
                repo_path=repo_path,
                push_mode=_default_push_mode(item.get("service_id", ""), repo_path),
                safety_profile=_default_safety_profile(item.get("service_id", ""), repo_path),
            )
            for repo_path in repo_paths
        ]

    deduped: list[RepoPolicy] = []
    seen: set[str] = set()
    for policy in policies:
        if policy.repo_path in seen:
            continue
        seen.add(policy.repo_path)
        deduped.append(policy)
    return deduped


def _default_managed_docs() -> list[ManagedDocConfig]:
    defaults = [
        ("readme", "README.md", False),
        ("api", "API.md", False),
        ("changelog", "CHANGELOG.md", False),
        ("handoff", "switchboard/local/control-center-handoff.md", True),
        ("runbook", "switchboard/local/runbook.md", True),
        ("approach_history", "switchboard/local/approach-history.md", True),
        ("doc_index_md", "switchboard/local/doc-index.md", True),
        ("doc_index_json", "switchboard/evidence/doc-index.json", True),
    ]
    return [
        ManagedDocConfig(doc_id=doc_id, path=path, enabled=enabled)
        for doc_id, path, enabled in defaults
    ]


def _managed_docs_from_record(item: dict[str, Any]) -> list[ManagedDocConfig]:
    entries = [ManagedDocConfig.model_validate(entry) for entry in item.get("managed_docs", [])]
    if not entries:
        entries = _default_managed_docs()

    deduped: list[ManagedDocConfig] = []
    seen: set[str] = set()
    defaults_by_id = {entry.doc_id: entry for entry in _default_managed_docs()}
    for entry in entries:
        if entry.doc_id in seen:
            continue
        seen.add(entry.doc_id)
        default = defaults_by_id.get(entry.doc_id)
        deduped.append(
            ManagedDocConfig(
                doc_id=entry.doc_id,
                path=entry.path or (default.path if default else ""),
                enabled=entry.enabled,
                generated_from=entry.generated_from,
                last_generated_at=entry.last_generated_at,
            )
        )
    for doc_id, default in defaults_by_id.items():
        if doc_id in seen:
            continue
        deduped.append(default)
    return deduped


def _normalize_service_record(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    scope_entries = _scope_entries_from_record(normalized)
    managed_docs = _managed_docs_from_record(normalized)
    repo_policies = _repo_policies_from_record(normalized, scope_entries)
    normalized["scope_entries"] = [entry.model_dump(mode="json") for entry in scope_entries]
    normalized["managed_docs"] = [entry.model_dump(mode="json") for entry in managed_docs]
    normalized["repo_policies"] = [policy.model_dump(mode="json") for policy in repo_policies]
    normalized.update(_flatten_scope(scope_entries))
    return normalized


class ManifestStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._servers_path = settings.manifest_dir / "servers.json"
        self._workspaces_path = settings.manifest_dir / "workspaces.json"
        self._services_path = settings.manifest_dir / "services.json"
        self._projects_path = settings.manifest_dir / "projects.json"

    def load_servers(self) -> list[ServerManifest]:
        return [ServerManifest.model_validate(item) for item in load_json(self._servers_path)]

    def load_workspaces(self) -> list[WorkspaceManifest]:
        return [WorkspaceManifest.model_validate(item) for item in load_json(self._workspaces_path)]

    def load_services(self) -> list[ServiceManifest]:
        return [ServiceManifest.model_validate(_normalize_service_record(item)) for item in load_json(self._services_path)]

    def load_projects(self) -> list[ProjectManifest]:
        return [ProjectManifest.model_validate(item) for item in load_json(self._projects_path)]

    def get_server(self, server_id: str) -> ServerManifest:
        for server in self.load_servers():
            if server.server_id == server_id:
                return server
        raise KeyError(f"Unknown server: {server_id}")

    def get_workspace(self, workspace_id: str) -> WorkspaceManifest:
        for workspace in self.load_workspaces():
            if workspace.workspace_id == workspace_id:
                return workspace
        raise KeyError(f"Unknown workspace: {workspace_id}")

    def get_service(self, service_id: str) -> ServiceManifest:
        for service in self.load_services():
            if service.service_id == service_id:
                return service
        raise KeyError(f"Unknown service: {service_id}")

    def get_workspace_services(self, workspace_id: str) -> list[ServiceManifest]:
        return [service for service in self.load_services() if service.workspace_id == workspace_id]

    def get_repo_policy(self, service_id: str, repo_path: str) -> RepoPolicy | None:
        service = self.get_service(service_id)
        for policy in service.repo_policies:
            if policy.repo_path == repo_path:
                return policy
        return None

    def resolve_server(
        self,
        server_id: str,
        runtime_passwords: dict[str, str] | None = None,
    ) -> ResolvedServer:
        server = self.get_server(server_id)
        runtime_passwords = runtime_passwords or {}
        env_values = _load_local_env_files()
        host = os.getenv(server_env_key(server_id, "HOST")) or env_values.get(server_env_key(server_id, "HOST"), server.host)
        username = os.getenv(server_env_key(server_id, "USERNAME")) or env_values.get(server_env_key(server_id, "USERNAME"), server.username)
        port = int(os.getenv(server_env_key(server_id, "PORT")) or env_values.get(server_env_key(server_id, "PORT"), str(server.port)))
        password = (
            runtime_passwords.get(server_id)
            or os.getenv(server_env_key(server_id, "PASSWORD"))
            or env_values.get(server_env_key(server_id, "PASSWORD"))
            or None
        )
        payload = server.model_dump()
        payload.update(
            {
                "host": host,
                "username": username,
                "port": port,
                "password": password,
            }
        )
        return ResolvedServer(
            **payload,
        )

    def create_service(self, workspace_id: str, payload: ServiceCreateRequest) -> ServiceManifest:
        self.get_workspace(workspace_id)
        existing = self.load_services()
        if any(service.service_id == payload.service_id for service in existing):
            raise ValueError(f"Service already exists: {payload.service_id}")
        service = ServiceManifest.model_validate(
            _normalize_service_record(
                {
                    "workspace_id": workspace_id,
                    **payload.model_dump(mode="json"),
                }
            )
        )
        save_json(self._services_path, [*load_json(self._services_path), service.model_dump(mode="json")])
        workspaces = load_json(self._workspaces_path)
        for workspace in workspaces:
            if workspace["workspace_id"] != workspace_id:
                continue
            services = workspace.setdefault("services", [])
            if payload.service_id not in services:
                services.append(payload.service_id)
            break
        save_json(self._workspaces_path, workspaces)
        return service

    def patch_service(self, service_id: str, payload: ServicePatchRequest) -> ServiceManifest:
        services = load_json(self._services_path)
        updated: ServiceManifest | None = None
        for index, item in enumerate(services):
            if item["service_id"] != service_id:
                continue
            merged = _normalize_service_record({**item, **payload.model_dump(exclude_none=True, mode="json")})
            updated = ServiceManifest.model_validate(merged)
            services[index] = updated.model_dump(mode="json")
            break
        if updated is None:
            raise KeyError(f"Unknown service: {service_id}")
        save_json(self._services_path, services)
        return updated

    def delete_service(self, service_id: str) -> ServiceManifest:
        services = load_json(self._services_path)
        removed: ServiceManifest | None = None
        retained: list[dict[str, Any]] = []

        for item in services:
            if item["service_id"] == service_id:
                removed = ServiceManifest.model_validate(_normalize_service_record(item))
                continue
            retained.append(item)

        if removed is None:
            raise KeyError(f"Unknown service: {service_id}")

        save_json(self._services_path, retained)

        workspaces = load_json(self._workspaces_path)
        for workspace in workspaces:
            services_list = workspace.setdefault("services", [])
            workspace["services"] = [item for item in services_list if item != service_id]
        save_json(self._workspaces_path, workspaces)
        return removed

    def get_project(self, project_id: str) -> ProjectManifest:
        for project in self.load_projects():
            if project.project_id == project_id:
                return project
        raise KeyError(f"Unknown project: {project_id}")

    def get_workspace_projects(self, workspace_id: str) -> list[ProjectManifest]:
        return [project for project in self.load_projects() if project.workspace_id == workspace_id]

    def create_project(self, workspace_id: str, payload: ProjectCreateRequest) -> ProjectManifest:
        self.get_workspace(workspace_id)
        existing = self.load_projects()
        if any(project.project_id == payload.project_id for project in existing):
            raise ValueError(f"Project already exists: {payload.project_id}")
        project = ProjectManifest.model_validate(
            {
                "workspace_id": workspace_id,
                **payload.model_dump(mode="json"),
            }
        )
        save_json(self._projects_path, [*load_json(self._projects_path), project.model_dump(mode="json")])
        return project

    def patch_project(self, project_id: str, payload: ProjectPatchRequest) -> ProjectManifest:
        projects = load_json(self._projects_path)
        updated: ProjectManifest | None = None
        for index, item in enumerate(projects):
            if item["project_id"] != project_id:
                continue
            merged = {**item, **payload.model_dump(exclude_none=True, mode="json")}
            updated = ProjectManifest.model_validate(merged)
            projects[index] = updated.model_dump(mode="json")
            break
        if updated is None:
            raise KeyError(f"Unknown project: {project_id}")
        save_json(self._projects_path, projects)
        return updated

    def delete_project(self, project_id: str) -> ProjectManifest:
        projects = load_json(self._projects_path)
        removed: ProjectManifest | None = None
        retained: list[dict[str, Any]] = []
        for item in projects:
            if item["project_id"] == project_id:
                removed = ProjectManifest.model_validate(item)
                continue
            retained.append(item)
        if removed is None:
            raise KeyError(f"Unknown project: {project_id}")
        save_json(self._projects_path, retained)
        return removed

    def create_server(self, payload: ServerCreateRequest) -> ServerManifest:
        existing = self.load_servers()
        if any(server.server_id == payload.server_id for server in existing):
            raise ValueError(f"Server already exists: {payload.server_id}")
        server = ServerManifest.model_validate(payload.model_dump(mode="json"))
        save_json(self._servers_path, [*load_json(self._servers_path), server.model_dump(mode="json")])
        return server

    def patch_server(self, server_id: str, payload: ServerPatchRequest) -> ServerManifest:
        servers = load_json(self._servers_path)
        updated: ServerManifest | None = None
        for index, item in enumerate(servers):
            if item["server_id"] != server_id:
                continue
            merged = {**item, **payload.model_dump(exclude_none=True, mode="json")}
            updated = ServerManifest.model_validate(merged)
            servers[index] = updated.model_dump(mode="json")
            break
        if updated is None:
            raise KeyError(f"Unknown server: {server_id}")
        save_json(self._servers_path, servers)
        return updated

    def delete_server(self, server_id: str) -> ServerManifest:
        servers = load_json(self._servers_path)
        removed: ServerManifest | None = None
        retained: list[dict[str, Any]] = []
        for item in servers:
            if item["server_id"] == server_id:
                removed = ServerManifest.model_validate(item)
                continue
            retained.append(item)
        if removed is None:
            raise KeyError(f"Unknown server: {server_id}")
        save_json(self._servers_path, retained)
        return removed
