# 正式报告总览

## 汇总说明

- 正式报告总数：`669`，成功 `597`，失败 `72`。
- 这份文件是唯一正式汇总报告；单个合约、批量合约、单策略报告和多策略对比报告都收录在同一张表里。
- 主键口径：`symbol + interval + report_view`；同一视图重复生成时会覆盖旧记录。
- 样本外净收益率高于 `5.00%` 的记录会在总表中加粗，便于先看高收益候选。

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
| 恒生科技成分股 | **1810.HK** | **XIAOMI - W** | 1d | compare | 多策略对比 | **9.66%** | 4.35% | ok | **推荐 日线超跌反弹；对比 网格 / 日线超跌反弹** | [打开报告](1810_hk/daily/1810_hk_daily_strategy_compare_report.md) |
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
| 指数ETF | 159605.SZ | 中概互联网ETF | 1m | minute_index_grid_retrace | 指数回落反弹网格 | -1.21% | 1.64% | ok | rise_trigger=2.00% sell_pullback=0.50% decline_trigger=2.00% buy_rebound=0.50% base=50.00% grid_trade=20.00% score=-3.63 | [打开报告](159605_sz/minute/159605_sz_1m_index_grid_report.md) |
| 指数ETF | 159866.SZ | 日经ETF | 1m | minute_index_grid_retrace | 指数回落反弹网格 | 1.07% | 0.58% | ok | rise_trigger=3.00% sell_pullback=0.80% decline_trigger=3.00% buy_rebound=0.80% base=50.00% grid_trade=20.00% score=-3.66 | [打开报告](159866_sz/minute/159866_sz_1m_index_grid_report.md) |
| 指数ETF | 159941.SZ | 纳指ETF | 1m | minute_index_grid_retrace | 指数回落反弹网格 | 1.13% | 0.41% | ok | rise_trigger=2.00% sell_pullback=0.50% decline_trigger=2.00% buy_rebound=0.50% base=50.00% grid_trade=20.00% score=-1.67 | [打开报告](159941_sz/minute/159941_sz_1m_index_grid_report.md) |
| 港股通沪ETF | 2800.HK | 盈富基金 | 1d | grid | 网格 | 2.04% | 0.67% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](2800_hk/daily/2800_hk_grid_report.md) |
| 港股通沪ETF | 2801.HK | 安硕中国 | 1d | grid | 网格 | 1.97% | 3.59% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](2801_hk/daily/2801_hk_grid_report.md) |
| 港股通沪ETF | 2825.HK | 标智香港１００ | 1d | grid | 网格 | 3.21% | 1.56% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](2825_hk/daily/2825_hk_grid_report.md) |
| 港股通沪ETF | 2828.HK | 恒生中国企业 | 1d | grid | 网格 | 1.55% | 2.14% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.37 | [打开报告](2828_hk/daily/2828_hk_grid_report.md) |
| 港股通沪ETF | 2837.HK | ＧＸ恒生科技 | 1d | grid | 网格 | -5.00% | 5.47% | ok | grid_spacing=6.00% grid_count=4 take_profit=5.00% score=0.00 | [打开报告](2837_hk/daily/2837_hk_grid_report.md) |
| 港股通沪ETF | 3032.HK | 恒生科技ＥＴＦ | 1d | grid | 网格 | -5.98% | 6.32% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=2.11 | [打开报告](3032_hk/daily/3032_hk_grid_report.md) |
| 港股通沪ETF | 3033.HK | 南方恒生科技 | 1d | grid | 网格 | -1.79% | 5.34% | ok | grid_spacing=6.00% grid_count=4 take_profit=5.00% score=2.12 | [打开报告](3033_hk/daily/3033_hk_grid_report.md) |
| 港股通沪ETF | 3037.HK | 南方恒指ＥＴＦ | 1d | grid | 网格 | 2.08% | 0.67% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](3037_hk/daily/3037_hk_grid_report.md) |
| 港股通沪ETF | 3039.HK | 易方达恒指ＥＳＧ | 1d | grid | 网格 | 2.61% | 2.46% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](3039_hk/daily/3039_hk_grid_report.md) |
| 港股通沪ETF | 3040.HK | ＧＸ中国 | 1d | grid | 网格 | -0.78% | 3.60% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=0.00 | [打开报告](3040_hk/daily/3040_hk_grid_report.md) |
| 港股通沪ETF | 3067.HK | 安硕恒生科技 | 1d | grid | 网格 | -1.65% | 5.10% | ok | grid_spacing=6.00% grid_count=4 take_profit=5.00% score=1.35 | [打开报告](3067_hk/daily/3067_hk_grid_report.md) |
| 港股通沪ETF | 3069.HK | 华夏恒生生科 | 1d | grid | 网格 | 2.82% | 0.80% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=-3.46 | [打开报告](3069_hk/daily/3069_hk_grid_report.md) |
| 港股通沪ETF | 3070.HK | 平安香港高息 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](3070_hk/daily/3070_hk_grid_report.md) |
| 港股通沪ETF | 3088.HK | 华夏恒生科技 | 1d | grid | 网格 | -1.63% | 5.30% | ok | grid_spacing=6.00% grid_count=4 take_profit=5.00% score=0.00 | [打开报告](3088_hk/daily/3088_hk_grid_report.md) |
| 港股通沪ETF | 3110.HK | ＧＸ恒生股息 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](3110_hk/daily/3110_hk_grid_report.md) |
| 港股通沪ETF | 3115.HK | 安硕恒生指数 | 1d | grid | 网格 | 2.41% | 0.78% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](3115_hk/daily/3115_hk_grid_report.md) |
| 港股通沪ETF | 3167.HK | 工银南方中国 | 1d | grid | 网格 | 2.20% | 3.57% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=1.36 | [打开报告](3167_hk/daily/3167_hk_grid_report.md) |
| 港股通沪ETF | 3174.HK | 南方恒生生科 | 1d | grid | 网格 | -0.14% | 0.14% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=-3.82 | [打开报告](3174_hk/daily/3174_hk_grid_report.md) |
| 港股通沪ETF | 3403.HK | 华夏恒ＥＳＧ | 1d | grid | 网格 | 3.21% | 1.73% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=1.09 | [打开报告](3403_hk/daily/3403_hk_grid_report.md) |
| 港股通沪ETF | 3406.HK | 平安科技精选 | 1d | grid | 网格 | -5.86% | 5.99% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=2.10 | [打开报告](3406_hk/daily/3406_hk_grid_report.md) |
| 港股通沪ETF | 3423.HK | 招商恒生科技 | 1d | grid | 网格 | -0.95% | 5.23% | ok | grid_spacing=6.00% grid_count=4 take_profit=7.00% score=0.00 | [打开报告](3423_hk/daily/3423_hk_grid_report.md) |
| 港股通沪ETF | 3431.HK | 南方港韩科技 | 1d | grid | 网格 | 3.60% | 0.02% | ok | grid_spacing=5.00% grid_count=4 take_profit=3.00% score=3.94 | [打开报告](3431_hk/daily/3431_hk_grid_report.md) |
| 港股通沪ETF | 3432.HK | 南方港股通 | 1d | grid | 网格 | 1.30% | 0.46% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=-4.31 | [打开报告](3432_hk/daily/3432_hk_grid_report.md) |
| 港股通沪ETF | 3437.HK | 博时央企红利 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](3437_hk/daily/3437_hk_grid_report.md) |
| 港股通沪ETF | 3441.HK | 南方东西精选 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](3441_hk/daily/3441_hk_grid_report.md) |
| 港股通沪ETF | 3442.HK | 南方港美科技 | 1d | grid | 网格 | -7.41% | 7.56% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=0.00 | [打开报告](3442_hk/daily/3442_hk_grid_report.md) |
| 港股通沪ETF | 3443.HK | 南方香港股票 | 1d | grid | 网格 | 3.31% | 1.19% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](3443_hk/daily/3443_hk_grid_report.md) |
| 港股通沪ETF | 3469.HK | 南方港股通红利 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](3469_hk/daily/3469_hk_grid_report.md) |
| 港股通沪ETF | 3477.HK | 平安东西精选 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](3477_hk/daily/3477_hk_grid_report.md) |
| 港股通沪ETF | 3483.HK | 易方达高股息 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](3483_hk/daily/3483_hk_grid_report.md) |
| 港股通沪ETF | 3489.HK | 易方达ＡＩ | 1d | grid | 网格 | -5.36% | 6.24% | ok | grid_spacing=5.00% grid_count=4 take_profit=3.00% score=0.35 | [打开报告](3489_hk/daily/3489_hk_grid_report.md) |
| 港股通沪股票 | 0001.HK | 长和 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0001_hk/daily/0001_hk_grid_report.md) |
| 港股通沪股票 | 0002.HK | 中电控股 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=500, price=66.78 | [打开报告](0002_hk/daily/0002_hk_1d_grid_report.md) |
| 港股通沪股票 | 0003.HK | 香港中华煤气 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0003_hk/daily/0003_hk_grid_report.md) |
| 港股通沪股票 | 0004.HK | 九龙仓集团 | 1d | grid | 网格 | 1.80% | 0.34% | ok | grid_spacing=5.00% grid_count=4 take_profit=7.00% score=3.61 | [打开报告](0004_hk/daily/0004_hk_grid_report.md) |
| 港股通沪股票 | 0005.HK | 汇丰控股 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=400, price=104.68 | [打开报告](0005_hk/daily/0005_hk_1d_grid_report.md) |
| 港股通沪股票 | 0006.HK | 电能实业 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0006_hk/daily/0006_hk_grid_report.md) |
| 港股通沪股票 | 0008.HK | 电讯盈科 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=5.00% grid_count=7 take_profit=3.00% score=0.00 | [打开报告](0008_hk/daily/0008_hk_grid_report.md) |
| 港股通沪股票 | 0010.HK | 恒隆集团 | 1d | grid | 网格 | 0.83% | 0.02% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0010_hk/daily/0010_hk_grid_report.md) |
| 港股通沪股票 | 0012.HK | 恒基地产 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=1000, price=29.72 | [打开报告](0012_hk/daily/0012_hk_1d_grid_report.md) |
| 港股通沪股票 | 0013.HK | 和黄医药 | 1d | grid | 网格 | -0.26% | 0.26% | ok | grid_spacing=7.00% grid_count=6 take_profit=3.00% score=-1.65 | [打开报告](0013_hk/daily/0013_hk_grid_report.md) |
| 港股通沪股票 | 0014.HK | 希慎兴业 | 1d | grid | 网格 | 0.66% | 0.01% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0014_hk/daily/0014_hk_grid_report.md) |
| 港股通沪股票 | 0016.HK | 新鸿基地产 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=500, price=90.33 | [打开报告](0016_hk/daily/0016_hk_1d_grid_report.md) |
| 港股通沪股票 | 0017.HK | 新世界发展 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0017_hk/daily/0017_hk_grid_report.md) |
| 港股通沪股票 | 0019.HK | 太古股份公司Ａ | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=500, price=66.79 | [打开报告](0019_hk/daily/0019_hk_1d_grid_report.md) |
| 港股通沪股票 | 0020.HK | 商汤－Ｗ | 1d | grid | 网格 | -0.98% | 2.47% | ok | grid_spacing=7.00% grid_count=6 take_profit=5.00% score=3.88 | [打开报告](0020_hk/daily/0020_hk_grid_report.md) |
| 港股通沪股票 | 0023.HK | 东亚银行 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=4 take_profit=5.00% score=3.06 | [打开报告](0023_hk/daily/0023_hk_grid_report.md) |
| 港股通沪股票 | 0027.HK | 银河娱乐 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=1000, price=39.53 | [打开报告](0027_hk/daily/0027_hk_1d_grid_report.md) |
| 港股通沪股票 | 0038.HK | 第一拖拉机股份 | 1d | grid | 网格 | -0.03% | 0.03% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=4.73 | [打开报告](0038_hk/daily/0038_hk_grid_report.md) |
| 港股通沪股票 | 0041.HK | 鹰君 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=0.00 | [打开报告](0041_hk/daily/0041_hk_grid_report.md) |
| 港股通沪股票 | 0066.HK | 港铁公司 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0066_hk/daily/0066_hk_grid_report.md) |
| 港股通沪股票 | 0081.HK | 中国海外宏洋集团 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=7 take_profit=7.00% score=-1.06 | [打开报告](0081_hk/daily/0081_hk_grid_report.md) |
| 港股通沪股票 | 0083.HK | 信和置业 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0083_hk/daily/0083_hk_grid_report.md) |
| 港股通沪股票 | 0087.HK | 太古股份公司Ｂ | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0087_hk/daily/0087_hk_grid_report.md) |
| 港股通沪股票 | 0101.HK | 恒隆地产 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0101_hk/daily/0101_hk_grid_report.md) |
| 港股通沪股票 | 0107.HK | 四川成渝高速公路 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=1.67 | [打开报告](0107_hk/daily/0107_hk_grid_report.md) |
| 港股通沪股票 | **0119.HK** | **保利置业集团** | 1d | grid | 网格 | **9.66%** | 4.52% | ok | **grid_spacing=3.00% grid_count=4 take_profit=7.00% score=2.71** | [打开报告](0119_hk/daily/0119_hk_grid_report.md) |
| 港股通沪股票 | 0123.HK | 越秀地产 | 1d | grid | 网格 | 1.55% | 0.49% | ok | grid_spacing=7.00% grid_count=7 take_profit=5.00% score=-1.75 | [打开报告](0123_hk/daily/0123_hk_grid_report.md) |
| 港股通沪股票 | 0135.HK | 昆仑能源 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0135_hk/daily/0135_hk_grid_report.md) |
| 港股通沪股票 | 0136.HK | 中国儒意 | 1d | grid | 网格 | -4.62% | 5.46% | ok | grid_spacing=7.00% grid_count=6 take_profit=3.00% score=-3.75 | [打开报告](0136_hk/daily/0136_hk_grid_report.md) |
| 港股通沪股票 | 0142.HK | 第一太平 | 1d | grid | 网格 | -1.10% | 1.84% | ok | grid_spacing=4.00% grid_count=6 take_profit=5.00% score=-0.68 | [打开报告](0142_hk/daily/0142_hk_grid_report.md) |
| 港股通沪股票 | 0144.HK | 招商局港口 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=2000, price=14.96 | [打开报告](0144_hk/daily/0144_hk_1d_grid_report.md) |
| 港股通沪股票 | 0148.HK | 建滔集团 | 1d | grid | 网格 | 1.80% | 0.35% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=6.43 | [打开报告](0148_hk/daily/0148_hk_grid_report.md) |
| 港股通沪股票 | 0151.HK | 中国旺旺 | 1d | grid | 网格 | -1.07% | 2.63% | ok | grid_spacing=5.00% grid_count=4 take_profit=3.00% score=-1.13 | [打开报告](0151_hk/daily/0151_hk_grid_report.md) |
| 港股通沪股票 | 0152.HK | 深圳国际 | 1d | grid | 网格 | -5.90% | 5.90% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=2.33 | [打开报告](0152_hk/daily/0152_hk_grid_report.md) |
| 港股通沪股票 | 0165.HK | 中国光大控股 | 1d | grid | 网格 | -5.04% | 5.04% | ok | grid_spacing=7.00% grid_count=5 take_profit=7.00% score=0.00 | [打开报告](0165_hk/daily/0165_hk_grid_report.md) |
| 港股通沪股票 | 0168.HK | 青岛啤酒股份 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=2000, price=50.95 | [打开报告](0168_hk/daily/0168_hk_1d_grid_report.md) |
| 港股通沪股票 | 0173.HK | 嘉华国际 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=5.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0173_hk/daily/0173_hk_grid_report.md) |
| 港股通沪股票 | 0175.HK | 吉利汽车 | 1d | grid | 网格 | 0.77% | 1.21% | ok | grid_spacing=7.00% grid_count=6 take_profit=3.00% score=0.24 | [打开报告](0175_hk/daily/0175_hk_grid_report.md) |
| 港股通沪股票 | 0177.HK | 江苏宁沪高速公路 | 1d | grid | 网格 | 0.61% | 0.10% | ok | grid_spacing=5.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0177_hk/daily/0177_hk_grid_report.md) |
| 港股通沪股票 | 0179.HK | 德昌电机控股 | 1d | grid | 网格 | 2.93% | 5.76% | ok | grid_spacing=5.00% grid_count=4 take_profit=3.00% score=3.74 | [打开报告](0179_hk/daily/0179_hk_grid_report.md) |
| 港股通沪股票 | 0187.HK | 京城机电股份 | 1d | grid | 网格 | 2.30% | 0.02% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=-11.36 | [打开报告](0187_hk/daily/0187_hk_grid_report.md) |
| 港股通沪股票 | 0189.HK | 东岳集团 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=6 take_profit=7.00% score=1.49 | [打开报告](0189_hk/daily/0189_hk_grid_report.md) |
| 港股通沪股票 | **0200.HK** | **新濠国际发展** | 1d | grid | 网格 | **6.79%** | 3.03% | ok | **grid_spacing=5.00% grid_count=4 take_profit=3.00% score=-10.83** | [打开报告](0200_hk/daily/0200_hk_grid_report.md) |
| 港股通沪股票 | 0220.HK | 统一企业中国 | 1d | grid | 网格 | 0.79% | 0.52% | ok | grid_spacing=7.00% grid_count=7 take_profit=7.00% score=-0.74 | [打开报告](0220_hk/daily/0220_hk_grid_report.md) |
| 港股通沪股票 | 0241.HK | 阿里健康 | 1d | grid | 网格 | -2.92% | 4.70% | ok | grid_spacing=3.00% grid_count=6 take_profit=3.00% score=-2.70 | [打开报告](0241_hk/daily/0241_hk_grid_report.md) |
| 港股通沪股票 | 0257.HK | 光大环境 | 1d | grid | 网格 | 1.16% | 0.02% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0257_hk/daily/0257_hk_grid_report.md) |
| 港股通沪股票 | 0267.HK | 中信股份 | 1d | grid | 网格 | 4.49% | 2.47% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0267_hk/daily/0267_hk_grid_report.md) |
| 港股通沪股票 | 0268.HK | 金蝶国际 | 1d | grid | 网格 | -5.37% | 5.37% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=0.63 | [打开报告](0268_hk/daily/0268_hk_grid_report.md) |
| 港股通沪股票 | 0270.HK | 粤海投资 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=7 take_profit=3.00% score=0.00 | [打开报告](0270_hk/daily/0270_hk_grid_report.md) |
| 港股通沪股票 | 0285.HK | 比亚迪电子 | 1d | grid | 网格 | -2.85% | 4.45% | ok | grid_spacing=7.00% grid_count=5 take_profit=5.00% score=-2.91 | [打开报告](0285_hk/daily/0285_hk_grid_report.md) |
| 港股通沪股票 | 0288.HK | 万洲国际 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=2.37 | [打开报告](0288_hk/daily/0288_hk_grid_report.md) |
| 港股通沪股票 | 0290.HK | 国富量子 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=4 take_profit=7.00% score=-8.00 | [打开报告](0290_hk/daily/0290_hk_grid_report.md) |
| 港股通沪股票 | **0291.HK** | **华润啤酒** | 1d | grid | 网格 | **5.66%** | 1.99% | ok | **grid_spacing=3.00% grid_count=4 take_profit=3.00% score=4.90** | [打开报告](0291_hk/daily/0291_hk_grid_report.md) |
| 港股通沪股票 | **0293.HK** | **国泰航空** | 1d | grid | 网格 | **6.59%** | 0.65% | ok | **grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00** | [打开报告](0293_hk/daily/0293_hk_grid_report.md) |
| 港股通沪股票 | 0297.HK | 中化化肥 | 1d | grid | 网格 | 1.03% | 0.22% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0297_hk/daily/0297_hk_grid_report.md) |
| 港股通沪股票 | **0300.HK** | **美的集团** | 1d | grid | 网格 | **5.42%** | 3.93% | ok | **grid_spacing=3.00% grid_count=4 take_profit=3.00% score=2.46** | [打开报告](0300_hk/daily/0300_hk_grid_report.md) |
| 港股通沪股票 | 0303.HK | VTECH HOLDINGS | 1d | grid | 网格 | 1.96% | 0.71% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=4.79 | [打开报告](0303_hk/daily/0303_hk_grid_report.md) |
| 港股通沪股票 | 0308.HK | 香港中旅 | 1d | grid | 网格 | 1.14% | 4.92% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0308_hk/daily/0308_hk_grid_report.md) |
| 港股通沪股票 | 0316.HK | 东方海外国际 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=500, price=132.15 | [打开报告](0316_hk/daily/0316_hk_1d_grid_report.md) |
| 港股通沪股票 | 0317.HK | 中船防务 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=2000, price=16.02 | [打开报告](0317_hk/daily/0317_hk_1d_grid_report.md) |
| 港股通沪股票 | 0322.HK | 康师傅控股 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=5 take_profit=5.00% score=2.61 | [打开报告](0322_hk/daily/0322_hk_grid_report.md) |
| 港股通沪股票 | 0323.HK | 马鞍山钢铁股份 | 1d | grid | 网格 | 2.29% | 5.29% | ok | grid_spacing=4.00% grid_count=4 take_profit=5.00% score=0.00 | [打开报告](0323_hk/daily/0323_hk_grid_report.md) |
| 港股通沪股票 | 0325.HK | 布鲁可 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=300, price=101.60 | [打开报告](0325_hk/daily/0325_hk_1d_grid_report.md) |
| 港股通沪股票 | 0336.HK | 华宝国际 | 1d | grid | 网格 | -3.01% | 3.01% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=-17.61 | [打开报告](0336_hk/daily/0336_hk_grid_report.md) |
| 港股通沪股票 | 0338.HK | 上海石油化工股份 | 1d | grid | 网格 | 0.99% | 4.57% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=1.00 | [打开报告](0338_hk/daily/0338_hk_grid_report.md) |
| 港股通沪股票 | 0345.HK | VITASOY INT'L | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-6.02 | [打开报告](0345_hk/daily/0345_hk_grid_report.md) |
| 港股通沪股票 | 0347.HK | 鞍钢股份 | 1d | grid | 网格 | -6.15% | 7.13% | ok | grid_spacing=5.00% grid_count=4 take_profit=3.00% score=-2.36 | [打开报告](0347_hk/daily/0347_hk_grid_report.md) |
| 港股通沪股票 | 0354.HK | 中国软件国际 | 1d | grid | 网格 | -5.14% | 5.19% | ok | grid_spacing=5.00% grid_count=4 take_profit=3.00% score=-6.38 | [打开报告](0354_hk/daily/0354_hk_grid_report.md) |
| 港股通沪股票 | 0358.HK | 江西铜业股份 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=1000, price=35.21 | [打开报告](0358_hk/daily/0358_hk_1d_grid_report.md) |
| 港股通沪股票 | 0363.HK | 上海实业控股 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0363_hk/daily/0363_hk_grid_report.md) |
| 港股通沪股票 | 0371.HK | 北控水务集团 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=4 take_profit=7.00% score=2.12 | [打开报告](0371_hk/daily/0371_hk_grid_report.md) |
| 港股通沪股票 | 0384.HK | 中国燃气 | 1d | grid | 网格 | 0.68% | 0.36% | ok | grid_spacing=6.00% grid_count=7 take_profit=3.00% score=0.00 | [打开报告](0384_hk/daily/0384_hk_grid_report.md) |
| 港股通沪股票 | 0386.HK | 中国石油化工股份 | 1d | grid | 网格 | 0.01% | 1.15% | ok | grid_spacing=4.00% grid_count=4 take_profit=7.00% score=2.11 | [打开报告](0386_hk/daily/0386_hk_grid_report.md) |
| 港股通沪股票 | 0388.HK | 香港交易所 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=100, price=436.66 | [打开报告](0388_hk/daily/0388_hk_1d_grid_report.md) |
| 港股通沪股票 | 0390.HK | 中国中铁 | 1d | grid | 网格 | -1.84% | 1.84% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0390_hk/daily/0390_hk_grid_report.md) |
| 港股通沪股票 | 0392.HK | 北京控股 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=6 take_profit=3.00% score=0.00 | [打开报告](0392_hk/daily/0392_hk_grid_report.md) |
| 港股通沪股票 | **0425.HK** | **敏实集团** | 1d | grid | 网格 | **6.25%** | 1.74% | ok | **grid_spacing=3.00% grid_count=4 take_profit=3.00% score=1.19** | [打开报告](0425_hk/daily/0425_hk_grid_report.md) |
| 港股通沪股票 | 0440.HK | 大新金融 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0440_hk/daily/0440_hk_grid_report.md) |
| 港股通沪股票 | 0460.HK | 四环医药 | 1d | grid | 网格 | -1.62% | 1.62% | ok | grid_spacing=6.00% grid_count=7 take_profit=3.00% score=-2.10 | [打开报告](0460_hk/daily/0460_hk_grid_report.md) |
| 港股通沪股票 | 0467.HK | 联合能源集团 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=7 take_profit=5.00% score=-2.80 | [打开报告](0467_hk/daily/0467_hk_grid_report.md) |
| 港股通沪股票 | 0470.HK | 先导智能 | 1d | grid | 网格 | - | - | failed | 样本内区间为空，无法构建样本窗口。 | [打开报告](0470_hk/daily/0470_hk_1d_grid_report.md) |
| 港股通沪股票 | 0501.HK | 豪威集团 | 1d | grid | 网格 | - | - | failed | Yahoo 行情下载失败，流程已停止: Yahoo 返回空数据，无法继续处理。 | [打开报告](0501_hk/daily/0501_hk_1d_grid_report.md) |
| 港股通沪股票 | 0506.HK | 中国食品 | 1d | grid | 网格 | -5.54% | 6.59% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=0.00 | [打开报告](0506_hk/daily/0506_hk_grid_report.md) |
| 港股通沪股票 | 0512.HK | 远大医药 | 1d | grid | 网格 | 0.91% | 5.54% | ok | grid_spacing=4.00% grid_count=4 take_profit=5.00% score=-3.18 | [打开报告](0512_hk/daily/0512_hk_grid_report.md) |
| 港股通沪股票 | 0522.HK | ASMPT | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0522_hk/daily/0522_hk_grid_report.md) |
| 港股通沪股票 | 0525.HK | 广深铁路股份 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=0.00 | [打开报告](0525_hk/daily/0525_hk_grid_report.md) |
| 港股通沪股票 | 0546.HK | 阜丰集团 | 1d | grid | 网格 | -2.69% | 2.86% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=0.30 | [打开报告](0546_hk/daily/0546_hk_grid_report.md) |
| 港股通沪股票 | 0548.HK | 深圳高速公路股份 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0548_hk/daily/0548_hk_grid_report.md) |
| 港股通沪股票 | 0551.HK | 裕元集团 | 1d | grid | 网格 | -1.17% | 2.67% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=0.00 | [打开报告](0551_hk/daily/0551_hk_grid_report.md) |
| 港股通沪股票 | 0552.HK | 中国通信服务 | 1d | grid | 网格 | 3.79% | 3.87% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=2.41 | [打开报告](0552_hk/daily/0552_hk_grid_report.md) |
| 港股通沪股票 | 0553.HK | 南京熊猫电子股份 | 1d | grid | 网格 | 1.76% | 1.58% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=-10.78 | [打开报告](0553_hk/daily/0553_hk_grid_report.md) |
| 港股通沪股票 | 0564.HK | 中创智领 | 1d | grid | 网格 | 1.42% | 3.37% | ok | grid_spacing=5.00% grid_count=4 take_profit=5.00% score=0.00 | [打开报告](0564_hk/daily/0564_hk_grid_report.md) |
| 港股通沪股票 | 0568.HK | 山东墨龙 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-4.29 | [打开报告](0568_hk/daily/0568_hk_grid_report.md) |
| 港股通沪股票 | 0570.HK | 中国中药 | 1d | grid | 网格 | -3.04% | 3.25% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=0.00 | [打开报告](0570_hk/daily/0570_hk_grid_report.md) |
| 港股通沪股票 | 0576.HK | 浙江沪杭甬 | 1d | grid | 网格 | 0.52% | 0.17% | ok | grid_spacing=6.00% grid_count=7 take_profit=3.00% score=0.00 | [打开报告](0576_hk/daily/0576_hk_grid_report.md) |
| 港股通沪股票 | 0586.HK | 海螺创业 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=4 take_profit=7.00% score=5.74 | [打开报告](0586_hk/daily/0586_hk_grid_report.md) |
| 港股通沪股票 | 0588.HK | 北京北辰实业股份 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=7 take_profit=3.00% score=-0.86 | [打开报告](0588_hk/daily/0588_hk_grid_report.md) |
| 港股通沪股票 | 0590.HK | 六福集团 | 1d | grid | 网格 | -1.06% | 2.00% | ok | grid_spacing=6.00% grid_count=4 take_profit=7.00% score=2.33 | [打开报告](0590_hk/daily/0590_hk_grid_report.md) |
| 港股通沪股票 | 0598.HK | 中国外运 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0598_hk/daily/0598_hk_grid_report.md) |
| 港股通沪股票 | 0604.HK | 深圳控股 | 1d | grid | 网格 | 0.49% | 0.85% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=0.00 | [打开报告](0604_hk/daily/0604_hk_grid_report.md) |
| 港股通沪股票 | 0631.HK | 三一国际 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=7 take_profit=3.00% score=0.00 | [打开报告](0631_hk/daily/0631_hk_grid_report.md) |
| 港股通沪股票 | 0636.HK | KLN | 1d | grid | 网格 | -1.91% | 2.89% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=3.52 | [打开报告](0636_hk/daily/0636_hk_grid_report.md) |
| 港股通沪股票 | 0638.HK | 广和通 | 1d | grid | 网格 | - | - | failed | Yahoo 行情下载失败，流程已停止: Yahoo 返回空数据，无法继续处理。 | [打开报告](0638_hk/daily/0638_hk_1d_grid_report.md) |
| 港股通沪股票 | 0639.HK | 首钢资源 | 1d | grid | 网格 | -3.35% | 3.77% | ok | grid_spacing=3.00% grid_count=7 take_profit=3.00% score=0.00 | [打开报告](0639_hk/daily/0639_hk_grid_report.md) |
| 港股通沪股票 | 0656.HK | 复星国际 | 1d | grid | 网格 | 3.16% | 2.05% | ok | grid_spacing=7.00% grid_count=7 take_profit=5.00% score=-1.25 | [打开报告](0656_hk/daily/0656_hk_grid_report.md) |
| 港股通沪股票 | 0659.HK | 周大福创建 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0659_hk/daily/0659_hk_grid_report.md) |
| 港股通沪股票 | **0666.HK** | **瑞浦兰钧** | 1d | grid | 网格 | **5.94%** | 2.42% | ok | **grid_spacing=3.00% grid_count=6 take_profit=7.00% score=0.00** | [打开报告](0666_hk/daily/0666_hk_grid_report.md) |
| 港股通沪股票 | 0667.HK | 中国东方教育 | 1d | grid | 网格 | -0.68% | 4.04% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-9.01 | [打开报告](0667_hk/daily/0667_hk_grid_report.md) |
| 港股通沪股票 | 0669.HK | 创科实业 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=500, price=95.33 | [打开报告](0669_hk/daily/0669_hk_1d_grid_report.md) |
| 港股通沪股票 | 0670.HK | 中国东方航空股份 | 1d | grid | 网格 | -2.93% | 4.97% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=0.00 | [打开报告](0670_hk/daily/0670_hk_grid_report.md) |
| 港股通沪股票 | 0683.HK | 嘉里建设 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0683_hk/daily/0683_hk_grid_report.md) |
| 港股通沪股票 | 0688.HK | 中国海外发展 | 1d | grid | 网格 | 0.75% | 0.32% | ok | grid_spacing=6.00% grid_count=6 take_profit=3.00% score=-0.30 | [打开报告](0688_hk/daily/0688_hk_grid_report.md) |
| 港股通沪股票 | 0696.HK | 中国民航信息网络 | 1d | grid | 网格 | 1.93% | 2.58% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=3.66 | [打开报告](0696_hk/daily/0696_hk_grid_report.md) |
| 港股通沪股票 | 0697.HK | 首程控股 | 1d | grid | 网格 | -0.17% | 7.02% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=12.18 | [打开报告](0697_hk/daily/0697_hk_grid_report.md) |
| 港股通沪股票 | 0699.HK | 均胜电子 | 1d | grid | 网格 | - | - | failed | Yahoo 行情下载失败，流程已停止: Yahoo 返回空数据，无法继续处理。 | [打开报告](0699_hk/daily/0699_hk_1d_grid_report.md) |
| 港股通沪股票 | 0700.HK | 腾讯控股 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=100, price=593.58 | [打开报告](0700_hk/daily/0700_hk_1d_grid_report.md) |
| 港股通沪股票 | 0719.HK | 山东新华制药股份 | 1d | grid | 网格 | -0.11% | 1.45% | ok | grid_spacing=3.00% grid_count=7 take_profit=5.00% score=-1.54 | [打开报告](0719_hk/daily/0719_hk_grid_report.md) |
| 港股通沪股票 | 0728.HK | 中国电信 | 1d | grid | 网格 | 2.44% | 1.07% | ok | grid_spacing=6.00% grid_count=6 take_profit=3.00% score=0.28 | [打开报告](0728_hk/daily/0728_hk_grid_report.md) |
| 港股通沪股票 | 0751.HK | 创维集团 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=6 take_profit=3.00% score=0.00 | [打开报告](0751_hk/daily/0751_hk_grid_report.md) |
| 港股通沪股票 | 0753.HK | 中国国航 | 1d | grid | 网格 | -4.79% | 6.62% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=0.00 | [打开报告](0753_hk/daily/0753_hk_grid_report.md) |
| 港股通沪股票 | 0754.HK | 合生创展集团 | 1d | grid | 网格 | -0.75% | 1.86% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=-9.23 | [打开报告](0754_hk/daily/0754_hk_grid_report.md) |
| 港股通沪股票 | 0762.HK | 中国联通 | 1d | grid | 网格 | 1.23% | 0.55% | ok | grid_spacing=7.00% grid_count=6 take_profit=3.00% score=-1.49 | [打开报告](0762_hk/daily/0762_hk_grid_report.md) |
| 港股通沪股票 | 0763.HK | 中兴通讯 | 1d | grid | 网格 | -4.96% | 5.80% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=-8.09 | [打开报告](0763_hk/daily/0763_hk_grid_report.md) |
| 港股通沪股票 | 0772.HK | 阅文集团 | 1d | grid | 网格 | -4.51% | 5.41% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=-5.74 | [打开报告](0772_hk/daily/0772_hk_grid_report.md) |
| 港股通沪股票 | 0780.HK | 同程旅行 | 1d | grid | 网格 | -7.35% | 8.60% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=2.34 | [打开报告](0780_hk/daily/0780_hk_grid_report.md) |
| 港股通沪股票 | 0788.HK | 中国铁塔 | 1d | grid | 网格 | 0.07% | 1.95% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0788_hk/daily/0788_hk_grid_report.md) |
| 港股通沪股票 | 0811.HK | 新华文轩 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=4 take_profit=5.00% score=0.49 | [打开报告](0811_hk/daily/0811_hk_grid_report.md) |
| 港股通沪股票 | 0817.HK | 中国金茂 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=7 take_profit=7.00% score=2.06 | [打开报告](0817_hk/daily/0817_hk_grid_report.md) |
| 港股通沪股票 | 0819.HK | 天能动力 | 1d | grid | 网格 | 2.91% | 0.77% | ok | grid_spacing=7.00% grid_count=5 take_profit=3.00% score=0.00 | [打开报告](0819_hk/daily/0819_hk_grid_report.md) |
| 港股通沪股票 | 0826.HK | 天工国际 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0826_hk/daily/0826_hk_grid_report.md) |
| 港股通沪股票 | 0836.HK | 华润电力 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=2000, price=17.74 | [打开报告](0836_hk/daily/0836_hk_1d_grid_report.md) |
| 港股通沪股票 | 0839.HK | 中教控股 | 1d | grid | 网格 | -6.26% | 6.52% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=2.34 | [打开报告](0839_hk/daily/0839_hk_grid_report.md) |
| 港股通沪股票 | 0853.HK | 微创医疗 | 1d | grid | 网格 | -3.72% | 5.04% | ok | grid_spacing=7.00% grid_count=7 take_profit=5.00% score=-6.13 | [打开报告](0853_hk/daily/0853_hk_grid_report.md) |
| 港股通沪股票 | 0855.HK | 中国水务 | 1d | grid | 网格 | 0.50% | 0.58% | ok | grid_spacing=7.00% grid_count=6 take_profit=3.00% score=-0.56 | [打开报告](0855_hk/daily/0855_hk_grid_report.md) |
| 港股通沪股票 | 0856.HK | 伟仕佳杰 | 1d | grid | 网格 | 4.48% | 1.28% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=-2.13 | [打开报告](0856_hk/daily/0856_hk_grid_report.md) |
| 港股通沪股票 | 0857.HK | 中国石油股份 | 1d | grid | 网格 | 0.53% | 0.12% | ok | grid_spacing=5.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0857_hk/daily/0857_hk_grid_report.md) |
| 港股通沪股票 | 0867.HK | 康哲药业 | 1d | grid | 网格 | -3.13% | 4.64% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=9.47 | [打开报告](0867_hk/daily/0867_hk_grid_report.md) |
| 港股通沪股票 | 0868.HK | 信义玻璃 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=5.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0868_hk/daily/0868_hk_grid_report.md) |
| 港股通沪股票 | 0874.HK | 白云山 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=2000, price=18.42 | [打开报告](0874_hk/daily/0874_hk_1d_grid_report.md) |
| 港股通沪股票 | 0880.HK | 澳博控股 | 1d | grid | 网格 | -2.21% | 2.56% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-4.09 | [打开报告](0880_hk/daily/0880_hk_grid_report.md) |
| 港股通沪股票 | 0881.HK | 中升控股 | 1d | grid | 网格 | -5.77% | 5.77% | ok | grid_spacing=7.00% grid_count=6 take_profit=3.00% score=-11.65 | [打开报告](0881_hk/daily/0881_hk_grid_report.md) |
| 港股通沪股票 | 0883.HK | 中国海洋石油 | 1d | grid | 网格 | 0.78% | 0.02% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=0.93 | [打开报告](0883_hk/daily/0883_hk_grid_report.md) |
| 港股通沪股票 | 0895.HK | 东江环保 | 1d | grid | 网格 | -0.16% | 0.80% | ok | grid_spacing=7.00% grid_count=4 take_profit=7.00% score=-1.08 | [打开报告](0895_hk/daily/0895_hk_grid_report.md) |
| 港股通沪股票 | 0902.HK | 华能国际电力股份 | 1d | grid | 网格 | 0.40% | 0.08% | ok | grid_spacing=6.00% grid_count=6 take_profit=3.00% score=0.59 | [打开报告](0902_hk/daily/0902_hk_grid_report.md) |
| 港股通沪股票 | 0909.HK | 明源云 | 1d | grid | 网格 | -4.99% | 5.51% | ok | grid_spacing=4.00% grid_count=4 take_profit=7.00% score=-8.59 | [打开报告](0909_hk/daily/0909_hk_grid_report.md) |
| 港股通沪股票 | 0914.HK | 海螺水泥 | 1d | grid | 网格 | -3.34% | 4.97% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=2.12 | [打开报告](0914_hk/daily/0914_hk_grid_report.md) |
| 港股通沪股票 | 0916.HK | 龙源电力 | 1d | grid | 网格 | 1.16% | 0.02% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=0.00 | [打开报告](0916_hk/daily/0916_hk_grid_report.md) |
| 港股通沪股票 | 0917.HK | 趣致集团 | 1d | grid | 网格 | -2.58% | 5.02% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-11.10 | [打开报告](0917_hk/daily/0917_hk_grid_report.md) |
| 港股通沪股票 | 0921.HK | 海信家电 | 1d | grid | 网格 | -5.53% | 7.26% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=11.36 | [打开报告](0921_hk/daily/0921_hk_grid_report.md) |
| 港股通沪股票 | 0934.HK | 中石化冠德 | 1d | grid | 网格 | 0.99% | 1.04% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=-0.24 | [打开报告](0934_hk/daily/0934_hk_grid_report.md) |
| 港股通沪股票 | 0939.HK | 建设银行 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0939_hk/daily/0939_hk_grid_report.md) |
| 港股通沪股票 | 0941.HK | 中国移动 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=500, price=85.60 | [打开报告](0941_hk/daily/0941_hk_1d_grid_report.md) |
| 港股通沪股票 | 0956.HK | 新天绿色能源 | 1d | grid | 网格 | -0.02% | 0.02% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-0.04 | [打开报告](0956_hk/daily/0956_hk_grid_report.md) |
| 港股通沪股票 | 0960.HK | 龙湖集团 | 1d | grid | 网格 | 1.58% | 0.94% | ok | grid_spacing=7.00% grid_count=7 take_profit=5.00% score=-1.44 | [打开报告](0960_hk/daily/0960_hk_grid_report.md) |
| 港股通沪股票 | 0966.HK | 中国太平 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=6.06 | [打开报告](0966_hk/daily/0966_hk_grid_report.md) |
| 港股通沪股票 | 0968.HK | 信义光能 | 1d | grid | 网格 | -0.54% | 0.61% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-0.34 | [打开报告](0968_hk/daily/0968_hk_grid_report.md) |
| 港股通沪股票 | 0975.HK | MONGOL MINING | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=3000, price=12.38 | [打开报告](0975_hk/daily/0975_hk_1d_grid_report.md) |
| 港股通沪股票 | 0981.HK | 中芯国际 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=500, price=80.15 | [打开报告](0981_hk/daily/0981_hk_1d_grid_report.md) |
| 港股通沪股票 | 0990.HK | 至源控股 | 1d | grid | 网格 | 0.72% | 0.01% | ok | grid_spacing=5.00% grid_count=5 take_profit=3.00% score=4.98 | [打开报告](0990_hk/daily/0990_hk_grid_report.md) |
| 港股通沪股票 | 0991.HK | 大唐发电 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=1.57 | [打开报告](0991_hk/daily/0991_hk_grid_report.md) |
| 港股通沪股票 | 0992.HK | 联想集团 | 1d | grid | 网格 | 1.84% | 0.76% | ok | grid_spacing=7.00% grid_count=5 take_profit=3.00% score=-1.27 | [打开报告](0992_hk/daily/0992_hk_grid_report.md) |
| 港股通沪股票 | 0995.HK | 安徽皖通高速公路 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0995_hk/daily/0995_hk_grid_report.md) |
| 港股通沪股票 | 0998.HK | 中信银行 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](0998_hk/daily/0998_hk_grid_report.md) |
| 港股通沪股票 | 0999.HK | 小菜园 | 1d | grid | 网格 | -5.20% | 5.55% | ok | grid_spacing=5.00% grid_count=7 take_profit=3.00% score=-0.40 | [打开报告](0999_hk/daily/0999_hk_grid_report.md) |
| 港股通沪股票 | 1024.HK | 快手－Ｗ | 1d | grid | 网格 | -5.02% | 5.14% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=1.61 | [打开报告](1024_hk/daily/1024_hk_grid_report.md) |
| 港股通沪股票 | 1030.HK | 新城发展 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=-1.61 | [打开报告](1030_hk/daily/1030_hk_grid_report.md) |
| 港股通沪股票 | 1033.HK | 中石化油服 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=5.00% grid_count=4 take_profit=3.00% score=4.75 | [打开报告](1033_hk/daily/1033_hk_grid_report.md) |
| 港股通沪股票 | 1038.HK | 长江基建集团 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=0.00 | [打开报告](1038_hk/daily/1038_hk_grid_report.md) |
| 港股通沪股票 | 1044.HK | 恒安国际 | 1d | grid | 网格 | 0.99% | 1.88% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](1044_hk/daily/1044_hk_grid_report.md) |
| 港股通沪股票 | 1052.HK | 越秀交通基建 | 1d | grid | 网格 | -5.65% | 6.05% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](1052_hk/daily/1052_hk_grid_report.md) |
| 港股通沪股票 | 1053.HK | 重庆钢铁股份 | 1d | grid | 网格 | -1.74% | 2.30% | ok | grid_spacing=5.00% grid_count=4 take_profit=3.00% score=-2.29 | [打开报告](1053_hk/daily/1053_hk_grid_report.md) |
| 港股通沪股票 | 1055.HK | 中国南方航空股份 | 1d | grid | 网格 | -2.15% | 5.97% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=0.00 | [打开报告](1055_hk/daily/1055_hk_grid_report.md) |
| 港股通沪股票 | 1057.HK | 浙江世宝 | 1d | grid | 网格 | 0.89% | 0.08% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=1.82 | [打开报告](1057_hk/daily/1057_hk_grid_report.md) |
| 港股通沪股票 | 1060.HK | 大麦娱乐 | 1d | grid | 网格 | -5.33% | 5.46% | ok | grid_spacing=4.00% grid_count=6 take_profit=3.00% score=-7.04 | [打开报告](1060_hk/daily/1060_hk_grid_report.md) |
| 港股通沪股票 | 1065.HK | 天津创业环保股份 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=5.00% grid_count=4 take_profit=5.00% score=0.00 | [打开报告](1065_hk/daily/1065_hk_grid_report.md) |
| 港股通沪股票 | 1066.HK | 威高股份 | 1d | grid | 网格 | -4.88% | 5.26% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=-1.08 | [打开报告](1066_hk/daily/1066_hk_grid_report.md) |
| 港股通沪股票 | 1070.HK | ＴＣＬ电子 | 1d | grid | 网格 | 2.50% | 0.12% | ok | grid_spacing=5.00% grid_count=4 take_profit=7.00% score=2.00 | [打开报告](1070_hk/daily/1070_hk_grid_report.md) |
| 港股通沪股票 | 1071.HK | 华电国际电力股份 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=6 take_profit=3.00% score=0.00 | [打开报告](1071_hk/daily/1071_hk_grid_report.md) |
| 港股通沪股票 | 1072.HK | 东方电气 | 1d | grid | 网格 | 2.32% | 0.44% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=6.21 | [打开报告](1072_hk/daily/1072_hk_grid_report.md) |
| 港股通沪股票 | 1083.HK | 港华智慧能源 | 1d | grid | 网格 | 1.02% | 1.01% | ok | grid_spacing=6.00% grid_count=4 take_profit=5.00% score=3.20 | [打开报告](1083_hk/daily/1083_hk_grid_report.md) |
| 港股通沪股票 | 1088.HK | 中国神华 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=5.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](1088_hk/daily/1088_hk_grid_report.md) |
| 港股通沪股票 | 1093.HK | 石药集团 | 1d | grid | 网格 | -0.40% | 0.40% | ok | grid_spacing=7.00% grid_count=6 take_profit=5.00% score=-2.42 | [打开报告](1093_hk/daily/1093_hk_grid_report.md) |
| 港股通沪股票 | 1099.HK | 国药控股 | 1d | grid | 网格 | -0.95% | 1.52% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](1099_hk/daily/1099_hk_grid_report.md) |
| 港股通沪股票 | 1108.HK | 凯盛新能 | 1d | grid | 网格 | -1.46% | 3.68% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=-4.24 | [打开报告](1108_hk/daily/1108_hk_grid_report.md) |
| 港股通沪股票 | 1109.HK | 华润置地 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=5.00% grid_count=7 take_profit=7.00% score=-1.07 | [打开报告](1109_hk/daily/1109_hk_grid_report.md) |
| 港股通沪股票 | 1112.HK | Ｈ＆Ｈ国际控股 | 1d | grid | 网格 | 2.55% | 0.97% | ok | grid_spacing=5.00% grid_count=4 take_profit=3.00% score=4.12 | [打开报告](1112_hk/daily/1112_hk_grid_report.md) |
| 港股通沪股票 | 1113.HK | 长实集团 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](1113_hk/daily/1113_hk_grid_report.md) |
| 港股通沪股票 | 1114.HK | BRILLIANCE CHI | 1d | grid | 网格 | -5.28% | 5.28% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=0.00 | [打开报告](1114_hk/daily/1114_hk_grid_report.md) |
| 港股通沪股票 | 1117.HK | 现代牧业 | 1d | grid | 网格 | -3.69% | 7.36% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=1.04 | [打开报告](1117_hk/daily/1117_hk_grid_report.md) |
| 港股通沪股票 | 1128.HK | 永利澳门 | 1d | grid | 网格 | 0.57% | 0.98% | ok | grid_spacing=5.00% grid_count=7 take_profit=3.00% score=-1.23 | [打开报告](1128_hk/daily/1128_hk_grid_report.md) |
| 港股通沪股票 | 1138.HK | 中远海能 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](1138_hk/daily/1138_hk_grid_report.md) |
| 港股通沪股票 | 1157.HK | 中联重科 | 1d | grid | 网格 | -0.06% | 0.06% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=2.87 | [打开报告](1157_hk/daily/1157_hk_grid_report.md) |
| 港股通沪股票 | 1164.HK | 中广核矿业 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=1.73 | [打开报告](1164_hk/daily/1164_hk_grid_report.md) |
| 港股通沪股票 | 1171.HK | 兖矿能源 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=5 take_profit=3.00% score=0.00 | [打开报告](1171_hk/daily/1171_hk_grid_report.md) |
| 港股通沪股票 | 1177.HK | 中国生物制药 | 1d | grid | 网格 | 0.01% | 2.61% | ok | grid_spacing=5.00% grid_count=7 take_profit=3.00% score=-10.09 | [打开报告](1177_hk/daily/1177_hk_grid_report.md) |
| 港股通沪股票 | 1186.HK | 中国铁建 | 1d | grid | 网格 | -1.05% | 1.05% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](1186_hk/daily/1186_hk_grid_report.md) |
| 港股通沪股票 | 1187.HK | 可孚医疗 | 1d | grid | 网格 | - | - | failed | 样本内区间为空，无法构建样本窗口。 | [打开报告](1187_hk/daily/1187_hk_1d_grid_report.md) |
| 港股通沪股票 | 1193.HK | 华润燃气 | 1d | grid | 网格 | -3.37% | 4.58% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](1193_hk/daily/1193_hk_grid_report.md) |
| 港股通沪股票 | 1196.HK | 伟禄集团 | 1d | grid | 网格 | -1.25% | 5.66% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=1.69 | [打开报告](1196_hk/daily/1196_hk_grid_report.md) |
| 港股通沪股票 | 1199.HK | 中远海运港口 | 1d | grid | 网格 | 2.06% | 1.78% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=0.00 | [打开报告](1199_hk/daily/1199_hk_grid_report.md) |
| 港股通沪股票 | 1208.HK | 五矿资源 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=4000, price=7.30 | [打开报告](1208_hk/daily/1208_hk_1d_grid_report.md) |
| 港股通沪股票 | 1209.HK | 华润万象生活 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=0.00 | [打开报告](1209_hk/daily/1209_hk_grid_report.md) |
| 港股通沪股票 | 1211.HK | 比亚迪股份 | 1d | grid | 网格 | 3.93% | 0.92% | ok | grid_spacing=5.00% grid_count=4 take_profit=7.00% score=1.04 | [打开报告](1211_hk/daily/1211_hk_grid_report.md) |
| 港股通沪股票 | 1258.HK | 中国有色矿业 | 1d | grid | 网格 | 2.51% | 5.78% | ok | grid_spacing=4.00% grid_count=4 take_profit=7.00% score=3.61 | [打开报告](1258_hk/daily/1258_hk_grid_report.md) |
| 港股通沪股票 | 1276.HK | 恒瑞医药 | 1d | grid | 网格 | 0.04% | 1.04% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-0.33 | [打开报告](1276_hk/daily/1276_hk_grid_report.md) |
| 港股通沪股票 | 1277.HK | 力量发展 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=0.00 | [打开报告](1277_hk/daily/1277_hk_grid_report.md) |
| 港股通沪股票 | 1288.HK | 农业银行 | 1d | grid | 网格 | 3.63% | 1.92% | ok | grid_spacing=6.00% grid_count=4 take_profit=7.00% score=0.00 | [打开报告](1288_hk/daily/1288_hk_grid_report.md) |
| 港股通沪股票 | 1299.HK | 友邦保险 | 1d | grid | 网格 | 2.16% | 0.05% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=1.66 | [打开报告](1299_hk/daily/1299_hk_grid_report.md) |
| 港股通沪股票 | 1302.HK | 先健科技 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=7 take_profit=7.00% score=-1.78 | [打开报告](1302_hk/daily/1302_hk_grid_report.md) |
| 港股通沪股票 | 1304.HK | FORTIOR | 1d | grid | 网格 | -3.39% | 5.32% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-2.21 | [打开报告](1304_hk/daily/1304_hk_grid_report.md) |
| 港股通沪股票 | 1308.HK | 海丰国际 | 1d | grid | 网格 | 1.33% | 0.70% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=0.36 | [打开报告](1308_hk/daily/1308_hk_grid_report.md) |
| 港股通沪股票 | 1310.HK | 香港宽频 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](1310_hk/daily/1310_hk_grid_report.md) |
| 港股通沪股票 | 1313.HK | 华润建材科技 | 1d | grid | 网格 | -3.34% | 3.87% | ok | grid_spacing=5.00% grid_count=7 take_profit=5.00% score=-2.34 | [打开报告](1313_hk/daily/1313_hk_grid_report.md) |
| 港股通沪股票 | 1316.HK | 耐世特 | 1d | grid | 网格 | -4.62% | 5.16% | ok | grid_spacing=7.00% grid_count=4 take_profit=5.00% score=3.97 | [打开报告](1316_hk/daily/1316_hk_grid_report.md) |
| 港股通沪股票 | 1318.HK | 毛戈平 | 1d | grid | 网格 | -2.05% | 4.32% | ok | grid_spacing=7.00% grid_count=7 take_profit=7.00% score=0.59 | [打开报告](1318_hk/daily/1318_hk_grid_report.md) |
| 港股通沪股票 | 1330.HK | 绿色动力环保 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](1330_hk/daily/1330_hk_grid_report.md) |
| 港股通沪股票 | 1333.HK | 博雷顿 | 1d | grid | 网格 | -5.07% | 5.07% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=-2.12 | [打开报告](1333_hk/daily/1333_hk_grid_report.md) |
| 港股通沪股票 | 1336.HK | 新华保险 | 1d | grid | 网格 | 0.32% | 4.79% | ok | grid_spacing=5.00% grid_count=4 take_profit=7.00% score=4.15 | [打开报告](1336_hk/daily/1336_hk_grid_report.md) |
| 港股通沪股票 | 1339.HK | 中国人民保险集团 | 1d | grid | 网格 | -2.71% | 6.45% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=5.44 | [打开报告](1339_hk/daily/1339_hk_grid_report.md) |
| 港股通沪股票 | 1347.HK | 华虹半导体 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=1000, price=88.30 | [打开报告](1347_hk/daily/1347_hk_1d_grid_report.md) |
| 港股通沪股票 | 1349.HK | 复旦张江 | 1d | grid | 网格 | 0.33% | 0.37% | ok | grid_spacing=3.00% grid_count=7 take_profit=3.00% score=-8.44 | [打开报告](1349_hk/daily/1349_hk_grid_report.md) |
| 港股通沪股票 | 1357.HK | 美图公司 | 1d | grid | 网格 | -1.63% | 5.35% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=-3.09 | [打开报告](1357_hk/daily/1357_hk_grid_report.md) |
| 港股通沪股票 | 1359.HK | 中国信达 | 1d | grid | 网格 | -0.61% | 1.20% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=3.65 | [打开报告](1359_hk/daily/1359_hk_grid_report.md) |
| 港股通沪股票 | 1361.HK | ３６１度 | 1d | grid | 网格 | -0.29% | 0.29% | ok | grid_spacing=6.00% grid_count=4 take_profit=5.00% score=4.01 | [打开报告](1361_hk/daily/1361_hk_grid_report.md) |
| 港股通沪股票 | 1364.HK | 古茗 | 1d | grid | 网格 | -0.78% | 0.90% | ok | grid_spacing=5.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](1364_hk/daily/1364_hk_grid_report.md) |
| 港股通沪股票 | 1368.HK | 特步国际 | 1d | grid | 网格 | -4.89% | 5.72% | ok | grid_spacing=7.00% grid_count=4 take_profit=7.00% score=-3.54 | [打开报告](1368_hk/daily/1368_hk_grid_report.md) |
| 港股通沪股票 | 1375.HK | 中州证券 | 1d | grid | 网格 | 0.11% | 1.33% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-4.36 | [打开报告](1375_hk/daily/1375_hk_grid_report.md) |
| 港股通沪股票 | 1378.HK | 中国宏桥 | 1d | grid | 网格 | 3.07% | 2.86% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=3.68 | [打开报告](1378_hk/daily/1378_hk_grid_report.md) |
| 港股通沪股票 | 1384.HK | 滴普科技 | 1d | grid | 网格 | -0.25% | 5.52% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=3.02 | [打开报告](1384_hk/daily/1384_hk_grid_report.md) |
| 港股通沪股票 | 1385.HK | 上海复旦 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=1000, price=43.78 | [打开报告](1385_hk/daily/1385_hk_1d_grid_report.md) |
| 港股通沪股票 | 1398.HK | 工商银行 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=5.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](1398_hk/daily/1398_hk_grid_report.md) |
| 港股通沪股票 | 1405.HK | 达势股份 | 1d | grid | 网格 | -3.37% | 5.04% | ok | grid_spacing=6.00% grid_count=6 take_profit=3.00% score=-1.01 | [打开报告](1405_hk/daily/1405_hk_grid_report.md) |
| 港股通沪股票 | 1415.HK | 高伟电子 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=1000, price=34.66 | [打开报告](1415_hk/daily/1415_hk_1d_grid_report.md) |
| 港股通沪股票 | **1428.HK** | **耀才证券金融** | 1d | grid | 网格 | **12.33%** | 3.38% | ok | **grid_spacing=6.00% grid_count=5 take_profit=7.00% score=1.64** | [打开报告](1428_hk/daily/1428_hk_grid_report.md) |
| 港股通沪股票 | 1448.HK | 福寿园 | 1d | grid | 网格 | 1.11% | 0.79% | ok | grid_spacing=7.00% grid_count=4 take_profit=5.00% score=1.72 | [打开报告](1448_hk/daily/1448_hk_grid_report.md) |
| 港股通沪股票 | 1456.HK | 国联民生 | 1d | grid | 网格 | -0.01% | 4.89% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=-5.47 | [打开报告](1456_hk/daily/1456_hk_grid_report.md) |
| 港股通沪股票 | 1475.HK | 日清食品 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=5.00% grid_count=4 take_profit=7.00% score=6.56 | [打开报告](1475_hk/daily/1475_hk_grid_report.md) |
| 港股通沪股票 | **1478.HK** | **丘钛科技** | 1d | grid | 网格 | **5.06%** | 1.05% | ok | **grid_spacing=7.00% grid_count=7 take_profit=7.00% score=-11.18** | [打开报告](1478_hk/daily/1478_hk_grid_report.md) |
| 港股通沪股票 | 1513.HK | 丽珠医药 | 1d | grid | 网格 | 0.43% | 0.12% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-3.07 | [打开报告](1513_hk/daily/1513_hk_grid_report.md) |
| 港股通沪股票 | 1519.HK | 极兔速递－Ｗ | 1d | grid | 网格 | 1.36% | 6.49% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=5.17 | [打开报告](1519_hk/daily/1519_hk_grid_report.md) |
| 港股通沪股票 | 1528.HK | 红星美凯龙 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=5.00% grid_count=4 take_profit=5.00% score=-13.82 | [打开报告](1528_hk/daily/1528_hk_grid_report.md) |
| 港股通沪股票 | 1530.HK | 三生制药 | 1d | grid | 网格 | 1.99% | 2.61% | ok | grid_spacing=7.00% grid_count=7 take_profit=7.00% score=1.65 | [打开报告](1530_hk/daily/1530_hk_grid_report.md) |
| 港股通沪股票 | 1548.HK | 金斯瑞生物科技 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=2000, price=17.59 | [打开报告](1548_hk/daily/1548_hk_1d_grid_report.md) |
| 港股通沪股票 | 1579.HK | 颐海国际 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=6 take_profit=3.00% score=3.22 | [打开报告](1579_hk/daily/1579_hk_grid_report.md) |
| 港股通沪股票 | 1585.HK | 雅迪控股 | 1d | grid | 网格 | 1.07% | 0.01% | ok | grid_spacing=5.00% grid_count=5 take_profit=3.00% score=-2.73 | [打开报告](1585_hk/daily/1585_hk_grid_report.md) |
| 港股通沪股票 | 1610.HK | 中粮家佳康 | 1d | grid | 网格 | -3.88% | 5.18% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=-2.18 | [打开报告](1610_hk/daily/1610_hk_grid_report.md) |
| 港股通沪股票 | 1618.HK | 中国中冶 | 1d | grid | 网格 | -1.48% | 2.53% | ok | grid_spacing=6.00% grid_count=7 take_profit=3.00% score=1.04 | [打开报告](1618_hk/daily/1618_hk_grid_report.md) |
| 港股通沪股票 | **1635.HK** | **大众公用** | 1d | grid | 网格 | **30.95%** | 3.43% | ok | **grid_spacing=3.00% grid_count=5 take_profit=3.00% score=0.00** | [打开报告](1635_hk/daily/1635_hk_grid_report.md) |
| 港股通沪股票 | 1658.HK | 邮储银行 | 1d | grid | 网格 | 0.65% | 0.40% | ok | grid_spacing=7.00% grid_count=7 take_profit=5.00% score=1.27 | [打开报告](1658_hk/daily/1658_hk_grid_report.md) |
| 港股通沪股票 | 1675.HK | 亚信科技 | 1d | grid | 网格 | -2.98% | 3.91% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-9.70 | [打开报告](1675_hk/daily/1675_hk_grid_report.md) |
| 港股通沪股票 | 1681.HK | 康臣药业 | 1d | grid | 网格 | -0.19% | 0.56% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](1681_hk/daily/1681_hk_grid_report.md) |
| 港股通沪股票 | 1686.HK | 新意网集团 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-10.57 | [打开报告](1686_hk/daily/1686_hk_grid_report.md) |
| 港股通沪股票 | 1691.HK | ＪＳ环球生活 | 1d | grid | 网格 | -4.03% | 4.91% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=12.19 | [打开报告](1691_hk/daily/1691_hk_grid_report.md) |
| 港股通沪股票 | 1729.HK | 汇聚科技 | 1d | grid | 网格 | -5.35% | 5.35% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=18.44 | [打开报告](1729_hk/daily/1729_hk_grid_report.md) |
| 港股通沪股票 | 1735.HK | 中环新能源 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=6 take_profit=3.00% score=0.00 | [打开报告](1735_hk/daily/1735_hk_grid_report.md) |
| 港股通沪股票 | 1766.HK | 中国中车 | 1d | grid | 网格 | -0.47% | 4.13% | ok | grid_spacing=5.00% grid_count=4 take_profit=7.00% score=0.00 | [打开报告](1766_hk/daily/1766_hk_grid_report.md) |
| 港股通沪股票 | 1772.HK | 赣锋锂业 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=5 take_profit=7.00% score=0.00 | [打开报告](1772_hk/daily/1772_hk_grid_report.md) |
| 港股通沪股票 | 1773.HK | 天立国际控股 | 1d | grid | 网格 | -2.89% | 5.35% | ok | grid_spacing=7.00% grid_count=7 take_profit=7.00% score=-11.37 | [打开报告](1773_hk/daily/1773_hk_grid_report.md) |
| 港股通沪股票 | 1776.HK | 广发证券 | 1d | grid | 网格 | -5.64% | 6.22% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=5.74 | [打开报告](1776_hk/daily/1776_hk_grid_report.md) |
| 港股通沪股票 | 1783.HK | 晋景新能 | 1d | grid | 网格 | 1.26% | 1.83% | ok | grid_spacing=4.00% grid_count=4 take_profit=5.00% score=7.19 | [打开报告](1783_hk/daily/1783_hk_grid_report.md) |
| 港股通沪股票 | 1787.HK | 山东黄金 | 1d | grid | 网格 | -3.48% | 4.61% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=0.00 | [打开报告](1787_hk/daily/1787_hk_grid_report.md) |
| 港股通沪股票 | 1788.HK | 国泰君安国际 | 1d | grid | 网格 | 2.91% | 0.99% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-10.44 | [打开报告](1788_hk/daily/1788_hk_grid_report.md) |
| 港股通沪股票 | 1789.HK | 爱康医疗 | 1d | grid | 网格 | 2.72% | 0.20% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=9.96 | [打开报告](1789_hk/daily/1789_hk_grid_report.md) |
| 港股通沪股票 | 1797.HK | 东方甄选 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=6 take_profit=3.00% score=-2.20 | [打开报告](1797_hk/daily/1797_hk_grid_report.md) |
| 港股通沪股票 | 1800.HK | 中国交通建设 | 1d | grid | 网格 | -5.14% | 5.14% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](1800_hk/daily/1800_hk_grid_report.md) |
| 港股通沪股票 | 1801.HK | 信达生物 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=500, price=105.30 | [打开报告](1801_hk/daily/1801_hk_1d_grid_report.md) |
| 港股通沪股票 | 1810.HK | 小米集团－Ｗ | 1d | grid | 网格 | -1.71% | 3.42% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-6.70 | [打开报告](1810_hk/daily/1810_hk_grid_report.md) |
| 港股通沪股票 | 1811.HK | 中广核新能源 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](1811_hk/daily/1811_hk_grid_report.md) |
| 港股通沪股票 | 1816.HK | 中广核电力 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=1.00 | [打开报告](1816_hk/daily/1816_hk_grid_report.md) |
| 港股通沪股票 | 1818.HK | 招金矿业 | 1d | grid | 网格 | -0.11% | 1.92% | ok | grid_spacing=7.00% grid_count=7 take_profit=5.00% score=0.00 | [打开报告](1818_hk/daily/1818_hk_grid_report.md) |
| 港股通沪股票 | 1828.HK | 富卫集团 | 1d | grid | 网格 | -2.48% | 2.55% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-1.01 | [打开报告](1828_hk/daily/1828_hk_grid_report.md) |
| 港股通沪股票 | 1833.HK | 平安好医生 | 1d | grid | 网格 | -4.00% | 4.26% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-10.19 | [打开报告](1833_hk/daily/1833_hk_grid_report.md) |
| 港股通沪股票 | 1836.HK | 九兴控股 | 1d | grid | 网格 | 1.06% | 0.73% | ok | grid_spacing=7.00% grid_count=4 take_profit=3.00% score=2.12 | [打开报告](1836_hk/daily/1836_hk_grid_report.md) |
| 港股通沪股票 | 1858.HK | 春立医疗 | 1d | grid | 网格 | -4.56% | 5.04% | ok | grid_spacing=3.00% grid_count=7 take_profit=3.00% score=4.65 | [打开报告](1858_hk/daily/1858_hk_grid_report.md) |
| 港股通沪股票 | 1860.HK | 汇量科技 | 1d | grid | 网格 | -3.36% | 4.94% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](1860_hk/daily/1860_hk_grid_report.md) |
| 港股通沪股票 | 1876.HK | 百威亚太 | 1d | grid | 网格 | 1.24% | 0.86% | ok | grid_spacing=7.00% grid_count=4 take_profit=5.00% score=-3.13 | [打开报告](1876_hk/daily/1876_hk_grid_report.md) |
| 港股通沪股票 | **1877.HK** | **君实生物** | 1d | grid | 网格 | **5.31%** | 2.87% | ok | **grid_spacing=7.00% grid_count=4 take_profit=3.00% score=-7.74** | [打开报告](1877_hk/daily/1877_hk_grid_report.md) |
| 港股通沪股票 | 1880.HK | 中国中免 | 1d | grid | 网格 | -3.86% | 5.65% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=6.52 | [打开报告](1880_hk/daily/1880_hk_grid_report.md) |
| 港股通沪股票 | 1882.HK | 海天国际 | 1d | grid | 网格 | 1.80% | 0.30% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=4.27 | [打开报告](1882_hk/daily/1882_hk_grid_report.md) |
| 港股通沪股票 | 1883.HK | 中信国际电讯 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](1883_hk/daily/1883_hk_grid_report.md) |
| 港股通沪股票 | 1888.HK | 建滔积层板 | 1d | grid | 网格 | 1.76% | 1.06% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=6.60 | [打开报告](1888_hk/daily/1888_hk_grid_report.md) |
| 港股通沪股票 | 1896.HK | 猫眼娱乐 | 1d | grid | 网格 | -4.84% | 8.04% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=-9.72 | [打开报告](1896_hk/daily/1896_hk_grid_report.md) |
| 港股通沪股票 | 1898.HK | 中煤能源 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=0.00 | [打开报告](1898_hk/daily/1898_hk_grid_report.md) |
| 港股通沪股票 | 1907.HK | 中国旭阳集团 | 1d | grid | 网格 | 1.70% | 0.31% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=3.27 | [打开报告](1907_hk/daily/1907_hk_grid_report.md) |
| 港股通沪股票 | 1908.HK | 建发国际集团 | 1d | grid | 网格 | -4.15% | 6.28% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=-0.64 | [打开报告](1908_hk/daily/1908_hk_grid_report.md) |
| 港股通沪股票 | 1910.HK | 新秀丽 | 1d | grid | 网格 | -4.42% | 6.36% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=14.46 | [打开报告](1910_hk/daily/1910_hk_grid_report.md) |
| 港股通沪股票 | **1918.HK** | **融创中国** | 1d | grid | 网格 | **5.16%** | 3.52% | ok | **grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-3.25** | [打开报告](1918_hk/daily/1918_hk_grid_report.md) |
| 港股通沪股票 | 1919.HK | 中远海控 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=7 take_profit=7.00% score=1.13 | [打开报告](1919_hk/daily/1919_hk_grid_report.md) |
| 港股通沪股票 | 1921.HK | 达力普控股 | 1d | grid | 网格 | -5.54% | 7.03% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=5.00 | [打开报告](1921_hk/daily/1921_hk_grid_report.md) |
| 港股通沪股票 | 1928.HK | 金沙中国有限公司 | 1d | grid | 网格 | -3.36% | 6.47% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=13.10 | [打开报告](1928_hk/daily/1928_hk_grid_report.md) |
| 港股通沪股票 | 1929.HK | 周大福 | 1d | grid | 网格 | 1.57% | 1.53% | ok | grid_spacing=7.00% grid_count=7 take_profit=7.00% score=-1.30 | [打开报告](1929_hk/daily/1929_hk_grid_report.md) |
| 港股通沪股票 | 1951.HK | 锦欣生殖 | 1d | grid | 网格 | 2.39% | 2.20% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=-6.59 | [打开报告](1951_hk/daily/1951_hk_grid_report.md) |
| 港股通沪股票 | 1952.HK | 云顶新耀 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=500, price=63.75 | [打开报告](1952_hk/daily/1952_hk_1d_grid_report.md) |
| 港股通沪股票 | 1963.HK | 重庆银行 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=1.12 | [打开报告](1963_hk/daily/1963_hk_grid_report.md) |
| 港股通沪股票 | 1972.HK | 太古地产 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](1972_hk/daily/1972_hk_grid_report.md) |
| 港股通沪股票 | 1988.HK | 民生银行 | 1d | grid | 网格 | -0.76% | 1.53% | ok | grid_spacing=7.00% grid_count=7 take_profit=7.00% score=1.46 | [打开报告](1988_hk/daily/1988_hk_grid_report.md) |
| 港股通沪股票 | 1989.HK | 广合科技 | 1d | grid | 网格 | - | - | failed | 样本内区间为空，无法构建样本窗口。 | [打开报告](1989_hk/daily/1989_hk_1d_grid_report.md) |
| 港股通沪股票 | **1997.HK** | **九龙仓置业** | 1d | grid | 网格 | **7.12%** | 2.45% | ok | **grid_spacing=3.00% grid_count=4 take_profit=5.00% score=4.98** | [打开报告](1997_hk/daily/1997_hk_grid_report.md) |
| 港股通沪股票 | 1999.HK | 敏华控股 | 1d | grid | 网格 | -4.35% | 6.32% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=3.64 | [打开报告](1999_hk/daily/1999_hk_grid_report.md) |
| 港股通沪股票 | 2005.HK | 石四药集团 | 1d | grid | 网格 | -5.91% | 6.46% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=0.00 | [打开报告](2005_hk/daily/2005_hk_grid_report.md) |
| 港股通沪股票 | 2007.HK | 碧桂园 | 1d | grid | 网格 | -0.15% | 5.02% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=0.00 | [打开报告](2007_hk/daily/2007_hk_grid_report.md) |
| 港股通沪股票 | 2009.HK | 金隅集团 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=7 take_profit=3.00% score=-0.57 | [打开报告](2009_hk/daily/2009_hk_grid_report.md) |
| 港股通沪股票 | 2013.HK | 微盟集团 | 1d | grid | 网格 | -2.06% | 3.25% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-6.75 | [打开报告](2013_hk/daily/2013_hk_grid_report.md) |
| 港股通沪股票 | 2015.HK | 理想汽车－Ｗ | 1d | grid | 网格 | 0.40% | 0.20% | ok | grid_spacing=7.00% grid_count=6 take_profit=3.00% score=-11.59 | [打开报告](2015_hk/daily/2015_hk_grid_report.md) |
| 港股通沪股票 | 2016.HK | 浙商银行 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=4 take_profit=5.00% score=1.30 | [打开报告](2016_hk/daily/2016_hk_grid_report.md) |
| 港股通沪股票 | 2018.HK | 瑞声科技 | 1d | grid | 网格 | -6.07% | 7.62% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=3.97 | [打开报告](2018_hk/daily/2018_hk_grid_report.md) |
| 港股通沪股票 | 2020.HK | 安踏体育 | 1d | grid | 网格 | 1.47% | 0.50% | ok | grid_spacing=7.00% grid_count=4 take_profit=5.00% score=-1.96 | [打开报告](2020_hk/daily/2020_hk_grid_report.md) |
| 港股通沪股票 | 2038.HK | 富智康集团 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](2038_hk/daily/2038_hk_grid_report.md) |
| 港股通沪股票 | 2039.HK | 中集集团 | 1d | grid | 网格 | 2.92% | 1.50% | ok | grid_spacing=4.00% grid_count=4 take_profit=5.00% score=27.45 | [打开报告](2039_hk/daily/2039_hk_grid_report.md) |
| 港股通沪股票 | 2050.HK | 三花智控 | 1d | grid | 网格 | -5.89% | 6.43% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=12.22 | [打开报告](2050_hk/daily/2050_hk_grid_report.md) |
| 港股通沪股票 | 2057.HK | 中通快递－Ｗ | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](2057_hk/daily/2057_hk_grid_report.md) |
| 港股通沪股票 | **2068.HK** | **中铝国际** | 1d | grid | 网格 | **13.95%** | 3.01% | ok | **grid_spacing=3.00% grid_count=4 take_profit=7.00% score=2.44** | [打开报告](2068_hk/daily/2068_hk_grid_report.md) |
| 港股通沪股票 | 2096.HK | 先声药业 | 1d | grid | 网格 | 0.40% | 1.53% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=7.86 | [打开报告](2096_hk/daily/2096_hk_grid_report.md) |
| 港股通沪股票 | 2097.HK | 蜜雪集团 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=100, price=405.60 | [打开报告](2097_hk/daily/2097_hk_1d_grid_report.md) |
| 港股通沪股票 | **2099.HK** | **中国黄金国际** | 1d | grid | 网格 | **8.77%** | 3.39% | ok | **grid_spacing=3.00% grid_count=4 take_profit=7.00% score=7.15** | [打开报告](2099_hk/daily/2099_hk_grid_report.md) |
| 港股通沪股票 | 2128.HK | 中国联塑 | 1d | grid | 网格 | 0.36% | 0.02% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=14.59 | [打开报告](2128_hk/daily/2128_hk_grid_report.md) |
| 港股通沪股票 | 2145.HK | 上美股份 | 1d | grid | 网格 | -2.25% | 4.57% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=1.43 | [打开报告](2145_hk/daily/2145_hk_grid_report.md) |
| 港股通沪股票 | 2155.HK | 森松国际 | 1d | grid | 网格 | -6.08% | 7.20% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=7.85 | [打开报告](2155_hk/daily/2155_hk_grid_report.md) |
| 港股通沪股票 | 2157.HK | 乐普生物 | 1d | grid | 网格 | 1.70% | 2.14% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-7.85 | [打开报告](2157_hk/daily/2157_hk_grid_report.md) |
| 港股通沪股票 | 2158.HK | 医渡科技 | 1d | grid | 网格 | 0.93% | 0.37% | ok | grid_spacing=7.00% grid_count=7 take_profit=5.00% score=0.66 | [打开报告](2158_hk/daily/2158_hk_grid_report.md) |
| 港股通沪股票 | 2162.HK | 康诺亚－Ｂ | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=500, price=72.00 | [打开报告](2162_hk/daily/2162_hk_1d_grid_report.md) |
| 港股通沪股票 | 2171.HK | 科济药业－Ｂ | 1d | grid | 网格 | -3.51% | 6.70% | ok | grid_spacing=5.00% grid_count=4 take_profit=7.00% score=-4.24 | [打开报告](2171_hk/daily/2171_hk_grid_report.md) |
| 港股通沪股票 | 2172.HK | 微创脑科学 | 1d | grid | 网格 | -3.46% | 6.93% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=-9.46 | [打开报告](2172_hk/daily/2172_hk_grid_report.md) |
| 港股通沪股票 | 2186.HK | 绿叶制药 | 1d | grid | 网格 | 0.82% | 3.34% | ok | grid_spacing=5.00% grid_count=7 take_profit=5.00% score=-9.16 | [打开报告](2186_hk/daily/2186_hk_grid_report.md) |
| 港股通沪股票 | 2192.HK | 医脉通 | 1d | grid | 网格 | 0.21% | 2.59% | ok | grid_spacing=6.00% grid_count=7 take_profit=3.00% score=-9.59 | [打开报告](2192_hk/daily/2192_hk_grid_report.md) |
| 港股通沪股票 | 2196.HK | 复星医药 | 1d | grid | 网格 | 0.39% | 1.78% | ok | grid_spacing=4.00% grid_count=6 take_profit=3.00% score=-1.89 | [打开报告](2196_hk/daily/2196_hk_grid_report.md) |
| 港股通沪股票 | 2202.HK | 万科企业 | 1d | grid | 网格 | -0.22% | 2.05% | ok | grid_spacing=5.00% grid_count=7 take_profit=3.00% score=-11.15 | [打开报告](2202_hk/daily/2202_hk_grid_report.md) |
| 港股通沪股票 | **2208.HK** | **金风科技** | 1d | grid | 网格 | **8.54%** | 1.78% | ok | **grid_spacing=7.00% grid_count=7 take_profit=5.00% score=0.00** | [打开报告](2208_hk/daily/2208_hk_grid_report.md) |
| 港股通沪股票 | 2218.HK | 安德利果汁 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=4 take_profit=3.00% score=-4.99 | [打开报告](2218_hk/daily/2218_hk_grid_report.md) |
| 港股通沪股票 | 2228.HK | 晶泰控股 | 1d | grid | 网格 | 2.77% | 6.30% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=8.53 | [打开报告](2228_hk/daily/2228_hk_grid_report.md) |
| 港股通沪股票 | 2232.HK | 晶苑国际 | 1d | grid | 网格 | 3.09% | 2.19% | ok | grid_spacing=5.00% grid_count=4 take_profit=5.00% score=0.00 | [打开报告](2232_hk/daily/2232_hk_grid_report.md) |
| 港股通沪股票 | 2233.HK | 西部水泥 | 1d | grid | 网格 | -16.75% | 19.25% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=0.00 | [打开报告](2233_hk/daily/2233_hk_grid_report.md) |
| 港股通沪股票 | 2238.HK | 广汽集团 | 1d | grid | 网格 | -3.03% | 4.31% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=13.90 | [打开报告](2238_hk/daily/2238_hk_grid_report.md) |
| 港股通沪股票 | 2252.HK | 微创机器人－Ｂ | 1d | grid | 网格 | 4.77% | 0.04% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=-10.82 | [打开报告](2252_hk/daily/2252_hk_grid_report.md) |
| 港股通沪股票 | 2255.HK | 海昌海洋公园 | 1d | grid | 网格 | -5.95% | 6.37% | ok | grid_spacing=5.00% grid_count=7 take_profit=5.00% score=-11.06 | [打开报告](2255_hk/daily/2255_hk_grid_report.md) |
| 港股通沪股票 | 2259.HK | 紫金黄金国际 | 1d | grid | 网格 | -0.25% | 0.25% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=0.00 | [打开报告](2259_hk/daily/2259_hk_grid_report.md) |
| 港股通沪股票 | 2268.HK | 药明合联 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=500, price=69.00 | [打开报告](2268_hk/daily/2268_hk_1d_grid_report.md) |
| 港股通沪股票 | 2269.HK | 药明生物 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=6 take_profit=3.00% score=0.89 | [打开报告](2269_hk/daily/2269_hk_grid_report.md) |
| 港股通沪股票 | **2273.HK** | **固生堂** | 1d | grid | 网格 | **5.74%** | 1.75% | ok | **grid_spacing=5.00% grid_count=4 take_profit=5.00% score=-2.12** | [打开报告](2273_hk/daily/2273_hk_grid_report.md) |
| 港股通沪股票 | 2276.HK | 康耐特光学 | 1d | grid | 网格 | -3.20% | 7.31% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=-7.01 | [打开报告](2276_hk/daily/2276_hk_grid_report.md) |
| 港股通沪股票 | 2282.HK | 美高梅中国 | 1d | grid | 网格 | -2.17% | 5.26% | ok | grid_spacing=4.00% grid_count=4 take_profit=7.00% score=7.90 | [打开报告](2282_hk/daily/2282_hk_grid_report.md) |
| 港股通沪股票 | 2285.HK | 泉峰控股 | 1d | grid | 网格 | -2.18% | 6.02% | ok | grid_spacing=5.00% grid_count=4 take_profit=5.00% score=3.68 | [打开报告](2285_hk/daily/2285_hk_grid_report.md) |
| 港股通沪股票 | 2291.HK | 心泰医疗 | 1d | grid | 网格 | -2.38% | 6.03% | ok | grid_spacing=7.00% grid_count=4 take_profit=3.00% score=-6.61 | [打开报告](2291_hk/daily/2291_hk_grid_report.md) |
| 港股通沪股票 | 2313.HK | 申洲国际 | 1d | grid | 网格 | -4.83% | 5.12% | ok | grid_spacing=7.00% grid_count=6 take_profit=3.00% score=0.00 | [打开报告](2313_hk/daily/2313_hk_grid_report.md) |
| 港股通沪股票 | 2314.HK | 理文造纸 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=4 take_profit=5.00% score=0.00 | [打开报告](2314_hk/daily/2314_hk_grid_report.md) |
| 港股通沪股票 | 2315.HK | 百奥赛图－Ｂ | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](2315_hk/daily/2315_hk_grid_report.md) |
| 港股通沪股票 | 2318.HK | 中国平安 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=500, price=58.25 | [打开报告](2318_hk/daily/2318_hk_1d_grid_report.md) |
| 港股通沪股票 | 2319.HK | 蒙牛乳业 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=4.12 | [打开报告](2319_hk/daily/2319_hk_grid_report.md) |
| 港股通沪股票 | 2328.HK | 中国财险 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=2000, price=18.28 | [打开报告](2328_hk/daily/2328_hk_1d_grid_report.md) |
| 港股通沪股票 | 2331.HK | 李宁 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=6.33 | [打开报告](2331_hk/daily/2331_hk_grid_report.md) |
| 港股通沪股票 | 2333.HK | 长城汽车 | 1d | grid | 网格 | -3.21% | 3.75% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-2.80 | [打开报告](2333_hk/daily/2333_hk_grid_report.md) |
| 港股通沪股票 | 2338.HK | 潍柴动力 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=5.00% grid_count=7 take_profit=5.00% score=0.78 | [打开报告](2338_hk/daily/2338_hk_grid_report.md) |
| 港股通沪股票 | 2343.HK | 太平洋航运 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=7 take_profit=5.00% score=0.00 | [打开报告](2343_hk/daily/2343_hk_grid_report.md) |
| 港股通沪股票 | 2356.HK | 大新银行集团 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](2356_hk/daily/2356_hk_grid_report.md) |
| 港股通沪股票 | 2357.HK | 中航科工 | 1d | grid | 网格 | -2.41% | 2.41% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=0.73 | [打开报告](2357_hk/daily/2357_hk_grid_report.md) |
| 港股通沪股票 | 2359.HK | 药明康德 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=7.00 | [打开报告](2359_hk/daily/2359_hk_grid_report.md) |
| 港股通沪股票 | 2367.HK | 巨子生物 | 1d | grid | 网格 | -0.71% | 2.36% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-5.67 | [打开报告](2367_hk/daily/2367_hk_grid_report.md) |
| 港股通沪股票 | **2378.HK** | **保诚** | 1d | grid | 网格 | **6.21%** | 3.27% | ok | **grid_spacing=3.00% grid_count=4 take_profit=7.00% score=0.00** | [打开报告](2378_hk/daily/2378_hk_grid_report.md) |
| 港股通沪股票 | 2380.HK | 中国电力 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](2380_hk/daily/2380_hk_grid_report.md) |
| 港股通沪股票 | 2382.HK | 舜宇光学科技 | 1d | grid | 网格 | 1.87% | 3.21% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-2.62 | [打开报告](2382_hk/daily/2382_hk_grid_report.md) |
| 港股通沪股票 | 2386.HK | 中石化炼化工程 | 1d | grid | 网格 | -3.79% | 6.25% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](2386_hk/daily/2386_hk_grid_report.md) |
| 港股通沪股票 | 2388.HK | 中银香港 | 1d | grid | 网格 | 1.28% | 0.67% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=0.00 | [打开报告](2388_hk/daily/2388_hk_grid_report.md) |
| 港股通沪股票 | 2400.HK | 心动公司 | 1d | grid | 网格 | -0.93% | 2.03% | ok | grid_spacing=7.00% grid_count=4 take_profit=3.00% score=-0.63 | [打开报告](2400_hk/daily/2400_hk_grid_report.md) |
| 港股通沪股票 | 2402.HK | 亿华通 | 1d | grid | 网格 | -8.55% | 9.20% | ok | grid_spacing=3.00% grid_count=5 take_profit=7.00% score=-5.00 | [打开报告](2402_hk/daily/2402_hk_grid_report.md) |
| 港股通沪股票 | 2410.HK | 同源康医药－Ｂ | 1d | grid | 网格 | -6.10% | 6.88% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=6.48 | [打开报告](2410_hk/daily/2410_hk_grid_report.md) |
| 港股通沪股票 | 2419.HK | 德康农牧 | 1d | grid | 网格 | -0.96% | 3.38% | ok | grid_spacing=7.00% grid_count=4 take_profit=3.00% score=-1.08 | [打开报告](2419_hk/daily/2419_hk_grid_report.md) |
| 港股通沪股票 | 2423.HK | 贝壳－Ｗ | 1d | grid | 网格 | 1.54% | 1.82% | ok | grid_spacing=6.00% grid_count=4 take_profit=5.00% score=-1.11 | [打开报告](2423_hk/daily/2423_hk_grid_report.md) |
| 港股通沪股票 | 2431.HK | 佑驾创新 | 1d | grid | 网格 | -3.12% | 5.17% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-11.86 | [打开报告](2431_hk/daily/2431_hk_grid_report.md) |
| 港股通沪股票 | 2432.HK | 越疆 | 1d | grid | 网格 | 3.82% | 2.60% | ok | grid_spacing=7.00% grid_count=6 take_profit=7.00% score=-9.93 | [打开报告](2432_hk/daily/2432_hk_grid_report.md) |
| 港股通沪股票 | 2460.HK | 华润饮料 | 1d | grid | 网格 | -2.80% | 4.89% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=-0.07 | [打开报告](2460_hk/daily/2460_hk_grid_report.md) |
| 港股通沪股票 | 2465.HK | 龙蟠科技 | 1d | grid | 网格 | -5.30% | 7.03% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=0.00 | [打开报告](2465_hk/daily/2465_hk_grid_report.md) |
| 港股通沪股票 | 2473.HK | 喜相逢集团 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](2473_hk/daily/2473_hk_grid_report.md) |
| 港股通沪股票 | 2476.HK | 胜宏科技 | 1d | grid | 网格 | - | - | failed | 样本内区间为空，无法构建样本窗口。 | [打开报告](2476_hk/daily/2476_hk_1d_grid_report.md) |
| 港股通沪股票 | 2477.HK | 经纬天地（新） | 1d | grid | 网格 | -6.70% | 10.35% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](2477_hk/daily/2477_hk_grid_report.md) |
| 港股通沪股票 | 2493.HK | 迈威生物－Ｂ | 1d | grid | 网格 | - | - | failed | 样本内区间为空，无法构建样本窗口。 | [打开报告](2493_hk/daily/2493_hk_1d_grid_report.md) |
| 港股通沪股票 | 2498.HK | 速腾聚创 | 1d | grid | 网格 | 1.73% | 1.47% | ok | grid_spacing=7.00% grid_count=7 take_profit=7.00% score=2.48 | [打开报告](2498_hk/daily/2498_hk_grid_report.md) |
| 港股通沪股票 | 2506.HK | 讯飞医疗科技 | 1d | grid | 网格 | 3.03% | 0.99% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-11.42 | [打开报告](2506_hk/daily/2506_hk_grid_report.md) |
| 港股通沪股票 | 2507.HK | 西锐 | 1d | grid | 网格 | -5.37% | 7.38% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=-9.60 | [打开报告](2507_hk/daily/2507_hk_grid_report.md) |
| 港股通沪股票 | 2510.HK | 德翔海运 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=4 take_profit=7.00% score=0.34 | [打开报告](2510_hk/daily/2510_hk_grid_report.md) |
| 港股通沪股票 | 2517.HK | 锅圈 | 1d | grid | 网格 | -4.68% | 9.00% | ok | grid_spacing=4.00% grid_count=5 take_profit=7.00% score=0.00 | [打开报告](2517_hk/daily/2517_hk_grid_report.md) |
| 港股通沪股票 | 2525.HK | 禾赛－Ｗ | 1d | grid | 网格 | 0.73% | 2.62% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-11.21 | [打开报告](2525_hk/daily/2525_hk_grid_report.md) |
| 港股通沪股票 | 2533.HK | 黑芝麻智能 | 1d | grid | 网格 | -3.04% | 6.21% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=0.00 | [打开报告](2533_hk/daily/2533_hk_grid_report.md) |
| 港股通沪股票 | 2555.HK | 茶百道 | 1d | grid | 网格 | 1.39% | 0.90% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-5.62 | [打开报告](2555_hk/daily/2555_hk_grid_report.md) |
| 港股通沪股票 | **2556.HK** | **迈富时** | 1d | grid | 网格 | **6.28%** | 0.96% | ok | **grid_spacing=6.00% grid_count=7 take_profit=3.00% score=-9.51** | [打开报告](2556_hk/daily/2556_hk_grid_report.md) |
| 港股通沪股票 | 2562.HK | 狮腾控股 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=5 take_profit=3.00% score=-6.40 | [打开报告](2562_hk/daily/2562_hk_grid_report.md) |
| 港股通沪股票 | 2565.HK | 派格生物医药－Ｂ | 1d | grid | 网格 | -6.11% | 12.38% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=0.00 | [打开报告](2565_hk/daily/2565_hk_grid_report.md) |
| 港股通沪股票 | 2570.HK | 重塑能源 | 1d | grid | 网格 | -5.16% | 5.16% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-0.57 | [打开报告](2570_hk/daily/2570_hk_grid_report.md) |
| 港股通沪股票 | 2575.HK | 轩竹生物－Ｂ | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=500, price=63.20 | [打开报告](2575_hk/daily/2575_hk_1d_grid_report.md) |
| 港股通沪股票 | 2577.HK | 英诺赛科 | 1d | grid | 网格 | -6.69% | 7.27% | ok | grid_spacing=7.00% grid_count=4 take_profit=7.00% score=-8.49 | [打开报告](2577_hk/daily/2577_hk_grid_report.md) |
| 港股通沪股票 | 2579.HK | 中伟新材 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=5 take_profit=5.00% score=5.73 | [打开报告](2579_hk/daily/2579_hk_grid_report.md) |
| 港股通沪股票 | 2580.HK | 奥克斯电气 | 1d | grid | 网格 | -4.70% | 5.51% | ok | grid_spacing=4.00% grid_count=7 take_profit=3.00% score=5.18 | [打开报告](2580_hk/daily/2580_hk_grid_report.md) |
| 港股通沪股票 | 2582.HK | 国富氢能 | 1d | grid | 网格 | 3.50% | 0.33% | ok | grid_spacing=5.00% grid_count=5 take_profit=5.00% score=3.82 | [打开报告](2582_hk/daily/2582_hk_grid_report.md) |
| 港股通沪股票 | 2583.HK | 西普尼 | 1d | grid | 网格 | -5.31% | 5.61% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](2583_hk/daily/2583_hk_grid_report.md) |
| 港股通沪股票 | 2586.HK | 多点数智 | 1d | grid | 网格 | -0.52% | 1.00% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-9.72 | [打开报告](2586_hk/daily/2586_hk_grid_report.md) |
| 港股通沪股票 | 2587.HK | 健康之路 | 1d | grid | 网格 | 1.97% | 2.95% | ok | grid_spacing=6.00% grid_count=5 take_profit=3.00% score=-9.06 | [打开报告](2587_hk/daily/2587_hk_grid_report.md) |
| 港股通沪股票 | 2588.HK | 中银航空租赁 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](2588_hk/daily/2588_hk_grid_report.md) |
| 港股通沪股票 | **2589.HK** | **沪上阿姨** | 1d | grid | 网格 | **9.76%** | 3.85% | ok | **grid_spacing=3.00% grid_count=4 take_profit=3.00% score=-4.56** | [打开报告](2589_hk/daily/2589_hk_grid_report.md) |
| 港股通沪股票 | 2590.HK | 极智嘉－Ｗ | 1d | grid | 网格 | -5.58% | 5.58% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=18.24 | [打开报告](2590_hk/daily/2590_hk_grid_report.md) |
| 港股通沪股票 | 2591.HK | 银诺医药－Ｂ | 1d | grid | 网格 | -5.36% | 7.10% | ok | grid_spacing=4.00% grid_count=4 take_profit=5.00% score=-14.13 | [打开报告](2591_hk/daily/2591_hk_grid_report.md) |
| 港股通沪股票 | 2595.HK | 劲方医药－Ｂ | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=7 take_profit=7.00% score=-11.18 | [打开报告](2595_hk/daily/2595_hk_grid_report.md) |
| 港股通沪股票 | 2600.HK | 中国铝业 | 1d | grid | 网格 | 2.65% | 4.40% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=1.81 | [打开报告](2600_hk/daily/2600_hk_grid_report.md) |
| 港股通沪股票 | 2601.HK | 中国太保 | 1d | grid | 网格 | 1.34% | 1.29% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=9.55 | [打开报告](2601_hk/daily/2601_hk_grid_report.md) |
| 港股通沪股票 | 2602.HK | 万物云 | 1d | grid | 网格 | 1.38% | 0.48% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-3.84 | [打开报告](2602_hk/daily/2602_hk_grid_report.md) |
| 港股通沪股票 | 2603.HK | 吉宏股份 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=7 take_profit=7.00% score=-9.77 | [打开报告](2603_hk/daily/2603_hk_grid_report.md) |
| 港股通沪股票 | 2607.HK | 上海医药 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](2607_hk/daily/2607_hk_grid_report.md) |
| 港股通沪股票 | 2609.HK | 佰泽医疗 | 1d | grid | 网格 | -7.28% | 7.28% | ok | grid_spacing=4.00% grid_count=6 take_profit=7.00% score=-1.16 | [打开报告](2609_hk/daily/2609_hk_grid_report.md) |
| 港股通沪股票 | 2610.HK | 南山铝业国际 | 1d | grid | 网格 | -12.29% | 14.62% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=10.52 | [打开报告](2610_hk/daily/2610_hk_grid_report.md) |
| 港股通沪股票 | 2611.HK | 国泰海通 | 1d | grid | 网格 | -6.14% | 6.14% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=4.40 | [打开报告](2611_hk/daily/2611_hk_grid_report.md) |
| 港股通沪股票 | 2617.HK | 药捷安康－Ｂ | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=500, price=117.80 | [打开报告](2617_hk/daily/2617_hk_1d_grid_report.md) |
| 港股通沪股票 | **2618.HK** | **京东物流** | 1d | grid | 网格 | **12.13%** | 3.86% | ok | **grid_spacing=4.00% grid_count=4 take_profit=3.00% score=-0.13** | [打开报告](2618_hk/daily/2618_hk_grid_report.md) |
| 港股通沪股票 | 2627.HK | 中慧生物－Ｂ | 1d | grid | 网格 | -6.14% | 7.62% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=-6.86 | [打开报告](2627_hk/daily/2627_hk_grid_report.md) |
| 港股通沪股票 | **2628.HK** | **中国人寿** | 1d | grid | 网格 | **5.87%** | 3.60% | ok | **grid_spacing=3.00% grid_count=5 take_profit=3.00% score=2.41** | [打开报告](2628_hk/daily/2628_hk_grid_report.md) |
| 港股通沪股票 | 2629.HK | MIRXES-B | 1d | grid | 网格 | -8.10% | 9.33% | ok | grid_spacing=5.00% grid_count=6 take_profit=3.00% score=10.44 | [打开报告](2629_hk/daily/2629_hk_grid_report.md) |
| 港股通沪股票 | 2631.HK | 天岳先进 | 1d | grid | 网格 | 4.63% | 2.14% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=0.00 | [打开报告](2631_hk/daily/2631_hk_grid_report.md) |
| 港股通沪股票 | 2635.HK | 诺比侃 | 1d | grid | 网格 | -5.07% | 5.07% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=11.18 | [打开报告](2635_hk/daily/2635_hk_grid_report.md) |
| 港股通沪股票 | 2637.HK | 海西新药 | 1d | grid | 网格 | 2.39% | 0.02% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](2637_hk/daily/2637_hk_grid_report.md) |
| 港股通沪股票 | 2643.HK | 曹操出行 | 1d | grid | 网格 | -4.11% | 5.06% | ok | grid_spacing=5.00% grid_count=7 take_profit=3.00% score=-11.99 | [打开报告](2643_hk/daily/2643_hk_grid_report.md) |
| 港股通沪股票 | 2648.HK | 安井食品 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](2648_hk/daily/2648_hk_grid_report.md) |
| 港股通沪股票 | 2650.HK | 挚达科技 | 1d | grid | 网格 | -5.08% | 5.08% | ok | grid_spacing=5.00% grid_count=7 take_profit=7.00% score=2.78 | [打开报告](2650_hk/daily/2650_hk_grid_report.md) |
| 港股通沪股票 | 2652.HK | 长风药业 | 1d | grid | 网格 | -4.05% | 4.39% | ok | grid_spacing=7.00% grid_count=6 take_profit=3.00% score=0.74 | [打开报告](2652_hk/daily/2652_hk_grid_report.md) |
| 港股通沪股票 | 2655.HK | 果下科技 | 1d | grid | 网格 | -6.42% | 6.42% | ok | grid_spacing=5.00% grid_count=4 take_profit=3.00% score=10.61 | [打开报告](2655_hk/daily/2655_hk_grid_report.md) |
| 港股通沪股票 | 2656.HK | 健康１６０ | 1d | grid | 网格 | -11.60% | 11.60% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](2656_hk/daily/2656_hk_grid_report.md) |
| 港股通沪股票 | 2659.HK | 宝济药业－Ｂ | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](2659_hk/daily/2659_hk_grid_report.md) |
| 港股通沪股票 | 2661.HK | 轻松健康 | 1d | grid | 网格 | -12.30% | 12.30% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](2661_hk/daily/2661_hk_grid_report.md) |
| 港股通沪股票 | 2665.HK | 图达通 | 1d | grid | 网格 | -6.81% | 9.89% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](2665_hk/daily/2665_hk_grid_report.md) |
| 港股通沪股票 | 2666.HK | 环球医疗 | 1d | grid | 网格 | -0.31% | 0.31% | ok | grid_spacing=6.00% grid_count=7 take_profit=3.00% score=0.00 | [打开报告](2666_hk/daily/2666_hk_grid_report.md) |
| 港股通沪股票 | 2669.HK | 中海物业 | 1d | grid | 网格 | -1.56% | 2.48% | ok | grid_spacing=7.00% grid_count=4 take_profit=5.00% score=-0.00 | [打开报告](2669_hk/daily/2669_hk_grid_report.md) |
| 港股通沪股票 | 2676.HK | 纳芯微 | 1d | grid | 网格 | 1.92% | 0.18% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](2676_hk/daily/2676_hk_grid_report.md) |
| 港股通沪股票 | 2685.HK | 量化派 | 1d | grid | 网格 | -8.65% | 9.23% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=7.50 | [打开报告](2685_hk/daily/2685_hk_grid_report.md) |
| 港股通沪股票 | 2687.HK | 卓越睿新 | 1d | grid | 网格 | -2.64% | 5.37% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](2687_hk/daily/2687_hk_grid_report.md) |
| 港股通沪股票 | 2688.HK | 新奥能源 | 1d | grid | 网格 | -2.52% | 3.86% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](2688_hk/daily/2688_hk_grid_report.md) |
| 港股通沪股票 | 2689.HK | 玖龙纸业 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=1.17 | [打开报告](2689_hk/daily/2689_hk_grid_report.md) |
| 港股通沪股票 | 2691.HK | 南华期货股份 | 1d | grid | 网格 | 3.29% | 0.38% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](2691_hk/daily/2691_hk_grid_report.md) |
| 港股通沪股票 | 2692.HK | 兆威机电 | 1d | grid | 网格 | - | - | failed | 样本内区间为空，无法构建样本窗口。 | [打开报告](2692_hk/daily/2692_hk_1d_grid_report.md) |
| 港股通沪股票 | **2698.HK** | **乐舒适** | 1d | grid | 网格 | **8.14%** | 4.86% | ok | **grid_spacing=3.00% grid_count=4 take_profit=3.00% score=8.37** | [打开报告](2698_hk/daily/2698_hk_grid_report.md) |
| 港股通沪股票 | 2701.HK | 国民技术 | 1d | grid | 网格 | - | - | failed | 样本内区间为空，无法构建样本窗口。 | [打开报告](2701_hk/daily/2701_hk_1d_grid_report.md) |
| 港股通沪股票 | 2714.HK | 牧原股份 | 1d | grid | 网格 | - | - | failed | 样本内区间为空，无法构建样本窗口。 | [打开报告](2714_hk/daily/2714_hk_1d_grid_report.md) |
| 港股通沪股票 | 2715.HK | 埃斯顿 | 1d | grid | 网格 | - | - | failed | 样本内区间为空，无法构建样本窗口。 | [打开报告](2715_hk/daily/2715_hk_1d_grid_report.md) |
| 港股通沪股票 | 2727.HK | 上海电气 | 1d | grid | 网格 | 1.69% | 0.70% | ok | grid_spacing=5.00% grid_count=7 take_profit=3.00% score=0.00 | [打开报告](2727_hk/daily/2727_hk_grid_report.md) |
| 港股通沪股票 | 2768.HK | 国恩科技 | 1d | grid | 网格 | - | - | failed | 样本内区间为空，无法构建样本窗口。 | [打开报告](2768_hk/daily/2768_hk_1d_grid_report.md) |
| 港股通沪股票 | 2788.HK | 创新实业 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=4.84 | [打开报告](2788_hk/daily/2788_hk_grid_report.md) |
| 港股通沪股票 | 2799.HK | 中信金融资产 | 1d | grid | 网格 | -2.07% | 3.61% | ok | grid_spacing=7.00% grid_count=7 take_profit=5.00% score=-0.22 | [打开报告](2799_hk/daily/2799_hk_grid_report.md) |
| 港股通沪股票 | 2858.HK | 易鑫集团 | 1d | grid | 网格 | -3.24% | 5.02% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-9.44 | [打开报告](2858_hk/daily/2858_hk_grid_report.md) |
| 港股通沪股票 | 2865.HK | 钧达股份 | 1d | grid | 网格 | 1.78% | 0.02% | ok | grid_spacing=5.00% grid_count=4 take_profit=5.00% score=-11.00 | [打开报告](2865_hk/daily/2865_hk_grid_report.md) |
| 港股通沪股票 | 2866.HK | 中远海发 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=7 take_profit=5.00% score=-0.55 | [打开报告](2866_hk/daily/2866_hk_grid_report.md) |
| 港股通沪股票 | 2869.HK | 绿城服务 | 1d | grid | 网格 | 4.20% | 2.41% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=5.06 | [打开报告](2869_hk/daily/2869_hk_grid_report.md) |
| 港股通沪股票 | 2877.HK | 神威药业 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=3.42 | [打开报告](2877_hk/daily/2877_hk_grid_report.md) |
| 港股通沪股票 | 2880.HK | 辽港股份 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-0.52 | [打开报告](2880_hk/daily/2880_hk_grid_report.md) |
| 港股通沪股票 | 2883.HK | 中海油田服务 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=0.00 | [打开报告](2883_hk/daily/2883_hk_grid_report.md) |
| 港股通沪股票 | 2888.HK | 渣打集团 | 1d | grid | 网格 | -2.94% | 4.61% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=0.00 | [打开报告](2888_hk/daily/2888_hk_grid_report.md) |
| 港股通沪股票 | 2889.HK | 博泰车联 | 1d | grid | 网格 | -4.23% | 8.23% | ok | grid_spacing=5.00% grid_count=4 take_profit=5.00% score=0.00 | [打开报告](2889_hk/daily/2889_hk_grid_report.md) |
| 港股通沪股票 | 2899.HK | 紫金矿业 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=2000, price=26.87 | [打开报告](2899_hk/daily/2899_hk_1d_grid_report.md) |
| 港股通沪股票 | 2940.HK | 经纬天地（旧） | 1d | grid | 网格 | - | - | failed | 样本内区间为空，无法构建样本窗口。 | [打开报告](2940_hk/daily/2940_hk_1d_grid_report.md) |
| 港股通沪股票 | 3200.HK | 大族数控 | 1d | grid | 网格 | - | - | failed | 样本内区间为空，无法构建样本窗口。 | [打开报告](3200_hk/daily/3200_hk_1d_grid_report.md) |
| 港股通沪股票 | 3268.HK | 美格智能 | 1d | grid | 网格 | - | - | failed | 样本内区间为空，无法构建样本窗口。 | [打开报告](3268_hk/daily/3268_hk_1d_grid_report.md) |
| 港股通沪股票 | 3288.HK | 海天味业 | 1d | grid | 网格 | 0.62% | 0.01% | ok | grid_spacing=4.00% grid_count=7 take_profit=3.00% score=0.54 | [打开报告](3288_hk/daily/3288_hk_grid_report.md) |
| 港股通沪股票 | 3296.HK | 华勤技术 | 1d | grid | 网格 | - | - | failed | 样本内区间为空，无法构建样本窗口。 | [打开报告](3296_hk/daily/3296_hk_1d_grid_report.md) |
| 港股通沪股票 | 3306.HK | 江南布衣 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=7 take_profit=7.00% score=1.16 | [打开报告](3306_hk/daily/3306_hk_grid_report.md) |
| 港股通沪股票 | 3311.HK | 中国建筑国际 | 1d | grid | 网格 | 2.99% | 1.05% | ok | grid_spacing=5.00% grid_count=4 take_profit=5.00% score=0.97 | [打开报告](3311_hk/daily/3311_hk_grid_report.md) |
| 港股通沪股票 | 3317.HK | 迅策 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](3317_hk/daily/3317_hk_grid_report.md) |
| 港股通沪股票 | 3320.HK | 华润医药 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-0.04 | [打开报告](3320_hk/daily/3320_hk_grid_report.md) |
| 港股通沪股票 | **3323.HK** | **中国建材** | 1d | grid | 网格 | **6.44%** | 0.91% | ok | **grid_spacing=4.00% grid_count=4 take_profit=5.00% score=3.13** | [打开报告](3323_hk/daily/3323_hk_grid_report.md) |
| 港股通沪股票 | 3328.HK | 交通银行 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=6 take_profit=3.00% score=0.00 | [打开报告](3328_hk/daily/3328_hk_grid_report.md) |
| 港股通沪股票 | 3330.HK | 灵宝黄金 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=0.00 | [打开报告](3330_hk/daily/3330_hk_grid_report.md) |
| 港股通沪股票 | **3339.HK** | **中国龙工** | 1d | grid | 网格 | **8.88%** | 4.71% | ok | **grid_spacing=3.00% grid_count=4 take_profit=5.00% score=0.00** | [打开报告](3339_hk/daily/3339_hk_grid_report.md) |
| 港股通沪股票 | 3347.HK | 泰格医药 | 1d | grid | 网格 | 2.81% | 5.35% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=0.35 | [打开报告](3347_hk/daily/3347_hk_grid_report.md) |
| 港股通沪股票 | 3360.HK | 远东宏信 | 1d | grid | 网格 | 3.42% | 2.30% | ok | grid_spacing=5.00% grid_count=4 take_profit=3.00% score=2.64 | [打开报告](3360_hk/daily/3360_hk_grid_report.md) |
| 港股通沪股票 | 3369.HK | 秦港股份 | 1d | grid | 网格 | -1.78% | 4.01% | ok | grid_spacing=4.00% grid_count=4 take_profit=7.00% score=0.00 | [打开报告](3369_hk/daily/3369_hk_grid_report.md) |
| 港股通沪股票 | 3380.HK | 龙光集团 | 1d | grid | 网格 | -6.60% | 6.60% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](3380_hk/daily/3380_hk_grid_report.md) |
| 港股通沪股票 | 3393.HK | 威胜控股 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=0.00 | [打开报告](3393_hk/daily/3393_hk_grid_report.md) |
| 港股通沪股票 | **3396.HK** | **联想控股** | 1d | grid | 网格 | **9.68%** | 3.16% | ok | **grid_spacing=3.00% grid_count=4 take_profit=7.00% score=-9.21** | [打开报告](3396_hk/daily/3396_hk_grid_report.md) |
| 港股通沪股票 | 3606.HK | 福耀玻璃 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=400, price=72.69 | [打开报告](3606_hk/daily/3606_hk_1d_grid_report.md) |
| 港股通沪股票 | 3613.HK | 同仁堂国药 | 1d | grid | 网格 | -1.54% | 1.69% | ok | grid_spacing=7.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](3613_hk/daily/3613_hk_grid_report.md) |
| 港股通沪股票 | 3618.HK | 重庆农村商业银行 | 1d | grid | 网格 | 3.35% | 0.12% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=2.45 | [打开报告](3618_hk/daily/3618_hk_grid_report.md) |
| 港股通沪股票 | **3633.HK** | **中裕能源** | 1d | grid | 网格 | **6.53%** | 0.56% | ok | **grid_spacing=4.00% grid_count=4 take_profit=5.00% score=-10.16** | [打开报告](3633_hk/daily/3633_hk_grid_report.md) |
| 港股通沪股票 | 3668.HK | 兖煤澳大利亚 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=4 take_profit=7.00% score=3.43 | [打开报告](3668_hk/daily/3668_hk_grid_report.md) |
| 港股通沪股票 | 3677.HK | 正力新能 | 1d | grid | 网格 | 1.59% | 0.75% | ok | grid_spacing=6.00% grid_count=7 take_profit=5.00% score=-1.41 | [打开报告](3677_hk/daily/3677_hk_grid_report.md) |
| 港股通沪股票 | 3678.HK | 弘业期货 | 1d | grid | 网格 | -2.06% | 3.76% | ok | grid_spacing=7.00% grid_count=4 take_profit=7.00% score=-12.28 | [打开报告](3678_hk/daily/3678_hk_grid_report.md) |
| 港股通沪股票 | 3690.HK | 美团－Ｗ | 1d | grid | 网格 | -6.14% | 7.32% | ok | grid_spacing=4.00% grid_count=4 take_profit=7.00% score=9.02 | [打开报告](3690_hk/daily/3690_hk_grid_report.md) |
| 港股通沪股票 | 3692.HK | 翰森制药 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=2000, price=36.12 | [打开报告](3692_hk/daily/3692_hk_1d_grid_report.md) |
| 港股通沪股票 | 3696.HK | 英矽智能 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](3696_hk/daily/3696_hk_grid_report.md) |
| 港股通沪股票 | 3698.HK | 徽商银行 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=7 take_profit=7.00% score=0.63 | [打开报告](3698_hk/daily/3698_hk_grid_report.md) |
| 港股通沪股票 | 3738.HK | 阜博集团 | 1d | grid | 网格 | -1.23% | 4.78% | ok | grid_spacing=7.00% grid_count=4 take_profit=3.00% score=0.70 | [打开报告](3738_hk/daily/3738_hk_grid_report.md) |
| 港股通沪股票 | 3750.HK | 宁德时代 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=100, price=540.68 | [打开报告](3750_hk/daily/3750_hk_1d_grid_report.md) |
| 港股通沪股票 | **3759.HK** | **康龙化成** | 1d | grid | 网格 | **12.46%** | 2.36% | ok | **grid_spacing=3.00% grid_count=4 take_profit=5.00% score=-1.26** | [打开报告](3759_hk/daily/3759_hk_grid_report.md) |
| 港股通沪股票 | 3800.HK | 协鑫科技 | 1d | grid | 网格 | -1.64% | 8.25% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=-9.53 | [打开报告](3800_hk/daily/3800_hk_grid_report.md) |
| 港股通沪股票 | 3808.HK | 中国重汽 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=1.56 | [打开报告](3808_hk/daily/3808_hk_grid_report.md) |
| 港股通沪股票 | 3858.HK | 佳鑫国际资源 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=5 take_profit=7.00% score=14.51 | [打开报告](3858_hk/daily/3858_hk_grid_report.md) |
| 港股通沪股票 | 3866.HK | 青岛银行 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=5.00% grid_count=4 take_profit=3.00% score=-0.68 | [打开报告](3866_hk/daily/3866_hk_grid_report.md) |
| 港股通沪股票 | 3868.HK | 信义能源 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=7 take_profit=3.00% score=-2.08 | [打开报告](3868_hk/daily/3868_hk_grid_report.md) |
| 港股通沪股票 | 3877.HK | 中国船舶租赁 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](3877_hk/daily/3877_hk_grid_report.md) |
| 港股通沪股票 | **3881.HK** | **希迪智驾** | 1d | grid | 网格 | **12.84%** | 0.84% | ok | **grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00** | [打开报告](3881_hk/daily/3881_hk_grid_report.md) |
| 港股通沪股票 | 3888.HK | 金山软件 | 1d | grid | 网格 | -3.05% | 3.53% | ok | grid_spacing=7.00% grid_count=7 take_profit=5.00% score=-1.18 | [打开报告](3888_hk/daily/3888_hk_grid_report.md) |
| 港股通沪股票 | 3896.HK | 金山云 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=5 take_profit=7.00% score=-8.05 | [打开报告](3896_hk/daily/3896_hk_grid_report.md) |
| 港股通沪股票 | **3898.HK** | **时代电气** | 1d | grid | 网格 | **9.61%** | 1.41% | ok | **grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00** | [打开报告](3898_hk/daily/3898_hk_grid_report.md) |
| 港股通沪股票 | 3899.HK | 中集安瑞科 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=4 take_profit=5.00% score=0.00 | [打开报告](3899_hk/daily/3899_hk_grid_report.md) |
| 港股通沪股票 | 3900.HK | 绿城中国 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=7 take_profit=3.00% score=1.18 | [打开报告](3900_hk/daily/3900_hk_grid_report.md) |
| 港股通沪股票 | 3908.HK | 中金公司 | 1d | grid | 网格 | -5.52% | 5.52% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=2.39 | [打开报告](3908_hk/daily/3908_hk_grid_report.md) |
| 港股通沪股票 | 3918.HK | 金界控股 | 1d | grid | 网格 | 0.51% | 1.73% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-0.37 | [打开报告](3918_hk/daily/3918_hk_grid_report.md) |
| 港股通沪股票 | 3931.HK | 中创新航 | 1d | grid | 网格 | 1.06% | 0.17% | ok | grid_spacing=5.00% grid_count=7 take_profit=3.00% score=0.00 | [打开报告](3931_hk/daily/3931_hk_grid_report.md) |
| 港股通沪股票 | 3933.HK | 联邦制药 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=2000, price=16.25 | [打开报告](3933_hk/daily/3933_hk_1d_grid_report.md) |
| 港股通沪股票 | 3939.HK | 万国黄金集团 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=7 take_profit=3.00% score=5.20 | [打开报告](3939_hk/daily/3939_hk_grid_report.md) |
| 港股通沪股票 | 3958.HK | 东方证券 | 1d | grid | 网格 | -4.37% | 5.12% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](3958_hk/daily/3958_hk_grid_report.md) |
| 港股通沪股票 | 3968.HK | 招商银行 | 1d | grid | 网格 | -1.57% | 2.62% | ok | grid_spacing=4.00% grid_count=4 take_profit=7.00% score=2.23 | [打开报告](3968_hk/daily/3968_hk_grid_report.md) |
| 港股通沪股票 | 3969.HK | 中国通号 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=5.00% grid_count=4 take_profit=7.00% score=0.00 | [打开报告](3969_hk/daily/3969_hk_grid_report.md) |
| 港股通沪股票 | 3986.HK | 兆易创新 | 1d | grid | 网格 | - | - | failed | 样本内区间为空，无法构建样本窗口。 | [打开报告](3986_hk/daily/3986_hk_1d_grid_report.md) |
| 港股通沪股票 | 3988.HK | 中国银行 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](3988_hk/daily/3988_hk_grid_report.md) |
| 港股通沪股票 | 3993.HK | 洛阳钼业 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=3000, price=16.35 | [打开报告](3993_hk/daily/3993_hk_1d_grid_report.md) |
| 港股通沪股票 | 3996.HK | 中国能源建设 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-0.78 | [打开报告](3996_hk/daily/3996_hk_grid_report.md) |
| 港股通沪股票 | 3998.HK | 波司登 | 1d | grid | 网格 | 1.19% | 0.77% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=0.00 | [打开报告](3998_hk/daily/3998_hk_grid_report.md) |
| 港股通沪股票 | 6030.HK | 中信证券 | 1d | grid | 网格 | -4.98% | 5.24% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=6.40 | [打开报告](6030_hk/daily/6030_hk_grid_report.md) |
| 港股通沪股票 | **6031.HK** | **三一重工** | 1d | grid | 网格 | **6.83%** | 1.63% | ok | **grid_spacing=3.00% grid_count=4 take_profit=5.00% score=3.61** | [打开报告](6031_hk/daily/6031_hk_grid_report.md) |
| 港股通沪股票 | 6049.HK | 保利物业 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-0.27 | [打开报告](6049_hk/daily/6049_hk_grid_report.md) |
| 港股通沪股票 | 6055.HK | 中烟香港 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=1000, price=42.30 | [打开报告](6055_hk/daily/6055_hk_1d_grid_report.md) |
| 港股通沪股票 | 6060.HK | 众安在线 | 1d | grid | 网格 | -3.81% | 4.30% | ok | grid_spacing=5.00% grid_count=7 take_profit=3.00% score=-11.09 | [打开报告](6060_hk/daily/6060_hk_grid_report.md) |
| 港股通沪股票 | 6066.HK | 中信建投证券 | 1d | grid | 网格 | 0.56% | 4.77% | ok | grid_spacing=7.00% grid_count=4 take_profit=7.00% score=2.10 | [打开报告](6066_hk/daily/6066_hk_grid_report.md) |
| 港股通沪股票 | 6069.HK | 盛业 | 1d | grid | 网格 | -4.60% | 6.64% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=12.83 | [打开报告](6069_hk/daily/6069_hk_grid_report.md) |
| 港股通沪股票 | 6078.HK | 海吉亚医疗 | 1d | grid | 网格 | -0.53% | 2.69% | ok | grid_spacing=7.00% grid_count=4 take_profit=7.00% score=-10.43 | [打开报告](6078_hk/daily/6078_hk_grid_report.md) |
| 港股通沪股票 | **6088.HK** | **FIT HON TENG** | 1d | grid | 网格 | **7.82%** | 2.94% | ok | **grid_spacing=3.00% grid_count=6 take_profit=7.00% score=3.98** | [打开报告](6088_hk/daily/6088_hk_grid_report.md) |
| 港股通沪股票 | 6090.HK | 不同集团 | 1d | grid | 网格 | -6.10% | 6.31% | ok | grid_spacing=6.00% grid_count=7 take_profit=3.00% score=2.12 | [打开报告](6090_hk/daily/6090_hk_grid_report.md) |
| 港股通沪股票 | 6098.HK | 碧桂园服务 | 1d | grid | 网格 | 2.24% | 0.02% | ok | grid_spacing=4.00% grid_count=4 take_profit=5.00% score=2.87 | [打开报告](6098_hk/daily/6098_hk_grid_report.md) |
| 港股通沪股票 | **6099.HK** | **招商证券** | 1d | grid | 网格 | **8.55%** | 2.33% | ok | **grid_spacing=3.00% grid_count=4 take_profit=5.00% score=-4.90** | [打开报告](6099_hk/daily/6099_hk_grid_report.md) |
| 港股通沪股票 | 6110.HK | 滔搏 | 1d | grid | 网格 | 1.85% | 0.55% | ok | grid_spacing=6.00% grid_count=7 take_profit=7.00% score=0.01 | [打开报告](6110_hk/daily/6110_hk_grid_report.md) |
| 港股通沪股票 | 6127.HK | 昭衍新药 | 1d | grid | 网格 | -5.14% | 8.05% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=-0.79 | [打开报告](6127_hk/daily/6127_hk_grid_report.md) |
| 港股通沪股票 | 6160.HK | 百济神州 | 1d | grid | 网格 | 1.40% | 1.29% | ok | grid_spacing=7.00% grid_count=5 take_profit=3.00% score=0.73 | [打开报告](6160_hk/daily/6160_hk_grid_report.md) |
| 港股通沪股票 | 6166.HK | 剑桥科技 | 1d | grid | 网格 | -2.18% | 5.96% | ok | grid_spacing=4.00% grid_count=4 take_profit=5.00% score=24.72 | [打开报告](6166_hk/daily/6166_hk_grid_report.md) |
| 港股通沪股票 | 6168.HK | 周六福 | 1d | grid | 网格 | -5.61% | 6.78% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=-0.55 | [打开报告](6168_hk/daily/6168_hk_grid_report.md) |
| 港股通沪股票 | 6178.HK | 光大证券 | 1d | grid | 网格 | 0.84% | 1.16% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-0.82 | [打开报告](6178_hk/daily/6178_hk_grid_report.md) |
| 港股通沪股票 | 6181.HK | 老铺黄金 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=100, price=717.16 | [打开报告](6181_hk/daily/6181_hk_1d_grid_report.md) |
| 港股通沪股票 | 6185.HK | 康希诺生物 | 1d | grid | 网格 | -0.65% | 2.53% | ok | grid_spacing=7.00% grid_count=7 take_profit=5.00% score=-4.62 | [打开报告](6185_hk/daily/6185_hk_grid_report.md) |
| 港股通沪股票 | 6186.HK | 中国飞鹤 | 1d | grid | 网格 | -2.35% | 3.02% | ok | grid_spacing=7.00% grid_count=7 take_profit=7.00% score=1.05 | [打开报告](6186_hk/daily/6186_hk_grid_report.md) |
| 港股通沪股票 | 6196.HK | 郑州银行 | 1d | grid | 网格 | 0.50% | 2.14% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=-5.26 | [打开报告](6196_hk/daily/6196_hk_grid_report.md) |
| 港股通沪股票 | 6198.HK | 青岛港 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](6198_hk/daily/6198_hk_grid_report.md) |
| 港股通沪股票 | 6600.HK | 卧安机器人 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](6600_hk/daily/6600_hk_grid_report.md) |
| 港股通沪股票 | 6603.HK | IFBH | 1d | grid | 网格 | -5.61% | 6.05% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-11.30 | [打开报告](6603_hk/daily/6603_hk_grid_report.md) |
| 港股通沪股票 | 6613.HK | 蓝思科技 | 1d | grid | 网格 | -5.99% | 7.46% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=9.60 | [打开报告](6613_hk/daily/6613_hk_grid_report.md) |
| 港股通沪股票 | 6618.HK | 京东健康 | 1d | grid | 网格 | -2.50% | 4.42% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=0.59 | [打开报告](6618_hk/daily/6618_hk_grid_report.md) |
| 港股通沪股票 | 6651.HK | 五一视界 | 1d | grid | 网格 | 1.02% | 0.02% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](6651_hk/daily/6651_hk_grid_report.md) |
| 港股通沪股票 | 6655.HK | 华新建材 | 1d | grid | 网格 | -5.43% | 10.13% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=0.00 | [打开报告](6655_hk/daily/6655_hk_grid_report.md) |
| 港股通沪股票 | 6666.HK | 恒大物业 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](6666_hk/daily/6666_hk_grid_report.md) |
| 港股通沪股票 | 6680.HK | 金力永磁 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=5.00% grid_count=5 take_profit=5.00% score=-0.25 | [打开报告](6680_hk/daily/6680_hk_grid_report.md) |
| 港股通沪股票 | 6681.HK | 脑动极光－Ｂ | 1d | grid | 网格 | -6.24% | 6.24% | ok | grid_spacing=7.00% grid_count=7 take_profit=7.00% score=0.00 | [打开报告](6681_hk/daily/6681_hk_grid_report.md) |
| 港股通沪股票 | 6682.HK | 范式智能 | 1d | grid | 网格 | -4.22% | 5.45% | ok | grid_spacing=6.00% grid_count=4 take_profit=3.00% score=-13.00 | [打开报告](6682_hk/daily/6682_hk_grid_report.md) |
| 港股通沪股票 | 6683.HK | 巨星传奇 | 1d | grid | 网格 | 0.52% | 0.63% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-10.73 | [打开报告](6683_hk/daily/6683_hk_grid_report.md) |
| 港股通沪股票 | 6687.HK | 聚水潭 | 1d | grid | 网格 | -8.60% | 9.54% | ok | grid_spacing=4.00% grid_count=7 take_profit=5.00% score=-10.59 | [打开报告](6687_hk/daily/6687_hk_grid_report.md) |
| 港股通沪股票 | 6690.HK | 海尔智家 | 1d | grid | 网格 | -8.80% | 8.83% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=2.67 | [打开报告](6690_hk/daily/6690_hk_grid_report.md) |
| 港股通沪股票 | 6693.HK | 赤峰黄金 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=6 take_profit=3.00% score=0.00 | [打开报告](6693_hk/daily/6693_hk_grid_report.md) |
| 港股通沪股票 | 6699.HK | 时代天使 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=7.00% grid_count=6 take_profit=5.00% score=-0.66 | [打开报告](6699_hk/daily/6699_hk_grid_report.md) |
| 港股通沪股票 | 6806.HK | 申万宏源 | 1d | grid | 网格 | -5.93% | 6.31% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=-1.38 | [打开报告](6806_hk/daily/6806_hk_grid_report.md) |
| 港股通沪股票 | 6808.HK | 高鑫零售 | 1d | grid | 网格 | 1.20% | 3.24% | ok | grid_spacing=6.00% grid_count=7 take_profit=3.00% score=1.46 | [打开报告](6808_hk/daily/6808_hk_grid_report.md) |
| 港股通沪股票 | 6809.HK | 澜起科技 | 1d | grid | 网格 | - | - | failed | 样本内区间为空，无法构建样本窗口。 | [打开报告](6809_hk/daily/6809_hk_1d_grid_report.md) |
| 港股通沪股票 | 6818.HK | 中国光大银行 | 1d | grid | 网格 | -0.20% | 1.25% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=1.85 | [打开报告](6818_hk/daily/6818_hk_grid_report.md) |
| 港股通沪股票 | 6821.HK | 凯莱英 | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=4 take_profit=7.00% score=-5.00 | [打开报告](6821_hk/daily/6821_hk_grid_report.md) |
| 港股通沪股票 | 6826.HK | 昊海生物科技 | 1d | grid | 网格 | -0.46% | 1.27% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=0.52 | [打开报告](6826_hk/daily/6826_hk_grid_report.md) |
| 港股通沪股票 | 6855.HK | 亚盛医药－Ｂ | 1d | grid | 网格 | -1.06% | 5.25% | ok | grid_spacing=5.00% grid_count=7 take_profit=5.00% score=-9.59 | [打开报告](6855_hk/daily/6855_hk_grid_report.md) |
| 港股通沪股票 | 6862.HK | 海底捞 | 1d | grid | 网格 | 0.92% | 0.05% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=3.82 | [打开报告](6862_hk/daily/6862_hk_grid_report.md) |
| 港股通沪股票 | 6865.HK | 福莱特玻璃 | 1d | grid | 网格 | 0.82% | 1.14% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-0.47 | [打开报告](6865_hk/daily/6865_hk_grid_report.md) |
| 港股通沪股票 | 6869.HK | 长飞光纤光缆 | 1d | grid | 网格 | 2.98% | 0.61% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=-5.54 | [打开报告](6869_hk/daily/6869_hk_grid_report.md) |
| 港股通沪股票 | 6881.HK | 中国银河 | 1d | grid | 网格 | -6.04% | 6.04% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=6.96 | [打开报告](6881_hk/daily/6881_hk_grid_report.md) |
| 港股通沪股票 | 6886.HK | HTSC | 1d | grid | 网格 | -3.32% | 5.21% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=1.66 | [打开报告](6886_hk/daily/6886_hk_grid_report.md) |
| 港股通沪股票 | 6936.HK | 顺丰控股 | 1d | grid | 网格 | -0.02% | 0.02% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-0.49 | [打开报告](6936_hk/daily/6936_hk_grid_report.md) |
| 港股通沪股票 | 6955.HK | 博安生物 | 1d | grid | 网格 | -3.28% | 4.32% | ok | grid_spacing=7.00% grid_count=7 take_profit=7.00% score=-6.35 | [打开报告](6955_hk/daily/6955_hk_grid_report.md) |
| 港股通沪股票 | 6963.HK | 阳光保险 | 1d | grid | 网格 | -1.27% | 4.39% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=10.19 | [打开报告](6963_hk/daily/6963_hk_grid_report.md) |
| 港股通沪股票 | 6969.HK | 思摩尔国际 | 1d | grid | 网格 | 2.32% | 1.55% | ok | grid_spacing=7.00% grid_count=7 take_profit=5.00% score=-7.82 | [打开报告](6969_hk/daily/6969_hk_grid_report.md) |
| 港股通沪股票 | 6979.HK | 珍酒李渡 | 1d | grid | 网格 | 0.93% | 0.73% | ok | grid_spacing=6.00% grid_count=7 take_profit=3.00% score=0.64 | [打开报告](6979_hk/daily/6979_hk_grid_report.md) |
| 港股通沪股票 | 6990.HK | 科伦博泰生物 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=100, price=498.60 | [打开报告](6990_hk/daily/6990_hk_1d_grid_report.md) |
| 港股通沪股票 | 6993.HK | 蓝月亮集团 | 1d | grid | 网格 | 0.93% | 0.01% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-1.50 | [打开报告](6993_hk/daily/6993_hk_grid_report.md) |
| 港股通沪股票 | 7618.HK | 京东工业 | 1d | grid | 网格 | -5.75% | 6.34% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=1.45 | [打开报告](7618_hk/daily/7618_hk_grid_report.md) |
| 港股通沪股票 | 9606.HK | 映恩生物－Ｂ | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=100, price=367.00 | [打开报告](9606_hk/daily/9606_hk_1d_grid_report.md) |
| 港股通沪股票 | 9611.HK | 龙旗科技 | 1d | grid | 网格 | - | - | failed | 样本内区间为空，无法构建样本窗口。 | [打开报告](9611_hk/daily/9611_hk_1d_grid_report.md) |
| 港股通沪股票 | 9626.HK | 哔哩哔哩－Ｗ | 1d | grid | 网格 | 0.41% | 6.39% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=0.00 | [打开报告](9626_hk/daily/9626_hk_grid_report.md) |
| 港股通沪股票 | 9633.HK | 农夫山泉 | 1d | grid | 网格 | 2.60% | 3.46% | ok | grid_spacing=5.00% grid_count=4 take_profit=7.00% score=-0.47 | [打开报告](9633_hk/daily/9633_hk_grid_report.md) |
| 港股通沪股票 | 9636.HK | 九方智投控股 | 1d | grid | 网格 | -6.01% | 6.01% | ok | grid_spacing=6.00% grid_count=5 take_profit=5.00% score=-5.63 | [打开报告](9636_hk/daily/9636_hk_grid_report.md) |
| 港股通沪股票 | 9658.HK | 特海国际 | 1d | grid | 网格 | -1.20% | 2.71% | ok | grid_spacing=6.00% grid_count=7 take_profit=3.00% score=-0.92 | [打开报告](9658_hk/daily/9658_hk_grid_report.md) |
| 港股通沪股票 | 9660.HK | 地平线机器人－Ｗ | 1d | grid | 网格 | -1.95% | 4.87% | ok | grid_spacing=5.00% grid_count=4 take_profit=5.00% score=-4.77 | [打开报告](9660_hk/daily/9660_hk_grid_report.md) |
| 港股通沪股票 | 9678.HK | 云知声 | 1d | grid | 网格 | -5.11% | 5.11% | ok | grid_spacing=7.00% grid_count=6 take_profit=3.00% score=-12.93 | [打开报告](9678_hk/daily/9678_hk_grid_report.md) |
| 港股通沪股票 | 9688.HK | 再鼎医药 | 1d | grid | 网格 | 1.34% | 0.84% | ok | grid_spacing=3.00% grid_count=6 take_profit=3.00% score=-1.82 | [打开报告](9688_hk/daily/9688_hk_grid_report.md) |
| 港股通沪股票 | 9690.HK | 途虎－Ｗ | 1d | grid | 网格 | -5.54% | 6.39% | ok | grid_spacing=7.00% grid_count=4 take_profit=3.00% score=-11.51 | [打开报告](9690_hk/daily/9690_hk_grid_report.md) |
| 港股通沪股票 | 9696.HK | 天齐锂业 | 1d | grid | 网格 | -5.49% | 5.98% | ok | grid_spacing=3.00% grid_count=4 take_profit=7.00% score=0.00 | [打开报告](9696_hk/daily/9696_hk_grid_report.md) |
| 港股通沪股票 | 9699.HK | 顺丰同城 | 1d | grid | 网格 | -2.54% | 2.54% | ok | grid_spacing=7.00% grid_count=7 take_profit=3.00% score=-3.63 | [打开报告](9699_hk/daily/9699_hk_grid_report.md) |
| 港股通沪股票 | 9858.HK | 优然牧业 | 1d | grid | 网格 | 1.75% | 8.73% | ok | grid_spacing=3.00% grid_count=6 take_profit=5.00% score=16.73 | [打开报告](9858_hk/daily/9858_hk_grid_report.md) |
| 港股通沪股票 | 9863.HK | 零跑汽车 | 1d | grid | 网格 | 1.96% | 3.48% | ok | grid_spacing=7.00% grid_count=7 take_profit=7.00% score=-4.68 | [打开报告](9863_hk/daily/9863_hk_grid_report.md) |
| 港股通沪股票 | 9868.HK | 小鹏集团－Ｗ | 1d | grid | 网格 | -3.57% | 5.10% | ok | grid_spacing=4.00% grid_count=4 take_profit=5.00% score=4.32 | [打开报告](9868_hk/daily/9868_hk_grid_report.md) |
| 港股通沪股票 | 9880.HK | 优必选 | 1d | grid | 网格 | -5.78% | 6.96% | ok | grid_spacing=4.00% grid_count=4 take_profit=3.00% score=0.00 | [打开报告](9880_hk/daily/9880_hk_grid_report.md) |
| 港股通沪股票 | 9887.HK | 维立志博－Ｂ | 1d | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=6.00% grid_count=6 take_profit=3.00% score=-7.17 | [打开报告](9887_hk/daily/9887_hk_grid_report.md) |
| 港股通沪股票 | 9890.HK | 贪玩 | 1d | grid | 网格 | -5.63% | 7.75% | ok | grid_spacing=4.00% grid_count=4 take_profit=5.00% score=15.28 | [打开报告](9890_hk/daily/9890_hk_grid_report.md) |
| 港股通沪股票 | 9896.HK | 名创优品 | 1d | grid | 网格 | -4.00% | 4.95% | ok | grid_spacing=5.00% grid_count=7 take_profit=3.00% score=-4.45 | [打开报告](9896_hk/daily/9896_hk_grid_report.md) |
| 港股通沪股票 | 9899.HK | 网易云音乐 | 1d | grid | 网格 | -3.63% | 5.03% | ok | grid_spacing=7.00% grid_count=6 take_profit=3.00% score=-8.35 | [打开报告](9899_hk/daily/9899_hk_grid_report.md) |
| 港股通沪股票 | 9911.HK | 赤子城科技 | 1d | grid | 网格 | -5.11% | 5.28% | ok | grid_spacing=6.00% grid_count=5 take_profit=5.00% score=1.64 | [打开报告](9911_hk/daily/9911_hk_grid_report.md) |
| 港股通沪股票 | 9926.HK | 康方生物 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=1000, price=155.80 | [打开报告](9926_hk/daily/9926_hk_1d_grid_report.md) |
| 港股通沪股票 | 9927.HK | 赛力斯 | 1d | grid | 网格 | -5.87% | 6.12% | ok | grid_spacing=7.00% grid_count=4 take_profit=7.00% score=4.35 | [打开报告](9927_hk/daily/9927_hk_grid_report.md) |
| 港股通沪股票 | 9969.HK | 诺诚健华 | 1d | grid | 网格 | 1.82% | 1.13% | ok | grid_spacing=7.00% grid_count=7 take_profit=5.00% score=-4.36 | [打开报告](9969_hk/daily/9969_hk_grid_report.md) |
| 港股通沪股票 | 9973.HK | 奇瑞汽车 | 1d | grid | 网格 | -4.96% | 5.84% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=3.61 | [打开报告](9973_hk/daily/9973_hk_grid_report.md) |
| 港股通沪股票 | 9980.HK | 东鹏饮料 | 1d | grid | 网格 | - | - | failed | 样本内区间为空，无法构建样本窗口。 | [打开报告](9980_hk/daily/9980_hk_1d_grid_report.md) |
| 港股通沪股票 | 9981.HK | 沃尔核材 | 1d | grid | 网格 | - | - | failed | 样本内区间为空，无法构建样本窗口。 | [打开报告](9981_hk/daily/9981_hk_1d_grid_report.md) |
| 港股通沪股票 | 9985.HK | 卫龙美味 | 1d | grid | 网格 | -5.21% | 6.33% | ok | grid_spacing=3.00% grid_count=4 take_profit=3.00% score=2.65 | [打开报告](9985_hk/daily/9985_hk_grid_report.md) |
| 港股通沪股票 | 9987.HK | 百胜中国 | 1d | grid | 网格 | -0.22% | 0.31% | ok | grid_spacing=5.00% grid_count=4 take_profit=3.00% score=1.72 | [打开报告](9987_hk/daily/9987_hk_grid_report.md) |
| 港股通沪股票 | 9988.HK | 阿里巴巴－Ｗ | 1d | grid | 网格 | -4.26% | 5.89% | ok | grid_spacing=3.00% grid_count=4 take_profit=5.00% score=1.62 | [打开报告](9988_hk/daily/9988_hk_grid_report.md) |
| 港股通沪股票 | 9989.HK | 海普瑞 | 1d | grid | 网格 | -0.22% | 0.98% | ok | grid_spacing=7.00% grid_count=4 take_profit=3.00% score=-0.34 | [打开报告](9989_hk/daily/9989_hk_grid_report.md) |
| 港股通沪股票 | 9992.HK | 泡泡玛特 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=200, price=303.62 | [打开报告](9992_hk/daily/9992_hk_1d_grid_report.md) |
| 港股通沪股票 | 9993.HK | 金辉控股 | 1d | grid | 网格 | -5.96% | 6.44% | ok | grid_spacing=7.00% grid_count=7 take_profit=5.00% score=-7.37 | [打开报告](9993_hk/daily/9993_hk_grid_report.md) |
| 港股通沪股票 | 9995.HK | 荣昌生物 | 1d | grid | 网格 | - | - | failed | 单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size=500, price=96.75 | [打开报告](9995_hk/daily/9995_hk_1d_grid_report.md) |
| 自定义标的 | 1810.HK | 1810.HK | 15m | grid | 网格 | 0.00% | 0.00% | ok | grid_spacing=4.00% grid_count=7 take_profit=1.00% score=-2.43 | [打开报告](1810_hk/minute/1810_hk_15m_grid_report.md) |
