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

这次按微软官方文档，把 `.vscode/` 重整成 3 个职责明确的文件：

- `.vscode/launch.json`：只放 Python 调试配置
- `.vscode/tasks.json`：只放“稳定显示终端输出”的运行任务
- `.vscode/settings.json`：只放工作区级调试与终端行为设置

### 调试入口

`launch.json` 现在仍只保留 2 个最稳妥的一键调试入口：

- 一键生成日线正式报告
- 一键生成 15 分钟正式报告

它们都直接基于仓库内置正式样本重算报告：

- 不依赖 Yahoo 网络连接
- 不依赖本地代理是否可用
- 更适合日常改代码后的快速回归验证

这两条调试配置现在改成走 VS Code `调试控制台`：

- `console=internalConsole`
- `internalConsoleOptions=openOnSessionStart`
- `redirectOutput=true`

这样点启动后，调试控制台会自动打开，标准输出和错误输出也会直接显示在那里，不再依赖终端面板是否刚好弹出。

### 终端入口

如果你想明确看到“真实终端里的执行过程”，再用 `Terminal: Run Task` 运行这两条任务：

- 终端生成日线正式报告
- 终端生成 15 分钟正式报告

这两条任务按微软任务系统配置了：

- `presentation.reveal=always`
- `presentation.focus=true`
- `presentation.panel=dedicated`
- `presentation.clear=true`

也就是每次执行都会主动切出独立终端面板，并清空旧输出。

### 工作区设置

`settings.json` 里额外固定了：

- `debug.openDebug=openOnSessionStart`
- `terminal.integrated.defaultProfile.windows=PowerShell -NoProfile`
- `terminal.integrated.automationProfile.windows=PowerShell -NoProfile`

目的是减少 PowerShell Profile 干扰，并让调试控制台、任务终端和自动化终端的行为尽量一致。

### 运行时你会看到什么

运行期间你会同时有两类输出位置：

- 调试控制台：用于 `F5` / 调试配置启动时看日志和报错
- 终端面板：用于 `Run Task` 时看完整终端输出

日志文件仍会额外写到 `log/etf_strategy_YYYY-MM-DD.log`，用于更细的排错。

当前常见提示包括：

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
