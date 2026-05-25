# 架构设计

ETF Strategy 当前由一套研究引擎和一套 Web 平台组成。两者共享 Python 策略、数据和报告能力，只是入口不同。

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

- 前端负责控制台交互，包括行情统计、回测提交、模板管理和历史报告查看。
- FastAPI 负责 JSON API、任务入队、报告查询和同步触发。
- PostgreSQL 是平台主存储，保存行情、同步记录、回测任务、报告、交易流水和参数模板。
- Worker 常驻轮询数据库中的回测任务，执行完成后写回报告数据。
- Scheduler 按固定时间从 Yahoo 同步行情。
- CLI 仍保留，适合本地研究、批量回测、CSV 导入和平台运维命令。

## 后端模块

- `etf_strategy/cli.py`：研究命令入口，负责参数解析和工作流分发。
- `etf_strategy/platform_cli.py`：平台命令入口，负责数据库初始化、API、Worker、Scheduler 和同步命令。
- `etf_strategy/data/`：Yahoo 下载、标准化、交易单位和标的池数据。
- `etf_strategy/strategy/`：网格、反转、指数 ETF 回落反弹等策略实现。
- `etf_strategy/workflow.py`：样本切分、寻参、验证和结果落盘的编排层。
- `etf_strategy/reporting.py`：图表、Markdown 报告和报告索引生成。
- `etf_strategy/db/`：SQLAlchemy 模型、数据库连接和迁移配置。
- `etf_strategy/repositories/`：数据库读写和查询。
- `etf_strategy/services/`：业务服务层，连接 API、仓储、策略工作流和报告落库。
- `etf_strategy/runtime/`：常驻 Worker 和 Scheduler。
- `etf_strategy/web/`：FastAPI 应用和请求模型。

## 前端模块

`frontend/` 是 Next.js 控制台，使用 Ant Design 和 ECharts：

- `/`：平台概览。
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

## 数据存储原则

- PostgreSQL 是长期主存储。
- CSV 只作为历史导入、离线调试和兼容 CLI 的输入形式。
- `outputs/` 和 `reports/platform/` 是运行产物，不应作为平台主数据源。
- 自动生成报告可以保存为文件，但平台报告的可查询信息以数据库中的结构化记录为准。
