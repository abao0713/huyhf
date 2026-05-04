import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
import numpy as np

from .base_strategy import BaseStrategy
from ..data.market_data import MarketDataClient, get_30m_klines, get_daily_klines
from ..okx.client import BinanceRestClient
from ..utils.indicators import calculate_macd, calculate_macd_area, check_divergence, binance_klines_to_dataframe, calculate_ma

logger = logging.getLogger(__name__)


@dataclass
class Fractal:
    """
    分型（顶分型/底分型）

    缠论中的分型是K线组合形态的基本单元：
    - 顶分型：三个连续K线，其中中间K线的最高点最高，形成一个类似"山顶"的形态
    - 底分型：三个连续K线，其中中间K线的最低点最低，形成一个类似"山谷"的形态

    属性说明：
    - idx: 分型在原始K线数据中的索引位置
    - type: 分型类型，"top"表示顶分型，"bottom"表示底分型
    - high: 分型中最高K线的最高价
    - low: 分型中最低K线的最低价
    - timestamp: 分型对应的时间戳
    """
    idx: int
    type: str
    high: float
    low: float
    timestamp: pd.Timestamp


@dataclass
class Pen:
    """
    笔（由分型构成的走势单元）

    笔是缠论中的基本走势单元，由一个底分型和一个紧接着的顶分型（或反之）构成：
    - 上升笔（up）：由底分型开始，到顶分型结束，代表价格上涨走势
    - 下降笔（down）：由顶分型开始，到底分型结束，代表价格下跌走势

    笔的有效性判断：
    1. 相邻两笔方向必须相反（上升笔后必须是下降笔）
    2. 上升笔的终点（顶分型）必须高于起点（底分型）
    3. 下降笔的终点（底分型）必须低于起点（顶分型）
    4. 新笔的起点不能破坏前一笔的方向

    属性说明：
    - start_fractal: 笔的起始分型
    - end_fractal: 笔的结束分型
    - direction: 笔的方向，"up"表示上升笔，"down"表示下降笔
    - high: 笔的最高点价格
    - low: 笔的最低点价格
    - start_time: 笔的起始时间
    - end_time: 笔的结束时间
    - macd_area: 笔对应的MACD柱状图面积，用于背驰判断
    """
    start_fractal: Fractal
    end_fractal: Fractal
    direction: str
    high: float
    low: float
    start_time: pd.Timestamp
    end_time: pd.Timestamp
    macd_area: float = 0.0


@dataclass
class Segment:
    """
    线段（由三笔构成的趋势单元）

    线段是缠论中的中级走势单元，代表一个较为持续的趋势行情：
    - 上升线段：由三笔构成，第一笔和第三笔方向相同（上升），第二笔为回调（下降）
    - 下降线段：由三笔构成，第一笔和第三笔方向相同（下降），第二笔为反弹（上升）

    线段的有效性判断（_pens_form_segment方法）：
    1. 需要至少三笔连续同向的笔
    2. 上升线段中，第三笔的终点必须高于第一笔的起点
    3. 上升线段中，第二笔的终点必须低于第一笔的起点（回调足够深）
    4. 下降线段中，第三笔的终点必须低于第一笔的起点
    5. 下降线段中，第二笔的终点必须高于第一笔的起点（反弹足够高）

    属性说明：
    - start_pen: 线段的起始笔
    - end_pen: 线段的结束笔
    - direction: 线段的方向，"up"表示上升线段，"down"表示下降线段
    - pens: 构成线段的所有笔列表（通常为3笔）
    """
    start_pen: Pen
    end_pen: Pen
    direction: str
    pens: List[Pen]


class ChanStrategy(BaseStrategy):
    """
    缠论策略

    基于缠论技术分析的交易策略实现。缠论是由国内某位匿名交易者创立的技术分析理论，
    其核心思想是通过分型、笔、线段等概念来描述价格的走势结构。

    入参说明：
    - symbol: 交易对名称，如"BTCUSDT"、"ETHUSDT"等
    - time_frame: K线时间周期，如"5m"（5分钟）、"30m"（30分钟）、"1h"（1小时）等
    - hg1: 分型查找参数，用于确定分型左右两侧的窗口大小
      * 5分钟周期默认值为4，表示在当前K线左右各4根K线范围内查找分型
      * 30分钟及以上周期默认值为8，较大周期需要更大的窗口来确认分型
    - macd_fast: MACD快线周期，默认12
    - macd_slow: MACD慢线周期，默认26
    - macd_signal: MACD信号线周期（EMA平滑周期），默认9
    - use_binance_client: 是否使用Binance客户端获取数据
      * True: 使用BinanceRestClient从Binance获取K线数据
      * False: 使用原有的market_data模块获取数据

    策略核心逻辑：
    1. 数据预处理：处理K线之间的包含关系，统一K线方向
    2. 分型识别：在预处理后的K线序列中查找顶分型和底分型
    3. 笔构建：将相邻的分型配对形成笔，判断笔的有效性
    4. 线段构建：将三笔组合形成线段，判断线段的有效性
    5. 背驰判断：通过比较相邻笔的MACD面积来判断是否出现背驰
    6. 信号生成：根据背驰情况和日线趋势生成交易信号
    """

    # 共振仓位配置常量
    RESONANCE_POSITION_SIZING = {
        "strong": 1.0,    # 强共振：100% 标准仓位（多头/空头排列完整）
        "normal": 0.7,    # 正常共振：70% 标准仓位（部分均线符合预期）
        "weak": 0.4,      # 弱共振：40% 标准仓位（均线排列混乱）
        "none": 0.7,      # 无共振：70% 标准仓位（保守策略）
    }

    def __init__(
        self,
        symbol: str = "BTCUSDT",
        time_frame: str = "30m",
        hg1: int = None,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        use_binance_client: bool = False,
        ma_short_period: int = 20,
        ma_medium_period: int = 60,
        ma_long_period: int = 120,
        enable_resonance: bool = True
    ):
        """
        初始化缠论策略

        参数：
        :param symbol: 交易对符号，默认为"BTCUSDT"
        :param time_frame: K线时间周期，默认为"30m"（30分钟）
        :param hg1: 分型查找的窗口参数，默认为None（自动根据time_frame设置）
                    5m周期默认4，30m及以上周期默认8
        :param macd_fast: MACD快线周期（EMA参数），默认12
        :param macd_slow: MACD慢线周期（EMA参数），默认26
        :param macd_signal: MACD信号线周期（对DIF的EMA平滑），默认9
        :param use_binance_client: 是否使用Binance客户端获取数据，默认False
        :param ma_short_period: 短期均线周期，默认20
        :param ma_medium_period: 中期均线周期，默认60
        :param ma_long_period: 长期均线周期，默认120
        :param enable_resonance: 是否启用共振验证功能，默认True
        """
        super().__init__("ChanStrategy")
        self.symbol = symbol
        self.time_frame = time_frame
        # 根据时间周期自动调整hg1参数
        # 较小周期使用较小的窗口，因为短期价格波动较大，需要更敏感的参数
        # 较大周期使用较大的窗口，因为价格波动相对平滑，需要更稳健的参数
        self.hg1 = hg1 if hg1 is not None else (4 if time_frame == "5m" else 8)
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.use_binance_client = use_binance_client

        # 均线配置参数
        self.ma_short_period = ma_short_period       # 短期均线周期（SMA20）
        self.ma_medium_period = ma_medium_period     # 中期均线周期（SMA60）
        self.ma_long_period = ma_long_period         # 长期均线周期（SMA120）
        
        # 共振验证开关
        self.enable_resonance = enable_resonance     # 是否启用均线共振验证

        # 数据存储
        self.df_30m: pd.DataFrame = pd.DataFrame()  # 30分钟K线数据
        self.df_5m: pd.DataFrame = pd.DataFrame()    # 5分钟K线数据
        self.df_daily: pd.DataFrame = pd.DataFrame()  # 日线K线数据（用于判断日线趋势）
        self.df_processed: pd.DataFrame = pd.DataFrame()  # 处理后的K线数据（经过包含关系处理）

        # 缠论元素存储
        self.fractals: List[Fractal] = []  # 识别出的所有分型列表
        self.pens: List[Pen] = []           # 识别出的所有笔列表
        self.segments: List[Segment] = []   # 识别出的所有线段列表

        # MACD指标数据
        self.macd_line: pd.Series = pd.Series()    # DIF线（快线减去慢线）
        self.signal_line: pd.Series = pd.Series()  # DEA线（信号线，DIF的EMA）
        self.histogram: pd.Series = pd.Series()    # MACD柱状图（DIF与DEA的差值）

        # 均线指标数据
        self.ma_short: pd.Series = pd.Series()      # 短期均线（SMA20）
        self.ma_medium: pd.Series = pd.Series()     # 中期均线（SMA60）
        self.ma_long: pd.Series = pd.Series()       # 长期均线（SMA120）

        # EMA趋势判断指标 (替代日线趋势)
        self.ema_fast: pd.Series = pd.Series()       # EMA快速线（EMA20）
        self.ema_slow: pd.Series = pd.Series()       # EMA慢速线（EMA60）

        # Binance客户端（可选）
        self.binance_client: Optional[BinanceRestClient] = None

        # 信号去重机制 - 独立的多空信号跟踪
        self.long_signal_info = {
            "action": None,           # 上次做多信号类型
            "pen_index": -1,          # 上次触发做多信号的笔索引
            "kline_index": -1,        # 上次触发做多信号的K线索引
            "cooldown_counter": 0     # 做多冷却期计数器
        }
        self.short_signal_info = {
            "action": None,           # 上次做空信号类型
            "pen_index": -1,          # 上次触发做空信号的笔索引
            "kline_index": -1,        # 上次触发做空信号的K线索引
            "cooldown_counter": 0     # 做空冷却期计数器
        }
        self.long_signal_cooldown_bars = 6   # 做多冷却期（优化：8→6，增加交易频率）
        self.short_signal_cooldown_bars = 6  # 做空冷却期（优化：8→6，增加交易频率）
        self._trend_position_mult: float = 1.0  # EMA趋势仓位系数（方案A：分级过滤）
        self._time_position_mult: float = 1.0   # 时间仓位系数（方案B：亚盘降仓）

    async def initialize(self, symbol: str) -> bool:
        """
        初始化策略，获取K线数据并进行预处理

        参数：
        :param symbol: 交易对符号

        返回：
        :return: 初始化是否成功

        初始化流程：
        1. 根据use_binance_client选择数据源
        2. 获取指定时间周期的K线数据
        3. 获取日线K线数据用于趋势判断
        4. 调用_process_data进行数据处理和缠论元素识别
        """
        self.symbol = symbol
        try:
            if self.use_binance_client:
                # 使用BinanceRestClient获取K线数据
                logger.info(f"[ChanStrategy] 使用BinanceRestClient获取K线数据，symbol={symbol}, time_frame={self.time_frame}")
                self.binance_client = BinanceRestClient()
                try:
                    # 根据时间周期获取K线数据
                    logger.info(f"[ChanStrategy] 获取{self.time_frame}K线数据...")
                    continuous_klines = await self.binance_client.get_continuous_klines(
                        pair=symbol,
                        contractType="PERPETUAL",
                        interval=self.time_frame,
                        limit=800  # 增加数据量以提高策略准确性
                    )

                    # 检查返回数据格式
                    if isinstance(continuous_klines, list) and continuous_klines:
                        logger.info(f"[ChanStrategy] 获取到 {len(continuous_klines)} 条{self.time_frame}K线数据")
                        if self.time_frame == "5m":
                            self.df_5m = binance_klines_to_dataframe(continuous_klines)
                        else:
                            self.df_30m = binance_klines_to_dataframe(continuous_klines)
                    else:
                        logger.error(f"[ChanStrategy] {self.time_frame}K线数据格式错误: {continuous_klines}")
                        return False

                    # 获取日线K线
                    logger.info(f"[ChanStrategy] 获取日线K线数据...")
                    daily_klines = await self.binance_client.get_continuous_klines(
                        pair=symbol,
                        contractType="PERPETUAL",
                        interval="1d",
                        limit=200
                    )

                    # 检查返回数据格式
                    if isinstance(daily_klines, list) and daily_klines:
                        logger.info(f"[ChanStrategy] 获取到 {len(daily_klines)} 条日线K线数据")
                        self.df_daily = binance_klines_to_dataframe(daily_klines)
                    else:
                        logger.error(f"[ChanStrategy] 日线K线数据格式错误: {daily_klines}")
                        return False
                finally:
                    await self.binance_client.close()
            else:
                # 使用原有的market_data获取K线数据
                logger.info(f"[ChanStrategy] 使用market_data获取K线数据，symbol={symbol}, time_frame={self.time_frame}")
                if self.time_frame == "5m":
                    # 假设存在get_5m_klines函数
                    try:
                        from ..data.market_data import get_5m_klines
                        self.df_5m = await get_5m_klines(symbol, 800)
                    except ImportError:
                        logger.error(f"[ChanStrategy] 未找到get_5m_klines函数")
                        return False
                else:
                    self.df_30m = await get_30m_klines(symbol, 800)
                self.df_daily = await get_daily_klines(symbol, 200)

            # 检查数据是否获取成功
            time_frame_data_empty = False
            if self.time_frame == "5m":
                time_frame_data_empty = self.df_5m.empty
            else:
                time_frame_data_empty = self.df_30m.empty

            if time_frame_data_empty or self.df_daily.empty:
                logger.error(f"[ChanStrategy] 获取数据失败，{self.time_frame}数据: {len(self.df_5m) if self.time_frame == '5m' else len(self.df_30m)} 条, 日线数据: {len(self.df_daily)} 条")
                return False

            logger.info(f"[ChanStrategy] 数据获取成功，开始处理数据...")
            self._process_data()
            logger.info(f"[ChanStrategy] 初始化成功，识别到 {len(self.fractals)} 个分型, {len(self.pens)} 笔")
            return True

        except Exception as e:
            logger.error(f"[ChanStrategy] 初始化失败: {str(e)}")
            return False

    def _process_data(self):
        """
        数据处理主流程

        该方法是缠论分析的核心处理流程，按顺序执行以下步骤：

        1. 数据源选择：根据time_frame选择对应的K线数据
           - 5m周期使用df_5m数据
           - 其他周期（如30m、1h等）使用df_30m数据

        2. 包含关系处理（_merge_inclusion）：
           处理相邻K线之间的包含关系，统一K线方向
           这是缠论分析的第一步，确保后续分型识别的准确性

        3. MACD指标计算（_calculate_macd）：
           计算MACD快线、慢线、信号线和柱状图
           用于后续的背驰判断

        4. 分型识别（_find_fractals）：
           在预处理后的K线序列中查找顶分型和底分型
           使用hg1参数确定左右窗口大小

        5. 笔构建（_build_pens）：
           将分型序列配对形成笔，过滤无效笔

        6. 线段构建（_build_segments）：
           将三笔组合形成线段
        """
        # 根据时间周期选择数据源
        if self.time_frame == "5m":
            self.df_processed = self.df_5m.copy()
        else:
            self.df_processed = self.df_30m.copy()

        # 步骤1：处理K线包含关系，统一K线方向
        self.df_processed = self._merge_inclusion(self.df_processed)
        # 步骤2：计算MACD指标
        self._calculate_macd()
        # 计算均线（用于共振验证）
        self._calculate_mavgs()
        # 步骤3：查找分型
        self.fractals = self._find_fractals(self.df_processed, self.hg1)
        # 步骤4：构建笔
        self.pens = self._build_pens(self.fractals)
        # 步骤5：构建线段
        self.segments = self._build_segments(self.pens)

    def _merge_inclusion(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        处理K线包含关系，用于处理K线合并的情况

        包含关系的定义：
        在缠论中，当三根连续K线满足以下条件时，存在包含关系：
        - 条件1：k3的高点 <= k1的高点 且 k3的低点 >= k1的低点（k3完全包含在k1内部）
        - 条件2：k3的高点 >= k1的高点 且 k3的低点 <= k1的低点（k1完全包含在k3内部）

        包含关系的处理原则：
        - 上升趋势中：取两根K线的高点最大值和低点最大值（向上合并）
        - 下降趋势中：取两根K线的高点最小值和低点最小值（向下合并）

        处理流程：
        1. 从第一根K线开始，每次检查连续三根K线是否存在包含关系
        2. 如果存在包含关系，根据趋势方向进行合并
        3. 合并后继续向后检查，直到处理完所有K线

        参数：
        :param df: 原始K线DataFrame，必须包含high、low、open、close、open_time等列

        返回：
        :return: 处理包含关系后的K线DataFrame
        """
        if len(df) < 5:
            return df

        df = df.reset_index(drop=True)
        merged = []
        i = 0

        # 滑动窗口检查包含关系，每次处理3根K线
        while i < len(df) - 2:
            k1 = df.iloc[i]      # 第一根K线
            k2 = df.iloc[i + 1]  # 第二根K线
            k3 = df.iloc[i + 2]  # 第三根K线

            # 检查是否存在包含关系
            if self._has_inclusion(k1, k2, k3):
                # 根据趋势方向确定合并方式
                direction = self._get_trend_direction(k1, k2)
                merged_high, merged_low = self._merge_klines(k1, k2, k3, direction)

                # 创建合并后的新K线
                new_row = k1.copy()
                new_row["high"] = merged_high
                new_row["low"] = merged_low
                merged.append(new_row)
                i += 3  # 合并后跳过已处理的三根K线
            else:
                merged.append(k1)
                i += 1

        # 处理剩余的K线
        while i < len(df):
            merged.append(df.iloc[i])
            i += 1

        if not merged:
            return df

        result = pd.DataFrame(merged).reset_index(drop=True)
        return result

    def _has_inclusion(self, k1, k2, k3) -> bool:
        """
        判断三根K线是否存在包含关系

        包含关系判断条件：
        条件1（k3包含在k1中）：k3.high <= k1.high 且 k3.low >= k1.low
        条件2（k1包含在k3中）：k3.high >= k1.high 且 k3.low <= k1.low

        参数：
        :param k1: 第一根K线
        :param k2: 第二根K线
        :param k3: 第三根K线
        :return: 是否存在包含关系
        """
        cond1 = (k3["high"] <= k1["high"] and k3["low"] >= k1["low"])
        cond2 = (k3["high"] >= k1["high"] and k3["low"] <= k1["low"])
        return cond1 or cond2

    def _get_trend_direction(self, k1, k2) -> str:
        """
        根据前两根K线判断当前趋势方向

        趋势方向判断逻辑：
        - 如果k2的高点高于k1的高点，说明当前是上升趋势（"up"）
        - 如果k2的高点低于k1的高点，说明当前是下降趋势（"down"）

        参数：
        :param k1: 第一根K线
        :param k2: 第二根K线
        :return: 趋势方向，"up"表示上升，"down"表示下降
        """
        return "up" if k2["high"] > k1["high"] else "down"

    def _merge_klines(self, k1, k2, k3, direction: str) -> Tuple[float, float]:
        """
        合并三根存在包含关系的K线

        合并规则：
        - 上升趋势中：取高点的最大值和低点的最大值（向上合并）
        - 下降趋势中：取高点的最小值和低点的最小值（向下合并）

        参数：
        :param k1: 第一根K线
        :param k2: 第二根K线
        :param k3: 第三根K线
        :param direction: 趋势方向，"up"或"down"
        :return: 合并后的高点和低点
        """
        if direction == "up":
            # 上升趋势取最大值
            high = max(k1["high"], k2["high"], k3["high"])
            low = max(k1["low"], k2["low"], k3["low"])
        else:
            # 下降趋势取最小值
            high = min(k1["high"], k2["high"], k3["high"])
            low = min(k1["low"], k2["low"], k3["low"])
        return high, low

    def _calculate_macd(self):
        """
        计算MACD指标

        MACD（Moving Average Convergence Divergence）指标计算：
        1. 快线（EMA12）：12日指数移动平均线
        2. 慢线（EMA26）：26日指数移动平均线
        3. DIF线：快线 - 慢线
        4. 信号线：DIF的9日指数移动平均线
        5. MACD柱状图：DIF - 信号线

        MACD柱状图面积计算：
        在缠论中，使用MACD柱状图的面积来判断背驰
        面积 = Σ(每根K线对应的MACD柱状图值)

        背驰判断原理：
        - 正常趋势中：价格上涨/下跌创新高/新低时，MACD面积应该同步放大
        - 背驰发生时：价格创新高/新低，但MACD面积比前一笔小，说明动力减弱
        """
        close = self.df_processed["close"]
        self.macd_line, self.signal_line, self.histogram = calculate_macd(
            close, self.macd_fast, self.macd_slow, self.macd_signal
        )

    def _calculate_mavgs(self):
        """
        计算均线指标（用于共振验证）

        均线计算说明：
        使用简单移动平均线（SMA）计算三个周期的均线：
        - 短期均线（SMA20）：反映短期价格趋势，敏感度较高
        - 中期均线（SMA60）：反映中期价格趋势，用于确认趋势方向
        - 长期均线（SMA120）：反映长期价格趋势，提供支撑/阻力参考

        共振验证原理：
        当缠论信号与均线排列方向一致时，形成技术指标共振，
        可以提高信号的可靠性并调整仓位大小：
        - 强共振：多头排列或空头排列完整，信号可靠性高
        - 弱共振：部分均线符合预期，信号可靠性中等
        - 无共振：均线排列混乱，信号可靠性较低

        数据不足处理：
        如果K线数据长度小于均线周期，则跳过该均线的计算，
        避免因数据不足导致的计算错误。
        """
        if len(self.df_processed) == 0:
            logger.warning(f"[ChanStrategy] K线数据为空，无法计算均线")
            return

        close = self.df_processed["close"]

        # 计算短期均线（SMA20）
        if len(close) >= self.ma_short_period:
            self.ma_short = calculate_ma(close, self.ma_short_period)
            logger.info(f"[ChanStrategy] 短期均线(SMA{self.ma_short_period}): {self.ma_short.iloc[-1]:.2f}")
        else:
            logger.warning(f"[ChanStrategy] 数据长度({len(close)})不足，无法计算短期均线(SMA{self.ma_short_period})")
            self.ma_short = pd.Series()

        # 计算中期均线（SMA60）
        if len(close) >= self.ma_medium_period:
            self.ma_medium = calculate_ma(close, self.ma_medium_period)
            logger.info(f"[ChanStrategy] 中期均线(SMA{self.ma_medium_period}): {self.ma_medium.iloc[-1]:.2f}")
        else:
            logger.warning(f"[ChanStrategy] 数据长度({len(close)})不足，无法计算中期均线(SMA{self.ma_medium_period})")
            self.ma_medium = pd.Series()

        # 计算长期均线（SMA120）
        if len(close) >= self.ma_long_period:
            self.ma_long = calculate_ma(close, self.ma_long_period)
            logger.info(f"[ChanStrategy] 长期均线(SMA{self.ma_long_period}): {self.ma_long.iloc[-1]:.2f}")
        else:
            logger.warning(f"[ChanStrategy] 数据长度({len(close)})不足，无法计算长期均线(SMA{self.ma_long_period})")
            self.ma_long = pd.Series()

        # ===== 计算 EMA 趋势判断指标 (EMA20/EMA60) =====
        self._calculate_ema_trend_indicators(close)

    def _calculate_ema_trend_indicators(self, close: pd.Series) -> None:
        """
        计算 EMA 趋势判断指标 (EMA20 和 EMA60)
        
        用于替代日线趋势判断，使用双均线系统识别趋势方向：
        
        趋势判断规则：
        - 多头趋势：EMA20 > EMA60 且 价格 > EMA20
        - 空头趋势：EMA20 < EMA60 且 价格 < EMA20
        - 震荡市：其他情况（均线粘合或价格在两均线之间）
        
        Args:
            close: 收盘价序列
        """
        try:
            from ..utils.indicators import calculate_ema
            
            ema_fast_period = 20  # EMA快速线周期
            ema_slow_period = 60  # EMA慢速线周期
            
            # 计算 EMA20 (快速线)
            if len(close) >= ema_fast_period:
                self.ema_fast = calculate_ema(close, ema_fast_period)
                logger.debug(f"[ChanStrategy] EMA{ema_fast_period}: {self.ema_fast.iloc[-1]:.2f}")
            else:
                self.ema_fast = pd.Series()
                logger.debug(f"[ChanStrategy] 数据不足，无法计算EMA{ema_fast_period}")
            
            # 计算 EMA60 (慢速线)
            if len(close) >= ema_slow_period:
                self.ema_slow = calculate_ema(close, ema_slow_period)
                logger.debug(f"[ChanStrategy] EMA{ema_slow_period}: {self.ema_slow.iloc[-1]:.2f}")
            else:
                self.ema_slow = pd.Series()
                logger.debug(f"[ChanStrategy] 数据不足，无法计算EMA{ema_slow_period}")
                
        except Exception as e:
            logger.warning(f"[ChanStrategy] EMA趋势指标计算失败: {e}")
            self.ema_fast = pd.Series()
            self.ema_slow = pd.Series()

    def _get_ema_trend(self) -> str:
        """
        获取当前 EMA 趋势状态
        
        使用 EMA20/EMA60 双均线系统判断趋势：
        
        Returns:
            str: 趋势状态
                - "bullish": 多头趋势 (EMA20 > EMA60 且 价格 > EMA20)
                - "bearish": 空头趋势 (EMA20 < EMA60 且 价格 < EMA20)
                - "neutral": 震荡/未知 (其他情况)
        """
        try:
            if len(self.ema_fast) < 1 or len(self.ema_slow) < 1:
                return "neutral"
            
            if self.df_processed.empty:
                return "neutral"
            
            ema_fast_val = self.ema_fast.iloc[-1]
            ema_slow_val = self.ema_slow.iloc[-1]
            current_price = self.df_processed["close"].iloc[-1]
            
            if pd.isna(ema_fast_val) or pd.isna(ema_slow_val):
                return "neutral"
            
            # 多头趋势: EMA20 > EMA60 且 价格在 EMA20 之上
            if ema_fast_val > ema_slow_val and current_price > ema_fast_val:
                return "bullish"
            
            # 空头趋势: EMA20 < EMA60 且 价格在 EMA20 之下
            elif ema_fast_val < ema_slow_val and current_price < ema_fast_val:
                return "bearish"
            
            # 其他情况: 震荡市
            else:
                return "neutral"
                
        except Exception as e:
            logger.warning(f"[ChanStrategy] EMA趋势判断失败: {e}")
            return "neutral"

    def _check_ma_support(self, price: float, ma_price: Optional[float], tolerance: float = 0.005) -> Optional[str]:
        """
        判断价格是否获得均线支撑

        支撑位判断逻辑：
        当价格接近或触及均线时，均线可能形成价格下方的支撑。
        通过计算价格与均线的偏离程度来判断支撑强度：

        - 强支撑（strong）：价格与均线偏离度 < 0.25%（极近距离）
          表示价格紧贴均线，支撑作用非常明显
        - 弱支撑（weak）：价格与均线偏离度 < 0.5%（接近距离）
          表示价格接近均线，有一定的支撑作用
        - 无支撑（None）：价格与均线偏离度 >= 0.5%
          表示价格远离均线，当前无支撑作用

        参数：
        :param price: 当前价格
        :param ma_price: 均线价格
        :param tolerance: 容差比例，默认0.005（0.5%）

        返回：
        :return: "strong"表示强支撑，"weak"表示弱支撑，None表示无支撑
        """
        if ma_price is None or ma_price == 0 or price <= 0:
            return None

        ratio = abs(price - ma_price) / ma_price

        if ratio <= tolerance * 0.5:
            return "strong"
        elif ratio <= tolerance:
            return "weak"
        else:
            return None

    def _check_ma_resistance(self, price: float, ma_price: Optional[float], tolerance: float = 0.005) -> Optional[str]:
        """
        判断价格是否受到均线压力

        压力位判断逻辑：
        当价格接近或触及均线时，均线可能形成价格上方的压力/阻力。
        通过计算价格与均线的偏离程度来判断压力强度：

        - 强压力（strong）：价格与均线偏离度 < 0.25%（极近距离）
          表示价格紧贴均线，压力作用非常明显
        - 弱压力（weak）：价格与均线偏离度 < 0.5%（接近距离）
          表示价格接近均线，有一定的压力作用
        - 无压力（None）：价格与均线偏离度 >= 0.5%
          表示价格远离均线，当前无压力作用

        注意：此方法的计算逻辑与_check_ma_support完全相同，
        区别仅在于语义：support表示下方支撑，resistance表示上方压力

        参数：
        :param price: 当前价格
        :param ma_price: 均线价格
        :param tolerance: 容差比例，默认0.005（0.5%）

        返回：
        :return: "strong"表示强压力，"weak"表示弱压力，None表示无压力
        """
        if ma_price is None or ma_price == 0 or price <= 0:
            return None

        ratio = abs(price - ma_price) / ma_price

        if ratio <= tolerance * 0.5:
            return "strong"
        elif ratio <= tolerance:
            return "weak"
        else:
            return None

    def _get_ma_signal(self, price: float) -> Dict[str, Any]:
        """
        获取均线支撑/压力综合信号

        综合检测方法，同时检查短期均线（MA20）和中期均线（MA60）
        对当前价格的支撑和压力情况，返回结构化的分析结果。

        检测逻辑：
        1. 分别获取MA20和MA60的最新值
        2. 对每条均线同时进行支撑和压力检测
        3. 返回最显著的支撑和压力信号

        应用场景：
        - 在生成交易信号时参考支撑/压力位
        - 辅助判断入场点和止损位置
        - 结合缠论背驰信号提高决策准确性

        参数：
        :param price: 当前价格

        返回：
        :return: 结构化字典，包含以下字段：
                 - has_support: 是否存在支撑位（bool）
                 - support_level: 支撑强度等级（"strong"/"weak"/None）
                 - support_ma_type: 提供支撑的均线类型（"MA20"/"MA60"/None）
                 - support_ma_price: 支撑均线价格（float/None）
                 - has_resistance: 是否存在压力位（bool）
                 - resistance_level: 压力强度等级（"strong"/"weak"/None）
                 - resistance_ma_type: 提供压力的均线类型（"MA20"/"MA60"/None）
                 - resistance_ma_price: 压力均线价格（float/None）
        """
        result = {
            "has_support": False,
            "support_level": None,
            "support_ma_type": None,
            "support_ma_price": None,
            "has_resistance": False,
            "resistance_level": None,
            "resistance_ma_type": None,
            "resistance_ma_price": None
        }

        # 检查MA20的支撑和压力
        if not self.ma_short.empty and len(self.ma_short) > 0:
            ma20_price = float(self.ma_short.iloc[-1])

            # 检查支撑（价格在均线下方附近）
            support_level = self._check_ma_support(price, ma20_price)
            if support_level is not None and not result["has_support"]:
                result["has_support"] = True
                result["support_level"] = support_level
                result["support_ma_type"] = f"MA{self.ma_short_period}"
                result["support_ma_price"] = ma20_price

            # 检查压力（价格在均线上方附近）
            resistance_level = self._check_ma_resistance(price, ma20_price)
            if resistance_level is not None and not result["has_resistance"]:
                result["has_resistance"] = True
                result["resistance_level"] = resistance_level
                result["resistance_ma_type"] = f"MA{self.ma_short_period}"
                result["resistance_ma_price"] = ma20_price

        # 检查MA60的支撑和压力
        if not self.ma_medium.empty and len(self.ma_medium) > 0:
            ma60_price = float(self.ma_medium.iloc[-1])

            # 检查支撑（价格在均线下方附近）
            support_level = self._check_ma_support(price, ma60_price)
            if support_level is not None:
                # 如果已有MA20的支撑，只保留更强的支撑
                if not result["has_support"] or \
                   (result["support_level"] == "weak" and support_level == "strong"):
                    result["has_support"] = True
                    result["support_level"] = support_level
                    result["support_ma_type"] = f"MA{self.ma_medium_period}"
                    result["support_ma_price"] = ma60_price

            # 检查压力（价格在均线上方附近）
            resistance_level = self._check_ma_resistance(price, ma60_price)
            if resistance_level is not None:
                # 如果已有MA20的压力，只保留更强的压力
                if not result["has_resistance"] or \
                   (result["resistance_level"] == "weak" and resistance_level == "strong"):
                    result["has_resistance"] = True
                    result["resistance_level"] = resistance_level
                    result["resistance_ma_type"] = f"MA{self.ma_medium_period}"
                    result["resistance_ma_price"] = ma60_price

        logger.debug(f"[ChanStrategy] 均线信号分析结果: {result}")
        return result

    def _evaluate_buy_signal_resonance(self, pen):
        """
        评估买入信号的共振强度

        共振判定原理：
        将缠论买入信号（底背驰）与均线支撑、日线趋势进行综合评估，
        判断信号的可靠性和强度，从而决定仓位大小。

        判定规则矩阵：
        - strong支撑 + (up/neutral)趋势 → strong（强共振）
        - weak支撑 + 非down趋势 → normal（正常共振）
        - any支撑 + down趋势 → weak（弱共振，存在矛盾）
        - 无支撑 → none（无共振）

        参数：
        :param pen: 当前笔（Pen对象），用于获取价格信息

        返回：
        :return: tuple: (resonance_level, reason)
            - resonance_level: "strong" | "normal" | "weak" | "none"
            - reason: 共振原因说明
        """
        chan_signal = "BUY (底背驰)"
        daily_trend = self._get_daily_trend()

        # 检查均线支撑（使用MA20）
        ma_support = None
        ma_price = None
        if len(self.ma_short) > 0:
            ma_price = self.ma_short.iloc[-1]
            ma_support = self._check_ma_support(
                price=pen.low,
                ma_price=ma_price
            )

        # 根据规则矩阵判定共振级别
        if ma_support == "strong" and daily_trend in ["up", "neutral"]:
            level = "strong"
            reason = f"{chan_signal} + 强支撑(MA20) + {daily_trend}趋势"
        elif ma_support == "weak" and daily_trend != "down":
            level = "normal"
            reason = f"{chan_signal} + 弱支撑 + {daily_trend}趋势"
        elif ma_support is not None and daily_trend == "down":
            level = "weak"
            reason = f"{chan_signal} + 下降趋势(矛盾)"
        else:
            level = "none"
            reason = f"{chan_signal} (纯缠论信号)"

        # 输出详细日志
        logger.info(f"[ChanStrategy] 共振信号评估(买入):")
        logger.info(f"  - 基础信号: {chan_signal}")
        ma_price_str = f"{ma_price:.2f}" if ma_price is not None else "N/A"
        logger.info(f"  - 价格: {pen.low:.2f} | MA20: {ma_price_str}")
        logger.info(f"  - 支撑强度: {ma_support}")
        logger.info(f"  - 日线趋势: {daily_trend}")
        logger.info(f"  - 共振级别: {level.upper()}")
        logger.info(f"  - 建议仓位: {self.RESONANCE_POSITION_SIZING[level]*100:.0f}%")

        return level, reason

    def _evaluate_sell_signal_resonance(self, pen):
        """
        评估卖出信号的共振强度

        共振判定原理：
        将缠论卖出信号（顶背驰）与均线压力、日线趋势进行综合评估，
        判断信号的可靠性和强度，从而决定仓位大小。

        判定规则矩阵（与买入镜像对称）：
        - strong压力 + (down/neutral)趋势 → strong（强共振）
        - weak压力 + 非up趋势 → normal（正常共振）
        - any压力 + up趋势 → weak（弱共振，存在矛盾）
        - 无压力 → none（无共振）

        参数：
        :param pen: 当前笔（Pen对象），用于获取价格信息

        返回：
        :return: tuple: (resonance_level, reason)
            - resonance_level: "strong" | "normal" | "weak" | "none"
            - reason: 共振原因说明
        """
        chan_signal = "SELL (顶背驰)"
        daily_trend = self._get_daily_trend()

        # 检查MA60压力
        ma_resistance = None
        ma_price = None
        if len(self.ma_medium) > 0:
            ma_price = self.ma_medium.iloc[-1]
            ma_resistance = self._check_ma_resistance(
                price=pen.high,
                ma_price=ma_price
            )

        # 根据规则矩阵判定共振级别（与买入逻辑镜像对称）
        if ma_resistance == "strong" and daily_trend in ["down", "neutral"]:
            level = "strong"
            reason = f"{chan_signal} + 强压力(MA60) + {daily_trend}趋势"
        elif ma_resistance == "weak" and daily_trend != "up":
            level = "normal"
            reason = f"{chan_signal} + 弱压力 + {daily_trend}趋势"
        elif ma_resistance is not None and daily_trend == "up":
            level = "weak"
            reason = f"{chan_signal} + 上升趋势(矛盾)"
        else:
            level = "none"
            reason = f"{chan_signal} (纯缠论信号)"

        # 输出详细日志
        logger.info(f"[ChanStrategy] 共振信号评估(卖出):")
        logger.info(f"  - 基础信号: {chan_signal}")
        ma_price_str = f"{ma_price:.2f}" if ma_price is not None else "N/A"
        logger.info(f"  - 价格: {pen.high:.2f} | MA60: {ma_price_str}")
        logger.info(f"  - 压力强度: {ma_resistance}")
        logger.info(f"  - 日线趋势: {daily_trend}")
        logger.info(f"  - 共振级别: {level.upper()}")
        logger.info(f"  - 建议仓位: {self.RESONANCE_POSITION_SIZING[level]*100:.0f}%")

        return level, reason

    def _find_fractals(self, df: pd.DataFrame, hg1: int = 8) -> List[Fractal]:
        """
        查找分型（顶分型和底分型）

        分型定义：
        - 顶分型：中间K线的最高点高于左右两侧K线的最高点
          条件：current.high > left_high 且 current.high > right_high
        - 底分型：中间K线的最低点低于左右两侧K线的最低点
          条件：current.low < left_low 且 current.low < right_low

        hg1参数说明：
        hg1定义了分型左右两侧的窗口大小。例如hg1=8表示：
        - 查找顶分型时，当前K线的最高点需要是前后各8根K线中的最高点
        - 查找底分型时，当前K线的最低点需要是前后各8根K线中的最低点

        参数：
        :param df: 处理后的K线数据DataFrame
        :param hg1: 分型查找窗口参数，默认8
        :return: 分型列表
        """
        fractals = []
        n = len(df)

        # 从hg1位置开始，到n-hg1位置结束，确保左右都有足够的K线
        for i in range(hg1, n - hg1):
            # 计算左侧hg1根K线的最高点和最低点
            left_high = df.iloc[i - hg1:i]["high"].max()
            left_low = df.iloc[i - hg1:i]["low"].min()
            # 计算右侧hg1根K线的最高点和最低点
            right_high = df.iloc[i + 1:i + hg1 + 1]["high"].max()
            right_low = df.iloc[i + 1:i + hg1 + 1]["low"].min()

            current = df.iloc[i]

            # 检查是否是顶分型
            if current["high"] > left_high and current["high"] > right_high:
                fractals.append(Fractal(
                    idx=i,
                    type="top",
                    high=current["high"],
                    low=current["low"],
                    timestamp=current["open_time"]
                ))

            # 检查是否是底分型
            if current["low"] < left_low and current["low"] < right_low:
                fractals.append(Fractal(
                    idx=i,
                    type="bottom",
                    high=current["high"],
                    low=current["low"],
                    timestamp=current["open_time"]
                ))

        return fractals

    def _build_pens(self, fractals: List[Fractal]) -> List[Pen]:
        """
        构建笔，从分型序列中识别有效笔

        笔的构成规则：
        1. 上升笔：由底分型（start）和顶分型（end）构成
        2. 下降笔：由顶分型（start）和底分型（end）构成

        笔的有效性过滤规则：
        1. 相邻两笔方向必须相反（笔的交替规则）
        2. 上升笔的终点必须高于起点
        3. 下降笔的终点必须低于起点

        MACD面积计算：
        每个笔对应一段价格走势，其MACD面积为该笔起始到结束位置之间
        所有MACD柱状图值的和。面积用于后续的背驰判断。

        参数：
        :param fractals: 分型列表
        :return: 有效笔列表
        """
        if len(fractals) < 2:
            return []

        pens = []
        i = 0
        
        # 遍历分型，寻找有效的笔
        while i < len(fractals) - 1:
            f1 = fractals[i]
            
            # 找到下一个不同类型的分型
            j = i + 1
            while j < len(fractals) and fractals[j].type == f1.type:
                # 对于相同类型的分型，保留极值
                if f1.type == "top":
                    if fractals[j].high > f1.high:
                        f1 = fractals[j]
                        i = j
                else:  # bottom
                    if fractals[j].low < f1.low:
                        f1 = fractals[j]
                        i = j
                j += 1
            
            # 如果找到不同类型的分型，形成笔
            if j < len(fractals):
                f2 = fractals[j]
                
                # 确定笔的方向和高低点
                if f1.type == "top" and f2.type == "bottom":
                    # 顶分型后是底分型 -> 下降笔
                    direction = "down"
                    high = f1.high
                    low = f2.low
                else:  # f1.type == "bottom" and f2.type == "top"
                    # 底分型后是顶分型 -> 上升笔
                    direction = "up"
                    high = f2.high  # 顶分型的高点
                    low = f1.low    # 底分型的低点
                
                # 笔必须有实际价格变动
                if (direction == "up" and low >= high) or (direction == "down" and high <= low):
                    i = j
                    continue
                
                # 创建笔对象
                pen = Pen(
                    start_fractal=f1,
                    end_fractal=f2,
                    direction=direction,
                    high=high,
                    low=low,
                    start_time=f1.timestamp,
                    end_time=f2.timestamp,
                    macd_area=0.0
                )

                # 计算笔的MACD面积
                if len(pens) > 0:
                    pen_start_idx = f1.idx
                    pen_end_idx = f2.idx
                    pen.macd_area = float(self.histogram.iloc[pen_start_idx:pen_end_idx].sum())

                pens.append(pen)
            
            i = j

        return pens

    def _build_segments(self, pens: List[Pen]) -> List[Segment]:
        """
        构建线段，从笔序列中识别有效线段

        线段定义：
        线段是由三笔构成的中级走势单元，代表一个较为持续的趋势行情。

        线段的有效性判断（_pens_form_segment）：
        1. 三笔的第一笔和第三笔方向必须相同
        2. 上升线段：第三笔的终点必须高于第一笔的起点，第二笔的回调低点必须低于第一笔的起点
        3. 下降线段：第三笔的终点必须低于第一笔的起点，第二笔的反弹高点必须高于第一笔的起点

        参数：
        :param pens: 笔列表
        :return: 有效线段列表
        """
        if len(pens) < 3:
            return []

        segments = []
        i = 0

        # 滑动窗口检查，每三笔判断一次是否构成线段
        while i < len(pens) - 2:
            seg_pens = [pens[i], pens[i + 1], pens[i + 2]]

            if self._pens_form_segment(seg_pens):
                # 三笔构成有效线段
                direction = seg_pens[0].direction
                segment = Segment(
                    start_pen=seg_pens[0],
                    end_pen=seg_pens[2],
                    direction=direction,
                    pens=seg_pens
                )
                segments.append(segment)
                i += 3  # 线段由三笔构成，向后移动三笔
            else:
                i += 1  # 不构成线段，向后移动一笔继续检查

        return segments

    def _pens_form_segment(self, pens: List[Pen]) -> bool:
        """
        判断三笔是否能构成线段

        线段构成条件（简化标准）：
        1. 三笔的第一笔(p1)和第三笔(p3)方向必须相同
        2. 上升线段：p1和p3为上升笔，p2为下降回调笔
        3. 下降线段：p1和p3为下降笔，p2为上升反弹笔

        参数：
        :param pens: 三笔组成的列表 [p1, p2, p3]
        :return: 是否构成有效线段
        """
        if len(pens) < 3:
            return False

        p1, p2, p3 = pens[0], pens[1], pens[2]

        # 条件1：p1和p3方向必须相同
        if p1.direction != p3.direction:
            return False

        # 条件2：p2必须与p1方向相反（回调或反弹）
        if p2.direction == p1.direction:
            return False

        return True

    def _get_daily_trend(self) -> str:
        """
        获取日线趋势方向

        日线趋势判断方法：
        使用日线收盘价的简单移动平均线（SMA）来判断趋势：
        - 上升趋势：MA5 > MA20 > MA60（多头排列）
        - 下降趋势：MA5 < MA20 < MA60（空头排列）
        - 中性趋势：其他情况

        返回：
        :return: 日线趋势，"up"表示上升，"down"表示下降，"neutral"表示中性
        """
        if len(self.df_daily) < 20:
            return "unknown"

        ma5 = self.df_daily["close"].iloc[-5:].mean()
        ma20 = self.df_daily["close"].iloc[-20:].mean()
        ma60 = self.df_daily["close"].iloc[-60:].mean() if len(self.df_daily) >= 60 else ma20

        if ma5 > ma20 > ma60:
            return "up"
        elif ma5 < ma20 < ma60:
            return "down"
        else:
            return "neutral"

    def _check_bottom_divergence(self, pen: Pen) -> bool:
        """
        底背驰判断

        底背驰定义：
        在下降趋势中，当前下降笔创新低（低点比前一下降笔低），但MACD面积
        比前一下降笔小（或者MACD柱子高度比前一下降笔短），说明下跌动力减弱，
        可能出现反转向上。

        底背驰条件：
        1. 当前笔是下降笔（direction == "down"）
        2. 当前笔的低点 < 前一个下降笔的低点（创新低）
        3. 当前笔的MACD面积 > 前一个下降笔的MACD面积（面积缩小）

        注意：比较的是两个连续的同向笔（都是下降笔），
        需要找到当前笔之前的那个下降笔进行比较。

        参数：
        :param pen: 当前的笔（应该是下降笔）
        :return: 是否发生底背驰
        """
        if len(self.pens) < 2:
            return False

        current_pen = pen
        prev_pen = None

        # 查找前一个下降笔
        for i in range(len(self.pens) - 2, -1, -1):
            if self.pens[i].direction == "up":
                # 找到前一个上升笔，跳过
                continue
            prev_pen = self.pens[i]
            break

        if prev_pen is None:
            return False

        # 获取当前笔和前一个下降笔的低点
        current_low = current_pen.low
        prev_low = prev_pen.low

        # 获取对应笔的MACD面积
        current_area = current_pen.macd_area
        prev_area = prev_pen.macd_area

        # 底背驰判断：价格创新低但MACD面积未明显缩小（>=前面积的90%）
        if current_low < prev_low:
            if prev_area != 0:
                ratio = current_area / prev_area
                logger.info(f"底背驰检测: 当前低点={current_low}, 前低点={prev_low}, "
                           f"当前MACD面积={current_area:.4f}, 前MACD面积={prev_area:.4f}, "
                           f"比值={ratio:.4f}, 阈值=0.85")
                if current_area >= prev_area * 0.85:
                    return True
            else:
                if current_area >= 0:
                    return True

        return False

    def _check_top_divergence(self, pen: Pen) -> bool:
        """
        顶背驰判断

        顶背驰定义：
        在上升趋势中，当前上升笔创新高（高点比前一上升笔高），但MACD面积
        比前一上升笔小（或者MACD柱子高度比前一上升笔短），说明上涨动力减弱，
        可能出现反转向下。

        顶背驰条件：
        1. 当前笔是上升笔（direction == "up"）
        2. 当前笔的高点 > 前一个上升笔的高点（创新高）
        3. 当前笔的MACD面积 < 前一个上升笔的MACD面积（面积缩小）

        注意：比较的是两个连续的同向笔（都是上升笔），
        需要找到当前笔之前的那个上升笔进行比较。

        参数：
        :param pen: 当前的笔（应该是上升笔）
        :return: 是否发生顶背驰
        """
        if len(self.pens) < 2:
            return False

        current_pen = pen
        prev_pen = None

        # 查找前一个上升笔
        for i in range(len(self.pens) - 2, -1, -1):
            if self.pens[i].direction == "down":
                # 找到前一个下降笔，跳过
                continue
            prev_pen = self.pens[i]
            break

        if prev_pen is None:
            return False

        # 获取当前笔和前一个上升笔的高点
        current_high = current_pen.high
        prev_high = prev_pen.high

        # 获取对应笔的MACD面积
        current_area = current_pen.macd_area
        prev_area = prev_pen.macd_area

        # 顶背驰判断：价格创新高且MACD面积明显缩小（<前面积的90%）
        if current_high > prev_high:
            if prev_area != 0:
                ratio = current_area / prev_area
                logger.info(f"顶背驰检测: 当前高点={current_high}, 前高点={prev_high}, "
                           f"当前MACD面积={current_area:.4f}, 前MACD面积={prev_area:.4f}, "
                           f"比值={ratio:.4f}, 阈值=0.85")
                if current_area < prev_area * 0.85:
                    return True
            else:
                if current_area < 0:
                    return True

        return False

    def _check_top_divergence_relaxed(self, pen: Pen) -> bool:
        """
        宽松版顶背驰判断（不强制要求创新高）

        在震荡或下跌趋势中，上升笔往往无法创新高，
        但只要MACD面积明显缩小，就说明上涨动能衰竭，
        可能出现反转向下。

        宽松顶背驰条件：
        1. 当前笔是上升笔（direction == "up"）
        2. 当前笔的MACD面积 < 前一个上升笔的MACD面积的80%（面积显著缩小）
        3. 可选：当前高点不超过前高的105%（避免极端情况）

        参数：
        :param pen: 当前的笔（应该是上升笔）
        :return: 是否发生宽松顶背驰
        """
        if len(self.pens) < 2:
            return False

        current_pen = pen
        prev_pen = None

        # 查找前一个上升笔
        for i in range(len(self.pens) - 2, -1, -1):
            if self.pens[i].direction == "down":
                continue
            prev_pen = self.pens[i]
            break

        if prev_pen is None:
            return False

        # 获取MACD面积
        current_area = current_pen.macd_area
        prev_area = prev_pen.macd_area

        # 面积必须为正数（上升笔的MACD面积应该为正）
        if current_area <= 0 or prev_area <= 0:
            return False

        # 宽松条件：面积缩小到前一笔的80%以下
        area_ratio = current_area / prev_area if prev_area != 0 else 1.0
        
        if area_ratio < 0.8:
            logger.debug(f"[ChanStrategy] 检测到宽松顶背驰: "
                        f"面积比={area_ratio:.2f} ({current_area:.2f}/{prev_area:.2f})")
            return True

        return False

    def _check_resistance_reversal(self, pen: Pen) -> bool:
        """
        均线压力位反转检测

        当价格上涨触及中期均线（MA60）压力位后出现回落迹象时，
        即使没有明显的顶背驰，也应该考虑卖出。

        判断条件：
        1. 当前笔是上升笔
        2. 笔的高点接近或超过MA60（偏差<1%）
        3. 当前K线出现看跌形态（可选：简化版本省略此条件）

        参数：
        :param pen: 当前的笔（应该是上升笔）
        :return: 是否检测到压力位反转
        """
        if not hasattr(self, 'ma_medium') or self.ma_medium.empty:
            return False

        if len(self.ma_medium) == 0:
            return False

        # 获取最新的MA60价格
        ma60_price = self.ma_medium.iloc[-1]

        if ma60_price is None or ma60_price <= 0:
            return False

        # 检查笔的高点是否接近MA60
        high_price = pen.high
        deviation = abs(high_price - ma60_price) / ma60_price

        # 如果高点在MA60附近（偏差<1%），认为是触及压力位
        if deviation < 0.01:
            logger.debug(f"[ChanStrategy] 检测到MA60压力位反转: "
                        f"高点{high_price:.2f} | MA60:{ma60_price:.2f} | 偏差:{deviation*100:.2f}%")
            return True

        return False

    async def on_bar(self, bar_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        K线数据更新回调

        当有新的K线数据更新时调用此方法

        参数：
        :param bar_data: K线数据字典
        :return: 交易信号字典
        """
        return self.generate_signal()

    async def on_order_update(self, order_data: Dict[str, Any]) -> None:
        """
        订单更新回调

        当有订单状态更新时调用此方法

        参数：
        :param order_data: 订单数据字典
        """
        logger.info(f"[{self.name}] 订单更新: {order_data}")

    def get_daily_trend(self) -> str:
        """
        获取日线级别的趋势方向（用于过滤信号）

        使用MA5/MA10/MA20均线系统判断趋势：
        - strong_up: 强上升趋势 (价格 > MA5 > MA10 > MA20)
        - up: 上升趋势 (价格 > MA10 > MA20)
        - strong_down: 强下降趋势 (价格 < MA5 < MA10 < MA20)
        - down: 下降趋势 (价格 < MA10 < MA20)
        - sideways: 震荡趋势 (其他情况)

        Returns:
            str: 趋势方向字符串
        """
        if not hasattr(self, 'df_1d') or self.df_1d.empty or len(self.df_1d) < 25:
            return "unknown"

        try:
            df = self.df_1d
            current_price = float(df['close'].iloc[-1])

            ma5 = df['close'].rolling(window=5).mean().iloc[-1]
            ma10 = df['close'].rolling(window=10).mean().iloc[-1]
            ma20 = df['close'].rolling(window=20).mean().iloc[-1]

            if pd.isna(ma5) or pd.isna(ma10) or pd.isna(ma20):
                return "unknown"

            if current_price > ma5 > ma10 > ma20:
                return "strong_up"
            elif current_price > ma10 > ma20:
                return "up"
            elif current_price < ma5 < ma10 < ma20:
                return "strong_down"
            elif current_price < ma10 < ma20:
                return "down"
            else:
                return "sideways"

        except Exception as e:
            logger.warning(f"[ChanStrategy] 日线趋势判断失败: {e}")
            return "unknown"

    def _get_trend_filter_result(self, action: str) -> float:
        """
        根据EMA趋势 + EMA120中期方向返回仓位系数
        """
        ema_trend = self._get_ema_trend()

        if ema_trend in ("neutral", "unknown"):
            return 1.0

        if ema_trend == "bearish" and action == "BUY":
            logger.info(f"[ChanStrategy] 空头趋势，拒绝BUY信号（仅顺势做多）")
            return 0.0

        if ema_trend == "bullish" and action == "SELL":
            logger.info(f"[ChanStrategy] 多头趋势，拒绝SELL信号（仅顺势做空）")
            return 0.0

        # === 中期方向偏置：SMA120斜率判断宏观方向 ===
        if action == "SELL":
            ma_long = self.ma_long
            if not ma_long.empty and len(ma_long) >= 20:
                sma_now = float(ma_long.iloc[-1])
                sma_20ago = float(ma_long.iloc[-20])
                if sma_20ago > 0 and sma_now / sma_20ago > 1.005:
                    logger.info(f"[ChanStrategy] SMA120中期上行(增速{(sma_now/sma_20ago-1)*100:.2f}%)，拒绝SELL信号")
                    return 0.0
        if action == "BUY":
            ma_long = self.ma_long
            if not ma_long.empty and len(ma_long) >= 20:
                sma_now = float(ma_long.iloc[-1])
                sma_20ago = float(ma_long.iloc[-20])
                if sma_20ago > 0 and sma_now / sma_20ago < 0.995:
                    logger.info(f"[ChanStrategy] SMA120中期下行(跌幅{(1-sma_now/sma_20ago)*100:.2f}%)，拒绝BUY信号")
                    return 0.0

        return 1.0

    def _calculate_trend_strength(self) -> float:
        """
        计算当前趋势强度 (0.0 ~ 1.0)

        基于 EMA20斜率 和 EMA20/EMA60乖离率 综合判断：
        - 0.0-0.3: 弱趋势/震荡
        - 0.3-0.5: 中等趋势
        - 0.5-0.8: 较强趋势
        - 0.8-1.0: 强趋势
        """
        df = self.df_30m
        if df is None or df.empty or len(df) < 65:
            return 0.3  # 数据不足，默认弱趋势

        if 'EMA20' not in df.columns or 'EMA60' not in df.columns:
            return 0.3

        # EMA20的斜率（最近5根K线的变化率）
        recent_ema20 = df['EMA20'].iloc[-5:].astype(float)
        if len(recent_ema20) < 5:
            return 0.3
        slope = (recent_ema20.iloc[-1] - recent_ema20.iloc[0]) / recent_ema20.iloc[0]

        # EMA20与EMA60的乖离率
        ema20_val = float(df['EMA20'].iloc[-1])
        ema60_val = float(df['EMA60'].iloc[-1])
        divergence = abs(ema20_val - ema60_val) / ema60_val

        # 综合强度 (斜率权重0.4, 乖离率权重0.6)
        slope_norm = min(abs(slope) * 100, 1.0)  # 斜率归一化
        div_norm = min(divergence * 20, 1.0)      # 乖离率归一化

        strength = 0.4 * slope_norm + 0.6 * div_norm
        return round(min(strength, 1.0), 2)

    def _calculate_rsi(self, period: int = 14) -> Optional[float]:
        closes = self.df_30m['close'].values
        if len(closes) < period + 1:
            return None
        try:
            deltas = np.diff(closes[-period-1:])
            gains = np.where(deltas > 0, deltas, 0.0)
            losses = np.where(deltas < 0, -deltas, 0.0)
            avg_gain = np.mean(gains)
            avg_loss = np.mean(losses)
            if avg_loss == 0:
                return 100.0
            rsi = 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
            return round(rsi, 1)
        except Exception:
            return None

    def should_filter_by_trend(self, action: str) -> bool:
        """
        根据 EMA 趋势决定是否过滤信号 (替代日线趋势判断)

        使用 EMA20/EMA60 双均线系统识别趋势方向：
        
        过滤规则：
        - 空头趋势 (bearish)：拒绝做多信号（顺势而为）
        - 多头趋势 (bullish)：拒绝做空信号（顺势而为）
        - 震荡市 (neutral)：不过滤，允许双向交易

        趋势判断标准：
        - 多头趋势：EMA20 > EMA60 且 价格 > EMA20
        - 空头趋势：EMA20 < EMA60 且 价格 < EMA20
        - 震荡市：其他情况

        Args:
            action: 信号类型 ("BUY" 或 "SELL")

        Returns:
            bool: True表示应该过滤（拒绝信号），False表示允许通过
        """
        ema_trend = self._get_ema_trend()

        # 空头趋势中拒绝做多
        if ema_trend == "bearish" and action == "BUY":
            logger.info(
                f"[ChanStrategy] 📉 EMA趋势过滤: {ema_trend}趋势(EMA20<EMA60, 价格<EMA20)，"
                f"拒绝BUY信号（只允许做空或等待）"
            )
            return True

        # 多头趋势中拒绝做空
        if ema_trend == "bullish" and action == "SELL":
            logger.info(
                f"[ChanStrategy] 📈 EMA趋势过滤: {ema_trend}趋势(EMA20>EMA60, 价格>EMA20)，"
                f"拒绝SELL信号（只允许做多或等待）"
            )
            return True

        # 震荡市或未知状态：不过滤
        return False

    def check_volatility_filter(self) -> bool:
        """
        波动率过滤器（方案6：ATR自适应）

        过滤规则：
        - ATR过低（<均值的50%）：市场处于休眠期，容易假突破，拒绝交易
        - ATR过高（>均值的200%）：市场波动过大，风险过高，拒绝交易
        - 正常范围：允许交易

        Returns:
            bool: True表示通过过滤（允许交易），False表示拒绝
        """
        try:
            if not hasattr(self, 'df_30m') or self.df_30m.empty or len(self.df_30m) < 30:
                return True  # 数据不足时默认通过

            # 计算当前ATR和平均ATR
            df = self.df_30m
            high = df['high'].astype(float)
            low = df['low'].astype(float)
            close = df['close'].astype(float)
            prev_close = close.shift(1)

            tr1 = high - low
            tr2 = abs(high - prev_close)
            tr3 = abs(low - prev_close)
            true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

            # 使用20周期ATR作为基准
            atr_current = true_range.ewm(span=14, adjust=False).mean().iloc[-1]
            atr_avg = true_range.ewm(span=20, adjust=False).mean().iloc[-20:].mean()

            if pd.isna(atr_current) or pd.isna(atr_avg) or atr_avg == 0:
                return True

            atr_ratio = atr_current / atr_avg

            # 过低波动率：拒绝交易（避免假突破）
            if atr_ratio < 0.5:
                logger.info(
                    f"[ChanStrategy] 📊 波动率过滤: ATR比率={atr_ratio:.2f} (<0.5)，"
                    f"市场休眠，拒绝交易"
                )
                return False

            # 过高波动率：拒绝交易（风险太大）
            if atr_ratio > 3.5:  # 从2.0放宽至3.5（适应180天数据的大波动）
                logger.info(
                    f"[ChanStrategy] 📊 波动率过滤: ATR比率={atr_ratio:.2f} (>3.5)，"
                    f"波动过大，拒绝交易"
                )
                return False

            # 正常范围：允许交易
            logger.debug(f"[ChanStrategy] 📊 波动率正常: ATR比率={atr_ratio:.2f}")
            return True

        except Exception as e:
            logger.warning(f"[ChanStrategy] 波动率检查失败: {e}")
            return True  # 出错时默认通过

    def check_time_filter(self) -> bool:
        """
        时间过滤器（方案8：避开低流动性时段）

        过滤规则：
        - 亚盘时段（UTC 00:00-08:00）：流动性较低，拒绝交易
        - 欧盘/美盘重叠时段：流动性最好，优先交易

        Returns:
            bool: True表示在可交易时段，False表示应跳过
        """
        try:
            if not hasattr(self, 'df_30m') or self.df_30m.empty:
                return True

            current_time = self.df_30m['open_time'].iloc[-1]

            if isinstance(current_time, str):
                from datetime import datetime
                current_time = datetime.strptime(current_time, "%Y-%m-%d %H:%M:%S")

            hour = current_time.hour

            # UTC时间转换（假设数据是UTC时间）
            # 亚盘：00:00-08:00 UTC (北京时间08:00-16:00)
            # 优化：改为降仓50%而非完全拒绝
            if 0 <= hour < 8:
                logger.info(
                    f"[ChanStrategy] ⏰ 亚盘时段({hour:02d}:00 UTC)，"
                    f"降低仓位至50%以控制流动性风险"
                )
                self._time_position_mult = 0.5
                return True  # 不拒绝，但降低仓位

            # 欧盘美盘重叠：13:00-17:00 UTC (最佳时段)
            if 13 <= hour < 17:
                logger.debug(f"[ChanStrategy] ⏰ 最佳时段: {hour:02d}:00 UTC")
                self._time_position_mult = 1.0
                return True

            # 其他时段：正常仓位
            self._time_position_mult = 1.0
            return True

        except Exception as e:
            logger.warning(f"[ChanStrategy] 时间检查失败: {e}")
            return True

    def calculate_target_price(self, action: str) -> Optional[float]:
        """
        计算目标价格（用于盈亏比计算）

        多单目标：最近阻力位（MA60或前高）
        空单目标：最近支撑位（MA60或前低）

        Args:
            action: 信号类型 ("BUY" 或 "SELL")

        Returns:
            float: 目标价格，无法计算时返回None
        """
        try:
            if not hasattr(self, 'ma_medium') or self.ma_medium.empty:
                return None

            current_price = float(self.df_30m['close'].iloc[-1])
            ma60 = float(self.ma_medium.iloc[-1]) if len(self.ma_medium) > 0 else None

            if action == "BUY":
                # 多单：取MA60和前高的较高者作为目标
                target = ma60 if ma60 and ma60 > current_price else None

                # 查找前高（最近10根K线的最高价）
                if len(self.df_30m) >= 10:
                    recent_high = self.df_30m['high'].iloc[-10:].max()
                    if target is None or recent_high > target:
                        target = recent_high

                # 如果都没有，使用当前价+3%
                if target is None:
                    target = current_price * 1.03

                return target

            else:  # SELL
                # 空单：取MA60和前低的较低者作为目标
                target = ma60 if ma60 and ma60 < current_price else None

                # 查找前低
                if len(self.df_30m) >= 10:
                    recent_low = self.df_30m['low'].iloc[-10:].min()
                    if target is None or recent_low < target:
                        target = recent_low

                # 如果都没有，使用当前价-3%
                if target is None:
                    target = current_price * 0.97

                return target

        except Exception as e:
            logger.warning(f"[ChanStrategy] 目标价计算失败: {e}")
            return None

    def check_risk_reward_ratio(
        self,
        action: str,
        entry_price: float,
        stop_loss: float
    ) -> Tuple[bool, float]:
        """
        检查盈亏比是否满足最低要求（>2:1才允许入场）

        Args:
            action: 信号类型 ("BUY" 或 "SELL")
            entry_price: 入场价格
            stop_loss: 止损价格

        Returns:
            tuple: (是否通过, 实际盈亏比)
        """
        MIN_RISK_REWARD_RATIO = 1.5  # 最低盈亏比要求（优化：2.5→1.5，增加交易机会）

        target_price = self.calculate_target_price(action)

        if target_price is None or stop_loss == 0:
            # 无法计算时默认通过（避免过度过滤）
            return True, 0.0

        # 计算风险和收益
        risk = abs(entry_price - stop_loss)

        if action == "BUY":
            reward = abs(target_price - entry_price)
        else:  # SELL
            reward = abs(entry_price - target_price)

        if risk == 0:
            return True, 0.0

        ratio = reward / risk

        if ratio >= MIN_RISK_REWARD_RATIO:
            logger.info(
                f"[ChanStrategy] ✅ 盈亏比通过: {ratio:.2f} >= {MIN_RISK_REWARD_RATIO} "
                f"(入场${entry_price:.2f}, 止损${stop_loss:.2f}, 目标${target_price:.2f})"
            )
            return True, ratio
        else:
            logger.info(
                f"[ChanStrategy] ❌ 盈亏比不足: {ratio:.2f} < {MIN_RISK_REWARD_RATIO} "
                f"(入场${entry_price:.2f}, 止损${stop_loss:.2f}, 目标${target_price:.2f})"
            )
            return False, ratio

    def generate_signal(self) -> Optional[Dict[str, Any]]:
        """
        生成交易信号（支持共振验证 + 信号去重）

        当 enable_resonance=True 时:
        - 在背驰检测后调用共振评估
        - 返回增强的信号字典（包含resonance_level等字段）

        当 enable_resonance=False 时:
        - 行为与原版完全一致（向后兼容）

        信号去重机制：
        - 做多信号至少间隔 long_signal_cooldown_bars 根K线
        - 做空信号至少间隔 short_signal_cooldown_bars 根K线
        - 多空信号独立冷却，互不影响
        - 避免同一背驰结构在连续多根K线重复触发

        返回：
        :return: 信号字典，包含以下字段：
                 - action: 信号类型，"BUY"、"SELL"或"HOLD"
                 - stop_loss: 止损价格
                 - reason: 信号原因说明
                 - position: 新持仓方向
                 - resonance_level: 共振等级（"none", "weak", "medium", "strong"）
                 - position_size_ratio: 建议仓位比例
                 - ma_info: 均线信息
        """
        if len(self.pens) < 2:
            return None

        last_pen = self.pens[-1]
        current_kline_idx = len(self.df_30m) - 1 if not self.df_30m.empty else 0

        # ===== 方案2：EMA趋势分级过滤（逆势降仓，不直接拒绝）=====
        if last_pen.direction == "down":
            self._trend_position_mult = self._get_trend_filter_result("BUY")
            if self._trend_position_mult == 0:
                return None
        elif last_pen.direction == "up":
            self._trend_position_mult = self._get_trend_filter_result("SELL")
            if self._trend_position_mult == 0:
                return None

        # ===== 方案6：波动率过滤器（ATR自适应）=====
        if not self.check_volatility_filter():
            return None

        # ===== 方案B：时间过滤器（亚盘降仓50%，不拒绝）=====
        self.check_time_filter()  # 设置 _time_position_mult (0.5 or 1.0)

        signal = {
            "action": "HOLD",
            "stop_loss": 0.0,
            "reason": "",
            "position": None,
            # 新增字段（默认值）
            "resonance_level": "none",
            "position_size_ratio": self.RESONANCE_POSITION_SIZING["none"],
            "ma_info": {}
        }

        # 更新冷却期计数器（多空独立递减）
        if self.long_signal_info["cooldown_counter"] > 0:
            self.long_signal_info["cooldown_counter"] -= 1
        if self.short_signal_info["cooldown_counter"] > 0:
            self.short_signal_info["cooldown_counter"] -= 1

        # ===== RSI确认（超买超卖过滤假信号）=====
        rsi = self._calculate_rsi()
        rsi_ok_buy = rsi is not None and rsi < 45
        rsi_ok_sell = rsi is not None and rsi > 55

        # 底背驰 -> 纯做多信号
        if last_pen.direction == "down":
            if self._check_bottom_divergence(last_pen):
                # 检查做多冷却期
                if (self.long_signal_info["action"] == "BUY" and
                    self.long_signal_info["pen_index"] == len(self.pens) - 1 and
                    self.long_signal_info["cooldown_counter"] > 0):
                    logger.debug(f"[ChanStrategy] BUY信号冷却期中，跳过 (剩余{self.long_signal_info['cooldown_counter']}根K线)")
                    return None

                if not rsi_ok_buy:
                    logger.info(f"[ChanStrategy] RSI={rsi:.1f}偏高，跳过BUY信号（需RSI<45）")
                    return None

                # 原始信号
                base_action = "BUY"
                base_reason = f"{self.time_frame}底背驰"

                # 共振评估（如果启用）
                if self.enable_resonance:
                    resonance_level, reason = self._evaluate_buy_signal_resonance(last_pen)
                    signal.update({
                        "action": base_action,
                        "stop_loss": last_pen.low * 0.995,
                        "reason": reason,
                        "position": "long",
                        "resonance_level": resonance_level,
                        "position_size_ratio": self.RESONANCE_POSITION_SIZING[resonance_level] * self._trend_position_mult * self._time_position_mult,
                        "ma_info": self._get_ma_signal(last_pen.low) if hasattr(self, '_get_ma_signal') else {},
                        "trend_mult": self._trend_position_mult,
                        "time_mult": self._time_position_mult
                    })
                else:
                    # 禁用共振时使用原始格式
                    signal.update({
                        "action": base_action,
                        "stop_loss": last_pen.low * 0.995,
                        "reason": base_reason,
                        "position": "long"
                    })

                # 记录做多信号信息并启动冷却期
                self.long_signal_info.update({
                    "action": "BUY",
                    "pen_index": len(self.pens) - 1,
                    "kline_index": current_kline_idx,
                    "cooldown_counter": self.long_signal_cooldown_bars
                })

                # ===== 方案4：盈亏比过滤器 =====
                rr_pass, rr_ratio = self.check_risk_reward_ratio(
                    "BUY",
                    last_pen.low,
                    signal["stop_loss"]
                )
                if not rr_pass:
                    return None

                signal["risk_reward_ratio"] = rr_ratio

                logger.info(f"[ChanStrategy] 信号: {signal}")
                return signal

        # 顶背驰 -> 纯做空信号（仅严格顶背驰）
        elif last_pen.direction == "up":
            if self._check_top_divergence(last_pen):
                # 检查做空冷却期
                if (self.short_signal_info["action"] == "SELL" and
                    self.short_signal_info["pen_index"] == len(self.pens) - 1 and
                    self.short_signal_info["cooldown_counter"] > 0):
                    logger.debug(f"[ChanStrategy] SELL信号冷却期中，跳过 (剩余{self.short_signal_info['cooldown_counter']}根K线)")
                    return None

                if not rsi_ok_sell:
                    logger.info(f"[ChanStrategy] RSI={rsi:.1f}偏低，跳过SELL信号（需RSI>55）")
                    return None

                base_action = "SELL"
                base_reason = f"{self.time_frame}顶背驰"

                if self.enable_resonance:
                    resonance_level, reason = self._evaluate_sell_signal_resonance(last_pen)
                    signal.update({
                        "action": base_action,
                        "stop_loss": last_pen.high * 1.005,
                        "reason": reason,
                        "position": "short",
                        "resonance_level": resonance_level,
                        "position_size_ratio": self.RESONANCE_POSITION_SIZING[resonance_level] * self._trend_position_mult * self._time_position_mult,
                        "ma_info": self._get_ma_signal(last_pen.high) if hasattr(self, '_get_ma_signal') else {},
                        "trend_mult": self._trend_position_mult,
                        "time_mult": self._time_position_mult
                    })
                else:
                    signal.update({
                        "action": base_action,
                        "stop_loss": last_pen.high * 1.005,
                        "reason": base_reason,
                        "position": "short"
                    })

                self.short_signal_info.update({
                    "action": "SELL",
                    "pen_index": len(self.pens) - 1,
                    "kline_index": current_kline_idx,
                    "cooldown_counter": self.short_signal_cooldown_bars
                })

                rr_pass, rr_ratio = self.check_risk_reward_ratio(
                    "SELL",
                    last_pen.high,
                    signal["stop_loss"]
                )
                if not rr_pass:
                    return None

                signal["risk_reward_ratio"] = rr_ratio

                logger.info(f"[ChanStrategy] 信号: {signal}")
                return signal

        return signal

    def get_status(self) -> Dict[str, Any]:
        """
        获取策略状态信息

        返回当前策略的状态，包括：
        - symbol: 交易对
        - fractals_count: 识别出的分型数量
        - pens_count: 识别出的笔数量
        - segments_count: 识别出的线段数量
        - daily_trend: 日线趋势方向
        - last_pen: 最后一笔的信息（方向、高点、低点）

        返回：
        :return: 策略状态字典
        """
        return {
            "symbol": self.symbol,
            "fractals_count": len(self.fractals),
            "pens_count": len(self.pens),
            "segments_count": len(self.segments),
            "daily_trend": self._get_daily_trend(),
            "last_pen": {
                "direction": self.pens[-1].direction if self.pens else None,
                "high": self.pens[-1].high if self.pens else None,
                "low": self.pens[-1].low if self.pens else None
            }
        }


class ChanStrategyExecutor:
    """
    缠论策略执行器

    用于实时运行缠论策略的执行器类。负责：
    1. 定期获取最新K线数据
    2. 调用ChanStrategy进行数据处理和信号生成
    3. 根据生成的信号执行实际的交易操作（买入/卖出）

    使用方式：
    1. 创建Executor实例，指定交易对、时间周期等参数
    2. 调用start()方法启动执行器
    3. 执行器会在check_interval时间间隔内循环执行策略
    4. 调用stop()方法停止执行器

    入参说明：
    - client: 交易所API客户端，用于获取持仓信息和下单交易
    - symbol: 交易对符号，如"BTCUSDT"
    - time_frame: K线时间周期，如"5m"、"30m"
    - check_interval: 检查间隔（秒），默认60秒
    - use_binance_client: 是否使用Binance客户端获取数据
    """

    def __init__(
        self,
        client,  # BinanceRestClient
        symbol: str = "BTCUSDT",
        time_frame: str = "30m",
        check_interval: int = 60,
        use_binance_client: bool = True
    ):
        """
        初始化策略执行器

        参数：
        :param client: 交易所API客户端实例
        :param symbol: 交易对符号
        :param time_frame: K线时间周期
        :param check_interval: 检查间隔（秒）
        :param use_binance_client: 是否使用Binance客户端获取数据
        """
        self.client = client
        self.strategy = ChanStrategy(symbol=symbol, time_frame=time_frame, use_binance_client=use_binance_client)
        self.symbol = symbol
        self.time_frame = time_frame
        self.check_interval = check_interval
        self.is_running = False
        self.market_data = MarketDataClient()

    async def start(self):
        """
        启动策略执行器

        启动流程：
        1. 设置运行状态为True
        2. 初始化策略（获取数据、进行处理）
        3. 进入循环执行模式，定期运行策略
        """
        logger.info(f"[ChanStrategyExecutor] 启动策略执行器")
        self.is_running = True

        initialized = await self.strategy.initialize(self.symbol)
        if not initialized:
            logger.error(f"[ChanStrategyExecutor] 策略初始化失败")
            return

        try:
            while self.is_running:
                await self._run_once()
                await asyncio.sleep(self.check_interval)
        except Exception as e:
            logger.error(f"[ChanStrategyExecutor] 策略执行异常: {str(e)}")
        finally:
            await self.market_data.close()

    async def stop(self):
        """
        停止策略执行器

        设置运行状态为False，循环将自动退出
        """
        logger.info(f"[ChanStrategyExecutor] 停止策略执行器")
        self.is_running = False

    async def _run_once(self):
        """
        执行一次完整的策略运行

        执行步骤：
        1. 获取最新的K线数据（指定周期 + 日线）
        2. 更新策略的数据
        3. 处理数据，识别分型、笔、线段
        4. 生成交易信号
        5. 如果有信号（非HOLD），执行交易
        """
        try:
            if self.strategy.use_binance_client:
                # 使用BinanceRestClient获取K线数据
                logger.info(f"[ChanStrategyExecutor] 使用BinanceRestClient获取K线数据，symbol={self.symbol}, time_frame={self.time_frame}")
                binance_client = BinanceRestClient()
                try:
                    # 根据时间周期获取K线数据
                    logger.info(f"[ChanStrategyExecutor] 获取{self.time_frame}K线数据...")
                    continuous_klines = await binance_client.get_continuous_klines(
                        pair=self.symbol,
                        contractType="PERPETUAL",
                        interval=self.time_frame,
                        limit=800  # 增加数据量以提高策略准确性
                    )

                    # 检查返回数据格式
                    if isinstance(continuous_klines, list) and continuous_klines:
                        logger.info(f"[ChanStrategyExecutor] 获取到 {len(continuous_klines)} 条{self.time_frame}K线数据")
                        if self.time_frame == "5m":
                            self.df_5m = binance_klines_to_dataframe(continuous_klines)
                        else:
                            self.df_30m = binance_klines_to_dataframe(continuous_klines)
                    else:
                        logger.error(f"[ChanStrategyExecutor] {self.time_frame}K线数据格式错误: {continuous_klines}")
                        return

                    # 获取日线K线
                    logger.info(f"[ChanStrategyExecutor] 获取日线K线数据...")
                    daily_klines = await binance_client.get_continuous_klines(
                        pair=self.symbol,
                        contractType="PERPETUAL",
                        interval="1d",
                        limit=200
                    )

                    # 检查返回数据格式
                    if isinstance(daily_klines, list) and daily_klines:
                        logger.info(f"[ChanStrategyExecutor] 获取到 {len(daily_klines)} 条日线K线数据")
                        self.df_daily = binance_klines_to_dataframe(daily_klines)
                    else:
                        logger.error(f"[ChanStrategyExecutor] 日线K线数据格式错误: {daily_klines}")
                        return
                finally:
                    await binance_client.close()
            else:
                # 使用原有的market_data获取K线数据
                logger.info(f"[ChanStrategyExecutor] 使用market_data获取K线数据，symbol={self.symbol}, time_frame={self.time_frame}")
                if self.time_frame == "5m":
                    # 假设存在get_5m_klines函数
                    try:
                        from ..data.market_data import get_5m_klines
                        self.df_5m = await get_5m_klines(self.symbol, 800)
                    except ImportError:
                        logger.error(f"[ChanStrategyExecutor] 未找到get_5m_klines函数")
                        return
                else:
                    self.df_30m = await get_30m_klines(self.symbol, 800)
                self.df_daily = await get_daily_klines(self.symbol, 200)

            # 检查数据是否获取成功
            time_frame_data_empty = False
            if self.time_frame == "5m":
                time_frame_data_empty = self.df_5m.empty
            else:
                time_frame_data_empty = self.df_30m.empty

            if time_frame_data_empty or self.df_daily.empty:
                logger.warning(f"[ChanStrategyExecutor] 获取数据为空，{self.time_frame}数据: {len(self.df_5m) if self.time_frame == '5m' else len(self.df_30m)} 条, 日线数据: {len(self.df_daily)} 条")
                return

            logger.info(f"[ChanStrategyExecutor] 数据获取成功，开始处理数据...")
            if self.time_frame == "5m":
                self.strategy.df_5m = self.df_5m
            else:
                self.strategy.df_30m = self.df_30m
            self.strategy.df_daily = self.df_daily
            self.strategy._process_data()
            logger.info(f"[ChanStrategyExecutor] 数据处理完成，识别到 {len(self.strategy.fractals)} 个分型, {len(self.strategy.pens)} 笔")

            signal = self.strategy.generate_signal()
            logger.info(f"[ChanStrategyExecutor] 生成交易信号: {signal}")

            if signal and signal["action"] != "HOLD":
                logger.info(f"[ChanStrategyExecutor] 执行交易信号: {signal['action']}")
                await self._execute_signal(signal)

        except Exception as e:
            logger.error(f"[ChanStrategyExecutor] 执行异常: {str(e)}")

    async def _execute_signal(self, signal: Dict[str, Any]):
        """
        执行交易信号

        交易执行逻辑：
        1. 获取当前持仓情况
        2. 获取当前账户余额
        3. 根据信号类型执行交易：
           - BUY信号：如果有空单先平仓，然后开多单
           - SELL信号：如果有多单先平仓，然后开空单
        4. 计算下单数量（投入比例 * 杠杆）
        5. 设置止损（多单：爆仓价120%，空单：爆仓价80%）

        参数：
        :param signal: 交易信号字典，包含action、stop_loss等字段
        
        配置参数：
        - 投入比例：默认10%（可配置）
        - 杠杆倍数：默认50倍（可配置）
        """
        try:
            # 配置参数
            investment_ratio = 0.10  # 每次投入总金额的10%
            leverage = 50  # 50倍杠杆

            # 获取当前持仓情况
            position = await self.client.get_positions(self.symbol)
            
            # 获取当前账户余额
            balance = await self.client.get_balance()
            usdt_balance = float(balance.get("USDT", 0))
            
            # 获取当前价格
            ticker = await self.client.get_ticker(self.symbol)
            current_price = float(ticker.get("lastPrice", 0))

            # BUY信号：买入做多
            if signal["action"] == "BUY":
                # 检查是否有空头持仓，如果有先平仓
                short_positions = [p for p in position if p.get("positionAmt", 0) < 0]
                if short_positions:
                    logger.info(f"[ChanStrategyExecutor] 有空单持仓，先平仓")
                    for pos in short_positions:
                        close_result = await self.client.place_order(
                            symbol=self.symbol,
                            side="BUY",
                            position_side="SHORT",
                            order_type="MARKET",
                            quantity=abs(float(pos["positionAmt"]))
                        )
                        logger.info(f"[ChanStrategyExecutor] 平空单结果: {close_result}")

                # 计算下单数量
                investment_amount = usdt_balance * investment_ratio
                quantity = (investment_amount * leverage) / current_price
                quantity = round(quantity, 3)  # 保留3位小数

                # 计算止损价格（多单止损 = 爆仓价格 * 120%）
                # 爆仓价格 ≈ 开仓价格 * (1 - 1/杠杆)
                liquidation_price = current_price * (1 - 1/leverage)
                stop_loss_price = liquidation_price * 1.2

                # 开多单
                result = await self.client.place_order(
                    symbol=self.symbol,
                    side="BUY",
                    position_side="LONG",
                    order_type="MARKET",
                    quantity=quantity
                )
                logger.info(f"[ChanStrategyExecutor] 买入下单结果: {result}")
                logger.info(f"[ChanStrategyExecutor] 投入金额: ${investment_amount:.2f}, 数量: {quantity}, 杠杆: {leverage}x, 止损: {stop_loss_price:.2f}")

            # SELL信号：卖出做空
            elif signal["action"] == "SELL":
                # 检查是否有多头持仓，如果有先平仓
                long_positions = [p for p in position if p.get("positionAmt", 0) > 0]
                if long_positions:
                    logger.info(f"[ChanStrategyExecutor] 有多单持仓，先平仓")
                    for pos in long_positions:
                        close_result = await self.client.place_order(
                            symbol=self.symbol,
                            side="SELL",
                            position_side="LONG",
                            order_type="MARKET",
                            quantity=float(pos["positionAmt"])
                        )
                        logger.info(f"[ChanStrategyExecutor] 平多单结果: {close_result}")

                # 计算下单数量
                investment_amount = usdt_balance * investment_ratio
                quantity = (investment_amount * leverage) / current_price
                quantity = round(quantity, 3)  # 保留3位小数

                # 计算止损价格（空单止损 = 爆仓价格 * 80%）
                # 爆仓价格 ≈ 开仓价格 * (1 + 1/杠杆)
                liquidation_price = current_price * (1 + 1/leverage)
                stop_loss_price = liquidation_price * 0.8

                # 开空单
                result = await self.client.place_order(
                    symbol=self.symbol,
                    side="SELL",
                    position_side="SHORT",
                    order_type="MARKET",
                    quantity=quantity
                )
                logger.info(f"[ChanStrategyExecutor] 卖出下单结果: {result}")
                logger.info(f"[ChanStrategyExecutor] 投入金额: ${investment_amount:.2f}, 数量: {quantity}, 杠杆: {leverage}x, 止损: {stop_loss_price:.2f}")

        except Exception as e:
            logger.error(f"[ChanStrategyExecutor] 执行信号失败: {str(e)}")


if __name__ == "__main__":
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import asyncio
    from strategies.chan_strategy import ChanStrategy

    async def test():
        # 测试30分钟级别
        print("=== 测试30分钟级别策略 ===")
        strategy_30m = ChanStrategy(symbol="BTCUSDT", time_frame="30m")
        if await strategy_30m.initialize("BTCUSDT"):
            status = strategy_30m.get_status()
            print("30分钟策略状态:", status)

            signal = strategy_30m.generate_signal()
            print("30分钟交易信号:", signal)

        # 测试5分钟级别
        print("\n=== 测试5分钟级别策略 ===")
        strategy_5m = ChanStrategy(symbol="BTCUSDT", time_frame="5m")
        if await strategy_5m.initialize("BTCUSDT"):
            status = strategy_5m.get_status()
            print("5分钟策略状态:", status)

            signal = strategy_5m.generate_signal()
            print("5分钟交易信号:", signal)

    asyncio.run(test())
