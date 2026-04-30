"""Node runtime process helpers."""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

from .node import NODE_DIR_NAME, load_node_manifest


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


def _manifest_runtime_port(project_root: Path) -> int | None:
    try:
        value = load_node_manifest(project_root).get("runtime_port")
    except (FileNotFoundError, ValueError):
        return None
    try:
        port = int(value)
    except (TypeError, ValueError):
        return None
    return port if port > 0 else None


def _extract_port_from_command(command: str) -> int | None:
    match = re.search(r"--port(?:=|\s+)(\d+)\b", command)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _node_process_for_project(project_root: Path) -> dict[str, Any] | None:
    root_token = str(project_root.resolve())
    commands = (
        ["ps", "-eo", "pid=,args="],
        ["ps", "ax", "-o", "pid=,command="],
    )
    output = ""
    for command in commands:
        try:
            output = subprocess.run(command, check=False, capture_output=True, text=True).stdout
        except FileNotFoundError:
            continue
        if output:
            break
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        pid_text, _, command_text = stripped.partition(" ")
        if not pid_text.isdigit():
            continue
        if "switchboard" not in command_text or "node" not in command_text or "serve" not in command_text:
            continue
        if root_token not in command_text:
            continue
        return {
            "pid": int(pid_text),
            "port": _extract_port_from_command(command_text),
            "command": command_text,
        }
    return None


def _cleanup_stale_pid(pid_file: Path) -> None:
    pid = _read_pid(pid_file)
    if pid and not _pid_running(pid):
        pid_file.unlink(missing_ok=True)


def node_status(project_root: str | Path, port: int | None = None) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    paths = runtime_paths(project_root)
    paths["runtime"].mkdir(parents=True, exist_ok=True)
    _cleanup_stale_pid(paths["pid"])
    detected_process = _node_process_for_project(project_root)
    detected_pid = detected_process.get("pid") if detected_process else None
    detected_port = detected_process.get("port") if detected_process else None
    port = port or detected_port or _manifest_runtime_port(project_root)
    pid = _read_pid(paths["pid"])
    if not _pid_running(pid) and _pid_running(detected_pid):
        pid = detected_pid
    port_pid = _port_listener_pid(port) if port else None
    status = "running" if _pid_running(pid) else "stopped"
    if status == "stopped" and port_pid:
        status = "running_unmanaged"
    return {
        "project_root": str(project_root),
        "runtime_dir": str(paths["runtime"]),
        "pid_file": str(paths["pid"]),
        "log_file": str(paths["log"]),
        "pid": pid,
        "port": port,
        "port_pid": port_pid,
        "detected_process_pid": detected_pid,
        "detected_process_port": detected_port,
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
