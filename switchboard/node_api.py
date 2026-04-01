"""FastAPI app for node mode."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .node import list_node_files, load_node_manifest, resolve_static_app_dir, snapshot_node


def create_node_app(project_root: str | Path) -> FastAPI:
    project_root = Path(project_root).resolve()
    app = FastAPI(title="Switchboard Node", version=__version__)
    static_dir = resolve_static_app_dir()
    assets_dir = static_dir / "assets" if static_dir else None

    @app.get("/api/health")
    def health() -> dict[str, object]:
        manifest = load_node_manifest(project_root) if (project_root / "switchboard" / "node.manifest.json").exists() else snapshot_node(project_root)["manifest"]
        return {
            "status": "ok",
            "mode": "node",
            "version": __version__,
            "service_id": manifest["service_id"],
            "project_root": str(project_root),
        }

    @app.get("/api/node")
    def node_info() -> dict[str, object]:
        snapshot = snapshot_node(project_root)
        return {
            "manifest": snapshot["manifest"],
            "scope_snapshot": snapshot["scope_snapshot"],
            "files": list_node_files(project_root),
        }

    @app.post("/api/node/snapshot")
    def refresh_snapshot() -> dict[str, object]:
        return snapshot_node(project_root)

    if assets_dir and assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    if static_dir and (static_dir / "index.html").exists():

        @app.get("/", include_in_schema=False)
        def root() -> FileResponse:
            return FileResponse(static_dir / "index.html")

        @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
        def spa(full_path: str):
            if full_path.startswith("api/"):
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            candidate = static_dir / full_path
            if candidate.exists() and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(static_dir / "index.html")

    return app
