import sys
from pathlib import Path

from loguru import logger


def configure_logging(log_dir: str = "log") -> None:
    """配置日志输出。

    终端保留 INFO 级别，文件保留 DEBUG 级别，便于回测排查。
    """
    logger.remove()

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    logger.add(
        sys.stderr,
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    )
    logger.add(
        log_path / "etf_strategy_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="30 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
        encoding="utf-8",
    )
