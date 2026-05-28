# Strategy Studio

Strategy Studio 是一个中文优先的开源策略研究平台，用于从 Yahoo Finance 获取行情、长期存储 K 线、提交异步回测任务，并在 Web 前端按新手流程创建回测、查看报告和准备数据。

当前架构由 Python 研究引擎、FastAPI 后端、PostgreSQL、Worker、Scheduler 和 Next.js 前端组成。CLI 仍然保留，但只承担数据库同步、数据库回测与运维命令。

## 功能概览

- 行情数据：Yahoo 同步、PostgreSQL 长期存储。
- 回测执行：API 入队，Worker 异步执行，报告结构化落库。
- 参数模板：在数据库中管理策略、周期、执行口径和寻参空间。
- 多策略研究：网格、定投、双均线趋势、MACD 趋势、唐奇安突破、布林带均值回归、日线反弹、分钟反抽和指数回落网格共用同一套工作流。
- Web 前端：研究总览、创建回测、查看报告、数据覆盖、策略模板和系统状态；数据覆盖页会直接推荐适合建立基线样本的标的和应补周期，研究总览与回测任务页都会实时展示阶段、预计剩余时间和资源收口结果，报告详情会先给出收益/回撤/期末权益/对照结论，再按需展开细节。
- CLI 研究：保留数据库同步、数据库回测和批量任务入口。
- 仓库边界：历史行情、历史 Markdown 报告和平台回测结果不再随仓库提交，数据库是唯一长期事实来源。

## 架构

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

更多设计说明见 [架构设计](doc/architecture.md) 和 [数据流转](doc/data-flow.md)。

## 快速开始

### 1. 安装依赖

后端：

```powershell
py -3.13 -m pip install -r requirements.txt
```

前端：

```powershell
cd frontend
npm install
```

### 2. 初始化数据库

默认数据库连接为：

```text
postgresql+psycopg://postgres:tian@localhost:5432/strategy_studio
```

初始化数据库：

```powershell
py -3.13 main.py init-db
```

如需准备首批可回测行情：

```powershell
py -3.13 main.py sync-now --symbol 1810.HK --interval 1d
```

生产环境请通过 `STRATEGY_STUDIO_DATABASE_URL` 覆盖默认连接。仓库不再提交样例行情和历史报告；平台回测结果默认只写入数据库，日常使用应优先围绕数据库、API 和前端页面展开。

### 3. 启动平台

Windows 开发环境：

```powershell
scripts\start_platform_windows.bat
```

或者分别启动：

```powershell
py -3.13 main.py api --host 127.0.0.1 --port 8000 --replace-existing
py -3.13 main.py worker --poll-interval 5 --max-concurrent-jobs 2 --max-optimization-workers 4
py -3.13 main.py scheduler

cd frontend
$env:NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"
npx next dev --hostname 127.0.0.1 --port 3000
```

访问地址：

- API：`http://127.0.0.1:8000`
- API 文档：`http://127.0.0.1:8000/docs`
- 研究总览：`http://127.0.0.1:3000`
- 创建回测：`http://127.0.0.1:3000/backtests`
- 系统状态：`http://127.0.0.1:3000/platform`

VS Code 用户可以直接使用 `启动平台前后端全套`。

## 常用命令

手动同步行情：

```powershell
py -3.13 main.py sync-now --symbol 1810.HK --interval 15m --period 60d
```

提交平台回测建议优先通过前端或 API 入队，Worker 会异步执行并把结果写回数据库；如需补齐行情覆盖，可直接使用 `sync-now` 或前端数据覆盖页。

批量研究：

```powershell
py -3.13 main.py batch --symbol-set hstech_plus_513050 --interval 1d --download --proxy http://127.0.0.1:7897 --jobs auto
```

## 项目结构

```text
strategy_studio/    Python 后端、策略、数据、服务和运行时
frontend/        Next.js 前端控制台
alembic/         PostgreSQL 迁移
data/            数据边界说明
reports/         报告边界说明
doc/             长期维护文档
tests/           unittest 测试
```

其中：

- `data/`：只保留边界说明，不存放正式行情数据。
- `reports/`：只保留边界说明，不存放正式回测报告。
- 本地工作区不再约定任何正式数据或正式报告目录。

## 文档

- [文档导航](doc/index.md)
- [架构设计](doc/architecture.md)
- [数据流转](doc/data-flow.md)
- [部署指南](doc/deployment.md)
- [运维手册](doc/operations.md)
- [开发指南](doc/development.md)
- [API 接口说明](doc/api.md)
- [策略引擎](doc/strategy-engine.md)
- [开源准备度审计](doc/open-source-readiness.md)
- [前端说明](frontend/README.md)
- [前端体验审查](doc/frontend-ux-audit.md)
- [数据目录说明](data/README.md)
- [报告目录说明](reports/README.md)

## 配置

常用环境变量：

- `STRATEGY_STUDIO_DATABASE_URL`
- `STRATEGY_STUDIO_ADMIN_DATABASE`
- `STRATEGY_STUDIO_API_HOST`
- `STRATEGY_STUDIO_API_PORT`
- `STRATEGY_STUDIO_WORKER_MAX_CONCURRENT_JOBS`
- `STRATEGY_STUDIO_WORKER_MAX_OPTIMIZATION_WORKERS`
- `STRATEGY_STUDIO_PROXY`
- `STRATEGY_STUDIO_ENABLE_PROCESS_CONTROL`
- `NEXT_PUBLIC_API_BASE_URL`

更多部署细节见 [部署指南](doc/deployment.md)。

## 测试

后端：

```powershell
py -3.13 -m unittest tests.test_platform_features tests.test_repo_contracts
py -3.13 -m unittest tests.test_grid_strategy tests.test_yahoo_data
git diff --check
```

前端：

```powershell
cd frontend
npm run lint
npm run build
npx playwright install chromium
npm run test:smoke
```

## 贡献

欢迎提交改进。开始前请阅读 [贡献指南](CONTRIBUTING.md)。本项目使用 [MIT License](LICENSE)，并补充了 [安全策略](SECURITY.md) 和 [支持说明](SUPPORT.md)。

提交要求：

- 提交日志使用中文。
- 功能变更必须补测试。
- 命令、API、数据流、部署方式或报告口径变化必须同步更新文档。
- 不提交运行缓存、日志和一次性实验产物。
