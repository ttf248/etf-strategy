# 开发与维护说明

这份文档面向后续维护者，重点回答：

- 从哪里进入代码
- 常见改动应该改哪里
- 哪些改动必须同步更新文档和测试

## 运行入口

统一入口是根目录 `main.py` 的 `main()`。

不要把 `python -m 包名` 当成主运行方式。

## 关键模块职责

### `etf_strategy/cli.py`

负责：

- 解析命令行参数
- 选择日线或分钟线工作流
- 转发平台模式相关命令
- 输出适合终端阅读的中文结果

不负责：

- 具体回测逻辑
- 报告模板细节

### `etf_strategy/workflow.py`

负责：

- 串起样本切分、样本内寻参、样本外验证、结果落盘
- 根据 `strategy_kind` 在网格与反转类策略之间分发

它是编排层，不适合继续堆大量文案解释。

### `etf_strategy/strategy/grid.py`

负责：

- 核心网格回测逻辑
- 样本切分
- 参数搜索
- 综合评分

### `etf_strategy/strategy/rebound.py`

负责：

- 日线超跌反弹
- 分钟急跌反抽
- 分钟反抽 + 冲高回落过滤
- 反转类策略的参数搜索与权益曲线产物

### `etf_strategy/strategy/index_grid.py`

负责：

- 三只指数 ETF 的 `1m` 动态回落/反弹网格策略
- 50% 底仓 + 20% 固定交易单元的交易状态机
- 相对买入持有的收益对照字段

### `etf_strategy/reporting.py`

负责：

- 图表生成
- Markdown 报告模板
- 把结构化结果翻译成更适合阅读的中文说明

它应该承担“结果解释”，不应该承担项目首页教程职责。

### `etf_strategy/data/`

负责：

- Yahoo 数据下载与标准化；下载必须配置代理，失败后直接停止
- 交易单位规则
- 日线全历史默认下载口径
- 分钟线本地样本增量合并

### `etf_strategy/db/`

负责：

- PostgreSQL 连接配置
- SQLAlchemy 模型
- Alembic 迁移
- 数据库初始化

### `etf_strategy/repositories/`

负责：

- 行情、同步任务、回测任务、报告的数据库读写
- PostgreSQL upsert、统计查询和任务状态流转
- 策略参数模板的列表、查询、默认模板切换和落库更新

### `etf_strategy/services/`

负责：

- CSV 导入
- 行情统计与数据库查询
- Yahoo 同步任务
- 异步回测任务提交与结果落库
- 模板种子初始化、模板 CRUD 和模板到回测请求的合并

### `etf_strategy/web/`

负责：

- FastAPI 应用
- Web API 路由
- 前端消费的 JSON 契约，包括模板中心接口

### `etf_strategy/runtime/`

负责：

- 常驻 worker 轮询执行回测任务
- APScheduler 定时同步 Yahoo 行情

### `frontend/`

负责：

- Next.js 前端控制台
- 行情统计、回测任务、历史报告页面
- 调用 FastAPI 接口并展示结构化报告

## 常见改动应该改哪里

### 新增命令或调整 CLI 参数

至少同步更新：

- `etf_strategy/cli.py`
- `etf_strategy/platform_cli.py`
- `etf_strategy/data/yahoo.py`
- `README.md`
- `.vscode/launch.json`
- 对应测试

### 修改样本切分规则

至少同步更新：

- `etf_strategy/strategy/grid.py`
- `etf_strategy/workflow.py`
- `README.md`
- 对应专题文档
- 报告口径

### 修改报告结构或解释口径

至少同步更新：

- `etf_strategy/reporting.py`
- `doc/xiaomi_strategy_research.md`
- [回测报告阅读指南](report_reading_guide.md)
- 示例报告
- `task.md`

### 修改默认样本数据或默认路径

至少同步更新：

- `etf_strategy/config.py`
- `etf_strategy/cli.py`
- `.gitignore`
- `README.md`
- 相关测试

### 修改下载与样本积累规则

至少同步更新：

- `etf_strategy/data/yahoo.py`
- `etf_strategy/services/sync.py`
- `etf_strategy/repositories/market_data.py`
- `etf_strategy/cli.py`
- `doc/glossary.md`
- `doc/minute_grid_research.md`
- `.vscode/launch.json`
- `task.md`

### 修改默认调试入口

当前仓库保留更直接的 `launch.json` 样式，VS Code 配置收敛为两部分：

- `.vscode/launch.json`：负责一键启动
- `.vscode/settings.json`：负责终端 profile

其中 `launch.json` 当前提供四条单进程调试配置和两条组合启动：

- 启动前端 Dev Server
- 启动 API 服务
- 启动回测 Worker
- 启动行情 Scheduler
- 启动平台后端全套
- 启动平台前后端全套

使用这些配置的前提是 VS Code 已安装 Microsoft 的 Python / Python Debugger 扩展，否则 `debugpy` 调试类型不会被注册。

另外，VS Code 一键启动使用的是当前工作区选中的 Python 解释器。第一次启动平台前，先执行 `Python: Select Interpreter`，并确认该解释器已经安装：

- `py -3.13 -m pip install -r requirements.txt`

如果 `启动 API 服务` 报 `No module named 'uvicorn'`，通常就是解释器切错了，或者切换后还没有在该环境里安装依赖。

Python 调试配置统一采用下面这组字段：

- `type=debugpy`
- `request=launch`
- `program=${workspaceFolder}/main.py`
- `cwd=${workspaceFolder}`
- `console=integratedTerminal`
- `args` 中显式传入 `api`、`worker` 或 `scheduler`
- 运行时直接看 VS Code 集成终端里的 `INFO` 级别提示
- 更详细的定位日志仍写入 `log/etf_strategy_YYYY-MM-DD.log`
- `main.py` 会主动尝试把 Windows 控制台切到 UTF-8，`.vscode/launch.json` 也会显式传入 `PYTHONUTF8=1` 和 `PYTHONIOENCODING=utf-8`
- `report` 命令会输出 `[1/2] -> [2/2]` 进度，`run` 命令会输出 `[1/3] -> [2/3] -> [3/3]` 顶层进度
- `batch` 命令用于多标的研究汇总，默认分钟线周期为 `15m`，把单标的结果写到 `outputs/batch/<symbol>/`，批量汇总写到 `outputs/batch/batch_summary.csv`，所有单标的/批量/单策略/多策略对比都会统一回写到 `reports/report_index.md`，单标的正式报告写到 `reports/<symbol>/minute/`
- 内置标的池除了 `hstech_plus_513050`，还支持 `southbound_shanghai_all` 和 `index_grid_etfs`
- `index_grid_etfs` 当前固定为 `159941.SZ`、`159605.SZ`、`159866.SZ`，默认策略是 `minute_index_grid_retrace`
- `reports/report_index.md` 会把样本外净收益率高于 `5%` 的记录加粗，便于在大批量回测后快速定位高收益候选

前端调试入口使用 `node-terminal`，在 `frontend/` 目录下直接执行：

- `npx next dev --hostname 127.0.0.1 --port 3000`

并显式传入：

- `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000`

Windows 环境如果想直接拉起四个窗口，使用：

- `scripts/start_platform_windows.bat`

该脚本会先检查 `uvicorn / fastapi / sqlalchemy / psycopg` 是否已安装；缺失时直接提示先安装 `requirements.txt`，不再继续拉起后端窗口。

这里没有继续使用参考示例里的 `type=python`，因为微软当前 Python 调试文档已经把 `debugpy` 作为 Python Debugger 扩展的调试类型；旧写法在部分 VS Code 环境里会导致无法启动调试。

`settings.json` 里额外固定：

- `terminal.integrated.defaultProfile.windows=PowerShell -NoProfile`
- `terminal.integrated.automationProfile.windows=PowerShell -NoProfile`

这样可以减少 PowerShell Profile 对调试和任务终端的干扰。

如果代码改动会影响：

- 运行命令
- 默认样本路径
- 默认 symbol / interval
- 报告生成入口

就必须同步更新 `.vscode/launch.json` 和需要受影响的 `.vscode/settings.json`，并实际执行对应命令确认它还能跑通。

## 文档更新触发条件

下面这些改动，默认都必须同步更新文档：

- 新增命令
- 修改参数含义
- 修改样本切分口径
- 修改报告结构
- 修改正式样本文件名或路径
- 修改输出目录约定

## 测试约定

当前项目使用标准库 `unittest`。

默认验证命令：

```powershell
py -3.13 -m unittest tests.test_grid_strategy
```

如果改动涉及文档链接、报告结构或默认样本路径，后续应补轻量检查，避免文档和代码口径脱节。

## 关于 `task.md`

`task.md` 需要持续更新，但它的职责是：

- 记录 AI 任务背景
- 记录本轮修改方案、修改内容和设计取舍

它不是正式用户文档，也不应该替代 `doc/`。
