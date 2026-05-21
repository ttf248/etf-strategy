# ETF Strategy

基于 Yahoo Finance 数据的小型策略回测项目，当前默认用 `1810.HK` 作为开发验证样本，研究“样本起点建仓 + 固定股数网格交易”的回测流程。

## 快速跳转

- [最新日线正式报告](reports/1810_hk_grid_report.md)
- [最新 15 分钟正式报告](reports/minute/1810_hk_15m_grid_report.md)
- [参数筛选方法说明](doc/grid_parameter_search.md)
- [回测报告阅读指南](doc/report_reading_guide.md)
- [项目导航与阅读顺序](doc/index.md)

这个仓库现在的定位不是“一次性脚本”，而是“可重复运行的策略研究工程”：

- 所有命令统一从根目录 `main.py` 进入
- 只保留 Yahoo 数据链路，降低维护面
- 同时输出中间结果、图表、交易记录和中文报告，方便复盘
- 回测命令默认使用 `realistic` 执行口径，计入可配置的手续费、滑点、仓位上限和停手机制

## 你先从哪里开始

如果你第一次进入这个仓库，建议按下面顺序看：

1. 看这份 README，了解项目定位和最短上手路径
2. 看[项目导航与阅读顺序](doc/index.md)，建立整体结构感
3. 看[回测报告阅读指南](doc/report_reading_guide.md)，知道报告里的图和指标怎么读
4. 再按需要看专题文档和正式报告

## 仓库内置正式样本

为了让默认流程可复现，仓库直接跟踪两份正式样本：

- `data/processed/1810_hk_daily.csv`
- `data/processed/1810_hk_15m.csv`

它们分别对应：

- 日线主流程默认输入快照
- `15m` 分钟线研究默认输入快照

测试临时 CSV 和一次性研究样本不会一起纳入版本控制。

需要注意：

- `download` 和 `run` 命令现在会优先把新下载的数据和本地 CSV 做合并
- 日线在不传 `--start/--end` 时，会按 Yahoo 可提供的全历史口径下载
- 仓库里提交的两份 CSV 只是当前示例快照，不代表下载能力上限

## 最短上手路径

### 1. 安装依赖

```powershell
py -3.13 -m pip install -r requirements.txt
```

### 2. 直接生成日线报告

```powershell
py -3.13 main.py report --data data/processed/1810_hk_daily.csv --symbol 1810.HK
```

输出：

- 中间结果：`outputs/`
- 正式报告：`reports/1810_hk_grid_report.md`

### 3. 直接生成 15 分钟线报告

```powershell
py -3.13 main.py report --data data/processed/1810_hk_15m.csv --symbol 1810.HK --interval 15m
```

输出：

- 中间结果：`outputs/minute/`
- 正式报告：`reports/minute/1810_hk_15m_grid_report.md`

## 文档导航

总导航：

- [项目导航与阅读顺序](doc/index.md)

结果阅读：

- [回测报告阅读指南](doc/report_reading_guide.md)
- [术语表与口径说明](doc/glossary.md)

专题说明：

- [日线网格参数测试方法](doc/grid_parameter_search.md)
- [Yahoo 分钟线支持与 15 分钟回测说明](doc/minute_grid_research.md)

维护者入口：

- [开发与维护说明](doc/development_guide.md)

## 常用命令速查

### 下载日线数据

```powershell
py -3.13 main.py download --symbol 1810.HK --proxy http://127.0.0.1:7897
```

如果你只想下载某一段日线区间，也可以显式传：

```powershell
py -3.13 main.py download --symbol 1810.HK --start 2024-01-01 --end 2026-05-22 --proxy http://127.0.0.1:7897
```

### 下载默认分钟线数据

```powershell
py -3.13 main.py download --symbol 1810.HK --interval 15m --period 60d --proxy http://127.0.0.1:7897
```

说明：

- 分钟线免费数据通常只有最近 `60d`
- 项目会先把这次下载结果和本地 `data/processed/1810_hk_15m.csv` 做时间戳合并，再进入后续回测

### 样本内参数搜索

```powershell
py -3.13 main.py optimize --data data/processed/1810_hk_daily.csv --symbol 1810.HK
```

### 样本外验证

```powershell
py -3.13 main.py backtest --data data/processed/1810_hk_daily.csv --symbol 1810.HK --grid-spacing 0.07 --grid-count 5 --take-profit 0.03
```

### 执行口径与风控参数

`optimize`、`backtest`、`report`、`run` 默认使用更接近实盘的口径：

- `--execution-profile realistic`
- 默认计入手续费、滑点、最大仓位占用和止损停手
- 报告会同时对比网格、只拿底仓和买入持有

如果需要复现旧的简化研究口径，可以显式传：

```powershell
py -3.13 main.py report --data data/processed/1810_hk_daily.csv --symbol 1810.HK --execution-profile research
```

常用覆盖参数：

- `--commission-bps`：单边手续费，单位 bps
- `--slippage-bps`：单边滑点，单位 bps
- `--max-position-ratio`：最大仓位占总资金比例，例如 `0.95`
- `--stop-loss-pct`：触发停止新增网格的跌幅，例如 `0.2`
- `--cooldown-bars`：触发停手后的冷却 K 线数量

### 一键执行完整流程

```powershell
py -3.13 main.py run --symbol 1810.HK --proxy http://127.0.0.1:7897
```

如果你希望限定这次日线完整流程只使用某个时间段，也可以显式传 `--start` 和 `--end`。

如果你在中国大陆直连 Yahoo，通常需要代理。可以设置：

```powershell
$env:ETF_STRATEGY_PROXY="http://127.0.0.1:7897"
```

## 项目结构速览

```text
etf_strategy/    源码
data/processed/  默认正式样本输入
outputs/         运行中间结果
reports/         正式图表与中文报告
doc/             长期维护文档
tests/           标准库 unittest 用例
task.md          AI 任务记录
```

## 输出与版本控制

- `data/processed/`：默认正式样本输入，当前只跟踪两份 `1810.HK` 示例样本
- `outputs/`：运行时中间文件，默认忽略版本控制
- `reports/`：正式中文报告、图表和交易记录展示
- `log/`：日志输出

## VS Code 运行与调试

现在 VS Code 配置收敛成“轻量 `launch.json` + 辅助 `settings.json`”：

- `.vscode/launch.json`：只保留 2 条 Python 启动配置
- `.vscode/settings.json`：只保留 Windows 终端的 `PowerShell -NoProfile` 设置

### 启动入口

使用这些启动项前，需要 VS Code 已安装 Microsoft 的 Python / Python Debugger 扩展；否则 `debugpy` 调试类型不会被识别。

`launch.json` 当前只保留 2 个一键入口：

- 一键生成日线正式报告
- 一键生成 15 分钟正式报告

它们都直接基于仓库内置正式样本重算报告：

- 不依赖 Yahoo 网络连接
- 不依赖本地代理是否可用
- 更适合日常改代码后的快速回归验证

这两条配置保留你给的集成终端启动风格，但调试器类型使用微软当前 Python 调试文档推荐的 `debugpy`：

- `type=debugpy`
- `request=launch`
- `program=${workspaceFolder}/main.py`
- `console=integratedTerminal`

原因是 `type=python` 属于旧写法，在当前 Python Debugger 扩展下可能导致 VS Code 无法启动调试。现在点启动后，程序仍会直接在 VS Code 集成终端里执行。

### 终端设置

`settings.json` 里只额外保留：

- `terminal.integrated.defaultProfile.windows=PowerShell -NoProfile`
- `terminal.integrated.automationProfile.windows=PowerShell -NoProfile`

目的是减少 PowerShell Profile 干扰，尽量避免终端刚启动就先输出无关内容或报错。

### 运行时你会看到什么

运行期间主要看 VS Code 底部终端面板。

日志文件仍会额外写到 `log/etf_strategy_YYYY-MM-DD.log`，用于更细的排错。

当前终端常见提示包括：

- 收到哪个命令，例如 `report` / `run`
- 分步骤进度，例如 `[1/2]`、`[2/2]` 或完整流程里的 `[1/3]`、`[2/3]`、`[3/3]`
- 当前处理的标的、周期、数据文件
- 开始执行样本内寻参、样本外验证、正式报告生成
- 每个大步骤完成后的输出路径和耗时

其中 `run` 命令会明确按 3 个顶层阶段打印：

- `[1/3]` 下载并合并最新行情
- `[2/3]` 执行完整回测工作流
- `[3/3]` 生成正式报告

## 验证

```powershell
py -3.13 -m unittest tests.test_grid_strategy tests.test_repo_contracts tests.test_yahoo_data
```
