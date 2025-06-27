import baostock as bs
import pandas as pd
import argparse
import os
from datetime import datetime
from loguru import logger


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


def download_stock_data(stock_code, start_date, end_date, frequency="d", adjustflag="2"):
    """下载股票数据"""
    logger.info(f"开始下载股票数据: {stock_code}, 时间范围: {start_date} 到 {end_date}")
    
    #### 登陆系统 ####
    lg = bs.login()
    logger.info(f'登录响应 error_code: {lg.error_code}')
    logger.info(f'登录响应 error_msg: {lg.error_msg}')
    
    if lg.error_code != '0':
        logger.error(f"登录失败: {lg.error_msg}")
        return None
    
    try:
        #### 获取沪深A股历史K线数据 ####
        # 详细指标参数，参见"历史行情指标参数"章节；"分钟线"参数与"日线"参数不同。"分钟线"不包含指数。
        # 分钟线指标：date,time,code,open,high,low,close,volume,amount,adjustflag
        # 周月线指标：date,code,open,high,low,close,volume,amount,adjustflag,turn,pctChg
        
        fields = "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST"
        if frequency in ["5", "15", "30", "60"]:
            # 分钟线数据字段不同
            fields = "date,time,code,open,high,low,close,volume,amount,adjustflag"
        
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
        
        return result
        
    except Exception as e:
        logger.error(f"下载数据时发生错误: {str(e)}")
        return None
    finally:
        #### 登出系统 ####
        bs.logout()
        logger.info("已登出系统")


def generate_filename(stock_code, start_date, end_date, frequency):
    """生成文件名"""
    # 清理股票代码，移除前缀
    clean_code = stock_code.replace('sh.', '').replace('sz.', '')
    
    # 频率映射
    freq_map = {
        'd': 'daily',
        'w': 'weekly', 
        'm': 'monthly',
        '5': '5min',
        '15': '15min',
        '30': '30min',
        '60': '60min'
    }
    
    freq_str = freq_map.get(frequency, frequency)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    filename = f"{clean_code}_{freq_str}_{start_date}_{end_date}_{timestamp}.csv"
    return filename


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='下载股票历史数据')
    parser.add_argument('--code', '-c', required=True, help='股票代码，如: sh.600000')
    parser.add_argument('--start', '-s', required=True, help='开始日期，格式: YYYY-MM-DD')
    parser.add_argument('--end', '-e', required=True, help='结束日期，格式: YYYY-MM-DD')
    parser.add_argument('--frequency', '-f', default='d', 
                       choices=['d', 'w', 'm', '5', '15', '30', '60'],
                       help='数据频率: d=日线, w=周线, m=月线, 5/15/30/60=分钟线')
    parser.add_argument('--adjustflag', '-a', default='2', choices=['1', '2', '3'],
                       help='复权类型: 1=后复权, 2=前复权, 3=不复权')
    parser.add_argument('--output-dir', '-o', default='data', help='输出目录，默认为data')
    
    args = parser.parse_args()
    
    # 设置日志
    setup_logging()
    
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
        print(f"数据下载完成，共 {len(result)} 条记录")
        print(f"文件保存路径: {filepath}")
        print(result.head())
    else:
        logger.error("未能获取到有效数据")
        print("数据下载失败，请检查参数和网络连接")


if __name__ == "__main__":
    main()