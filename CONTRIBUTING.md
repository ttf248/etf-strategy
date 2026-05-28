# 贡献指南

感谢关注 Strategy Studio。这个项目面向策略研究平台建设，贡献时请优先保持架构清晰、数据口径明确、文档和测试同步。

## 开发流程

1. 安装后端依赖：

```powershell
py -3.13 -m pip install -r requirements.txt
```

2. 安装前端依赖：

```powershell
cd frontend
npm install
```

3. 初始化数据库并导入样例数据：

```powershell
py -3.13 main.py init-db
py -3.13 main.py import-csv --source-dir data/samples
```

4. 使用 VS Code 一键启动，或按 [部署指南](doc/deployment.md) 分别启动 API、Worker、Scheduler 和前端。

## 提交要求

- Git 提交日志使用中文。
- 每个提交只包含一个清晰目标。
- 不提交 `outputs/`、`log/`、前端构建缓存和一次性实验产物。
- 修改命令、API、数据库、数据流、部署或报告口径时，必须同步更新文档。
- 不再维护 `task.md`；任务背景和设计取舍应通过提交、注释、测试和长期文档沉淀。

## 测试要求

后端常用验证：

```powershell
py -3.13 -m unittest tests.test_platform_features tests.test_repo_contracts
py -3.13 -m unittest tests.test_grid_strategy tests.test_yahoo_data
git diff --check
```

前端常用验证：

```powershell
cd frontend
npm run lint
npm run build
```

文档-only 改动至少运行：

```powershell
py -3.13 -m unittest tests.test_repo_contracts
git diff --check
```

## 文档规范

- 文档默认使用中文。
- 用户文档只描述当前仓库真实能力，不提前承诺未实现功能。
- 架构、数据流、部署、运维和开发说明分别维护，避免 README 过长。
- 开源样例报告位于 `reports/examples/`，平台运行产物默认写入 `reports/platform/`。

## 数据和策略口径

- PostgreSQL 是平台长期主存储。
- CSV 是导入、调试和兼容 CLI 的输入形式。
- Yahoo 数据访问失败时应明确报错，不静默切换数据源。
- 策略结果必须说明样本、周期、执行口径和费用/风控假设。
