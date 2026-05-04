import pandas as pd
import numpy as np
from typing import Tuple, Dict, Any, List


def calculate_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """计算MACD指标
    :param close: 收盘价序列
    :param fast: 快线周期
    :param slow: 慢线周期
    :param signal: 信号线周期
    :return: (MACD线, 信号线, 柱状图)
    """
    ema_fast = calculate_ema(close, fast)
    ema_slow = calculate_ema(close, slow)

    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """计算指数移动平均线
    :param series: 数据序列
    :param period: 周期
    :return: EMA序列
    """
    return series.ewm(span=period, adjust=False).mean()


def calculate_ma(series: pd.Series, period: int) -> pd.Series:
    """计算简单移动平均线
    :param series: 数据序列
    :param period: 周期
    :return: MA序列
    """
    return series.rolling(window=period).mean()


def calculate_macd_area(
    macd_histogram: pd.Series,
    start_idx: int,
    end_idx: int
) -> float:
    """计算MACD柱状图在指定区间的面积（用于背驰判断）
    :param macd_histogram: MACD柱状图
    :param start_idx: 起始索引
    :param end_idx: 结束索引
    :return: 面积值（红柱为正，绿柱为负）
    """
    if start_idx >= end_idx or start_idx < 0 or end_idx >= len(macd_histogram):
        return 0.0

    area = float(macd_histogram.iloc[start_idx:end_idx].sum())
    return area


def calculate_slope(series: pd.Series, period: int = 5) -> float:
    """计算序列的斜率
    :param series: 数据序列
    :param period: 计算斜率的周期
    :return: 斜率值
    """
    if len(series) < period:
        return 0.0

    recent = series.iloc[-period:].values
    x = np.arange(period)
    slope, _ = np.polyfit(x, recent, 1)
    return float(slope)


def check_divergence(
    current_pen_low: float,
    previous_pen_low: float,
    current_macd_area: float,
    previous_macd_area: float,
    pen_type: str = "bottom"
) -> bool:
    """判断背驰
    :param current_pen_low: 当前笔的低点
    :param previous_pen_low: 前一笔的低点
    :param current_macd_area: 当前笔对应的MACD面积
    :param previous_macd_area: 前一笔对应的MACD面积
    :param pen_type: 笔类型 "bottom"(底背驰) 或 "top"(顶背驰)
    :return: 是否背驰
    """
    if pen_type == "bottom":
        if current_pen_low >= previous_pen_low:
            return False
        if current_macd_area >= previous_macd_area:
            return True
        return False
    else:
        if current_pen_low <= previous_pen_low:
            return False
        if current_macd_area <= previous_macd_area:
            return True
        return False


def binance_klines_to_dataframe(klines: List[List[Any]]) -> pd.DataFrame:
    """将Binance API格式的K线数据转换为DataFrame
    
    :param klines: Binance API返回的K线数据，格式为嵌套列表
    :return: 包含open_time, open, high, low, close, volume字段的DataFrame
    """
    if not klines:
        return pd.DataFrame()

    data = []
    for kline in klines:
        open_time = pd.to_datetime(kline[0], unit='ms')
        open_price = float(kline[1])
        high = float(kline[2])
        low = float(kline[3])
        close = float(kline[4])
        volume = float(kline[5])
        
        data.append({
            'open_time': open_time,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })

    df = pd.DataFrame(data)
    return df


def dataframe_to_binance_klines(df: pd.DataFrame) -> List[List[Any]]:
    """将DataFrame格式的K线数据转换为Binance API格式
    
    :param df: 包含open_time, open, high, low, close, volume字段的DataFrame
    :return: Binance API格式的K线数据，格式为嵌套列表
    """
    if df.empty:
        return []

    klines = []
    for _, row in df.iterrows():
        kline = [
            int(row['open_time'].timestamp() * 1000),  # 开盘时间
            str(row['open']),                           # 开盘价
            str(row['high']),                           # 最高价
            str(row['low']),                            # 最低价
            str(row['close']),                          # 收盘价
            str(row['volume']),                         # 成交量
            int(row['open_time'].timestamp() * 1000 + 30 * 60 * 1000),  # 收盘时间
            str(row['volume'] * row['close']),          # 成交额
            0,                                          # 成交笔数
            str(row['volume'] * 0.5),                  # 主动买入成交量
            str(row['volume'] * 0.5 * row['close']),    # 主动买入成交额
            "0"                                         # 忽略该参数
        ]
        klines.append(kline)

    return klines


if __name__ == "__main__":
    test_data = pd.Series([100 + i + np.sin(i/10)*5 for i in range(100)])
    test_data.iloc[50:70] = test_data.iloc[50:70] * 1.05

    macd, signal, histogram = calculate_macd(test_data)
    print(f"MACD: {macd.iloc[-1]:.2f}")
    print(f"Signal: {signal.iloc[-1]:.2f}")
    print(f"Histogram: {histogram.iloc[-1]:.2f}")
    print(f"Slope: {calculate_slope(test_data):.4f}")

    # 测试数据格式转换
    test_klines = [
        [1499040000000, "0.01634790", "0.80000000", "0.01575800", "0.01577100", "148976.11427815", 1499644799999, "2434.19055334", 308, "1756.87402397", "28.46694368", "17928899.62484339"]
    ]
    df = binance_klines_to_dataframe(test_klines)
    print("\n转换为DataFrame:")
    print(df)

    converted_back = dataframe_to_binance_klines(df)
    print("\n转换回Binance格式:")
    print(converted_back)