"""Pydantic models for manifests and requests."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


FavoriteTier = Literal["primary", "secondary", "none"]
OwnershipTier = Literal["owned", "shared", "infra"]
ConnectionType = Literal["local", "ssh"]
ScopeKind = Literal["repo", "doc", "log", "exclude"]
ScopePathType = Literal["file", "dir", "glob"]
ScopeSource = Literal["seeded", "user_added", "node_manifest", "tasks_completed"]
PushMode = Literal["allowed", "blocked"]
SafetyProfile = Literal["generic_python", "secret_heavy"]
MonitoringMode = Literal["manual", "detect", "node_managed"]
ActionStatus = Literal[
    "ok",
    "partial",
    "auth_failed",
    "unreachable",
    "vpn_or_network_blocked",
    "command_missing",
    "path_missing",
    "not_git_repo",
    "dirty_repo",
    "permission_limited",
    "skipped_by_exclude",
    "unverified",
]


class ServerManifest(BaseModel):
    server_id: str
    name: str
    connection_type: ConnectionType
    host: str
    username: str
    port: int = 22
    tags: list[str] = Field(default_factory=list)
    favorite_tier: FavoriteTier = "none"
    notes: str = ""


class ResolvedServer(ServerManifest):
    password: str | None = None


class RuntimeConfig(BaseModel):
    expected_ports: list[int] = Field(default_factory=list)
    healthcheck_command: str = ""
    run_command_hint: str = ""
    monitoring_mode: MonitoringMode = "manual"
    notes: str = ""

    @field_validator("expected_ports")
    @classmethod
    def validate_expected_ports(cls, value: list[int]) -> list[int]:
        deduped: list[int] = []
        for port in value:
            if port < 1 or port > 65535:
                raise ValueError("expected_ports entries must be between 1 and 65535")
            if port not in deduped:
                deduped.append(port)
        return deduped


class LocationSpec(BaseModel):
    location_id: str
    server_id: str
    access_mode: ConnectionType
    root: str
    role: str
    is_primary: bool = False
    path_aliases: list[str] = Field(default_factory=list)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)


class ScopeEntry(BaseModel):
    entry_id: str | None = None
    kind: ScopeKind
    path: str
    path_type: ScopePathType
    source: ScopeSource = "user_added"
    enabled: bool = True

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("path must not be empty")
        return trimmed


class RepoPolicy(BaseModel):
    repo_path: str
    push_mode: PushMode = "allowed"
    safety_profile: SafetyProfile = "generic_python"
    allowed_branches: list[str] = Field(default_factory=list)
    allowed_remotes: list[str] = Field(default_factory=list)

    @field_validator("repo_path")
    @classmethod
    def validate_repo_path(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("repo_path must not be empty")
        return trimmed


class ServiceManifest(BaseModel):
    service_id: str
    workspace_id: str
    display_name: str
    kind: str = "service"
    ownership_tier: OwnershipTier = "owned"
    tags: list[str] = Field(default_factory=list)
    favorite_tier: FavoriteTier = "none"
    locations: list[LocationSpec] = Field(default_factory=list)
    repo_paths: list[str] = Field(default_factory=list)
    docs_paths: list[str] = Field(default_factory=list)
    log_paths: list[str] = Field(default_factory=list)
    allowed_git_pull_paths: list[str] = Field(default_factory=list)
    exclude_globs: list[str] = Field(default_factory=list)
    scope_entries: list[ScopeEntry] = Field(default_factory=list)
    repo_policies: list[RepoPolicy] = Field(default_factory=list)
    notes: str = ""
    path_aliases: list[str] = Field(default_factory=list)


class WorkspaceManifest(BaseModel):
    workspace_id: str
    name: str
    tags: list[str] = Field(default_factory=list)
    favorite_tier: FavoriteTier = "none"
    servers: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    notes: str = ""


class CollectRequest(BaseModel):
    runtime_passwords: dict[str, str] = Field(default_factory=dict)
    service_ids: list[str] = Field(default_factory=list)

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):  # type: ignore[override]
        if isinstance(obj, dict):
            obj = {
                **obj,
                "runtime_passwords": obj.get("runtime_passwords", obj.get("password_overrides", {})),
                "service_ids": obj.get("service_ids", obj.get("service_filter", [])),
            }
        return super().model_validate(obj, *args, **kwargs)


class ServiceCreateRequest(BaseModel):
    service_id: str
    display_name: str
    kind: str = "service"
    ownership_tier: OwnershipTier = "owned"
    tags: list[str] = Field(default_factory=list)
    favorite_tier: FavoriteTier = "none"
    locations: list[LocationSpec] = Field(default_factory=list)
    repo_paths: list[str] = Field(default_factory=list)
    docs_paths: list[str] = Field(default_factory=list)
    log_paths: list[str] = Field(default_factory=list)
    allowed_git_pull_paths: list[str] = Field(default_factory=list)
    exclude_globs: list[str] = Field(default_factory=list)
    scope_entries: list[ScopeEntry] = Field(default_factory=list)
    repo_policies: list[RepoPolicy] = Field(default_factory=list)
    notes: str = ""
    path_aliases: list[str] = Field(default_factory=list)


class ServicePatchRequest(BaseModel):
    display_name: str | None = None
    kind: str | None = None
    ownership_tier: OwnershipTier | None = None
    tags: list[str] | None = None
    favorite_tier: FavoriteTier | None = None
    locations: list[LocationSpec] | None = None
    repo_paths: list[str] | None = None
    docs_paths: list[str] | None = None
    log_paths: list[str] | None = None
    allowed_git_pull_paths: list[str] | None = None
    exclude_globs: list[str] | None = None
    scope_entries: list[ScopeEntry] | None = None
    repo_policies: list[RepoPolicy] | None = None
    notes: str | None = None
    path_aliases: list[str] | None = None


class DownloadRequest(BaseModel):
    server_id: str | None = None
    kind: Literal["doc", "log"]
    files: list[str] = Field(default_factory=list)
    runtime_password: str | None = None


class GitPullRequest(BaseModel):
    repo_path: str = Field(min_length=1)
    server_id: str | None = None
    runtime_password: str | None = None

    @field_validator("repo_path")
    @classmethod
    def validate_repo_path(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("repo_path must not be empty")
        return trimmed


class RepoActionRequest(BaseModel):
    repo_path: str = Field(min_length=1)
    server_id: str | None = None
    runtime_password: str | None = None

    @field_validator("repo_path")
    @classmethod
    def validate_repo_path(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("repo_path must not be empty")
        return trimmed


class GitPushRequest(RepoActionRequest):
    remote: str | None = None
    branch: str | None = None


class ScanRootRequest(BaseModel):
    server_id: str
    root: str
    runtime_password: str | None = None
    max_depth: int = Field(default=2, ge=0, le=4)

    @field_validator("root")
    @classmethod
    def validate_root(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("root must not be empty")
        return trimmed


class DiscoveryTreeRequest(BaseModel):
    server_id: str
    root: str
    node_path: str | None = None
    runtime_password: str | None = None

    @field_validator("root")
    @classmethod
    def validate_root(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("root must not be empty")
        return trimmed

    @field_validator("node_path")
    @classmethod
    def validate_node_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        return trimmed


class PullBundleRequest(BaseModel):
    server_id: str | None = None
    runtime_password: str | None = None
    extra_includes: list[ScopeEntry] = Field(default_factory=list)
    extra_excludes: list[str] = Field(default_factory=list)


class RuntimeActionRequest(BaseModel):
    location_id: str | None = None
    runtime_password: str | None = None


class NodeSyncRequest(BaseModel):
    location_id: str | None = None
    runtime_password: str | None = None
    include_scope_snapshot: bool = True
    include_runtime_config: bool = True


class SecretPathQuery(BaseModel):
    service_id: str
