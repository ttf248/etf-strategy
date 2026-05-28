# 架构设计

Strategy Studio 当前由一套研究引擎和一套 Web 平台组成。两者共享 Python 策略、数据和报告能力，只是入口不同。

## 系统边界

```text
Next.js Frontend
        |
        v
FastAPI API  <---- CLI main.py
        |
        v
PostgreSQL
   |        |
   v        v
Worker   Scheduler
   |        |
   v        v
Backtest  Yahoo Sync
```

- 前端负责控制台交互，包括平台总控、行情统计、回测提交、模板管理和历史报告查看。
- FastAPI 负责 JSON API、任务入队、报告查询、同步触发和平台状态聚合，是前端统一访问后端能力的门面。
- PostgreSQL 是平台主存储，保存行情、同步记录、回测任务、报告、交易流水和参数模板。
- Worker 常驻轮询数据库中的回测任务，执行完成后写回报告数据。
- Scheduler 按固定时间从 Yahoo 同步行情。
- CLI 仍保留，但只负责数据库同步、数据库回测和平台运维命令。

## 后端模块

- `strategy_studio/cli.py`：研究命令入口，负责参数解析和工作流分发。
- `strategy_studio/platform_cli.py`：平台命令入口，负责数据库初始化、API、Worker、Scheduler 和同步命令。
- `strategy_studio/data/`：Yahoo 下载、标准化、交易单位和标的池数据。
- `strategy_studio/strategy/`：网格、反转、指数 ETF 回落反弹等策略实现。
- `strategy_studio/workflow.py`：样本切分、寻参、验证和结果汇总的编排层。
- `strategy_studio/reporting.py`：研究态图表、临时 Markdown 报告与测试辅助工具。
- `strategy_studio/db/`：SQLAlchemy 模型、数据库连接和迁移配置。
- `strategy_studio/repositories/`：数据库读写和查询。
- `strategy_studio/services/`：业务服务层，连接 API、仓储、策略工作流和报告落库。
- `strategy_studio/runtime/`：常驻 Worker 和 Scheduler。
- `strategy_studio/web/`：FastAPI 应用和请求模型。

当前后端保持模块化单体，不单独引入前置网关或 RPC 框架。API、Worker 和 Scheduler 是同一代码包的不同进程入口，跨进程协作通过 PostgreSQL 中的任务、同步记录和心跳表完成；只有出现跨语言、跨机器或独立扩缩容需求时，才需要升级为独立网关加 RPC。

## 前端模块

`frontend/` 是 Next.js 控制台，使用 Ant Design 和 ECharts：

- `/`：平台概览。
- `/platform`：平台总控，查看 API、Frontend、Worker、Scheduler、数据库、任务队列、同步调度和最近日志。
- `/market-data`：行情统计、覆盖区间和同步记录。
- `/templates`：策略参数模板管理。
- `/backtests`：提交回测任务、查看队列和重试任务。
- `/reports`：历史报告列表。
- `/reports/[id]`：报告详情、曲线、交易和事件。

前端只通过 `NEXT_PUBLIC_API_BASE_URL` 指向后端，不直接访问数据库。

## 进程模型

生产部署至少需要四类进程：

- API：`main.py api --host 127.0.0.1 --port 8000 --replace-existing`
- Worker：`main.py worker --poll-interval 5`
- Scheduler：`main.py scheduler`
- Frontend：`npx next start` 或开发模式 `npx next dev`

Windows 开发环境可以使用 `.vscode/launch.json` 或 `scripts/start_platform_windows.bat` 一键拉起。

Worker 和 Scheduler 会写入 `platform_heartbeats` 心跳记录，前端平台总控页据此判断常驻进程是否可见。Web 进程控制默认关闭；只有设置 `STRATEGY_STUDIO_ENABLE_PROCESS_CONTROL=true` 后，相关接口才允许进入后续受控操作。

## 数据存储原则

- PostgreSQL 是正式行情、任务和报告的唯一长期主存储。
- 平台标准流程不再依赖本地 CSV 输入，也不再生成仓库内正式 Markdown 报告。
- `outputs/` 仅允许承载测试隔离或临时研究产物，不应作为平台主数据源。
- 前端、API 和 Worker 查询的报告事实以数据库中的结构化记录为准。
