"""CLI entrypoints for Switchboard."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import typer

from .collectors import CollectionCoordinator
from .config import ROOT_DIR, get_settings
from .manifests import ManifestStore
from .models import CollectRequest
from .node import install_node, snapshot_node, upgrade_node, verify_node_update
from .node_api import create_node_app
from .node_runtime import node_status, start_node_runtime, stop_node_runtime, runtime_paths
from .storage import SnapshotStore


app = typer.Typer(help="Switchboard control-center commands.")
node_app = typer.Typer(help="Switchboard node-mode commands.")
release_app = typer.Typer(help="Build releasable Switchboard artifacts.")
app.add_typer(node_app, name="node")
app.add_typer(release_app, name="release")


def _runtime_passwords(pairs: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in pairs:
        if "=" not in item:
            continue
        server_id, password = item.split("=", 1)
        result[server_id] = password
    return result


def _run(command: list[str], cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


@app.command()
def seed_snapshots() -> None:
    settings = get_settings()
    manifests = ManifestStore(settings)
    snapshots = SnapshotStore(settings, manifests)
    seeded = snapshots.seed_flat_files()
    typer.echo(json.dumps(seeded, indent=2))


@app.command()
def collect(
    workspace_id: str,
    service: list[str] = typer.Option(None, "--service"),
    password: list[str] = typer.Option(None, "--password"),
) -> None:
    settings = get_settings()
    manifests = ManifestStore(settings)
    snapshots = SnapshotStore(settings, manifests)
    coordinator = CollectionCoordinator(settings, manifests, snapshots)
    payload = CollectRequest(
        service_ids=service or [],
        runtime_passwords=_runtime_passwords(password or []),
    )
    result = coordinator.collect_workspace(workspace_id, payload)
    typer.echo(json.dumps(result, indent=2))


@app.command()
def serve(
    host: str = "127.0.0.1",
    port: int = 8009,
    reload: bool = False,
) -> None:
    import uvicorn

    uvicorn.run("switchboard.api:app", host=host, port=port, reload=reload)


@app.command()
def scaffold(
    service_id: str,
    path: str,
    display_name: str | None = None,
) -> None:
    """Compatibility alias for node install."""
    result = install_node(path, service_id=service_id, display_name=display_name)
    typer.echo(json.dumps(result, indent=2))


@node_app.command("install")
def node_install(
    project_root: str = typer.Option(..., "--project-root"),
    service_id: str | None = typer.Option(None, "--service-id"),
    display_name: str | None = typer.Option(None, "--display-name"),
) -> None:
    result = install_node(project_root, service_id=service_id, display_name=display_name)
    typer.echo(json.dumps(result, indent=2))


@node_app.command("upgrade")
def node_upgrade(
    project_root: str = typer.Option(..., "--project-root"),
) -> None:
    result = upgrade_node(project_root)
    typer.echo(json.dumps(result, indent=2))


@node_app.command("snapshot")
def node_snapshot(
    project_root: str = typer.Option(..., "--project-root"),
) -> None:
    result = snapshot_node(project_root)
    typer.echo(json.dumps(result, indent=2))


@node_app.command("verify-update")
def node_verify_update(
    project_root: str = typer.Option(..., "--project-root"),
) -> None:
    result = verify_node_update(project_root)
    typer.echo(json.dumps(result, indent=2))
    if result.get("status") != "ok":
        raise typer.Exit(1)


@node_app.command("serve")
def node_serve(
    project_root: str = typer.Option(..., "--project-root"),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8010, "--port"),
) -> None:
    import uvicorn

    app_instance = create_node_app(project_root)
    uvicorn.run(app_instance, host=host, port=port)


@node_app.command("start")
def node_start(
    project_root: str = typer.Option(..., "--project-root"),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8010, "--port"),
) -> None:
    result = start_node_runtime(project_root, host=host, port=port)
    typer.echo(json.dumps(result, indent=2))


@node_app.command("stop")
def node_stop(
    project_root: str = typer.Option(..., "--project-root"),
    port: int = typer.Option(8010, "--port"),
) -> None:
    result = stop_node_runtime(project_root, port=port)
    typer.echo(json.dumps(result, indent=2))


@node_app.command("status")
def node_runtime_status(
    project_root: str = typer.Option(..., "--project-root"),
    port: int = typer.Option(8010, "--port"),
) -> None:
    result = node_status(project_root, port=port)
    typer.echo(json.dumps(result, indent=2))


@node_app.command("logs")
def node_logs(
    project_root: str = typer.Option(..., "--project-root"),
    lines: int = typer.Option(40, "--lines"),
) -> None:
    log_file = runtime_paths(project_root)["log"]
    if not log_file.exists():
        typer.echo("")
        return
    text = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    tail = "\n".join(text[-lines:])
    typer.echo(tail)


@release_app.command("build")
def release_build(
    wheel_out: str = typer.Option("release", "--wheel-out"),
) -> None:
    """
    Build the frontend, bundle static assets into the Python package, and build a wheel.
    """
    root = ROOT_DIR
    dist_dir = root / "dist"
    static_app_dir = root / "switchboard" / "static" / "app"
    wheel_dir = root / wheel_out

    _run(["npm", "run", "build"], root)

    if static_app_dir.exists():
        shutil.rmtree(static_app_dir)
    static_app_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(dist_dir, static_app_dir)

    wheel_dir.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "uv",
            "build",
            "--wheel",
            "--no-build-isolation",
            "--offline",
            "--python",
            sys.executable,
            "--out-dir",
            str(wheel_dir),
        ],
        root,
    )
    typer.echo(str(wheel_dir))


if __name__ == "__main__":
    app()
