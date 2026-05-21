# 开发与维护说明

这份文档面向后续维护者，重点回答：

- 从哪里进入代码
- 常见改动应该改哪里
- 哪些改动必须同步更新文档和测试

## 运行入口

统一入口是根目录 `main.py` 的 `main()`。

不要把 `python -m 包名` 当成主运行方式。

## 关键模块职责

### `etf_strategy/cli.py`

负责：

- 解析命令行参数
- 选择日线或分钟线工作流
- 输出适合终端阅读的中文结果

不负责：

- 具体回测逻辑
- 报告模板细节

### `etf_strategy/workflow.py`

负责：

- 串起样本切分、样本内寻参、样本外验证、结果落盘

它是编排层，不适合继续堆大量文案解释。

### `etf_strategy/strategy/grid.py`

负责：

- 核心网格回测逻辑
- 样本切分
- 参数搜索
- 综合评分

### `etf_strategy/reporting.py`

负责：

- 图表生成
- Markdown 报告模板
- 把结构化结果翻译成更适合阅读的中文说明

它应该承担“结果解释”，不应该承担项目首页教程职责。

### `etf_strategy/data/`

负责：

- Yahoo 数据下载与标准化；下载必须配置代理，失败后直接停止
- 交易单位规则
- 日线全历史默认下载口径
- 分钟线本地样本增量合并

## 常见改动应该改哪里

### 新增命令或调整 CLI 参数

至少同步更新：

- `etf_strategy/cli.py`
- `etf_strategy/data/yahoo.py`
- `README.md`
- `.vscode/launch.json`
- 对应测试

### 修改样本切分规则

至少同步更新：

- `etf_strategy/strategy/grid.py`
- `etf_strategy/workflow.py`
- `README.md`
- 对应专题文档
- 报告口径

### 修改报告结构或解释口径

至少同步更新：

- `etf_strategy/reporting.py`
- [回测报告阅读指南](report_reading_guide.md)
- 示例报告
- `task.md`

### 修改默认样本数据或默认路径

至少同步更新：

- `etf_strategy/config.py`
- `etf_strategy/cli.py`
- `.gitignore`
- `README.md`
- 相关测试

### 修改下载与样本积累规则

至少同步更新：

- `etf_strategy/data/yahoo.py`
- `etf_strategy/cli.py`
- `doc/glossary.md`
- `doc/minute_grid_research.md`
- `.vscode/launch.json`
- `task.md`

### 修改默认调试入口

当前仓库保留更直接的 Python `launch.json` 样式，VS Code 配置收敛为两部分：

- `.vscode/launch.json`：负责一键启动
- `.vscode/settings.json`：负责终端 profile

其中 `launch.json` 当前只保留两条一键调试配置：

- 基于 `hstech_plus_513050` 标的池的一键批量分钟线报告
- 基于 `data/processed/1810_hk_15m.csv` 的 15 分钟正式报告重算

使用这些配置的前提是 VS Code 已安装 Microsoft 的 Python / Python Debugger 扩展，否则 `debugpy` 调试类型不会被注册。

这两条配置当前统一采用下面这组字段：

- `type=debugpy`
- `request=launch`
- `program=${workspaceFolder}/main.py`
- `cwd=${workspaceFolder}`
- `console=integratedTerminal`
- `args` 中显式传入 `--execution-profile realistic`，确保 VS Code 一键报告使用接近实盘的默认口径
- 运行时直接看 VS Code 集成终端里的 `INFO` 级别提示
- 更详细的定位日志仍写入 `log/etf_strategy_YYYY-MM-DD.log`
- `main.py` 会主动尝试把 Windows 控制台切到 UTF-8，`.vscode/launch.json` 也会显式传入 `PYTHONUTF8=1` 和 `PYTHONIOENCODING=utf-8`
- `report` 命令会输出 `[1/2] -> [2/2]` 进度，`run` 命令会输出 `[1/3] -> [2/3] -> [3/3]` 顶层进度
- `batch` 命令用于多标的研究汇总，默认分钟线周期为 `15m`，把单标的结果写到 `outputs/batch/<symbol>/`，批量汇总写到 `outputs/batch/batch_summary.csv`，汇总报告索引写到 `reports/hstech_15m_report_index.md`，单标的正式报告写到 `reports/<symbol>/minute/`

这里没有继续使用参考示例里的 `type=python`，因为微软当前 Python 调试文档已经把 `debugpy` 作为 Python Debugger 扩展的调试类型；旧写法在部分 VS Code 环境里会导致无法启动调试。

`settings.json` 里额外固定：

- `terminal.integrated.defaultProfile.windows=PowerShell -NoProfile`
- `terminal.integrated.automationProfile.windows=PowerShell -NoProfile`

这样可以减少 PowerShell Profile 对调试和任务终端的干扰。

如果代码改动会影响：

- 运行命令
- 默认样本路径
- 默认 symbol / interval
- 报告生成入口

就必须同步更新 `.vscode/launch.json` 和需要受影响的 `.vscode/settings.json`，并实际执行对应命令确认它还能跑通。

## 文档更新触发条件

下面这些改动，默认都必须同步更新文档：

- 新增命令
- 修改参数含义
- 修改样本切分口径
- 修改报告结构
- 修改正式样本文件名或路径
- 修改输出目录约定

## 测试约定

当前项目使用标准库 `unittest`。

默认验证命令：

```powershell
py -3.13 -m unittest tests.test_grid_strategy
```

如果改动涉及文档链接、报告结构或默认样本路径，后续应补轻量检查，避免文档和代码口径脱节。

## 关于 `task.md`

`task.md` 需要持续更新，但它的职责是：

- 记录 AI 任务背景
- 记录本轮修改方案、修改内容和设计取舍

它不是正式用户文档，也不应该替代 `doc/`。
