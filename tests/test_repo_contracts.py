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
        self.assertTrue((REPO_ROOT / "data" / "reference" / "southbound_shanghai_eligible_snapshot.csv").exists())

    def test_document_links_resolve_to_existing_files(self) -> None:
        markdown_files = [
            REPO_ROOT / "README.md",
            REPO_ROOT / "doc" / "index.md",
            REPO_ROOT / "doc" / "report_reading_guide.md",
            REPO_ROOT / "doc" / "glossary.md",
            REPO_ROOT / "doc" / "grid_parameter_search.md",
            REPO_ROOT / "doc" / "minute_grid_research.md",
            REPO_ROOT / "doc" / "index_grid_research.md",
            REPO_ROOT / "doc" / "xiaomi_strategy_research.md",
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
        readme_lines = (REPO_ROOT / "README.md").read_text(encoding="utf-8").splitlines()[:45]
        top_block = "\n".join(readme_lines)
        self.assertIn("reports/report_index.md", top_block)
        self.assertIn("reports/1810_hk/daily/1810_hk_daily_strategy_compare_report.md", top_block)
        self.assertIn("reports/1810_hk/minute/1810_hk_15m_strategy_compare_report.md", top_block)
        self.assertIn("reports/1810_hk/minute/1810_hk_15m_grid_report.md", top_block)

    def test_vscode_launch_contains_platform_entries(self) -> None:
        launch_payload = json.loads((REPO_ROOT / ".vscode" / "launch.json").read_text(encoding="utf-8"))
        configurations = launch_payload.get("configurations", [])
        self.assertEqual(len(configurations), 4)
        config_names = {config["name"] for config in configurations}
        self.assertEqual(config_names, {"启动 API 服务", "启动回测 Worker", "启动行情 Scheduler", "启动前端 Dev Server"})
        python_configs = [config for config in configurations if config["type"] == "debugpy"]
        self.assertEqual(len(python_configs), 3)
        for config in python_configs:
            self.assertEqual(config["program"], "${workspaceFolder}/main.py")
            self.assertEqual(config["cwd"], "${workspaceFolder}")
            self.assertIn(config["args"][0], {"api", "worker", "scheduler"})
            self.assertEqual(config["console"], "integratedTerminal")
            self.assertEqual(config["env"]["PYTHONUTF8"], "1")
            self.assertEqual(config["env"]["PYTHONIOENCODING"], "utf-8")
        frontend_config = next(config for config in configurations if config["name"] == "启动前端 Dev Server")
        self.assertEqual(frontend_config["type"], "node-terminal")
        self.assertEqual(frontend_config["cwd"], "${workspaceFolder}/frontend")
        self.assertIn("npm run dev", frontend_config["command"])
        self.assertEqual(frontend_config["env"]["NEXT_PUBLIC_API_BASE_URL"], "http://127.0.0.1:8000")
        compound_names = {item["name"] for item in launch_payload.get("compounds", [])}
        self.assertEqual(compound_names, {"启动平台后端全套", "启动平台前后端全套"})

    def test_vscode_settings_keep_no_profile_terminal(self) -> None:
        settings_payload = json.loads((REPO_ROOT / ".vscode" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings_payload["terminal.integrated.defaultProfile.windows"], "PowerShell -NoProfile")
        self.assertEqual(
            settings_payload["terminal.integrated.automationProfile.windows"]["source"],
            "PowerShell",
        )
        self.assertEqual(
            settings_payload["terminal.integrated.automationProfile.windows"]["args"],
            ["-NoProfile"],
        )

    def test_reports_keep_two_layer_structure(self) -> None:
        report_files = [
            REPO_ROOT / "reports" / "1810_hk" / "daily" / "1810_hk_grid_report.md",
            REPO_ROOT / "reports" / "1810_hk" / "minute" / "1810_hk_15m_grid_report.md",
            REPO_ROOT / "reports" / "1810_hk" / "daily" / "1810_hk_daily_strategy_compare_report.md",
            REPO_ROOT / "reports" / "1810_hk" / "minute" / "1810_hk_15m_strategy_compare_report.md",
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
