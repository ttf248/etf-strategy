# 指数 ETF 1 分钟回落反弹网格说明

这份文档只解释一件事：

- 仓库里新增的 `minute_index_grid_retrace` 到底在验证什么
- 三只指数 ETF 用的固定参数是什么
- 应该用什么命令生成报告

## 策略目标

这套策略不是去预测方向，而是验证：

- 指数长期上涨假设下，先拿 `50%` 底仓
- 再用总资金 `20%` 的固定交易单元
- 去吃分钟级波动里的“下跌后反弹买入、上涨后回落卖出”

最终判断标准不是“网格成交了几次”，而是：

- 策略最终收益是否跑赢同标的买入持有

## 当前固定支持的三只 ETF

| 标的 | 名称 | 上涨触发 | 回落卖出 | 下跌触发 | 反弹买入 |
| --- | --- | --- | --- | --- | --- |
| `159941.SZ` | 纳指ETF | `2%` | `0.5%` | `2%` | `0.5%` |
| `159605.SZ` | 中概互联网ETF | `2%` | `0.5%` | `2%` | `0.5%` |
| `159866.SZ` | 日经ETF | `3%` | `0.8%` | `3%` | `0.8%` |

补充口径：

- 总资金：`10000`
- 底仓比例：`50%`
- 单次网格比例：`20%`
- 最小交易单位：A 股 ETF 默认 `100` 股

## 触发语义

策略按“条件单语义”而不是固定锚点网格运行：

1. 先以首根 `1m` K 线收盘价附近建立底仓
2. 相对最近参考成交价，先出现足够大的上涨或下跌
3. 再记录后续局部高点或低点
4. 从局部高点回落到阈值时卖出一笔网格仓
5. 从局部低点反弹到阈值时买入一笔网格仓
6. 每次网格成交后，参考价重置为最新成交价

底仓默认长期持有，不参与网格卖出。

## 推荐命令

### 批量生成三只 ETF 的 1 分钟报告

```powershell
py -3.13 main.py batch --symbol-set index_grid_etfs --strategy minute_index_grid_retrace --interval 1m --period 60d --download --proxy http://127.0.0.1:7897 --jobs auto --cache-dir outputs/cache/index_grid_1m --output-dir outputs/index_grid --report-dir reports
```

### 基于已有本地 CSV 生成单标的报告

```powershell
py -3.13 main.py report --data data/processed/159941_sz_1m.csv --symbol 159941.SZ --interval 1m --strategy minute_index_grid_retrace --output-dir outputs/index_grid/159941 --report-dir reports/159941_sz/minute
```

### 只做样本外验证

```powershell
py -3.13 main.py backtest --data data/processed/159941_sz_1m.csv --symbol 159941.SZ --interval 1m --strategy minute_index_grid_retrace --output-dir outputs/index_grid/159941/validation
```

## 输出路径

- 中间结果：`outputs/index_grid/`
- 单标的报告目录：`reports/<symbol>/minute/`
- 报告文件命名：`<symbol>_1m_index_grid_report.md`
- 正式汇总索引：`reports/report_index.md`

## 结果怎么读

看报告时优先看这三个字段：

- `StrategyVsBuyHold`
- `OutperformBuyHold`
- `GridRealizedProfit`

阅读顺序建议：

1. 先看样本外是否跑赢买入持有
2. 再看跑赢来自底仓还是来自网格兑现
3. 最后再看交易流水确认触发是否符合预期

如果样本外没有跑赢买入持有，不代表网格逻辑完全无效，只代表在最近 `60d` 的 `1m` 波动结构里，这套固定参数没有体现出优势。
