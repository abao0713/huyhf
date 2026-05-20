"""
缠论策略V2 - 分型驱动交易系统

核心改进：
- 使用分型识别替代背驰判断作为主要触发条件
- 支持动态加仓（最多3次）
- 支持即时反转（顶底分型切换时立即平仓反向开仓）
- 完全配置化的参数系统
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .base_strategy import BaseStrategy
from .chan_strategy import ChanStrategy, Fractal, Pen
from ..binance.client import BinanceRestClient
from ..utils.indicators import binance_klines_to_dataframe

logger = logging.getLogger(__name__)


@dataclass
class PositionState:
    """持仓状态数据类"""
    direction: Optional[str] = None  # "long" / "short" / None
    entry_count: int = 0             # 当前加仓次数（0=首仓, 1/2/3=加仓）
    total_position_size: float = 0.0 # 总持仓数量
    avg_entry_price: float = 0.0     # 平均入场价
    initial_stop_loss: float = 0.0   # 初始止损价


class ChanStrategyV2(BaseStrategy):
    """
    缠论策略V2 - 分型驱动交易系统
    
    核心特性：
    1. 分型触发：识别到顶/底分型立即交易（无需等待背驰）
    2. 动态加仓：同向分型可加仓最多3次
    3. 即时反转：反向分型出现时立即平仓+反向开仓
    4. 配置化：所有参数均可通过构造函数配置
    
    入参说明：
    - symbol: 交易对名称，如"ETHUSDC"
    - time_frame: K线时间周期，如"30m"
    - hg1: 分型查找参数，默认8
    - max_add_positions: 最大加仓次数，默认3
    - investment_ratio: 每次投入比例，默认10%
    - leverage: 杠杆倍数，默认20
    - long_stop_loss_ratio: 多单固定止损比例，默认5%
    - short_stop_loss_ratio: 空单固定止损比例，默认5%
    - use_atr_stop: 是否使用ATR动态止损，默认True
    - atr_multiplier: ATR止损倍数，默认3.5
    """

    def __init__(
        self,
        symbol: str = "ETHUSDC",
        time_frame: str = "30m",
        hg1: int = 8,
        
        # ===== 交易配置 =====
        max_add_positions: int = 3,
        investment_ratio: float = 0.10,
        leverage: int = 20,
        
        # ===== 止损配置 =====
        long_stop_loss_ratio: float = 0.05,
        short_stop_loss_ratio: float = 0.05,
        use_atr_stop: bool = True,
        atr_multiplier: float = 3.5,
        
        # ===== 追踪止损配置 =====
        use_trailing_stop: bool = True,
        trailing_activation: float = 0.025,
        trailing_distance: float = 0.020,
        
        # ===== 数据源配置 =====
        use_binance_client: bool = False,
    ):
        """
        初始化策略V2
        
        Args:
            symbol: 交易对符号
            time_frame: K线周期
            hg1: 分型窗口大小
            max_add_positions: 最大加仓次数
            investment_ratio: 投入比例 (0-1)
            leverage: 杠杆倍数
            long_stop_loss_ratio: 多单固定止损比例
            short_stop_loss_ratio: 空单固定止损比例
            use_atr_stop: 是否使用ATR动态止损
            atr_multiplier: ATR倍数
            use_trailing_stop: 是否使用追踪止损
            trailing_activation: 追踪止损激活阈值
            trailing_distance: 追踪止损距离
            use_binance_client: 是否使用Binance客户端
        """
        super().__init__("ChanStrategyV2")
        
        self.symbol = symbol
        self.time_frame = time_frame
        self.hg1 = hg1
        
        # 交易配置
        self.max_add_positions = max_add_positions
        self.investment_ratio = investment_ratio
        self.leverage = leverage
        
        # 止损配置
        self.long_stop_loss_ratio = long_stop_loss_ratio
        self.short_stop_loss_ratio = short_stop_loss_ratio
        self.use_atr_stop = use_atr_stop
        self.atr_multiplier = atr_multiplier
        
        # 追踪止损配置
        self.use_trailing_stop = use_trailing_stop
        self.trailing_activation = trailing_activation
        self.trailing_distance = trailing_distance
        
        # 数据源配置
        self.use_binance_client = use_binance_client
        
        # 数据存储（复用自ChanStrategy）
        self.df_30m: pd.DataFrame = pd.DataFrame()
        self.df_5m: pd.DataFrame = pd.DataFrame()
        self.df_daily: pd.DataFrame = pd.DataFrame()
        self.df_processed: pd.DataFrame = pd.DataFrame()
        
        # 缠论元素存储
        self.fractals: List[Fractal] = []
        self.pens: List[Pen] = []
        self.segments: List[Any] = []
        
        # ATR相关
        self.current_atr: float = 0.0
        
        # 持仓状态跟踪
        self.position_state = PositionState()
        
        # 分型历史记录（用于检测新分型）
        self.last_fractal_type: Optional[str] = None
        self.last_fractal_idx: int = -1
        
        # 已处理分型追踪（用时间戳防重复）
        self._last_processed_fractal_ts: Optional[pd.Timestamp] = None
        
        # 内部策略实例（用于数据处理）
        self._internal_strategy: Optional[ChanStrategy] = None

    async def initialize(self, symbol: str) -> bool:
        """
        初始化策略
        
        Args:
            symbol: 交易对符号
            
        Returns:
            初始化是否成功
        """
        self.symbol = symbol
        
        try:
            logger.info(f"[ChanStrategyV2] 初始化策略: symbol={symbol}, time_frame={self.time_frame}")
            
            # 创建内部策略实例（仅用于数据处理逻辑）
            self._internal_strategy = ChanStrategy(
                symbol=symbol,
                time_frame=self.time_frame,
                hg1=self.hg1,
                use_binance_client=False
            )
            
            # 注意：不调用 _internal_strategy.initialize()
            # 因为它会尝试从网络下载数据
            # 数据将由回测引擎通过 load_data_for_backtest() 注入
            
            # 初始化分型跟踪状态
            self._current_fractal_idx = 0
            
            # 标记为未初始化（等待数据注入）
            self._data_injected = False
            
            logger.info(f"[ChanStrategyV2] 初始化成功（等待数据注入模式）")
            return True
            
        except Exception as e:
            logger.error(f"[ChanStrategyV2] 初始化失败: {e}", exc_info=True)
            return False

    def load_data_for_backtest(self, df_30m: pd.DataFrame, df_daily: pd.DataFrame):
        """
        注入回测数据（由回测引擎调用）
        
        Args:
            df_30m: 30分钟K线数据
            df_daily: 日线K线数据
        """
        try:
            logger.info(f"[ChanStrategyV2] 注入回测数据: 30m={len(df_30m)}条, 1d={len(df_daily)}条")
            
            # 设置内部策略的数据
            self._internal_strategy.df_30m = df_30m
            self._internal_strategy.df_daily = df_daily
            self._internal_strategy.symbol = self.symbol
            
            # 禁用包含关系合并，确保分型索引与原始K线索引一致
            self._internal_strategy.use_inclusion_merge = False
            
            # 调用数据处理
            self._internal_strategy._process_data()
            
            # 同步处理后的数据到V2策略
            self._sync_internal_data()
            
            # 计算ATR
            self._calculate_atr()
            
            # 标记数据已注入
            self._data_injected = True
            
            logger.info(f"[ChanStrategyV2] 数据处理完成:")
            logger.info(f"  - 分型数量: {len(self.fractals)}")
            logger.info(f"  - 笔数量: {len(self.pens)}")
            logger.info(f"  - ATR值: {self.current_atr:.4f}")
            
            if self.fractals:
                first_fractal = self.fractals[0]
                ftype = first_fractal.type.upper()
                price = first_fractal.high if first_fractal.type == "top" else first_fractal.low
                logger.info(f"  - 首个分型: {ftype} @ 索引{first_fractal.idx}, 价格{price:.2f}")
                
        except Exception as e:
            logger.error(f"[ChanStrategyV2] 数据注入失败: {e}", exc_info=True)

    def _calculate_atr(self) -> None:
        """计算当前ATR值"""
        try:
            if self.df_30m is None or self.df_30m.empty or len(self.df_30m) < 15:
                self.current_atr = 0.0
                return
            
            df = self.df_30m
            high = df['high'].astype(float)
            low = df['low'].astype(float)
            close = df['close'].astype(float)
            prev_close = close.shift(1)
            
            tr1 = high - low
            tr2 = abs(high - prev_close)
            tr3 = abs(low - prev_close)
            true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            atr = true_range.ewm(span=14, adjust=False).mean()
            self.current_atr = float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0.0
            
        except Exception as e:
            logger.warning(f"[ChanStrategyV2] ATR计算失败: {e}")
            self.current_atr = 0.0

    def _process_data(self):
        """
        数据处理（V2策略不需要每根K线重新处理）
        
        由于我们在initialize时已经完成了所有数据处理，
        这里只需要保持接口兼容性，不做实际操作。
        """
        pass

    def _sync_internal_data(self):
        """同步内部策略的数据到V2策略"""
        self.fractals = self._internal_strategy.fractals
        self.pens = self._internal_strategy.pens
        self.segments = self._internal_strategy.segments
        self.df_processed = self._internal_strategy.df_processed
        self.df_30m = getattr(self._internal_strategy, 'df_30m', None)
        self.df_5m = getattr(self._internal_strategy, 'df_5m', None)
        self.df_daily = getattr(self._internal_strategy, 'df_daily', None)

    def _get_latest_fractal(self) -> Optional[Fractal]:
        """
        获取最新的分型（最后一个分型）
        
        Returns:
            最新的Fractal对象，如果没有则返回None
        """
        if not self.fractals:
            return None
        return self.fractals[-1]

    def _is_new_fractal(self, fractal: Fractal) -> bool:
        """
        检查是否是新的未处理分型
        
        Args:
            fractal: 要检查的分型对象
            
        Returns:
            是否是新分型
        """
        if self.last_fractal_idx != fractal.idx:
            self.last_fractal_idx = fractal.idx
            self.last_fractal_type = fractal.type
            return True
        return False

    def _calculate_long_stop_loss(self, entry_price: float) -> float:
        """
        计算多单止损价
        
        Args:
            entry_price: 入场价格
            
        Returns:
            止损价格
        """
        if self.use_atr_stop and self.current_atr > 0:
            stop_loss = entry_price - (self.current_atr * self.atr_multiplier)
            logger.debug(f"[ChanStrategyV2] ATR多单止损: 入场{entry_price:.2f} - ATR({self.current_atr:.4f})×{self.atr_multiplier} = {stop_loss:.2f}")
            return stop_loss
        else:
            stop_loss = entry_price * (1 - self.long_stop_loss_ratio)
            logger.debug(f"[ChanStrategyV2] 固定多单止损: {entry_price:.2f} × (1-{self.long_stop_loss_ratio}) = {stop_loss:.2f}")
            return stop_loss

    def _calculate_short_stop_loss(self, entry_price: float) -> float:
        """
        计算空单止损价
        
        Args:
            entry_price: 入场价格
            
        Returns:
            止损价格
        """
        if self.use_atr_stop and self.current_atr > 0:
            stop_loss = entry_price + (self.current_atr * self.atr_multiplier)
            logger.debug(f"[ChanStrategyV2] ATR空单止损: 入场{entry_price:.2f} + ATR({self.current_atr:.4f})×{self.atr_multiplier} = {stop_loss:.2f}")
            return stop_loss
        else:
            stop_loss = entry_price * (1 + self.short_stop_loss_ratio)
            logger.debug(f"[ChanStrategyV2] 固定空单止损: {entry_price:.2f} × (1+{self.short_stop_loss_ratio}) = {stop_loss:.2f}")
            return stop_loss

    def _create_buy_signal(
        self,
        fractal: Fractal,
        is_first: bool = False,
        is_add: bool = False
    ) -> Dict[str, Any]:
        """
        创建买入信号
        
        Args:
            fractal: 触发信号的底分型
            is_first: 是否是首仓
            is_add: 是否是加仓
            
        Returns:
            信号字典
        """
        entry_price = fractal.low * 1.001  # 在底分型低点上方0.1%入场
        stop_loss = self._calculate_long_stop_loss(entry_price)
        
        if is_first:
            reason = f"首仓 - 底分型@{fractal.low:.2f}"
        elif is_add:
            add_num = self.position_state.entry_count + 1
            reason = f"加仓({add_num}/{self.max_add_positions}) - 底分型@{fractal.low:.2f}"
        else:
            reason = f"BUY - 底分型@{fractal.low:.2f}"
        
        signal = {
            "action": "BUY",
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "reason": reason,
            "position": "long",
            "is_first_position": is_first,
            "is_add_position": is_add,
            "fractal_idx": fractal.idx,
            "fractal_type": fractal.type,
            "leverage": self.leverage,
        }
        
        logger.info(f"[ChanStrategyV2] 📈 生成买入信号: {reason}, 入场价={entry_price:.2f}, 止损={stop_loss:.2f}")
        return signal

    def _create_sell_signal(
        self,
        fractal: Fractal,
        is_first: bool = False,
        is_add: bool = False
    ) -> Dict[str, Any]:
        """
        创建卖出信号
        
        Args:
            fractal: 触发信号的顶分型
            is_first: 是否是首仓
            is_add: 是否是加仓
            
        Returns:
            信号字典
        """
        entry_price = fractal.high * 0.999  # 在顶分型高点下方0.1%入场
        stop_loss = self._calculate_short_stop_loss(entry_price)
        
        if is_first:
            reason = f"首仓 - 顶分型@{fractal.high:.2f}"
        elif is_add:
            add_num = self.position_state.entry_count + 1
            reason = f"加仓({add_num}/{self.max_add_positions}) - 顶分型@{fractal.high:.2f}"
        else:
            reason = f"SELL - 顶分型@{fractal.high:.2f}"
        
        signal = {
            "action": "SELL",
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "reason": reason,
            "position": "short",
            "is_first_position": is_first,
            "is_add_position": is_add,
            "fractal_idx": fractal.idx,
            "fractal_type": fractal.type,
            "leverage": self.leverage,
        }
        
        logger.info(f"[ChanStrategyV2] 📉 生成卖出信号: {reason}, 入场价={entry_price:.2f}, 止损={stop_loss:.2f}")
        return signal

    def _create_reversal_signal(
        self,
        reversal_type: str,
        fractal: Fractal
    ) -> Dict[str, Any]:
        """
        创建反转信号（平仓+反向开仓）
        
        Args:
            reversal_type: 反转类型 ("long_to_short" 或 "short_to_long")
            fractal: 触发反转的分型
            
        Returns:
            反转信号字典
        """
        if reversal_type == "long_to_short":
            action = "REVERSE_TO_SHORT"
            close_reason = f"⚡ 顶分型反转@{fractal.high:.2f}"
            new_action = "SELL"
            new_entry_price = fractal.high * 0.999
            new_stop_loss = self._calculate_short_stop_loss(new_entry_price)
            
        else:  # short_to_long
            action = "REVERSE_TO_LONG"
            close_reason = f"⚡ 底分型反转@{fractal.low:.2f}"
            new_action = "BUY"
            new_entry_price = fractal.low * 1.001
            new_stop_loss = self._calculate_long_stop_loss(new_entry_price)
        
        signal = {
            "action": action,
            "close_reason": close_reason,
            "new_action": new_action,
            "new_entry_price": new_entry_price,
            "new_stop_loss": new_stop_loss,
            "reason": f"{close_reason} → 开{'空' if new_action == 'SELL' else '多'}",
            "position": "short" if new_action == "SELL" else "long",
            "is_first_position": True,  # 反转后的首仓
            "is_add_position": False,
            "fractal_idx": fractal.idx,
            "fractal_type": fractal.type,
            "leverage": self.leverage,
        }
        
        current_dir = self.position_state.direction or "无持仓"
        logger.info(f"[ChanStrategyV2] 🔄 生成反转信号: {current_dir} → {signal['position']}, {close_reason}")
        return signal

    def update_position_state(
        self,
        direction: Optional[str] = None,
        entry_count: int = 0,
        signal: Dict[str, Any] = None
    ) -> None:
        """
        更新V2策略的持仓状态
        
        Args:
            direction: 持仓方向 ("long", "short", 或 None)
            entry_count: 加仓次数（0表示首仓）
            signal: 信号字典（自动从中提取direction和entry_count）
        """
        if signal is not None:
            pos = signal.get("position", "")
            direction = pos if pos in ("long", "short") else direction
            if signal.get("is_first_position"):
                entry_count = 1
            elif signal.get("is_add_position"):
                entry_count = self.position_state.entry_count + 1
        
        self.position_state.direction = direction
        self.position_state.entry_count = entry_count
        
        if direction is None:
            self.position_state.total_position_size = 0.0
            self.position_state.avg_entry_price = 0.0
            self.position_state.initial_stop_loss = 0.0
        
        logger.debug(f"[ChanStrategyV2] 更新持仓状态: 方向={direction}, 加仓次数={entry_count}")

    def extend_cooldown_after_loss(self, position_type: str):
        """
        扩展冷却期（亏损后调用）
        
        V2策略不需要复杂的冷却期机制，
        因为它是基于分型的，每个分型都是独立的交易机会。
        这里只做日志记录。
        
        Args:
            position_type: 持仓类型 ("long" 或 "short")
        """
        logger.info(f"[ChanStrategyV2] 检测到{position_type}方向亏损，V2策略不扩展冷却期")

    async def on_bar(self, bar_data: Dict[str, Any], bar_idx: int = None) -> Optional[Dict[str, Any]]:
        """
        K线数据更新回调
        
        Args:
            bar_data: K线数据字典
            bar_idx: 当前K线索引（用于分型匹配）
            
        Returns:
            交易信号字典
        """
        return self.generate_signal(bar_idx=bar_idx)

    async def on_order_update(self, order_data: Dict[str, Any]) -> None:
        """
        订单更新回调
        
        Args:
            order_data: 订单数据字典
        """
        logger.info(f"[ChanStrategyV2] 订单更新: {order_data}")

    def _build_signal_for_fractal(self, fractal: Fractal) -> Optional[Dict[str, Any]]:
        current_state = self.position_state.direction
        fractal_type = fractal.type

        logger.info(f"[ChanStrategyV2] 处理分型: "
                   f"类型={fractal_type}, bar_idx={fractal.idx}, ts={fractal.timestamp}, "
                   f"持仓={current_state or '空仓'}, 加仓次数={self.position_state.entry_count}")

        if current_state is None:
            if fractal_type == "bottom":
                return self._create_buy_signal(fractal, is_first=True)
            elif fractal_type == "top":
                return self._create_sell_signal(fractal, is_first=True)

        elif current_state == "long":
            if fractal_type == "bottom":
                if self.position_state.entry_count < self.max_add_positions:
                    return self._create_buy_signal(fractal, is_add=True)
                else:
                    logger.info(f"[ChanStrategyV2] 已达最大加仓次数({self.max_add_positions}次)")
                    return None
            elif fractal_type == "top":
                return self._create_reversal_signal("long_to_short", fractal)

        elif current_state == "short":
            if fractal_type == "top":
                if self.position_state.entry_count < self.max_add_positions:
                    return self._create_sell_signal(fractal, is_add=True)
                else:
                    logger.info(f"[ChanStrategyV2] 已达最大加仓次数({self.max_add_positions}次)")
                    return None
            elif fractal_type == "bottom":
                return self._create_reversal_signal("short_to_long", fractal)

        return None

    def generate_signal(self, bar_idx: int = None) -> Optional[Dict[str, Any]]:
        """
        V2策略信号生成逻辑（核心方法）
        
        实时模式(bar_idx提供)：
        扫描所有 <= bar_idx 的分型，返回第一个未处理分型的信号。
        用 _last_processed_fractal_ts 追踪已处理分型，确保不重复触发。
        
        回测模式(bar_idx为None)：
        顺序遍历所有分型，每次调用返回下一个分型的信号。
        
        Args:
            bar_idx: 当前K线在数据框中的索引
        
        Returns:
            信号字典，或HOLD信号
        """
        if not self.fractals or len(self.fractals) == 0:
            return {"action": "HOLD"}

        if bar_idx is not None:
            for i in range(self._current_fractal_idx, len(self.fractals)):
                fractal = self.fractals[i]
                if fractal.idx > bar_idx:
                    break
                if (self._last_processed_fractal_ts is not None and
                        fractal.timestamp <= self._last_processed_fractal_ts):
                    self._current_fractal_idx = i + 1
                    continue

                self._current_fractal_idx = i + 1
                self._last_processed_fractal_ts = fractal.timestamp
                signal = self._build_signal_for_fractal(fractal)
                if signal:
                    return signal
                break

            return {"action": "HOLD"}

        if self._current_fractal_idx >= len(self.fractals):
            return {"action": "HOLD"}
        fractal = self.fractals[self._current_fractal_idx]
        self._current_fractal_idx += 1

        signal = self._build_signal_for_fractal(fractal)
        if signal:
            return signal
        return {"action": "HOLD"}

    def generate_all_pending_signals(self, bar_idx: int) -> List[Dict[str, Any]]:
        """
        批量生成所有待处理分型的信号（补救机制）
        
        扫描所有 fractal.idx <= bar_idx 且未被处理的分型，
        依次生成信号并更新持仓状态，返回全部信号列表。
        
        Args:
            bar_idx: 当前K线在数据框中的索引
        
        Returns:
            信号列表
        """
        if not self.fractals or len(self.fractals) == 0:
            return []

        signals = []
        for i in range(self._current_fractal_idx, len(self.fractals)):
            fractal = self.fractals[i]
            if fractal.idx > bar_idx:
                break
            if (self._last_processed_fractal_ts is not None and
                    fractal.timestamp <= self._last_processed_fractal_ts):
                self._current_fractal_idx = i + 1
                continue

            self._current_fractal_idx = i + 1
            self._last_processed_fractal_ts = fractal.timestamp

            signal = self._build_signal_for_fractal(fractal)
            if signal:
                signals.append(signal)
                self.update_position_state(signal=signal)

        return signals

    def get_status(self) -> Dict[str, Any]:
        """
        获取策略状态信息
        
        Returns:
            策略状态字典
        """
        return {
            "name": self.name,
            "symbol": self.symbol,
            "time_frame": self.time_frame,
            "version": "V2",
            
            # 缠论元素统计
            "fractals_count": len(self.fractals),
            "pens_count": len(self.pens),
            "segments_count": len(self.segments),
            
            # 持仓状态
            "position_direction": self.position_state.direction,
            "entry_count": self.position_state.entry_count,
            "total_position_size": self.position_state.total_position_size,
            "avg_entry_price": self.position_state.avg_entry_price,
            
            # 配置参数
            "max_add_positions": self.max_add_positions,
            "investment_ratio": self.investment_ratio,
            "leverage": self.leverage,
            
            # 技术指标
            "current_atr": self.current_atr,
            
            # 分型信息
            "last_fractal_type": self.last_fractal_type,
            "last_fractal_idx": self.last_fractal_idx,
        }


class ChanStrategyV2Executor:
    """
    缠论V2策略执行器（实时/模拟盘交易）

    负责：
    1. 定期获取最新K线数据（Binance API）
    2. 调用ChanStrategyV2进行数据处理和信号生成
    3. 根据V2信号类型执行交易：首次开仓、加仓、反转（平全部+反向开仓）
    4. 支持模拟盘（is_simulated=True）和实盘模式
    """

    def __init__(
        self,
        client,
        symbol: str = "ETHUSDC",
        time_frame: str = "30m",
        check_interval: int = 60,
        investment_ratio: float = 0.10,
        leverage: int = 20,
        max_add_positions: int = 3,
        long_sl_multiplier: float = 1.50,
        short_sl_multiplier: float = 0.70,
        hg1: int = 8,
    ):
        self.client = client
        self.symbol = symbol
        self.time_frame = time_frame
        self.check_interval = check_interval
        self.is_running = False

        self.investment_ratio = investment_ratio
        self.leverage = leverage
        self.max_add_positions = max_add_positions
        self.long_sl_multiplier = long_sl_multiplier
        self.short_sl_multiplier = short_sl_multiplier

        self.strategy = ChanStrategyV2(
            symbol=symbol,
            time_frame=time_frame,
            hg1=hg1,
            use_binance_client=True,
            max_add_positions=max_add_positions,
            investment_ratio=investment_ratio,
            leverage=leverage,
            long_stop_loss_ratio=0.03,
            short_stop_loss_ratio=0.03,
        )

        self._entry_count = 0

    async def start(self):
        logger.info(f"[ChanStrategyV2Executor] 启动V2策略执行器 | "
                   f"symbol={self.symbol} | timeframe={self.time_frame} | "
                   f"simulated={self.client.is_simulated} | "
                   f"投入={self.investment_ratio*100:.0f}% | 杠杆={self.leverage}x | 加仓={self.max_add_positions}次")
        self.is_running = True

        initialized = await self.strategy.initialize(self.symbol)
        if not initialized:
            logger.error(f"[ChanStrategyV2Executor] 策略初始化失败")
            return

        try:
            while self.is_running:
                await self._run_once()
                await asyncio.sleep(self.check_interval)
        except Exception as e:
            logger.error(f"[ChanStrategyV2Executor] 策略执行异常: {str(e)}", exc_info=True)
        finally:
            logger.info(f"[ChanStrategyV2Executor] 策略执行器已停止")

    async def stop(self):
        logger.info(f"[ChanStrategyV2Executor] 停止策略执行器")
        self.is_running = False

    async def _run_once(self):
        try:
            binance_client = BinanceRestClient(
                api_key=self.client.api_key,
                secret_key=self.client.secret_key,
                is_simulated=self.client.is_simulated,
            )
            try:
                logger.info(f"[ChanStrategyV2Executor] 获取{self.time_frame}K线数据...")
                continuous_klines = await binance_client.get_continuous_klines(
                    pair=self.symbol,
                    contractType="PERPETUAL",
                    interval=self.time_frame,
                    limit=800,
                )

                if not (isinstance(continuous_klines, list) and continuous_klines):
                    logger.error(f"[ChanStrategyV2Executor] K线数据格式错误")
                    return

                logger.info(f"[ChanStrategyV2Executor] 获取到 {len(continuous_klines)} 条{self.time_frame}K线")
                if isinstance(continuous_klines, list) and len(continuous_klines) > 0:
                    first_time = pd.to_datetime(continuous_klines[0][0], unit='ms')
                    last_time = pd.to_datetime(continuous_klines[-1][0], unit='ms')
                    delay_mins = (pd.Timestamp.now() - last_time).total_seconds() / 60
                    logger.info(f"[ChanStrategyV2Executor] {self.time_frame}K线时间: {first_time} ~ {last_time}")
                    logger.info(f"[ChanStrategyV2Executor] 最新{self.time_frame}K线: {last_time} (延迟{delay_mins:.1f}分钟)")

                if self.time_frame == "5m":
                    self.df_5m = binance_klines_to_dataframe(continuous_klines)
                else:
                    self.df_30m = binance_klines_to_dataframe(continuous_klines)

                logger.info(f"[ChanStrategyV2Executor] 获取日线K线数据...")
                daily_klines = await binance_client.get_continuous_klines(
                    pair=self.symbol,
                    contractType="PERPETUAL",
                    interval="1d",
                    limit=200,
                )

                if not (isinstance(daily_klines, list) and daily_klines):
                    logger.error(f"[ChanStrategyV2Executor] 日线K线数据格式错误")
                    return

                logger.info(f"[ChanStrategyV2Executor] 获取到 {len(daily_klines)} 条日线K线")
                if isinstance(daily_klines, list) and len(daily_klines) > 0:
                    daily_first = pd.to_datetime(daily_klines[0][0], unit='ms')
                    daily_last = pd.to_datetime(daily_klines[-1][0], unit='ms')
                    logger.info(f"[ChanStrategyV2Executor] 日线K线时间: {daily_first} ~ {daily_last}")
                self.df_daily = binance_klines_to_dataframe(daily_klines)
            finally:
                await binance_client.close()

            if self.time_frame == "5m":
                if self.df_5m.empty:
                    logger.warning(f"[ChanStrategyV2Executor] 5m数据为空")
                    return
                self.strategy._internal_strategy.df_5m = self.df_5m
                self.strategy._internal_strategy.df_30m = self.df_5m
            else:
                if self.df_30m.empty:
                    logger.warning(f"[ChanStrategyV2Executor] 30m数据为空")
                    return
                self.strategy._internal_strategy.df_30m = self.df_30m

            self.strategy._internal_strategy.df_daily = self.df_daily
            self.strategy._internal_strategy.use_inclusion_merge = False
            self.strategy._internal_strategy._process_data()
            self.strategy._sync_internal_data()
            self.strategy._calculate_atr()

            self.strategy._current_fractal_idx = 0

            status = self.strategy.get_status()
            logger.info(f"[ChanStrategyV2Executor] V2策略状态: "
                       f"分型={status['fractals_count']} | "
                       f"持仓={status['position_direction'] or '空仓'} | "
                       f"入场次数={status['entry_count']}")

            if self.strategy.fractals:
                recent = self.strategy.fractals[-5:]
                f_info = []
                for f in recent:
                    f_type = "顶" if f.type == "top" else "底"
                    f_price = f.high if f.type == "top" else f.low
                    f_info.append(f"{f_type}@{f.idx}({f_price:.2f})")
                logger.info(f"[ChanStrategyV2Executor] 最新分型: {' → '.join(f_info)}")

            bar_idx = len(self.strategy._internal_strategy.df_processed) - 1
            pending_signals = self.strategy.generate_all_pending_signals(bar_idx=bar_idx)

            if pending_signals:
                for signal in pending_signals:
                    logger.info(f"[ChanStrategyV2Executor] >>> V2信号: action={signal['action']}, "
                               f"add={signal.get('is_add_position', False)}, "
                               f"reason={signal.get('reason', '')}")
                    await self._execute_v2_signal(signal)
            else:
                logger.info(f"[ChanStrategyV2Executor] 无新交易信号 (HOLD)")

        except Exception as e:
            logger.error(f"[ChanStrategyV2Executor] 执行异常: {str(e)}", exc_info=True)

    async def _execute_v2_signal(self, signal: Dict[str, Any]):
        action = signal.get("action", "")
        is_add = signal.get("is_add_position", False)

        try:
            df = self.strategy._internal_strategy.df_processed
            current_price = float(df.iloc[-1]["close"]) if not df.empty else 0
            if current_price <= 0:
                logger.error(f"[ChanStrategyV2Executor] 无法获取当前价格")
                return

            account = await self.client.get_account()
            usdt_balance = float(account.get("availableBalance", 0)) if isinstance(account, dict) else 0
            if usdt_balance <= 0:
                usdt_balance = float(account.get("totalMarginBalance", account.get("balance", 10000)))
            logger.info(f"[ChanStrategyV2Executor] 当前价格={current_price:.2f} | 可用余额=${usdt_balance:.2f}")

            if action == "REVERSE_TO_SHORT":
                await self._close_all_long(usdt_balance)
                await self._open_short(current_price, usdt_balance)
                self._entry_count = 1

            elif action == "REVERSE_TO_LONG":
                await self._close_all_short(usdt_balance)
                await self._open_long(current_price, usdt_balance)
                self._entry_count = 1

            elif action == "BUY":
                if is_add:
                    await self._add_long(current_price, usdt_balance)
                    self._entry_count += 1
                else:
                    await self._close_all_short(usdt_balance)
                    await self._open_long(current_price, usdt_balance)
                    self._entry_count = 1

            elif action == "SELL":
                if is_add:
                    await self._add_short(current_price, usdt_balance)
                    self._entry_count += 1
                else:
                    await self._close_all_long(usdt_balance)
                    await self._open_short(current_price, usdt_balance)
                    self._entry_count = 1

            self.strategy.update_position_state(signal=signal)

        except Exception as e:
            logger.error(f"[ChanStrategyV2Executor] 执行信号失败: {str(e)}", exc_info=True)

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
            logger.info(f"[ChanStrategyV2Executor] 无多单需平仓")
            return
        logger.info(f"[ChanStrategyV2Executor] 平掉全部多单: {qty:.3f}")

        result = await self.client.place_order(
            symbol=self.symbol,
            side="SELL",
            position_side="LONG",
            order_type="MARKET",
            quantity=qty,
        )
        logger.info(f"[ChanStrategyV2Executor] 平多单结果: {result.get('msg', result.get('error', 'OK'))}")

    async def _close_all_short(self, usdt_balance: float):
        qty = await self._get_position_quantity("SHORT")
        if qty <= 0:
            logger.info(f"[ChanStrategyV2Executor] 无空单需平仓")
            return
        logger.info(f"[ChanStrategyV2Executor] 平掉全部空单: {qty:.3f}")

        result = await self.client.place_order(
            symbol=self.symbol,
            side="BUY",
            position_side="SHORT",
            order_type="MARKET",
            quantity=qty,
        )
        logger.info(f"[ChanStrategyV2Executor] 平空单结果: {result.get('msg', result.get('error', 'OK'))}")

    async def _open_long(self, price: float, balance: float):
        investment_amount = balance * self.investment_ratio
        qty = (investment_amount * self.leverage) / price
        qty = round(qty, 3)

        liquidation_price = price * (1 - 1 / self.leverage)
        stop_loss_price = liquidation_price * self.long_sl_multiplier

        result = await self.client.place_order(
            symbol=self.symbol,
            side="BUY",
            position_side="LONG",
            order_type="MARKET",
            quantity=qty,
        )
        logger.info(f"[ChanStrategyV2Executor] 开多: 投入=${investment_amount:.2f} | "
                   f"数量={qty} | 杠杆={self.leverage}x | 止损≈{stop_loss_price:.2f}")
        return result

    async def _open_short(self, price: float, balance: float):
        investment_amount = balance * self.investment_ratio
        qty = (investment_amount * self.leverage) / price
        qty = round(qty, 3)

        liquidation_price = price * (1 + 1 / self.leverage)
        stop_loss_price = liquidation_price * self.short_sl_multiplier

        result = await self.client.place_order(
            symbol=self.symbol,
            side="SELL",
            position_side="SHORT",
            order_type="MARKET",
            quantity=qty,
        )
        logger.info(f"[ChanStrategyV2Executor] 开空: 投入=${investment_amount:.2f} | "
                   f"数量={qty} | 杠杆={self.leverage}x | 止损≈{stop_loss_price:.2f}")
        return result

    async def _add_long(self, price: float, balance: float):
        investment_amount = balance * self.investment_ratio * 0.5
        qty = (investment_amount * self.leverage) / price
        qty = round(qty, 3)

        result = await self.client.place_order(
            symbol=self.symbol,
            side="BUY",
            position_side="LONG",
            order_type="MARKET",
            quantity=qty,
        )
        logger.info(f"[ChanStrategyV2Executor] 加仓多单(#{self._entry_count + 1}): "
                   f"投入=${investment_amount:.2f} | 数量={qty}")
        return result

    async def _add_short(self, price: float, balance: float):
        investment_amount = balance * self.investment_ratio * 0.5
        qty = (investment_amount * self.leverage) / price
        qty = round(qty, 3)

        result = await self.client.place_order(
            symbol=self.symbol,
            side="SELL",
            position_side="SHORT",
            order_type="MARKET",
            quantity=qty,
        )
        logger.info(f"[ChanStrategyV2Executor] 加仓空单(#{self._entry_count + 1}): "
                   f"投入=${investment_amount:.2f} | 数量={qty}")
        return result


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    
    async def test():
        print("=" * 70)
        print("测试 ChanStrategyV2 - ETHUSDC 30分钟级别")
        print("=" * 70)
        
        strategy = ChanStrategyV2(
            symbol="ETHUSDC",
            time_frame="30m",
            max_add_positions=3,
            investment_ratio=0.10,
            leverage=20,
            use_binance_client=False
        )
        
        print("\n初始化策略...")
        success = await strategy.initialize("ETHUSDC")
        
        if success:
            status = strategy.get_status()
            print("\n✅ 策略初始化成功!")
            print(f"\n📊 策略状态:")
            for key, value in status.items():
                print(f"  {key}: {value}")
            
            print("\n生成测试信号...")
            signal = strategy.generate_signal()
            print(f"\n📈 交易信号: {signal}")
        else:
            print("\n❌ 策略初始化失败!")
    
    asyncio.run(test())
