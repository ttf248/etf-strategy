# 部署指南

本文按生产部署思路说明当前仓库可运行的部署方式。仓库暂未提供 Docker Compose、systemd 或反向代理配置文件，因此这些部分只给出落地要求，不虚构未提交的脚本。

## 运行组件

生产环境至少包含：

- PostgreSQL 服务器。
- Python 后端环境。
- Node.js 前端环境。
- API 进程。
- Worker 进程。
- Scheduler 进程。
- 前端构建和服务进程。

## 基础依赖

后端：

```powershell
py -3.13 -m pip install -r requirements.txt
```

前端：

```powershell
cd frontend
npm install
npm run build
```

PostgreSQL 默认连接：

```text
postgresql+psycopg://postgres:tian@localhost:5432/strategy_studio
```

生产环境建议通过环境变量覆盖默认值，不要依赖本地默认密码。

## 环境变量

常用环境变量：

- `STRATEGY_STUDIO_DATABASE_URL`：平台数据库连接串。
- `STRATEGY_STUDIO_ADMIN_DATABASE`：初始化数据库时连接的管理员库，默认 `postgres`。
- `STRATEGY_STUDIO_API_HOST`：API 默认监听地址。
- `STRATEGY_STUDIO_API_PORT`：API 默认监听端口。
- `STRATEGY_STUDIO_FRONTEND_HOST`：前端默认主机。
- `STRATEGY_STUDIO_FRONTEND_PORT`：前端默认端口。
- `STRATEGY_STUDIO_PLATFORM_OUTPUT_DIR`：平台中间产物目录。
- `STRATEGY_STUDIO_PLATFORM_REPORT_DIR`：平台报告导出目录。
- `STRATEGY_STUDIO_PROXY`：访问 Yahoo 时使用的代理。
- `NEXT_PUBLIC_API_BASE_URL`：前端访问 API 的基础地址。

## 初始化数据库

```powershell
py -3.13 main.py init-db
py -3.13 main.py import-csv --source-dir data/processed
```

`init-db` 会创建项目数据库并执行 Alembic 迁移。`import-csv` 用于把仓库已有的标准化行情导入 PostgreSQL。

## 启动后端

API：

```powershell
py -3.13 main.py api --host 127.0.0.1 --port 8000 --replace-existing
```

Worker：

```powershell
py -3.13 main.py worker --poll-interval 5
```

Scheduler：

```powershell
py -3.13 main.py scheduler
```

如果 Yahoo 访问需要代理：

```powershell
$env:STRATEGY_STUDIO_PROXY="http://127.0.0.1:7897"
py -3.13 main.py scheduler --proxy $env:STRATEGY_STUDIO_PROXY
```

## 启动前端

开发模式：

```powershell
cd frontend
$env:NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"
npx next dev --hostname 127.0.0.1 --port 3000
```

生产模式：

```powershell
cd frontend
$env:NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"
npm run build
npm run start
```

## 进程守护建议

生产部署时，应使用系统级进程管理器守护 API、Worker、Scheduler 和前端服务。要求：

- 每个进程独立启动和重启。
- 日志输出落盘并可检索。
- 数据库连接串和代理通过环境变量注入。
- API 不直接暴露到公网时，由反向代理负责 TLS、域名和访问控制。
- Worker 和 Scheduler 不需要公网入口。

## Windows 开发一键启动

本地开发可使用：

```powershell
scripts\start_platform_windows.bat
```

该脚本会拉起 API、Worker、Scheduler 和前端 Dev Server。API 会使用 `--replace-existing` 替换本项目残留的旧 API 进程；前端如果 `3000` 被占用，会要求先释放端口。
