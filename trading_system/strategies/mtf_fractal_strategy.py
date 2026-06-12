"""
Crypto_Chan_4H_Master_v1 策略

基于缠论多周期（4H/1H/15M）的双向持仓交易系统。

核心逻辑：
1. 4H 级别判断趋势方向和中枢结构（缠论分型/笔/中枢/背驰）
2. 1H 级别确认信号（MACD、分型验证）
3. 15M 级别精确入场
4. ATR 动态止损止盈
5. 执行指令引擎处理特殊规则（RULE_001~005）
6. 双向持仓对冲管理（趋势模式/震荡模式）
"""

import asyncio
import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd

from .base_strategy import BaseStrategy
from .chan_strategy import ChanStrategy
from .chan_first_buy_strategy import ChanTheoryFirstBuyAnalyzer, ZhongShu
from ..utils.indicators import calculate_macd, binance_klines_to_dataframe, calculate_macd_area, calculate_atr, calculate_ema

logger = logging.getLogger(__name__)


# ==============================================================================
# Crypto_Chan_4H_Master_v1 Strategy
# 基于缠论多周期（4H/1H/15M）的双向持仓交易系统
# ==============================================================================


# ─── 配置模型 Dataclasses ───

@dataclass
class TimeframeConfig:
    """时间框架配置"""
    trend_level: str = "4h"
    structure_level: str = "1h"
    entry_level: str = "15m"

    @classmethod
    def from_dict(cls, d: dict) -> "TimeframeConfig":
        return cls(
            trend_level=d.get("trend_level", "4h"),
            structure_level=d.get("structure_level", "1h"),
            entry_level=d.get("entry_level", "15m"),
        )


@dataclass
class StrategyMetadata:
    """策略元数据"""
    name: str = "Crypto_Chan_4H_Master_v1"
    version: str = "1.0"
    description: str = ""
    base_currency: str = "USDC"
    trading_pairs: List[str] = field(default_factory=lambda: ["BTC/USDC", "ETH/USDC"])
    timeframe_config: TimeframeConfig = field(default_factory=TimeframeConfig)

    @classmethod
    def from_dict(cls, d: dict) -> "StrategyMetadata":
        return cls(
            name=d.get("name", "Crypto_Chan_4H_Master_v1"),
            version=d.get("version", "1.0"),
            description=d.get("description", ""),
            base_currency=d.get("base_currency", "USDC"),
            trading_pairs=d.get("trading_pairs", ["BTC/USDC", "ETH/USDC"]),
            timeframe_config=TimeframeConfig.from_dict(d.get("timeframe_config", {})),
        )


@dataclass
class WeekendModeConfig:
    """周末模式配置"""
    enabled: bool = True
    days: List[str] = field(default_factory=lambda: ["Sat", "Sun"])
    action: str = "reduce_position_to_50_percent_and_no_breakout_trades"

    @classmethod
    def from_dict(cls, d: dict) -> "WeekendModeConfig":
        return cls(
            enabled=d.get("enabled", True),
            days=d.get("days", ["Sat", "Sun"]),
            action=d.get("action", "reduce_position_to_50_percent_and_no_breakout_trades"),
        )


@dataclass
class FundingRateFuseConfig:
    """资金费率熔断配置"""
    threshold: float = 0.001
    condition_gt: str = "disable_long_entry_on_3rd_buy"
    condition_lt: str = "disable_short_entry_on_3rd_sell"

    @classmethod
    def from_dict(cls, d: dict) -> "FundingRateFuseConfig":
        return cls(
            threshold=d.get("threshold", 0.001),
            condition_gt=d.get("condition_gt", "disable_long_entry_on_3rd_buy"),
            condition_lt=d.get("condition_lt", "disable_short_entry_on_3rd_sell"),
        )


@dataclass
class GlobalFiltersConfig:
    """全局过滤器配置"""
    daily_cutoff: str = "0:00"
    weekend_mode: WeekendModeConfig = field(default_factory=WeekendModeConfig)
    funding_rate_fuse: FundingRateFuseConfig = field(default_factory=FundingRateFuseConfig)

    @classmethod
    def from_dict(cls, d: dict) -> "GlobalFiltersConfig":
        return cls(
            daily_cutoff=d.get("daily_cutoff", "0:00"),
            weekend_mode=WeekendModeConfig.from_dict(d.get("weekend_mode", {})),
            funding_rate_fuse=FundingRateFuseConfig.from_dict(d.get("funding_rate_fuse", {})),
        )


@dataclass
class ATRConfig:
    """ATR 指标配置"""
    period: int = 14
    source: str = "4h"
    multiplier_stop_loss: float = 1.5
    multiplier_take_profit: float = 3.0

    @classmethod
    def from_dict(cls, d: dict) -> "ATRConfig":
        return cls(
            period=d.get("period", 14),
            source=d.get("source", "4h"),
            multiplier_stop_loss=d.get("multiplier_stop_loss", 1.5),
            multiplier_take_profit=d.get("multiplier_take_profit", 3.0),
        )


@dataclass
class MACDConfig:
    """MACD 指标配置"""
    fast: int = 12
    slow: int = 26
    signal: int = 9

    @classmethod
    def from_dict(cls, d: dict) -> "MACDConfig":
        return cls(
            fast=d.get("fast", 12),
            slow=d.get("slow", 26),
            signal=d.get("signal", 9),
        )


@dataclass
class IndicatorConfig:
    """指标配置"""
    atr: ATRConfig = field(default_factory=ATRConfig)
    macd: MACDConfig = field(default_factory=MACDConfig)

    @classmethod
    def from_dict(cls, d: dict) -> "IndicatorConfig":
        return cls(
            atr=ATRConfig.from_dict(d.get("atr", {})),
            macd=MACDConfig.from_dict(d.get("macd", {})),
        )


@dataclass
class TradeSetupEntry:
    """单笔交易入场配置"""
    level: str = "4h"
    condition: str = ""
    confirmation_1h: str = ""
    entry_15m: str = ""
    stop_loss: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "TradeSetupEntry":
        return cls(
            level=d.get("level", "4h"),
            condition=d.get("condition", ""),
            confirmation_1h=d.get("confirmation_1h", ""),
            entry_15m=d.get("entry_15m", ""),
            stop_loss=d.get("stop_loss", ""),
        )


@dataclass
class LongSetup:
    """做多入场配置"""
    type_2_buy: TradeSetupEntry = field(default_factory=TradeSetupEntry)
    type_2b_like_buy: TradeSetupEntry = field(default_factory=TradeSetupEntry)

    @classmethod
    def from_dict(cls, d: dict) -> "LongSetup":
        return cls(
            type_2_buy=TradeSetupEntry.from_dict(d.get("type_2_buy", {})),
            type_2b_like_buy=TradeSetupEntry.from_dict(d.get("type_2b_like_buy", {})),
        )


@dataclass
class ShortSetup:
    """做空入场配置"""
    type_2_sell: TradeSetupEntry = field(default_factory=TradeSetupEntry)

    @classmethod
    def from_dict(cls, d: dict) -> "ShortSetup":
        return cls(
            type_2_sell=TradeSetupEntry.from_dict(d.get("type_2_sell", {})),
        )


@dataclass
class TradeLogicConfig:
    """交易逻辑配置"""
    long_setup: LongSetup = field(default_factory=LongSetup)
    short_setup: ShortSetup = field(default_factory=ShortSetup)

    @classmethod
    def from_dict(cls, d: dict) -> "TradeLogicConfig":
        return cls(
            long_setup=LongSetup.from_dict(d.get("long_setup", {})),
            short_setup=ShortSetup.from_dict(d.get("short_setup", {})),
        )


@dataclass
class HedgingRules:
    """对冲规则配置"""
    trend_main_pct: float = 1.0
    trend_hedge_pct: float = 0.3
    trend_trigger: str = "1h divergence against 4h trend"
    range_short_pct: float = 0.5
    range_long_pct: float = 0.5
    range_net_exposure: float = 0.0
    range_exit_rule: str = "Close opposite side if price breaks 4h central pivot."

    @classmethod
    def from_dict(cls, d: dict) -> "HedgingRules":
        trend = d.get("trend_mode", {})
        range_m = d.get("range_mode", {})
        return cls(
            trend_main_pct=float(str(trend.get("main_position", "100%")).rstrip("%")) / 100 if "main_position" in trend else 1.0,
            trend_hedge_pct=float(str(trend.get("hedge_position", "0-30%")).split("-")[-1].rstrip("%")) / 100 if "hedge_position" in trend else 0.3,
            trend_trigger=trend.get("trigger", "1h divergence against 4h trend"),
            range_short_pct=float(str(range_m.get("upper_bound_short", "50%")).rstrip("%")) / 100,
            range_long_pct=float(str(range_m.get("lower_bound_long", "50%")).rstrip("%")) / 100,
            range_net_exposure=float(str(range_m.get("net_exposure", "0%")).rstrip("%")) / 100,
            range_exit_rule=range_m.get("exit_rule", ""),
        )


@dataclass
class SizingConfig:
    """仓位计算配置"""
    method: str = "atr_based"
    risk_per_trade_percent: float = 1.0
    calculation: str = "Position_Size = (Account_Equity * Risk%) / (ATR_4h * 1.5)"

    @classmethod
    def from_dict(cls, d: dict) -> "SizingConfig":
        return cls(
            method=d.get("method", "atr_based"),
            risk_per_trade_percent=float(d.get("risk_per_trade_percent", 1.0)),
            calculation=d.get("calculation", ""),
        )


@dataclass
class PositionManagementConfig:
    """仓位管理配置"""
    hedging_rules: HedgingRules = field(default_factory=HedgingRules)
    sizing: SizingConfig = field(default_factory=SizingConfig)

    @classmethod
    def from_dict(cls, d: dict) -> "PositionManagementConfig":
        return cls(
            hedging_rules=HedgingRules.from_dict(d.get("hedging_rules", {})),
            sizing=SizingConfig.from_dict(d.get("sizing", {})),
        )


@dataclass
class ExecutionDirective:
    """执行指令"""
    directive_id: str = ""
    priority: int = 99
    condition: str = ""
    action: str = ""
    params: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "ExecutionDirective":
        return cls(
            directive_id=d.get("id", ""),
            priority=d.get("priority", 99),
            condition=d.get("condition", ""),
            action=d.get("action", ""),
            params=d.get("params", {}),
        )


@dataclass
class StrategyConfigRoot:
    """策略配置根容器"""
    metadata: StrategyMetadata = field(default_factory=StrategyMetadata)
    global_filters: GlobalFiltersConfig = field(default_factory=GlobalFiltersConfig)
    indicators: IndicatorConfig = field(default_factory=IndicatorConfig)
    trade_logic: TradeLogicConfig = field(default_factory=TradeLogicConfig)
    position_management: PositionManagementConfig = field(default_factory=PositionManagementConfig)
    execution_directives: List[ExecutionDirective] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "StrategyConfigRoot":
        directives = [ExecutionDirective.from_dict(dd) for dd in d.get("execution_directives", [])]
        directives.sort(key=lambda x: x.priority)
        return cls(
            metadata=StrategyMetadata.from_dict(d.get("strategy_metadata", {})),
            global_filters=GlobalFiltersConfig.from_dict(d.get("global_filters", {})),
            indicators=IndicatorConfig.from_dict(d.get("indicators", {})),
            trade_logic=TradeLogicConfig.from_dict(d.get("trade_logic", {})),
            position_management=PositionManagementConfig.from_dict(d.get("position_management", {})),
            execution_directives=directives,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "StrategyConfigRoot":
        return cls.from_dict(json.loads(json_str))


# ─── CCXT 数据适配器 ───
# 从 market_data 模块重导出 CCXTDataProvider，保持向后兼容
# 原有代码可通过 `from mtf_fractal_strategy import CCXTDataProvider` 继续使用
from ..data.market_data import CCXTDataProvider  # noqa: F811 (re-export)


# ─── CryptoChan4HMasterStrategy 核心策略类 ───

class MarketRegime(Enum):
    """市场状态枚举"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGE = "range"
    UNKNOWN = "unknown"


@dataclass
class TradeRecordV2:
    """交易记录数据结构"""
    timestamp: pd.Timestamp
    action: str  # OPEN_LONG, OPEN_SHORT, CLOSE_LONG, CLOSE_SHORT
    price: float
    quantity: float
    pnl: float = 0.0
    reason: str = ""


@dataclass
class HedgingState:
    """对冲持仓状态"""
    long_qty: float = 0.0
    short_qty: float = 0.0
    long_entry_price: float = 0.0
    short_entry_price: float = 0.0
    long_stop_loss: float = 0.0
    short_stop_loss: float = 0.0
    long_take_profit: float = 0.0
    short_take_profit: float = 0.0
    regime: MarketRegime = MarketRegime.UNKNOWN

    @property
    def net_exposure(self) -> float:
        return self.long_qty - self.short_qty

    @property
    def has_long(self) -> bool:
        return self.long_qty > 0

    @property
    def has_short(self) -> bool:
        return self.short_qty > 0


@dataclass
class ChanAnalysisResult:
    """缠论分析结果容器"""
    fractals: List = field(default_factory=list)
    pens: List = field(default_factory=list)
    zhongshu_list: List = field(default_factory=list)
    has_bottom_fractal: bool = False
    has_top_fractal: bool = False
    last_bottom_low: float = 0.0
    last_top_high: float = 0.0
    beichi_bottom: bool = False
    beichi_top: bool = False


class CryptoChan4HMasterStrategy(BaseStrategy):
    """
    Crypto_Chan_4H_Master_v1 策略

    基于缠论4H/1H/15M级别的加密货币交易系统，支持双向持仓与动态对冲。

    核心逻辑：
    1. 4H 级别判断趋势方向和中枢结构
    2. 1H 级别确认信号（MACD、分型）
    3. 15M 级别精确入场
    4. ATR 动态止损止盈
    5. 执行指令引擎处理特殊规则
    6. 双向持仓对冲管理
    """

    def __init__(self, config: StrategyConfigRoot):
        super().__init__(config.metadata.name)
        self.config = config
        self.symbol = config.metadata.trading_pairs[0] if config.metadata.trading_pairs else "ETH/USDC"

        # 多周期数据容器
        self.df_4h: pd.DataFrame = pd.DataFrame()
        self.df_1h: pd.DataFrame = pd.DataFrame()
        self.df_15m: pd.DataFrame = pd.DataFrame()
        self.df_daily: pd.DataFrame = pd.DataFrame()

        # 指标缓存
        self._macd_4h: Dict[str, pd.Series] = {}
        self._macd_1h: Dict[str, pd.Series] = {}
        self._macd_15m: Dict[str, pd.Series] = {}
        self._atr_4h: pd.Series = pd.Series()
        self._atr_1h: pd.Series = pd.Series()
        self._atr_value: float = 0.0

        # 缠论分析结果
        self._chan_4h = ChanAnalysisResult()
        self._chan_1h = ChanAnalysisResult()
        self._chan_15m = ChanAnalysisResult()

        # 缠论引擎实例 (复用 ChanStrategy)
        self._chan_engine_4h = ChanStrategy(symbol="ETHUSDC", time_frame="4h", use_binance_client=False)
        self._chan_engine_1h = ChanStrategy(symbol="ETHUSDC", time_frame="1h", use_binance_client=False)
        self._chan_engine_15m = ChanStrategy(symbol="ETHUSDC", time_frame="15m", use_binance_client=False)
        self._chan_analyzer = ChanTheoryFirstBuyAnalyzer()

        # 持仓和对冲状态
        self.hedging = HedgingState()
        self.trades: List[TradeRecordV2] = []
        self.equity_curve: List[float] = []
        self.initial_capital: float = 10000.0
        self.current_capital: float = 10000.0

        # 日线趋势状态
        self.daily_trend: str = "NEUTRAL"  # UP, DOWN, NEUTRAL
        self._last_daily_refresh_date: Optional[date] = None

        # 资金费率（外部注入）
        self.funding_rate: float = 0.0

        # 执行引擎上下文
        self._market_regime: MarketRegime = MarketRegime.UNKNOWN
        self._last_signal_bar_idx: int = -1

        # 背驰检测状态
        self._beichi_bottom_detected: bool = False
        self._beichi_top_detected: bool = False
        self._first_buy_low: float = 0.0
        self._first_sell_high: float = 0.0

        logger.info(f"[{self.name}] 策略初始化完成: symbol={self.symbol}, "
                   f"timeframes=4H/1H/15M")

    # ─── 数据注入 ───

    def inject_data(self, df_4h: pd.DataFrame, df_1h: pd.DataFrame = None,
                    df_15m: pd.DataFrame = None, df_daily: pd.DataFrame = None) -> None:
        """注入多周期K线数据"""
        if df_4h is not None and not df_4h.empty:
            self.df_4h = df_4h.copy()
        if df_1h is not None and not df_1h.empty:
            self.df_1h = df_1h.copy()
        if df_15m is not None and not df_15m.empty:
            self.df_15m = df_15m.copy()
        if df_daily is not None and not df_daily.empty:
            self.df_daily = df_daily.copy()
        self._calculate_all_indicators()
        self._run_chan_analysis()

    def load_data_for_backtest(self, df_4h: pd.DataFrame, df_1h: pd.DataFrame = None,
                               df_15m: pd.DataFrame = None, df_daily: pd.DataFrame = None) -> None:
        """回测模式数据加载"""
        self.inject_data(df_4h, df_1h, df_15m, df_daily)
        self._backtest_mode = True
        logger.info(f"[{self.name}] 回测数据加载: 4h={len(df_4h)}行, "
                    f"1h={len(df_1h) if df_1h is not None else 0}行, "
                    f"15m={len(df_15m) if df_15m is not None else 0}行")

    # ─── 指标计算 ───

    def _calculate_all_indicators(self) -> None:
        """计算所有技术指标"""
        self._calculate_macd_all()
        self._calculate_atr_all()
        if not self.df_daily.empty:
            self._update_daily_trend()

    def _calculate_macd_all(self) -> None:
        """计算所有周期的 MACD"""
        macd_params = (self.config.indicators.macd.fast,
                       self.config.indicators.macd.slow,
                       self.config.indicators.macd.signal)
        for df, cache, label in [
            (self.df_4h, self._macd_4h, "4h"),
            (self.df_1h, self._macd_1h, "1h"),
            (self.df_15m, self._macd_15m, "15m"),
        ]:
            if not df.empty and len(df) >= 30:
                macd_line, sig_line, hist = calculate_macd(
                    df["close"].astype(float), *macd_params
                )
                cache["macd"] = macd_line
                cache["signal"] = sig_line
                cache["histogram"] = hist

    def _calculate_atr_all(self) -> None:
        """计算所有周期的 ATR"""
        atr_period = self.config.indicators.atr.period
        for df, cache_attr in [(self.df_4h, "_atr_4h"), (self.df_1h, "_atr_1h")]:
            if not df.empty and len(df) >= atr_period + 1:
                atr_series = calculate_atr(df, period=atr_period)
                setattr(self, cache_attr, atr_series)
        if not self._atr_4h.empty:
            self._atr_value = float(self._atr_4h.iloc[-1]) if not pd.isna(self._atr_4h.iloc[-1]) else 0.0

    def get_current_atr(self, source: str = "4h") -> float:
        """获取当前 ATR 值"""
        src = self._atr_4h if source == "4h" else self._atr_1h
        if src.empty:
            return 0.0
        val = float(src.iloc[-1])
        return val if not pd.isna(val) else 0.0

    def _update_daily_trend(self) -> None:
        """更新日线趋势判断（每日 0:00 UTC+8 刷新）"""
        if self.df_daily.empty or len(self.df_daily) < 60:
            self.daily_trend = "NEUTRAL"
            return
        closes = self.df_daily["close"].astype(float)
        ema20 = calculate_ema(closes, 20)
        ema60 = calculate_ema(closes, 60)
        if ema20.empty or ema60.empty:
            self.daily_trend = "NEUTRAL"
            return
        e20 = float(ema20.iloc[-1])
        e60 = float(ema60.iloc[-1])
        if e20 > e60 * 1.02:
            self.daily_trend = "UP"
        elif e20 < e60 * 0.98:
            self.daily_trend = "DOWN"
        else:
            self.daily_trend = "NEUTRAL"

    # ─── 缠论分析 ───

    def _run_chan_analysis(self) -> None:
        """运行缠论分析（分型→笔→中枢→背驰）"""
        for df, engine, result, label in [
            (self.df_4h, self._chan_engine_4h, self._chan_4h, "4H"),
            (self.df_1h, self._chan_engine_1h, self._chan_1h, "1H"),
            (self.df_15m, self._chan_engine_15m, self._chan_15m, "15M"),
        ]:
            if df.empty or len(df) < 10:
                continue
            try:
                engine.df_30m = df.copy()
                engine._process_data()
                result.fractals = getattr(engine, 'fractals', [])
                result.pens = getattr(engine, 'pens', [])
                result.segments = getattr(engine, 'segments', [])
                zhongshu_list = self._identify_zhongshu(result.pens)
                result.zhongshu_list = zhongshu_list
                if result.fractals:
                    recent = result.fractals[-3:] if len(result.fractals) >= 3 else result.fractals
                    for f in recent:
                        if f.type == "bottom":
                            result.has_bottom_fractal = True
                            result.last_bottom_low = f.low
                        if f.type == "top":
                            result.has_top_fractal = True
                            result.last_top_high = f.high
                self._check_beichi(result, engine)
                logger.debug(f"[{self.name}] {label} 缠论: 分型={len(result.fractals)}, "
                           f"笔={len(result.pens)}, 中枢={len(result.zhongshu_list)}, "
                           f"底背驰={result.beichi_bottom}, 顶背驰={result.beichi_top}")
            except Exception as e:
                logger.warning(f"[{self.name}] {label} 缠论分析失败: {e}")

    @staticmethod
    def _identify_zhongshu(pens: List) -> List:
        """
        识别中枢（基于三笔重叠）

        中枢定义：连续三笔的[高、低]区间有重叠
        上升中枢：下-上-下三笔重叠
        下跌中枢：上-下-上三笔重叠
        """
        zhongshu_list = []
        if len(pens) < 3:
            return zhongshu_list
        for i in range(len(pens) - 2):
            p1, p2, p3 = pens[i], pens[i + 1], pens[i + 2]
            high_vals = [p.high for p in [p1, p2, p3]]
            low_vals = [p.low for p in [p1, p2, p3]]
            overlap_high = min(high_vals)
            overlap_low = max(low_vals)
            if overlap_low < overlap_high:
                direction = "up" if p1.direction == "down" else "down"
                zs = ZhongShu(
                    start_idx=p1.start_fractal.idx,
                    end_idx=p3.end_fractal.idx,
                    upper=round(overlap_high, 4),
                    lower=round(overlap_low, 4),
                    direction=direction,
                    zhongshu_range=round(overlap_high - overlap_low, 4),
                )
                zhongshu_list.append(zs)
        merged = []
        for zs in zhongshu_list:
            overlapped = False
            for m in merged:
                if zs.lower < m.upper and zs.upper > m.lower:
                    m.upper = max(m.upper, zs.upper)
                    m.lower = min(m.lower, zs.lower)
                    m.end_idx = max(m.end_idx, zs.end_idx)
                    overlapped = True
                    break
            if not overlapped:
                merged.append(zs)
        return merged

    @staticmethod
    def _check_beichi(result: "ChanAnalysisResult", engine: Any) -> None:
        """
        背驰判断：比较相邻同向笔的 MACD 面积

        底背驰：价格新低，但 MACD 面积（绿柱和）缩小
        顶背驰：价格新高，但 MACD 面积（红柱和）缩小
        """
        pens = result.pens
        if len(pens) < 2:
            return
        histogram = getattr(engine, 'histogram', pd.Series())
        if histogram.empty:
            return
        down_pens = [p for p in pens if hasattr(p, 'direction') and p.direction == 'down']
        up_pens = [p for p in pens if hasattr(p, 'direction') and p.direction == 'up']
        if len(down_pens) >= 2:
            p1, p2 = down_pens[-2], down_pens[-1]
            area1 = calculate_macd_area(histogram, p1.start_fractal.idx, p1.end_fractal.idx)
            area2 = calculate_macd_area(histogram, p2.start_fractal.idx, p2.end_fractal.idx)
            if p2.end_fractal.low < p1.end_fractal.low and abs(area2) < abs(area1):
                result.beichi_bottom = True
                result.last_bottom_low = p2.end_fractal.low
        if len(up_pens) >= 2:
            p1, p2 = up_pens[-2], up_pens[-1]
            area1 = calculate_macd_area(histogram, p1.start_fractal.idx, p1.end_fractal.idx)
            area2 = calculate_macd_area(histogram, p2.start_fractal.idx, p2.end_fractal.idx)
            if p2.end_fractal.high > p1.end_fractal.high and area2 < area1:
                result.beichi_top = True
                result.last_top_high = p2.end_fractal.high

    # ─── 中枢相关辅助方法 ───

    def _get_first_zhongshu(self, direction: str = "down") -> Optional[ZhongShu]:
        """获取第一个中枢"""
        zs_list = self._chan_4h.zhongshu_list
        for zs in zs_list:
            if hasattr(zs, 'direction') and zs.direction == direction:
                return zs
        return zs_list[0] if zs_list else None

    def _get_last_zhongshu(self, direction: str = "down") -> Optional[ZhongShu]:
        """获取最后一个中枢"""
        zs_list = self._chan_4h.zhongshu_list
        matching = [zs for zs in zs_list if hasattr(zs, 'direction') and zs.direction == direction]
        if matching:
            return matching[-1]
        return zs_list[-1] if zs_list else None

    def _price_in_zhongshu_range(self, price: float, zs: ZhongShu) -> bool:
        """判断价格是否在中枢范围内"""
        return zs.lower <= price <= zs.upper

    def _price_near_zhongshu(self, price: float, zs: ZhongShu, tolerance: float = 0.005) -> bool:
        """判断价格是否在中枢附近（一定容差范围内）"""
        margin = zs.zhongshu_range * 0.5 if zs.zhongshu_range > 0 else zs.upper * tolerance
        return (zs.lower - margin) <= price <= (zs.upper + margin)

    def _price_broke_zhongshu_up(self, price: float, zs: ZhongShu) -> bool:
        """判断价格是否向上突破中枢"""
        return price > zs.upper

    # ─── 信号生成：Type 2 Buy（二买）───

    def _detect_type_2_buy(self) -> Optional[Dict[str, Any]]:
        """
        检测二买信号

        条件:
        1. 4H 已有底背驰（一买确认）
        2. 价格回调到第一个4H中枢附近，不破一买低点
        3. 1H 确认：MACD 绿柱比前一波缩小 + 有底分型
        4. 15M 入场：突破下降趋势线或底分型收阳
        """
        if not self._chan_4h.beichi_bottom:
            return None
        self._first_buy_low = self._chan_4h.last_bottom_low
        current_price = float(self.df_4h.iloc[-1]["close"]) if not self.df_4h.empty else 0
        if current_price <= 0:
            return None
        first_zs = self._get_first_zhongshu("down")
        if first_zs is None:
            logger.debug(f"[{self.name}] 无4H中枢，无法判断二买")
            return None
        if not self._price_near_zhongshu(current_price, first_zs, tolerance=0.01):
            return None
        if self._first_buy_low > 0 and current_price <= self._first_buy_low:
            return None
        confirmed_1h = self._confirm_1h_long()
        entry_15m = self._confirm_15m_entry_long()
        if not (confirmed_1h and entry_15m):
            return None
        atr_val = self.get_current_atr("4h")
        sl_mult = self.config.indicators.atr.multiplier_stop_loss
        tp_mult = self.config.indicators.atr.multiplier_take_profit
        stop_loss = round(current_price - atr_val * sl_mult, 4)
        take_profit = round(current_price + atr_val * tp_mult, 4)
        size = self._calculate_position_size(current_price, stop_loss)
        logger.info(f"[{self.name}] 二买信号触发: price={current_price:.4f}, "
                    f"stop={stop_loss:.4f}, tp={take_profit:.4f}, size={size:.4f}")
        return {
            "action": "OPEN_LONG",
            "type": "type_2_buy",
            "price": current_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "size": size,
            "reason": f"二买: 回调至中枢[{first_zs.lower:.2f}-{first_zs.upper:.2f}], 1H确认+15M入场",
        }

    def _detect_type_2b_buy(self) -> Optional[Dict[str, Any]]:
        """
        检测类二买信号

        条件:
        1. 价格已向上突破4H中枢
        2. 回踩中枢上沿（支撑确认）
        3. 1H 确认：缩量 + MACD 柱不创新低
        4. 15M 入场：中枢区域小级别底分型
        """
        if self.df_4h.empty:
            return None
        current_price = float(self.df_4h.iloc[-1]["close"])
        last_zs = self._get_last_zhongshu("down")
        if last_zs is None:
            return None
        if not self._price_broke_zhongshu_up(current_price, last_zs):
            recent_lows = self.df_4h["low"].astype(float).iloc[-10:]
            if not any(low <= last_zs.upper * 1.01 for low in recent_lows):
                return None
        if not self._price_near_zhongshu(current_price, last_zs, tolerance=0.015):
            return None
        if not self._confirm_1h_volume_shrink():
            return None
        if not self._confirm_1h_macd_higher_low():
            return None
        if not self._confirm_15m_bottom_fractal():
            return None
        atr_val = self.get_current_atr("4h")
        sl_mult = self.config.indicators.atr.multiplier_stop_loss
        tp_mult = self.config.indicators.atr.multiplier_take_profit
        stop_loss = round(current_price - atr_val * sl_mult, 4)
        take_profit = round(current_price + atr_val * tp_mult, 4)
        size = self._calculate_position_size(current_price, stop_loss)
        logger.info(f"[{self.name}] 类二买信号触发: price={current_price:.4f}, stop={stop_loss:.4f}")
        return {
            "action": "OPEN_LONG",
            "type": "type_2b_buy",
            "price": current_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "size": size,
            "reason": f"类二买: 突破中枢[{last_zs.lower:.2f}-{last_zs.upper:.2f}]后回踩, 缩量+MACD确认",
        }

    def _detect_type_2_sell(self) -> Optional[Dict[str, Any]]:
        """
        检测二卖信号

        条件:
        1. 4H 已有顶背驰（一卖确认）
        2. 价格反弹到第一个4H中枢附近，不破一卖高点
        3. 1H 确认：MACD 红柱比前一波缩小 + 有顶分型
        4. 15M 入场：跌破上升趋势线或顶分型收阴
        """
        if not self._chan_4h.beichi_top:
            return None
        self._first_sell_high = self._chan_4h.last_top_high
        current_price = float(self.df_4h.iloc[-1]["close"]) if not self.df_4h.empty else 0
        if current_price <= 0:
            return None
        first_zs = self._get_first_zhongshu("down")
        if first_zs is None:
            return None
        if not self._price_near_zhongshu(current_price, first_zs, tolerance=0.01):
            return None
        if self._first_sell_high > 0 and current_price >= self._first_sell_high:
            return None
        confirmed_1h = self._confirm_1h_short()
        entry_15m = self._confirm_15m_entry_short()
        if not (confirmed_1h and entry_15m):
            return None
        atr_val = self.get_current_atr("4h")
        sl_mult = self.config.indicators.atr.multiplier_stop_loss
        tp_mult = self.config.indicators.atr.multiplier_take_profit
        stop_loss = round(current_price + atr_val * sl_mult, 4)
        take_profit = round(current_price - atr_val * tp_mult, 4)
        size = self._calculate_position_size(current_price, stop_loss)
        logger.info(f"[{self.name}] 二卖信号触发: price={current_price:.4f}, stop={stop_loss:.4f}")
        return {
            "action": "OPEN_SHORT",
            "type": "type_2_sell",
            "price": current_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "size": size,
            "reason": f"二卖: 反弹至中枢[{first_zs.lower:.2f}-{first_zs.upper:.2f}], 1H确认+15M入场",
        }

    # ─── 1H / 15M 确认方法 ───

    def _confirm_1h_long(self) -> bool:
        """1H 做多确认：MACD 绿柱缩小 + 底分型"""
        if not self._macd_1h or self._chan_1h.fractals is None:
            return False
        hist = self._macd_1h.get("histogram", pd.Series())
        if len(hist) < 10:
            return False
        recent_5 = hist.iloc[-5:]
        prev_5 = hist.iloc[-10:-5]
        green_shrinking = (recent_5.min() > prev_5.min() and recent_5.min() < 0)
        has_bottom = self._chan_1h.has_bottom_fractal
        return green_shrinking and has_bottom

    def _confirm_1h_short(self) -> bool:
        """1H 做空确认：MACD 红柱缩小 + 顶分型"""
        if not self._macd_1h or self._chan_1h.fractals is None:
            return False
        hist = self._macd_1h.get("histogram", pd.Series())
        if len(hist) < 10:
            return False
        recent_5 = hist.iloc[-5:]
        prev_5 = hist.iloc[-10:-5]
        red_shrinking = (recent_5.max() < prev_5.max() and recent_5.max() > 0)
        has_top = self._chan_1h.has_top_fractal
        return red_shrinking and has_top

    def _confirm_1h_volume_shrink(self) -> bool:
        """1H 缩量确认"""
        if self.df_1h.empty or "volume" not in self.df_1h.columns or len(self.df_1h) < 10:
            return True
        vol = self.df_1h["volume"].astype(float)
        current_vol = float(vol.iloc[-1])
        avg_vol = float(vol.iloc[-10:].mean())
        return current_vol < avg_vol

    def _confirm_1h_macd_higher_low(self) -> bool:
        """1H MACD 柱不创新低"""
        hist = self._macd_1h.get("histogram", pd.Series())
        if len(hist) < 10:
            return True
        recent_low = float(hist.iloc[-5:].min())
        prev_low = float(hist.iloc[-15:-5].min())
        return recent_low >= prev_low

    def _confirm_15m_entry_long(self) -> bool:
        """15M 做多入场：突破下降趋势线 或 底分型"""
        if self.df_15m.empty or len(self.df_15m) < 20:
            return True
        closes = self.df_15m["close"].astype(float)
        highs = self.df_15m["high"].astype(float)
        recent_highs = highs.iloc[-15:]
        trendline_val = float(recent_highs.iloc[0] + (recent_highs.iloc[-1] - recent_highs.iloc[0]) * 0.5)
        break_trend = float(closes.iloc[-1]) > trendline_val
        has_bottom = self._chan_15m.has_bottom_fractal
        return break_trend or has_bottom

    def _confirm_15m_entry_short(self) -> bool:
        """15M 做空入场：跌破上升趋势线 或 顶分型"""
        if self.df_15m.empty or len(self.df_15m) < 20:
            return True
        closes = self.df_15m["close"].astype(float)
        lows = self.df_15m["low"].astype(float)
        recent_lows = lows.iloc[-15:]
        trendline_val = float(recent_lows.iloc[0] + (recent_lows.iloc[-1] - recent_lows.iloc[0]) * 0.5)
        break_trend = float(closes.iloc[-1]) < trendline_val
        has_top = self._chan_15m.has_top_fractal
        return break_trend or has_top

    def _confirm_15m_bottom_fractal(self) -> bool:
        """15M 底分型确认"""
        return self._chan_15m.has_bottom_fractal

    # ─── 仓位计算 ───

    def _calculate_position_size(self, entry_price: float, stop_loss: float) -> float:
        """
        ATR 仓位计算

        Position_Size = (Account_Equity * Risk%) / (ATR_4h * 1.5)
        """
        risk_pct = self.config.position_management.sizing.risk_per_trade_percent / 100.0
        atr = self.get_current_atr("4h")
        sl_mult = self.config.indicators.atr.multiplier_stop_loss
        risk_amount = abs(entry_price - stop_loss)
        if risk_amount <= 0:
            risk_amount = atr * sl_mult if atr > 0 else entry_price * 0.02
        if risk_amount <= 0:
            return 0.0
        size = (self.current_capital * risk_pct) / risk_amount
        return round(size, 4)

    # ─── 执行指令引擎 ───

    def evaluate_directives(self) -> List[Dict[str, Any]]:
        """
        按优先级评估所有执行指令

        返回匹配的指令列表，按优先级排序
        """
        matched = []
        for directive in self.config.execution_directives:
            result = self._evaluate_directive(directive)
            if result:
                matched.append(result)
        matched.sort(key=lambda x: x.get("priority", 99))
        return matched

    def _evaluate_directive(self, directive: ExecutionDirective) -> Optional[Dict[str, Any]]:
        """评估单条指令"""
        cond = directive.condition
        action = directive.action
        params = directive.params
        ctx = {
            "Daily_Trend": self.daily_trend,
            "Funding_Rate": self.funding_rate,
            "Weekday": datetime.now().strftime("%a"),
            "Range_Mode": self._market_regime == MarketRegime.RANGE,
        }
        if "4h_Type_2B_Confirmed" in cond or "4h_Type_2S_Confirmed" in cond:
            return self._eval_rule_001_002(directive, ctx)
        if "Funding_Rate" in cond:
            return self._eval_rule_003(directive, ctx)
        if "Range_Mode" in cond and "Price_Breaks_4h_Pivot" in cond:
            return self._eval_rule_004(directive, ctx)
        if "Weekday" in cond:
            return self._eval_rule_005(directive, ctx)
        return None

    def _eval_rule_001_002(self, directive: ExecutionDirective, ctx: dict) -> Optional[Dict]:
        """RULE_001/002: 日线趋势 + 分型确认 → 开主仓位"""
        current_price = float(self.df_4h.iloc[-1]["close"]) if not self.df_4h.empty else 0
        if directive.action == "OPEN_LONG_MAIN_POSITION":
            if self.daily_trend == "UP" and self._chan_4h.has_bottom_fractal:
                atr = self.get_current_atr("4h")
                sl = round(current_price - atr * 1.5, 4)
                tp = round(current_price + atr * 3.0, 4)
                size = self._calculate_position_size(current_price, sl)
                if self._apply_global_filters("long", current_price):
                    return {"priority": directive.priority, "action": "OPEN_LONG",
                            "price": current_price, "stop_loss": sl, "take_profit": tp,
                            "size": size, "reason": f"{directive.directive_id}: 日线UP+4H底分型"}
        elif directive.action == "OPEN_SHORT_MAIN_POSITION":
            if self.daily_trend == "DOWN" and self._chan_4h.has_top_fractal:
                atr = self.get_current_atr("4h")
                sl = round(current_price + atr * 1.5, 4)
                tp = round(current_price - atr * 3.0, 4)
                size = self._calculate_position_size(current_price, sl)
                if self._apply_global_filters("short", current_price):
                    return {"priority": directive.priority, "action": "OPEN_SHORT",
                            "price": current_price, "stop_loss": sl, "take_profit": tp,
                            "size": size, "reason": f"{directive.directive_id}: 日线DOWN+4H顶分型"}
        return None

    def _eval_rule_003(self, directive: ExecutionDirective, ctx: dict) -> Optional[Dict]:
        """RULE_003: 资金费率熔断"""
        if self.funding_rate > self.config.global_filters.funding_rate_fuse.threshold:
            logger.warning(f"[{self.name}] 资金费率{self.funding_rate:.4f} > {self.config.global_filters.funding_rate_fuse.threshold}, 禁止做多")
            return {"priority": directive.priority, "action": "REJECT_ENTRY",
                    "reason": "Funding rate too high, risk of long squeeze.",
                    "blocked_direction": "long"}
        return None

    def _eval_rule_004(self, directive: ExecutionDirective, ctx: dict) -> Optional[Dict]:
        """RULE_004: 突破中枢 → 从震荡切换到趋势"""
        current_price = float(self.df_4h.iloc[-1]["close"]) if not self.df_4h.empty else 0
        last_zs = self._get_last_zhongshu()
        if last_zs and current_price > last_zs.upper and self._market_regime == MarketRegime.RANGE:
            self._market_regime = MarketRegime.TRENDING_UP
            return {"priority": directive.priority, "action": "CLOSE_SHORT_AND_OPEN_LONG",
                    "transition": "from_range_to_trend",
                    "reason": f"价格突破中枢上沿{last_zs.upper:.4f}, 震荡→多头趋势"}
        return None

    def _eval_rule_005(self, directive: ExecutionDirective, ctx: dict) -> Optional[Dict]:
        """RULE_005: 周末降杠杆"""
        weekday = datetime.now().strftime("%a")
        weekend_days = self.config.global_filters.weekend_mode.days
        if self.config.global_filters.weekend_mode.enabled and weekday in weekend_days:
            max_lev = directive.params.get("max_leverage", 5)
            size_mult = directive.params.get("size_multiplier", 0.5)
            return {"priority": directive.priority, "action": "ADJUST_LEVERAGE_AND_SIZE",
                    "max_leverage": max_lev, "size_multiplier": size_mult,
                    "reason": f"周末模式: 杠杆≤{max_lev}x, 仓位×{size_mult}"}
        return None

    # ─── 全局过滤器 ───

    def _apply_global_filters(self, direction: str, price: float) -> bool:
        """应用全局过滤器"""
        if self._check_weekend_mode():
            logger.info(f"[{self.name}] 周末模式，不做突破交易")
            return False
        if self._check_funding_rate_fuse(direction):
            return False
        return True

    def _check_weekend_mode(self) -> bool:
        """检查是否处于周末模式"""
        cfg = self.config.global_filters.weekend_mode
        if not cfg.enabled:
            return False
        weekday = datetime.now().strftime("%a")
        return weekday in cfg.days

    def _check_funding_rate_fuse(self, direction: str) -> bool:
        """检查资金费率熔断"""
        fuse = self.config.global_filters.funding_rate_fuse
        if direction == "long" and self.funding_rate > fuse.threshold:
            logger.warning(f"[{self.name}] 资金费率{self.funding_rate:.4f}>{fuse.threshold}, 禁止做多")
            return True
        return False

    # ─── 主信号生成 ───

    def generate_signal(self, bar_idx: int = None) -> Optional[Dict[str, Any]]:
        """生成交易信号（主入口）"""
        if self.df_4h.empty:
            return None
        if bar_idx is not None and bar_idx == self._last_signal_bar_idx:
            return None
        self._last_signal_bar_idx = bar_idx if bar_idx is not None else self._last_signal_bar_idx
        self._refresh_daily_if_needed()
        return self._generate_signal_v2()

    def _generate_signal_v2(self) -> Optional[Dict[str, Any]]:
        """信号生成核心逻辑"""
        directives = self.evaluate_directives()
        for d in directives:
            if d.get("action") in ("OPEN_LONG", "OPEN_SHORT", "CLOSE_SHORT_AND_OPEN_LONG"):
                logger.info(f"[{self.name}] 执行指令触发: {d}")
                return d
        for d in directives:
            if d.get("action") == "REJECT_ENTRY":
                logger.info(f"[{self.name}] 指令拒绝入场: {d}")
                return None
            if d.get("action") == "ADJUST_LEVERAGE_AND_SIZE":
                logger.info(f"[{self.name}] 周末调整: {d}")
        if not self.hedging.has_long and not self.hedging.has_short:
            type_2b = self._detect_type_2b_buy()
            if type_2b:
                return type_2b
            type_2_buy = self._detect_type_2_buy()
            if type_2_buy:
                return type_2_buy
            type_2_sell = self._detect_type_2_sell()
            if type_2_sell:
                return type_2_sell
        if self.hedging.has_long:
            exit_sig = self._check_long_exit()
            if exit_sig:
                return exit_sig
            hedge_sig = self._check_hedge_trigger("short")
            if hedge_sig:
                return hedge_sig
        if self.hedging.has_short:
            exit_sig = self._check_short_exit()
            if exit_sig:
                return exit_sig
            hedge_sig = self._check_hedge_trigger("long")
            if hedge_sig:
                return hedge_sig
        return None

    def _refresh_daily_if_needed(self) -> None:
        """每日 0:00 UTC+8 刷新日线趋势"""
        today = datetime.now().date()
        if self._last_daily_refresh_date != today:
            self._last_daily_refresh_date = today
            self._update_daily_trend()
            logger.info(f"[{self.name}] 日线趋势刷新: {self.daily_trend}")

    # ─── 出场信号检查 ───

    def _check_long_exit(self) -> Optional[Dict]:
        """检查做多出场"""
        if self.hedging.long_stop_loss > 0:
            current_price = float(self.df_4h.iloc[-1]["close"]) if not self.df_4h.empty else 0
            if current_price <= self.hedging.long_stop_loss:
                return {"action": "CLOSE_LONG", "price": current_price,
                        "reason": f"止损触发 (SL={self.hedging.long_stop_loss:.4f})"}
            if current_price >= self.hedging.long_take_profit:
                return {"action": "CLOSE_LONG", "price": current_price,
                        "reason": f"止盈触发 (TP={self.hedging.long_take_profit:.4f})"}
        if self._chan_4h.has_top_fractal and self._chan_4h.beichi_top:
            current_price = float(self.df_4h.iloc[-1]["close"]) if not self.df_4h.empty else 0
            return {"action": "CLOSE_LONG", "price": current_price,
                    "reason": "4H顶背驰，做多出场"}
        return None

    def _check_short_exit(self) -> Optional[Dict]:
        """检查做空出场"""
        if self.hedging.short_stop_loss > 0:
            current_price = float(self.df_4h.iloc[-1]["close"]) if not self.df_4h.empty else 0
            if current_price >= self.hedging.short_stop_loss:
                return {"action": "CLOSE_SHORT", "price": current_price,
                        "reason": f"止损触发 (SL={self.hedging.short_stop_loss:.4f})"}
            if current_price <= self.hedging.short_take_profit:
                return {"action": "CLOSE_SHORT", "price": current_price,
                        "reason": f"止盈触发 (TP={self.hedging.short_take_profit:.4f})"}
        if self._chan_4h.has_bottom_fractal and self._chan_4h.beichi_bottom:
            current_price = float(self.df_4h.iloc[-1]["close"]) if not self.df_4h.empty else 0
            return {"action": "CLOSE_SHORT", "price": current_price,
                    "reason": "4H底背驰，做空出场"}
        return None

    # ─── 对冲逻辑 ───

    def _check_hedge_trigger(self, hedge_direction: str) -> Optional[Dict]:
        """
        检查是否触发对冲开仓

        趋势模式：主仓位100%，对冲仓位0-30%（1H与4H背离时触发）
        震荡模式：上沿做空50%，下沿做多50%
        """
        if hedge_direction == "short":
            if self.hedging.short_qty > 0:
                return None
            if self._market_regime == MarketRegime.TRENDING_UP:
                if self._chan_1h.beichi_top and not self._chan_4h.beichi_top:
                    current_price = float(self.df_4h.iloc[-1]["close"]) if not self.df_4h.empty else 0
                    atr = self.get_current_atr("4h")
                    hedge_size = self.hedging.long_qty * self.config.position_management.hedging_rules.trend_hedge_pct
                    return {"action": "OPEN_SHORT_HEDGE", "price": current_price,
                            "size": round(hedge_size, 4),
                            "stop_loss": round(current_price + atr * 1.5, 4),
                            "reason": "趋势模式对冲: 1H顶背驰 vs 4H多头趋势"}
            elif self._market_regime == MarketRegime.RANGE:
                last_zs = self._get_last_zhongshu()
                if last_zs:
                    current_price = float(self.df_4h.iloc[-1]["close"]) if not self.df_4h.empty else 0
                    if current_price >= last_zs.upper * (1 - 0.005):
                        hedge_pct = self.config.position_management.hedging_rules.range_short_pct
                        size = self._calculate_position_size(current_price,
                                                             current_price + self.get_current_atr("4h") * 1.5)
                        return {"action": "OPEN_SHORT_HEDGE", "price": current_price,
                                "size": round(size * hedge_pct, 4),
                                "stop_loss": round(current_price + self.get_current_atr("4h") * 1.5, 4),
                                "reason": f"震荡模式: 中枢上沿{last_zs.upper:.4f}做空"}
        elif hedge_direction == "long":
            if self.hedging.long_qty > 0:
                return None
            if self._market_regime == MarketRegime.TRENDING_DOWN:
                if self._chan_1h.beichi_bottom and not self._chan_4h.beichi_bottom:
                    current_price = float(self.df_4h.iloc[-1]["close"]) if not self.df_4h.empty else 0
                    atr = self.get_current_atr("4h")
                    hedge_size = self.hedging.short_qty * self.config.position_management.hedging_rules.trend_hedge_pct
                    return {"action": "OPEN_LONG_HEDGE", "price": current_price,
                            "size": round(hedge_size, 4),
                            "stop_loss": round(current_price - atr * 1.5, 4),
                            "reason": "趋势模式对冲: 1H底背驰 vs 4H空头趋势"}
            elif self._market_regime == MarketRegime.RANGE:
                last_zs = self._get_last_zhongshu()
                if last_zs:
                    current_price = float(self.df_4h.iloc[-1]["close"]) if not self.df_4h.empty else 0
                    if current_price <= last_zs.lower * (1 + 0.005):
                        hedge_pct = self.config.position_management.hedging_rules.range_long_pct
                        size = self._calculate_position_size(current_price,
                                                             current_price - self.get_current_atr("4h") * 1.5)
                        return {"action": "OPEN_LONG_HEDGE", "price": current_price,
                                "size": round(size * hedge_pct, 4),
                                "stop_loss": round(current_price - self.get_current_atr("4h") * 1.5, 4),
                                "reason": f"震荡模式: 中枢下沿{last_zs.lower:.4f}做多"}
        return None

    # ─── 仓位更新 ───

    def apply_signal(self, signal: Dict[str, Any]) -> None:
        """应用交易信号，更新内部持仓状态"""
        action = signal.get("action", "")
        price = signal.get("price", 0)
        size = signal.get("size", 0)
        if action == "OPEN_LONG":
            self.hedging.long_qty += size
            self.hedging.long_entry_price = price
            self.hedging.long_stop_loss = signal.get("stop_loss", 0)
            self.hedging.long_take_profit = signal.get("take_profit", 0)
            self._market_regime = MarketRegime.TRENDING_UP
            self.trades.append(TradeRecordV2(
                timestamp=pd.Timestamp.now(), action="OPEN_LONG",
                price=price, quantity=size, reason=signal.get("reason", "")))
        elif action == "OPEN_SHORT":
            self.hedging.short_qty += size
            self.hedging.short_entry_price = price
            self.hedging.short_stop_loss = signal.get("stop_loss", 0)
            self.hedging.short_take_profit = signal.get("take_profit", 0)
            self._market_regime = MarketRegime.TRENDING_DOWN
            self.trades.append(TradeRecordV2(
                timestamp=pd.Timestamp.now(), action="OPEN_SHORT",
                price=price, quantity=size, reason=signal.get("reason", "")))
        elif action == "CLOSE_LONG":
            if self.hedging.long_qty > 0:
                pnl = (price - self.hedging.long_entry_price) * self.hedging.long_qty
                self.trades[-1].pnl = pnl if self.trades else 0
            self.hedging.long_qty = 0
            self.hedging.long_entry_price = 0
            self.hedging.long_stop_loss = 0
            self.hedging.long_take_profit = 0
        elif action == "CLOSE_SHORT":
            if self.hedging.short_qty > 0:
                pnl = (self.hedging.short_entry_price - price) * self.hedging.short_qty
                self.trades[-1].pnl = pnl if self.trades else 0
            self.hedging.short_qty = 0
            self.hedging.short_entry_price = 0
            self.hedging.short_stop_loss = 0
            self.hedging.short_take_profit = 0
        elif action == "CLOSE_SHORT_AND_OPEN_LONG":
            if self.hedging.short_qty > 0:
                pnl = (self.hedging.short_entry_price - price) * self.hedging.short_qty
                self.hedging.short_qty = 0
            atr = self.get_current_atr("4h")
            self.hedging.long_qty += self._calculate_position_size(price, price - atr * 1.5)
            self.hedging.long_entry_price = price
            self.hedging.long_stop_loss = round(price - atr * 1.5, 4)
            self.hedging.long_take_profit = round(price + atr * 3.0, 4)
            self._market_regime = MarketRegime.TRENDING_UP
        elif action == "OPEN_SHORT_HEDGE":
            self.hedging.short_qty += size
            self.hedging.short_entry_price = price
            self.hedging.short_stop_loss = signal.get("stop_loss", 0)
        elif action == "OPEN_LONG_HEDGE":
            self.hedging.long_qty += size
            self.hedging.long_entry_price = price
            self.hedging.long_stop_loss = signal.get("stop_loss", 0)
        elif action == "ADJUST_LEVERAGE_AND_SIZE":
            size_mult = signal.get("size_multiplier", 0.5)
            self.hedging.long_qty *= size_mult
            self.hedging.short_qty *= size_mult

    def clear_position(self) -> None:
        """清空持仓"""
        self.hedging = HedgingState()

    def get_status(self) -> Dict[str, Any]:
        """获取策略状态"""
        return {
            "name": self.name,
            "symbol": self.symbol,
            "daily_trend": self.daily_trend,
            "market_regime": self._market_regime.value,
            "long_qty": self.hedging.long_qty,
            "short_qty": self.hedging.short_qty,
            "net_exposure": self.hedging.net_exposure,
            "atr_4h": round(self._atr_value, 4),
            "funding_rate": self.funding_rate,
            "beichi_bottom_4h": self._chan_4h.beichi_bottom,
            "beichi_top_4h": self._chan_4h.beichi_top,
            "zhongshu_count_4h": len(self._chan_4h.zhongshu_list),
        }

    async def initialize(self, symbol: str) -> bool:
        self.symbol = symbol
        return True

    async def on_bar(self, bar_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self.generate_signal()

    async def on_order_update(self, order_data: Dict[str, Any]) -> None:
        pass


# ==============================================================================
# 回测引擎与报告
# ==============================================================================

@dataclass
class BacktestReportV2:
    """回测报告数据结构"""
    strategy_name: str = ""
    symbol: str = ""
    initial_capital: float = 10000.0
    final_capital: float = 10000.0
    total_return: float = 0.0
    annual_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    equity_curve: List[float] = field(default_factory=list)
    trade_history: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "initial_capital": self.initial_capital,
            "final_capital": round(self.final_capital, 2),
            "total_return_pct": round(self.total_return * 100, 2),
            "annual_return_pct": round(self.annual_return * 100, 2),
            "max_drawdown_pct": round(self.max_drawdown * 100, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "win_rate_pct": round(self.win_rate * 100, 2),
            "profit_factor": round(self.profit_factor, 2),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_win": round(self.avg_win, 4),
            "avg_loss": round(self.avg_loss, 4),
        }

    def print_report(self) -> None:
        """打印回测报告"""
        print("\n" + "=" * 70)
        print(f"  回测报告: {self.strategy_name}")
        print(f"  交易对: {self.symbol}")
        print("=" * 70)
        print(f"  初始资金:       ${self.initial_capital:>12,.2f}")
        print(f"  最终资金:       ${self.final_capital:>12,.2f}")
        print(f"  总收益率:       {self.total_return*100:>11.2f}%")
        print(f"  年化收益率:     {self.annual_return*100:>11.2f}%")
        print(f"  最大回撤:       {self.max_drawdown*100:>11.2f}%")
        print(f"  夏普比率:       {self.sharpe_ratio:>12.4f}")
        print(f"  胜率:           {self.win_rate*100:>11.2f}%")
        print(f"  盈亏比:         {self.profit_factor:>12.2f}")
        print(f"  总交易笔数:     {self.total_trades:>12}")
        print(f"  盈利笔数:       {self.winning_trades:>12}")
        print(f"  亏损笔数:       {self.losing_trades:>12}")
        print(f"  平均盈利:       ${self.avg_win:>11.4f}")
        print(f"  平均亏损:       ${self.avg_loss:>11.4f}")
        print("=" * 70)


def generate_backtest_report(strategy: CryptoChan4HMasterStrategy,
                             initial_capital: float = 10000.0) -> BacktestReportV2:
    """
    根据交易记录和权益曲线生成回测报告

    Args:
        strategy: 策略实例（含交易记录）
        initial_capital: 初始资金

    Returns:
        BacktestReportV2: 回测报告对象
    """
    report = BacktestReportV2(
        strategy_name=strategy.name,
        symbol=strategy.symbol,
        initial_capital=initial_capital,
        final_capital=strategy.current_capital,
        trade_history=[],
    )
    trades = strategy.trades
    report.total_trades = len(trades)
    if report.total_trades == 0:
        return report
    closed_trades = [t for t in trades if t.pnl != 0]
    report.total_trades = len(closed_trades)
    if report.total_trades == 0:
        return report
    pnl_values = [t.pnl for t in closed_trades]
    report.winning_trades = sum(1 for p in pnl_values if p > 0)
    report.losing_trades = sum(1 for p in pnl_values if p <= 0)
    if report.total_trades > 0:
        report.win_rate = report.winning_trades / report.total_trades
    wins = [p for p in pnl_values if p > 0]
    losses = [abs(p) for p in pnl_values if p <= 0]
    report.avg_win = float(np.mean(wins)) if wins else 0.0
    report.avg_loss = float(np.mean(losses)) if losses else 0.0
    total_profit = sum(wins)
    total_loss = sum(losses)
    if total_loss > 0:
        report.profit_factor = total_profit / total_loss
    report.final_capital = initial_capital + sum(pnl_values)
    if initial_capital > 0:
        report.total_return = (report.final_capital - initial_capital) / initial_capital
    equity = [initial_capital]
    for t in closed_trades:
        equity.append(equity[-1] + t.pnl)
    report.equity_curve = equity
    if len(equity) >= 2:
        peak = equity[0]
        max_dd = 0.0
        for val in equity[1:]:
            if val > peak:
                peak = val
            dd = (peak - val) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        report.max_drawdown = max_dd
        returns = []
        for i in range(1, len(equity)):
            if equity[i - 1] > 0:
                returns.append((equity[i] - equity[i - 1]) / equity[i - 1])
        if returns:
            mean_ret = np.mean(returns)
            std_ret = np.std(returns)
            if std_ret > 0:
                report.sharpe_ratio = (mean_ret / std_ret) * np.sqrt(252)
            years = len(closed_trades) / 365.0 if len(closed_trades) > 0 else 1.0
            if years > 0 and initial_capital > 0:
                report.annual_return = ((report.final_capital / initial_capital) ** (1.0 / max(years, 0.1))) - 1.0
    for t in closed_trades:
        report.trade_history.append({
            "timestamp": str(t.timestamp),
            "action": t.action,
            "price": t.price,
            "quantity": t.quantity,
            "pnl": round(t.pnl, 4),
            "reason": t.reason,
        })
    return report


class CryptoChan4HBacktestEngine:
    """
    Crypto_Chan_4H_Master_v1 回测引擎

    逐根 4H K 线推进，调用策略信号生成和执行
    """

    def __init__(self, config: StrategyConfigRoot, initial_capital: float = 10000.0,
                 commission: float = 0.0004):
        self.config = config
        self.initial_capital = initial_capital
        self.commission = commission
        self.strategy = CryptoChan4HMasterStrategy(config)
        self.strategy.current_capital = initial_capital
        self.strategy.initial_capital = initial_capital

    def run(self, df_4h: pd.DataFrame, df_1h: pd.DataFrame = None,
            df_15m: pd.DataFrame = None, df_daily: pd.DataFrame = None,
            progress: bool = True) -> BacktestReportV2:
        """
        运行回测

        Args:
            df_4h: 4H K线数据
            df_1h: 1H K线数据
            df_15m: 15M K线数据
            df_daily: 日线数据
            progress: 是否显示进度条

        Returns:
            BacktestReportV2: 回测报告
        """
        logger.info(f"[Backtest] 开始回测: {len(df_4h)} 根4H K线, 初始资金=${self.initial_capital:,.2f}")
        iterator = range(len(df_4h))
        if progress:
            try:
                from tqdm import tqdm
                iterator = tqdm(iterator, desc="回测中")
            except ImportError:
                pass
        for i in iterator:
            df_4h_slice = df_4h.iloc[:i + 1].copy()
            df_1h_slice = None
            df_15m_slice = None
            if df_1h is not None and not df_1h.empty:
                last_4h_time = df_4h.iloc[i].get("open_time", None)
                if last_4h_time is not None:
                    mask = df_1h["open_time"] <= last_4h_time
                    df_1h_slice = df_1h[mask].copy()
            if df_15m is not None and not df_15m.empty:
                last_4h_time = df_4h.iloc[i].get("open_time", None)
                if last_4h_time is not None:
                    mask = df_15m["open_time"] <= last_4h_time
                    df_15m_slice = df_15m[mask].copy()
            df_daily_slice = df_daily.copy() if df_daily is not None else None
            self.strategy.inject_data(df_4h_slice, df_1h_slice, df_15m_slice, df_daily_slice)
            signal = self.strategy.generate_signal(bar_idx=i)
            if signal:
                price = signal.get("price", 0)
                size = signal.get("size", 0)
                action = signal.get("action", "")
                if "OPEN" in action:
                    cost = price * size * self.commission
                    self.strategy.current_capital -= cost
                elif "CLOSE" in action:
                    cost = price * size * self.commission
                    self.strategy.current_capital -= cost
                self.strategy.apply_signal(signal)
        report = generate_backtest_report(self.strategy, self.initial_capital)
        logger.info(f"[Backtest] 回测完成: 总交易={report.total_trades}, "
                    f"收益率={report.total_return*100:.2f}%, "
                    f"最大回撤={report.max_drawdown*100:.2f}%")
        return report


def run_crypto_chan_backtest(
    symbol: str = "ETH/USDC",
    initial_capital: float = 10000.0,
    start_date: str = None,
    end_date: str = None,
    data_dir: str = None,
) -> BacktestReportV2:
    """
    便捷函数：运行 Crypto Chan 策略回测

    数据源优先级：
    1. 本地 CSV 文件 (data_dir)
    2. CCXT (如果已安装)

    Args:
        symbol: 交易对
        initial_capital: 初始资金
        start_date: 开始日期（YYYY-MM-DD）
        end_date: 结束日期（YYYY-MM-DD）
        data_dir: 本地数据目录

    Returns:
        BacktestReportV2
    """
    json_config = json.dumps({
        "strategy_metadata": {
            "name": "Crypto_Chan_4H_Master_v1",
            "version": "1.0",
            "description": "基于缠论4H/1H/15M级别的交易系统",
            "base_currency": "USDC",
            "trading_pairs": [symbol],
            "timeframe_config": {"trend_level": "4h", "structure_level": "1h", "entry_level": "15m"}
        },
        "global_filters": {
            "daily_cutoff": "0:00",
            "weekend_mode": {"enabled": True, "days": ["Sat", "Sun"],
                            "action": "reduce_position_to_50_percent_and_no_breakout_trades"},
            "funding_rate_fuse": {"threshold": 0.001,
                                 "condition_gt": "disable_long_entry_on_3rd_buy",
                                 "condition_lt": "disable_short_entry_on_3rd_sell"}
        },
        "indicators": {
            "atr": {"period": 14, "source": "4h", "multiplier_stop_loss": 1.5, "multiplier_take_profit": 3.0},
            "macd": {"fast": 12, "slow": 26, "signal": 9}
        },
        "trade_logic": {
            "long_setup": {
                "type_2_buy": {"level": "4h",
                               "condition": "Price retraces to the first 4h central pivot after 1st buy",
                               "confirmation_1h": "MACD green bars shrink",
                               "entry_15m": "Break of 15m downtrend line or 15m bottom fractal close",
                               "stop_loss": "Entry_price - (ATR_4h * 1.5)"},
                "type_2b_like_buy": {"level": "4h",
                                     "condition": "Price breaks above 4h central pivot and retests",
                                     "confirmation_1h": "Volume decreases on pullback",
                                     "entry_15m": "15m small reversal at the pivot zone",
                                     "stop_loss": "Entry_price - (ATR_4h * 1.5)"}
            },
            "short_setup": {
                "type_2_sell": {"level": "4h",
                                "condition": "Price rallies to the first 4h central pivot after 1st sell",
                                "confirmation_1h": "MACD red bars shrink",
                                "entry_15m": "Break of 15m uptrend line or 15m top fractal close",
                                "stop_loss": "Entry_price + (ATR_4h * 1.5)"}
            }
        },
        "position_management": {
            "hedging_rules": {
                "trend_mode": {"main_position": "100%", "hedge_position": "0-30%",
                               "trigger": "1h divergence against 4h trend"},
                "range_mode": {"upper_bound_short": "50%", "lower_bound_long": "50%",
                               "net_exposure": "0%",
                               "exit_rule": "Close opposite side if price breaks 4h central pivot."}
            },
            "sizing": {"method": "atr_based", "risk_per_trade_percent": 1.0,
                       "calculation": "Position_Size = (Account_Equity * Risk%) / (ATR_4h * 1.5)"}
        },
        "execution_directives": [
            {"id": "RULE_001", "priority": 1,
             "condition": "Daily_Trend == UP AND 4h_Type_2B_Confirmed",
             "action": "OPEN_LONG_MAIN_POSITION", "params": {"size": "full", "sl": "atr_1.5"}},
            {"id": "RULE_002", "priority": 1,
             "condition": "Daily_Trend == DOWN AND 4h_Type_2S_Confirmed",
             "action": "OPEN_SHORT_MAIN_POSITION", "params": {"size": "full", "sl": "atr_1.5"}},
            {"id": "RULE_003", "priority": 2,
             "condition": "Funding_Rate > 0.001 AND Action == OPEN_LONG",
             "action": "REJECT_ENTRY",
             "params": {"reason": "Funding rate too high, risk of long squeeze."}},
            {"id": "RULE_004", "priority": 3,
             "condition": "Price_Breaks_4h_Pivot_Upwards AND Range_Mode == TRUE",
             "action": "CLOSE_SHORT_AND_OPEN_LONG",
             "params": {"transition": "from_range_to_trend"}},
            {"id": "RULE_005", "priority": 4,
             "condition": "Weekday IN ['Sat', 'Sun']",
             "action": "ADJUST_LEVERAGE_AND_SIZE",
             "params": {"max_leverage": 5, "size_multiplier": 0.5}}
        ]
    })
    config = StrategyConfigRoot.from_json(json_config)
    if data_dir:
        data_path = Path(data_dir)
        symbol_file = symbol.replace("/", "").replace("USDC", "USDC")
        csv_files = {
            "4h": data_path / f"{symbol_file}_4h.csv",
            "1h": data_path / f"{symbol_file}_1h.csv",
            "15m": data_path / f"{symbol_file}_15m.csv",
            "1d": data_path / f"{symbol_file}_1d.csv",
        }
        dfs = {}
        for tf, fp in csv_files.items():
            if fp.exists():
                dfs[tf] = pd.read_csv(fp)
                if "open_time" in dfs[tf].columns:
                    dfs[tf]["open_time"] = pd.to_datetime(dfs[tf]["open_time"])
                logger.info(f"[Backtest] 加载 {tf}: {len(dfs[tf])} 行 from {fp}")
        if start_date and end_date:
            for tf in dfs:
                if "open_time" in dfs[tf].columns:
                    mask = (dfs[tf]["open_time"] >= pd.Timestamp(start_date)) & \
                           (dfs[tf]["open_time"] <= pd.Timestamp(end_date))
                    dfs[tf] = dfs[tf][mask]
        engine = CryptoChan4HBacktestEngine(config, initial_capital)
        return engine.run(
            df_4h=dfs.get("4h", pd.DataFrame()),
            df_1h=dfs.get("1h", pd.DataFrame()),
            df_15m=dfs.get("15m", pd.DataFrame()),
            df_daily=dfs.get("1d", pd.DataFrame()),
        )
    try:
        provider = CCXTDataProvider("binance")
        dfs = provider.fetch_multiple_timeframes(symbol, ["4h", "1h", "15m", "1d"], limit=500)
        engine = CryptoChan4HBacktestEngine(config, initial_capital)
        return engine.run(
            df_4h=dfs.get("4h", pd.DataFrame()),
            df_1h=dfs.get("1h", pd.DataFrame()),
            df_15m=dfs.get("15m", pd.DataFrame()),
            df_daily=dfs.get("1d", pd.DataFrame()),
        )
    except ImportError:
        logger.warning("[Backtest] CCXT 未安装且未指定 data_dir，无法获取数据")
        raise RuntimeError("需要安装 ccxt (pip install ccxt) 或通过 data_dir 指定本地CSV数据路径")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    print("Crypto_Chan_4H_Master_v1 Strategy Module")
    print("=" * 60)
    print("用法:")
    print("  from trading_system.strategies.mtf_fractal_strategy import run_crypto_chan_backtest")
    print("  report = run_crypto_chan_backtest('ETH/USDC', data_dir='trading_system/data/binance_history')")
    print("  report.print_report()")