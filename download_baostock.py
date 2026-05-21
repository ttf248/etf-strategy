import baostock as bs
import pandas as pd
import argparse
import os
from datetime import datetime
from loguru import logger
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

# http://baostock.com/baostock/index.php/A%E8%82%A1K%E7%BA%BF%E6%95%B0%E6%8D%AE

class DataFrequency(Enum):
    """数据频率枚举"""
    DAILY = "d"      # 日线
    WEEKLY = "w"     # 周线
    MONTHLY = "m"    # 月线
    MIN_5 = "5"      # 5分钟线
    MIN_15 = "15"    # 15分钟线
    MIN_30 = "30"    # 30分钟线
    MIN_60 = "60"    # 60分钟线


class AdjustFlag(Enum):
    """复权类型枚举"""
    POST_ADJUST = "1"   # 后复权
    PRE_ADJUST = "2"    # 前复权
    NO_ADJUST = "3"     # 不复权


@dataclass
class DailyWeeklyMonthlyData:
    """日线、周线、月线数据结构（包含停牌证券）"""
    date: str           # 交易所行情日期，格式：YYYY-MM-DD
    code: str           # 证券代码，格式：sh.600000。sh：上海，sz：深圳
    open: float         # 今开盘价格，精度：小数点后4位；单位：人民币元
    high: float         # 最高价，精度：小数点后4位；单位：人民币元
    low: float          # 最低价，精度：小数点后4位；单位：人民币元
    close: float        # 今收盘价，精度：小数点后4位；单位：人民币元
    preclose: float     # 昨日收盘价，精度：小数点后4位；单位：人民币元
    volume: int         # 成交数量，单位：股
    amount: float       # 成交金额，精度：小数点后4位；单位：人民币元
    adjustflag: str     # 复权状态，不复权、前复权、后复权
    turn: Optional[float]  # 换手率，精度：小数点后6位；单位：%
    tradestatus: str    # 交易状态，1：正常交易 0：停牌
    pctChg: float       # 涨跌幅（百分比），精度：小数点后6位
    peTTM: Optional[float]     # 滚动市盈率，精度：小数点后6位
    psTTM: Optional[float]     # 滚动市销率，精度：小数点后6位
    pcfNcfTTM: Optional[float] # 滚动市现率，精度：小数点后6位
    pbMRQ: Optional[float]     # 市净率，精度：小数点后6位
    isST: str           # 是否ST，1是，0否


@dataclass
class MinuteData:
    """分钟线数据结构（5、15、30、60分钟，不包含指数）"""
    date: str           # 交易所行情日期，格式：YYYY-MM-DD
    time: str           # 交易所行情时间，格式：YYYYMMDDHHMMSSsss
    code: str           # 证券代码，格式：sh.600000。sh：上海，sz：深圳
    open: float         # 开盘价格，精度：小数点后4位；单位：人民币元
    high: float         # 最高价，精度：小数点后4位；单位：人民币元
    low: float          # 最低价，精度：小数点后4位；单位：人民币元
    close: float        # 收盘价，精度：小数点后4位；单位：人民币元
    volume: int         # 成交数量，单位：股；时间范围内的累计成交数量
    amount: float       # 成交金额，精度：小数点后4位；单位：人民币元；时间范围内的累计成交金额
    adjustflag: str     # 复权状态，不复权、前复权、后复权


class DataFieldsConfig:
    """数据字段配置类"""
    
    # 日线、周线、月线字段（包含停牌证券）
    DAILY_WEEKLY_MONTHLY_FIELDS = [
        "date",         # 交易所行情日期，格式：YYYY-MM-DD
        "code",         # 证券代码，格式：sh.600000。sh：上海，sz：深圳
        "open",         # 今开盘价格，精度：小数点后4位；单位：人民币元
        "high",         # 最高价，精度：小数点后4位；单位：人民币元
        "low",          # 最低价，精度：小数点后4位；单位：人民币元
        "close",        # 今收盘价，精度：小数点后4位；单位：人民币元
        "preclose",     # 昨日收盘价，精度：小数点后4位；单位：人民币元
        "volume",       # 成交数量，单位：股
        "amount",       # 成交金额，精度：小数点后4位；单位：人民币元
        "adjustflag",   # 复权状态，不复权、前复权、后复权
        "turn",         # 换手率，精度：小数点后6位；单位：%
        "tradestatus",  # 交易状态，1：正常交易 0：停牌
        "pctChg",       # 涨跌幅（百分比），精度：小数点后6位
        "peTTM",        # 滚动市盈率，精度：小数点后6位
        "psTTM",        # 滚动市销率，精度：小数点后6位
        "pcfNcfTTM",    # 滚动市现率，精度：小数点后6位
        "pbMRQ",        # 市净率，精度：小数点后6位
        "isST"          # 是否ST，1是，0否
    ]
    
    # 分钟线字段（5、15、30、60分钟，不包含指数）
    MINUTE_FIELDS = [
        "date",         # 交易所行情日期，格式：YYYY-MM-DD
        "time",         # 交易所行情时间，格式：YYYYMMDDHHMMSSsss
        "code",         # 证券代码，格式：sh.600000。sh：上海，sz：深圳
        "open",         # 开盘价格，精度：小数点后4位；单位：人民币元
        "high",         # 最高价，精度：小数点后4位；单位：人民币元
        "low",          # 最低价，精度：小数点后4位；单位：人民币元
        "close",        # 收盘价，精度：小数点后4位；单位：人民币元
        "volume",       # 成交数量，单位：股；时间范围内的累计成交数量
        "amount",       # 成交金额，精度：小数点后4位；单位：人民币元；时间范围内的累计成交金额
        "adjustflag"    # 复权状态，不复权、前复权、后复权
    ]
    
    @classmethod
    def get_fields_by_frequency(cls, frequency: str) -> List[str]:
        """根据频率获取对应的字段列表"""
        if frequency in ["5", "15", "30", "60"]:
            return cls.MINUTE_FIELDS
        else:
            return cls.DAILY_WEEKLY_MONTHLY_FIELDS
    
    @classmethod
    def get_fields_string(cls, frequency: str) -> str:
        """获取字段字符串，用于API调用"""
        fields = cls.get_fields_by_frequency(frequency)
        return ",".join(fields)


def setup_logging(log_dir='log'):
    """设置日志配置"""
    # 日志库默认输出到终端，移除终端的日志，目前保留终端的日志
    # logger.remove()
    
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, 'download_data_{time:YYYY-MM-DD}.log')
    
    # 添加日志记录器，按天滚动，并保留30天的日志
    log_format = "{time:YYYY-MM-DD HH:mm:ss} - {level} - {name}:{function}:{line} - {message}"
    logger.add(log_file, rotation="00:00", retention="30 days", level="DEBUG", format=log_format)


def download_stock_data(stock_code: str, start_date: str, end_date: str, 
                       frequency: str = "d", adjustflag: str = "2") -> Optional[pd.DataFrame]:
    """下载股票数据
    
    Args:
        stock_code: 股票代码，格式如 sh.600000 或 sz.000001
        start_date: 开始日期，格式 YYYY-MM-DD
        end_date: 结束日期，格式 YYYY-MM-DD
        frequency: 数据频率，支持 d/w/m/5/15/30/60
        adjustflag: 复权类型，1-后复权，2-前复权，3-不复权
    
    Returns:
        pandas.DataFrame: 股票数据，失败时返回None
    """
    logger.info(f"开始下载股票数据: {stock_code}, 时间范围: {start_date} 到 {end_date}, 频率: {frequency}")
    
    # 验证频率参数
    valid_frequencies = [freq.value for freq in DataFrequency]
    if frequency not in valid_frequencies:
        logger.error(f"无效的频率参数: {frequency}, 支持的频率: {valid_frequencies}")
        return None
    
    # 验证复权参数
    valid_adjustflags = [flag.value for flag in AdjustFlag]
    if adjustflag not in valid_adjustflags:
        logger.error(f"无效的复权参数: {adjustflag}, 支持的复权类型: {valid_adjustflags}")
        return None
    
    #### 登陆系统 ####
    lg = bs.login()
    logger.info(f'登录响应 error_code: {lg.error_code}')
    logger.info(f'登录响应 error_msg: {lg.error_msg}')
    
    if lg.error_code != '0':
        logger.error(f"登录失败: {lg.error_msg}")
        return None
    
    try:
        #### 获取沪深A股历史K线数据 ####
        # 根据频率获取对应的字段配置
        fields = DataFieldsConfig.get_fields_string(frequency)
        logger.info(f"使用字段配置: {fields}")
        
        # 分钟线数据不包含指数，需要验证股票代码
        if frequency in ["5", "15", "30", "60"]:
            if not (stock_code.startswith('sh.') or stock_code.startswith('sz.')):
                logger.error(f"分钟线数据不支持指数代码: {stock_code}")
                return None
        
        rs = bs.query_history_k_data_plus(stock_code, fields,
                                         start_date=start_date, end_date=end_date,
                                         frequency=frequency, adjustflag=adjustflag)
        
        logger.info(f'查询响应 error_code: {rs.error_code}')
        logger.info(f'查询响应 error_msg: {rs.error_msg}')
        
        if rs.error_code != '0':
            logger.error(f"查询数据失败: {rs.error_msg}")
            return None
        
        #### 打印结果集 ####
        data_list = []
        while (rs.error_code == '0') & rs.next():
            # 获取一条记录，将记录合并在一起
            data_list.append(rs.get_row_data())
        
        result = pd.DataFrame(data_list, columns=rs.fields)
        logger.info(f"成功获取 {len(result)} 条数据")
        
        # 数据类型转换和验证
        if not result.empty:
            result = validate_and_convert_data(result, frequency)
        
        return result
        
    except Exception as e:
        logger.error(f"下载数据时发生错误: {str(e)}")
        return None
    finally:
        #### 登出系统 ####
        bs.logout()
        logger.info("已登出系统")


def validate_and_convert_data(df: pd.DataFrame, frequency: str) -> pd.DataFrame:
    """验证和转换数据类型
    
    Args:
        df: 原始数据DataFrame
        frequency: 数据频率
    
    Returns:
        转换后的DataFrame
    """
    try:
        # 根据频率确定数据类型
        if frequency in ["5", "15", "30", "60"]:
            # 分钟线数据转换
            numeric_cols = ["open", "high", "low", "close", "volume", "amount"]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
        else:
            # 日线、周线、月线数据转换
            numeric_cols = ["open", "high", "low", "close", "preclose", "volume", "amount", "pctChg"]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 特殊处理可能为空字符串的字段
            optional_numeric_cols = ["turn", "peTTM", "psTTM", "pcfNcfTTM", "pbMRQ"]
            for col in optional_numeric_cols:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: float(x) if x and str(x).strip() else None)
        
        logger.info("数据类型转换成功")
        return df
    
    except Exception as e:
        logger.warning(f"数据类型转换过程中出现警告: {str(e)}")
        return df


def generate_filename(stock_code: str, start_date: str, end_date: str, frequency: str) -> str:
    """生成文件名
    
    Args:
        stock_code: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        frequency: 数据频率
    
    Returns:
        生成的文件名
    """
    # 清理股票代码，移除前缀
    clean_code = stock_code.replace('sh.', '').replace('sz.', '')
    
    # 频率映射
    freq_map = {
        DataFrequency.DAILY.value: 'daily',
        DataFrequency.WEEKLY.value: 'weekly', 
        DataFrequency.MONTHLY.value: 'monthly',
        DataFrequency.MIN_5.value: '5min',
        DataFrequency.MIN_15.value: '15min',
        DataFrequency.MIN_30.value: '30min',
        DataFrequency.MIN_60.value: '60min'
    }
    
    freq_str = freq_map.get(frequency, frequency)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    filename = f"{clean_code}_{freq_str}_{start_date}_{end_date}.csv"
    return filename


def get_data_info(frequency: str) -> str:
    """获取数据类型信息
    
    Args:
        frequency: 数据频率
    
    Returns:
        数据类型描述信息
    """
    if frequency in ["5", "15", "30", "60"]:
        return f"{frequency}分钟线数据（不包含指数）"
    elif frequency == "d":
        return "日线数据（包含停牌证券）"
    elif frequency == "w":
        return "周线数据（包含停牌证券）"
    elif frequency == "m":
        return "月线数据（包含停牌证券）"
    else:
        return "未知数据类型"


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='下载股票历史数据 - 支持日线、周线、月线、分钟线数据',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
数据类型说明:
  日线/周线/月线: 包含停牌证券，字段包括开高低收、前收盘价、成交量额、换手率、交易状态、涨跌幅、ST标识
  分钟线数据: 不包含指数，字段包括开高低收、成交量额、时间信息

示例:
  python baostock_download.py -c sh.600000 -s 2024-01-01 -e 2024-12-31
  python baostock_download.py -c sz.000001 -s 2024-01-01 -e 2024-12-31 -f 5 -a 1
        """
    )
    
    parser.add_argument('--code', '-c', required=True, 
                       help='股票代码，格式: sh.XXXXXX或sz.XXXXXX（分钟线不支持指数）')
    parser.add_argument('--start', '-s', required=True, 
                       help='开始日期，格式: YYYY-MM-DD')
    parser.add_argument('--end', '-e', required=True, 
                       help='结束日期，格式: YYYY-MM-DD')
    parser.add_argument('--frequency', '-f', default=DataFrequency.DAILY.value, 
                       choices=[freq.value for freq in DataFrequency],
                       help='数据频率: d=日线, w=周线, m=月线, 5/15/30/60=分钟线')
    parser.add_argument('--adjustflag', '-a', default=AdjustFlag.PRE_ADJUST.value, 
                       choices=[flag.value for flag in AdjustFlag],
                       help='复权类型: 1=后复权, 2=前复权, 3=不复权')
    parser.add_argument('--output-dir', '-o', default='data', 
                       help='输出目录，默认为data')
    
    args = parser.parse_args()
    
    # 设置日志
    setup_logging()
    
    # 显示下载信息
    data_type_info = get_data_info(args.frequency)
    print(f"\n=== 股票数据下载工具 ===")
    print(f"股票代码: {args.code}")
    print(f"时间范围: {args.start} 至 {args.end}")
    print(f"数据类型: {data_type_info}")
    print(f"复权方式: {AdjustFlag(args.adjustflag).name}")
    print(f"输出目录: {args.output_dir}")
    print("=" * 30)
    
    # 创建输出目录
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
        logger.info(f"创建输出目录: {args.output_dir}")
    
    # 下载数据
    result = download_stock_data(args.code, args.start, args.end, args.frequency, args.adjustflag)
    
    if result is not None and not result.empty:
        # 生成文件名
        filename = generate_filename(args.code, args.start, args.end, args.frequency)
        filepath = os.path.join(args.output_dir, filename)
        
        # 保存到CSV文件
        result.to_csv(filepath, index=False, encoding='utf-8-sig')
        logger.info(f"数据已保存到: {filepath}")
        
        # 显示结果信息
        print(f"\n✅ 数据下载完成！")
        print(f"📊 数据记录数: {len(result)} 条")
        print(f"📁 文件保存路径: {filepath}")
        print(f"📋 数据字段: {', '.join(result.columns.tolist())}")
        
        # 显示数据预览
        print(f"\n📈 数据预览（前5行）:")
        print(result.head().to_string(index=False))
        
        # 显示数据统计信息
        if 'close' in result.columns:
            print(f"\n📊 价格统计信息:")
            close_prices = pd.to_numeric(result['close'], errors='coerce')
            print(f"   最高价: {close_prices.max():.2f}")
            print(f"   最低价: {close_prices.min():.2f}")
            print(f"   平均价: {close_prices.mean():.2f}")
            
    else:
        logger.error("未能获取到有效数据")
        print("\n❌ 数据下载失败，请检查以下项目:")
        print("   1. 网络连接是否正常")
        print("   2. 股票代码格式是否正确")
        print("   3. 日期范围是否合理")
        print("   4. 分钟线数据是否使用了指数代码")


if __name__ == "__main__":
    main()