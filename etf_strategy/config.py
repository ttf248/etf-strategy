"""项目默认配置。

这里故意只保留轻量常量，不在配置层引入复杂逻辑，
避免默认值和运行时推导规则分散在多个文件里。
"""

from pathlib import Path

# 默认标的是小米港股，既用于命令行默认值，也用于 README 示例。
DEFAULT_SYMBOL = "1810.HK"
DEFAULT_DATA_PATH = Path("data/processed/xiaomi_1810_hk_daily.csv")
DEFAULT_MINUTE_DATA_PATH = Path("data/processed/xiaomi_1810_hk_15m.csv")
DEFAULT_MINUTE_INTERVAL = "15m"
DEFAULT_MINUTE_PERIOD = "60d"
# 中间结果与正式报告目录分开，方便重复回测时只替换输出而不污染文档目录。
DEFAULT_OUTPUT_DIR = Path("outputs")
DEFAULT_MINUTE_OUTPUT_DIR = DEFAULT_OUTPUT_DIR / "minute"
DEFAULT_REPORT_DIR = Path("reports")
DEFAULT_MINUTE_REPORT_DIR = DEFAULT_REPORT_DIR / "minute"
