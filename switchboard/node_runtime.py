"""Node runtime process helpers."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

from .node import NODE_DIR_NAME


def runtime_paths(project_root: str | Path) -> dict[str, Path]:
    root = Path(project_root).resolve() / NODE_DIR_NAME / "runtime"
    return {
        "runtime": root,
        "pid": root / "node.pid",
        "log": root / "node.log",
    }


def _read_pid(path: Path) -> int | None:
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _pid_running(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _port_listener_pid(port: int) -> int | None:
    try:
        output = subprocess.run(
            ["lsof", "-tiTCP:%s" % port, "-sTCP:LISTEN"],
            check=False,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except FileNotFoundError:
        return None
    if not output:
        return None
    first = output.splitlines()[0].strip()
    try:
        return int(first)
    except ValueError:
        return None


def _cleanup_stale_pid(pid_file: Path) -> None:
    pid = _read_pid(pid_file)
    if pid and not _pid_running(pid):
        pid_file.unlink(missing_ok=True)


def node_status(project_root: str | Path, port: int | None = None) -> dict[str, Any]:
    paths = runtime_paths(project_root)
    paths["runtime"].mkdir(parents=True, exist_ok=True)
    _cleanup_stale_pid(paths["pid"])
    pid = _read_pid(paths["pid"])
    port_pid = _port_listener_pid(port) if port else None
    status = "running" if _pid_running(pid) else "stopped"
    if status == "stopped" and port_pid:
        status = "running_unmanaged"
    return {
        "project_root": str(Path(project_root).resolve()),
        "runtime_dir": str(paths["runtime"]),
        "pid_file": str(paths["pid"]),
        "log_file": str(paths["log"]),
        "pid": pid,
        "port": port,
        "port_pid": port_pid,
        "status": status,
    }


def start_node_runtime(project_root: str | Path, host: str = "127.0.0.1", port: int = 8010) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    paths = runtime_paths(project_root)
    paths["runtime"].mkdir(parents=True, exist_ok=True)
    _cleanup_stale_pid(paths["pid"])

    status = node_status(project_root, port=port)
    if status["status"] == "running":
        return {**status, "message": "Node already running."}
    if status["status"] == "running_unmanaged":
        return {**status, "message": f"Port {port} is already in use by pid {status['port_pid']}."}

    with paths["log"].open("ab") as log_handle:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "switchboard.cli",
                "node",
                "serve",
                "--project-root",
                str(project_root),
                "--host",
                host,
                "--port",
                str(port),
            ],
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            cwd=project_root,
            start_new_session=True,
            env=os.environ.copy(),
        )
    paths["pid"].write_text(f"{process.pid}\n", encoding="utf-8")
    return {
        **node_status(project_root, port=port),
        "message": f"Started node on http://{host}:{port}",
        "host": host,
    }


def stop_node_runtime(project_root: str | Path, port: int | None = None) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    paths = runtime_paths(project_root)
    status = node_status(project_root, port=port)
    stopped: list[int] = []

    pid = status.get("pid")
    if pid and _pid_running(pid):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
        stopped.append(pid)

    port_pid = status.get("port_pid")
    if port_pid and port_pid not in stopped:
        try:
            os.kill(port_pid, signal.SIGTERM)
        except OSError:
            pass
        stopped.append(port_pid)

    paths["pid"].unlink(missing_ok=True)
    return {
        **node_status(project_root, port=port),
        "stopped_pids": stopped,
        "message": "Stopped node." if stopped else "Node was not running.",
    }
