# 数据流转

本平台的数据链路围绕 PostgreSQL 设计。平台报告不再以本地 Markdown 作为长期主存储。

## 行情进入系统

当前自动同步主链路有三类正式来源：

- Yahoo 同步：通过 `sync-now`、Scheduler 或前端同步按钮触发。
- 通达信原始导入：通过 `sync-now --provider tdx` 或后续统一任务面板触发。
- Tushare 公司行动抓取：通过 `sync-now --provider tushare` 或后续统一任务面板触发。
- 通达信前复权重算：通过 `sync-now --provider tdx_qfq` 或后续统一任务面板触发。

标准流程：

```text
Yahoo
    |
    v
标准化 K 线
    |
    v
instruments + price_bars
    |
    v
行情统计 / 回测读取
```

`price_bars` 使用 `instrument_id + interval + bar_time` 唯一约束，重复导入会更新已有 K 线，不会生成重复记录。

当前 Yahoo 同步除了单标的外，还支持 `symbol_set=yahoo_global_active_100` 批量样本池。前端 `/market-data` 的 Yahoo 批量任务和 CLI `sync-now --provider yahoo --symbol-set yahoo_global_active_100` 走的是同一套入口；若网络环境要求代理，统一任务会在 `data_ingestion_jobs` 中保留失败状态和首个错误原因。

通达信当前已接通的原始行情链路为：

```text
vipdoc/*.day / *.lc1 / *.1 / *.lc5 / *.5
    |
    v
二进制解析 + 周期识别
    |
    v
market_data_series(provider=tdx, adjustment_kind=raw, interval=1d/1m/5m)
    |
    v
market_data_bars + source_file_manifests + data_ingestion_jobs
```

同一文件再次导入时，会先比较 `source_size / source_mtime / record_count / tail_hash`；未变化则跳过，严格尾部增长时走安全增量窗口。

Tushare 当前已接通的链路为：

```text
Tushare dividend API
    |
    v
ts_code -> instrument/alias 映射
    |
    v
只保留已有 ex_date 的实施事件
    |
    v
corporate_action_events + data_ingestion_jobs
```

当前抓取按单个 `ts_code` 全量覆盖写入。这样即使源端修订了某次分红送转的日期或数值，也不会在库里留下陈旧事件。

通达信前复权当前已接通的链路为：

```text
market_data_series(provider=tdx, adjustment_kind=raw, interval=1d)
    +
corporate_action_events(provider=tushare)
    |
    v
price_adjustment_segments(provider=tdx_qfq, adjustment_kind=qfq)
    |
    v
market_data_series(provider=tdx_qfq, adjustment_kind=qfq, interval=1d)
    |
    v
market_data_bars + data_ingestion_jobs
```

当前前复权算法沿用外部 C++ 版本的核心思路：先把公司行动合并成日期级仿射事件，再反向预计算后缀 `A/B`，最后用连续区间映射整段日线，避免每条 K 线重复扫描全部事件。

为后续接入通达信和 Tushare，数据库已预留多数据源基础结构：

- `data_providers`：渠道注册。
- `instrument_aliases`：同一标的在不同渠道中的代码映射。
- `market_data_series` / `market_data_bars`：统一 K 线事实表。
- `corporate_action_events`：公司行动事实表。
- `price_adjustment_segments`：前复权公式区间。
- `source_file_manifests`：文件型来源的增量状态。
- `data_ingestion_jobs` / `data_ingestion_job_items`：统一后台任务状态。

这些表当前已接通 Yahoo 原始 K 线、通达信原始 `1d / 1m / 5m`、Tushare 公司行动和通达信前复权日线四条子链路；前端 `/market-data` 也已经接入统一任务面板，可直接查看 provider 摘要和最近导入任务。

## 同步记录

每次 Yahoo 同步会写入：

- `data_sync_runs`：一次同步任务的总体状态。
- `data_sync_run_items`：每个标的的同步结果。

这些记录用于前端查看最近同步状态，也用于排查代理、限流、空数据和单标的失败。

## 回测任务流

前端或 API 提交回测后，后端不在请求内直接执行耗时计算，而是写入队列表：

```text
POST /api/backtests
    |
    v
backtest_jobs(status=queued)
    |
    v
Worker poll
    |
    v
读取 price_bars -> 执行策略工作流 -> 写报告表
```

Worker 执行完成后写入：

- `backtest_reports`：报告元数据、指标、参数和产物索引。
- `backtest_equity_curves`：权益曲线和回撤。
- `backtest_trades`：成交记录。
- `backtest_events`：策略事件。

## 参数模板流

参数模板保存在 `strategy_parameter_templates`。提交回测时可以传 `template_id`，服务层会把模板默认值、请求覆盖值和参数空间合并为最终请求快照。

设计目标是保证历史任务可复现：模板后续被修改，不应改变已经提交任务的真实执行参数。

## 报告流

报告只保留一种正式表现形式：

- 结构化报告：存储在 PostgreSQL，供前端查询和绘图。

平台 worker 执行回测时只写数据库，不再落地本地 Markdown 报告。

## 数据边界

- 日线可以下载 Yahoo 可提供的长期历史。
- 分钟线受 Yahoo 免费数据窗口限制，常见周期只能获取较近区间。
- 代理配置由命令参数或环境变量提供，平台不会静默切换数据源。
- 所有行情和回测结果都以下载或导入时的数据快照为准，不代表实时行情。
