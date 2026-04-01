"""FastAPI application."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .collectors import CollectionCoordinator
from .config import get_settings
from .manifests import ManifestStore
from .models import (
    CollectRequest,
    DiscoveryTreeRequest,
    DownloadRequest,
    GitPullRequest,
    GitPushRequest,
    PullBundleRequest,
    RepoActionRequest,
    ScanRootRequest,
    ServiceCreateRequest,
    ServicePatchRequest,
)
from .storage import SnapshotStore


settings = get_settings()
manifest_store = ManifestStore(settings)
snapshot_store = SnapshotStore(settings, manifest_store)
coordinator = CollectionCoordinator(settings, manifest_store, snapshot_store)

app = FastAPI(title="Switchboard", version="0.1.0")


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
        "version": "0.1.0",
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
        "services": [service.model_dump(mode="json") for service in services],
    }


@app.get("/api/workspaces/{workspace_id}/latest")
def get_workspace_latest(workspace_id: str) -> dict[str, object]:
    latest = snapshot_store.get_workspace_latest(workspace_id)
    if latest is None:
        try:
            workspace = manifest_store.get_workspace(workspace_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "generated": None,
            "workspace": workspace.model_dump(mode="json"),
            "servers": [],
            "services": [],
            "repo_inventory": [],
            "docs_index": [],
            "logs_index": [],
            "summary": {"status": "unverified", "server_count": 0, "service_count": 0},
        }
    return _normalize_latest_snapshot(latest)


@app.get("/api/workspaces/{workspace_id}/runs")
def get_workspace_runs(workspace_id: str) -> dict[str, object]:
    return {"workspace_id": workspace_id, "runs": snapshot_store.get_workspace_runs(workspace_id)}


@app.get("/api/services/{service_id}")
def get_service(service_id: str) -> dict[str, object]:
    try:
        service = manifest_store.get_service(service_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"service": service.model_dump(mode="json")}


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
    return {"service": service.model_dump(mode="json")}


@app.patch("/api/services/{service_id}")
def patch_service(service_id: str, request: ServicePatchRequest) -> dict[str, object]:
    try:
        service = manifest_store.patch_service(service_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"service": service.model_dump(mode="json")}


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
