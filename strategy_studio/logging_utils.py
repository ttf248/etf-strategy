import sys

from loguru import logger


def configure_logging() -> None:
    """配置日志输出。

    数据库优先模式下不再默认落地本地日志文件，避免工作区继续沉淀运行数据。
    """
    logger.remove()

    # 终端日志以可读性优先，只保留用户最关心的信息。
    logger.add(
        sys.stderr,
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    )
