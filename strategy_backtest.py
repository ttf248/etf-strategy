import pandas as pd
import numpy as np
import os
import random
import matplotlib.pyplot as plt
from loguru import logger

def setup_logging(log_dir='log'):
    """设置日志配置"""
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file = os.path.join(log_dir, 'strategy_backtest_{time:YYYY-MM-DD}.log')

    log_format = "{time:YYYY-MM-DD HH:mm:ss} - {level} - {name}:{function}:{line} - {message}"
    logger.add(log_file, rotation="00:00", retention="30 days", level="DEBUG", format=log_format)

setup_logging()

class StrategyBacktester:
    def __init__(self, initial_capital, total_investment, data_path):
        self.initial_capital = initial_capital
        self.total_investment = total_investment
        self.data = self.load_data(data_path)
        self.trades = []
        self.portfolio_history = []

    def load_data(self, data_path):
        """加载并预处理数据"""
        df = pd.read_csv(data_path)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df.sort_index(inplace=True)
        logger.info(f"数据加载成功，共 {len(df)} 条记录，从 {df.index.min().date()} 到 {df.index.max().date()}.")
        return df

    def run_backtest(self, start_date, down_add_threshold, max_holding_days=547, profit_target_ratio=0.15, annualized_profit_target=0.08, max_drawdown_stop_loss_ratio=0.25, use_stop_loss=False):
        """运行单次回测

        Args:
            start_date (str): 初始建仓日期
            down_add_threshold (float): 下跌加仓阈值 (例如 0.05 for 5%)
            max_holding_days (int): 最大持仓天数
            profit_target_ratio (float): 累计收益率止盈目标
            annualized_profit_target (float): 年化收益率止盈目标
            max_drawdown_stop_loss_ratio (float): 最大回撤止损阈值
            use_stop_loss (bool): 是否启用止损机制
        """
        self.trades = []
        self.portfolio_history = []
        
        data_slice = self.data[self.data.index >= pd.to_datetime(start_date)]
        if data_slice.empty:
            logger.warning(f"指定的开始日期 {start_date} 之后没有数据，无法进行回测。")
            return None, None

        initial_date = data_slice.index[0]
        initial_price = data_slice['close'].iloc[0]

        # 初始化账户
        remaining_add_on_capital = self.total_investment - self.initial_capital
        invested_capital = self.initial_capital
        shares = self.initial_capital / initial_price
        weighted_avg_cost = initial_price
        last_add_on_level = 0 # 用于跟踪下跌加仓的级别

        self._record_trade(initial_date, 'buy', initial_price, shares, self.initial_capital)

        for current_date, row in data_slice.iloc[1:].iterrows():
            current_price = row['close']
            market_value = shares * current_price
            total_portfolio_value = market_value
            cumulative_return_ratio = (total_portfolio_value - invested_capital) / invested_capital if invested_capital > 0 else 0
            holding_days = (current_date - initial_date).days
            annualized_return = ((1 + cumulative_return_ratio) ** (365.0 / holding_days) - 1) if holding_days > 0 else 0

            self._record_portfolio_history(current_date, invested_capital, market_value, cumulative_return_ratio, annualized_return)

            # 检查止盈/止损条件
            exit_reason = self._check_exit_conditions(
                holding_days, max_holding_days, invested_capital, self.total_investment, 
                cumulative_return_ratio, profit_target_ratio, annualized_return, annualized_profit_target,
                use_stop_loss, max_drawdown_stop_loss_ratio
            )
            if exit_reason:
                self._record_trade(current_date, 'sell', current_price, shares, market_value, exit_reason)
                logger.info(f"策略结束于 {current_date.date()}。原因: {exit_reason}")
                break

            # 检查加仓条件
            price_drawdown_ratio = (weighted_avg_cost - current_price) / weighted_avg_cost
            
            # 核心加仓逻辑：当价格下跌超过阈值时加仓
            if remaining_add_on_capital > 0 and price_drawdown_ratio > down_add_threshold:
                # 简单实现：每次加仓剩余资金的1/3
                # TODO: 可以根据下跌幅度动态调整加仓金额
                add_on_times_left = 3 # 假设剩余资金分3次加完
                if 'add_on_count' not in locals():
                    add_on_count = 0
                
                # 确保至少能加3次
                if add_on_count < add_on_times_left:
                    amount_to_invest = remaining_add_on_capital / (add_on_times_left - add_on_count)
                    if amount_to_invest > remaining_add_on_capital:
                        amount_to_invest = remaining_add_on_capital

                    new_shares = amount_to_invest / current_price
                    
                    # 更新账户状态
                    invested_capital += amount_to_invest
                    remaining_add_on_capital -= amount_to_invest
                    total_cost = (shares * weighted_avg_cost) + (new_shares * current_price)
                    shares += new_shares
                    weighted_avg_cost = total_cost / shares
                    add_on_count += 1

                    self._record_trade(current_date, 'add_on', current_price, new_shares, amount_to_invest)
                    logger.info(f"在 {current_date.date()} 加仓 {amount_to_invest:.2f}元, 当前成本价: {weighted_avg_cost:.3f}")
        
        return self.trades, self.portfolio_history

    def _record_trade(self, date, trade_type, price, shares, amount, reason=''):
        self.trades.append({
            'date': date,
            'type': trade_type,
            'price': price,
            'shares': shares,
            'amount': amount,
            'reason': reason
        })

    def _record_portfolio_history(self, date, invested_capital, market_value, cumulative_return_ratio, annualized_return):
        self.portfolio_history.append({
            'date': date,
            'invested_capital': invested_capital,
            'market_value': market_value,
            'cumulative_return_ratio': cumulative_return_ratio,
            'annualized_return': annualized_return
        })

    def _check_exit_conditions(self, holding_days, max_holding_days, invested_capital, total_investment, cumulative_return_ratio, profit_target_ratio, annualized_return, annualized_profit_target, use_stop_loss, max_drawdown_stop_loss_ratio):
        # 条件四：极端止损
        if use_stop_loss and cumulative_return_ratio <= -max_drawdown_stop_loss_ratio:
            return f"达到最大回撤止损点: {cumulative_return_ratio:.2%}"

        # 条件二：收益率目标达成
        if cumulative_return_ratio >= profit_target_ratio:
            return f"达到累计收益率目标: {cumulative_return_ratio:.2%}"

        all_capital_invested = invested_capital >= total_investment
        # 条件二（备用）
        if all_capital_invested and annualized_return >= annualized_profit_target:
            return f"资金全部投入且达到年化收益率目标: {annualized_return:.2%}"

        # 条件三：最大持仓时间
        if holding_days > max_holding_days:
            if all_capital_invested or cumulative_return_ratio >= 0.08: # 累计收益率达到8%也退出
                return f"达到最大持仓时间 ({holding_days}天) 且满足退出条件"
        
        return None

    def find_optimal_params(self, num_random_starts=100, threshold_range=(0.03, 0.10), threshold_step=0.005):
        """寻找最优参数"""
        results = []
        
        # 确保有足够的数据进行随机抽样
        valid_start_dates = self.data.index[:-max_holding_days] # 保证至少有max_holding_days的后续数据
        if len(valid_start_dates) < num_random_starts:
            logger.warning(f"有效起始日期数量 ({len(valid_start_dates)}) 少于要求的随机次数 ({num_random_starts})。将使用所有有效日期。")
            start_dates = valid_start_dates
        else:
            start_dates = random.sample(list(valid_start_dates), num_random_starts)

        down_add_thresholds = np.arange(threshold_range[0], threshold_range[1] + threshold_step, threshold_step)

        for threshold in down_add_thresholds:
            logger.info(f"--- 开始测试下跌加仓阈值: {threshold:.2%} ---")
            batch_results = []
            for start_date in start_dates:
                trades, history = self.run_backtest(start_date=start_date, down_add_threshold=threshold)
                if trades:
                    final_trade = trades[-1]
                    initial_trade = trades[0]
                    holding_days = (final_trade['date'] - initial_trade['date']).days
                    
                    # 计算最终收益
                    if final_trade['type'] == 'sell':
                        final_value = final_trade['amount']
                    else: # 如果是因为数据结束而停止，则按最后一天的市价计算
                        last_day_price = self.data.loc[final_trade['date']]['close']
                        final_value = final_trade['shares'] * last_day_price
                    
                    total_invested = sum(t['amount'] for t in trades if t['type'] in ['buy', 'add_on'])
                    cumulative_return = (final_value - total_invested) / total_invested
                    annualized_return = ((1 + cumulative_return) ** (365.0 / holding_days) - 1) if holding_days > 0 else 0

                    batch_results.append({
                        'start_date': start_date,
                        'threshold': threshold,
                        'holding_days': holding_days,
                        'cumulative_return': cumulative_return,
                        'annualized_return': annualized_return,
                        'exit_reason': final_trade.get('reason', 'Data End')
                    })
            
            if batch_results:
                avg_annualized_return = np.mean([r['annualized_return'] for r in batch_results])
                avg_holding_days = np.mean([r['holding_days'] for r in batch_results])
                success_rate = len([r for r in batch_results if r['cumulative_return'] > 0]) / len(batch_results)
                
                results.append({
                    'threshold': threshold,
                    'avg_annualized_return': avg_annualized_return,
                    'avg_holding_days': avg_holding_days,
                    'success_rate': success_rate
                })
                logger.info(f"阈值 {threshold:.2%}: 平均年化收益率={avg_annualized_return:.2%}, 平均持仓天数={avg_holding_days:.1f}, 成功率={success_rate:.2%}")

        if not results:
            logger.error("参数寻优未能产生任何结果。")
            return None

        results_df = pd.DataFrame(results)
        optimal_params = results_df.loc[results_df['avg_annualized_return'].idxmax()]
        logger.info(f"\n*** 最优参数寻优结果 ***")
        logger.info(f"最优下跌加仓阈值: {optimal_params['threshold']:.2%}")
        logger.info(f"对应平均年化收益率: {optimal_params['avg_annualized_return']:.2%}")
        logger.info(f"对应平均持仓天数: {optimal_params['avg_holding_days']:.1f}")
        logger.info(f"对应成功率: {optimal_params['success_rate']:.2%}")
        
        return results_df

    def plot_results(self, trades, portfolio_history, title='Strategy Backtest Results'):
        """绘制回测结果图表"""
        if not trades or not portfolio_history:
            logger.warning("没有交易或历史记录可供绘制。")
            return

        trades_df = pd.DataFrame(trades).set_index('date')
        history_df = pd.DataFrame(portfolio_history).set_index('date')

        fig, ax1 = plt.subplots(figsize=(16, 9))
        fig.suptitle(title, fontsize=16)

        # 1. 股价 & 交易点
        start_date, end_date = history_df.index.min(), history_df.index.max()
        price_data = self.data.loc[start_date:end_date]['close']
        ax1.plot(price_data.index, price_data, label='ETF Close Price', color='gray', alpha=0.7)
        
        buy_points = trades_df[trades_df['type'] == 'buy']
        add_on_points = trades_df[trades_df['type'] == 'add_on']
        sell_points = trades_df[trades_df['type'] == 'sell']

        ax1.scatter(buy_points.index, buy_points['price'], marker='^', color='red', s=150, label='Initial Buy', zorder=5)
        ax1.scatter(add_on_points.index, add_on_points['price'], marker='^', color='orange', s=100, label='Add-on', zorder=5)
        if not sell_points.empty:
            ax1.scatter(sell_points.index, sell_points['price'], marker='v', color='green', s=150, label=f"Sell ({sell_points['reason'].iloc[0]})", zorder=5)

        ax1.set_xlabel('Date')
        ax1.set_ylabel('Price', color='black')
        ax1.tick_params(axis='y', labelcolor='black')

        # 2. 累计投入资金
        ax2 = ax1.twinx()
        ax2.plot(history_df.index, history_df['invested_capital'], 'b--', label='Invested Capital')
        ax2.set_ylabel('Invested Capital (CNY)', color='blue')
        ax2.tick_params(axis='y', labelcolor='blue')

        # 3. 收益率曲线 (在第三个Y轴)
        ax3 = ax1.twinx()
        ax3.spines['right'].set_position(('outward', 60))
        ax3.plot(history_df.index, history_df['cumulative_return_ratio'] * 100, 'g-.', label='Cumulative Return')
        ax3.plot(history_df.index, history_df['annualized_return'] * 100, 'm:', label='Annualized Return')
        ax3.set_ylabel('Return Rate (%)', color='green')
        ax3.tick_params(axis='y', labelcolor='green')
        ax3.axhline(0, color='grey', linestyle='--', linewidth=0.8)

        # 图例合并
        lines, labels = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        lines3, labels3 = ax3.get_legend_handles_labels()
        ax3.legend(lines + lines2 + lines3, labels + labels2 + labels3, loc='upper left')

        fig.tight_layout()
        plt.show()

if __name__ == '__main__':
    # --- 参数配置 ---
    DATA_FILE = 'data/600570_daily_2010-01-01_2025-06-27_20250627_211631.csv'
    INITIAL_CAPITAL = 50000
    TOTAL_INVESTMENT = 200000
    # 从2020年开始回测，以覆盖更多市场周期
    TEST_START_DATE = '2020-01-02' 
    # 使用一个较为常见的阈值进行单次回测展示
    TEST_THRESHOLD = 0.07 
    # 全局最大持仓天数，用于参数寻优时的数据有效性判断
    max_holding_days = 547

    # --- 初始化回测器 ---
    if not os.path.exists(DATA_FILE):
        logger.error(f"数据文件不存在: {DATA_FILE}")
        logger.error("请先运行 baostock_download.py 下载数据，或检查文件路径。")
    else:
        backtester = StrategyBacktester(
            initial_capital=INITIAL_CAPITAL,
            total_investment=TOTAL_INVESTMENT,
            data_path=DATA_FILE
        )

        # --- 模式一：运行单次回测并绘图（默认启用） ---
        # logger.info(f"--- 开始单次回测 --- ")
        # logger.info(f"初始建仓日期: {TEST_START_DATE}, 下跌加仓阈值: {TEST_THRESHOLD:.2%}")
        # trades, portfolio_history = backtester.run_backtest(
        #     start_date=TEST_START_DATE, 
        #     down_add_threshold=TEST_THRESHOLD,
        #     max_holding_days=max_holding_days
        # )

        # if trades and portfolio_history:
        #     backtester.plot_results(
        #         trades, 
        #         portfolio_history, 
        #         title=f'Backtest starting {TEST_START_DATE} with {TEST_THRESHOLD:.2%} Threshold'
        #     )
        # else:
        #     logger.warning("单次回测未能生成有效结果，无法绘图。")

        # --- 模式二：寻找最优参数（默认关闭，取消注释以运行） ---
        logger.info("\n--- 开始进行参数寻优 --- ")
        # 注意：这将需要几分钟时间来完成100次随机启动的回测
        optimal_results_df = backtester.find_optimal_params(
            num_random_starts=100, 
            threshold_range=(0.03, 0.10), 
            threshold_step=0.005
        )
        if optimal_results_df is not None:
            print("\n参数寻优结果汇总:")
            print(optimal_results_df)