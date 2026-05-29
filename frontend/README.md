# Strategy Studio Frontend

这是 Strategy Studio 的回测实验室前端，基于 Next.js、React、Ant Design 和 ECharts 构建。

前端只负责交互和展示，不直接访问 PostgreSQL。所有数据都通过 FastAPI 获取。

当前全局壳层采用常见工作台布局：左侧只保留 Logo、研究主路径和维护入口；顶部收敛为“页头 + 单一决策横幅”，把研究状态、推荐下一步和关键判断统一放进同一个信息层级，避免侧栏或顶部看板承载过多并列说明信息。菜单抽屉只在移动端渲染，桌面端不再重复出现与左侧固定导航相同的入口。

## 页面

- `/`：研究总览，展示当前数据覆盖、推荐动作和最近结果入口。
- `/backtests`：创建回测，输入标的、选择模板并提交任务；任务区会实时显示当前阶段、预计剩余时间和平台实际采用的并发计划。
- `/reports`：查看报告，先按标的归纳哪一组最值得继续研究，再筛选历史回测结果并先看解释型结论。
- `/reports/[id]`：报告详情，先看收益、回撤、期末权益、相对买入持有表现和同标的横向定位，再展开权益曲线、交易和事件，并可直接带去对比同标的报告。
- `/market-data`：数据准备，先设定当前标的，再在同一页查看 Yahoo、通达信原始日线、Tushare 公司行动和通达信前复权的任务概览；其中 Yahoo 批量入口会默认走内置 `yahoo_global_active_100` 样本池，同时保留可直接回测样本的覆盖检查、推荐周期和高级明细。
- `/templates`：策略模板，查看默认模板、按目标筛选和对比适合谁用，并在高级编辑区维护参数预设。
- `/platform`：系统状态，展示服务健康、队列、同步调度、本机进程和最近日志。

## 环境变量

```powershell
$env:STRATEGY_STUDIO_API_ORIGIN="http://127.0.0.1:8000"
```

如果不设置，前端会默认把同源 `/api/*` 代理到本机 `http://127.0.0.1:8000`。只有后端不跑在默认地址时，才需要显式覆盖这个变量。

## 开发

```powershell
npm install
$env:STRATEGY_STUDIO_API_ORIGIN="http://127.0.0.1:8000"
npx next dev --hostname 127.0.0.1 --port 3000
```

访问：

```text
http://127.0.0.1:3000
```

## 构建

```powershell
npm run lint
$env:STRATEGY_STUDIO_API_ORIGIN="http://127.0.0.1:8000"
npm run build
npm run start
```

## 冒烟验证

先确保本地 API 已启动，并且已经执行过 `init-db`，同时数据库里已经有可回测行情；你可以通过 `sync-now` 或前端数据覆盖页预先准备数据。

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
- 浏览器端默认只请求同源 `/api/*`，由 Next 服务代理到 FastAPI。
- 策略模板相关前端配置放在 `src/lib/strategy-template-config.ts`。
- 页面文案保持中文，优先服务策略研究场景；系统状态和内部进程概念只放在维护入口。
