import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import HTTPException
from pydantic import ValidationError

from switchboard.api import collect_workspace, get_workspace_latest, git_pull
from switchboard.config import Settings
from switchboard.collectors import CollectionCoordinator
from switchboard.manifests import ManifestStore, save_json
from switchboard.models import CollectRequest, GitPullRequest, PullBundleRequest
from switchboard.storage import SnapshotStore, read_json


class BackendRegressionTests(unittest.TestCase):
    def test_latest_includes_inventory_keys(self) -> None:
        body = get_workspace_latest("zapp")
        for key in ("workspace", "servers", "services", "summary", "repo_inventory", "docs_index", "logs_index"):
            self.assertIn(key, body)

    def test_git_pull_rejects_non_allowlisted_path(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            git_pull("docgenerator", GitPullRequest(repo_path="/etc/passwd"))
        self.assertEqual(ctx.exception.status_code, 403)

    def test_git_pull_rejects_empty_path(self) -> None:
        with self.assertRaises(ValidationError):
            GitPullRequest(repo_path="   ")

    def test_collect_returns_structured_snapshot(self) -> None:
        body = collect_workspace("zapp", CollectRequest())
        self.assertIn("services", body)
        self.assertIsInstance(body["services"], list)
        for service in body["services"]:
            self.assertIn("status", service)

    def test_delete_service_clears_active_service_data(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest_dir = root / "switchboard" / "manifests"
            evidence_dir = root / "docs" / "evidence"
            archive_dir = evidence_dir / "archive"
            private_state_dir = root / "state" / "private"
            downloads_dir = root / "downloads"

            save_json(
                manifest_dir / "servers.json",
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
                manifest_dir / "workspaces.json",
                [
                    {
                        "workspace_id": "pesu",
                        "name": "PESU",
                        "tags": [],
                        "favorite_tier": "primary",
                        "servers": ["local_mac"],
                        "services": ["emailagent"],
                        "notes": "",
                    }
                ],
            )
            save_json(
                manifest_dir / "services.json",
                [
                    {
                        "service_id": "emailagent",
                        "workspace_id": "pesu",
                        "display_name": "Email Agent",
                        "kind": "service",
                        "ownership_tier": "owned",
                        "tags": [],
                        "favorite_tier": "primary",
                        "locations": [
                            {
                                "location_id": "emailagent-local",
                                "server_id": "local_mac",
                                "access_mode": "local",
                                "root": "/tmp/emailagent",
                                "role": "primary",
                                "is_primary": True,
                                "path_aliases": [],
                            }
                        ],
                        "scope_entries": [
                            {
                                "entry_id": "repo-1",
                                "kind": "repo",
                                "path": "/tmp/emailagent",
                                "path_type": "dir",
                                "source": "user_added",
                                "enabled": True,
                            }
                        ],
                    }
                ],
            )

            archive_token = "2026-04-01T00-00-00+00-00"
            archive_snapshot_rel = f"evidence/archive/{archive_token}/workspace-pesu.json"
            save_json(
                evidence_dir / "workspace-registry.json",
                {
                    "generated": "2026-04-01T00:00:00+00:00",
                    "workspaces": [
                        {
                            "workspace_id": "pesu",
                            "name": "PESU",
                            "servers": ["local_mac"],
                            "services": ["emailagent"],
                            "service_count": 1,
                            "last_status": "partial",
                        }
                    ],
                },
            )
            save_json(
                evidence_dir / "service-inventory.json",
                {
                    "generated": "2026-04-01T00:00:00+00:00",
                    "services": [
                        {
                            "service_id": "emailagent",
                            "workspace_id": "pesu",
                            "display_name": "Email Agent",
                            "last_status": "ok",
                        }
                    ],
                },
            )
            save_json(
                evidence_dir / "repo-inventory.json",
                {
                    "generated": "2026-04-01T00:00:00+00:00",
                    "repos": [{"service_id": "emailagent", "repo_path": "/tmp/emailagent"}],
                },
            )
            save_json(
                evidence_dir / "docs-index.json",
                {
                    "generated": "2026-04-01T00:00:00+00:00",
                    "files": [{"service_id": "emailagent", "path": "/tmp/emailagent/README.md"}],
                },
            )
            save_json(
                evidence_dir / "logs-index.json",
                {
                    "generated": "2026-04-01T00:00:00+00:00",
                    "files": [{"service_id": "emailagent", "path": "/tmp/emailagent/server.log"}],
                },
            )
            save_json(
                evidence_dir / "pull-bundle-history.json",
                {
                    "generated": "2026-04-01T00:00:00+00:00",
                    "bundles": [{"service_id": "emailagent", "bundle_id": "bundle-1"}],
                },
            )
            save_json(
                evidence_dir / "repo-safety-history.json",
                {
                    "generated": "2026-04-01T00:00:00+00:00",
                    "checks": [{"service_id": "emailagent", "repo_path": "/tmp/emailagent"}],
                },
            )
            save_json(
                evidence_dir / "run-history.json",
                {
                    "generated": "2026-04-01T00:00:00+00:00",
                    "runs": [
                        {
                            "workspace_id": "pesu",
                            "generated": "2026-04-01T00:00:00+00:00",
                            "archive_path": archive_snapshot_rel,
                            "status": "partial",
                            "service_count": 1,
                            "server_count": 1,
                        }
                    ],
                },
            )
            save_json(
                archive_dir / archive_token / "workspace-pesu.json",
                {
                    "generated": "2026-04-01T00:00:00+00:00",
                    "workspace": {"workspace_id": "pesu", "name": "PESU"},
                    "servers": [{"server_id": "local_mac", "status": "ok"}],
                    "services": [{"service_id": "emailagent", "status": "ok"}],
                    "repo_inventory": [{"service_id": "emailagent", "repo_path": "/tmp/emailagent"}],
                    "docs_index": [{"service_id": "emailagent", "path": "/tmp/emailagent/README.md"}],
                    "logs_index": [{"service_id": "emailagent", "path": "/tmp/emailagent/server.log"}],
                    "secret_path_index": [{"service_id": "emailagent", "path": "/tmp/emailagent/.env"}],
                    "summary": {"status": "partial", "service_count": 1, "server_count": 1},
                },
            )
            save_json(
                private_state_dir / "secret-path-index.json",
                {
                    "generated": "2026-04-01T00:00:00+00:00",
                    "entries": [{"service_id": "emailagent", "path": "/tmp/emailagent/.env"}],
                },
            )
            save_json(
                private_state_dir / "repo-safety-findings.json",
                {
                    "generated": "2026-04-01T00:00:00+00:00",
                    "checks": [{"service_id": "emailagent", "findings": [{"path": ".env"}]}],
                },
            )
            save_json(private_state_dir / "runtime-cache.json", {"generated": "", "cache": {}})

            bundle_dir = downloads_dir / "pesu" / "emailagent"
            bundle_dir.mkdir(parents=True, exist_ok=True)
            (bundle_dir / "marker.txt").write_text("x", encoding="utf-8")

            settings = Settings(
                manifest_dir=manifest_dir,
                evidence_dir=evidence_dir,
                archive_dir=archive_dir,
                private_state_dir=private_state_dir,
                downloads_dir=downloads_dir,
            )
            manifests = ManifestStore(settings)
            snapshots = SnapshotStore(settings, manifests)

            removed = manifests.delete_service("emailagent")
            result = snapshots.delete_service_data("emailagent", removed.workspace_id)

            self.assertTrue(result["deleted"])
            self.assertEqual(removed.workspace_id, "pesu")
            self.assertEqual(manifests.load_services(), [])
            self.assertEqual(manifests.get_workspace("pesu").services, [])
            self.assertFalse((downloads_dir / "pesu" / "emailagent").exists())
            self.assertEqual(read_json(evidence_dir / "service-inventory.json", {"services": []})["services"], [])
            self.assertEqual(read_json(evidence_dir / "repo-inventory.json", {"repos": []})["repos"], [])
            self.assertEqual(read_json(evidence_dir / "docs-index.json", {"files": []})["files"], [])
            self.assertEqual(read_json(evidence_dir / "logs-index.json", {"files": []})["files"], [])
            self.assertEqual(read_json(evidence_dir / "pull-bundle-history.json", {"bundles": []})["bundles"], [])
            self.assertEqual(read_json(evidence_dir / "repo-safety-history.json", {"checks": []})["checks"], [])
            self.assertEqual(read_json(private_state_dir / "secret-path-index.json", {"entries": []})["entries"], [])
            self.assertEqual(read_json(private_state_dir / "repo-safety-findings.json", {"checks": []})["checks"], [])
            self.assertEqual(
                read_json(evidence_dir / "workspace-registry.json", {"workspaces": []})["workspaces"][0]["service_count"],
                0,
            )
            self.assertEqual(
                read_json(archive_dir / archive_token / "workspace-pesu.json", {})["summary"]["service_count"],
                0,
            )
            self.assertEqual(
                read_json(archive_dir / archive_token / "workspace-pesu.json", {})["services"],
                [],
            )

    def test_pull_bundle_includes_repo_entries(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_root = root / "project"
            project_root.mkdir()
            (project_root / "main.py").write_text("print('ok')\n", encoding="utf-8")
            (project_root / "README.md").write_text("# test\n", encoding="utf-8")

            manifest_dir = root / "switchboard" / "manifests"
            evidence_dir = root / "docs" / "evidence"
            archive_dir = evidence_dir / "archive"
            private_state_dir = root / "state" / "private"
            downloads_dir = root / "downloads"

            save_json(
                manifest_dir / "servers.json",
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
                manifest_dir / "workspaces.json",
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
                manifest_dir / "services.json",
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
                        "scope_entries": [
                            {
                                "entry_id": "repo-1",
                                "kind": "repo",
                                "path": str(project_root / "main.py"),
                                "path_type": "file",
                                "source": "user_added",
                                "enabled": True,
                            },
                            {
                                "entry_id": "doc-1",
                                "kind": "doc",
                                "path": str(project_root / "README.md"),
                                "path_type": "file",
                                "source": "user_added",
                                "enabled": True,
                            },
                        ],
                    }
                ],
            )

            settings = Settings(
                manifest_dir=manifest_dir,
                evidence_dir=evidence_dir,
                archive_dir=archive_dir,
                private_state_dir=private_state_dir,
                downloads_dir=downloads_dir,
            )
            manifests = ManifestStore(settings)
            snapshots = SnapshotStore(settings, manifests)
            coordinator = CollectionCoordinator(settings, manifests, snapshots)

            result = coordinator.pull_bundle("svc", PullBundleRequest())

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["file_count"], 2)
            files = {Path(item["target_path"]).name: item for item in result["files"]}
            self.assertIn("main.py", files)
            self.assertIn("README.md", files)
            self.assertEqual(files["main.py"]["kind"], "repo")

    def test_scope_classifier_defaults_python_file_to_repo(self) -> None:
        settings = Settings()
        manifests = ManifestStore(settings)
        snapshots = SnapshotStore(settings, manifests)
        coordinator = CollectionCoordinator(settings, manifests, snapshots)

        self.assertEqual(coordinator._suggest_scope_kind("main.py", "/workspace/aichat/main.py", "file"), "repo")
        self.assertEqual(coordinator._suggest_scope_kind("README.md", "/workspace/aichat/README.md", "file"), "doc")
        self.assertEqual(coordinator._suggest_scope_kind("backend", "/workspace/aichat/backend", "dir"), "doc")


if __name__ == "__main__":
    unittest.main()
