# 开发指南

本文面向贡献者和维护者，说明如何开发、测试和提交改动。

## 本地环境

后端依赖：

```powershell
py -3.13 -m pip install -r requirements.txt
```

前端依赖：

```powershell
cd frontend
npm install
```

数据库默认使用本机 PostgreSQL：

```text
localhost:5432
database: strategy_studio
admin user: postgres
```

密码和连接串可以通过 `STRATEGY_STUDIO_DATABASE_URL` 覆盖。

本地导入目录与运行产物分离：

- `data/processed/`：手工准备后等待导入数据库的临时 CSV，默认不提交。
- `reports/platform/`：只有显式导出时才会生成的临时报告，默认不提交。

## 开发启动

推荐使用 VS Code 的 `启动平台前后端全套`，它会拉起：

- 前端 Dev Server。
- API 服务。
- 回测 Worker。
- 行情 Scheduler。

命令行方式：

```powershell
py -3.13 main.py api --host 127.0.0.1 --port 8000 --replace-existing
py -3.13 main.py worker --poll-interval 5
py -3.13 main.py scheduler
cd frontend
npx next dev --hostname 127.0.0.1 --port 3000
```

## 代码组织

- 后端入口固定为根目录 `main.py`。
- 不使用 `python -m 包名` 作为主运行方式。
- CLI、API、Worker 和 Scheduler 共享同一套服务层和策略工作流。
- 前端不直接访问数据库，只通过 FastAPI。

## 常见开发任务

新增 API：

- 在 `strategy_studio/web/app.py` 添加路由。
- 在 `strategy_studio/web/schemas.py` 添加请求模型。
- 在 `services/` 和 `repositories/` 中分别实现业务逻辑和数据库访问。
- 更新 [API 接口说明](api.md) 和测试。

新增策略：

- 在 `strategy_studio/strategy/` 中实现策略逻辑。
- 在 `strategy_studio/strategy/registry.py` 注册策略代码、中文名、支持周期、参数字段、寻参入口和验证入口。
- 如需平台提交，确认模板服务和前端模板配置能读取或同步该参数空间。
- 如需专用报告，更新 `reporting.py`；否则复用通用报告结构。
- 更新 [策略引擎](strategy-engine.md)。

修改数据表：

- 更新 SQLAlchemy 模型。
- 新增 Alembic 迁移。
- 更新 [数据流转](data-flow.md) 和相关服务测试。

修改启动入口：

- 更新 `.vscode/launch.json`。
- 更新 `scripts/start_platform_windows.bat`。
- 更新 [部署指南](deployment.md) 和 [运维手册](operations.md)。

## 测试

常用验证：

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

如果改动只涉及文档，至少运行 `tests.test_repo_contracts` 和 `git diff --check`。

## 文档同步规则

以下改动必须同步更新文档：

- 新增或修改命令。
- 新增或修改 API。
- 修改数据库表或数据流。
- 修改启动方式、端口、环境变量。
- 修改策略口径、报告口径或默认导入路径。
- 修改前端页面或主要工作流。

## 提交约定

- Git 提交日志使用中文。
- 每个提交只包含当前任务相关文件。
- 不提交运行缓存、日志和一次性实验产物。
- 不再维护 `task.md`；需要长期保留的任务背景和取舍应写入文档、注释或提交记录。
