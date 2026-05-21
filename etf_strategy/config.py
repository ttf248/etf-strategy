"""项目默认配置。

这里故意只保留轻量常量，不在配置层引入复杂逻辑，
避免默认值和运行时推导规则分散在多个文件里。
"""

from pathlib import Path

# 默认标的只作为示例输入存在，不代表服务绑定某一只股票。
DEFAULT_SYMBOL = "1810.HK"
DEFAULT_DATA_PATH = Path("data/processed/1810_hk_daily.csv")
DEFAULT_MINUTE_DATA_PATH = Path("data/processed/1810_hk_15m.csv")
DEFAULT_MINUTE_INTERVAL = "15m"
DEFAULT_MINUTE_PERIOD = "60d"
# 中间结果与正式报告目录分开，方便重复回测时只替换输出而不污染文档目录。
DEFAULT_OUTPUT_DIR = Path("outputs")
DEFAULT_MINUTE_OUTPUT_DIR = DEFAULT_OUTPUT_DIR / "minute"
DEFAULT_REFERENCE_DATA_DIR = Path("data/reference")
DEFAULT_SOUTHBOUND_SHANGHAI_SNAPSHOT_PATH = DEFAULT_REFERENCE_DATA_DIR / "southbound_shanghai_eligible_snapshot.csv"
DEFAULT_REPORT_ROOT = Path("reports")
DEFAULT_REPORT_INDEX_PATH = DEFAULT_REPORT_ROOT / "report_index.md"
DEFAULT_REPORT_REGISTRY_PATH = DEFAULT_REPORT_ROOT / "report_registry.csv"
DEFAULT_REPORT_DIR = DEFAULT_REPORT_ROOT / "1810_hk" / "daily"
DEFAULT_MINUTE_REPORT_DIR = DEFAULT_REPORT_ROOT / "1810_hk" / "minute"
DEFAULT_BATCH_REPORT_DIR = DEFAULT_REPORT_ROOT
