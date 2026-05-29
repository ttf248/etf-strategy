# 运维手册

本文记录平台运行后的常见操作和故障处理。

## 健康检查

API 健康检查：

```powershell
curl http://127.0.0.1:8000/health
```

正常返回：

```json
{"status":"ok"}
```

平台运行态体检：

```powershell
py -3.13 main.py check-runtime
```

该命令会直接输出数据库迁移状态、后台心跳、任务队列，以及 Yahoo / 通达信 / Tushare 的运行时配置摘要。若数据库异常、`worker / scheduler` 没有可见心跳，或某条数据链路处于 `misconfigured`，命令会返回非零退出码，适合在日常排障或自动化脚本里先做前置检查。

前端默认地址：

```text
http://127.0.0.1:3000
```

平台总控页：

```text
http://127.0.0.1:3000/platform
```

总控页会聚合 API、Frontend、数据库、Worker、Scheduler、队列、同步调度和最近日志。Worker 与 Scheduler 通过数据库心跳判断可见性，心跳长期不更新时应优先检查对应进程是否仍在运行。

数据准备页：

```text
http://127.0.0.1:3000/market-data
```

该页现在会先设定“当前目标标的”，然后在同一页直接展示 Yahoo 单周期、Yahoo 三周期链路、A 股统一补数链路、通达信原始行情、Tushare 公司行动和通达信前复权六类 provider 的摘要卡片、最近统一导入任务，以及“统一序列检查”“通达信原始文件 Manifest 检查”和“前复权输入与公式检查”面板；如果需要围绕单个标的集中排查，还可以直接打开“全链路诊断”抽屉，把最近相关任务、统一序列、manifest、公司行动和复权区间放在同一个视图里。若只是补当前回测样本，优先使用页内 Yahoo 覆盖检查与推荐周期；若想把当前 Yahoo 标的或默认 100 个全球高活跃样本一次性补齐 `1d / 15m / 1m`，优先使用 Yahoo 三周期链路；若要一键完成 A 股原始导入、公司行动和前复权，优先使用统一补数链路；若只想单独处理通达信原始 `1d / 1m / 5m`、公司行动或前复权，则使用对应 provider 卡片上的当前标的或批量按钮。当前通达信原始卡片已支持直接输入 `SH600000`、`SZ000001`、`10#AUDUSD` 这类不同市场代码；而“当前目标标的”检查区除了旧的回测样本覆盖，还会额外识别统一多数据源主干表中已经存在的序列，避免把已导入的 TDX 标的误判成“完全没有覆盖”。页面触发同步后会先创建 `data_ingestion_jobs` 队列任务，并由 `main.py worker` 在后台领取执行；最近任务区会自动轮询最新状态，支持直接展开 Yahoo 三周期链路和 A 股统一补数链路的子步骤明细，也支持打开任务详情抽屉查看 `data_ingestion_job_items` 文件级/标的级明细，若当前是 API 队列父任务，还可以继续跳转查看其下游子任务。现在最近任务区和任务详情还支持直接取消排队/执行中的统一导入任务，或把失败、部分失败、已取消的任务按原条件重新入队；任务详情和全链路诊断还能直接把目标标的带到“统一序列检查”“Manifest 检查”“前复权输入与公式检查”三个面板，避免人工重复输入筛选条件。若任务显示成功但仍怀疑落库结果异常，再用这些定位动作核对 `market_data_series`、`source_file_manifests`、`corporate_action_events` 和 `price_adjustment_segments`。

现在如果是 `tdx_qfq` 前复权任务，还可以直接在任务详情里看到：

- 批量阶段耗时：输入预加载、区间构建、区间写回、公式应用、K 线写回、平均每标的耗时。
- 单标的摘要：`raw / segment / adjusted` 三类摘要 digest、区间来源 `source_hash`，以及“常规跳过 / force 缓存跳过”的具体原因。

如果前复权任务显示成功但你仍怀疑“为什么这次没写回”或“为什么重复 `--force` 却秒过”，优先先看这些 digest 与跳过原因，再决定是否继续翻数据库。

维护页 `/platform` 现在还会直接显示多数据源运行配置摘要：数据库连接状态、通达信 `vipdoc` 解析结果、按市场/周期汇总的可见 K 线文件数、Tushare token 是否存在，以及 Yahoo 是否显式配置代理。若怀疑平台“命令能跑但前端任务总失败”，建议先看这里，再决定是否继续翻日志或直接重试导入任务。

## 行情同步

手动同步单个标的：

```powershell
py -3.13 main.py sync-now --symbol 1810.HK --interval 1d
py -3.13 main.py sync-now --provider yahoo_pipeline --symbol-set yahoo_global_active_100 --interval all --limit 100
py -3.13 main.py sync-now --provider yahoo_pipeline --symbol SPY --interval all
py -3.13 main.py sync-now --provider yahoo --symbol-set yahoo_global_active_100 --interval 1d --limit 100
py -3.13 main.py sync-now --provider yahoo --symbol-set yahoo_global_active_100 --interval 15m --period 60d --limit 100
py -3.13 main.py sync-now --provider yahoo --symbol-set yahoo_global_active_100 --interval 1m --period 7d --limit 100
py -3.13 main.py sync-now --provider tdx --interval all --limit 100
py -3.13 main.py sync-now --provider tdx --symbol sh600000 --interval 1d
py -3.13 main.py sync-now --provider tdx --symbol sh600000 --interval 1m
py -3.13 main.py sync-now --provider tdx --symbol sh600000 --interval 5m
py -3.13 main.py sync-now --provider tdx --symbol sh600000 --interval all
py -3.13 main.py sync-now --provider tdx --symbol "10#AUDUSD" --interval 1d
py -3.13 main.py sync-now --provider tdx_pipeline --symbol sh600000 --interval 1d
py -3.13 main.py sync-now --provider tdx_pipeline --symbol sh600000 --interval all
py -3.13 main.py sync-now --provider tushare --symbol sh600000
py -3.13 main.py sync-now --provider tdx_qfq --symbol sh600000 --interval 1d
```

同步所有已知标的：

```powershell
py -3.13 main.py sync-now --interval 15m --period 60d
```

按通达信原始文件导入：

```powershell
py -3.13 main.py sync-now --provider tdx --interval 1d --limit 100
py -3.13 main.py sync-now --provider tdx --interval 1d --force
py -3.13 main.py sync-now --provider tdx --interval all --limit 100 --force
py -3.13 main.py sync-now --provider tdx --interval 1m --symbol sh600000 --force
py -3.13 main.py sync-now --provider tdx --interval 5m --symbol sh600000 --force
py -3.13 main.py sync-now --provider tdx --interval 1d --symbol "10#AUDUSD" --force
py -3.13 main.py sync-now --provider tdx_pipeline --interval all --limit 20 --force
py -3.13 main.py sync-now --provider tdx_pipeline --symbol sh600000 --interval 1d --force
py -3.13 main.py sync-now --provider tushare --limit 20
py -3.13 main.py sync-now --provider tdx_qfq --limit 20
```

当前 `provider=tdx` 已支持原始 `1d / 1m / 5m` 文件导入，并依赖 `STRATEGY_STUDIO_TDX_VIPDOC` 或 `STRATEGY_STUDIO_TDX_CONFIG_PATH` 指向有效的 `vipdoc` 配置。其中 `1d` 扫描 `.day`，`1m` 扫描 `.lc1/.1`，`5m` 扫描 `.lc5/.5`；若使用 `interval=all`，会顺序执行三个 TDX 周期，适合直接按配置路径全量导入。当前导入会保留 `vipdoc` 第一层市场目录，已覆盖常见 `sh / sz / bj / ds`；其中 `ds` 日线价格字段按 `float32` 位模式解析，不再沿用 A 股 `.day` 的整数缩放口径。若命令里要显式指定 `ds` 代码，PowerShell 下请用引号包住 `#`，例如 `--symbol "10#AUDUSD"`。若本机 `vipdoc` 目录结构和默认假设不一致，应先确认实际文件位置再执行导入。

A 股统一补数链路注意事项：

- `provider=tdx_pipeline` 会把 `tdx raw -> tushare actions -> tdx_qfq rebuild` 串成一个总任务，并另外在统一任务域记录 workflow 本身与所有子任务 ID。
- `interval=1d` 时执行 `tdx 1d -> tushare -> tdx_qfq 1d`；`interval=all` 时执行 `tdx all -> tushare -> tdx_qfq 1d`，适合一次性补齐原始 `1d / 1m / 5m`、公司行动与前复权。
- 当 workflow 以批量模式执行且未显式传 `--symbol` 时，Tushare 抓取和前复权重算会自动跟随数据库里已有、且可映射 Tushare `ts_code` 的通达信原始 `1d` 标的集，而不是单独取 Tushare 默认样本；`ds` 等非 A 股原始标的不会被误送进这条链路。
- workflow 的 `bars_inserted / bars_updated` 是子步骤聚合值，其中 Tushare 仍沿用“事件条数复用 bars 字段”的口径；排查时应同时结合 `workflow_results` 和最近统一导入任务查看。
- 若上游原始导入或公司行动抓取彻底失败，workflow 会停止后续步骤；若只是部分失败，则仍会尽量继续执行后续步骤，便于保留已完成部分。

Yahoo 默认样本池注意事项：

- `symbol_set=yahoo_global_active_100` 会按内置 100 个全球高活跃样本创建或更新 Yahoo 标的，并按 `limit` 控制本次实际执行数量。
- `1d` 会下载可获得的完整日线历史；`15m` 默认应配 `--period 60d`；`1m` 默认应配 `--period 7d`。
- 当前网络环境若无法直连 Yahoo，命令会明确返回失败状态与首个错误原因；常见情况是必须通过 `--proxy` 或 `STRATEGY_STUDIO_PROXY` 配置代理。

Yahoo 三周期链路注意事项：

- `provider=yahoo_pipeline` 固定要求 `--interval all`，后台会顺序执行 `yahoo 1d -> yahoo 15m -> yahoo 1m` 三个子步骤。
- 未显式传 `--symbol` 或 `--symbol-set` 时，workflow 会默认回退到 `yahoo_global_active_100`，适合直接补默认样本池。
- 分钟线子步骤会自动套用 `15m=60d`、`1m=7d` 的 Yahoo 免费窗口，不需要再手动传 `--period`。
- 返回结果和统一任务详情会同时记录 workflow 自身 `ingestion_job_id`、三个子任务 `child_ingestion_job_ids` 与 `workflow_results`，便于直接在 `/market-data` 或数据库里追踪三步是否都成功落库。

Tushare 公司行动抓取注意事项：

- 优先通过 `STRATEGY_STUDIO_TUSHARE_TOKEN` 提供 token；未设置时，会尝试从 `STRATEGY_STUDIO_TUSHARE_CONFIG_PATH` 指向的 yaml 中读取 `tushare.token`。
- 当前只写入 `dividend` 中已有 `ex_date` 的实施事件，落库表为 `corporate_action_events`。
- 当前未传 `--symbol` 时必须同时给 `--limit`，避免误触发全市场全量抓取。
- 当前按单个 `ts_code` 全量覆盖写入；如果同一事件被源端修订，下一次抓取会直接替换旧记录。

通达信前复权重算注意事项：

- 当前只支持 `1d` 日线，并且要求数据库中已经存在同标的的 `provider=tdx` 原始 `1d` 序列。
- 当前目标范围仅限可映射 Tushare `ts_code` 的 `sh / sz / bj` 原始日线；`ds` 等非 A 股原始标的不会进入前复权重算。
- 当前公司行动输入只读取 `provider=tushare` 下的已实施事件；没有公司行动时会生成恒等公式区间，输出价格等于原始价格。
- 前复权任务会同时重建 `price_adjustment_segments` 和 `market_data_series(provider=tdx_qfq, adjustment_kind=qfq)` 对应的 `market_data_bars`。
- 当前重复执行会全量重算目标标的，但由于 K 线与区间都按唯一键覆盖写入，不会生成重复行。

Scheduler 默认在 Asia/Shanghai 时区运行：

- 18:05 同步 `1d`。
- 18:15 同步 `15m`，窗口 `60d`。
- 18:25 同步 `1m`，窗口 `7d`。

## 回测任务

回测由 API 入队，Worker 执行。若任务长期停留在 `queued`：

1. 确认 Worker 进程存在。
2. 查看日志中是否有数据库或策略异常。
3. 确认目标标的和周期在旧 `price_bars`，或 `market_data_series + market_data_bars` 的统一序列中有足够数据。

失败任务可以通过前端重试，也可以调用 `POST /api/backtests/{job_id}/retry`。

取消任务可以在前端任务中心执行，也可以调用 `POST /api/backtests/{job_id}/cancel`。排队任务会立即取消，运行中任务会先进入 `cancel_requested`，等待 Worker 到达安全检查点后变为 `cancelled`。

回测读取链路当前的优先顺序是：

1. 若请求未显式指定统一行情 provider，且 `price_bars` 中已存在该标的/周期，则优先复用旧 Yahoo 兼容表。
2. 若请求带了 `market_data_provider` / `market_data_adjustment_kind`，或旧表没有该标的周期，则继续尝试从 `market_data_series + market_data_bars` 读取。
3. 如果统一主干表里同一标的/周期存在多条可用序列，例如同时有 `tdx raw` 和 `tdx_qfq qfq`，当前会明确报错，要求请求方显式指定 provider 或复权口径，避免 Worker 误选错误序列。

前端 `/backtests` 现在已经直接暴露了这两个可选字段：

- “行情来源”：可选 `Yahoo`、`通达信原始`、`通达信前复权`，留空表示自动选择。
- “复权口径”：可选 `raw`、`qfq`，留空表示自动判断。

若你是从 `/market-data` 的“基于当前标的创建回测”跳过去，且当前标的只存在于统一主干表，页面会自动把对应 provider / adjustment 预填好，避免再手工选择一次。

研究总览、数据准备页和创建回测页里的推荐样本与“可直接进入主流程”统计，当前也已经切到同一套自动可回测口径：

- 旧 `price_bars` 已覆盖的标的/周期仍优先沿用旧表，保持兼容。
- 若旧表没有覆盖，但统一主干表里同标的同周期只有唯一一条可用序列，该样本会自动进入首页推荐和创建回测页预设。
- 若统一主干表里同标的同周期同时存在多条可用序列，例如 `tdx raw` 和 `tdx_qfq qfq` 并存，则前端不会把它自动当成推荐样本；此时应在创建回测页显式选择“行情来源 / 复权口径”，避免误用错误序列。

## 日志

排查顺序：

1. 先看对应进程终端输出。
2. 数据问题再查前端同步记录或 `data_sync_runs`。

前端平台总控页提供最近日志摘录，只用于快速定位；本地默认不再额外落地日志文件。

## 进程控制

Web 端进程控制默认关闭，避免误杀本机服务。只有本地开发确实需要时才设置：

```powershell
$env:STRATEGY_STUDIO_ENABLE_PROCESS_CONTROL="true"
```

当前接口只作为受控入口，不建议把它当作生产进程管理方案。生产环境应使用系统服务、Supervisor、容器编排或 CI/CD 发布脚本管理进程。

## 端口占用

API 默认端口是 `8000`，前端默认端口是 `3000`。

检查端口：

```powershell
netstat -ano | Select-String '127.0.0.1:8000'
netstat -ano | Select-String '127.0.0.1:3000'
```

API 启动项默认带 `--replace-existing`，只会替换命令行可识别为本项目 `main.py api` 的旧进程。其他服务占用 `8000` 时不会被自动结束。

## 数据库维护

初始化：

```powershell
py -3.13 main.py init-db
```

准备首批数据库行情：

```powershell
py -3.13 main.py sync-now --symbol 1810.HK --interval 1d
```

## Yahoo 访问问题

在无法直连 Yahoo 的网络环境中，需要配置代理：

```powershell
$env:STRATEGY_STUDIO_PROXY="http://127.0.0.1:7897"
```

常见失败原因：

- 代理不可用。
- Yahoo 限流。
- 分钟线请求窗口超过 Yahoo 免费数据范围。
- 标的代码不是 Yahoo 可识别格式。

## 运行产物清理

默认不应提交以下目录中的临时产物：

- 前端构建缓存。

平台回测结果应留存在数据库，本地工作区不再保留正式报告文件。
