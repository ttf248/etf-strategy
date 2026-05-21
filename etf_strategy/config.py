from pathlib import Path

DEFAULT_SYMBOL = "1810.HK"
DEFAULT_DATA_PATH = Path("data/processed/xiaomi_1810_hk_daily.csv")
DEFAULT_MINUTE_DATA_PATH = Path("data/processed/xiaomi_1810_hk_15m.csv")
DEFAULT_MINUTE_INTERVAL = "15m"
DEFAULT_MINUTE_PERIOD = "60d"
DEFAULT_OUTPUT_DIR = Path("outputs")
DEFAULT_MINUTE_OUTPUT_DIR = DEFAULT_OUTPUT_DIR / "minute"
DEFAULT_REPORT_DIR = Path("reports")
DEFAULT_MINUTE_REPORT_DIR = DEFAULT_REPORT_DIR / "minute"
