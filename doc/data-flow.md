# 数据流转

本平台的数据链路围绕 PostgreSQL 设计。CSV 只作为导入或离线研究输入，平台报告不再以本地 Markdown 作为长期主存储。

## 行情进入系统

行情有两种来源：

- Yahoo 同步：通过 `sync-now`、Scheduler 或前端同步按钮触发。
- CSV 导入：通过 `import-csv` 把临时整理在 `data/processed/` 下的标准化历史文件导入数据库。

标准流程：

```text
Yahoo / CSV
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

报告有两种表现形式：

- 结构化报告：存储在 PostgreSQL，供前端查询和绘图。
- 文件报告：只有在显式传入导出目录时，CLI 研究工作流才会临时生成 Markdown、图片和 CSV，适合离线阅读，但不再作为平台长期事实来源。

`reports/platform/` 默认视为运行产物，不纳入版本控制。平台 worker 执行回测时只写数据库，不再落地本地 Markdown 报告。

## 数据边界

- 日线可以下载 Yahoo 可提供的长期历史。
- 分钟线受 Yahoo 免费数据窗口限制，常见周期只能获取较近区间。
- 代理配置由命令参数或环境变量提供，平台不会静默切换数据源。
- 所有行情和回测结果都以下载或导入时的数据快照为准，不代表实时行情。
