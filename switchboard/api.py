"""FastAPI application."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from . import __version__
from .collectors import CollectionCoordinator
from .config import get_settings
from .manifests import ManifestStore
from .models import (
    ActionLockRequest,
    CollectRequest,
    DiscoveryTreeRequest,
    DownloadRequest,
    GitPullRequest,
    GitPushRequest,
    NodeSyncRequest,
    ProjectCreateRequest,
    ProjectPatchRequest,
    PullBundleRequest,
    RepoActionRequest,
    RuntimeActionRequest,
    ScanRootRequest,
    ServerCreateRequest,
    ServerPatchRequest,
    ServiceCreateRequest,
    ServicePatchRequest,
)
from .storage import SnapshotStore


settings = get_settings()
manifest_store = ManifestStore(settings)
snapshot_store = SnapshotStore(settings, manifest_store)
coordinator = CollectionCoordinator(settings, manifest_store, snapshot_store)

app = FastAPI(title="Switchboard", version=__version__)


def _normalize_latest_snapshot(snapshot: dict[str, object]) -> dict[str, object]:
    normalized = dict(snapshot)
    normalized.setdefault("servers", [])
    normalized.setdefault("services", [])
    normalized.setdefault("repo_inventory", [])
    normalized.setdefault("docs_index", [])
    normalized.setdefault("logs_index", [])
    summary = normalized.setdefault("summary", {})
    if isinstance(summary, dict):
        summary.setdefault("status", "unverified")
        summary.setdefault("server_count", len(normalized["servers"]))
        summary.setdefault("service_count", len(normalized["services"]))
    return normalized


def _enrich_service_payload(payload: dict[str, object]) -> dict[str, object]:
    enriched = dict(payload)
    service_id = str(enriched.get("service_id") or "")
    if not service_id:
        return enriched
    runtime_state = snapshot_store.get_service_runtime_state(service_id)
    enriched["runtime_checks"] = runtime_state["runtime_checks"]
    enriched["node_sync"] = runtime_state["node_sync"]
    
    task_ledger = snapshot_store.get_service_task_ledger(service_id)
    enriched["task_ledger"] = task_ledger.get("tasks", [])
    return enriched


def _enrich_latest_snapshot(snapshot: dict[str, object]) -> dict[str, object]:
    normalized = _normalize_latest_snapshot(snapshot)
    services = []
    for service in normalized.get("services", []):
        if isinstance(service, dict):
            services.append(_enrich_service_payload(service))
        else:
            services.append(service)
    normalized["services"] = services
    return normalized


def _raise_for_action_result(result: dict[str, object]) -> None:
    status = result.get("status")
    message = str(result.get("message") or result.get("output") or "Request failed.")
    if status == "permission_limited":
        raise HTTPException(status_code=403, detail={"status": status, "message": message})
    if status == "path_missing":
        raise HTTPException(status_code=422, detail={"status": status, "message": message})


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "version": __version__,
        "timestamp": __import__("datetime").datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "framework": "switchboard",
        "vpn_note": "If VPN is needed for a server, turn it on manually. Switchboard does not store VPN state.",
    }


@app.get("/api/workspaces")
def list_workspaces() -> dict[str, object]:
    workspaces = manifest_store.load_workspaces()
    services = manifest_store.load_services()
    return {
        "workspaces": [
            {
                **workspace.model_dump(mode="json"),
                "server_count": len(workspace.servers),
                "service_count": len([service for service in services if service.workspace_id == workspace.workspace_id]),
            }
            for workspace in workspaces
        ]
    }


@app.get("/api/servers")
def list_servers() -> dict[str, object]:
    return {"servers": [server.model_dump(mode="json") for server in manifest_store.load_servers()]}


@app.get("/api/workspaces/{workspace_id}")
def get_workspace(workspace_id: str) -> dict[str, object]:
    try:
        workspace = manifest_store.get_workspace(workspace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    services = manifest_store.get_workspace_services(workspace_id)
    return {
        "workspace": workspace.model_dump(mode="json"),
        "services": [_enrich_service_payload(service.model_dump(mode="json")) for service in services],
    }


@app.get("/api/workspaces/{workspace_id}/latest")
def get_workspace_latest(workspace_id: str) -> dict[str, object]:
    latest = snapshot_store.get_workspace_latest(workspace_id)
    if latest is None:
        try:
            workspace = manifest_store.get_workspace(workspace_id)
            services = manifest_store.get_workspace_services(workspace_id)
            servers = [
                manifest_store.get_server(server_id).model_dump(mode="json")
                for server_id in workspace.servers
            ]
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "generated": None,
            "workspace": workspace.model_dump(mode="json"),
            "servers": [
                {
                    **server,
                    "status": "unverified",
                    "hostname": server.get("host"),
                    "services": [],
                    "docker": [],
                    "firewall": "unverified",
                    "ports": [],
                }
                for server in servers
            ],
            "services": [_enrich_service_payload(service.model_dump(mode="json")) for service in services],
            "repo_inventory": [],
            "docs_index": [],
            "logs_index": [],
            "summary": {
                "status": "unverified",
                "server_count": len(workspace.servers),
                "service_count": len(services),
            },
        }
    return _enrich_latest_snapshot(latest)


@app.get("/api/workspaces/{workspace_id}/runs")
def get_workspace_runs(workspace_id: str) -> dict[str, object]:
    return {"workspace_id": workspace_id, "runs": snapshot_store.get_workspace_runs(workspace_id)}


@app.get("/api/services/{service_id}")
def get_service(service_id: str) -> dict[str, object]:
    try:
        service = manifest_store.get_service(service_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"service": _enrich_service_payload(service.model_dump(mode="json"))}


@app.get("/api/services/{service_id}/scope")
def get_service_scope(service_id: str) -> dict[str, object]:
    try:
        service = manifest_store.get_service(service_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "service_id": service_id,
        "scope_entries": [entry.model_dump(mode="json") for entry in service.scope_entries],
        "repo_policies": [policy.model_dump(mode="json") for policy in service.repo_policies],
    }


@app.post("/api/discovery/scan-root")
def scan_root(request: ScanRootRequest) -> dict[str, object]:
    return coordinator.scan_root(request)


@app.post("/api/discovery/tree")
def browse_tree(request: DiscoveryTreeRequest) -> dict[str, object]:
    return coordinator.browse_tree(request)


@app.post("/api/workspaces/{workspace_id}/collect")
def collect_workspace(workspace_id: str, request: CollectRequest) -> dict[str, object]:
    try:
        return coordinator.collect_workspace(workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/workspaces/{workspace_id}/services")
def create_service(workspace_id: str, request: ServiceCreateRequest) -> dict[str, object]:
    try:
        service = manifest_store.create_service(workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"service": _enrich_service_payload(service.model_dump(mode="json"))}


@app.patch("/api/services/{service_id}")
def patch_service(service_id: str, request: ServicePatchRequest) -> dict[str, object]:
    try:
        service = manifest_store.patch_service(service_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"service": _enrich_service_payload(service.model_dump(mode="json"))}


@app.delete("/api/services/{service_id}")
def delete_service(service_id: str) -> dict[str, object]:
    try:
        service = manifest_store.delete_service(service_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return snapshot_store.delete_service_data(service_id, service.workspace_id)


@app.post("/api/services/{service_id}/downloads")
def download_files(service_id: str, request: DownloadRequest) -> dict[str, object]:
    try:
        return coordinator.download_files(service_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/services/{service_id}/actions/git-status")
def git_status(service_id: str, request: RepoActionRequest) -> dict[str, object]:
    try:
        return coordinator.git_status(service_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/services/{service_id}/actions/safety-check")
def safety_check(service_id: str, request: RepoActionRequest) -> dict[str, object]:
    try:
        return coordinator.safety_check(service_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/services/{service_id}/actions/git-pull")
def git_pull(service_id: str, request: GitPullRequest) -> dict[str, object]:
    try:
        result = coordinator.git_pull(service_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _raise_for_action_result(result)
    return result


@app.post("/api/services/{service_id}/actions/git-push")
def git_push(service_id: str, request: GitPushRequest) -> dict[str, object]:
    try:
        result = coordinator.git_push(service_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _raise_for_action_result(result)
    return result


@app.post("/api/services/{service_id}/actions/runtime-check")
def runtime_check(service_id: str, request: RuntimeActionRequest) -> dict[str, object]:
    try:
        result = coordinator.runtime_check(service_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _raise_for_action_result(result)
    return result


@app.post("/api/services/{service_id}/actions/sync-from-node")
def sync_from_node(service_id: str, request: NodeSyncRequest) -> dict[str, object]:
    try:
        result = coordinator.sync_from_node(service_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _raise_for_action_result(result)
    if isinstance(result.get("service"), dict):
        result = {**result, "service": _enrich_service_payload(result["service"])}
    return result


@app.post("/api/services/{service_id}/actions/sync-to-node")
def sync_to_node(service_id: str, request: NodeSyncRequest) -> dict[str, object]:
    try:
        result = coordinator.sync_to_node(service_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _raise_for_action_result(result)
    return result


@app.get("/api/services/{service_id}/pull-bundles")
def list_pull_bundles(service_id: str) -> dict[str, object]:
    try:
        manifest_store.get_service(service_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"service_id": service_id, "bundles": snapshot_store.list_pull_bundles(service_id)}


@app.post("/api/services/{service_id}/pull-bundles")
def create_pull_bundle(service_id: str, request: PullBundleRequest) -> dict[str, object]:
    try:
        result = coordinator.pull_bundle(service_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _raise_for_action_result(result)
    return result


@app.get("/api/services/{service_id}/secret-paths")
def get_secret_paths(service_id: str) -> dict[str, object]:
    try:
        manifest_store.get_service(service_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return snapshot_store.get_service_secret_paths(service_id)


@app.get("/api/servers")
def list_servers() -> dict[str, object]:
    return {"servers": [s.model_dump(mode="json") for s in manifest_store.load_servers()]}

@app.get("/api/services/{service_id}/task-ledger")
def get_service_task_ledger(service_id: str) -> dict[str, object]:
    ledger = snapshot_store.get_service_task_ledger(service_id)
    return {"tasks": ledger.get("tasks", [])}


@app.get("/api/services/{service_id}/action-locks")
def get_service_action_locks(service_id: str) -> dict[str, object]:
    cache = snapshot_store._read_runtime_cache()
    locks = snapshot_store._prune_expired_locks(cache).get("action_locks", {})
    return {"locks": [lock for key, lock in locks.items() if lock.get("service_id") == service_id]}


@app.post("/api/services/{service_id}/action-locks")
def acquire_service_action_lock(service_id: str, request: ActionLockRequest) -> dict[str, object]:
    lock = snapshot_store.acquire_action_lock(request.action_key, service_id)
    if lock is None:
        raise HTTPException(status_code=409, detail="Lock already active")
    return {"status": "ok", "lock": lock}


@app.delete("/api/services/{service_id}/action-locks/{action_key}")
def release_service_action_lock(service_id: str, action_key: str) -> dict[str, object]:
    lock = snapshot_store.release_action_lock(action_key, service_id)
    return {"status": "ok", "lock": lock}


@app.post("/api/workspaces/{workspace_id}/health-check")
def workspace_health_check(workspace_id: str, runtime_passwords: dict[str, str] | None = None) -> dict[str, object]:
    return coordinator.workspace_health_check(workspace_id, runtime_passwords)


@app.get("/api/workspaces/{workspace_id}/projects")
def list_workspace_projects(workspace_id: str) -> dict[str, object]:
    projects = manifest_store.get_workspace_projects(workspace_id)
    return {"projects": [p.model_dump(mode="json") for p in projects]}


@app.post("/api/workspaces/{workspace_id}/projects")
def create_project(workspace_id: str, request: ProjectCreateRequest) -> dict[str, object]:
    try:
        project = manifest_store.create_project(workspace_id, request)
        return {"status": "ok", "project": project.model_dump(mode="json")}
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.patch("/api/projects/{project_id}")
def patch_project(project_id: str, request: ProjectPatchRequest) -> dict[str, object]:
    try:
        project = manifest_store.patch_project(project_id, request)
        return {"status": "ok", "project": project.model_dump(mode="json")}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str) -> dict[str, object]:
    try:
        project = manifest_store.delete_project(project_id)
        return {"status": "ok", "project": project.model_dump(mode="json")}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/servers")
def create_server(request: ServerCreateRequest) -> dict[str, object]:
    try:
        server = manifest_store.create_server(request)
        return {"status": "ok", "server": server.model_dump(mode="json")}
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.patch("/api/servers/{server_id}")
def patch_server(server_id: str, request: ServerPatchRequest) -> dict[str, object]:
    try:
        server = manifest_store.patch_server(server_id, request)
        return {"status": "ok", "server": server.model_dump(mode="json")}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/servers/{server_id}")
def delete_server(server_id: str) -> dict[str, object]:
    try:
        server = manifest_store.delete_server(server_id)
        return {"status": "ok", "server": server.model_dump(mode="json")}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
