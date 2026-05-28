# Strategy Studio Frontend

这是 Strategy Studio 的回测实验室前端，基于 Next.js、React、Ant Design 和 ECharts 构建。

前端只负责交互和展示，不直接访问 PostgreSQL。所有数据都通过 FastAPI 获取。

## 页面

- `/`：新手首页，解释如何开始第一次回测。
- `/backtests`：创建回测，输入标的、选择模板并提交任务。
- `/reports`：查看报告，筛选历史回测结果并先看解释型结论。
- `/reports/[id]`：报告详情，先看结论、收益、回撤，再展开权益曲线、交易和事件，并可直接带去对比同标的报告。
- `/market-data`：数据准备，输入标的检查是否已有可回测行情，直接查看推荐示例标的和应补周期，缺数据时再同步。
- `/templates`：策略模板，查看默认模板、按目标筛选和对比适合谁用，并在高级编辑区维护参数预设。
- `/platform`：系统状态，展示服务健康、队列、同步调度、本机进程和最近日志。

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

## 冒烟验证

先确保本地 API 已启动，并且已经执行过 `init-db` 与 `import-csv` 导入样例行情。

首次执行需要安装浏览器：

```powershell
npx playwright install chromium
```

然后执行：

```powershell
npm run test:smoke
```

该命令默认优先复用本地 `3000` 端口上已经运行的前端；如果本地没有运行实例，则会自动拉起一个测试专用前端服务，并使用真实 FastAPI 接口验证“首页 -> 创建回测 -> 提交任务”的主路径。测试结束后会对新建任务补发取消请求，避免队列持续堆积。

## 与后端协作

前端依赖以下 API 分组：

- `/api/market-data/*`
- `/api/backtests/*`
- `/api/reports/*`
- `/api/templates/*`
- `/api/platform/*`

接口说明见 [API 接口说明](../doc/api.md)。整体架构见 [架构设计](../doc/architecture.md)。

## 开发约定

- 业务页面使用 `src/app/` 路由。
- 可复用视图组件放在 `src/components/`。
- API 调用封装在 `src/lib/api.ts`。
- 策略模板相关前端配置放在 `src/lib/strategy-template-config.ts`。
- 页面文案保持中文，优先服务第一次使用的回测用户；系统状态和内部进程概念只放在维护入口。
