import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from switchboard.node import install_node, node_paths, snapshot_node
from switchboard.node_api import create_node_app


class NodeModeTests(unittest.TestCase):
    def test_install_node_creates_switchboard_pack_only(self) -> None:
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir) / "sample-project"
            project_root.mkdir(parents=True)
            readme = project_root / "README.md"
            readme.write_text("existing root readme\n", encoding="utf-8")

            result = install_node(project_root, service_id="sample-service", display_name="Sample Service")
            paths = node_paths(project_root)

            self.assertEqual(readme.read_text(encoding="utf-8"), "existing root readme\n")
            self.assertTrue(paths["node_root"].exists())
            self.assertTrue(paths["core_readme"].exists())
            self.assertTrue(paths["bootstrap_prompt"].exists())
            self.assertTrue(paths["runtime_prompt"].exists())
            self.assertTrue(paths["tasks_completed"].exists())
            self.assertTrue(paths["completed_tasks_json"].exists())
            self.assertTrue(paths["start_script"].exists())
            self.assertTrue(paths["run_script"].exists())
            self.assertEqual(result["manifest"]["service_id"], "sample-service")
            top_level = sorted(path.name for path in project_root.iterdir())
            self.assertEqual(top_level, ["README.md", "switchboard"])

    def test_snapshot_splits_tasks_into_derived_docs_and_json(self) -> None:
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir) / "sample-project"
            install_node(project_root, service_id="sample-service", display_name="Sample Service")
            paths = node_paths(project_root)
            paths["tasks_completed"].write_text(
                "# Tasks Completed\n\n"
                "## 2026-04-01T12:00:00+00:00 | Standardized docs\n"
                "- Tags: task, handoff\n"
                "- Summary: Standardized the local docs.\n"
                "- Changed Paths: switchboard/core/README.md, switchboard/local/tasks-completed.md\n"
                "- Version: 1.1\n"
                "- Readme:\n"
                "  ## Overview\n"
                "  Standardized the project docs.\n"
                "- API:\n"
                "  ## Surface\n"
                "  Added /health.\n"
                "- Changelog:\n"
                "  - Standardized the project docs.\n"
                "- Notes:\n"
                "  - Added the first handoff entry.\n\n"
                "## 2026-04-01T13:00:00+00:00 | Updated scope\n"
                "- Tags: task, decision, runbook, scope\n"
                "- Summary: Updated the tracked scope and runbook.\n"
                "- Changed Paths: switchboard/local/tasks-completed.md\n"
                "- Scope Entries:\n"
                "  - doc | file | /tmp/sample-project/README.md | true\n"
                "  - exclude | glob | venv | true\n",
                encoding="utf-8",
            )

            result = snapshot_node(project_root)
            completed = json.loads(paths["completed_tasks_json"].read_text(encoding="utf-8"))
            scope_snapshot = json.loads(paths["scope_snapshot"].read_text(encoding="utf-8"))
            doc_index = json.loads(paths["doc_index_json"].read_text(encoding="utf-8"))

            self.assertEqual(len(completed["tasks"]), 2)
            self.assertIn("Standardized docs", paths["handoff"].read_text(encoding="utf-8"))
            self.assertIn("Updated scope", paths["runbook"].read_text(encoding="utf-8"))
            self.assertIn("Updated scope", paths["approach_history"].read_text(encoding="utf-8"))
            self.assertEqual(result["scope_snapshot"]["scope_entries"][0]["kind"], "doc")
            self.assertEqual(scope_snapshot["scope_entries"][1]["kind"], "exclude")
            self.assertEqual(result["manifest"]["managed_docs"][0]["doc_id"], "readme")
            self.assertTrue(any(entry["doc_id"] == "doc_index_json" for entry in doc_index["docs"]))
            self.assertIn("Switchboard Playbook", paths["playbook"].read_text(encoding="utf-8"))

    def test_snapshot_only_rewrites_opted_in_root_docs(self) -> None:
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir) / "sample-project"
            install_node(project_root, service_id="sample-service", display_name="Sample Service")
            paths = node_paths(project_root)
            root_readme = project_root / "README.md"
            root_readme.write_text("manual root readme\n", encoding="utf-8")

            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            for entry in manifest["managed_docs"]:
                if entry["doc_id"] == "readme":
                    entry["enabled"] = False
            paths["manifest"].write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            paths["tasks_completed"].write_text(
                "# Tasks Completed\n\n"
                "## 2026-04-01T12:00:00+00:00 | Update readme\n"
                "- Tags: task\n"
                "- Summary: Update readme block.\n"
                "- Changed Paths: switchboard/local/tasks-completed.md\n"
                "- Readme:\n"
                "  Updated readme text.\n",
                encoding="utf-8",
            )

            snapshot_node(project_root)
            self.assertEqual(root_readme.read_text(encoding="utf-8"), "manual root readme\n")

            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            for entry in manifest["managed_docs"]:
                if entry["doc_id"] == "readme":
                    entry["enabled"] = True
            paths["manifest"].write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            snapshot_node(project_root)
            self.assertIn("Updated readme text.", root_readme.read_text(encoding="utf-8"))

    def test_node_api_exposes_health_and_manifest(self) -> None:
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir) / "sample-project"
            install_node(project_root, service_id="sample-service", display_name="Sample Service")
            client = TestClient(create_node_app(project_root))

            health = client.get("/api/health")
            info = client.get("/api/node")

            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json()["mode"], "node")
            self.assertEqual(info.status_code, 200)
            self.assertEqual(info.json()["manifest"]["service_id"], "sample-service")
            self.assertIn("runtime", info.json())
            self.assertIn("last_snapshot_at", info.json())
            self.assertEqual(info.json()["runtime"]["monitoring_mode"], "manual")


if __name__ == "__main__":
    unittest.main()
