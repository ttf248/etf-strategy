# ETF Strategy

基于 Yahoo Finance 数据的小型策略回测项目，当前聚焦小米港股 `1810.HK` 的左侧建仓 + 网格交易验证。

项目目标已经从早期的“ETF 补仓脚本”调整为“可重复运行的策略研究工程”。现在的仓库重点是：

- 统一入口：所有命令都从根目录 `main.py` 进入
- 单一数据源：仅保留 Yahoo 数据链路
- 可解释回测：日线主流程 + 分钟线补充研究，图表和中文报告同时输出

## 方法文档

- [日线网格参数测试方法](doc/grid_parameter_search.md)
- [Yahoo 分钟线支持与 15 分钟回测说明](doc/minute_grid_research.md)

## 当前策略口径

- 先定位最近一轮明显下跌样本，默认围绕 `2026-01-01` 前最近 `120` 天回看
- 从局部高点回撤 `10%` 后，使用总资金 `50%` 建立底仓
- 剩余 `50%` 资金用于双向网格
- 网格参数搜索维度：
  - `grid_spacing`：网格间距
  - `grid_count`：网格层数
  - `take_profit`：单层止盈比例
- 选优目标：收益、最大回撤、成本下降幅度的综合评分

### 参数怎么理解

当前默认总资金是 `200000`，其中：

- 底仓资金 `100000`：价格从局部高点回撤 `10%` 时一次性买入。
- 网格资金 `100000`：专门留给后续网格买卖。

这三个参数在当前实现里的实际含义是：

- `grid_spacing`
  - 表示每一层网格之间的价格间隔比例。
  - 例如最优参数里的 `6%`，含义是：以初始建仓价为基准，后续每跌 `6%` 再开下一层买入位。
  - 如果初始建仓价是 `53.35`，那么第 1 层大约在 `50.15`，第 2 层大约在 `46.95`，再往下继续展开。
- `grid_count`
  - 表示最多准备多少层网格仓位。
  - 例如最优参数里的 `7`，含义是：剩余那 `100000` 网格资金会被拆成 `7` 份预算，每层约 `14285.71`。
  - 实际成交时因为股票按整数股下单，所以每层真正投入金额会和预算有少量误差。
  - 这 `7` 层不是一次性全买，而是只有跌到对应价位才触发对应那一层。
- `take_profit`
  - 表示某一层网格买入后，价格从该层买入价反弹多少就把这一层卖掉。
  - 例如最优参数里的 `3%`，含义是：某层如果在 `46.00` 买入，只要涨到约 `47.38`，这一层就会止盈卖出。
  - 这里卖掉的是该层网格仓位，不会把最开始的底仓一起卖掉。

一句话概括：

- `grid_spacing` 决定“跌多少再补一层”
- `grid_count` 决定“最多补几层、每层分多少钱”
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
py -3.13 main.py optimize --data data/processed/xiaomi_1810_hk_daily.csv
```

输出目录默认是 `outputs/optimize/`，会生成：

- `in_sample_window.csv`
- `in_sample_grid_search.csv`
- `in_sample_best_*.csv`

### 3. 使用指定参数做 2026 样本外验证

```powershell
py -3.13 main.py backtest --data data/processed/xiaomi_1810_hk_daily.csv --grid-spacing 0.06 --grid-count 7 --take-profit 0.03
```

输出目录默认是 `outputs/validation/`。

上面这个例子翻成中文就是：

- 每跌 `6%` 开下一层网格
- 最多开 `7` 层
- 某层买入后，反弹 `3%` 就把这一层卖掉

### 4. 直接生成图表和中文报告

```powershell
py -3.13 main.py report --data data/processed/xiaomi_1810_hk_daily.csv
```

会重新执行样本内寻参与样本外验证，并输出到：

- 中间结果：`outputs/`
- 报告目录：`reports/`

如果要生成 15 分钟线报告：

```powershell
py -3.13 main.py report --data data/processed/xiaomi_1810_hk_15m.csv --interval 15m
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
3. 2026 样本外验证
4. 生成图表和中文报告

如果要跑默认 15 分钟线研究流程：

```powershell
py -3.13 main.py run --interval 15m --period 60d --proxy http://127.0.0.1:7897
```

分钟线默认使用最近 `60d` 数据，并按 `75% / 25%` 自动拆分样本内与样本外。

## 验证

```powershell
py -3.13 -m unittest tests.test_grid_strategy
```

## 输出说明

- `outputs/`：运行时中间文件，默认忽略版本控制
- `outputs/minute/`：分钟线研究中间文件，默认忽略版本控制
- `reports/`：图表与正式中文报告
- `reports/minute/`：15 分钟线研究报告
- `log/`：日志输出

## 设计取舍

- 使用 `backtesting.py` 做订单撮合和权益曲线，避免继续维护手写回测循环
- Yahoo 数据优先走 `yfinance`，失败后自动回退到 Yahoo Chart API，解决大陆环境限流和区域限制
- 报告里同时保留收益、回撤、成本摊薄，不把“摊薄成本”误当成“绝对赚钱”
