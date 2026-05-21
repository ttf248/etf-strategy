"""项目统一入口。

仓库规则要求所有命令都通过根目录 `main.py` 进入，
这样 VS Code 调试、命令行调用和后续自动化脚本都能共用同一入口。
"""

from etf_strategy.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
