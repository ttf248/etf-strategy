# ETF Strategy

ETF Strategy 是一个中文优先的开源策略研究平台，用于从 Yahoo Finance 获取行情、长期存储 K 线、提交异步回测任务，并在 Web 控制台查看行情统计、参数模板和历史回测报告。

当前架构由 Python 研究引擎、FastAPI 后端、PostgreSQL、Worker、Scheduler 和 Next.js 前端组成。CLI 仍然保留，用于离线研究、批量回测、CSV 导入和运维命令。

## 功能概览

- 行情数据：Yahoo 下载、本地 CSV 导入、PostgreSQL 长期存储。
- 回测执行：API 入队，Worker 异步执行，报告结构化落库。
- 参数模板：在数据库中管理策略、周期、执行口径和寻参空间。
- Web 控制台：行情统计、同步记录、回测任务、模板中心、历史报告。
- CLI 研究：保留下载、寻参、验证、报告和批量研究入口。
- 报告样例：[统一报告索引](reports/report_index.md)、[日线多策略报告](reports/1810_hk/daily/1810_hk_daily_strategy_compare_report.md)、[15 分钟多策略报告](reports/1810_hk/minute/1810_hk_15m_strategy_compare_report.md)、[15 分钟网格基线报告](reports/1810_hk/minute/1810_hk_15m_grid_report.md)。

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
postgresql+psycopg://postgres:tian@localhost:5432/etf_strategy
```

初始化并导入本地样例行情：

```powershell
py -3.13 main.py init-db
py -3.13 main.py import-csv --source-dir data/processed
```

生产环境请通过 `ETF_STRATEGY_DATABASE_URL` 覆盖默认连接。

### 3. 启动平台

Windows 开发环境：

```powershell
scripts\start_platform_windows.bat
```

或者分别启动：

```powershell
py -3.13 main.py api --host 127.0.0.1 --port 8000 --replace-existing
py -3.13 main.py worker --poll-interval 5
py -3.13 main.py scheduler

cd frontend
$env:NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"
npx next dev --hostname 127.0.0.1 --port 3000
```

访问地址：

- API：`http://127.0.0.1:8000`
- API 文档：`http://127.0.0.1:8000/docs`
- 前端：`http://127.0.0.1:3000`

VS Code 用户可以直接使用 `启动平台前后端全套`。

## 常用命令

手动同步行情：

```powershell
py -3.13 main.py sync-now --symbol 1810.HK --interval 1d
```

提交本地报告研究：

```powershell
py -3.13 main.py report --data data/processed/1810_hk_15m.csv --symbol 1810.HK --interval 15m --compare-strategies --jobs auto --cache-dir outputs/cache/minute_compare
```

批量研究：

```powershell
py -3.13 main.py batch --symbol-set southbound_shanghai_all --interval 1d --download --proxy http://127.0.0.1:7897 --jobs auto --cache-dir outputs/cache/southbound_daily
```

离线批量重跑：

```powershell
py -3.13 main.py batch --symbol-set southbound_shanghai_all --interval 15m --local-only --cache-dir outputs/cache/southbound_15m
```

## 项目结构

```text
etf_strategy/    Python 后端、策略、数据、服务和运行时
frontend/        Next.js 前端控制台
alembic/         PostgreSQL 迁移
data/            样例输入和参考数据
reports/         样例报告和批量报告索引
outputs/         运行中间产物，默认不提交
doc/             长期维护文档
tests/           unittest 测试
```

## 文档

- [文档导航](doc/index.md)
- [架构设计](doc/architecture.md)
- [数据流转](doc/data-flow.md)
- [部署指南](doc/deployment.md)
- [运维手册](doc/operations.md)
- [开发指南](doc/development.md)
- [API 接口说明](doc/api.md)
- [策略引擎](doc/strategy-engine.md)
- [前端说明](frontend/README.md)

## 配置

常用环境变量：

- `ETF_STRATEGY_DATABASE_URL`
- `ETF_STRATEGY_ADMIN_DATABASE`
- `ETF_STRATEGY_API_HOST`
- `ETF_STRATEGY_API_PORT`
- `ETF_STRATEGY_PLATFORM_OUTPUT_DIR`
- `ETF_STRATEGY_PLATFORM_REPORT_DIR`
- `ETF_STRATEGY_PROXY`
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
```

## 贡献

欢迎提交改进。开始前请阅读 [贡献指南](CONTRIBUTING.md)。本项目使用 [MIT License](LICENSE)。

提交要求：

- 提交日志使用中文。
- 功能变更必须补测试。
- 命令、API、数据流、部署方式或报告口径变化必须同步更新文档。
- 不提交运行缓存、日志和一次性实验产物。
