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


def calculate_price_slope(prices: pd.Series) -> float:
    """对整段价格序列做线性回归，返回斜率（用于下跌角度对比）
    :param prices: 价格序列
    :return: 线性回归斜率值
    """
    if len(prices) < 2:
        return 0.0
    x = np.arange(len(prices))
    x_mean = x.mean()
    y_mean = prices.mean()
    numerator = np.sum((x - x_mean) * (prices.values - y_mean))
    denominator = np.sum((x - x_mean) ** 2)
    if abs(denominator) < 1e-10:
        return 0.0
    return float(numerator / denominator)


def calculate_deviation_rate(close: pd.Series, ma: pd.Series) -> pd.Series:
    """计算价格与均线的乖离率：(close - MA) / MA * 100%
    :param close: 收盘价序列
    :param ma: 均线序列
    :return: 乖离率序列（百分比）
    """
    valid = (ma.notna()) & (ma != 0)
    result = pd.Series(np.nan, index=close.index)
    result[valid] = (close[valid] - ma[valid]) / ma[valid] * 100.0
    return result


def calculate_ma_slope(close: pd.Series, period: int, lookback: int = 10) -> float:
    """计算MA在最近lookback根K线的斜率，判断均线走平/放缓
    :param close: 收盘价序列
    :param period: 均线周期
    :param lookback: 回溯K线数量
    :return: MA斜率值
    """
    if len(close) < period + lookback:
        return 0.0
    ma = calculate_ma(close, period)
    recent_ma = ma.iloc[-lookback:].dropna()
    if len(recent_ma) < 3:
        return 0.0
    return calculate_price_slope(recent_ma)


def calculate_volume_ratio(current_vol: float, previous_vol: float) -> float:
    """计算成交量比例：当前量/前次量
    :param current_vol: 当前成交量
    :param previous_vol: 前次成交量
    :return: 成交量比值
    """
    if previous_vol <= 0:
        return float('inf')
    return current_vol / previous_vol


def detect_volume_price_pattern(df: pd.DataFrame, recent_bars: int = 40) -> dict:
    """检测量价关系：下跌放量→反弹无量 是否转变为 下跌缩量→反弹温和放量

    分前后两段统计：
    - 前半段：统计下跌K线和反弹K线的平均成交量
    - 后半段：统计下跌K线和反弹K线的平均成交量
    - 对比判断模式是否转变

    :param df: K线DataFrame，需包含open,high,low,close,volume
    :param recent_bars: 统计的最近K线数量
    :return: 包含各阶段量价分析的字典
    """
    result = {
        'pattern_shifted': False,
        'early_fall_vol': 0.0,
        'early_bounce_vol': 0.0,
        'late_fall_vol': 0.0,
        'late_bounce_vol': 0.0,
        'detail': ''
    }

    if df.empty or len(df) < recent_bars:
        result['detail'] = '数据不足'
        return result

    df_recent = df.iloc[-recent_bars:].copy()
    mid = len(df_recent) // 2

    early_data = df_recent.iloc[:mid]
    late_data = df_recent.iloc[mid:]

    def classify_bars(data):
        fall_bars = []
        bounce_bars = []
        prev_close = None
        for _, row in data.iterrows():
            change = 0
            if prev_close is not None:
                change = row['close'] - prev_close
            prev_close = row['close']
            if change < 0:
                fall_bars.append(row)
            elif change > 0:
                bounce_bars.append(row)
        return fall_bars, bounce_bars

    early_fall, early_bounce = classify_bars(early_data)
    late_fall, late_bounce = classify_bars(late_data)

    early_fall_avg = np.mean([b['volume'] for b in early_fall]) if early_fall else 0
    early_bounce_avg = np.mean([b['volume'] for b in early_bounce]) if early_bounce else 0
    late_fall_avg = np.mean([b['volume'] for b in late_fall]) if late_fall else 0
    late_bounce_avg = np.mean([b['volume'] for b in late_bounce]) if late_bounce else 0

    result['early_fall_vol'] = early_fall_avg
    result['early_bounce_vol'] = early_bounce_avg
    result['late_fall_vol'] = late_fall_avg
    result['late_bounce_vol'] = late_bounce_avg

    early_abnormal = early_fall_avg > early_bounce_avg and early_fall_avg > 0 and early_bounce_avg > 0
    late_normal = late_fall_avg > 0 and late_bounce_avg > 0 and late_fall_avg < late_bounce_avg

    if early_abnormal and late_normal:
        result['pattern_shifted'] = True
        result['detail'] = '确认：前期下跌放量反弹无量 → 近期下跌缩量反弹温和放量'
    elif late_fall_avg > 0 and early_fall_avg > 0 and late_fall_avg < early_fall_avg:
        result['pattern_shifted'] = True
        result['detail'] = '确认：下跌量持续萎缩，模式正在转变'
    else:
        result['detail'] = '量价模式尚未明显转变'

    return result


def count_klines_between_points(df: pd.DataFrame, start_idx: int, end_idx: int) -> int:
    """统计两点之间的K线数量
    :param df: K线DataFrame
    :param start_idx: 起始索引
    :param end_idx: 结束索引
    :return: K线数量
    """
    if start_idx < 0 or end_idx < 0 or start_idx >= len(df) or end_idx >= len(df):
        return 0
    return abs(end_idx - start_idx)


def find_price_extremes(df: pd.DataFrame, window: int = 5) -> dict:
    """找出局部高点和低点序列
    :param df: K线DataFrame
    :param window: 局部极值窗口
    :return: {'highs': List[int], 'lows': List[int]} 索引列表
    """
    highs = []
    lows = []
    n = len(df)

    for i in range(window, n - window):
        is_high = True
        is_low = True
        for j in range(1, window + 1):
            if df['high'].iloc[i] <= df['high'].iloc[i - j] or df['high'].iloc[i] <= df['high'].iloc[i + j]:
                is_high = False
            if df['low'].iloc[i] >= df['low'].iloc[i - j] or df['low'].iloc[i] >= df['low'].iloc[i + j]:
                is_low = False
        if is_high:
            highs.append(i)
        if is_low:
            lows.append(i)

    return {'highs': highs, 'lows': lows}


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """计算ATR平均真实波幅
    :param df: K线DataFrame，需包含high,low,close
    :param period: ATR周期
    :return: ATR序列
    """
    high = df['high']
    low = df['low']
    close = df['close'].shift(1)

    tr1 = high - low
    tr2 = (high - close).abs()
    tr3 = (low - close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(span=period, adjust=False).mean()
    return atr


def detect_volume_price_pattern_uptrend(df: pd.DataFrame, recent_bars: int = 40) -> dict:
    """检测上升趋势量价关系：上涨放量→回调无量 是否转变为 上涨缩量→回调放量

    分前后两段统计：
    - 前半段：统计上涨K线和回调K线的平均成交量（正常模式：上涨放量、回调缩量）
    - 后半段：统计上涨K线和回调K线的平均成交量（检测是否转变为上涨缩量、回调放量）
    - 对比判断量价结构是否被破坏

    :param df: K线DataFrame，需包含open,high,low,close,volume
    :param recent_bars: 统计的最近K线数量
    :return: 包含各阶段量价分析的字典
    """
    result = {
        'pattern_shifted': False,
        'early_rise_vol': 0.0,
        'early_pullback_vol': 0.0,
        'late_rise_vol': 0.0,
        'late_pullback_vol': 0.0,
        'detail': ''
    }

    if df.empty or len(df) < recent_bars:
        result['detail'] = '数据不足'
        return result

    df_recent = df.iloc[-recent_bars:].copy()
    mid = len(df_recent) // 2

    early_data = df_recent.iloc[:mid]
    late_data = df_recent.iloc[mid:]

    def classify_bars(data):
        rise_bars = []
        pullback_bars = []
        prev_close = None
        for _, row in data.iterrows():
            change = 0
            if prev_close is not None:
                change = row['close'] - prev_close
            prev_close = row['close']
            if change > 0:
                rise_bars.append(row)
            elif change < 0:
                pullback_bars.append(row)
        return rise_bars, pullback_bars

    early_rise, early_pullback = classify_bars(early_data)
    late_rise, late_pullback = classify_bars(late_data)

    early_rise_avg = np.mean([b['volume'] for b in early_rise]) if early_rise else 0
    early_pullback_avg = np.mean([b['volume'] for b in early_pullback]) if early_pullback else 0
    late_rise_avg = np.mean([b['volume'] for b in late_rise]) if late_rise else 0
    late_pullback_avg = np.mean([b['volume'] for b in late_pullback]) if late_pullback else 0

    result['early_rise_vol'] = early_rise_avg
    result['early_pullback_vol'] = early_pullback_avg
    result['late_rise_vol'] = late_rise_avg
    result['late_pullback_vol'] = late_pullback_avg

    early_healthy = early_rise_avg > early_pullback_avg and early_rise_avg > 0 and early_pullback_avg > 0
    late_broken = late_rise_avg > 0 and late_pullback_avg > 0 and late_rise_avg < late_pullback_avg

    if early_healthy and late_broken:
        result['pattern_shifted'] = True
        result['detail'] = '确认：前期上涨放量回调缩量 → 近期上涨缩量回调放量，量价结构破坏'
    elif late_rise_avg > 0 and early_rise_avg > 0 and late_rise_avg < early_rise_avg:
        result['pattern_shifted'] = True
        result['detail'] = '确认：上涨量持续萎缩，量价背离加剧'
    else:
        result['detail'] = '量价结构尚未明显破坏'

    return result


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