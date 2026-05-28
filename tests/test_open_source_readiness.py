import subprocess
import tomllib
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class OpenSourceReadinessTests(unittest.TestCase):
    """验证仓库是否保持开源项目所需的元信息和目录边界。"""

    def test_required_governance_files_exist(self) -> None:
        required_paths = [
            REPO_ROOT / ".editorconfig",
            REPO_ROOT / ".gitattributes",
            REPO_ROOT / ".github" / "workflows" / "ci.yml",
            REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml",
            REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml",
            REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml",
            REPO_ROOT / ".github" / "pull_request_template.md",
            REPO_ROOT / "SECURITY.md",
            REPO_ROOT / "SUPPORT.md",
            REPO_ROOT / "pyproject.toml",
            REPO_ROOT / "data" / "README.md",
            REPO_ROOT / "reports" / "README.md",
            REPO_ROOT / "doc" / "open-source-readiness.md",
        ]
        for path in required_paths:
            self.assertTrue(path.exists(), msg=f"{path.relative_to(REPO_ROOT)} 缺失")

    def test_pyproject_contains_basic_metadata(self) -> None:
        payload = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        project = payload["project"]
        self.assertEqual(project["name"], "strategy-studio")
        self.assertEqual(project["requires-python"], ">=3.13")
        self.assertIn("dynamic", project)
        self.assertIn("dependencies", project["dynamic"])

    def test_runtime_outputs_are_not_tracked(self) -> None:
        tracked_files = subprocess.run(
            ["git", "ls-files"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.splitlines()
        disallowed_prefixes = [
            "data/processed/",
            "reports/platform/",
        ]
        allowed_exact = {
            "data/processed/.gitkeep",
            "reports/platform/.gitkeep",
        }
        for tracked_file in tracked_files:
            self.assertNotEqual(tracked_file, "task.md", msg="task.md 不应继续纳入版本控制")
            for prefix in disallowed_prefixes:
                if tracked_file.startswith(prefix) and tracked_file not in allowed_exact:
                    self.fail(f"{tracked_file} 属于运行产物，不应纳入版本控制")

    def test_repo_only_keeps_curated_examples(self) -> None:
        tracked_files = subprocess.run(
            ["git", "ls-files"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.splitlines()
        tracked_sample_csvs = [item for item in tracked_files if item.startswith("data/samples/") and item.endswith(".csv")]
        tracked_example_reports = [item for item in tracked_files if item.startswith("reports/examples/") and item.endswith(".md")]
        self.assertEqual(
            sorted(tracked_sample_csvs),
            [
                "data/samples/1810_hk_15m.csv",
                "data/samples/1810_hk_daily.csv",
            ],
        )
        self.assertEqual(
            sorted(tracked_example_reports),
            [
                "reports/examples/1810_hk/daily/1810_hk_daily_strategy_compare_report.md",
                "reports/examples/1810_hk/daily/1810_hk_grid_report.md",
                "reports/examples/1810_hk/minute/1810_hk_15m_grid_report.md",
                "reports/examples/1810_hk/minute/1810_hk_15m_strategy_compare_report.md",
                "reports/examples/report_index.md",
            ],
        )


if __name__ == "__main__":
    unittest.main()
