"""项目统一入口。

仓库规则要求所有命令都通过根目录 `main.py` 进入，
这样 VS Code 调试、命令行调用和后续自动化脚本都能共用同一入口。
"""

import os
import sys

from strategy_studio.cli import main


def configure_console_encoding() -> None:
    """尽量把 Windows 控制台统一到 UTF-8。

    这个项目的控制台输出默认是中文。
    如果不在入口尽早统一编码，Windows 外部终端在不同码页下容易出现乱码。
    """
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    if os.name == "nt":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleCP(65001)
            kernel32.SetConsoleOutputCP(65001)
        except Exception:
            # 控制台码页切换失败时，至少继续尝试重设 Python 自身的流编码。
            pass

    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


if __name__ == "__main__":
    configure_console_encoding()
    raise SystemExit(main())
