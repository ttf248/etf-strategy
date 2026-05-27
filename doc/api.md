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
- `GET /api/platform/processes`
- `GET /api/platform/logs`
- `POST /api/platform/processes/{service_name}/restart`

平台控制面接口用于前端总控页聚合 API、Frontend、数据库、Worker、Scheduler、任务队列、同步调度和最近日志。进程重启接口默认返回 `403`，只有设置 `ETF_STRATEGY_ENABLE_PROCESS_CONTROL=true` 后才允许进入受控流程；当前不会默认开放 Web 端杀进程能力。

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
- `interval`：默认 `1d`。
- `proxy`：可选代理。
- `period`：分钟线窗口，例如 `60d` 或 `7d`。

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

当前内置策略类型包括 `grid`、`dca`、`daily_rebound`、`minute_rebound`、`minute_rebound_with_fade_filter` 和 `minute_index_grid_retrace`。其中 `dca` 仅支持日线周期。

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
