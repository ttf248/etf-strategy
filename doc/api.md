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
- `GET /api/market-data/bars`
- `GET /api/market-data/sync-runs`
- `POST /api/market-data/sync`

这些接口用于查询标的、行情覆盖、统计信息、K 线数据、同步历史，以及手动触发行情同步。

`POST /api/market-data/sync` 支持字段：

- `symbol`：可选；为空时同步数据库中已知标的。
- `provider`：默认 `yahoo`；也可传 `tdx`。
- `interval`：默认 `1d`。
- `proxy`：可选代理。
- `period`：分钟线窗口，例如 `60d` 或 `7d`。
- `vipdoc_path`：通达信 `vipdoc` 根目录；仅 `provider=tdx` 时使用。
- `force`：是否忽略文件 manifest 强制重建；仅 `provider=tdx` 时使用。
- `limit`：限制文件数量；仅 `provider=tdx` 时使用。

当前返回体除了旧版 `run_id / bars_inserted / bars_updated`，还会附带统一任务域的 `ingestion_job_id / series_bars_inserted / series_bars_updated`，便于后续前端切换到多数据源任务面板。

当前 `provider=tdx` 只支持原始 `1d` 日线导入。分钟线、公司行动与前复权重算会继续沿同一任务域扩展。

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
