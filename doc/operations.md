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

前端默认地址：

```text
http://127.0.0.1:3000
```

平台总控页：

```text
http://127.0.0.1:3000/platform
```

总控页会聚合 API、Frontend、数据库、Worker、Scheduler、队列、同步调度和最近日志。Worker 与 Scheduler 通过数据库心跳判断可见性，心跳长期不更新时应优先检查对应进程是否仍在运行。

## 行情同步

手动同步单个标的：

```powershell
py -3.13 main.py sync-now --symbol 1810.HK --interval 1d
py -3.13 main.py sync-now --provider tdx --symbol sh600000 --interval 1d
py -3.13 main.py sync-now --provider tushare --symbol sh600000
```

同步所有已知标的：

```powershell
py -3.13 main.py sync-now --interval 15m --period 60d
```

按通达信原始文件导入：

```powershell
py -3.13 main.py sync-now --provider tdx --interval 1d --limit 100
py -3.13 main.py sync-now --provider tdx --interval 1d --force
py -3.13 main.py sync-now --provider tushare --limit 20
```

当前 `provider=tdx` 只支持原始 `1d` 日线，并依赖 `STRATEGY_STUDIO_TDX_VIPDOC` 或 `STRATEGY_STUDIO_TDX_CONFIG_PATH` 指向有效的 `vipdoc` 配置。

Tushare 公司行动抓取注意事项：

- 优先通过 `STRATEGY_STUDIO_TUSHARE_TOKEN` 提供 token；未设置时，会尝试从 `STRATEGY_STUDIO_TUSHARE_CONFIG_PATH` 指向的 yaml 中读取 `tushare.token`。
- 当前只写入 `dividend` 中已有 `ex_date` 的实施事件，落库表为 `corporate_action_events`。
- 当前未传 `--symbol` 时必须同时给 `--limit`，避免误触发全市场全量抓取。
- 当前按单个 `ts_code` 全量覆盖写入；如果同一事件被源端修订，下一次抓取会直接替换旧记录。

Scheduler 默认在 Asia/Shanghai 时区运行：

- 18:05 同步 `1d`。
- 18:15 同步 `15m`，窗口 `60d`。
- 18:25 同步 `1m`，窗口 `7d`。

## 回测任务

回测由 API 入队，Worker 执行。若任务长期停留在 `queued`：

1. 确认 Worker 进程存在。
2. 查看日志中是否有数据库或策略异常。
3. 确认目标标的和周期在 `price_bars` 中有足够数据。

失败任务可以通过前端重试，也可以调用 `POST /api/backtests/{job_id}/retry`。

取消任务可以在前端任务中心执行，也可以调用 `POST /api/backtests/{job_id}/cancel`。排队任务会立即取消，运行中任务会先进入 `cancel_requested`，等待 Worker 到达安全检查点后变为 `cancelled`。

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
