# ETF Strategy Frontend

这是 ETF Strategy 的 Web 控制台，基于 Next.js、React、Ant Design 和 ECharts 构建。

前端只负责交互和展示，不直接访问 PostgreSQL。所有数据都通过 FastAPI 获取。

## 页面

- `/`：平台概览。
- `/market-data`：行情统计、覆盖区间、同步记录。
- `/templates`：策略参数模板管理。
- `/backtests`：回测任务提交、队列查看和重试。
- `/reports`：历史报告列表。
- `/reports/[id]`：报告详情、权益曲线、交易和事件。

## 环境变量

```powershell
$env:NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"
```

如果不设置，前端应按代码中的默认 API 地址访问本地后端。

## 开发

```powershell
npm install
npx next dev --hostname 127.0.0.1 --port 3000
```

访问：

```text
http://127.0.0.1:3000
```

## 构建

```powershell
npm run lint
npm run build
npm run start
```

## 与后端协作

前端依赖以下 API 分组：

- `/api/market-data/*`
- `/api/backtests/*`
- `/api/reports/*`
- `/api/templates/*`

接口说明见 [API 接口说明](../doc/api.md)。整体架构见 [架构设计](../doc/architecture.md)。

## 开发约定

- 业务页面使用 `src/app/` 路由。
- 可复用视图组件放在 `src/components/`。
- API 调用封装在 `src/lib/api.ts`。
- 策略模板相关前端配置放在 `src/lib/strategy-template-config.ts`。
- 页面文案保持中文，风格偏内部研究平台，不做营销型落地页。
