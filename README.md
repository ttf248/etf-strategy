# ETF Strategy

基于 Yahoo Finance 数据的小型策略回测项目，当前聚焦小米港股 `1810.HK` 的样本起点建仓 + 固定股数网格交易验证。

项目目标已经从早期的“ETF 补仓脚本”调整为“可重复运行的策略研究工程”。现在的仓库重点是：

- 统一入口：所有命令都从根目录 `main.py` 进入
- 单一数据源：仅保留 Yahoo 数据链路
- 可解释回测：日线主流程 + 分钟线补充研究，图表、交易表格和中文报告同时输出

## 仓库内置正式样本

为了保证默认流程可复现，仓库会直接跟踪两份正式样本数据：

- `data/processed/xiaomi_1810_hk_daily.csv`
- `data/processed/xiaomi_1810_hk_15m.csv`

它们分别对应：

- 日线主流程默认输入
- `15m` 分钟线研究默认输入

测试临时 CSV 和一次性研究样本不会一起纳入版本控制。

## 方法文档

- [日线网格参数测试方法](doc/grid_parameter_search.md)
- [Yahoo 分钟线支持与 15 分钟回测说明](doc/minute_grid_research.md)

## 当前策略口径

- 日线主流程：
  - 以 `2026-01-01` 作为样本外起点
  - 向前回看 `120` 天作为样本内窗口
- 分钟线研究：
  - 使用 Yahoo 最近 `60d` 的 `15m` 数据
  - 按 `75% / 25%` 拆分样本内与样本外
- 资金规则：
  - 总资金 `200000`
  - 样本开始时用 `50%` 资金建立底仓
  - 剩余 `50%` 资金用于双向网格
- 下单规则：
  - 底仓和网格都按“股数”下单，不再按“固定金额”下单
  - 先查询标的最小交易单位，再按整手向下取整
  - 当前支持：
    - 港股：抓取公开页面里的 `Lot Size`
    - 美股：默认 `1` 股
    - 其他市场：直接报错
- 选优目标：收益、最大回撤、成本下降幅度的综合评分

### 参数怎么理解

当前日线最优参数是：

- `grid_spacing = 7%`
- `grid_count = 5`
- `take_profit = 3%`

这三个参数在当前实现里的实际含义是：

- `grid_spacing`
  - 表示每一层网格之间的价格间隔比例。
  - 例如 `7%` 的含义是：以样本起点的底仓建仓价为基准，后续每跌 `7%` 再开下一层买入位。
  - 如果底仓建仓价是 `55.85`，那么第 1 层大约在 `51.94`，第 2 层大约在 `48.03`。
- `grid_count`
  - 表示最多准备多少层网格仓位。
  - 例如 `5` 的含义是：最多允许开启 `5` 层固定股数网格仓位。
  - 它不再表示“把剩余资金拆成几份预算”；现在每一层买入的都是同样的固定股数。
  - 当前这组日线最优参数里：
    - 底仓固定数量：`1600` 股
    - 单层网格固定数量：`200` 股
  - 这 `5` 层不是一次性全买，而是只有跌到对应价位才触发对应那一层。
- `take_profit`
  - 表示某一层网格买入后，价格从该层买入价反弹多少就把这一层卖掉。
  - 例如 `3%` 的含义是：某层如果在 `48.00` 买入，只要涨到约 `49.44`，这一层就会止盈卖出。
  - 这里卖掉的是该层网格仓位，不会把最开始的底仓一起卖掉。

一句话概括：

- `grid_spacing` 决定“跌多少再补一层”
- `grid_count` 决定“最多补几层固定股数仓位”
- `take_profit` 决定“某层买进去后，反弹多少先兑现这一层”

## 项目结构

```text
etf_strategy/
  data/          Yahoo 下载与标准化
  strategy/      网格策略、样本切分、参数搜索
  reporting.py   图表与 Markdown 报告生成
  workflow.py    样本内/样本外工作流编排
main.py          统一 CLI 入口
tests/           标准库 unittest 用例
```

## 安装依赖

```powershell
py -3.13 -m pip install -r requirements.txt
```

如果你在中国大陆直连 Yahoo，通常需要代理。可以二选一：

```powershell
$env:ETF_STRATEGY_PROXY="http://127.0.0.1:7897"
```

或者在命令里显式传：

```powershell
--proxy http://127.0.0.1:7897
```

## 命令说明

### 1. 下载并标准化小米港股数据

```powershell
py -3.13 main.py download --start 2024-01-01 --end 2026-05-22 --proxy http://127.0.0.1:7897
```

默认输出到 `data/processed/xiaomi_1810_hk_daily.csv`。

如果要下载默认分钟线研究样本：

```powershell
py -3.13 main.py download --symbol 1810.HK --interval 15m --period 60d --proxy http://127.0.0.1:7897
```

默认输出到 `data/processed/xiaomi_1810_hk_15m.csv`。

### 2. 样本内参数搜索

```powershell
py -3.13 main.py optimize --data data/processed/xiaomi_1810_hk_daily.csv --symbol 1810.HK
```

输出目录默认是 `outputs/optimize/`，会生成：

- `in_sample_window.csv`
- `in_sample_grid_search.csv`
- `in_sample_best_*.csv`

如果你的 CSV 文件名不是类似 `1810_hk_1d.csv`、`xiaomi_1810_hk_daily.csv` 这种可推断格式，建议显式传 `--symbol`。

### 3. 使用指定参数做日线样本外验证

```powershell
py -3.13 main.py backtest --data data/processed/xiaomi_1810_hk_daily.csv --symbol 1810.HK --grid-spacing 0.07 --grid-count 5 --take-profit 0.03
```

输出目录默认是 `outputs/validation/`。

上面这个例子翻成中文就是：

- 每跌 `7%` 开下一层网格
- 最多开 `5` 层固定股数网格
- 某层买入后，反弹 `3%` 就把这一层卖掉

### 4. 直接生成图表和中文报告

```powershell
py -3.13 main.py report --data data/processed/xiaomi_1810_hk_daily.csv --symbol 1810.HK
```

会重新执行样本内寻参与样本外验证，并输出到：

- 中间结果：`outputs/`
- 报告目录：`reports/`

如果要生成 15 分钟线报告：

```powershell
py -3.13 main.py report --data data/processed/xiaomi_1810_hk_15m.csv --symbol 1810.HK --interval 15m
```

对应输出到：

- 中间结果：`outputs/minute/`
- 报告目录：`reports/minute/`

### 5. 一键执行完整流程

```powershell
py -3.13 main.py run --start 2024-01-01 --end 2026-05-22 --proxy http://127.0.0.1:7897
```

该命令会依次完成：

1. 下载 Yahoo 数据
2. 样本内寻参
3. 日线样本外验证
4. 生成图表和中文报告

如果要跑默认 15 分钟线研究流程：

```powershell
py -3.13 main.py run --interval 15m --period 60d --proxy http://127.0.0.1:7897
```

分钟线默认使用最近 `60d` 数据，并按 `75% / 25%` 自动拆分样本内与样本外。

## VS Code 调试

仓库已提供 `.vscode/launch.json`，覆盖当前主要入口：

- 下载日线数据
- 下载 15 分钟数据
- 日线样本内寻参
- 日线生成报告
- 15 分钟生成报告
- 日线完整流程
- 15 分钟完整流程

直接在 VS Code 的 Run and Debug 面板里选择对应配置即可。

## 验证

```powershell
py -3.13 -m unittest tests.test_grid_strategy
```

## 输出说明

- `data/processed/`：默认正式样本输入，当前只跟踪日线与 `15m` 两份小米样本
- `outputs/`：运行时中间文件，默认忽略版本控制
- `outputs/minute/`：分钟线研究中间文件，默认忽略版本控制
- `reports/`：图表、交易表格与正式中文报告
- `reports/minute/`：15 分钟线研究报告
- `log/`：日志输出

## 设计取舍

- 使用 `backtesting.py` 做订单撮合和权益曲线，避免继续维护手写回测循环
- Yahoo 数据优先走 `yfinance`，失败后自动回退到 Yahoo Chart API，解决大陆环境限流和区域限制
- 固定股数下单先查最小交易单位，避免出现港股按非整手数量回测、结果不符合真实交易规则
- 报告里同时保留收益、回撤、成本摊薄和交易记录，不把“摊薄成本”误当成“绝对赚钱”
