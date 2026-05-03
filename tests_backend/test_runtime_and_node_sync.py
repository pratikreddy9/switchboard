import json
import socket
import subprocess
import sys
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from pydantic import ValidationError

from switchboard.collectors import CollectionCoordinator
from switchboard.config import Settings
from switchboard.manifests import ManifestStore, save_json
from switchboard.models import CollectRequest, NodeSyncRequest, RuntimeActionRequest, RuntimeConfig
from switchboard.node import init_manager_node, install_node, node_paths
from switchboard.node_runtime import manager_runtime_paths, manager_status, node_status, start_manager_runtime, stop_manager_runtime
from switchboard.storage import SnapshotStore


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_port(port: int, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for 127.0.0.1:{port}")


def _settings(root: Path) -> Settings:
    manifest_dir = root / "switchboard" / "manifests"
    evidence_dir = root / "docs" / "evidence"
    archive_dir = evidence_dir / "archive"
    private_state_dir = root / "state" / "private"
    downloads_dir = root / "downloads"
    return Settings(
        manifest_dir=manifest_dir,
        evidence_dir=evidence_dir,
        archive_dir=archive_dir,
        private_state_dir=private_state_dir,
        downloads_dir=downloads_dir,
    )


def _write_local_fixture(root: Path, project_root: Path, runtime: dict, scope_entries: list[dict]) -> tuple[ManifestStore, SnapshotStore, CollectionCoordinator]:
    settings = _settings(root)
    save_json(
        settings.manifest_dir / "servers.json",
        [
            {
                "server_id": "local_mac",
                "name": "Local Mac",
                "connection_type": "local",
                "host": "localhost",
                "username": "p",
                "port": 22,
                "tags": [],
            }
        ],
    )
    save_json(
        settings.manifest_dir / "workspaces.json",
        [
            {
                "workspace_id": "zapp",
                "name": "ZAPP",
                "tags": [],
                "favorite_tier": "primary",
                "servers": ["local_mac"],
                "services": ["svc"],
                "notes": "",
            }
        ],
    )
    save_json(
        settings.manifest_dir / "services.json",
        [
            {
                "service_id": "svc",
                "workspace_id": "zapp",
                "display_name": "Svc",
                "kind": "service",
                "ownership_tier": "owned",
                "tags": [],
                "favorite_tier": "primary",
                "locations": [
                    {
                        "location_id": "svc-local",
                        "server_id": "local_mac",
                        "access_mode": "local",
                        "root": str(project_root),
                        "role": "primary",
                        "is_primary": True,
                        "path_aliases": [],
                        "runtime": runtime,
                    }
                ],
                "scope_entries": scope_entries,
            }
        ],
    )
    manifests = ManifestStore(settings)
    snapshots = SnapshotStore(settings, manifests)
    coordinator = CollectionCoordinator(settings, manifests, snapshots)
    return manifests, snapshots, coordinator


class RuntimeAndNodeSyncTests(unittest.TestCase):
    def test_runtime_config_dedupes_ports_and_rejects_invalid_values(self) -> None:
        runtime = RuntimeConfig(expected_ports=[8000, 8000, 8500], monitoring_mode="detect")
        self.assertEqual(runtime.expected_ports, [8000, 8500])
        with self.assertRaises(ValidationError):
            RuntimeConfig(expected_ports=[0])

    def test_runtime_check_local_uses_runtime_config_and_preserves_manual_hint(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_root = root / "project"
            project_root.mkdir(parents=True)
            install_node(project_root, service_id="svc", display_name="Svc")

            port = _free_port()
            server = subprocess.Popen(
                [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
                cwd=project_root,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                _wait_for_port(port)
                manifests, snapshots, coordinator = _write_local_fixture(
                    root,
                    project_root,
                    runtime={
                        "expected_ports": [port],
                        "healthcheck_command": f"{sys.executable} -c \"import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:{port}').status)\"",
                        "run_command_hint": "python -m http.server",
                        "monitoring_mode": "detect",
                        "notes": "Local runtime check fixture",
                    },
                    scope_entries=[
                        {
                            "entry_id": "repo-1",
                            "kind": "repo",
                            "path": str(project_root),
                            "path_type": "dir",
                            "source": "user_added",
                            "enabled": True,
                        },
                        {
                            "entry_id": "doc-1",
                            "kind": "doc",
                            "path": str(project_root / "switchboard" / "node.manifest.json"),
                            "path_type": "file",
                            "source": "user_added",
                            "enabled": True,
                        },
                    ],
                )
                self.assertIsNotNone(manifests.get_service("svc"))
                with mock.patch.object(coordinator, "_lookup_process_command", return_value=""):
                    result = coordinator.runtime_check("svc", RuntimeActionRequest(location_id="svc-local"))

                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["configured_ports"], [port])
                self.assertIn(port, [entry["port"] for entry in result["detected_ports"]])
                self.assertEqual(result["healthcheck_status"], "ok")
                self.assertEqual(result["detected_process_command"], "")
                self.assertEqual(result["run_command_hint"], "python -m http.server")
                self.assertTrue(result["node_present"])
                runtime_state = snapshots.get_service_runtime_state("svc")
                self.assertEqual(runtime_state["runtime_checks"][0]["location_id"], "svc-local")
            finally:
                server.terminate()
                server.wait(timeout=5)

    def test_manager_runtime_start_status_and_stop_use_manager_runtime_files(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manager_root = root / "manager"
            port = _free_port()
            init_manager_node(manager_root, runtime_port=port)
            runtime = manager_runtime_paths(manager_root)

            started = start_manager_runtime(manager_root, port=port)
            try:
                _wait_for_port(port)
                status = manager_status(manager_root, port=port)

                self.assertEqual(started["status"], "running")
                self.assertEqual(status["status"], "running")
                self.assertEqual(Path(status["pid_file"]), runtime["pid"])
                self.assertEqual(Path(status["log_file"]), runtime["log"])
            finally:
                stopped = stop_manager_runtime(manager_root, port=port)

            self.assertIn(started["pid"], stopped["stopped_pids"])

    def test_node_status_marks_manager_owned_port_separately(self) -> None:
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir) / "project"
            install_node(project_root, service_id="svc", display_name="Svc")

            with (
                mock.patch("switchboard.node_runtime._port_listener_pid", return_value=12345),
                mock.patch("switchboard.node_runtime._process_command", return_value="python -m switchboard.cli node manager-serve --port 8010"),
            ):
                status = node_status(project_root, port=8010)

            self.assertEqual(status["status"], "stopped_manager_owned")

    def test_runtime_check_remote_mocked_ssh_uses_manual_hint_when_detection_missing(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            settings = _settings(root)
            save_json(
                settings.manifest_dir / "servers.json",
                [
                    {
                        "server_id": "ssh_box",
                        "name": "SSH Box",
                        "connection_type": "ssh",
                        "host": "10.0.0.5",
                        "username": "tester",
                        "port": 22,
                        "tags": [],
                    }
                ],
            )
            save_json(
                settings.manifest_dir / "workspaces.json",
                [
                    {
                        "workspace_id": "zapp",
                        "name": "ZAPP",
                        "tags": [],
                        "favorite_tier": "primary",
                        "servers": ["ssh_box"],
                        "services": ["svc"],
                        "notes": "",
                    }
                ],
            )
            save_json(
                settings.manifest_dir / "services.json",
                [
                    {
                        "service_id": "svc",
                        "workspace_id": "zapp",
                        "display_name": "Svc",
                        "locations": [
                            {
                                "location_id": "svc-ssh",
                                "server_id": "ssh_box",
                                "access_mode": "ssh",
                                "root": "/srv/app",
                                "role": "primary",
                                "is_primary": True,
                                "path_aliases": [],
                                "runtime": {
                                    "expected_ports": [9001],
                                    "healthcheck_command": "curl -fsS http://127.0.0.1:9001/health",
                                    "run_command_hint": "uvicorn app:app --port 9001",
                                    "monitoring_mode": "detect",
                                    "notes": "SSH runtime fixture",
                                },
                            }
                        ],
                        "scope_entries": [],
                    }
                ],
            )
            manifests = ManifestStore(settings)
            snapshots = SnapshotStore(settings, manifests)
            coordinator = CollectionCoordinator(settings, manifests, snapshots)

            @contextmanager
            def fake_open_ssh(_server):
                yield (object(), object())

            with (
                mock.patch.object(coordinator, "_open_ssh", side_effect=lambda server: fake_open_ssh(server)),
                mock.patch.object(
                    coordinator,
                    "_collect_remote_listener_details",
                    return_value=[{"port": 9001, "protocol": "tcp", "process": "", "pid": None, "state": "LISTEN"}],
                ),
                mock.patch.object(coordinator, "_remote_exists", return_value=True),
                mock.patch.object(coordinator, "_run_healthcheck_remote", return_value={"status": "ok", "output": "healthy"}),
                mock.patch.object(coordinator, "_lookup_process_command", return_value=""),
            ):
                result = coordinator.runtime_check("svc", RuntimeActionRequest(location_id="svc-ssh"))

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["detected_ports"][0]["port"], 9001)
            self.assertEqual(result["detected_process_command"], "")
            self.assertEqual(result["run_command_hint"], "uvicorn app:app --port 9001")
            self.assertTrue(result["node_present"])

    def test_sync_to_node_and_sync_from_node_round_trip_runtime_and_scope(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_root = root / "project"
            install_node(project_root, service_id="svc", display_name="Svc")
            paths = node_paths(project_root)

            manifests, snapshots, coordinator = _write_local_fixture(
                root,
                project_root,
                runtime={
                    "expected_ports": [8000],
                    "healthcheck_command": "curl -fsS http://127.0.0.1:8000/health",
                    "run_command_hint": "uvicorn main:app --port 8000",
                    "monitoring_mode": "manual",
                    "notes": "Control center runtime",
                },
                scope_entries=[
                    {
                        "entry_id": "repo-1",
                        "kind": "repo",
                        "path": str(project_root),
                        "path_type": "dir",
                        "source": "user_added",
                        "enabled": True,
                    },
                    {
                        "entry_id": "doc-1",
                        "kind": "doc",
                        "path": str(paths["manifest"]),
                        "path_type": "file",
                        "source": "user_added",
                        "enabled": True,
                    },
                    {
                        "entry_id": "exclude-1",
                        "kind": "exclude",
                        "path": "venv",
                        "path_type": "glob",
                        "source": "user_added",
                        "enabled": True,
                    },
                ],
            )

            pushed = coordinator.sync_to_node("svc", NodeSyncRequest(location_id="svc-local"))
            self.assertEqual(pushed["status"], "ok")

            node_manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            scope_snapshot = json.loads(paths["scope_snapshot"].read_text(encoding="utf-8"))
            self.assertEqual(node_manifest["runtime"]["expected_ports"], [8000])
            self.assertEqual(node_manifest["runtime"]["run_command_hint"], "uvicorn main:app --port 8000")
            self.assertEqual(scope_snapshot["scope_entries"][0]["kind"], "repo")
            self.assertTrue(any(entry["doc_id"] == "readme" for entry in node_manifest["managed_docs"]))

            node_manifest["runtime"] = {
                "expected_ports": [8100],
                "healthcheck_command": "curl -fsS http://127.0.0.1:8100/health",
                "run_command_hint": "python node_runner.py",
                "monitoring_mode": "node_managed",
                "notes": "Node override",
            }
            paths["manifest"].write_text(json.dumps(node_manifest, indent=2) + "\n", encoding="utf-8")
            paths["scope_snapshot"].write_text(
                json.dumps(
                    {
                        "generated": "2026-04-01T00:00:00+00:00",
                        "service_id": "svc",
                        "project_root": str(project_root),
                        "scope_entries": [
                            {
                                "kind": "doc",
                                "path_type": "file",
                                "path": str(paths["manifest"]),
                                "enabled": True,
                                "source": "tasks_completed",
                            },
                            {
                                "kind": "exclude",
                                "path_type": "glob",
                                "path": "venv",
                                "enabled": True,
                                "source": "tasks_completed",
                            },
                            {
                                "kind": "doc",
                                "path_type": "file",
                                "path": str(project_root / "legacy-handoff.md"),
                                "enabled": True,
                                "source": "manual_codex_handoff",
                            },
                            {
                                "kind": "code",
                                "path_type": "file",
                                "path": str(project_root / "app.py"),
                                "enabled": True,
                                "source": "tasks_completed",
                            },
                        ],
                        "scope_updates": [],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            pulled = coordinator.sync_from_node("svc", NodeSyncRequest(location_id="svc-local"))
            self.assertEqual(pulled["status"], "ok")
            self.assertEqual(pulled["service"]["locations"][0]["runtime"]["expected_ports"], [8100])
            self.assertEqual(pulled["service"]["locations"][0]["runtime"]["monitoring_mode"], "node_managed")
            self.assertTrue(any(entry["doc_id"] == "readme" for entry in pulled["service"]["managed_docs"]))

            stored_service = manifests.get_service("svc")
            self.assertIn(str(paths["manifest"]), stored_service.docs_paths)
            self.assertIn(str(project_root / "README.md"), stored_service.docs_paths)
            self.assertIn(str(project_root / "API.md"), stored_service.docs_paths)
            self.assertIn(str(project_root / "CHANGELOG.md"), stored_service.docs_paths)
            self.assertTrue(
                any(
                    entry.path == str(project_root / "legacy-handoff.md") and entry.source == "tasks_completed"
                    for entry in stored_service.scope_entries
                )
            )
            self.assertTrue(
                any(
                    entry.path == str(project_root / "app.py") and entry.kind == "code"
                    for entry in stored_service.scope_entries
                )
            )
            self.assertEqual(stored_service.exclude_globs, ["venv"])
            self.assertEqual(stored_service.allowed_git_pull_paths, [])
            sync_state = snapshots.get_service_runtime_state("svc")["node_sync"]
            self.assertEqual(sync_state[0]["direction"], "from_node")
            self.assertTrue(sync_state[0]["timestamp"])
            self.assertIn("doc_index", sync_state[0])

    def test_collect_with_service_filter_only_resolves_relevant_servers(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_root = root / "project"
            project_root.mkdir(parents=True)

            settings = _settings(root)
            save_json(
                settings.manifest_dir / "servers.json",
                [
                    {
                        "server_id": "local_mac",
                        "name": "Local Mac",
                        "connection_type": "local",
                        "host": "localhost",
                        "username": "p",
                        "port": 22,
                        "tags": [],
                    },
                    {
                        "server_id": "ssh_box",
                        "name": "SSH Box",
                        "connection_type": "ssh",
                        "host": "10.0.0.5",
                        "username": "tester",
                        "port": 22,
                        "tags": [],
                    },
                ],
            )
            save_json(
                settings.manifest_dir / "workspaces.json",
                [
                    {
                        "workspace_id": "zapp",
                        "name": "ZAPP",
                        "tags": [],
                        "favorite_tier": "primary",
                        "servers": ["local_mac", "ssh_box"],
                        "services": ["svc"],
                        "notes": "",
                    }
                ],
            )
            save_json(
                settings.manifest_dir / "services.json",
                [
                    {
                        "service_id": "svc",
                        "workspace_id": "zapp",
                        "display_name": "Svc",
                        "locations": [
                            {
                                "location_id": "svc-local",
                                "server_id": "local_mac",
                                "access_mode": "local",
                                "root": str(project_root),
                                "role": "primary",
                                "is_primary": True,
                                "path_aliases": [],
                            }
                        ],
                        "scope_entries": [],
                    }
                ],
            )

            manifests = ManifestStore(settings)
            snapshots = SnapshotStore(settings, manifests)
            coordinator = CollectionCoordinator(settings, manifests, snapshots)
            result = coordinator.collect_workspace("zapp", CollectRequest(service_ids=["svc"]))

            self.assertEqual([entry["server_id"] for entry in result["servers"]], ["local_mac"])


if __name__ == "__main__":
    unittest.main()
