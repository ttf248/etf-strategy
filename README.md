# Strategy Studio

Strategy Studio 是一个中文优先的开源策略研究平台，用于从 Yahoo Finance、通达信、Tushare 等渠道获取行情或公司行动、长期存储结构化数据、提交异步回测任务，并在 Web 前端按新手流程创建回测、查看报告和准备数据。

当前架构由 Python 研究引擎、FastAPI 后端、PostgreSQL、Worker、Scheduler 和 Next.js 前端组成。CLI 仍然保留，但只承担数据库同步、数据库回测与运维命令。

## 功能概览

- 行情数据：Yahoo 单周期同步、Yahoo 默认样本三周期链路、通达信原始 `1d / 1m / 5m` 导入、Tushare 公司行动抓取、通达信前复权日线重算、PostgreSQL 长期存储。
- 回测执行：API 入队，Worker 异步执行，报告结构化落库。
- 参数模板：在数据库中管理策略、周期、执行口径和寻参空间。
- 多策略研究：网格、定投、双均线趋势、MACD 趋势、唐奇安突破、放量突破、布林带均值回归、日线反弹、分钟反抽和指数回落网格共用同一套工作流。
- Web 前端：研究总览、创建回测、查看报告、数据覆盖、策略模板和系统状态；左侧导航只保留主路径与维护入口，顶部收敛成“页头 + 单一决策横幅”，把研究状态、下一步动作和关键判断统一放进同一个信息层级；数据准备页现在会先设定当前标的，再在同一页直接管理 Yahoo 单周期、Yahoo 三周期链路、通达信原始 `1d / 1m / 5m`、Tushare 公司行动和通达信前复权任务，同时保留面向当前回测链路的覆盖检查、推荐周期和 TDX 多周期任务入口；其中通达信原始任务已支持直接输入 `SH600000`、`SZ000001`、`10#AUDUSD` 这类不同市场代码，当前标的检查区也会额外识别统一多数据源主干表里已经存在的序列，不再只看旧 Yahoo/`price_bars` 覆盖口径；研究总览、数据准备页和创建回测页里的“推荐样本 / 可直接进入主流程”统计，现已统一基于自动可回测口径计算：若旧 `price_bars` 已覆盖则优先沿用旧表，否则只把统一主干表里同标的同周期唯一可用的序列纳入推荐，避免在多条候选序列并存时误导用户；创建回测页现在也支持显式指定统一行情 provider 与复权口径，既可继续沿用旧 Yahoo 回测表，也可直接基于 `tdx raw` 或 `tdx_qfq qfq` 这类统一主干表序列发起研究；系统状态页除了 API / Frontend / Database / Worker / Scheduler 心跳外，还会直接显示 Yahoo / 通达信 / Tushare 三条数据链路的配置摘要，其中通达信会额外给出当前 `vipdoc` 下按市场/周期汇总的可见 K 线文件数，便于先确认导入范围，再决定是否进入任务级排障；研究总览与回测任务页都会实时展示阶段、预计剩余时间和资源收口结果，结果库会先按标的归纳哪一组最值得继续研究，再下钻到单份报告；报告详情会先给出收益/回撤/期末权益/对照结论，并直接标明同标的同周期中的横向位置，再按需展开细节。
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

更多设计说明见 [架构设计](doc/architecture.md) 、[数据流转](doc/data-flow.md) 和 [多数据源行情后台规划](doc/multi-source-market-data-plan.md)。

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

初始化数据库：

```powershell
py -3.13 main.py check-db
py -3.13 main.py check-runtime
py -3.13 main.py init-db
```

如需准备首批可回测行情：

```powershell
py -3.13 main.py sync-now --symbol 1810.HK --interval 1d
py -3.13 main.py sync-now --provider yahoo_pipeline --symbol-set yahoo_global_active_100 --interval all --limit 100
py -3.13 main.py sync-now --provider yahoo --symbol-set yahoo_global_active_100 --interval 1d --limit 100
py -3.13 main.py sync-now --provider yahoo --symbol-set yahoo_global_active_100 --interval 15m --period 60d --limit 100
py -3.13 main.py sync-now --provider yahoo --symbol-set yahoo_global_active_100 --interval 1m --period 7d --limit 100
py -3.13 main.py sync-now --provider tdx --interval all --limit 100
py -3.13 main.py sync-now --provider tdx --interval all --limit 100 --batch-rounds 10
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
$env:STRATEGY_STUDIO_API_ORIGIN="http://127.0.0.1:8000"
npx next dev --hostname 127.0.0.1 --port 3000
```

访问地址：

- API：`http://127.0.0.1:8000`
- API 文档：`http://127.0.0.1:8000/docs`
- 研究总览：`http://127.0.0.1:3000`
- 创建回测：`http://127.0.0.1:3000/backtests`
- 系统状态：`http://127.0.0.1:3000/platform`

VS Code 用户可以直接使用 `启动平台前后端全套`。

如需在命令行快速确认“数据库是否连通、Worker/Scheduler 是否在线，以及 Yahoo / 通达信 / Tushare 的运行前提是否已经就绪”，可以执行：

```powershell
py -3.13 main.py check-runtime
```

该命令会汇总数据库迁移状态、后台心跳、任务队列以及多数据源运行态；若数据库异常、关键 provider 配置不完整，或 `worker / scheduler` 心跳缺失，会返回非零退出码，便于脚本或排障流程直接判断。若当前机器存在 Windows 系统代理候选，但项目尚未通过 `--proxy` 或 `STRATEGY_STUDIO_PROXY` 显式启用，输出里也会直接提示，避免把“本机有代理但命令没带上”误判成 Yahoo 本身故障。

## 常用命令

手动同步行情：

```powershell
py -3.13 main.py sync-now --symbol 1810.HK --interval 15m --period 60d
py -3.13 main.py sync-now --provider yahoo_pipeline --symbol-set yahoo_global_active_100 --interval all --limit 100
py -3.13 main.py sync-now --provider yahoo_pipeline --symbol SPY --interval all
py -3.13 main.py sync-now --provider yahoo --symbol-set yahoo_global_active_100 --interval 1d --limit 100
py -3.13 main.py sync-now --provider yahoo --symbol-set yahoo_global_active_100 --interval 15m --period 60d --limit 100
py -3.13 main.py sync-now --provider yahoo --symbol-set yahoo_global_active_100 --interval 1m --period 7d --limit 100
py -3.13 main.py sync-now --provider tdx --interval all --limit 100
py -3.13 main.py sync-now --provider tdx --interval all --limit 100 --batch-rounds 10
py -3.13 main.py sync-now --provider tdx --interval 1d --symbol sh600000
py -3.13 main.py sync-now --provider tdx --interval 1m --symbol sh600000
py -3.13 main.py sync-now --provider tdx --interval 5m --symbol sh600000
py -3.13 main.py sync-now --provider tdx --interval all --symbol sh600000
py -3.13 main.py sync-now --provider tdx --interval 1d --symbol "10#AUDUSD"
py -3.13 main.py sync-now --provider tdx_pipeline --interval all --symbol sh600000
py -3.13 main.py sync-now --provider tdx_pipeline --limit 20
py -3.13 main.py sync-now --provider tushare --symbol sh600000
py -3.13 main.py sync-now --provider tushare --limit 10
py -3.13 main.py sync-now --provider tdx_qfq --symbol sh600000 --interval 1d
```

提交平台回测建议优先通过前端或 API 入队，Worker 会异步执行并把结果写回数据库；行情同步现在也已跟随这一模式：前端 `/market-data` 和 `POST /api/market-data/sync` 会先创建 `data_ingestion_jobs` 队列任务，由 `main.py worker` 在后台领取并执行，页面会按任务状态自动轮询刷新；如需立刻同步并等待结果，仍可直接使用 `main.py sync-now`。当前 `provider=yahoo` 已支持通过 `--symbol-set yahoo_global_active_100` 导入内置 100 个全球高活跃样本；`provider=yahoo_pipeline` 会把这套默认样本，或当前单个 Yahoo 标的，串行补齐 `1d / 15m / 1m` 三个周期，并把 workflow 本身与三个子任务一起记入统一任务域。`provider=tdx` 当前已支持通达信原始 `1d / 1m / 5m` 文件导入，其中 `1m` 对应 `.lc1/.1`、`5m` 对应 `.lc5/.5`，并支持 `--interval all` 顺序导入配置路径下可见的全部 TDX 周期与市场；当前已覆盖常见 `sh / sz / bj / ds` 目录，其中 `ds` 市场的 `.day` 会按 `float32` 价格布局解析，命令行若传这类代码请使用引号包住 `#`。当 `provider=tdx` 以批量模式运行且传了 `--limit`、但未传 `--force` 和 `--symbol` 时，当前会优先挑选“还没有 manifest 的文件”以及“源文件已变化、需要重建/追加的文件”，避免多次分批导入反复卡在排序靠前、但已经导过的同一批文件；如果还额外传入 `--batch-rounds N`，同一条命令会继续串行执行多轮批量导入，直到达到轮数上限，或当前批量范围已经没有待导文件为止。`provider=tdx_pipeline` 则会把 `tdx raw -> tushare actions -> tdx_qfq rebuild` 串成一条统一 A 股补数链路，支持 `--interval 1d` 或 `--interval all`，并在批量模式下只跟随数据库中可映射 Tushare `ts_code` 的 `sh / sz / bj` 通达信原始 `1d` 标的继续抓取公司行动和重算前复权，不会把 `ds` 原始标的误送进 A 股链路；`provider=tushare` 和 `provider=tdx_qfq` 仍可单独执行公司行动抓取与前复权日线重算。回测读取链路当前仍优先兼容旧 `price_bars`，但若请求里显式给出 `market_data_provider` / `market_data_adjustment_kind`，或旧表没有该标的周期而统一主干表里只有唯一可用序列，Worker 也可以直接从 `market_data_series + market_data_bars` 读取真实落库行情继续回测；这让 `tdx` 原始序列和 `tdx_qfq` 前复权序列可以逐步进入统一研究主路径。最近任务区现在还支持打开任务详情，直接查看 `data_ingestion_job_items` 文件级/标的级明细；若 API 队列任务下挂了内部子任务，还可以在详情抽屉里继续跳转查看，同时也支持直接取消排队/执行中的统一导入任务，或把失败、部分失败、已取消的任务按原条件重新入队；同页新增“统一序列检查”卡片，可直接按 provider 和 symbol 查看 `market_data_series + market_data_bars` 中真实落库的标的、周期、复权口径、K 线条数与最近时间；新增“前复权输入与公式检查”卡片后，还可以继续按标的核对 `corporate_action_events` 里的实施事件和 `price_adjustment_segments` 里的 A/B 公式区间；新增“通达信原始文件 Manifest 检查”卡片后，则可以继续核对 `source_file_manifests` 中每个 `vipdoc` 文件最近是跳过、追加还是重建；新增“全链路诊断”抽屉后，可以围绕单个标的一次性查看最近相关任务、统一序列、manifest、公司行动和复权区间，并直接把目标标的定位到对应排查表。

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
- [多数据源行情后台规划](doc/multi-source-market-data-plan.md)
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
- `STRATEGY_STUDIO_TDX_VIPDOC`
- `STRATEGY_STUDIO_TDX_CONFIG_PATH`
- `STRATEGY_STUDIO_TUSHARE_TOKEN`
- `STRATEGY_STUDIO_TUSHARE_CONFIG_PATH`
- `STRATEGY_STUDIO_TUSHARE_RATE_LIMIT_PER_MINUTE`
- `STRATEGY_STUDIO_TUSHARE_TIMEOUT_SECONDS`
- `STRATEGY_STUDIO_TUSHARE_RETRIES`
- `STRATEGY_STUDIO_ENABLE_PROCESS_CONTROL`
- `STRATEGY_STUDIO_API_ORIGIN`

更多部署细节见 [部署指南](doc/deployment.md)。

## 测试

后端：

```powershell
py -3.13 -m unittest tests.test_qfq_data
py -3.13 -m unittest tests.test_tushare_data
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
