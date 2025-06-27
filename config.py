# config.py

# 投资标的ETF代码
ETF_CODE = "512000"  # 华宝中证全指证券公司ETF

# 数据文件路径，请根据实际情况修改
# 注意：您提供的文件名是 399300 和 399437，但策略要求是 512000。
# 这里暂时使用一个占位符，后续需要您确认使用哪个文件。
# 假设我们使用一个名为 '512000.csv' 的文件，您需要将其放在 data 目录下。
# baostock 没有基金的数据，用证券指数替代
DATA_FILE_PATH = "data/600570_daily_2010-01-01_2025-06-27_20250627_211631.csv"

# 投资参数
TOTAL_CAPITAL = 200000  # 总投资金额
INITIAL_INVESTMENT = 50000  # 初始投资金额
NUM_TOP_UPS = 3  # 后续加仓次数

# 策略退出条件
MAX_HOLDING_YEARS = 1  # 最长持有一年
TARGET_ANNUALIZED_RETURN = 0.10  # 目标年化收益率 10%

# 回测参数
BACKTEST_RUNS = 100  # 随机回测次数
MAX_DROP_PERCENTAGE = 0.10 # 最大回撤百分比

# 日志配置
LOG_DIR = "log"