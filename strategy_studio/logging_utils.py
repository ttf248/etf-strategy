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

    # 终端日志以可读性优先，只保留用户最关心的信息。
    logger.add(
        sys.stderr,
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    )
    # 文件日志保留更详细的定位信息，便于排查下载异常或回测口径问题。
    logger.add(
        log_path / "strategy_studio_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="30 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
        encoding="utf-8",
    )
