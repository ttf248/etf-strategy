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

`GET /api/platform/status` 当前除了 API / Frontend / Database / Heartbeats / Queue / Sync Schedule 外，还会返回：

- `market_data_runtime.yahoo`：Yahoo 默认样本池、三周期 workflow、项目显式代理配置状态，以及 Windows 下可探测到的系统代理候选与提示信息。
- `market_data_runtime.tdx`：`STRATEGY_STUDIO_TDX_VIPDOC` 或 `STRATEGY_STUDIO_TDX_CONFIG_PATH` 解析出的 `vipdoc` 路径、来源、是否存在、第一层市场目录摘要，以及按 `1d / 1m / 5m` 和市场目录汇总的可见 K 线文件数。
- `market_data_runtime.tushare`：Tushare 配置文件、token 是否存在、来源、限速、超时和重试参数。

这些字段用于前端 `/platform` 维护页直接判断“数据库、TDX 路径、Tushare 凭据是否已经具备触发多数据源导入任务的前提”，避免必须先跑任务再从失败结果倒推配置问题。

## Market Data

- `GET /api/market-data/instruments`
- `GET /api/market-data/coverages`
- `GET /api/market-data/stats`
- `GET /api/market-data/provider-series`
- `GET /api/market-data/symbol-diagnostics`
- `GET /api/market-data/corporate-actions`
- `GET /api/market-data/adjustment-segments`
- `GET /api/market-data/source-file-manifests`
- `GET /api/market-data/ingestion-jobs/{job_id}`
- `GET /api/market-data/bars`
- `GET /api/market-data/sync-runs`
- `POST /api/market-data/sync`
- `POST /api/market-data/ingestion-jobs/{job_id}/retry`
- `POST /api/market-data/ingestion-jobs/{job_id}/cancel`

这些接口用于查询标的、行情覆盖、统计信息、导入任务详情、K 线数据、同步历史，以及手动触发行情同步。其中 `GET /api/market-data/stats` 当前除了保留旧 `coverages / recent_sync_runs` 外，还会返回：

- `backtest_coverages / backtest_instrument_count / backtest_total_bars / backtest_by_interval`：面向自动回测主路径的覆盖统计。选择规则与 Worker 读取链路保持一致：若旧 `price_bars` 已覆盖，则优先沿用旧表；否则只在统一主干表 `market_data_series + market_data_bars` 中同标的同周期存在唯一可用序列时，才把该序列纳入首页、推荐样本和默认回测候选。若同一标的同周期同时存在多条统一序列候选，则不会进入自动推荐，调用方应改为显式指定 `market_data_provider / market_data_adjustment_kind`。
- `provider_summaries`：按 provider 聚合的多渠道摘要，包含 `series_count / bars_count / action_count / segment_count / manifest_count / latest_ingestion_at / latest_ingestion_status` 等字段，供 `/market-data` 多渠道任务面板直接渲染。
- `recent_ingestion_jobs`：统一导入任务域的最近任务列表，覆盖 Yahoo 单周期、Yahoo 三周期链路、A 股统一补数链路、通达信原始、Tushare 公司行动和通达信前复权六类后台任务。每条记录还会附带 `summary_json`，用于前端直接展开 workflow 子步骤、文件导入摘要或其他渠道专属诊断信息。

`backtest_coverages[]` 的单条记录在旧覆盖字段基础上还会附带：

- `market_data_provider`：当前自动回测口径最终选中的 provider，例如 `yahoo`、`tdx`、`tdx_qfq`。
- `market_data_adjustment_kind`：当前序列的复权口径，例如 `raw`、`qfq`。
- `backtest_source_kind`：当前候选来自旧 `legacy_price_bars`，还是统一主干表 `market_data_series`。

`GET /api/market-data/provider-series` 用于直接检查统一主干表里的实际序列结果，默认按最近入库时间倒序返回最近 100 条，也支持：

- `provider`：可选；传 `yahoo`、`tdx`、`tushare`、`tdx_qfq`、`tdx_pipeline` 对应的底层落库渠道，传 `all` 或留空表示不过滤。
- `symbol`：可选；传统一标的代码或源代码，例如 `SH600000`，用于把序列检查聚焦到单个标的。
- `limit`：可选；限制返回条数，便于前端仅展示最近一批真实落库序列。

返回项当前包含：

- 序列主键与 provider 信息：`series_id / provider_key / provider_name`
- 标的与映射信息：`instrument_symbol / instrument_name / source_symbol / market / exchange`
- 序列口径：`interval / adjustment_kind / session_type / price_type / bar_type / currency / timezone`
- 序列状态：`bar_count / first_bar_time / last_bar_time / last_ingested_at / is_active`
- 元数据摘要：`metadata_summary`，其中会收敛 `source_period / source_file / raw_provider_key / raw_series_id / action_provider_key / raw_frame_digest / segment_frame_digest / adjusted_frame_digest`，便于前端直接诊断通达信原始链路与前复权派生链路的依赖关系。

`GET /api/market-data/symbol-diagnostics` 用于围绕单个标的一次性聚合全链路排查结果，当前会把统一序列、最近公司行动、最近复权区间、最近通达信文件 manifest 和最近相关导入任务一起返回。支持：

- `symbol`：必填；统一标的代码，例如 `sh600000`。
- `limit`：可选；限制每个子列表返回条数，默认 20。

返回体当前包含：

- 标的概览：`symbol / instrument_name / exchange`
- 汇总计数：`summary.series_count / summary.corporate_action_count / summary.adjustment_segment_count / summary.manifest_count / summary.recent_job_count / summary.qfq_series_count / summary.qfq_normal_skip_ready_count / summary.qfq_force_cache_ready_count`
- 序列列表：`series_rows[]`
- 公司行动列表：`corporate_action_rows[]`
- 复权区间列表：`adjustment_segment_rows[]`
- Manifest 列表：`source_file_manifest_rows[]`
- 最近相关任务：`recent_ingestion_jobs[]`
- 前复权派生链路诊断：`qfq_series_diagnostics[]`，逐条返回 `raw_provider_key / raw_series_id / raw_last_ingested_at / action_provider_key / latest_action_updated_at / normal_skip_ready / force_skip_cache_ready / *_digest / *_reasons`，用于直接判断该标的的 `tdx_qfq` 是否已经最新、以及重复 `--force` 时是否具备跳过区间/K 线写回的缓存条件。

`GET /api/market-data/corporate-actions` 用于直接检查 `corporate_action_events` 中的实施事件，默认按 `ex_date` 倒序返回最近 100 条，也支持：

- `provider`：可选；当前主要是 `tushare`，传 `all` 或留空表示不过滤。
- `symbol`：可选；支持按统一标的代码或源代码过滤，例如 `sh600000`。
- `limit`：可选；限制返回条数。

返回项当前包含：

- 事件主键与 provider 信息：`event_id / provider_key / provider_name`
- 标的与源代码：`instrument_symbol / instrument_name / source_symbol`
- 事件口径：`action_type / announce_date / record_date / ex_date / pay_date / end_date`
- 数值字段：`cash_dividend / stock_bonus_ratio / stock_conversion_ratio / rights_ratio / rights_price`
- 状态字段：`status / ingested_at / updated_at`

`GET /api/market-data/adjustment-segments` 用于直接检查 `price_adjustment_segments` 中的前复权公式区间，默认按最近更新时间倒序返回最近 100 条，也支持：

- `provider`：可选；当前主要是 `tdx_qfq`，传 `all` 或留空表示不过滤。
- `symbol`：可选；按统一标的代码过滤，例如 `sh600000`。
- `limit`：可选；限制返回条数。

返回项当前包含：

- 区间主键与 provider 信息：`segment_id / provider_key / provider_name`
- 标的与口径：`instrument_symbol / instrument_name / adjustment_kind`
- 公式区间：`start_date / end_date / adjust_a / adjust_b / status`
- 来源与审计字段：`action_provider_name / payload_json / generated_at / updated_at`

其中 `payload_json` 当前除了 `source / reason / event_count` 外，还会额外记录：

- `source_hash`：该区间会应用的后续公司行动摘要 hash，便于判断“这段公式到底来自哪批事件”。

`GET /api/market-data/source-file-manifests` 用于直接检查 `source_file_manifests` 中的文件增量状态，默认按最近更新时间倒序返回最近 100 条，也支持：

- `provider`：可选；当前主要是 `tdx`，传 `all` 或留空表示不过滤。
- `symbol`：可选；支持按统一标的代码过滤，例如 `sh600000`，也会同时尝试匹配 `source_path`。
- `interval`：可选；支持 `1d / 1m / 5m`。
- `limit`：可选；限制返回条数。

返回项当前包含：

- Manifest 主键与 provider 信息：`manifest_id / provider_key / provider_name`
- 关联对象：`instrument_symbol / instrument_name / series_id`
- 文件与周期：`source_path / file_kind / market / interval`
- 文件状态：`source_size / source_mtime / record_count / tail_hash / status / last_bar_time`
- 导入附加信息：`payload_json / updated_at`

`GET /api/market-data/ingestion-jobs/{job_id}` 返回单个统一导入任务的完整详情，包含：

- 任务级字段：`provider_key / job_type / status / target_scope_json / options_json / summary_json / error_message`
- 子项明细：`items[]`，逐条返回 `item_key / source_symbol / instrument_symbol / interval / stage / status / rows_inserted / rows_updated / error_message / details_json`

当任务来自 `provider=tdx_qfq` 时，当前还会额外暴露两组排查字段：

- `summary_json.timing_json`：批量前复权重算的阶段耗时，例如 `preload_input_ms / segment_build_ms / segment_replace_ms / segment_apply_ms / bar_upsert_ms / total_elapsed_ms`。
- `items[].details_json`：单标的前复权子项的 `reason / normal_skip_reasons / force_skip_reasons / *_digest / segment_source_hashes / timing_json`，用于直接判断该标的是“因为已最新而跳过”“因为 `--force` 命中缓存而跳过写回”，还是确实发生了区间重建与 K 线写回。

`POST /api/market-data/sync` 支持字段：

- `symbol`：可选；`provider=yahoo` 为空时同步数据库中已知标的；`provider=tushare`、`provider=tdx_qfq` 和 `provider=tdx_pipeline` 当前建议显式传单个标的。
- `symbol_set`：可选；当前主要给 `provider=yahoo` 使用，例如 `yahoo_global_active_100`。
- `provider`：默认 `yahoo`；也可传 `yahoo_pipeline`、`tdx`、`tdx_pipeline`、`tushare`、`tdx_qfq`。
- `interval`：默认 `1d`；`provider=yahoo_pipeline` 固定使用 `all`，表示顺序同步 `1d / 15m / 1m`；`provider=tdx` 还支持 `all`，表示顺序导入 `1d / 1m / 5m`；`provider=tdx_pipeline` 支持 `1d` 或 `all`，分别对应“日线链路”和“全周期原始导入 + 公司行动 + 前复权”。
- `proxy`：可选代理。
- `period`：分钟线窗口，例如 `60d` 或 `7d`。
- `vipdoc_path`：通达信 `vipdoc` 根目录；`provider=tdx` 和 `provider=tdx_pipeline` 会使用它解析本地原始行情。
- `force`：是否忽略文件 manifest 强制重建；`provider=tdx` 和 `provider=tdx_pipeline` 时生效。
- `batch_rounds`：可选；当前只支持 `provider=tdx` 的批量原始导入模式，且要求未传 `symbol`、未传 `force`，并显式传入 `limit`。服务会在同一请求里连续执行多轮批量导入，直到达到轮数上限，或当前范围已经没有待导文件。
- `limit`：`provider=yahoo` 或 `provider=yahoo_pipeline` 时限制 `symbol_set` 或已知标的数量；`provider=tdx` 时限制本次实际处理的 `1d / 1m / 5m` 文件数量；若 `interval=all`，当前按每个 TDX 周期各自套用同一个 `limit`。当 `provider=tdx` 未传 `symbol` 且未传 `force` 时，服务会先跳过 manifest 已确认“未变化”的文件，优先把 `limit` 用在尚未导入或源文件已变化的文件上，便于多次分批推进完整 `vipdoc` 导入；`provider=tushare`、`provider=tdx_qfq` 或 `provider=tdx_pipeline` 时限制抓取股票数。当前 `provider=tushare` 未传 `symbol` 时必须提供 `limit`，避免误触发全市场全量抓取。

当前返回体除了旧版 `run_id / bars_inserted / bars_updated`，还会附带统一任务域的 `ingestion_job_id / series_bars_inserted / series_bars_updated`。其中 `provider=tushare` 会把“事件条数”复用到 `bars_inserted / bars_updated` 字段，并额外返回 `events_deleted / fetched_rows / implemented_rows`；`provider=tdx_qfq` 会额外返回 `segment_rows_inserted / segment_rows_updated / segment_rows_deleted / action_rows_used`；`provider=yahoo_pipeline` 和 `provider=tdx_pipeline` 会返回 workflow 总任务 `ingestion_job_id`、子任务 `child_ingestion_job_ids` / `ingestion_job_ids` 以及逐步骤的 `workflow_results`，便于前端直接展示统一链路状态。

当前 `provider=yahoo` 已支持通过 `symbol_set=yahoo_global_active_100` 导入内置 100 个全球高活跃样本；若同步失败，返回体会附带 `status` 和统一任务 `error_message`。`provider=yahoo_pipeline` 会再向上封装一层 workflow：固定执行 `yahoo 1d -> yahoo 15m -> yahoo 1m`，并在未显式传 `symbol` 或 `symbol_set` 时默认回退到 `yahoo_global_active_100`；分钟线步骤会自动使用 `15m=60d`、`1m=7d` 的窗口。`provider=tdx` 当前支持原始 `1d / 1m / 5m` 导入，分别对应 `.day`、`.lc1/.1`、`.lc5/.5` 文件，并共用同一套 `source_file_manifests` 增量状态；若传 `interval=all`，服务会顺序编排三个 TDX 周期，并在返回体中给出聚合统计与子任务 `ingestion_job_ids`。当批量请求额外传入 `batch_rounds` 时，服务会在同一请求里连续执行多轮 `tdx` 批量导入，并把每一轮的摘要放进 `round_results`，便于直接观察本次请求实际推进了多少轮。当前导入会保留 `vipdoc` 第一层市场目录，已覆盖常见 `sh / sz / bj / ds`；其中 `ds` 市场 `.day` 的 `open/high/low/close` 会按 `float32` 价格布局解析，若要显式传这类代码，建议命令行使用引号包住 `#`。`provider=tdx_pipeline` 会再向上封装一层 workflow：`interval=1d` 时执行 `tdx 1d -> tushare -> tdx_qfq 1d`，`interval=all` 时执行 `tdx all -> tushare -> tdx_qfq 1d`。当 workflow 以批量模式运行且未显式传 `symbol` 时，后两步会自动跟随数据库中已有的通达信原始 `1d` 标的集，而不是退回到 Tushare 的独立默认样本口径，并把 workflow 自身与所有子任务都记入统一任务域；`provider=tushare` 只支持 `dividend` 公司行动抓取，并且只把已有 `ex_date` 的实施事件写入 `corporate_action_events`；`provider=tdx_qfq` 只支持基于数据库中现有的通达信原始 `1d` 日线和 Tushare 公司行动重算前复权 `1d` 日线。

前端和 API 现在默认只负责“入队”，不会阻塞等待导入结束。`POST /api/market-data/sync` 至少会返回 `provider / ingestion_job_id / status=queued / target_symbol / interval / requested_via=api`；实际导入由 `main.py worker` 在后台领取执行。若你需要命令行里同步等待最终结果，继续使用 `main.py sync-now`。

`POST /api/market-data/ingestion-jobs/{job_id}/retry` 用于把失败、部分失败或已取消的 API 父任务重新放回队列。返回体包含：

- `job_id`
- `status`：成功重排时为 `queued`
- `changed`：是否真正发生了状态变化

`POST /api/market-data/ingestion-jobs/{job_id}/cancel` 用于取消统一导入任务。当前语义与回测任务保持一致：

- `queued`：直接转成 `cancelled`
- `running`：先转成 `cancel_requested`，Worker 会在 provider 子步骤或单个标的/文件循环的安全检查点停止后续处理
- 其他终态：返回原状态，`changed=false`

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

- `symbol`：必填，统一标的代码，例如 `1810.HK`、`SH600000`。
- `interval`：可选，默认由模板或服务默认值决定。
- `strategy_kind`：可选，策略类型。
- `market_data_provider`：可选；显式指定回测要读取的统一行情 provider，例如 `yahoo`、`tdx`、`tdx_qfq`。
- `market_data_adjustment_kind`：可选；显式指定统一行情复权口径，例如 `raw`、`qfq`。若传 `market_data_provider=tdx_qfq` 且未显式传该字段，后端会自动补成 `qfq`。
- `template_id`：可选，引用参数模板。
- `parameter_space`：可选，覆盖或补充模板参数空间。
- `execution_profile` 和费用/风控字段：可选，控制实盘化回测口径。

回测读取顺序当前为：

- 默认先尝试旧 `price_bars`，保证现有 Yahoo 回测入口不回归。
- 若请求显式给出了 `market_data_provider` / `market_data_adjustment_kind`，或旧 `price_bars` 没有该标的周期，则继续尝试统一主干表 `market_data_series + market_data_bars`。
- 如果统一主干表里同一标的/周期匹配出多条可用序列，接口会返回 `400`，要求调用方显式指定 provider 或复权口径，而不是隐式猜测。

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
