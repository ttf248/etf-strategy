# 历史股票数据回测

模型： Gemini2.5-pro

## 提示词

中文回复 投资标的物：中国的券商ETF基金，场内交易， 华宝中证全指证券公司ETF，场内代码为 512000

准备进行一个投资计划，初始投资五万，总金额：二十万，初始投资五万，后续的资金，分三次进行加仓

下跌的定义： 当市价低于总平均成本的百分比

用最近五年的收市价数据计算，假如在任意时间点进行建仓，买入初始的五万
下跌多少，进行加仓合适，持有多长时间合适

策略截止条件：

- 二十万本金全部
- 限制最多持有一年 或者 年化收益率超过 10%

任务详情：

1. 思考建立什么样的数学模型合适，我这种方案，有对应的交易策略吗
2. 用Python代码实现你的模型，代码不要立即生成，你先分析方案是否还有优化空间
3. 代码最终是绘制坐标图，我需要在一张图中看到投资时间、当前投入的的资金、加仓的时间点、当前累计收益率、折算的年华收益率
4. 最终的代码需要能支持自行回测，随机抽取 100 个日期进行初始建仓
5. 计算最优的加仓时间，下跌多少加仓是不是固定值，需要基于历史数据回测，帮我算出来最优值
6. 历史数据通过 csv 文件提供

日志相关的代码

```python
def setup_logging(log_dir='log'):
    """设置日志配置"""
    # 日志库默认输出到终端，移除终端的日志，目前保留终端的日志
    # logger.remove()
   
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
   
    log_file = os.path.join(log_dir, 'E2E02_consumer_{time:YYYY-MM-DD}.log')
   
    # 添加日志记录器，按天滚动，并保留30天的日志
    # TODO：日志级别的控制，通过环境变量控制，容器启动脚本注入
    log_format = "{time:YYYY-MM-DD HH:mm:ss} - {level} - {name}:{function}:{line} - {message}"
    logger.add(log_file, rotation="00:00", retention="30 days", level="DEBUG", format=log_format)
```

## 数据源

还没开工，和AI沟通方案，发现了数据源的问题，本来是让腾讯混元给我推荐几个免费白嫖行情数据的库，了解到了不同的复权计算逻辑

[https://ttf248.life/p/where-can-i-find-backtest-data](https://ttf248.life/p/where-can-i-find-backtest-data)

