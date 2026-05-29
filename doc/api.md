# API 接口说明

后端使用 FastAPI，默认地址为：

```text
http://127.0.0.1:8000
```

交互式文档由 FastAPI 自动提供：

```text
http://127.0.0.1:8000/docs
```

## Health

- `GET /health`

用于确认 API 进程可用。正常返回 `{"status":"ok"}`。

## Platform

- `GET /api/platform/status`
- `GET /api/platform/database-check`
- `GET /api/platform/processes`
- `GET /api/platform/logs`
- `POST /api/platform/processes/{service_name}/restart`

平台控制面接口用于前端总控页聚合 API、Frontend、数据库、Worker、Scheduler、任务队列、同步调度和最近日志。`GET /api/platform/database-check` 会额外返回目标数据库是否存在、当前 Alembic 版本、代码头版本和表概览，便于排查“实例可达但业务库不存在”或“数据库未迁移到最新版本”这类问题。进程重启接口默认返回 `403`，只有设置 `STRATEGY_STUDIO_ENABLE_PROCESS_CONTROL=true` 后才允许进入受控流程；当前不会默认开放 Web 端杀进程能力。

## Market Data

- `GET /api/market-data/instruments`
- `GET /api/market-data/coverages`
- `GET /api/market-data/stats`
- `GET /api/market-data/provider-series`
- `GET /api/market-data/ingestion-jobs/{job_id}`
- `GET /api/market-data/bars`
- `GET /api/market-data/sync-runs`
- `POST /api/market-data/sync`

这些接口用于查询标的、行情覆盖、统计信息、导入任务详情、K 线数据、同步历史，以及手动触发行情同步。其中 `GET /api/market-data/stats` 当前除了保留旧 `coverages / recent_sync_runs` 外，还会返回：

- `provider_summaries`：按 provider 聚合的多渠道摘要，包含 `series_count / bars_count / action_count / segment_count / manifest_count / latest_ingestion_at / latest_ingestion_status` 等字段，供 `/market-data` 多渠道任务面板直接渲染。
- `recent_ingestion_jobs`：统一导入任务域的最近任务列表，覆盖 Yahoo、A 股统一补数链路、通达信原始、Tushare 公司行动和通达信前复权五类后台任务。每条记录还会附带 `summary_json`，用于前端直接展开 workflow 子步骤、文件导入摘要或其他渠道专属诊断信息。

`GET /api/market-data/provider-series` 用于直接检查统一主干表里的实际序列结果，默认按最近入库时间倒序返回最近 100 条，也支持：

- `provider`：可选；传 `yahoo`、`tdx`、`tushare`、`tdx_qfq`、`tdx_pipeline` 对应的底层落库渠道，传 `all` 或留空表示不过滤。
- `limit`：可选；限制返回条数，便于前端仅展示最近一批真实落库序列。

返回项当前包含：

- 序列主键与 provider 信息：`series_id / provider_key / provider_name`
- 标的与映射信息：`instrument_symbol / instrument_name / source_symbol / market / exchange`
- 序列口径：`interval / adjustment_kind / session_type / price_type / bar_type / currency / timezone`
- 序列状态：`bar_count / first_bar_time / last_bar_time / last_ingested_at / is_active`

`GET /api/market-data/ingestion-jobs/{job_id}` 返回单个统一导入任务的完整详情，包含：

- 任务级字段：`provider_key / job_type / status / target_scope_json / options_json / summary_json / error_message`
- 子项明细：`items[]`，逐条返回 `item_key / source_symbol / instrument_symbol / interval / stage / status / rows_inserted / rows_updated / error_message / details_json`

`POST /api/market-data/sync` 支持字段：

- `symbol`：可选；`provider=yahoo` 为空时同步数据库中已知标的；`provider=tushare`、`provider=tdx_qfq` 和 `provider=tdx_pipeline` 当前建议显式传单个标的。
- `symbol_set`：可选；当前主要给 `provider=yahoo` 使用，例如 `yahoo_global_active_100`。
- `provider`：默认 `yahoo`；也可传 `tdx`、`tdx_pipeline`、`tushare`、`tdx_qfq`。
- `interval`：默认 `1d`；`provider=tdx` 还支持 `all`，表示顺序导入 `1d / 1m / 5m`；`provider=tdx_pipeline` 支持 `1d` 或 `all`，分别对应“日线链路”和“全周期原始导入 + 公司行动 + 前复权”。
- `proxy`：可选代理。
- `period`：分钟线窗口，例如 `60d` 或 `7d`。
- `vipdoc_path`：通达信 `vipdoc` 根目录；`provider=tdx` 和 `provider=tdx_pipeline` 会使用它解析本地原始行情。
- `force`：是否忽略文件 manifest 强制重建；`provider=tdx` 和 `provider=tdx_pipeline` 时生效。
- `limit`：`provider=yahoo` 时限制 `symbol_set` 或已知标的数量；`provider=tdx` 时限制本次扫描到的 `1d / 1m / 5m` 文件数量；若 `interval=all`，当前按每个 TDX 周期各自套用同一个 `limit`；`provider=tushare`、`provider=tdx_qfq` 或 `provider=tdx_pipeline` 时限制抓取股票数。当前 `provider=tushare` 未传 `symbol` 时必须提供 `limit`，避免误触发全市场全量抓取。

当前返回体除了旧版 `run_id / bars_inserted / bars_updated`，还会附带统一任务域的 `ingestion_job_id / series_bars_inserted / series_bars_updated`。其中 `provider=tushare` 会把“事件条数”复用到 `bars_inserted / bars_updated` 字段，并额外返回 `events_deleted / fetched_rows / implemented_rows`；`provider=tdx_qfq` 会额外返回 `segment_rows_inserted / segment_rows_updated / segment_rows_deleted / action_rows_used`；`provider=tdx_pipeline` 会返回 workflow 总任务 `ingestion_job_id`、子任务 `child_ingestion_job_ids` / `ingestion_job_ids` 以及逐步骤的 `workflow_results`，便于前端直接展示统一链路状态。

当前 `provider=yahoo` 已支持通过 `symbol_set=yahoo_global_active_100` 导入内置 100 个全球高活跃样本；若同步失败，返回体会附带 `status` 和统一任务 `error_message`。`provider=tdx` 当前支持原始 `1d / 1m / 5m` 导入，分别对应 `.day`、`.lc1/.1`、`.lc5/.5` 文件，并共用同一套 `source_file_manifests` 增量状态；若传 `interval=all`，服务会顺序编排三个 TDX 周期，并在返回体中给出聚合统计与子任务 `ingestion_job_ids`。`provider=tdx_pipeline` 会再向上封装一层 workflow：`interval=1d` 时执行 `tdx 1d -> tushare -> tdx_qfq 1d`，`interval=all` 时执行 `tdx all -> tushare -> tdx_qfq 1d`。当 workflow 以批量模式运行且未显式传 `symbol` 时，后两步会自动跟随数据库中已有的通达信原始 `1d` 标的集，而不是退回到 Tushare 的独立默认样本口径，并把 workflow 自身与所有子任务都记入统一任务域；`provider=tushare` 只支持 `dividend` 公司行动抓取，并且只把已有 `ex_date` 的实施事件写入 `corporate_action_events`；`provider=tdx_qfq` 只支持基于数据库中现有的通达信原始 `1d` 日线和 Tushare 公司行动重算前复权 `1d` 日线。

## Backtests

- `POST /api/backtests`
- `GET /api/backtests`
- `GET /api/backtests/{job_id}`
- `POST /api/backtests/{job_id}/retry`
- `POST /api/backtests/{job_id}/cancel`
- `POST /api/backtests/bulk-retry`
- `POST /api/backtests/bulk-cancel`

回测提交接口只负责入队。实际执行由 Worker 完成。

主要请求字段：

- `symbol`：必填，Yahoo 标的代码。
- `interval`：可选，默认由模板或服务默认值决定。
- `strategy_kind`：可选，策略类型。
- `template_id`：可选，引用参数模板。
- `parameter_space`：可选，覆盖或补充模板参数空间。
- `execution_profile` 和费用/风控字段：可选，控制实盘化回测口径。

当前内置策略类型包括 `grid`、`dca`、`ma_cross`、`macd_trend`、`donchian_breakout`、`volume_breakout`、`bollinger_reversion`、`daily_rebound`、`minute_rebound`、`minute_rebound_with_fade_filter` 和 `minute_index_grid_retrace`。其中 `dca`、`ma_cross`、`macd_trend`、`donchian_breakout`、`volume_breakout` 与 `bollinger_reversion` 仅支持日线周期。

取消任务时，`queued` 任务会直接变为 `cancelled`；`running` 任务会先变为 `cancel_requested`，由 Worker 在安全检查点停止并落为 `cancelled`。

## Reports

- `GET /api/reports`
- `GET /api/reports/{report_id}`

报告接口返回结构化指标、参数、权益曲线、成交和事件数据，用于前端展示历史回测报告。

## Templates

- `GET /api/templates`
- `GET /api/templates/{template_id}`
- `POST /api/templates`
- `PATCH /api/templates/{template_id}`

参数模板用于保存策略、周期、执行口径和寻参空间。提交回测时引用模板，会在入队时生成请求快照，保证历史任务可复现。

## 错误处理

- 参数校验失败通常返回 `400`。
- 资源不存在返回 `404`。
- 后端进程级异常会写入日志，前端只展示接口返回的错误信息。
