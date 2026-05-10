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
        direction: Optional[str],
        entry_count: int = 0
    ) -> None:
        """
        更新V2策略的持仓状态
        
        Args:
            direction: 持仓方向 ("long", "short", 或 None)
            entry_count: 加仓次数（0表示首仓）
        """
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

    def generate_signal(self, bar_idx: int = None) -> Optional[Dict[str, Any]]:
        """
        V2策略信号生成逻辑（核心方法）
        
        基于分型索引的匹配逻辑：
        1. 查找当前bar_idx位置是否有分型
        2. 如果有，根据分型类型和当前持仓状态生成信号
        
        Args:
            bar_idx: 当前K线在数据框中的索引（None时保持顺序处理向后兼容）
        
        Returns:
            信号字典，或HOLD信号
        """
        if not self.fractals or len(self.fractals) == 0:
            return {"action": "HOLD"}
        
        if bar_idx is not None:
            while self._current_fractal_idx < len(self.fractals):
                fractal = self.fractals[self._current_fractal_idx]
                if fractal.idx > bar_idx:
                    return {"action": "HOLD"}
                if fractal.idx == bar_idx:
                    break
                self._current_fractal_idx += 1
            else:
                return {"action": "HOLD"}
            
            fractal = self.fractals[self._current_fractal_idx]
            self._current_fractal_idx += 1
        else:
            if self._current_fractal_idx >= len(self.fractals):
                return {"action": "HOLD"}
            fractal = self.fractals[self._current_fractal_idx]
            self._current_fractal_idx += 1

        current_state = self.position_state.direction
        fractal_type = fractal.type

        logger.info(f"[ChanStrategyV2] 处理分型[{self._current_fractal_idx}/{len(self.fractals)}]: "
                   f"类型={fractal_type}, bar_idx={fractal.idx}, "
                   f"持仓={current_state or '空仓'}, 加仓次数={self.position_state.entry_count}")

        signal = None

        if current_state is None:
            if fractal_type == "bottom":
                signal = self._create_buy_signal(fractal, is_first=True)
            elif fractal_type == "top":
                signal = self._create_sell_signal(fractal, is_first=True)

        elif current_state == "long":
            if fractal_type == "bottom":
                if self.position_state.entry_count < self.max_add_positions:
                    signal = self._create_buy_signal(fractal, is_add=True)
                else:
                    logger.info(f"[ChanStrategyV2] 已达最大加仓次数({self.max_add_positions}次)")

            elif fractal_type == "top":
                signal = self._create_reversal_signal("long_to_short", fractal)

        elif current_state == "short":
            if fractal_type == "top":
                if self.position_state.entry_count < self.max_add_positions:
                    signal = self._create_sell_signal(fractal, is_add=True)
                else:
                    logger.info(f"[ChanStrategyV2] 已达最大加仓次数({self.max_add_positions}次)")

            elif fractal_type == "bottom":
                signal = self._create_reversal_signal("short_to_long", fractal)

        return signal if signal else {"action": "HOLD"}

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
