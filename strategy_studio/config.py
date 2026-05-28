"""项目默认配置。

这里故意只保留轻量常量，不在配置层引入复杂逻辑。
数据库是正式数据与结果的唯一存储；本文件中的本地目录仅用于
非正式的临时研究输出或测试隔离，不代表受支持的产品落盘路径。
"""

from pathlib import Path

# 默认标的只作为示例输入存在，不代表服务绑定某一只股票。
DEFAULT_SYMBOL = "1810.HK"
DEFAULT_MINUTE_INTERVAL = "15m"
DEFAULT_MINUTE_PERIOD = "60d"
# 历史研究模块仍可能产出临时文件，但正式平台流程不依赖这些目录。
DEFAULT_OUTPUT_DIR = Path("outputs")
DEFAULT_MINUTE_OUTPUT_DIR = DEFAULT_OUTPUT_DIR / "minute"
# 港股每手股数默认只做内存缓存；如需调试持久化，再显式覆盖缓存路径。
DEFAULT_HK_LOT_SIZE_CACHE_PATH: Path | None = None
DEFAULT_REPORT_ROOT = DEFAULT_OUTPUT_DIR / "report_runtime"
DEFAULT_REPORT_INDEX_PATH = DEFAULT_REPORT_ROOT / "report_index.md"
DEFAULT_REPORT_REGISTRY_PATH = DEFAULT_REPORT_ROOT / "report_registry.csv"
DEFAULT_REPORT_DIR = DEFAULT_REPORT_ROOT / "1810_hk" / "daily"
DEFAULT_MINUTE_REPORT_DIR = DEFAULT_REPORT_ROOT / "1810_hk" / "minute"
