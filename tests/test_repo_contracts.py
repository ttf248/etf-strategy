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
