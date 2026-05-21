import yfinance as yf
import pandas as pd
import os

def download_stock_data(ticker, start_date, end_date):
    """
    下载股票日线数据并保存为日线、月线和年线格式的CSV文件.
    会下载 auto_adjust=True (复权) 和 auto_adjust=False (不复权) 两份数据.
    For strategy trading, common data fields include Open, High, Low, Close, and Volume (OHLCV).
    :param ticker: 股票代码
    :param start_date: 开始日期
    :param end_date: 结束日期
    """
    yf.set_config(proxy="http://127.0.0.1:7897")
    folder_path = 'data'
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    # --- Download and process auto_adjust=True data ---
    data_adj = yf.download(ticker, start=start_date, end=end_date, interval='1d', auto_adjust=True)

    if data_adj.empty:
        print(f"No data found for ticker {ticker} with auto_adjust=True.")
    else:
        if isinstance(data_adj.columns, pd.MultiIndex):
            data_adj.columns = data_adj.columns.droplevel(1)

        ohlcv_adj = data_adj[['Open', 'High', 'Low', 'Close', 'Volume']]

        # Save daily adjusted data
        daily_adj_path = os.path.join(folder_path, f'{ticker}_daily_{start_date}_{end_date}_adj.csv')
        ohlcv_adj.to_csv(daily_adj_path)
        print(f"Daily adjusted data for {ticker} saved to {daily_adj_path}")

        # Resample and save monthly adjusted data
        monthly_adj_data = ohlcv_adj.resample('ME').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
        })
        monthly_adj_path = os.path.join(folder_path, f'{ticker}_monthly_{start_date}_{end_date}_adj.csv')
        monthly_adj_data.to_csv(monthly_adj_path)
        print(f"Monthly adjusted data for {ticker} saved to {monthly_adj_path}")

        # Resample and save yearly adjusted data
        yearly_adj_data = ohlcv_adj.resample('YE').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
        })
        yearly_adj_data['Change'] = (yearly_adj_data['Close'] - yearly_adj_data['Open']) / yearly_adj_data['Open']
        yearly_adj_path = os.path.join(folder_path, f'{ticker}_yearly_{start_date}_{end_date}_adj.csv')
        yearly_adj_data.to_csv(yearly_adj_path)
        print(f"Yearly adjusted data for {ticker} saved to {yearly_adj_path}")

    # --- Download and process auto_adjust=False data ---
    data_raw = yf.download(ticker, start=start_date, end=end_date, interval='1d', auto_adjust=False)

    if data_raw.empty:
        print(f"No data found for ticker {ticker} with auto_adjust=False.")
    else:
        if isinstance(data_raw.columns, pd.MultiIndex):
            data_raw.columns = data_raw.columns.droplevel(1)
        # For auto_adjust=False, columns are 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume'
        ohlcv_raw = data_raw[['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']]

        # Save daily raw data
        daily_raw_path = os.path.join(folder_path, f'{ticker}_daily_{start_date}_{end_date}_raw.csv')
        ohlcv_raw.to_csv(daily_raw_path)
        print(f"Daily raw data for {ticker} saved to {daily_raw_path}")

        # Resample and save monthly raw data
        monthly_raw_data = ohlcv_raw.resample('ME').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Adj Close': 'last', 'Volume': 'sum'
        })
        monthly_raw_path = os.path.join(folder_path, f'{ticker}_monthly_{start_date}_{end_date}_raw.csv')
        monthly_raw_data.to_csv(monthly_raw_path)
        print(f"Monthly raw data for {ticker} saved to {monthly_raw_path}")

        # Resample and save yearly raw data
        yearly_raw_data = ohlcv_raw.resample('YE').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Adj Close': 'last', 'Volume': 'sum'
        })
        # Calculate change based on 'Adj Close' for a more accurate representation of return
        yearly_open = ohlcv_raw['Adj Close'].resample('YE').first()
        yearly_close = ohlcv_raw['Adj Close'].resample('YE').last()
        yearly_raw_data['Change'] = (yearly_close - yearly_open) / yearly_open
        yearly_raw_path = os.path.join(folder_path, f'{ticker}_yearly_{start_date}_{end_date}_raw.csv')
        yearly_raw_data.to_csv(yearly_raw_path)
        print(f"Yearly raw data for {ticker} saved to {yearly_raw_path}")


if __name__ == '__main__':
    # 示例：下载华夏上证50ETF(510050.SS)从2010年到2024年的日线、月线、年线数据
    download_stock_data('510050.SS', '2013-01-01', '2024-12-31')