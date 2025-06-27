# main.py

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import random
from datetime import datetime, timedelta
from loguru import logger

import config

def setup_logging():
    """设置日志配置"""
    if not os.path.exists(config.LOG_DIR):
        os.makedirs(config.LOG_DIR)
    
    log_file = os.path.join(config.LOG_DIR, 'strategy_backtest_{time:YYYY-MM-DD}.log')
    
    log_format = "{time:YYYY-MM-DD HH:mm:ss} - {level} - {name}:{function}:{line} - {message}"
    logger.add(log_file, rotation="00:00", retention="30 days", level="INFO", format=log_format)
    logger.info("日志系统初始化完成")

def load_data(file_path):
    """加载并预处理ETF数据"""
    try:
        df = pd.read_csv(file_path)
        logger.info(f"成功从 {file_path} 加载数据，共 {len(df)} 条记录")
        
        # --- 数据清洗和预处理 ---
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # 根据用户要求，筛选最近五年的数据
        five_years_ago = datetime.now() - timedelta(days=5*365)
        df = df[df.index >= five_years_ago]
        
        # 确保数据按时间升序排列
        df.sort_index(inplace=True)
        
        # 只需要收盘价
        df = df[['close']]
        
        logger.info(f"数据预处理完成，筛选最近五年数据后，剩余 {len(df)} 条记录")
        return df
    except FileNotFoundError:
        logger.error(f"数据文件未找到: {file_path}")
        return None

def run_backtest_simulation(df, start_date, drop_percentage):
    """执行单次回测模拟"""
    # 找到实际的交易开始日期
    trading_days = df[df.index >= start_date]
    if len(trading_days) < 20: # 如果剩余交易日太少，无法进行有意义的回测
        return None

    # 初始化投资组合
    capital_to_invest = config.TOTAL_CAPITAL - config.INITIAL_INVESTMENT
    top_up_amount = capital_to_invest / config.NUM_TOP_UPS
    top_ups_left = config.NUM_TOP_UPS

    # 初始投资
    first_day_price = trading_days.iloc[0]['close']
    shares = config.INITIAL_INVESTMENT / first_day_price
    total_investment = config.INITIAL_INVESTMENT
    avg_cost = first_day_price

    # 记录交易历史
    history = []
    history.append({
        'date': trading_days.index[0],
        'action': 'BUY',
        'price': first_day_price,
        'shares_traded': shares,
        'total_shares': shares,
        'total_investment': total_investment,
        'avg_cost': avg_cost,
        'cumulative_return': 0,
        'annualized_return': 0
    })

    # 开始模拟
    for i in range(1, len(trading_days)):
        current_date = trading_days.index[i]
        current_price = trading_days.iloc[i]['close']
        
        # 检查是否需要加仓
        if top_ups_left > 0 and current_price < avg_cost * (1 - drop_percentage):
            shares_to_buy = top_up_amount / current_price
            shares += shares_to_buy
            total_investment += top_up_amount
            avg_cost = total_investment / shares
            top_ups_left -= 1
            
            history.append({
                'date': current_date,
                'action': 'TOP-UP',
                'price': current_price,
                'shares_traded': shares_to_buy,
                'total_shares': shares,
                'total_investment': total_investment,
                'avg_cost': avg_cost
            })
            logger.info(f"{current_date}: 价格下跌超过 {drop_percentage:.2%}，加仓 {top_up_amount:.2f}")

        # 计算当前收益
        current_value = shares * current_price
        cumulative_return = (current_value - total_investment) / total_investment
        
        holding_days = (current_date - history[0]['date']).days + 1
        annualized_return = cumulative_return * (365.0 / holding_days) if holding_days > 0 else 0
        
        # 更新最后一条记录的收益率
        history[-1]['cumulative_return'] = cumulative_return
        history[-1]['annualized_return'] = annualized_return

        # 检查退出条件
        exit_reason = None
        if holding_days >= config.MAX_HOLDING_YEARS * 365:
            exit_reason = f"持有满 {config.MAX_HOLDING_YEARS} 年"
        elif annualized_return >= config.TARGET_ANNUALIZED_RETURN:
            exit_reason = f"年化收益率达到 {config.TARGET_ANNUALIZED_RETURN:.2%}"
        elif top_ups_left == 0 and i == len(trading_days) - 1: # 资金用完且到数据末尾
            exit_reason = "资金全部投入且已到数据末尾"

        if exit_reason:
            logger.info(f"{current_date}: 满足退出条件: {exit_reason}。最终年化收益率: {annualized_return:.2%}")
            return {
                'start_date': start_date,
                'end_date': current_date,
                'holding_days': holding_days,
                'final_annualized_return': annualized_return,
                'history': history
            }

    # 如果循环结束仍未退出（例如数据不足一年）
    return {
        'start_date': start_date,
        'end_date': trading_days.index[-1],
        'holding_days': (trading_days.index[-1] - history[0]['date']).days + 1,
        'final_annualized_return': annualized_return,
        'history': history
    }

def find_optimal_drop_percentage(df):
    """通过多次回测找到最优的下跌加仓百分比"""
    logger.info("开始寻找最优加仓百分比...")
    
    # 我们将测试从 1% 到 20% 的所有下跌百分比
    drop_percentages = np.arange(0.01, 0.21, 0.01)
    results = []

    # 获取所有可能的开始日期
    possible_start_dates = df.index[:-20] # 保证至少有20天的交易期

    for perc in drop_percentages:
        annual_returns = []
        for _ in range(config.BACKTEST_RUNS):
            # 随机选择一个开始日期
            start_date = random.choice(possible_start_dates)
            simulation_result = run_backtest_simulation(df, start_date, perc)
            if simulation_result:
                annual_returns.append(simulation_result['final_annualized_return'])
        
        if annual_returns:
            avg_return = np.mean(annual_returns)
            results.append({'drop_percentage': perc, 'avg_annualized_return': avg_return})
            logger.info(f"下跌 {perc:.2%} 加仓策略的平均年化收益率: {avg_return:.2%}")

    if not results:
        logger.warning("未能找到任何有效的回测结果。")
        return None

    # 找到最优结果
    optimal_result = max(results, key=lambda x: x['avg_annualized_return'])
    logger.info(f"找到最优加仓百分比: {optimal_result['drop_percentage']:.2%}, 平均年化收益率: {optimal_result['avg_annualized_return']:.2%}")
    
    return optimal_result['drop_percentage']

def plot_simulation_results(df, simulation_result):
    """将单次模拟结果可视化"""
    history_df = pd.DataFrame(simulation_result['history'])
    history_df.set_index('date', inplace=True)

    # 准备绘图数据
    start_date = simulation_result['start_date']
    end_date = simulation_result['end_date']
    plot_df = df[(df.index >= start_date) & (df.index <= end_date)].copy()

    # 创建一个足够大的图表
    fig, ax1 = plt.subplots(figsize=(16, 9))
    fig.suptitle(f"策略回测结果 (最优加仓跌幅: {history_df.index[0].strftime('%Y-%m-%d')} to {history_df.index[-1].strftime('%Y-%m-%d')})", fontsize=16)

    # 坐标轴1: 价格
    ax1.set_xlabel('日期')
    ax1.set_ylabel('价格 (元)', color='tab:blue')
    ax1.plot(plot_df.index, plot_df['close'], label='ETF收盘价', color='tab:blue', alpha=0.7)
    ax1.plot(history_df.index, history_df['avg_cost'], label='平均持仓成本', color='tab:orange', linestyle='--')
    ax1.tick_params(axis='y', labelcolor='tab:blue')

    # 标记买入点
    buy_points = history_df[history_df['action'] == 'BUY']
    ax1.scatter(buy_points.index, buy_points['price'], marker='^', color='red', s=100, label='初始建仓')
    topup_points = history_df[history_df['action'] == 'TOP-UP']
    ax1.scatter(topup_points.index, topup_points['price'], marker='^', color='green', s=100, label='加仓')

    # 坐标轴2: 投入资金
    ax2 = ax1.twinx()
    ax2.set_ylabel('累计投入资金 (元)', color='tab:purple')
    ax2.plot(history_df.index, history_df['total_investment'], label='累计投入资金', color='tab:purple', linestyle=':')
    ax2.tick_params(axis='y', labelcolor='tab:purple')

    # 坐标轴3: 收益率
    ax3 = ax1.twinx()
    ax3.spines['right'].set_position(('outward', 60))
    ax3.set_ylabel('收益率 (%)', color='tab:green')
    ax3.plot(history_df.index, history_df['cumulative_return'] * 100, label='累计收益率', color='tab:green')
    ax3.plot(history_df.index, history_df['annualized_return'] * 100, label='年化收益率', color='tab:red', linestyle='-.')
    ax3.tick_params(axis='y', labelcolor='tab:green')
    ax3.axhline(y=config.TARGET_ANNUALIZED_RETURN * 100, color='grey', linestyle='--', label=f'目标年化收益率 ({config.TARGET_ANNUALIZED_RETURN:.0%})')

    # 图例
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    lines3, labels3 = ax3.get_legend_handles_labels()
    ax3.legend(lines + lines2 + lines3, labels + labels2 + labels3, loc='upper left')

    plt.grid(True)
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    
    # 保存图表
    plot_filename = f"backtest_result_{start_date.strftime('%Y%m%d')}.png"
    plt.savefig(plot_filename)
    logger.info(f"回测结果图表已保存至 {plot_filename}")
    plt.show()

if __name__ == '__main__':
    setup_logging()
    
    # 加载数据
    etf_data = load_data(config.DATA_FILE_PATH)
    
    if etf_data is not None and not etf_data.empty:
        # 1. 找到最优加仓参数
        optimal_percentage = find_optimal_drop_percentage(etf_data)

        if optimal_percentage is not None:
            logger.info(f"\n*** 最优加仓策略已找到 ***")
            logger.info(f"当价格低于平均成本 {optimal_percentage:.2%} 时进行加仓，可以获得最高的历史平均年化收益。")
            logger.info("\n*** 使用最优参数进行一次模拟以供展示 ***")

            # 2. 使用最优参数进行一次回测用于可视化
            # 我们选择一个固定的、较近的开始日期来进行展示，例如两年前
            display_start_date = etf_data.index[-1] - timedelta(days=2*365)
            if display_start_date < etf_data.index[0]:
                display_start_date = etf_data.index[0]
            
            final_simulation = run_backtest_simulation(etf_data, display_start_date, optimal_percentage)

            if final_simulation:
                # 3. 可视化结果
                plot_simulation_results(etf_data, final_simulation)
                logger.info("\n回测与可视化完成！")
            else:
                logger.error("无法使用最优参数完成最终的模拟回测。")
        else:
            logger.error("无法找到最优的加仓百分比，请检查数据和配置。")
    else:
        logger.error("数据加载失败或数据为空，程序退出。")