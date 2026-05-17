"""
多周期共振底分型预判策略 (Multi-Timeframe Resonance Bottom Fractal Strategy)

核心逻辑：
1. 4小时K线检测价格进入支撑区域+底分型雏形(K1/K2)
2. 30分钟K线检测4类确认信号（底背离/看涨形态/趋势突破/金叉）
3. 满足>=2个信号触发试探性入场（40%仓位）
4. 4小时K3收盘>K2最高价确认加仓（60%仓位）
5. 多层风控：单笔2%止损、连续3次止损暂停、日亏损5%停止
6. 【新增】K3形成过程中提前入场：通过15分钟级别一买/二买分析
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .base_strategy import BaseStrategy
from .chan_strategy import ChanStrategy
from .chan_first_buy_strategy import ChanTheoryFirstBuyAnalyzer
from ..utils.indicators import calculate_macd, binance_klines_to_dataframe

logger = logging.getLogger(__name__)


@dataclass
class MTFPositionState:
    direction: Optional[str] = None
    entry_count: int = 0
    probe_entry_price: float = 0.0
    probe_qty: float = 0.0
    confirm_added: bool = False
    is_early_entry: bool = False
    avg_entry_price: float = 0.0
    total_position_size: float = 0.0
    k1_idx: int = -1
    k2_idx: int = -1
    k3_idx: int = -1
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0


@dataclass
class BottomFractalK12Structure:
    has_structure: bool = False
    k1_idx: int = -1
    k2_idx: int = -1
    k3_idx: int = -1
    k1_low: float = 0.0
    k1_open: float = 0.0
    k1_close: float = 0.0
    k2_low: float = 0.0
    k2_high: float = 0.0
    k3_partial_low: float = 0.0
    k3_partial_high: float = 0.0
    k3_partial_close: float = 0.0
    is_k3_forming: bool = False
    is_in_second_half: bool = False
    confidence: float = 0.0


@dataclass
class TopFractalK12Structure:
    has_structure: bool = False
    k1_idx: int = -1
    k2_idx: int = -1
    k3_idx: int = -1
    k1_high: float = 0.0
    k1_open: float = 0.0
    k1_close: float = 0.0
    k2_high: float = 0.0
    k2_low: float = 0.0
    k3_partial_low: float = 0.0
    k3_partial_high: float = 0.0
    k3_partial_close: float = 0.0
    is_k3_forming: bool = False
    is_in_second_half: bool = False
    confidence: float = 0.0


class MultiTFFractalStrategy(BaseStrategy):

    def __init__(
        self,
        symbol: str = "ETHUSDC",
        support_levels: List[float] = None,
        support_threshold: float = 10.0,
        probe_ratio: float = 0.40,
        confirm_ratio: float = 0.40,
        leverage: int = 20,
        investment_ratio: float = 0.50,
        max_loss_per_trade_pct: float = 0.02,
        max_consecutive_stops: int = 3,
        max_daily_loss_pct: float = 0.05,
        trendline_period: int = 20,
        stop_offset: float = 5.0,
        resistance_levels: List[float] = None,
        resistance_threshold: float = 10.0,
        profit_loss_ratio: float = 2.5,
        enable_trend_filter: bool = True,
        enable_volume_filter: bool = True,
        atr_period: int = 14,
        atr_multiplier: float = 5.0,
        auto_levels: bool = True,
        min_signal_count: int = 2,
        enable_early_entry: bool = True,
        early_entry_min_confidence: float = 0.6,
        k3_second_half_threshold: float = 0.4,
        early_entry_ratio: float = 0.40,
        enable_early_short_entry: bool = True,
        early_short_entry_min_confidence: float = 0.6,
        early_short_entry_ratio: float = 0.40,
        min_early_entry_conditions: int = 2,
    ):
        super().__init__("MultiTFFractalStrategy")
        self.symbol = symbol
        self.support_levels = support_levels or []
        self.support_threshold = support_threshold
        self.probe_ratio = probe_ratio
        self.confirm_ratio = confirm_ratio
        self.leverage = leverage
        self.investment_ratio = investment_ratio
        self.max_loss_per_trade_pct = max_loss_per_trade_pct
        self.max_consecutive_stops = max_consecutive_stops
        self.max_daily_loss_pct = max_daily_loss_pct
        self.trendline_period = trendline_period
        self.stop_offset = stop_offset
        self.resistance_levels = resistance_levels or []
        self.resistance_threshold = resistance_threshold
        self.profit_loss_ratio = profit_loss_ratio
        self.enable_trend_filter = enable_trend_filter
        self.enable_volume_filter = enable_volume_filter
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.auto_levels = auto_levels
        self.min_signal_count = min_signal_count
        self._auto_levels_calculated = False
        self.enable_early_entry = enable_early_entry
        self.early_entry_min_confidence = early_entry_min_confidence
        self.k3_second_half_threshold = k3_second_half_threshold
        self.early_entry_ratio = early_entry_ratio

        self.df_4h: pd.DataFrame = pd.DataFrame()
        self.df_30m: pd.DataFrame = pd.DataFrame()
        self.df_15m: pd.DataFrame = pd.DataFrame()
        self.df_daily: pd.DataFrame = pd.DataFrame()

        self._macd_4h: Dict[str, pd.Series] = {}
        self._macd_30m: Dict[str, pd.Series] = {}
        self._macd_15m: Dict[str, pd.Series] = {}
        self._sma_4h: Dict[str, pd.Series] = {}

        self.position_state = MTFPositionState()
        self.fractals = []
        self.pens = []
        self.segments = []
        self.current_atr = 0.0
        self._last_processed_signal_ts: Optional[pd.Timestamp] = None
        self._chan = ChanStrategy(symbol=symbol, time_frame="4h", hg1=8, use_binance_client=False)
        self._chan_first_buy_analyzer = ChanTheoryFirstBuyAnalyzer()

        self._consecutive_stops: int = 0
        self._daily_pnl: float = 0.0
        self._current_date: Optional[date] = None
        self._trading_paused: bool = False
        self._daily_stopped: bool = False
        self._last_signal_time: Optional[pd.Timestamp] = None
        self._last_short_signal_time: Optional[pd.Timestamp] = None
        self._last_top_fractal_price: Optional[float] = None
        self._last_top_fractal_time: Optional[int] = None
        self._last_bottom_fractal_price: Optional[float] = None
        self._last_bottom_fractal_time: Optional[int] = None
        self._bottom_fractal_k12: BottomFractalK12Structure = BottomFractalK12Structure()
        self._top_fractal_k12: TopFractalK12Structure = TopFractalK12Structure()
        self._chan_first_sell_analyzer = ChanTheoryFirstBuyAnalyzer()
        self.enable_early_short_entry = enable_early_short_entry
        self.early_short_entry_min_confidence = early_short_entry_min_confidence
        self.early_short_entry_ratio = early_short_entry_ratio
        self.min_early_entry_conditions = min_early_entry_conditions

    def set_support_levels(self, levels: List[float]):
        self.support_levels = sorted(levels, reverse=True)

    def set_resistance_levels(self, levels: List[float]):
        self.resistance_levels = sorted(levels)

    async def initialize(self, symbol: str) -> bool:
        self.symbol = symbol
        self._current_date = datetime.now().date()
        self._daily_pnl = 0.0
        self._consecutive_stops = 0
        self._trading_paused = False
        self._daily_stopped = False
        logger.info(f"[MTF] 策略初始化: symbol={symbol}, 支撑位={self.support_levels}, 阻力位={self.resistance_levels}")
        return True

    async def on_bar(self, bar_data: Dict[str, Any], bar_idx: int = None) -> Optional[Dict[str, Any]]:
        return self.generate_signal()

    async def on_order_update(self, order_data: Dict[str, Any]) -> None:
        logger.info(f"[MTF] 订单更新: {order_data}")

    def inject_data(self, df_4h: pd.DataFrame, df_30m: pd.DataFrame, df_15m: pd.DataFrame = None, df_daily: pd.DataFrame = None):
        self.df_4h = df_4h.copy()
        self.df_30m = df_30m.copy()
        if not hasattr(self, '_df_30m_full') or len(df_30m) > len(self._df_30m_full):
            self._df_30m_full = df_30m.copy()
        if df_15m is not None and not df_15m.empty:
            self.df_15m = df_15m.copy()
            if not hasattr(self, '_df_15m_full') or len(df_15m) > len(self._df_15m_full):
                self._df_15m_full = df_15m.copy()
            self._calculate_indicators_15m()
        if df_daily is not None:
            self.df_daily = df_daily.copy()
        self._calculate_indicators()
        self._chan.df_30m = self.df_4h.copy()
        self._chan._process_data()
        self.fractals = getattr(self._chan, 'fractals', [])
        self.pens = getattr(self._chan, 'pens', [])
        self.segments = getattr(self._chan, 'segments', [])
        self.df_processed = getattr(self._chan, 'df_processed', pd.DataFrame()).copy()
        self._calculate_atr()
        self._calculate_auto_levels()
        logger.info(f"[MTF] 数据处理完成: 分型={len(self.fractals)}, 笔={len(self.pens)}, ATR={self.current_atr:.2f}")

    def _calculate_indicators(self):
        if not self.df_4h.empty:
            macd_4h, sig_4h, hist_4h = calculate_macd(
                self.df_4h["close"].astype(float)
            )
            self._macd_4h = {"macd": macd_4h, "signal": sig_4h, "histogram": hist_4h}
            self._calc_kdj_4h()
            self._sma_4h["SMA20"] = self.df_4h["close"].astype(float).rolling(20).mean()
            self._sma_4h["SMA60"] = self.df_4h["close"].astype(float).rolling(60).mean()

        if not self.df_30m.empty:
            macd_30m, sig_30m, hist_30m = calculate_macd(
                self.df_30m["close"].astype(float)
            )
            self._macd_30m = {"macd": macd_30m, "signal": sig_30m, "histogram": hist_30m}
            self._calc_kdj_30m()

    def _calc_kdj_4h(self):
        if self.df_4h.empty or len(self.df_4h) < 9:
            self._kdj_4h = {"k": pd.Series(dtype=float), "d": pd.Series(dtype=float), "j": pd.Series(dtype=float)}
            return
        high = self.df_4h["high"].astype(float)
        low = self.df_4h["low"].astype(float)
        close = self.df_4h["close"].astype(float)
        self._kdj_4h = self._calc_kdj(high, low, close)

    def _calc_kdj_30m(self):
        if self.df_30m.empty or len(self.df_30m) < 9:
            self._kdj_30m = {"k": pd.Series(dtype=float), "d": pd.Series(dtype=float), "j": pd.Series(dtype=float)}
            return
        high = self.df_30m["high"].astype(float)
        low = self.df_30m["low"].astype(float)
        close = self.df_30m["close"].astype(float)
        self._kdj_30m = self._calc_kdj(high, low, close)

    def _calc_kdj(self, high: pd.Series, low: pd.Series, close: pd.Series,
                  n: int = 9, m1: int = 3, m2: int = 3) -> Dict[str, pd.Series]:
        lowest_low = low.rolling(window=n).min()
        highest_high = high.rolling(window=n).max()
        rsv = (close - lowest_low) / (highest_high - lowest_low + 1e-10) * 100
        k = rsv.ewm(com=m1 - 1, adjust=False).mean()
        d = k.ewm(com=m2 - 1, adjust=False).mean()
        j = 3 * k - 2 * d
        return {"k": k, "d": d, "j": j}

    def _calculate_auto_levels(self):
        if not self.auto_levels or self.df_4h.empty or len(self.df_4h) < 30:
            return
        df = self.df_4h
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        recent_high = float(high.iloc[-60:].max())
        recent_low = float(low.iloc[-60:].min())
        recent_range = recent_high - recent_low

        supports = sorted([
            round(recent_low, 2),
            round(recent_low + recent_range * 0.15, 2),
            round(recent_low + recent_range * 0.30, 2),
            round(recent_low + recent_range * 0.45, 2),
        ])

        resistances = sorted([
            round(recent_low + recent_range * 0.55, 2),
            round(recent_low + recent_range * 0.70, 2),
            round(recent_low + recent_range * 0.85, 2),
            round(recent_high, 2),
        ])

        self.support_levels = supports
        self.resistance_levels = resistances

        self._auto_levels_calculated = True
        logger.info(f"[MTF] 自动支撑/阻力位: 支撑={self.support_levels}, 阻力={self.resistance_levels}")

    def _check_support_zone(self) -> Tuple[bool, float]:
        if self.df_4h.empty or not self.support_levels:
            return False, 0.0
        current_price = float(self.df_4h.iloc[-1]["close"])
        current_low = float(self.df_4h.iloc[-1]["low"])
        check_price = min(current_price, current_low)
        atr = getattr(self, 'current_atr', 0.0) or 0.0
        threshold = min(atr * 0.5, current_price * 0.01) if atr > 0 else current_price * 0.01
        for level in self.support_levels:
            if check_price <= level + threshold:
                logger.info(f"[MTF] 价格进入支撑区域: 当前={check_price:.2f}, 支撑位={level}, 阈值={threshold:.2f}")
                return True, level
        return False, 0.0

    def _calculate_atr(self) -> None:
        try:
            if self.df_4h is None or self.df_4h.empty or len(self.df_4h) < 15:
                self.current_atr = 0.0
                return
            df = self.df_4h
            high = df['high'].astype(float)
            low = df['low'].astype(float)
            close = df['close'].astype(float)
            prev_close = close.shift(1)
            tr1 = high - low
            tr2 = abs(high - prev_close)
            tr3 = abs(low - prev_close)
            true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = true_range.ewm(span=self.atr_period, adjust=False).mean()
            self.current_atr = float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0.0
        except Exception as e:
            logger.warning(f"[MTF] ATR计算失败: {e}")
            self.current_atr = 0.0

    def _check_4h_bottom_fractal_k1k2(self) -> BottomFractalK12Structure:
        """
        检测4小时底分型K1/K2结构
        
        K1: 下跌K线（收盘<开盘）
        K2: 最低点低于K1低点
        K3候选: 当前K线，低点高于K2低点
        
        Returns:
            BottomFractalK12Structure对象，包含检测结果
        """
        result = BottomFractalK12Structure()
        
        if len(self.df_4h) < 3:
            return result
        
        k1_idx = len(self.df_4h) - 3
        k2_idx = len(self.df_4h) - 2
        k3_idx = len(self.df_4h) - 1
        
        k1 = self.df_4h.iloc[k1_idx]
        k2 = self.df_4h.iloc[k2_idx]
        k3 = self.df_4h.iloc[k3_idx]
        
        k1_open = float(k1["open"])
        k1_close = float(k1["close"])
        k1_low = float(k1["low"])
        
        k2_low = float(k2["low"])
        k2_high = float(k2["high"])
        
        k3_partial_low = float(k3["low"])
        k3_partial_high = float(k3["high"])
        k3_partial_close = float(k3["close"])
        
        is_k1_down = k1_close < k1_open
        is_k2_lower_low = k2_low < k1_low
        is_k3_forming = k3_partial_low > k2_low
        
        if not (is_k1_down and is_k2_lower_low):
            return result
        
        confidence = 0.0
        if is_k1_down:
            confidence += 0.3
        if is_k2_lower_low:
            confidence += 0.3
        if is_k3_forming:
            confidence += 0.4
        
        result.has_structure = True
        result.k1_idx = k1_idx
        result.k2_idx = k2_idx
        result.k3_idx = k3_idx
        result.k1_low = k1_low
        result.k1_open = k1_open
        result.k1_close = k1_close
        result.k2_low = k2_low
        result.k2_high = k2_high
        result.k3_partial_low = k3_partial_low
        result.k3_partial_high = k3_partial_high
        result.k3_partial_close = k3_partial_close
        result.is_k3_forming = is_k3_forming
        result.is_in_second_half = self._is_in_candle_second_half()
        result.confidence = confidence
        
        logger.info(f"[MTF-提前入场] K1/K2底分型结构检测: "
                   f"K1_idx={k1_idx}, K2_idx={k2_idx}, K3_idx={k3_idx}, "
                   f"K1_down={is_k1_down}, K2_lower={is_k2_lower_low}, "
                   f"K3_forming={is_k3_forming}, second_half={result.is_in_second_half}, "
                   f"confidence={confidence:.2f}")
        
        return result

    def _is_in_candle_second_half(self) -> bool:
        """
        判断当前是否处于4小时K线的后半段
        
        逻辑: 获取当前4小时K线的开始时间，计算当前时间距离K线开始已过去多少分钟
        如果超过K线周期的50%，返回True
        
        Returns:
            bool: 是否处于K线后半段
        """
        if self.df_4h.empty:
            return False
        
        current_bar = self.df_4h.iloc[-1]
        
        if "open_time" not in current_bar:
            return True
        
        bar_open_time = current_bar["open_time"]
        current_time = pd.Timestamp.now()
        
        if isinstance(bar_open_time, str):
            bar_open_time = pd.to_datetime(bar_open_time)
        
        elapsed_minutes = (current_time - bar_open_time).total_seconds() / 60
        candle_duration = 240
        elapsed_ratio = elapsed_minutes / candle_duration
        
        is_second_half = elapsed_ratio >= self.k3_second_half_threshold
        
        if is_second_half:
            logger.info(f"[MTF-提前入场] K线后半段检测: 已过{elapsed_minutes:.1f}分钟/{candle_duration}分钟 ({elapsed_ratio:.2%})")
        
        return is_second_half

    def _calculate_indicators_15m(self):
        """计算15分钟K线技术指标"""
        if self.df_15m.empty or len(self.df_15m) < 20:
            return
        
        try:
            macd_15m, sig_15m, hist_15m = calculate_macd(
                self.df_15m["close"].astype(float)
            )
            self._macd_15m = {"macd": macd_15m, "signal": sig_15m, "histogram": hist_15m}
            self._calc_kdj_15m()
        except Exception as e:
            logger.warning(f"[MTF] 15分钟指标计算失败: {e}")
            self._macd_15m = {}

    def _calc_kdj_15m(self):
        """计算15分钟KDJ指标"""
        if self.df_15m.empty or len(self.df_15m) < 9:
            self._kdj_15m = {"k": pd.Series(dtype=float), "d": pd.Series(dtype=float), "j": pd.Series(dtype=float)}
            return
        high = self.df_15m["high"].astype(float)
        low = self.df_15m["low"].astype(float)
        close = self.df_15m["close"].astype(float)
        self._kdj_15m = self._calc_kdj(high, low, close)

    def _check_15m_first_buy(self) -> Tuple[bool, Dict[str, Any]]:
        """
        在15分钟K线中直接检测底背驰（MACD背离）
        
        检测最近100根K线中两个低点之间的背离：
        - 价格低点降低（新低 < 前低）
        - MACD DIF低点抬高（新低DIF > 前低DIF）
        
        Returns:
            Tuple[bool, Dict]: (是否检测到底背驰, 详细分析结果)
        """
        if self.df_15m.empty or len(self.df_15m) < 50:
            logger.info("[MTF-提前入场] 15分钟数据不足，无法检测底背驰")
            return False, {}
        
        try:
            if not self._macd_15m or "macd" not in self._macd_15m:
                logger.info("[MTF-提前入场] 15分钟MACD未计算")
                return False, {}
            
            lookback = min(100, len(self.df_15m))
            lows = self.df_15m["low"].astype(float).iloc[-lookback:].reset_index(drop=True)
            dif = self._macd_15m["macd"].iloc[-lookback:].reset_index(drop=True)
            
            if len(lows) < 30:
                return False, {}
            
            half = len(lows) // 2
            low1 = float(lows.iloc[:half].min())
            low1_idx = int(lows.iloc[:half].idxmin())
            low2 = float(lows.iloc[half:].min())
            low2_idx = int(lows.iloc[half:].idxmin())
            
            if low2_idx - low1_idx < 5:
                return False, {}
            
            if low2 < low1:
                dif1 = float(dif.iloc[low1_idx])
                dif2 = float(dif.iloc[low2_idx])
                
                if dif2 > dif1:
                    logger.info(f"[MTF-提前入场] 15分钟底背驰检测成功: "
                              f"价格低点{low1:.4f}->{low2:.4f}, "
                              f"DIF {dif1:.4f}->{dif2:.4f}")
                    
                    return True, {
                        'price_low1': low1,
                        'price_low2': low2,
                        'dif_low1': dif1,
                        'dif_low2': dif2,
                        'suggested_entry': float(self.df_15m["close"].iloc[-1]),
                    }
            
            return False, {}
            
        except Exception as e:
            logger.warning(f"[MTF-提前入场] 15分钟底背驰检测异常: {e}")
            return False, {}

    def _check_15m_second_buy(self, k1k2_info: BottomFractalK12Structure) -> Tuple[bool, Dict[str, Any]]:
        """
        在15分钟K线中检测第二类买点
        
        条件:
        - 一买后价格反弹
        - 回调低点不破一买低点
        - 回调低点高于K2低点
        
        Returns:
            Tuple[bool, Dict]: (是否检测到二买, 详细分析结果)
        """
        if self.df_15m.empty or len(self.df_15m) < 50:
            return False, {}
        
        try:
            closes = self.df_15m["close"].astype(float)
            lows = self.df_15m["low"].astype(float)
            highs = self.df_15m["high"].astype(float)
            
            lookback = min(100, len(self.df_15m))
            recent_lows = lows.iloc[-lookback:]
            
            if len(recent_lows) < 20:
                return False, {}
            
            recent_low_idx = int(recent_lows.idxmin())
            prev_low_idx = int(closes.iloc[:recent_low_idx - 1].idxmin()) if recent_low_idx > 0 else recent_low_idx
            
            if prev_low_idx >= recent_low_idx or recent_low_idx >= len(self.df_15m) - 5:
                return False, {}
            
            recent_low_price = float(lows.iloc[recent_low_idx])
            k2_low = k1k2_info.k2_low
            
            if recent_low_price > k2_low:
                recent_high_idx = int(closes.iloc[recent_low_idx:].idxmax()) if recent_low_idx < len(closes) - 1 else recent_low_idx
                
                if recent_high_idx > recent_low_idx and recent_high_idx < len(self.df_15m) - 1:
                    pullback_low_idx = int(lows.iloc[recent_high_idx:].idxmin())
                    pullback_low = float(lows.iloc[pullback_low_idx])
                    
                    if pullback_low > recent_low_price and pullback_low > k2_low:
                        confidence = 0.0
                        if pullback_low > recent_low_price:
                            confidence += 0.4
                        if pullback_low > k2_low:
                            confidence += 0.3
                        if len(self.df_15m) - 1 - pullback_low_idx < 20:
                            confidence += 0.3
                        
                        logger.info(f"[MTF-提前入场] 15分钟二买检测成功: "
                                  f"一买={recent_low_price:.4f}, 回调={pullback_low:.4f}, "
                                  f"K2_low={k2_low:.4f}, confidence={confidence:.2f}")
                        
                        return True, {
                            'first_buy_low': recent_low_price,
                            'pullback_low': pullback_low,
                            'pullback_low_idx': pullback_low_idx,
                            'k2_low': k2_low,
                            'confidence': confidence,
                            'suggested_entry': float(closes.iloc[-1]),
                        }
            
            return False, {}
            
        except Exception as e:
            logger.warning(f"[MTF-提前入场] 15分钟二买检测异常: {e}")
            return False, {}

    def _check_15m_uptrend(self) -> Tuple[bool, str]:
        """
        确认15分钟趋势已转为向上
        
        检测方法:
        - MA5 > MA20（短期均线在长期均线上方）
        - 近期低点抬高（LL > HL）
        - 出现连续阳线
        
        Returns:
            Tuple[bool, str]: (是否确认趋势向上, 确认原因)
        """
        if self.df_15m.empty or len(self.df_15m) < 30:
            return False, ""
        
        try:
            closes = self.df_15m["close"].astype(float)
            
            ma5 = closes.rolling(window=5).mean()
            ma20 = closes.rolling(window=20).mean()
            ma60 = closes.rolling(window=60).mean()
            
            ma_bullish = float(ma5.iloc[-1]) > float(ma20.iloc[-1]) > float(ma60.iloc[-1])
            
            lows = self.df_15m["low"].astype(float)
            recent_lows = lows.iloc[-10:]
            if len(recent_lows) >= 5:
                ll = float(recent_lows.min())
                prev_lows = lows.iloc[-20:-10] if len(lows) >= 20 else lows.iloc[:-10]
                hl = float(prev_lows.min()) if len(prev_lows) > 0 else ll
                low_higher = ll > hl
            else:
                low_higher = False
            
            opens = self.df_15m["open"].astype(float)
            bullish_count = 0
            for i in range(-5, 0):
                if i >= -len(closes) and i >= -len(opens):
                    if float(closes.iloc[i]) > float(opens.iloc[i]):
                        bullish_count += 1
            consecutive_bullish = bullish_count >= 3
            
            reasons = []
            if ma_bullish:
                reasons.append("均线多头排列")
            if low_higher:
                reasons.append("低点抬高")
            if consecutive_bullish:
                reasons.append("连续阳线")
            
            confirmed = sum([ma_bullish, low_higher, consecutive_bullish]) >= 2
            
            if confirmed:
                logger.info(f"[MTF-提前入场] 15分钟趋势向上确认: {', '.join(reasons)}")
            else:
                logger.info(f"[MTF-提前入场] 15分钟趋势未确认向上: MA={ma_bullish}, LL>{hl}={low_higher}, 阳线={consecutive_bullish}")
            
            return confirmed, ", ".join(reasons) if reasons else ""
            
        except Exception as e:
            logger.warning(f"[MTF-提前入场] 15分钟趋势检测异常: {e}")
            return False, ""

    def _generate_early_entry_signal(self) -> Optional[Dict[str, Any]]:
        """
        在K3形成过程中提前入场做多
        
        触发条件:
        1. 4小时底分型K1/K2结构已形成
        2. 当前处于K3后半段
        3. 15分钟级别满足以下任一条件:
           - 15分钟一买确认（底背驰）
           - 15分钟二买确认（回调不破前低）
        4. 15分钟趋势向上确认
        
        Returns:
            Optional[Dict]: 入场信号字典
        """
        if not self.enable_early_entry:
            return None
        
        if self.df_15m.empty or len(self.df_15m) < 50:
            logger.info("[MTF-提前入场] 15分钟数据不足，跳过提前入场检测")
            return None
        
        k1k2 = self._check_4h_bottom_fractal_k1k2()
        
        if not k1k2.has_structure:
            logger.info("[MTF-提前入场] 未检测到K1/K2底分型结构")
            return None
        
        if not k1k2.is_k3_forming:
            logger.info("[MTF-提前入场] K3未在形成中")
            return None
        
        if not k1k2.is_in_second_half:
            logger.info("[MTF-提前入场] K3未进入后半段，跳过")
            return None
        
        first_buy_detected, first_buy_info = self._check_15m_first_buy()
        second_buy_detected, second_buy_info = self._check_15m_second_buy(k1k2)
        uptrend_confirmed, uptrend_reason = self._check_15m_uptrend()
        
        satisfied_count = sum([first_buy_detected, second_buy_detected, uptrend_confirmed])
        
        logger.info(f"[MTF-提前入场] 3条件检测: 一买={first_buy_detected}, "
                   f"二买={second_buy_detected}, 趋势向上={uptrend_confirmed}, "
                   f"满足={satisfied_count}/{self.min_early_entry_conditions}")
        
        if satisfied_count < self.min_early_entry_conditions:
            return None
        
        reasons = []
        if first_buy_detected:
            reasons.append("15分钟底背驰(一买)")
        if second_buy_detected:
            reasons.append("15分钟二买")
        if uptrend_confirmed:
            reasons.append(f"15分钟趋势向上({uptrend_reason})")
        
        entry_price = float(self.df_4h.iloc[-1]["close"])
        
        stop_loss = k1k2.k2_low - self.stop_offset
        if self.current_atr > 0:
            atr_stop = entry_price - self.current_atr * self.atr_multiplier
            stop_loss = min(stop_loss, atr_stop)
        
        take_profit = entry_price + (entry_price - stop_loss) * self.profit_loss_ratio
        
        liq_price = entry_price * (1 - 1 / self.leverage)
        if stop_loss < liq_price:
            stop_loss = liq_price + 1.0
        
        signal_type = "first_buy" if first_buy_detected else ("second_buy" if second_buy_detected else "uptrend")
        
        logger.info(f"[MTF-提前入场] 生成信号: type={signal_type}, "
                   f"entry={entry_price:.4f}, stop={stop_loss:.4f}, "
                   f"satisfied={satisfied_count}/{self.min_early_entry_conditions}, "
                   f"reason={', '.join(reasons)}")
        
        return {
            "action": "EARLY_ENTRY",
            "type": "early_entry",
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "position": "long",
            "position_ratio": self.early_entry_ratio,
            "reason": f"提前入场: {', '.join(reasons)} (满足{satisfied_count}/{self.min_early_entry_conditions})",
            "k1_idx": k1k2.k1_idx,
            "k2_idx": k1k2.k2_idx,
            "k3_idx": k1k2.k3_idx,
            "signal_type": signal_type,
            "satisfied_count": satisfied_count,
            "leverage": self.leverage,
            "first_buy_info": first_buy_info,
            "second_buy_info": second_buy_info,
        }

    def _check_4h_top_fractal_k1k2(self) -> TopFractalK12Structure:
        """
        检测4小时顶分型K1/K2结构
        
        K1: 上涨K线（收盘>开盘）
        K2: 最高点高于K1高点
        K3候选: 当前K线，高点低于K2高点
        
        Returns:
            TopFractalK12Structure对象，包含检测结果
        """
        result = TopFractalK12Structure()
        
        if len(self.df_4h) < 3:
            return result
        
        k1_idx = len(self.df_4h) - 3
        k2_idx = len(self.df_4h) - 2
        k3_idx = len(self.df_4h) - 1
        
        k1 = self.df_4h.iloc[k1_idx]
        k2 = self.df_4h.iloc[k2_idx]
        k3 = self.df_4h.iloc[k3_idx]
        
        k1_open = float(k1["open"])
        k1_close = float(k1["close"])
        k1_high = float(k1["high"])
        
        k2_low = float(k2["low"])
        k2_high = float(k2["high"])
        
        k3_partial_low = float(k3["low"])
        k3_partial_high = float(k3["high"])
        k3_partial_close = float(k3["close"])
        
        is_k1_up = k1_close > k1_open
        is_k2_higher_high = k2_high > k1_high
        is_k3_forming = k3_partial_high < k2_high
        
        if not (is_k1_up and is_k2_higher_high):
            return result
        
        confidence = 0.0
        if is_k1_up:
            confidence += 0.3
        if is_k2_higher_high:
            confidence += 0.3
        if is_k3_forming:
            confidence += 0.4
        
        result.has_structure = True
        result.k1_idx = k1_idx
        result.k2_idx = k2_idx
        result.k3_idx = k3_idx
        result.k1_high = k1_high
        result.k1_open = k1_open
        result.k1_close = k1_close
        result.k2_high = k2_high
        result.k2_low = k2_low
        result.k3_partial_low = k3_partial_low
        result.k3_partial_high = k3_partial_high
        result.k3_partial_close = k3_partial_close
        result.is_k3_forming = is_k3_forming
        result.is_in_second_half = self._is_in_candle_second_half()
        result.confidence = confidence
        
        logger.info(f"[MTF-提前做空] K1/K2顶分型结构检测: "
                   f"K1_idx={k1_idx}, K2_idx={k2_idx}, K3_idx={k3_idx}, "
                   f"K1_up={is_k1_up}, K2_higher={is_k2_higher_high}, "
                   f"K3_forming={is_k3_forming}, second_half={result.is_in_second_half}, "
                   f"confidence={confidence:.2f}")
        
        return result

    def _check_15m_first_sell(self) -> Tuple[bool, Dict[str, Any]]:
        """
        在15分钟K线中直接检测顶背驰（MACD背离）
        
        检测最近100根K线中两个高点之间的背离：
        - 价格高点抬高（新高 > 前高）
        - MACD DIF高点降低（新高DIF < 前高DIF）
        
        Returns:
            Tuple[bool, Dict]: (是否检测到顶背驰, 详细分析结果)
        """
        if self.df_15m.empty or len(self.df_15m) < 50:
            logger.info("[MTF-提前做空] 15分钟数据不足，无法检测顶背驰")
            return False, {}
        
        try:
            if not self._macd_15m or "macd" not in self._macd_15m:
                logger.info("[MTF-提前做空] 15分钟MACD未计算")
                return False, {}
            
            lookback = min(100, len(self.df_15m))
            highs = self.df_15m["high"].astype(float).iloc[-lookback:].reset_index(drop=True)
            dif = self._macd_15m["macd"].iloc[-lookback:].reset_index(drop=True)
            
            if len(highs) < 30:
                return False, {}
            
            half = len(highs) // 2
            high1 = float(highs.iloc[:half].max())
            high1_idx = int(highs.iloc[:half].idxmax())
            high2 = float(highs.iloc[half:].max())
            high2_idx = int(highs.iloc[half:].idxmax())
            
            if high2_idx - high1_idx < 5:
                return False, {}
            
            if high2 > high1:
                dif1 = float(dif.iloc[high1_idx])
                dif2 = float(dif.iloc[high2_idx])
                
                if dif2 < dif1:
                    logger.info(f"[MTF-提前做空] 15分钟顶背驰检测成功: "
                              f"价格高点{high1:.4f}->{high2:.4f}, "
                              f"DIF {dif1:.4f}->{dif2:.4f}")
                    
                    return True, {
                        'price_high1': high1,
                        'price_high2': high2,
                        'dif_high1': dif1,
                        'dif_high2': dif2,
                        'suggested_entry': float(self.df_15m["close"].iloc[-1]),
                    }
            
            return False, {}
            
        except Exception as e:
            logger.warning(f"[MTF-提前做空] 15分钟顶背驰检测异常: {e}")
            return False, {}

    def _check_15m_second_sell(self, k1k2_info: TopFractalK12Structure) -> Tuple[bool, Dict[str, Any]]:
        """
        在15分钟K线中检测第二类卖点
        
        条件:
        - 一卖后价格下跌
        - 反弹高点不破一卖高点
        - 反弹高点低于K2高点
        
        Returns:
            Tuple[bool, Dict]: (是否检测到二卖, 详细分析结果)
        """
        if self.df_15m.empty or len(self.df_15m) < 50:
            return False, {}
        
        try:
            closes = self.df_15m["close"].astype(float)
            lows = self.df_15m["low"].astype(float)
            highs = self.df_15m["high"].astype(float)
            
            lookback = min(100, len(self.df_15m))
            recent_highs = highs.iloc[-lookback:]
            
            if len(recent_highs) < 20:
                return False, {}
            
            recent_high_idx = int(recent_highs.idxmax())
            prev_high_idx = int(closes.iloc[:recent_high_idx - 1].idxmax()) if recent_high_idx > 0 else recent_high_idx
            
            if prev_high_idx >= recent_high_idx or recent_high_idx >= len(self.df_15m) - 5:
                return False, {}
            
            recent_high_price = float(highs.iloc[recent_high_idx])
            k2_high = k1k2_info.k2_high
            
            if recent_high_price < k2_high:
                recent_low_idx = int(closes.iloc[:recent_high_idx].idxmin()) if recent_high_idx > 0 else recent_high_idx
                
                if recent_low_idx < recent_high_idx and recent_low_idx > 0:
                    pullback_high_idx = int(highs.iloc[recent_low_idx:recent_high_idx].idxmax())
                    pullback_high = float(highs.iloc[pullback_high_idx])
                    
                    if pullback_high < recent_high_price and pullback_high < k2_high:
                        confidence = 0.0
                        if pullback_high < recent_high_price:
                            confidence += 0.4
                        if pullback_high < k2_high:
                            confidence += 0.3
                        if len(self.df_15m) - 1 - pullback_high_idx < 20:
                            confidence += 0.3
                        
                        logger.info(f"[MTF-提前做空] 15分钟二卖检测成功: "
                                  f"一卖={recent_high_price:.4f}, 反弹={pullback_high:.4f}, "
                                  f"K2_high={k2_high:.4f}, confidence={confidence:.2f}")
                        
                        return True, {
                            'first_sell_high': recent_high_price,
                            'pullback_high': pullback_high,
                            'pullback_high_idx': pullback_high_idx,
                            'k2_high': k2_high,
                            'confidence': confidence,
                            'suggested_entry': float(closes.iloc[-1]),
                        }
            
            return False, {}
            
        except Exception as e:
            logger.warning(f"[MTF-提前做空] 15分钟二卖检测异常: {e}")
            return False, {}

    def _check_15m_downtrend(self) -> Tuple[bool, str]:
        """
        确认15分钟趋势已转为向下
        
        检测方法:
        - MA5 < MA20 < MA60（短期均线在长期均线下方）
        - 近期高点降低（LH < HL）
        - 出现连续阴线
        
        Returns:
            Tuple[bool, str]: (是否确认趋势向下, 确认原因)
        """
        if self.df_15m.empty or len(self.df_15m) < 30:
            return False, ""
        
        try:
            closes = self.df_15m["close"].astype(float)
            
            ma5 = closes.rolling(window=5).mean()
            ma20 = closes.rolling(window=20).mean()
            ma60 = closes.rolling(window=60).mean()
            
            ma_bearish = float(ma5.iloc[-1]) < float(ma20.iloc[-1]) < float(ma60.iloc[-1])
            
            highs = self.df_15m["high"].astype(float)
            recent_highs = highs.iloc[-10:]
            if len(recent_highs) >= 5:
                lh = float(recent_highs.max())
                prev_highs = highs.iloc[-20:-10] if len(highs) >= 20 else highs.iloc[:-10]
                hl = float(prev_highs.max()) if len(prev_highs) > 0 else lh
                high_lower = lh < hl
            else:
                high_lower = False
            
            opens = self.df_15m["open"].astype(float)
            bearish_count = 0
            for i in range(-5, 0):
                if i >= -len(closes) and i >= -len(opens):
                    if float(closes.iloc[i]) < float(opens.iloc[i]):
                        bearish_count += 1
            consecutive_bearish = bearish_count >= 3
            
            reasons = []
            if ma_bearish:
                reasons.append("均线空头排列")
            if high_lower:
                reasons.append("高点降低")
            if consecutive_bearish:
                reasons.append("连续阴线")
            
            confirmed = sum([ma_bearish, high_lower, consecutive_bearish]) >= 2
            
            if confirmed:
                logger.info(f"[MTF-提前做空] 15分钟趋势向下确认: {', '.join(reasons)}")
            else:
                logger.info(f"[MTF-提前做空] 15分钟趋势未确认向下: MA={ma_bearish}, LH<{hl}={high_lower}, 阴线={consecutive_bearish}")
            
            return confirmed, ", ".join(reasons) if reasons else ""
            
        except Exception as e:
            logger.warning(f"[MTF-提前做空] 15分钟趋势检测异常: {e}")
            return False, ""

    def _generate_early_short_entry_signal(self) -> Optional[Dict[str, Any]]:
        """
        在K3形成过程中提前入场做空
        
        触发条件:
        1. 4小时顶分型K1/K2结构已形成
        2. 当前处于K3后半段
        3. 15分钟级别满足以下任一条件:
           - 15分钟一卖确认（顶背驰）
           - 15分钟二卖确认（反弹不过前高）
        4. 15分钟趋势向下确认
        
        Returns:
            Optional[Dict]: 做空入场信号字典
        """
        if not self.enable_early_short_entry:
            return None
        
        if self.df_15m.empty or len(self.df_15m) < 50:
            logger.info("[MTF-提前做空] 15分钟数据不足，跳过提前做空检测")
            return None
        
        k1k2 = self._check_4h_top_fractal_k1k2()
        
        if not k1k2.has_structure:
            logger.info("[MTF-提前做空] 未检测到K1/K2顶分型结构")
            return None
        
        if not k1k2.is_k3_forming:
            logger.info("[MTF-提前做空] K3未在形成中")
            return None
        
        if not k1k2.is_in_second_half:
            logger.info("[MTF-提前做空] K3未进入后半段，跳过")
            return None
        
        first_sell_detected, first_sell_info = self._check_15m_first_sell()
        second_sell_detected, second_sell_info = self._check_15m_second_sell(k1k2)
        downtrend_confirmed, downtrend_reason = self._check_15m_downtrend()
        
        satisfied_count = sum([first_sell_detected, second_sell_detected, downtrend_confirmed])
        
        logger.info(f"[MTF-提前做空] 3条件检测: 一卖={first_sell_detected}, "
                   f"二卖={second_sell_detected}, 趋势向下={downtrend_confirmed}, "
                   f"满足={satisfied_count}/{self.min_early_entry_conditions}")
        
        if satisfied_count < self.min_early_entry_conditions:
            return None
        
        reasons = []
        if first_sell_detected:
            reasons.append("15分钟顶背驰(一卖)")
        if second_sell_detected:
            reasons.append("15分钟二卖")
        if downtrend_confirmed:
            reasons.append(f"15分钟趋势向下({downtrend_reason})")
        
        entry_price = float(self.df_4h.iloc[-1]["close"])
        
        stop_loss = k1k2.k2_high + self.stop_offset
        if self.current_atr > 0:
            atr_stop = entry_price + self.current_atr * self.atr_multiplier
            stop_loss = max(stop_loss, atr_stop)
        
        take_profit = entry_price - (stop_loss - entry_price) * self.profit_loss_ratio
        
        liq_price = entry_price * (1 + 1 / self.leverage)
        if stop_loss > liq_price:
            stop_loss = liq_price - 1.0
        
        signal_type = "first_sell" if first_sell_detected else ("second_sell" if second_sell_detected else "downtrend")
        
        logger.info(f"[MTF-提前做空] 生成信号: type={signal_type}, "
                   f"entry={entry_price:.4f}, stop={stop_loss:.4f}, "
                   f"satisfied={satisfied_count}/{self.min_early_entry_conditions}, "
                   f"reason={', '.join(reasons)}")
        
        return {
            "action": "EARLY_SHORT_ENTRY",
            "type": "early_short_entry",
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "position": "short",
            "position_ratio": self.early_short_entry_ratio,
            "reason": f"提前做空: {', '.join(reasons)} (满足{satisfied_count}/{self.min_early_entry_conditions})",
            "k1_idx": k1k2.k1_idx,
            "k2_idx": k1k2.k2_idx,
            "k3_idx": k1k2.k3_idx,
            "signal_type": signal_type,
            "satisfied_count": satisfied_count,
            "leverage": self.leverage,
            "first_sell_info": first_sell_info,
            "second_sell_info": second_sell_info,
        }

    def _check_4h_bottom_fractal(self) -> Tuple[bool, int, int]:
        if len(self.df_4h) < 3 or not self.fractals:
            return False, -1, -1
        recent = self.fractals[-2:] if len(self.fractals) >= 2 else self.fractals
        last_fractal = recent[-1]
        if last_fractal.type != "bottom":
            return False, -1, -1
        k2_idx = last_fractal.idx
        k1_idx = recent[-2].idx if len(recent) >= 2 and recent[-2].type == "top" else k2_idx - 1
        k2 = self.df_processed.iloc[k2_idx] if not self.df_processed.empty else self.df_4h.iloc[k2_idx]
        k2_close = float(k2["close"])
        k2_open = float(k2["open"])
        if k2_close <= k2_open * 0.5:
            return False, -1, -1
        fractal_price = float(k2["low"])
        current_bar_idx = len(self.df_4h) - 1
        if self._last_bottom_fractal_time is not None and self._last_bottom_fractal_price is not None:
            bars_since = current_bar_idx - self._last_bottom_fractal_time
            price_diff_pct = abs(fractal_price - self._last_bottom_fractal_price) / self._last_bottom_fractal_price
            if bars_since < 12 and price_diff_pct < 0.02:
                logger.info(f"[MTF] 底分型去重: 同水平{fractal_price:.2f}({bars_since}k前已触发), 跳过")
                return False, -1, -1
        self._last_bottom_fractal_price = fractal_price
        self._last_bottom_fractal_time = current_bar_idx
        logger.info(f"[MTF] 4h底分型(Chan): idx={k2_idx}, low={float(k2['low']):.2f}, close={k2_close:.2f}")
        return True, k1_idx, k2_idx

    def _check_resistance_zone(self) -> Tuple[bool, float]:
        if self.df_4h.empty or not self.resistance_levels:
            return False, 0.0
        current_price = float(self.df_4h.iloc[-1]["close"])
        current_high = float(self.df_4h.iloc[-1]["high"])
        check_price = max(current_price, current_high)
        atr = getattr(self, 'current_atr', 0.0) or 0.0
        threshold = min(atr * 0.5, current_price * 0.01) if atr > 0 else current_price * 0.01
        for level in self.resistance_levels:
            if check_price >= level - threshold:
                logger.info(f"[MTF] 价格进入阻力区域: 当前={check_price:.2f}, 阻力位={level}, 阈值={threshold:.2f}")
                return True, level
        return False, 0.0

    def _check_4h_top_fractal(self) -> Tuple[bool, int, int]:
        if len(self.df_4h) < 3 or not self.fractals:
            return False, -1, -1
        recent = self.fractals[-2:] if len(self.fractals) >= 2 else self.fractals
        last_fractal = recent[-1]
        if last_fractal.type != "top":
            return False, -1, -1
        k2_idx = last_fractal.idx
        k1_idx = recent[-2].idx if len(recent) >= 2 and recent[-2].type == "bottom" else k2_idx - 1
        k2 = self.df_processed.iloc[k2_idx] if not self.df_processed.empty else self.df_4h.iloc[k2_idx]
        k2_close = float(k2["close"])
        k2_open = float(k2["open"])
        if k2_close >= k2_open * 1.5:
            return False, -1, -1
        fractal_price = float(k2["high"])
        current_bar_idx = len(self.df_4h) - 1
        if self._last_top_fractal_time is not None and self._last_top_fractal_price is not None:
            bars_since = current_bar_idx - self._last_top_fractal_time
            price_diff_pct = abs(fractal_price - self._last_top_fractal_price) / self._last_top_fractal_price
            if bars_since < 12 and price_diff_pct < 0.02:
                logger.info(f"[MTF] 顶分型去重: 同水平{fractal_price:.2f}({bars_since}k前已触发), 跳过")
                return False, -1, -1
        self._last_top_fractal_price = fractal_price
        self._last_top_fractal_time = current_bar_idx
        logger.info(f"[MTF] 4h顶分型(Chan): idx={k2_idx}, high={float(k2['high']):.2f}, close={k2_close:.2f}")
        return True, k1_idx, k2_idx

    def _check_30m_divergence(self) -> bool:
        if len(self.df_30m) < 20 or "_macd_30m" not in self.__dict__:
            return False
        closes = self.df_30m["close"].astype(float)
        lookback = min(20, len(closes) // 3)
        recent_lows = closes.iloc[-lookback:]
        recent_low_idx = int(recent_lows.idxmin())
        prev_low_idx = int(closes.iloc[:recent_low_idx - 1].idxmin()) if recent_low_idx > 0 else recent_low_idx
        if prev_low_idx >= recent_low_idx:
            return False
        recent_price = float(closes.iloc[recent_low_idx])
        prev_price = float(closes.iloc[prev_low_idx])
        if recent_price >= prev_price:
            return False
        macd_hist = self._macd_30m["histogram"]
        recent_macd = float(macd_hist.iloc[recent_low_idx]) if recent_low_idx < len(macd_hist) else 0
        prev_macd = float(macd_hist.iloc[prev_low_idx]) if prev_low_idx < len(macd_hist) else 0
        if recent_macd >= prev_macd:
            logger.info(f"[MTF] 30m底背离: 价格{recent_price:.2f}<{prev_price:.2f}, MACD柱{recent_macd:.4f}>={prev_macd:.4f}")
            return True
        return False

    def _check_30m_bullish_candlestick(self) -> bool:
        if len(self.df_30m) < 4:
            return False

        def is_bullish_engulfing(c1, c2) -> bool:
            c1_body = float(c1["close"]) - float(c1["open"])
            return (float(c1["close"]) < float(c1["open"]) and
                    float(c2["close"]) > float(c2["open"]) and
                    abs(c1_body) < float(c2["close"]) - float(c2["open"]))

        def is_hammer(c) -> bool:
            o, h, l, cl = float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"])
            body = abs(cl - o)
            lower_shadow = min(o, cl) - l
            upper_shadow = h - max(o, cl)
            return lower_shadow > body * 2 and upper_shadow < body * 0.5

        def is_morning_star(c1, c2, c3) -> bool:
            c1_bear = float(c1["close"]) < float(c1["open"])
            c2_small = abs(float(c2["close"]) - float(c2["open"])) < abs(float(c1["close"]) - float(c1["open"])) * 0.5
            c3_bull = float(c3["close"]) > float(c3["open"]) and float(c3["close"]) > (float(c1["open"]) + float(c1["close"])) / 2
            return c1_bear and c2_small and c3_bull and float(c3["low"]) < float(c2["low"])

        recent = self.df_30m.iloc[-3:]
        if len(recent) >= 3:
            if is_morning_star(recent.iloc[0], recent.iloc[1], recent.iloc[2]):
                logger.info("[MTF] 30m看涨形态: 早晨之星")
                return True
        if len(recent) >= 2:
            if is_bullish_engulfing(recent.iloc[0], recent.iloc[1]):
                logger.info("[MTF] 30m看涨形态: 看涨吞没")
                return True
        current = self.df_30m.iloc[-1]
        if is_hammer(current):
            logger.info("[MTF] 30m看涨形态: 锤子线")
            return True
        return False

    def _check_30m_trendline_break(self) -> bool:
        if len(self.df_30m) < self.trendline_period:
            return False
        closes = self.df_30m["close"].astype(float).iloc[-self.trendline_period:]
        highs = self.df_30m["high"].astype(float).iloc[-self.trendline_period:]
        x = np.arange(len(closes))

        # Method 1: Break above descending trendline (reversal)
        slope_low, intercept_low = np.polyfit(x, highs.values, 1)
        if slope_low < 0:
            trendline_val = slope_low * (len(closes) - 1) + intercept_low
            if float(closes.iloc[-1]) > trendline_val:
                logger.info(f"[MTF] 30m突破下降趋势线: 收盘={float(closes.iloc[-1]):.2f}, 趋势线={trendline_val:.2f}")
                return True

        # Method 2: Break above recent consolidation high
        if len(self.df_30m) >= 12:
            recent_highs = highs.iloc[-12:-2]
            consolidation_high = float(recent_highs.max())
            if float(closes.iloc[-1]) > consolidation_high and float(closes.iloc[-2]) <= consolidation_high:
                logger.info(f"[MTF] 30m突破盘整高点: 收盘={float(closes.iloc[-1]):.2f}, 前高={consolidation_high:.2f}")
                return True

        return False

    def _check_30m_golden_cross(self) -> bool:
        macd_ok = False
        if self._macd_30m and len(self._macd_30m["macd"]) >= 2:
            macd_line = self._macd_30m["macd"]
            sig_line = self._macd_30m["signal"]
            if (float(macd_line.iloc[-2]) <= float(sig_line.iloc[-2]) and
                    float(macd_line.iloc[-1]) > float(sig_line.iloc[-1])):
                macd_ok = True
                logger.info("[MTF] 30m MACD金叉")

        kdj_ok = False
        if self._kdj_30m and len(self._kdj_30m["k"]) >= 2:
            k_line = self._kdj_30m["k"]
            d_line = self._kdj_30m["d"]
            if (float(k_line.iloc[-2]) <= float(d_line.iloc[-2]) and
                    float(k_line.iloc[-1]) > float(d_line.iloc[-1]) and
                    float(k_line.iloc[-1]) < 20):
                kdj_ok = True
                logger.info("[MTF] 30m KDJ低位金叉(K<20)")

        return macd_ok or kdj_ok

    def _check_30m_momentum_bullish(self) -> bool:
        """简化做多动量信号"""
        if len(self.df_30m) < 10:
            return False
        closes = self.df_30m["close"].astype(float)
        last_close = float(closes.iloc[-1])
        prev_close = float(closes.iloc[-8])

        if (last_close - prev_close) / prev_close > 0.01:
            logger.info(f"[MTF] 30m做多动量: 8k涨幅={((last_close-prev_close)/prev_close*100):.2f}%")
            return True

        if len(closes) >= 4:
            c1 = closes.iloc[-4:]
            o1 = self.df_30m["open"].astype(float).iloc[-4:]
            if all(float(c1.iloc[i]) > float(o1.iloc[i]) for i in range(4)):
                logger.info("[MTF] 30m做多动量: 连续4根阳线")
                return True

        return False

    def _check_30m_momentum_bearish(self) -> bool:
        """简化做空动量信号"""
        if len(self.df_30m) < 10:
            return False
        closes = self.df_30m["close"].astype(float)
        last_close = float(closes.iloc[-1])
        prev_close = float(closes.iloc[-8])

        if (prev_close - last_close) / prev_close > 0.01:
            logger.info(f"[MTF] 30m做空动量: 8k跌幅={((prev_close-last_close)/prev_close*100):.2f}%")
            return True

        if len(closes) >= 4:
            c1 = closes.iloc[-4:]
            o1 = self.df_30m["open"].astype(float).iloc[-4:]
            if all(float(c1.iloc[i]) < float(o1.iloc[i]) for i in range(4)):
                logger.info("[MTF] 30m做空动量: 连续4根阴线")
                return True

        return False

    def _check_30m_top_divergence(self) -> bool:
        if len(self.df_30m) < 20 or "_macd_30m" not in self.__dict__:
            return False
        closes = self.df_30m["close"].astype(float)
        lookback = min(20, len(closes) // 3)
        recent_highs = closes.iloc[-lookback:]
        recent_high_idx = int(recent_highs.idxmax())
        prev_high_idx = int(closes.iloc[:recent_high_idx - 1].idxmax()) if recent_high_idx > 0 else recent_high_idx
        if prev_high_idx >= recent_high_idx:
            return False
        recent_price = float(closes.iloc[recent_high_idx])
        prev_price = float(closes.iloc[prev_high_idx])
        if recent_price <= prev_price:
            return False
        macd_hist = self._macd_30m["histogram"]
        recent_macd = float(macd_hist.iloc[recent_high_idx]) if recent_high_idx < len(macd_hist) else 0
        prev_macd = float(macd_hist.iloc[prev_high_idx]) if prev_high_idx < len(macd_hist) else 0
        if recent_macd <= prev_macd:
            logger.info(f"[MTF] 30m顶背离: 价格{recent_price:.2f}>{prev_price:.2f}, MACD柱{recent_macd:.4f}<={prev_macd:.4f}")
            return True
        return False

    def _check_30m_bearish_candlestick(self) -> bool:
        if len(self.df_30m) < 4:
            return False

        def is_bearish_engulfing(c1, c2) -> bool:
            c1_body = float(c1["close"]) - float(c1["open"])
            return (float(c1["close"]) > float(c1["open"]) and
                    float(c2["close"]) < float(c2["open"]) and
                    abs(c1_body) < abs(float(c2["open"]) - float(c2["close"])))

        def is_shooting_star(c) -> bool:
            o, h, l, cl = float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"])
            body = abs(cl - o)
            upper_shadow = h - max(o, cl)
            lower_shadow = min(o, cl) - l
            return upper_shadow > body * 2 and lower_shadow < body * 0.5

        def is_evening_star(c1, c2, c3) -> bool:
            c1_bull = float(c1["close"]) > float(c1["open"])
            c2_small = abs(float(c2["close"]) - float(c2["open"])) < abs(float(c1["close"]) - float(c1["open"])) * 0.5
            c3_bear = float(c3["close"]) < float(c3["open"]) and float(c3["close"]) < (float(c1["open"]) + float(c1["close"])) / 2
            return c1_bull and c2_small and c3_bear and float(c3["high"]) > float(c2["high"])

        def is_dark_cloud_cover(c1, c2) -> bool:
            c1_bull = float(c1["close"]) > float(c1["open"])
            c2_open_above = float(c2["open"]) > float(c1["high"])
            c1_mid = (float(c1["open"]) + float(c1["close"])) / 2
            c2_close_below = float(c2["close"]) < c1_mid
            c2_bear = float(c2["close"]) < float(c2["open"])
            return c1_bull and c2_bear and c2_open_above and c2_close_below

        recent = self.df_30m.iloc[-3:]
        if len(recent) >= 3:
            if is_evening_star(recent.iloc[0], recent.iloc[1], recent.iloc[2]):
                logger.info("[MTF] 30m看跌形态: 黄昏之星")
                return True
        if len(recent) >= 2:
            if is_bearish_engulfing(recent.iloc[0], recent.iloc[1]):
                logger.info("[MTF] 30m看跌形态: 看跌吞没")
                return True
            if is_dark_cloud_cover(recent.iloc[0], recent.iloc[1]):
                logger.info("[MTF] 30m看跌形态: 乌云盖顶")
                return True
        current = self.df_30m.iloc[-1]
        if is_shooting_star(current):
            logger.info("[MTF] 30m看跌形态: 射击之星")
            return True
        return False

    def _check_30m_trendline_break_down(self) -> bool:
        if len(self.df_30m) < self.trendline_period:
            return False
        closes = self.df_30m["close"].astype(float).iloc[-self.trendline_period:]
        lows = self.df_30m["low"].astype(float).iloc[-self.trendline_period:]
        x = np.arange(len(closes))

        # Method 1: Break below rising trendline (reversal)
        slope_high, intercept_high = np.polyfit(x, lows.values, 1)
        if slope_high > 0:
            trendline_val = slope_high * (len(closes) - 1) + intercept_high
            if float(closes.iloc[-1]) < trendline_val:
                logger.info(f"[MTF] 30m跌破上升趋势线: 收盘={float(closes.iloc[-1]):.2f}, 趋势线={trendline_val:.2f}")
                return True

        # Method 2: Break below recent consolidation low
        if len(self.df_30m) >= 12:
            recent_lows = lows.iloc[-12:-2]
            consolidation_low = float(recent_lows.min())
            if float(closes.iloc[-1]) < consolidation_low and float(closes.iloc[-2]) >= consolidation_low:
                logger.info(f"[MTF] 30m跌破盘整低点: 收盘={float(closes.iloc[-1]):.2f}, 前低={consolidation_low:.2f}")
                return True

        return False

    def _check_30m_death_cross(self) -> bool:
        macd_ok = False
        if self._macd_30m and len(self._macd_30m["macd"]) >= 2:
            macd_line = self._macd_30m["macd"]
            sig_line = self._macd_30m["signal"]
            ml_1 = float(macd_line.iloc[-1])
            ml_2 = float(macd_line.iloc[-2])
            sl_1 = float(sig_line.iloc[-1])
            sl_2 = float(sig_line.iloc[-2])
            cross_down = ml_2 >= sl_2 and ml_1 < sl_1
            if not cross_down:
                logger.info(f"[MTF-MACD] no death_cross | MACD: {ml_2:.4f}->{ml_1:.4f} | Signal: {sl_2:.4f}->{sl_1:.4f} | df30m_len={len(self.df_30m)}")
            else:
                macd_ok = True
                logger.info("[MTF] 30m MACD死叉")

        kdj_ok = False
        if self._kdj_30m and len(self._kdj_30m["k"]) >= 2:
            k_line = self._kdj_30m["k"]
            d_line = self._kdj_30m["d"]
            if (float(k_line.iloc[-2]) >= float(d_line.iloc[-2]) and
                    float(k_line.iloc[-1]) < float(d_line.iloc[-1]) and
                    float(k_line.iloc[-2]) > 80):
                kdj_ok = True
                logger.info("[MTF] 30m KDJ高位死叉(K>80)")

        return macd_ok or kdj_ok

    def _check_30m_short_signals(self) -> Tuple[int, Dict[str, bool]]:
        bc = self._check_30m_bearish_candlestick()
        tb = self._check_30m_trendline_break_down()
        dc = self._check_30m_death_cross()
        mom = self._check_30m_momentum_bearish()
        results = {
            "top_divergence": False,
            "bearish_candlestick": bc,
            "trendline_break_down": tb,
            "death_cross": dc,
            "momentum": mom,
        }
        count = sum(1 for v in results.values() if v)
        if count == 0:
            macd_info = ""
            if self._macd_30m and len(self._macd_30m.get("macd", [])) >= 2:
                ml = float(self._macd_30m["macd"].iloc[-1])
                sl = float(self._macd_30m["signal"].iloc[-1])
                macd_info = f", MACD={ml:.4f}/Signal={sl:.4f}"
            logger.debug(f"[MTF-DEBUG] 30m做空信号全部False | df_30m_len={len(self.df_30m)}{macd_info}")
        return count, results

    def _check_30m_signals(self) -> Tuple[int, Dict[str, bool]]:
        bc = self._check_30m_bullish_candlestick()
        tb = self._check_30m_trendline_break()
        gc = self._check_30m_golden_cross()
        mom = self._check_30m_momentum_bullish()
        results = {
            "divergence": False,
            "bullish_candlestick": bc,
            "trendline_break": tb,
            "golden_cross": gc,
            "momentum": mom,
        }
        count = sum(1 for v in results.values() if v)
        return count, results

    def _check_long_exit_signals(self) -> Dict[str, bool]:
        signals = {
            "bearish_candlestick": self._check_30m_bearish_candlestick(),
            "trendline_break_down": self._check_30m_trendline_break_down(),
            "death_cross": self._check_30m_death_cross(),
        }
        return signals

    def _check_short_exit_signals(self) -> Dict[str, bool]:
        signals = {
            "bullish_candlestick": self._check_30m_bullish_candlestick(),
            "trendline_break": self._check_30m_trendline_break(),
            "golden_cross": self._check_30m_golden_cross(),
        }
        return signals

    def _generate_long_exit_signal(self) -> Optional[Dict]:
        price = float(self.df_4h.iloc[-1]["close"])

        top_k1k2 = self._check_4h_top_fractal_k1k2()
        if top_k1k2.has_structure and top_k1k2.is_k3_forming:
            logger.info("[LONG退出] 检测到提前顶分型K1/K2结构 → PARTIAL_CLOSE 60%")
            return {
                "action": "PARTIAL_CLOSE_LONG",
                "strategy": self.name,
                "reason": "提前顶分型→平60%",
                "timestamp": self.df_4h.iloc[-1].get("open_time", pd.Timestamp.now()),
                "price": price,
                "close_ratio": 0.60,
            }

        has_top_fractal, _, _ = self._check_4h_top_fractal()
        if has_top_fractal:
            logger.info("[LONG退出] 检测到标准顶分型确认 → CLOSE_LONG")
            signal = {
                "action": "CLOSE_LONG",
                "strategy": self.name,
                "reason": "顶分型确认→平剩余",
                "timestamp": self.df_4h.iloc[-1].get("open_time", pd.Timestamp.now()),
                "price": price,
            }

            in_resistance, _ = self._check_resistance_zone()
            if in_resistance:
                short_count, short_signals = self._check_30m_short_signals()
                if short_count >= self.min_signal_count:
                    short_active = [name for name, active in short_signals.items() if active]
                    signal["action"] = "REVERSE_TO_SHORT"
                    signal["reason"] = f"顶分型确认+阻力区→反手做空({', '.join(short_active)})"
                    signal["short_signals"] = short_active
                    signal["short_position_info"] = {
                        "entry_price": price,
                        "probe_ratio": self.probe_ratio,
                        "confirm_ratio": self.confirm_ratio,
                    }
                    logger.info("[REVERSE_TO_SHORT] 多单退出反手做空")
            return signal

        exit_signals = self._check_long_exit_signals()
        signal_count = sum(1 for v in exit_signals.values() if v)

        if signal_count < self.min_signal_count:
            return None

        active_signals = [name for name, active in exit_signals.items() if active]
        logger.info(
            f"[LONG退出] 30m做多退出信号: {', '.join(active_signals)} "
            f"({signal_count}/{self.min_signal_count})"
        )

        signal = {
            "action": "CLOSE_LONG",
            "strategy": self.name,
            "reason": f"30m反转信号: {', '.join(active_signals)}",
            "timestamp": self.df_4h.iloc[-1].get("open_time", pd.Timestamp.now()),
            "price": price,
        }

        in_resistance, _ = self._check_resistance_zone()
        has_top_fractal2, _, _ = self._check_4h_top_fractal()

        if in_resistance and has_top_fractal2:
            short_count, short_signals = self._check_30m_short_signals()
            if short_count >= self.min_signal_count:
                short_active = [name for name, active in short_signals.items() if active]
                signal["action"] = "REVERSE_TO_SHORT"
                signal["reason"] += f" → 反手做空({', '.join(short_active)})"
                signal["short_signals"] = short_active
                signal["short_position_info"] = {
                    "entry_price": price,
                    "probe_ratio": self.probe_ratio,
                    "confirm_ratio": self.confirm_ratio,
                }
                logger.info("[REVERSE_TO_SHORT] 多单退出立即反手做空")

        return signal

    def _generate_short_exit_signal(self) -> Optional[Dict]:
        price = float(self.df_4h.iloc[-1]["close"])

        bottom_k1k2 = self._check_4h_bottom_fractal_k1k2()
        if bottom_k1k2.has_structure and bottom_k1k2.is_k3_forming:
            logger.info("[SHORT退出] 检测到提前底分型K1/K2结构 → PARTIAL_CLOSE 60%")
            return {
                "action": "PARTIAL_CLOSE_SHORT",
                "strategy": self.name,
                "reason": "提前底分型→平60%",
                "timestamp": self.df_4h.iloc[-1].get("open_time", pd.Timestamp.now()),
                "price": price,
                "close_ratio": 0.60,
            }

        has_bottom_fractal, _, _ = self._check_4h_bottom_fractal()
        if has_bottom_fractal:
            logger.info("[SHORT退出] 检测到标准底分型确认 → CLOSE_SHORT")
            signal = {
                "action": "CLOSE_SHORT",
                "strategy": self.name,
                "reason": "底分型确认→平剩余",
                "timestamp": self.df_4h.iloc[-1].get("open_time", pd.Timestamp.now()),
                "price": price,
            }

            in_support, _ = self._check_support_zone()
            if in_support:
                long_count, long_signals = self._check_30m_signals()
                if long_count >= self.min_signal_count:
                    long_active = [name for name, active in long_signals.items() if active]
                    signal["action"] = "REVERSE_TO_LONG"
                    signal["reason"] = f"底分型确认+支撑区→反手做多({', '.join(long_active)})"
                    signal["long_signals"] = long_active
                    signal["long_position_info"] = {
                        "entry_price": price,
                        "probe_ratio": self.probe_ratio,
                        "confirm_ratio": self.confirm_ratio,
                    }
                    logger.info("[REVERSE_TO_LONG] 空单退出反手做多")
            return signal

        exit_signals = self._check_short_exit_signals()
        signal_count = sum(1 for v in exit_signals.values() if v)

        if signal_count < self.min_signal_count:
            return None

        active_signals = [name for name, active in exit_signals.items() if active]
        logger.info(
            f"[SHORT退出] 30m做空退出信号: {', '.join(active_signals)} "
            f"({signal_count}/{self.min_signal_count})"
        )

        signal = {
            "action": "CLOSE_SHORT",
            "strategy": self.name,
            "reason": f"30m反转信号: {', '.join(active_signals)}",
            "timestamp": self.df_4h.iloc[-1].get("open_time", pd.Timestamp.now()),
            "price": price,
        }

        in_support, _ = self._check_support_zone()
        has_bottom_fractal2, _, _ = self._check_4h_bottom_fractal()

        if in_support and has_bottom_fractal2:
            long_count, long_signals = self._check_30m_signals()
            if long_count >= self.min_signal_count:
                long_active = [name for name, active in long_signals.items() if active]
                signal["action"] = "REVERSE_TO_LONG"
                signal["reason"] += f" → 反手做多({', '.join(long_active)})"
                signal["long_signals"] = long_active
                signal["long_position_info"] = {
                    "entry_price": price,
                    "probe_ratio": self.probe_ratio,
                    "confirm_ratio": self.confirm_ratio,
                }
                logger.info("[REVERSE_TO_LONG] 空单退出立即反手做多")

        return signal

    def _get_30m_signal_low(self) -> float:
        if self.df_30m.empty:
            return 0.0
        return float(self.df_30m.iloc[-3:]["low"].min())

    def _get_30m_signal_high(self) -> float:
        if self.df_30m.empty:
            return 0.0
        return float(self.df_30m.iloc[-3:]["high"].max())

    def _check_risk(self, balance: float, stop_loss: float, entry_price: float,
                    qty: float) -> Tuple[bool, float]:
        if datetime.now().date() != self._current_date:
            self._current_date = datetime.now().date()
            self._daily_pnl = 0.0
            self._daily_stopped = False

        if self._daily_stopped:
            logger.warning("[MTF] 日亏损已达5%，今日停止交易")
            return False, qty

        if self._trading_paused:
            logger.warning("[MTF] 连续3次止损，交易已暂停")
            return False, qty

        price_diff = abs(entry_price - stop_loss)
        if price_diff <= 0:
            return False, qty

        loss_per_unit = price_diff
        max_loss = balance * self.max_loss_per_trade_pct
        safe_qty = max_loss / loss_per_unit if loss_per_unit > 0 else qty
        safe_qty = round(safe_qty, 3)

        if safe_qty < qty:
            logger.info(f"[MTF] 风控调整: qty {qty}→{safe_qty} (单笔亏损限制≤${max_loss:.2f})")
            return True, safe_qty
        return True, qty

    def _check_risk_short(self, balance: float, stop_loss: float, entry_price: float,
                          qty: float) -> Tuple[bool, float]:
        if datetime.now().date() != self._current_date:
            self._current_date = datetime.now().date()
            self._daily_pnl = 0.0
            self._daily_stopped = False

        if self._daily_stopped:
            logger.warning("[MTF] 日亏损已达5%，今日停止交易")
            return False, qty

        if self._trading_paused:
            logger.warning("[MTF] 连续3次止损，交易已暂停")
            return False, qty

        price_diff = abs(stop_loss - entry_price)
        if price_diff <= 0:
            return False, qty

        loss_per_unit = price_diff
        max_loss = balance * self.max_loss_per_trade_pct
        safe_qty = max_loss / loss_per_unit if loss_per_unit > 0 else qty
        safe_qty = round(safe_qty, 3)

        if safe_qty < qty:
            logger.info(f"[MTF] 做空风控调整: qty {qty}→{safe_qty} (单笔亏损限制≤${max_loss:.2f})")
            return True, safe_qty
        return True, qty

    def generate_signal(self, bar_idx: int = None) -> Optional[Dict[str, Any]]:
        if self.df_4h.empty or self.df_30m.empty:
            return None

        if bar_idx is not None:
            return self._generate_signal_internal()
        else:
            return self._generate_signal_internal()

    def _generate_signal_internal(self) -> Optional[Dict[str, Any]]:
        self._check_date_reset()

        if self._daily_stopped or self._trading_paused:
            return None

        current_time = self.df_4h.iloc[-1].get("open_time", pd.Timestamp.now())
        if (self._last_signal_time is not None and current_time <= self._last_signal_time):
            return None
        self._last_signal_time = current_time

        if self.position_state.direction is None:
            early_entry_signal = self._generate_early_entry_signal()
            early_short_entry_signal = self._generate_early_short_entry_signal()
            
            if early_entry_signal and early_short_entry_signal:
                early_long_count = early_entry_signal.get("satisfied_count", 0)
                early_short_count = early_short_entry_signal.get("satisfied_count", 0)
                if early_short_count > early_long_count:
                    logger.info(f"[MTF] 提前入场双向冲突: 做多{early_long_count} vs 做空{early_short_count}，选择做空")
                    return early_short_entry_signal
                else:
                    logger.info(f"[MTF] 提前入场双向冲突: 做多{early_long_count} vs 做空{early_short_count}，选择做多")
                    return early_entry_signal
            
            if early_entry_signal:
                return early_entry_signal
            
            if early_short_entry_signal:
                return early_short_entry_signal
            
            long_signal = self._generate_entry_signal()
            short_signal = self._generate_short_entry_signal()
            if long_signal and short_signal:
                long_count = sum(1 for v in long_signal.get("signal_details", {}).values() if v)
                short_count = sum(1 for v in short_signal.get("signal_details", {}).values() if v)
                if short_count > long_count:
                    logger.info(f"[MTF] 双向信号比较: 做多{long_count} vs 做空{short_count}，选择做空")
                    self._last_short_signal_time = current_time
                    return short_signal
                else:
                    logger.info(f"[MTF] 双向信号比较: 做多{long_count} vs 做空{short_count}，选择做多")
                    return long_signal
            if long_signal:
                return long_signal
            if short_signal:
                self._last_short_signal_time = current_time
                return short_signal
            
            return None
        elif self.position_state.direction == "long":
            exit_signal = self._generate_long_exit_signal()
            if exit_signal:
                return exit_signal
            if not self.position_state.confirm_added:
                state = self.position_state
                current_close = float(self.df_4h.iloc[-1]["close"])
                if (state.probe_entry_price and state.probe_entry_price > 0 and 
                    current_close < state.probe_entry_price * 0.99):
                    logger.info(f"[MTF] 试探做多仓位亏损{(1-current_close/state.probe_entry_price)*100:.1f}%>1%, 不加仓")
                else:
                    confirm_signal = self._generate_confirm_signal()
                    if confirm_signal:
                        return confirm_signal
        elif self.position_state.direction == "short":
            exit_signal = self._generate_short_exit_signal()
            if exit_signal:
                return exit_signal
            if not self.position_state.confirm_added:
                if (self._last_short_signal_time is not None and current_time <= self._last_short_signal_time):
                    return None
                self._last_short_signal_time = current_time
                state = self.position_state
                current_close = float(self.df_4h.iloc[-1]["close"])
                if (state.probe_entry_price and state.probe_entry_price > 0 and
                    current_close > state.probe_entry_price * 1.01):
                    logger.info(f"[MTF] 试探做空仓位亏损{(current_close/state.probe_entry_price-1)*100:.1f}%>1%, 不加仓")
                else:
                    confirm_signal = self._generate_short_confirm_signal()
                    if confirm_signal:
                        return confirm_signal

        return None

    def load_data_for_backtest(self, df_4h: pd.DataFrame, df_30m: pd.DataFrame = None, df_15m: pd.DataFrame = None, df_daily: pd.DataFrame = None):
        self.inject_data(df_4h, df_30m, df_15m, df_daily)
        self._last_processed_signal_ts = None
        self._backtest_mode = True
        logger.info(f"[MTF] 回测数据加载: 4h={len(df_4h)}行, 30m={len(df_30m) if df_30m is not None else 0}行, 15m={len(df_15m) if df_15m is not None else 0}行")

    def _process_data(self):
        df_30m_full = getattr(self, '_df_30m_full', self.df_30m)
        df_30m_sliced = df_30m_full
        if not self.df_4h.empty and not df_30m_full.empty:
            last_4h_time = self.df_4h.iloc[-1].get("open_time", None)
            if last_4h_time is not None:
                mask = df_30m_full["open_time"] <= last_4h_time
                df_30m_sliced = df_30m_full[mask].copy()
        self.inject_data(self.df_4h, df_30m_sliced, self.df_15m, self.df_daily)

    def generate_all_pending_signals(self, bar_idx: int) -> List[Dict[str, Any]]:
        signal = self.generate_signal(bar_idx=bar_idx)
        return [signal] if signal else []

    def extend_cooldown_after_loss(self, position_type: str = "long") -> None:
        self.on_stop_loss()

    def _check_date_reset(self):
        today = datetime.now().date()
        if today != self._current_date:
            self._current_date = today
            self._daily_pnl = 0.0
            self._daily_stopped = False
            logger.info("[MTF] 新交易日，重置风控状态")

    def _generate_entry_signal(self) -> Optional[Dict[str, Any]]:
        in_zone, support_level = self._check_support_zone()
        if not in_zone:
            return None

        has_bottom, k1_idx, k2_idx = self._check_4h_bottom_fractal()
        if not has_bottom:
            return None

        signal_count, signal_details = self._check_30m_signals()
        logger.info(f"[MTF] 30m信号检测: {signal_details}, 满足数={signal_count}/4")
        if signal_count < self.min_signal_count:
            logger.info(f"[MTF] 30m信号不足({signal_count}<{self.min_signal_count})，不触发入场")
            return None

        entry_price = float(self.df_4h.iloc[-1]["close"])
        signal_30m_low = self._get_30m_signal_low()
        df_ref = self.df_processed if not self.df_processed.empty else self.df_4h
        k2_low = float(df_ref.iloc[k2_idx]["low"])
        stop_loss = k2_low - self.stop_offset
        if self.current_atr > 0:
            atr_stop = entry_price - self.current_atr * self.atr_multiplier
            stop_loss = min(stop_loss, atr_stop)
        liq_price = entry_price * (1 - 1 / self.leverage)
        if stop_loss < liq_price:
            stop_loss = liq_price + 1.0

        position_ratio = self.probe_ratio

        if self.enable_trend_filter:
            trend = self._check_daily_trend("long")
            if trend == "block":
                return None
            if trend == "reduce":
                position_ratio = self.probe_ratio * 0.5
                logger.info("[MTF] 逆势做多降仓50%")
        if self.enable_volume_filter and self._check_volume_shrinkage():
            position_ratio = self.probe_ratio * 0.5
            logger.info("[MTF] 缩量做多降仓50%")

        take_profit = entry_price + (entry_price - stop_loss) * self.profit_loss_ratio

        logger.info(f"[MTF] 试探性入场条件满足 | 支撑位={support_level} | "
                   f"入场价={entry_price:.2f} | 止损={stop_loss:.2f} | 止盈={take_profit:.2f}")

        if signal_count > 0:
            fractal_dist = abs(entry_price - k2_low) / k2_low
            if fractal_dist > 0.04:
                logger.info(f"[MTF] 做多入口距底分型{fractal_dist*100:.1f}%>4%, 不交易")
                return None

        return {
            "action": "PROBE_ENTRY",
            "type": "probe",
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "position": "long",
            "position_ratio": position_ratio,
            "reason": f"多周期共振底分型@{support_level}",
            "k1_idx": k1_idx,
            "k2_idx": k2_idx,
            "signal_details": signal_details,
            "leverage": self.leverage,
        }

    def _generate_confirm_signal(self) -> Optional[Dict[str, Any]]:
        if len(self.df_4h) < 1:
            return None
        current = self.df_4h.iloc[-1]
        k3_close = float(current["close"])
        k2_idx = self.position_state.k2_idx
        df_ref = self.df_processed if not self.df_processed.empty else self.df_4h
        if k2_idx < 0 or k2_idx >= len(df_ref):
            return None
        k2_high = float(df_ref.iloc[k2_idx]["high"])
        k2_low = float(df_ref.iloc[k2_idx]["low"])
        current_idx = len(self.df_4h) - 1

        if current_idx <= k2_idx:
            return None

        if k3_close > k2_high:
            new_stop = k2_low - self.stop_offset
            confirm_ratio = self.investment_ratio - self.early_entry_ratio if self.position_state.is_early_entry else self.confirm_ratio
            logger.info(f"[MTF] K3确认加仓: K3收盘{k3_close:.2f} > K2最高{k2_high:.2f}, "
                       f"新止损→{new_stop:.2f}, 加仓比例→{confirm_ratio:.0%}")
            return {
                "action": "CONFIRM_ADD",
                "type": "confirm",
                "entry_price": k3_close,
                "stop_loss": new_stop,
                "position": "long",
                "position_ratio": confirm_ratio,
                "reason": f"K3确认@{k3_close:.2f}>{k2_high:.2f}",
                "k3_idx": current_idx,
                "leverage": self.leverage,
            }
        return None

    def _check_daily_trend(self, direction: str = "long") -> str:
        if self.df_daily.empty or len(self.df_daily) < 60:
            logger.info(f"[MTF] 日线数据不足({len(self.df_daily) if not self.df_daily.empty else 0}k)，减半仓位")
            return "reduce"
        closes = self.df_daily["close"].astype(float)
        ema20 = closes.ewm(span=20, adjust=False).mean()
        ema60 = closes.ewm(span=60, adjust=False).mean()
        if direction == "long" and float(ema20.iloc[-1]) < float(ema60.iloc[-1]) * 0.98:
            logger.info("[MTF] 日线EMA20<EMA60*0.98，空头趋势，禁止做多")
            return "block"
        if direction == "short" and float(ema20.iloc[-1]) > float(ema60.iloc[-1]) * 1.02:
            logger.info("[MTF] 日线EMA20>EMA60*1.02，多头趋势，禁止做空")
            return "block"
        if direction == "long" and float(ema20.iloc[-1]) < float(ema60.iloc[-1]):
            logger.info("[MTF] 日线EMA20<EMA60，弱空头趋势，减半做多仓位")
            return "reduce"
        if direction == "short" and float(ema20.iloc[-1]) > float(ema60.iloc[-1]):
            logger.info("[MTF] 日线EMA20>EMA60，弱多头趋势，减半做空仓位")
            return "reduce"
        return "ok"

    def _check_4h_trend(self, direction: str = "long") -> str:
        if len(self.df_4h) < 60 or "SMA20" not in self._sma_4h:
            logger.info(f"[MTF] 4h数据不足({len(self.df_4h)}k)，无法判断4h趋势，放行")
            return "ok"
        sma20 = float(self._sma_4h["SMA20"].iloc[-1])
        sma60 = float(self._sma_4h["SMA60"].iloc[-1])
        if direction == "long":
            if sma20 < sma60:
                logger.info(f"[MTF] 4h SMA20({sma20:.2f})<SMA60({sma60:.2f})，空头趋势，禁止做多")
                return "block"
            return "ok"
        else:
            if sma20 > sma60:
                logger.info(f"[MTF] 4h SMA20({sma20:.2f})>SMA60({sma60:.2f})，多头趋势，禁止做空")
                return "block"
            return "ok"

    def _check_strong_rally_avoid(self) -> bool:
        if len(self.df_4h) < 5:
            return False
        recent = self.df_4h.iloc[-5:]
        bullish_count = 0
        for i in range(5):
            row = recent.iloc[i]
            o = float(row["open"])
            c = float(row["close"])
            if c > o and c / o - 1 >= 0.003:
                bullish_count += 1
        if bullish_count >= 4:
            logger.info(f"[MTF] 4h连续{bullish_count}根强势阳线，避免做空")
            return True
        return False

    def _check_volume_shrinkage(self) -> bool:
        if self.df_30m.empty or len(self.df_30m) < 20:
            return False
        volumes = self.df_30m["volume"].astype(float)
        avg_vol = float(volumes.iloc[-20:].mean())
        last_vol = float(volumes.iloc[-1])
        if last_vol < avg_vol * 0.6:
            logger.info(f"[MTF] 30m成交量萎缩: {last_vol:.0f} < 均量{avg_vol:.0f}*0.6")
            return True
        return False

    def _generate_short_entry_signal(self) -> Optional[Dict[str, Any]]:
        in_zone, resistance_level = self._check_resistance_zone()
        if not in_zone:
            return None

        has_top, k1_idx, k2_idx = self._check_4h_top_fractal()
        if not has_top:
            return None

        signal_count, signal_details = self._check_30m_short_signals()
        logger.info(f"[MTF] 30m做空信号检测: {signal_details}, 满足数={signal_count}/4")
        if signal_count < self.min_signal_count:
            logger.info(f"[MTF] 30m做空信号不足({signal_count}<{self.min_signal_count})，不触发入场")
            return None

        entry_price = float(self.df_4h.iloc[-1]["close"])
        signal_30m_high = self._get_30m_signal_high()
        df_ref = self.df_processed if not self.df_processed.empty else self.df_4h
        k2_high = float(df_ref.iloc[k2_idx]["high"])
        stop_loss = k2_high + self.stop_offset
        if self.current_atr > 0:
            atr_stop = entry_price + self.current_atr * self.atr_multiplier
            stop_loss = max(stop_loss, atr_stop)
        liq_price = entry_price * (1 + 1 / self.leverage)
        if stop_loss > liq_price:
            stop_loss = liq_price - 1.0

        position_ratio = self.probe_ratio

        if self.enable_trend_filter:
            trend_signal = self._check_daily_trend("short")
            if trend_signal == "block":
                return None
            if trend_signal == "reduce":
                position_ratio *= 0.5

        if self.enable_volume_filter:
            if self._check_volume_shrinkage():
                position_ratio *= 0.5

        if self._check_strong_rally_avoid():
            return None

        take_profit = entry_price - (stop_loss - entry_price) * self.profit_loss_ratio

        logger.info(f"[MTF] 做空试探入场条件满足 | 阻力位={resistance_level} | "
                   f"入场价={entry_price:.2f} | 止损={stop_loss:.2f} | 止盈={take_profit:.2f}")

        if signal_count > 0:
            fractal_dist = abs(entry_price - k2_high) / k2_high
            if fractal_dist > 0.03:
                logger.info(f"[MTF] 做空入口距顶分型{fractal_dist*100:.1f}%>3%, 不交易")
                return None

        return {
            "action": "PROBE_ENTRY_SHORT",
            "type": "probe_short",
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "position": "short",
            "position_ratio": position_ratio,
            "reason": f"多周期共振顶分型@{resistance_level}",
            "k1_idx": k1_idx,
            "k2_idx": k2_idx,
            "signal_details": signal_details,
            "leverage": self.leverage,
        }

    def _generate_short_confirm_signal(self) -> Optional[Dict[str, Any]]:
        if len(self.df_4h) < 1:
            return None
        current = self.df_4h.iloc[-1]
        k3_close = float(current["close"])
        k2_idx = self.position_state.k2_idx
        df_ref = self.df_processed if not self.df_processed.empty else self.df_4h
        if k2_idx < 0 or k2_idx >= len(df_ref):
            return None
        k2_high = float(df_ref.iloc[k2_idx]["high"])
        k2_low = float(df_ref.iloc[k2_idx]["low"])
        current_idx = len(self.df_4h) - 1

        if current_idx <= k2_idx:
            return None

        if k3_close < k2_low:
            new_stop = k2_high + self.stop_offset
            confirm_ratio = self.investment_ratio - self.early_short_entry_ratio if self.position_state.is_early_entry else self.confirm_ratio
            logger.info(f"[MTF] K3确认做空加仓: K3收盘{k3_close:.2f} < K2最低{k2_low:.2f}, "
                       f"新止损→{new_stop:.2f}, 加仓比例→{confirm_ratio:.0%}")
            return {
                "action": "CONFIRM_ADD_SHORT",
                "type": "confirm_short",
                "entry_price": k3_close,
                "stop_loss": new_stop,
                "position": "short",
                "position_ratio": confirm_ratio,
                "reason": f"K3确认做空@{k3_close:.2f}<{k2_low:.2f}",
                "k3_idx": current_idx,
                "leverage": self.leverage,
            }
        return None

    def update_position_from_signal(self, signal: Dict[str, Any]):
        sig_type = signal.get("type", "")
        if sig_type == "probe":
            self.position_state.direction = "long"
            self.position_state.probe_entry_price = signal.get("entry_price", 0)
            self.position_state.k1_idx = signal.get("k1_idx", -1)
            self.position_state.k2_idx = signal.get("k2_idx", -1)
            self.position_state.stop_loss_price = signal.get("stop_loss", 0)
            self.position_state.confirm_added = False
            self.position_state.k3_idx = -1
            logger.info(f"[MTF] 更新持仓: 试探入场, 止损={signal.get('stop_loss', 0):.2f}")
        elif sig_type == "probe_short":
            self.position_state.direction = "short"
            self.position_state.probe_entry_price = signal.get("entry_price", 0)
            self.position_state.k1_idx = signal.get("k1_idx", -1)
            self.position_state.k2_idx = signal.get("k2_idx", -1)
            self.position_state.stop_loss_price = signal.get("stop_loss", 0)
            self.position_state.confirm_added = False
            self.position_state.k3_idx = -1
            logger.info(f"[MTF] 更新持仓: 做空试探入场, 止损={signal.get('stop_loss', 0):.2f}")
        elif sig_type == "confirm":
            self.position_state.confirm_added = True
            self.position_state.k3_idx = signal.get("k3_idx", -1)
            self.position_state.stop_loss_price = signal.get("stop_loss", 0)
            logger.info(f"[MTF] 更新持仓: 确认加仓, 新止损={signal.get('stop_loss', 0):.2f}")
        elif sig_type == "confirm_short":
            self.position_state.confirm_added = True
            self.position_state.k3_idx = signal.get("k3_idx", -1)
            self.position_state.stop_loss_price = signal.get("stop_loss", 0)
            logger.info(f"[MTF] 更新持仓: 做空确认加仓, 新止损={signal.get('stop_loss', 0):.2f}")
        elif sig_type == "early_entry":
            self.position_state.direction = "long"
            self.position_state.probe_entry_price = signal.get("entry_price", 0)
            self.position_state.k1_idx = signal.get("k1_idx", -1)
            self.position_state.k2_idx = signal.get("k2_idx", -1)
            self.position_state.k3_idx = signal.get("k3_idx", -1)
            self.position_state.stop_loss_price = signal.get("stop_loss", 0)
            self.position_state.confirm_added = False
            self.position_state.is_early_entry = True
            logger.info(f"[MTF] 更新持仓: 提前入场, 止损={signal.get('stop_loss', 0):.2f}, 满足条件={signal.get('satisfied_count', 0)}")
        elif sig_type == "early_short_entry":
            self.position_state.direction = "short"
            self.position_state.probe_entry_price = signal.get("entry_price", 0)
            self.position_state.k1_idx = signal.get("k1_idx", -1)
            self.position_state.k2_idx = signal.get("k2_idx", -1)
            self.position_state.k3_idx = signal.get("k3_idx", -1)
            self.position_state.stop_loss_price = signal.get("stop_loss", 0)
            self.position_state.confirm_added = False
            self.position_state.is_early_entry = True
            logger.info(f"[MTF] 更新持仓: 提前做空, 止损={signal.get('stop_loss', 0):.2f}, 满足条件={signal.get('satisfied_count', 0)}")

    def clear_position(self):
        self.position_state = MTFPositionState()

    def on_stop_loss(self):
        self._consecutive_stops += 1
        logger.warning(f"[MTF] 止损触发! 连续止损次数={self._consecutive_stops}/{self.max_consecutive_stops}")
        if self._consecutive_stops >= self.max_consecutive_stops:
            self._trading_paused = True
            logger.error(f"[MTF] 连续{self._consecutive_stops}次止损，暂停交易!")

    def on_profit(self):
        self._consecutive_stops = 0
        self._trading_paused = False

    def update_daily_pnl(self, pnl: float):
        prev_date = self._current_date
        self._current_date = datetime.now().date()
        if self._current_date != prev_date:
            self._daily_pnl = 0.0
            self._daily_stopped = False
        self._daily_pnl += pnl
        total_capital = 10000
        if abs(self._daily_pnl) >= total_capital * self.max_daily_loss_pct:
            self._daily_stopped = True
            logger.error(f"[MTF] 日亏损${abs(self._daily_pnl):.2f}≥{total_capital * self.max_daily_loss_pct:.2f}，停止当日交易")

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "symbol": self.symbol,
            "position_direction": self.position_state.direction,
            "confirm_added": self.position_state.confirm_added,
            "support_levels": self.support_levels,
            "consecutive_stops": self._consecutive_stops,
            "trading_paused": self._trading_paused,
            "daily_stopped": self._daily_stopped,
            "daily_pnl": self._daily_pnl,
        }


class MultiTFFractalStrategyExecutor:

    def __init__(
        self,
        client,
        symbol: str = "ETHUSDC",
        check_interval: int = 60,
        support_levels: List[float] = None,
        support_threshold: float = 10.0,
        probe_ratio: float = 0.40,
        confirm_ratio: float = 0.40,
        leverage: int = 20,
        investment_ratio: float = 0.10,
        max_loss_per_trade_pct: float = 0.02,
        max_consecutive_stops: int = 3,
        max_daily_loss_pct: float = 0.05,
        trendline_period: int = 20,
        stop_offset: float = 5.0,
        resistance_levels: List[float] = None,
        resistance_threshold: float = 10.0,
        profit_loss_ratio: float = 2.5,
        enable_trend_filter: bool = True,
        enable_volume_filter: bool = True,
        atr_period: int = 14,
        atr_multiplier: float = 5.0,
        enable_early_entry: bool = True,
        early_entry_min_confidence: float = 0.6,
        k3_second_half_threshold: float = 0.4,
        early_entry_ratio: float = 0.40,
        min_early_entry_conditions: int = 2,
    ):
        self.client = client
        self.symbol = symbol
        self.check_interval = check_interval
        self.is_running = False
        self.leverage = leverage
        self.investment_ratio = investment_ratio
        self.enable_early_entry = enable_early_entry

        self.strategy = MultiTFFractalStrategy(
            symbol=symbol,
            support_levels=support_levels,
            support_threshold=support_threshold,
            probe_ratio=probe_ratio,
            confirm_ratio=confirm_ratio,
            leverage=leverage,
            investment_ratio=investment_ratio,
            max_loss_per_trade_pct=max_loss_per_trade_pct,
            max_consecutive_stops=max_consecutive_stops,
            max_daily_loss_pct=max_daily_loss_pct,
            trendline_period=trendline_period,
            stop_offset=stop_offset,
            resistance_levels=resistance_levels,
            resistance_threshold=resistance_threshold,
            profit_loss_ratio=profit_loss_ratio,
            enable_trend_filter=enable_trend_filter,
            enable_volume_filter=enable_volume_filter,
            atr_period=atr_period,
            atr_multiplier=atr_multiplier,
            enable_early_entry=enable_early_entry,
            early_entry_min_confidence=early_entry_min_confidence,
            early_entry_ratio=early_entry_ratio,
            min_early_entry_conditions=min_early_entry_conditions,
            k3_second_half_threshold=k3_second_half_threshold,
        )

    async def start(self):
        logger.info(f"[MTF Executor] 启动执行器 | symbol={self.symbol} | "
                   f"支撑位={self.strategy.support_levels} | "
                   f"探仓={self.strategy.probe_ratio*100:.0f}% | 加仓={self.strategy.confirm_ratio*100:.0f}%")
        self.is_running = True

        initialized = await self.strategy.initialize(self.symbol)
        if not initialized:
            logger.error("[MTF Executor] 策略初始化失败")
            return

        try:
            while self.is_running:
                await self._run_once()
                await asyncio.sleep(self.check_interval)
        except Exception as e:
            logger.error(f"[MTF Executor] 执行异常: {e}", exc_info=True)
        finally:
            logger.info("[MTF Executor] 执行器已停止")

    async def stop(self):
        self.is_running = False

    async def _run_once(self):
        from ..okx.client import BinanceRestClient

        try:
            binance_client = BinanceRestClient(
                api_key=self.client.api_key,
                secret_key=self.client.secret_key,
                is_simulated=self.client.is_simulated,
            )
            try:
                logger.info("[MTF Executor] 获取4h K线...")
                klines_4h = await binance_client.get_continuous_klines(
                    pair=self.symbol, contractType="PERPETUAL", interval="4h", limit=800,
                )
                if not (isinstance(klines_4h, list) and klines_4h):
                    logger.error("[MTF Executor] 4h K线数据异常")
                    return

                logger.info(f"[MTF Executor] 获取到 {len(klines_4h)} 条4h K线")
                if isinstance(klines_4h, list) and len(klines_4h) > 0:
                    first_t = pd.to_datetime(klines_4h[0][0], unit='ms')
                    last_t = pd.to_datetime(klines_4h[-1][0], unit='ms')
                    delay = (pd.Timestamp.now() - last_t).total_seconds() / 60
                    logger.info(f"[MTF Executor] 4h时间: {first_t} ~ {last_t} (延迟{delay:.1f}分钟)")

                logger.info("[MTF Executor] 获取30m K线...")
                klines_30m = await binance_client.get_continuous_klines(
                    pair=self.symbol, contractType="PERPETUAL", interval="30m", limit=800,
                )
                if not (isinstance(klines_30m, list) and klines_30m):
                    logger.error("[MTF Executor] 30m K线数据异常")
                    return

                logger.info(f"[MTF Executor] 获取到 {len(klines_30m)} 条30m K线")
                if isinstance(klines_30m, list) and len(klines_30m) > 0:
                    first_30 = pd.to_datetime(klines_30m[0][0], unit='ms')
                    last_30 = pd.to_datetime(klines_30m[-1][0], unit='ms')
                    logger.info(f"[MTF Executor] 30m时间: {first_30} ~ {last_30}")

                df_4h = binance_klines_to_dataframe(klines_4h)
                df_30m = binance_klines_to_dataframe(klines_30m)
                
                df_15m = None
                if self.enable_early_entry:
                    logger.info("[MTF Executor] 获取15m K线用于提前入场分析...")
                    klines_15m = await binance_client.get_continuous_klines(
                        pair=self.symbol, contractType="PERPETUAL", interval="15m", limit=1000,
                    )
                    if isinstance(klines_15m, list) and klines_15m:
                        df_15m = binance_klines_to_dataframe(klines_15m)
                        logger.info(f"[MTF Executor] 获取到 {len(df_15m)} 条15m K线")
            finally:
                await binance_client.close()

            if df_4h.empty or df_30m.empty:
                logger.warning("[MTF Executor] K线数据为空")
                return

            self.strategy.inject_data(df_4h, df_30m, df_15m)

            status = self.strategy.get_status()
            logger.info(f"[MTF Executor] 策略状态: 持仓={status['position_direction'] or '空仓'} | "
                       f"加仓确认={status['confirm_added']} | "
                       f"连续止损={status['consecutive_stops']} | "
                       f"风控暂停={status['trading_paused']} | "
                       f"日停={status['daily_stopped']} | "
                       f"提前入场={self.enable_early_entry}")

            signal = self.strategy.generate_signal()
            if signal:
                logger.info(f"[MTF Executor] >>> 信号: action={signal['action']}, "
                           f"reason={signal.get('reason', '')}, ratio={signal.get('position_ratio', 0)}")
                await self._execute_signal(signal)
            else:
                logger.info("[MTF Executor] 无交易信号")

        except Exception as e:
            logger.error(f"[MTF Executor] 运行异常: {e}", exc_info=True)

    async def _execute_signal(self, signal: Dict[str, Any]):
        action = signal.get("action", "")
        try:
            df = self.strategy.df_4h
            current_price = float(df.iloc[-1]["close"]) if not df.empty else 0
            if current_price <= 0:
                logger.error("[MTF Executor] 无法获取当前价格")
                return

            account = await self.client.get_account()
            balance = float(account.get("availableBalance", 0)) if isinstance(account, dict) else 0
            if balance <= 0:
                balance = float(account.get("totalMarginBalance", account.get("balance", 10000)))

            if action == "PROBE_ENTRY":
                await self._open_long_probe(current_price, balance, signal)
            elif action == "CONFIRM_ADD":
                await self._add_long_confirm(current_price, balance, signal)
            elif action == "PROBE_ENTRY_SHORT":
                await self._open_short_probe(current_price, balance, signal)
            elif action == "CONFIRM_ADD_SHORT":
                await self._add_short_confirm(current_price, balance, signal)
            elif action == "EARLY_ENTRY":
                await self._open_early_entry(current_price, balance, signal)
            elif action == "EARLY_SHORT_ENTRY":
                await self._open_early_short_entry(current_price, balance, signal)
            elif action == "CLOSE_LONG":
                await self._close_all_long(balance)
                self.strategy.clear_position()
            elif action == "CLOSE_SHORT":
                await self._close_all_short(balance)
                self.strategy.clear_position()

        except Exception as e:
            logger.error(f"[MTF Executor] 执行信号失败: {e}", exc_info=True)

    async def _open_long_probe(self, price: float, balance: float, signal: Dict[str, Any]):
        stop_loss = signal.get("stop_loss", price * 0.95)
        ratio = signal.get("position_ratio", self.strategy.probe_ratio)
        investment = balance * self.investment_ratio * ratio
        qty = (investment * self.leverage) / price
        qty = round(qty, 3)

        ok, qty = self.strategy._check_risk(balance, stop_loss, price, qty)
        if not ok:
            return

        result = await self.client.place_order(
            symbol=self.symbol, side="BUY", position_side="LONG",
            order_type="MARKET", quantity=qty,
        )
        logger.info(f"[MTF Executor] 试探开多: 投入=${investment:.2f} | qty={qty} | 止损={stop_loss:.2f}")
        self.strategy.update_position_from_signal(signal)
        return result

    async def _add_long_confirm(self, price: float, balance: float, signal: Dict[str, Any]):
        stop_loss = signal.get("stop_loss", price * 0.95)
        ratio = signal.get("position_ratio", self.strategy.confirm_ratio)
        investment = balance * self.investment_ratio * ratio
        qty = (investment * self.leverage) / price
        qty = round(qty, 3)

        ok, qty = self.strategy._check_risk(balance, stop_loss, price, qty)
        if not ok:
            return

        result = await self.client.place_order(
            symbol=self.symbol, side="BUY", position_side="LONG",
            order_type="MARKET", quantity=qty,
        )
        logger.info(f"[MTF Executor] 确认加仓: 投入=${investment:.2f} | qty={qty} | 新止损={stop_loss:.2f}")
        self.strategy.update_position_from_signal(signal)
        return result

    async def _open_early_entry(self, price: float, balance: float, signal: Dict[str, Any]):
        stop_loss = signal.get("stop_loss", price * 0.95)
        ratio = signal.get("position_ratio", self.strategy.early_entry_ratio)
        investment = balance * self.investment_ratio * ratio
        qty = (investment * self.leverage) / price
        qty = round(qty, 3)

        ok, qty = self.strategy._check_risk(balance, stop_loss, price, qty)
        if not ok:
            return

        result = await self.client.place_order(
            symbol=self.symbol, side="BUY", position_side="LONG",
            order_type="MARKET", quantity=qty,
        )
        logger.info(f"[MTF Executor] 提前入场开多: 投入=${investment:.2f} | qty={qty} | "
                   f"止损={stop_loss:.2f} | 置信度={signal.get('confidence', 0):.2f} | "
                   f"信号类型={signal.get('signal_type', '')}")
        self.strategy.update_position_from_signal(signal)
        return result

    async def _open_early_short_entry(self, price: float, balance: float, signal: Dict[str, Any]):
        stop_loss = signal.get("stop_loss", price * 1.05)
        ratio = signal.get("position_ratio", self.strategy.early_short_entry_ratio)
        investment = balance * self.investment_ratio * ratio
        qty = (investment * self.leverage) / price
        qty = round(qty, 3)

        ok, qty = self.strategy._check_risk_short(balance, stop_loss, price, qty)
        if not ok:
            return

        result = await self.client.place_order(
            symbol=self.symbol, side="SELL", position_side="SHORT",
            order_type="MARKET", quantity=qty,
        )
        logger.info(f"[MTF Executor] 提前做空入场: 投入=${investment:.2f} | qty={qty} | "
                   f"止损={stop_loss:.2f} | 置信度={signal.get('confidence', 0):.2f} | "
                   f"信号类型={signal.get('signal_type', '')}")
        self.strategy.update_position_from_signal(signal)
        return result

    async def _open_short_probe(self, price: float, balance: float, signal: Dict[str, Any]):
        stop_loss = signal.get("stop_loss", price * 1.05)
        ratio = signal.get("position_ratio", self.strategy.probe_ratio)
        investment = balance * self.investment_ratio * ratio
        qty = (investment * self.leverage) / price
        qty = round(qty, 3)

        ok, qty = self.strategy._check_risk(balance, stop_loss, price, qty)
        if not ok:
            return

        result = await self.client.place_order(
            symbol=self.symbol, side="SELL", position_side="SHORT",
            order_type="MARKET", quantity=qty,
        )
        logger.info(f"[MTF Executor] 试探开空: 投入=${investment:.2f} | qty={qty} | 止损={stop_loss:.2f}")
        self.strategy.update_position_from_signal(signal)
        return result

    async def _add_short_confirm(self, price: float, balance: float, signal: Dict[str, Any]):
        stop_loss = signal.get("stop_loss", price * 1.05)
        ratio = signal.get("position_ratio", self.strategy.confirm_ratio)
        investment = balance * self.investment_ratio * ratio
        qty = (investment * self.leverage) / price
        qty = round(qty, 3)

        ok, qty = self.strategy._check_risk(balance, stop_loss, price, qty)
        if not ok:
            return

        result = await self.client.place_order(
            symbol=self.symbol, side="SELL", position_side="SHORT",
            order_type="MARKET", quantity=qty,
        )
        logger.info(f"[MTF Executor] 确认做空加仓: 投入=${investment:.2f} | qty={qty} | 新止损={stop_loss:.2f}")
        self.strategy.update_position_from_signal(signal)
        return result

    async def _get_position_quantity(self, side: str) -> float:
        positions = await self.client.get_positions(self.symbol)
        total = 0.0
        for pos in positions:
            pos_amt = float(pos.get("positionAmt", 0))
            if side == "LONG" and pos_amt > 0:
                total += pos_amt
            elif side == "SHORT" and pos_amt < 0:
                total += abs(pos_amt)
        return total

    async def _close_all_long(self, usdt_balance: float):
        qty = await self._get_position_quantity("LONG")
        if qty <= 0:
            logger.info(f"[MTF Executor] 无多单需平仓")
            return
        logger.info(f"[MTF Executor] 平掉全部多单: {qty:.3f}")

        result = await self.client.place_order(
            symbol=self.symbol,
            side="SELL",
            position_side="LONG",
            order_type="MARKET",
            quantity=qty,
        )
        logger.info(f"[MTF Executor] 平多单结果: {result.get('msg', result.get('error', 'OK'))}")

    async def _close_all_short(self, usdt_balance: float):
        qty = await self._get_position_quantity("SHORT")
        if qty <= 0:
            logger.info(f"[MTF Executor] 无空单需平仓")
            return
        logger.info(f"[MTF Executor] 平掉全部空单: {qty:.3f}")

        result = await self.client.place_order(
            symbol=self.symbol,
            side="BUY",
            position_side="SHORT",
            order_type="MARKET",
            quantity=qty,
        )
        logger.info(f"[MTF Executor] 平空单结果: {result.get('msg', result.get('error', 'OK'))}")