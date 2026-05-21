import json
import re
import unittest
from pathlib import Path

from etf_strategy.config import DEFAULT_DATA_PATH, DEFAULT_MINUTE_DATA_PATH


REPO_ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


class RepoContractTests(unittest.TestCase):
    """覆盖默认样本、Markdown 链接和报告结构这些仓库级契约。"""

    def test_default_sample_paths_exist(self) -> None:
        self.assertTrue((REPO_ROOT / DEFAULT_DATA_PATH).exists())
        self.assertTrue((REPO_ROOT / DEFAULT_MINUTE_DATA_PATH).exists())

    def test_document_links_resolve_to_existing_files(self) -> None:
        markdown_files = [
            REPO_ROOT / "README.md",
            REPO_ROOT / "doc" / "index.md",
            REPO_ROOT / "doc" / "report_reading_guide.md",
            REPO_ROOT / "doc" / "glossary.md",
            REPO_ROOT / "doc" / "grid_parameter_search.md",
            REPO_ROOT / "doc" / "minute_grid_research.md",
            REPO_ROOT / "doc" / "development_guide.md",
        ]

        for markdown_file in markdown_files:
            content = markdown_file.read_text(encoding="utf-8")
            for target in MARKDOWN_LINK_PATTERN.findall(content):
                if target.startswith(("http://", "https://", "#")):
                    continue
                relative_target = target.split("#", maxsplit=1)[0]
                resolved = (markdown_file.parent / relative_target).resolve()
                self.assertTrue(
                    resolved.exists(),
                    msg=f"{markdown_file.relative_to(REPO_ROOT)} -> {target} 不存在",
                )

    def test_readme_top_has_report_shortcuts(self) -> None:
        readme_lines = (REPO_ROOT / "README.md").read_text(encoding="utf-8").splitlines()[:20]
        top_block = "\n".join(readme_lines)
        self.assertIn("reports/1810_hk_grid_report.md", top_block)
        self.assertIn("reports/minute/1810_hk_15m_grid_report.md", top_block)

    def test_vscode_launch_only_keeps_one_click_report_configs(self) -> None:
        launch_payload = json.loads((REPO_ROOT / ".vscode" / "launch.json").read_text(encoding="utf-8"))
        configurations = launch_payload.get("configurations", [])
        self.assertEqual(len(configurations), 2)
        config_names = {config["name"] for config in configurations}
        self.assertEqual(config_names, {"一键生成日线正式报告", "一键生成15分钟正式报告"})
        for config in configurations:
            self.assertEqual(config["program"], "${workspaceFolder}/main.py")
            self.assertEqual(config["cwd"], "${workspaceFolder}")
            self.assertEqual(config["args"][0], "report")
            self.assertEqual(config["console"], "internalConsole")
            self.assertEqual(config["internalConsoleOptions"], "openOnSessionStart")
            self.assertTrue(config["redirectOutput"])
            self.assertTrue(config["justMyCode"])
            self.assertEqual(config["env"]["PYTHONUTF8"], "1")
            self.assertEqual(config["env"]["PYTHONIOENCODING"], "utf-8")

    def test_vscode_settings_open_debug_view_on_session_start(self) -> None:
        settings_payload = json.loads((REPO_ROOT / ".vscode" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings_payload["debug.openDebug"], "openOnSessionStart")
        self.assertEqual(settings_payload["terminal.integrated.defaultProfile.windows"], "PowerShell -NoProfile")
        self.assertEqual(
            settings_payload["terminal.integrated.automationProfile.windows"]["source"],
            "PowerShell",
        )
        self.assertEqual(
            settings_payload["terminal.integrated.automationProfile.windows"]["args"],
            ["-NoProfile"],
        )

    def test_vscode_tasks_keep_two_terminal_report_entries(self) -> None:
        tasks_payload = json.loads((REPO_ROOT / ".vscode" / "tasks.json").read_text(encoding="utf-8"))
        tasks = tasks_payload.get("tasks", [])
        self.assertEqual(len(tasks), 2)
        task_names = {task["label"] for task in tasks}
        self.assertEqual(task_names, {"终端生成日线正式报告", "终端生成 15 分钟正式报告"})
        for task in tasks:
            self.assertEqual(task["type"], "process")
            self.assertEqual(task["command"], "py")
            self.assertEqual(task["args"][1], "${workspaceFolder}/main.py")
            self.assertEqual(task["args"][2], "report")
            self.assertEqual(task["options"]["cwd"], "${workspaceFolder}")
            self.assertEqual(task["options"]["env"]["PYTHONUTF8"], "1")
            self.assertEqual(task["options"]["env"]["PYTHONIOENCODING"], "utf-8")
            self.assertEqual(task["presentation"]["reveal"], "always")
            self.assertTrue(task["presentation"]["focus"])
            self.assertEqual(task["presentation"]["panel"], "dedicated")
            self.assertTrue(task["presentation"]["clear"])
            self.assertFalse(task["presentation"]["showReuseMessage"])

    def test_reports_keep_two_layer_structure(self) -> None:
        report_files = [
            REPO_ROOT / "reports" / "1810_hk_grid_report.md",
            REPO_ROOT / "reports" / "minute" / "1810_hk_15m_grid_report.md",
        ]
        required_sections = [
            "## 第一层：先看结论",
            "## 第二层：展开细节",
            "## 最终结论",
        ]

        for report_file in report_files:
            content = report_file.read_text(encoding="utf-8")
            for section in required_sections:
                self.assertIn(section, content, msg=f"{report_file.relative_to(REPO_ROOT)} 缺少 {section}")


if __name__ == "__main__":
    unittest.main()
