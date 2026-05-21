# ETF Strategy

基于 Yahoo Finance 数据的小型策略回测项目。仓库当前保留两条研究主线：

- 现有固定股数纯现金网格
- 面向 `1810.HK` 的日线/分钟线多策略对比研究

所有 Yahoo 下载命令必须配置代理，Yahoo 下载失败时流程会直接停止并输出错误。

## 报告索引

| 分类 | 标的 | 名称 | 周期 | 样本外收益 | 最大回撤 | 状态/备注 | 报告 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 汇总索引 | all_reports | 单标的、批量、多策略对比统一汇总 | 多周期 | 见索引 | 见索引 | 唯一正式入口，所有新增报告都会回写到 `reports/` 根目录这份总表 | [打开索引](reports/report_index.md) |
| 默认样本 | 1810.HK | 小米集团-W 分钟多策略对比 | 15m | 见报告 | 见报告 | 默认优先阅读入口 | [打开报告](reports/1810_hk/minute/1810_hk_15m_strategy_compare_report.md) |
| 默认样本 | 1810.HK | 小米集团-W 日线多策略对比 | 1d | 见报告 | 见报告 | 日线左侧反弹专项研究 | [打开报告](reports/1810_hk/daily/1810_hk_daily_strategy_compare_report.md) |
| 基线报告 | 1810.HK | 小米集团-W 网格分钟报告 | 15m | 见报告 | 见报告 | 保留作对照基准 | [打开报告](reports/1810_hk/minute/1810_hk_15m_grid_report.md) |
| 方法文档 | - | 参数筛选方法说明 | - | - | - | 解释寻参和稳健性评分 | [打开文档](doc/grid_parameter_search.md) |
| 专题文档 | - | 小米多策略研究说明 | - | - | - | 汇总日线与分钟线结论 | [打开文档](doc/xiaomi_strategy_research.md) |
| 阅读指南 | - | 回测报告阅读指南 | - | - | - | 解释报告图表与指标 | [打开文档](doc/report_reading_guide.md) |

这个仓库现在的定位不是“一次性脚本”，而是“可重复运行的策略研究工程”：

- 所有命令统一从根目录 `main.py` 进入
- 数据链路只使用 Yahoo Finance；下载必须配置代理，失败后直接停止，避免静默切换数据源导致口径不一致
- 同时输出中间结果、图表、交易记录和中文报告，方便复盘
- 回测命令默认使用 `realistic` 执行口径，计入可配置的手续费、滑点、仓位上限、停手机制和左侧行情强制退出对照
- 批量入口默认支持恒生科技 30 只成分股和 `513050.SS` 的分钟线研究
- 仓库也内置上交所官方港股通沪名单快照，可直接批量研究当前 `633` 只合资格港股与 ETF

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

- 日线显式回测输入快照
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

### 2. 直接生成 15 分钟线多策略报告

```powershell
py -3.13 main.py report --data data/processed/1810_hk_15m.csv --symbol 1810.HK --interval 15m --compare-strategies --jobs auto --cache-dir outputs/cache/minute_compare
```

输出：

- 中间结果：`outputs/compare/minute/`
- 正式报告：`reports/1810_hk/minute/1810_hk_15m_strategy_compare_report.md`

### 2.1 生成日线多策略报告

```powershell
py -3.13 main.py report --data data/processed/1810_hk_daily.csv --symbol 1810.HK --interval 1d --compare-strategies --jobs auto --cache-dir outputs/cache/daily_compare
```

输出：

- 中间结果：`outputs/compare/daily/`
- 正式报告：`reports/1810_hk/daily/1810_hk_daily_strategy_compare_report.md`

### 3. 批量生成恒生科技分钟线报告

```powershell
py -3.13 main.py batch --symbol-set hstech_plus_513050 --download --proxy http://127.0.0.1:7897 --jobs auto --cache-dir outputs/cache
```

输出：

- 批量汇总：`outputs/batch/batch_summary.csv`
- 统一汇总报告：`reports/report_index.md`
- 单标的报告：`reports/<symbol>/minute/`

### 3.1 批量生成港股通沪日线网格报告

```powershell
py -3.13 main.py batch --symbol-set southbound_shanghai_all --interval 1d --download --proxy http://127.0.0.1:7897 --jobs auto --cache-dir outputs/cache/southbound_daily
```

### 3.2 批量生成港股通沪 15 分钟网格报告

```powershell
py -3.13 main.py batch --symbol-set southbound_shanghai_all --interval 15m --download --proxy http://127.0.0.1:7897 --jobs auto --cache-dir outputs/cache/southbound_15m
```

补充说明：

- `southbound_shanghai_all` 使用仓库内置的上交所官方快照 `data/reference/southbound_shanghai_eligible_snapshot.csv`
- 当前快照更新日：`2026-05-21`
- 统一汇总报告里，样本外净收益率高于 `5%` 的记录会加粗，方便先看高收益候选

## 文档导航

总导航：

- [项目导航与阅读顺序](doc/index.md)

结果阅读：

- [回测报告阅读指南](doc/report_reading_guide.md)
- [术语表与口径说明](doc/glossary.md)

专题说明：

- [日线网格参数测试方法](doc/grid_parameter_search.md)
- [Yahoo 分钟线支持与 15 分钟回测说明](doc/minute_grid_research.md)
- [小米多策略研究说明](doc/xiaomi_strategy_research.md)

维护者入口：

- [开发与维护说明](doc/development_guide.md)

## 常用命令速查

### 下载默认分钟线数据

```powershell
py -3.13 main.py download --symbol 1810.HK --proxy http://127.0.0.1:7897
```

说明：

- 默认周期是 `15m`
- 分钟线免费数据通常只有最近 `60d`；如果 Yahoo 返回限流、空数据或连接错误，流程会直接停止并输出报错
- 项目会先把这次下载结果和本地 `data/processed/1810_hk_15m.csv` 做时间戳合并，再进入后续回测

### 下载日线数据

如果你要显式下载日线，传 `--interval 1d`：

```powershell
py -3.13 main.py download --symbol 1810.HK --interval 1d --proxy http://127.0.0.1:7897
```

如果你只想下载某一段日线区间，也可以显式传：

```powershell
py -3.13 main.py download --symbol 1810.HK --interval 1d --start 2024-01-01 --end 2026-05-22 --proxy http://127.0.0.1:7897
```

### 样本内参数搜索

```powershell
py -3.13 main.py optimize --data data/processed/1810_hk_15m.csv --symbol 1810.HK --strategy minute_rebound
```

### 样本外验证

```powershell
py -3.13 main.py backtest --data data/processed/1810_hk_15m.csv --symbol 1810.HK --grid-spacing 0.04 --grid-count 7 --take-profit 0.01
```

### 执行口径与风控参数

`optimize`、`backtest`、`report`、`run` 默认使用更接近实盘的口径：

- `--execution-profile realistic`
- 默认计入手续费、滑点、最大仓位占用和止损停手
- 默认是纯现金网格：样本起点不买入，只把第一根 K 线收盘价作为网格锚点
- 默认同时计算 `hold` 和 `force_exit` 两种左侧行情口径：前者持有未平网格，后者在未平网格浮亏达到阈值后强制卖出并停止交易
- 报告会同时对比网格、现金闲置和买入持有

如果需要复现旧的简化研究口径，可以显式传：

```powershell
py -3.13 main.py report --data data/processed/1810_hk_15m.csv --symbol 1810.HK --execution-profile research
```

常用覆盖参数：

- `--strategy`：`grid`、`daily_rebound`、`minute_rebound`、`minute_rebound_with_fade_filter`
- `--compare-strategies`：在当前周期下同时输出多策略对比报告
- `--commission-bps`：单边手续费，单位 bps
- `--slippage-bps`：单边滑点，单位 bps
- `--max-position-ratio`：最大仓位占总资金比例，例如 `0.95`
- `--stop-loss-pct`：触发停止新增网格的跌幅，例如 `0.2`
- `--cooldown-bars`：触发停手后的冷却 K 线数量
- `--grid-mode`：当前支持 `cash`，表示不预先建仓的现金网格
- `--left-side-policy`：`hold`、`force_exit` 或 `both`
- `--force-exit-loss-pct`：强制退出阈值，例如 `0.05` 表示未平网格浮亏达到总资金 5% 后清仓
- `--jobs`：寻参并行线程数，可传整数或 `auto`
- `--cache-dir`：候选参数回测缓存目录，适合反复调报告模板时复用

### 一键执行完整流程

```powershell
py -3.13 main.py run --symbol 1810.HK --proxy http://127.0.0.1:7897
```

如果你希望跑日线完整流程，显式传 `--interval 1d`。如果你希望限定这次日线完整流程只使用某个时间段，也可以同时传 `--start` 和 `--end`。

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

- 一键生成恒科批量分钟报告
- 一键生成 1810 分钟多策略报告

其中 1810 单标的入口直接基于仓库内置正式样本重算多策略报告；恒科批量入口会先下载 Yahoo 分钟线，因此必须配置代理。

- 单标的报告入口不依赖 Yahoo 网络连接
- 批量下载入口必须确保本机 `http://127.0.0.1:7897` 代理可用，或按需修改 `launch.json` 中的 `--proxy`
- Yahoo 下载失败时，批量流程会直接停止并输出错误

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

### 批量研究多个标的

如果本地已经有对应标准化 CSV，可以批量运行：

```powershell
py -3.13 main.py batch --symbol-set hstech_plus_513050 --download --proxy http://127.0.0.1:7897 --jobs auto --cache-dir outputs/cache
```

输出：

- 批量汇总：`outputs/batch/batch_summary.csv`
- 统一汇总报告：`reports/report_index.md`
- 单标的中间结果：`outputs/batch/<symbol>/`
- 单标的报告：`reports/<symbol>/minute/`

也可以把 `--symbol-set` 换成：

- `southbound_shanghai_all`：上交所官方港股通沪全量名单，当前 `633` 只（`602` 股票 + `31` ETF）

如果希望批量运行前先下载并合并行情，加上 `--download`。批量入口仍然只做研究回测，不做实盘下单。

## 验证

```powershell
py -3.13 -m unittest tests.test_grid_strategy tests.test_repo_contracts tests.test_yahoo_data
```
