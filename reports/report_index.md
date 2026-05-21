# 正式报告总览

## 汇总说明

- 正式报告总数：`34`，成功 `31`，失败 `3`。
- 这份文件是唯一正式汇总报告；单个合约、批量合约、单策略报告和多策略对比报告都收录在同一张表里。
- 主键口径：`symbol + interval + report_view`；同一视图重复生成时会覆盖旧记录。

## 报告列表

| 分类 | 标的 | 名称 | 周期 | 视图 | 策略 | 样本外收益 | 最大回撤 | 状态 | 备注 | 报告 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 国内ETF | 513050.SS | 中概互联网ETF | 15m | grid | 网格 | 0.00% | 0.00% | ok | 间距 4.00% / 层数 7 / 止盈 3.00% | [打开报告](513050_ss/minute/513050_ss_15m_grid_report.md) |
| 恒生科技成分股 | 0020.HK | SENSETIME - W | 15m | grid | 网格 | -0.17% | 1.01% | ok | 间距 4.00% / 层数 4 / 止盈 1.00% | [打开报告](0020_hk/minute/0020_hk_15m_grid_report.md) |
| 恒生科技成分股 | 0241.HK | ALI HEALTH | 15m | grid | 网格 | -1.68% | 2.03% | ok | 间距 4.00% / 层数 7 / 止盈 1.00% | [打开报告](0241_hk/minute/0241_hk_15m_grid_report.md) |
| 恒生科技成分股 | 0268.HK | KINGDEE INT'L | 15m | grid | 网格 | -0.82% | 1.45% | ok | 间距 4.00% / 层数 7 / 止盈 3.00% | [打开报告](0268_hk/minute/0268_hk_15m_grid_report.md) |
| 恒生科技成分股 | 0285.HK | BYD ELECTRONIC | 15m | grid | 网格 | 0.00% | 0.00% | ok | 间距 4.00% / 层数 7 / 止盈 1.00% | [打开报告](0285_hk/minute/0285_hk_15m_grid_report.md) |
| 恒生科技成分股 | 0300.HK | MIDEA GROUP | 15m | grid | 网格 | 0.43% | 0.46% | ok | 间距 4.00% / 层数 6 / 止盈 3.00% | [打开报告](0300_hk/minute/0300_hk_15m_grid_report.md) |
| 恒生科技成分股 | 0700.HK | TENCENT | 15m | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=100, price=534.50 | [打开报告](0700_hk/minute/0700_hk_15m_grid_report.md) |
| 恒生科技成分股 | 0780.HK | TONGCHENGTRAVEL | 15m | grid | 网格 | -1.16% | 1.59% | ok | 间距 4.00% / 层数 6 / 止盈 2.00% | [打开报告](0780_hk/minute/0780_hk_15m_grid_report.md) |
| 恒生科技成分股 | 0981.HK | SMIC | 15m | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=500, price=71.10 | [打开报告](0981_hk/minute/0981_hk_15m_grid_report.md) |
| 恒生科技成分股 | 0992.HK | LENOVO GROUP | 15m | grid | 网格 | 2.47% | 0.87% | ok | 间距 1.00% / 层数 4 / 止盈 3.00% | [打开报告](0992_hk/minute/0992_hk_15m_grid_report.md) |
| 恒生科技成分股 | 1024.HK | KUAISHOU - W | 15m | grid | 网格 | 0.00% | 0.00% | ok | 间距 4.00% / 层数 7 / 止盈 2.00% | [打开报告](1024_hk/minute/1024_hk_15m_grid_report.md) |
| 恒生科技成分股 | 1211.HK | BYD COMPANY | 15m | grid | 网格 | -3.87% | 4.51% | ok | 间距 1.50% / 层数 4 / 止盈 2.00% | [打开报告](1211_hk/minute/1211_hk_15m_grid_report.md) |
| 恒生科技成分股 | 1347.HK | HUA HONG SEMI | 15m | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=1000, price=98.75 | [打开报告](1347_hk/minute/1347_hk_15m_grid_report.md) |
| 恒生科技成分股 | 1698.HK | TME - SW | 15m | grid | 网格 | 0.71% | 0.49% | ok | 间距 3.00% / 层数 7 / 止盈 1.50% | [打开报告](1698_hk/minute/1698_hk_15m_grid_report.md) |
| 恒生科技成分股 | 1810.HK | XIAOMI - W | 15m | compare | 多策略对比 | 0.00% | 0.00% | ok | 推荐 网格；对比 网格 / 分钟急跌反抽 / 分钟反抽+冲高回落过滤 | [打开报告](1810_hk/minute/1810_hk_15m_strategy_compare_report.md) |
| 恒生科技成分股 | 1810.HK | XIAOMI - W | 15m | grid | 网格 | 0.00% | 0.00% | ok | 间距 4.00% / 层数 7 / 止盈 1.00% | [打开报告](1810_hk/minute/1810_hk_15m_grid_report.md) |
| 恒生科技成分股 | 1810.HK | XIAOMI - W | 1d | compare | 多策略对比 | 9.66% | 4.35% | ok | 推荐 日线超跌反弹；对比 网格 / 日线超跌反弹 | [打开报告](1810_hk/daily/1810_hk_daily_strategy_compare_report.md) |
| 恒生科技成分股 | 1810.HK | XIAOMI - W | 1d | grid | 网格 | -1.71% | 3.42% | ok | 间距 7.00% / 层数 7 / 止盈 3.00% | [打开报告](1810_hk/daily/1810_hk_grid_report.md) |
| 恒生科技成分股 | 2015.HK | LI AUTO - W | 15m | grid | 网格 | -1.41% | 2.11% | ok | 间距 4.00% / 层数 4 / 止盈 3.00% | [打开报告](2015_hk/minute/2015_hk_15m_grid_report.md) |
| 恒生科技成分股 | 2382.HK | SUNNY OPTICAL | 15m | grid | 网格 | 0.28% | 0.15% | ok | 间距 2.00% / 层数 6 / 止盈 2.00% | [打开报告](2382_hk/minute/2382_hk_15m_grid_report.md) |
| 恒生科技成分股 | 3690.HK | MEITUAN - W | 15m | grid | 网格 | 0.00% | 0.00% | ok | 间距 4.00% / 层数 6 / 止盈 1.00% | [打开报告](3690_hk/minute/3690_hk_15m_grid_report.md) |
| 恒生科技成分股 | 3888.HK | KINGSOFT | 15m | grid | 网格 | -0.50% | 0.63% | ok | 间距 4.00% / 层数 6 / 止盈 1.50% | [打开报告](3888_hk/minute/3888_hk_15m_grid_report.md) |
| 恒生科技成分股 | 6618.HK | JD HEALTH | 15m | grid | 网格 | -2.00% | 2.90% | ok | 间距 4.00% / 层数 4 / 止盈 1.00% | [打开报告](6618_hk/minute/6618_hk_15m_grid_report.md) |
| 恒生科技成分股 | 6690.HK | HAIER SMARTHOME | 15m | grid | 网格 | -1.00% | 1.38% | ok | 间距 4.00% / 层数 7 / 止盈 3.00% | [打开报告](6690_hk/minute/6690_hk_15m_grid_report.md) |
| 恒生科技成分股 | 9618.HK | JD - SW | 15m | grid | 网格 | 0.51% | 0.10% | ok | 间距 1.50% / 层数 7 / 止盈 3.00% | [打开报告](9618_hk/minute/9618_hk_15m_grid_report.md) |
| 恒生科技成分股 | 9626.HK | BILIBILI - W | 15m | grid | 网格 | -4.04% | 4.69% | ok | 间距 4.00% / 层数 7 / 止盈 3.00% | [打开报告](9626_hk/minute/9626_hk_15m_grid_report.md) |
| 恒生科技成分股 | 9660.HK | HORIZONROBOT - W | 15m | grid | 网格 | -4.47% | 5.46% | ok | 间距 1.50% / 层数 5 / 止盈 2.00% | [打开报告](9660_hk/minute/9660_hk_15m_grid_report.md) |
| 恒生科技成分股 | 9863.HK | LEAPMOTOR | 15m | grid | 网格 | 0.32% | 1.35% | ok | 间距 4.00% / 层数 7 / 止盈 1.00% | [打开报告](9863_hk/minute/9863_hk_15m_grid_report.md) |
| 恒生科技成分股 | 9866.HK | NIO - SW | 15m | grid | 网格 | -2.18% | 5.17% | ok | 间距 2.00% / 层数 7 / 止盈 3.00% | [打开报告](9866_hk/minute/9866_hk_15m_grid_report.md) |
| 恒生科技成分股 | 9868.HK | XPENG - W | 15m | grid | 网格 | 0.69% | 0.20% | ok | 间距 4.00% / 层数 7 / 止盈 1.00% | [打开报告](9868_hk/minute/9868_hk_15m_grid_report.md) |
| 恒生科技成分股 | 9888.HK | BIDU - SW | 15m | grid | 网格 | 0.00% | 0.00% | ok | 间距 4.00% / 层数 7 / 止盈 1.00% | [打开报告](9888_hk/minute/9888_hk_15m_grid_report.md) |
| 恒生科技成分股 | 9961.HK | TRIP.COM - S | 15m | grid | 网格 | -3.64% | 5.11% | ok | 间距 1.50% / 层数 4 / 止盈 2.00% | [打开报告](9961_hk/minute/9961_hk_15m_grid_report.md) |
| 恒生科技成分股 | 9988.HK | BABA - W | 15m | grid | 网格 | 0.00% | 0.00% | ok | 间距 4.00% / 层数 7 / 止盈 3.00% | [打开报告](9988_hk/minute/9988_hk_15m_grid_report.md) |
| 恒生科技成分股 | 9999.HK | NTES - S | 15m | grid | 网格 | 0.48% | 0.87% | ok | 间距 1.00% / 层数 5 / 止盈 1.50% | [打开报告](9999_hk/minute/9999_hk_15m_grid_report.md) |
