"""
回测引擎模块
提供完整的现货交易回测功能，支持缠论策略
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from typing_extensions import  Literal

import numpy as np
import pandas as pd
from tqdm import tqdm

from trading_system.data.backtest_data import BacktestDataManager
from trading_system.strategies.chan_strategy import ChanStrategy
from trading_system.utils.chan_plotter import ChanPlotter

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backtest_engine.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """回测配置"""
    initial_balance: float = 10000.0
    commission: float = 0.0004  # 交易手续费率0.04%（双向收费），限价单模式下的优惠费率（vs 市价单的0.1%）
    slippage: float = 0.0005
    data_dir: str = "trading_system/data/binance_history"
    max_position_ratio: float = 1.0
    stop_loss_pct: float = 0.1
    take_profit_pct: float = 0.2
    plot_enabled: bool = True
    save_results: bool = True
    progress_bar: bool = True

    # 连续循环交易配置参数
    investment_ratio: float = 0.10  # 每次投入总金额的比例，默认10%
    leverage: int = 50  # 杠杆倍数，默认50倍
    long_stop_loss_multiplier: float = 1.20  # 多单止损 = 爆仓价格 * 此值，默认120%
    short_stop_loss_multiplier: float = 0.80  # 空单止损 = 爆仓价格 * 此值，默认80%

    # ATR止损配置（新增 - 第三轮优化）
    use_atr_stop_loss: bool = True  # 是否启用ATR止损
    atr_period: int = 14  # ATR计算周期
    atr_multiplier: float = 3.0  # ATR倍数（止损距离 = ATR * multiplier）【从2.5优化至3.0，更宽松】

    # 动态追踪止损配置（新增 - 第三轮优化）
    use_trailing_stop: bool = True  # 是否启用追踪止损
    trailing_stop_activation: float = 0.04  # 激活追踪止损的盈利比例(4%)【从3%优化至4%】
    trailing_stop_distance: float = 0.025  # 追踪止损距离(2.5%)【从2%优化至2.5%】
    trailing_stop_step: float = 0.015  # 追踪止损步进(1.5%)【从1%优化至1.5%】

    # 做多止盈止损（独立）
    long_take_profit_ratio: float = 0.05       # 做多止盈 5%
    long_stop_loss_ratio: float = 0.03         # 做多止损 3%
    long_trailing_stop_activation: float = 0.04  # 做多追踪止损激活阈值
    long_trailing_stop_distance: float = 0.02  # 做多追踪止损距离 2%

    # 做空止盈止损（独立）
    short_take_profit_ratio: float = 0.05       # 做空止盈 5%
    short_stop_loss_ratio: float = 0.03         # 做空止损 3%
    short_trailing_stop_activation: float = 0.04  # 做空追踪止损激活阈值
    short_trailing_stop_distance: float = 0.02  # 做空追踪止损距离 2%

    # 限价单配置（新增 - 价格偏差检测）
    limit_order_enabled: bool = True  # 是否启用限价单模式
    price_deviation_tolerance: float = 0.001  # 价格偏差容忍度，默认0.1%

    # 资金费用配置（合约交易 - 新增）
    funding_rate: float = 0.0001  # 默认资金费率0.01%（每4小时结算）
    enable_funding_fee: bool = True  # 是否启用资金费用计算


@dataclass
class LimitOrder:
    """限价单数据结构"""
    timestamp: datetime
    action: Literal["BUY", "SELL"]
    limit_price: float  # 期望成交价格
    amount: float
    deviation_tolerance: float = 0.001  # 偏差容忍度
    status: str = "pending"  # pending, filled, cancelled
    reason: str = ""


@dataclass
class TradeRecord:
    """交易记录数据结构"""
    timestamp: datetime
    action: Literal["BUY", "SELL"]
    price: float
    amount: float
    balance: float
    position: float
    equity: float
    profit: float = 0.0
    profit_pct: float = 0.0
    reason: str = ""
    stop_loss: float = 0.0
    take_profit: float = 0.0
    long_position: float = 0.0
    short_position: float = 0.0


@dataclass
class ClosedTrade:
    """已平仓交易记录"""
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    amount: float
    profit: float
    return_pct: float
    holding_hours: float
    stop_loss_hit: bool = False
    take_profit_hit: bool = False


class FundingFeeCalculator:
    """
    资金费用计算器

    合约交易每4小时结算一次资金费用（UTC时间：0:00, 4:00, 8:00, 12:00, 16:00, 20:00）
    多头持仓：费率为正时支付费用，费率为负时收取费用
    空头持仓：费率为正时收取费用，费率为负时支付费用
    """

    FUNDING_SETTLEMENT_HOURS = [0, 4, 8, 12, 16, 20]  # UTC结算时间点

    def __init__(self):
        self.last_settlement_time = None
        self.total_funding_fee_paid = 0.0  # 累计支付的资金费用
        self.total_funding_fee_received = 0.0  # 累计收到的资金费用
        self.funding_records: List[Dict] = []  # 资金费用记录

    def check_settlement(self, current_time: datetime, long_position: float,
                        long_position_value: float, short_position: float,
                        short_position_value: float, funding_rate: float = 0.0001) -> float:
        """
        检查是否需要结算资金费用

        Args:
            current_time: 当前时间
            long_position: 多头持仓数量（>=0）
            long_position_value: 多头持仓价值
            short_position: 空头持仓数量（>0）
            short_position_value: 空头持仓价值
            funding_rate: 当前资金费率（默认0.01%）

        Returns:
            本次结算的资金费用（正数=收到，负数=支付）
        """
        if long_position == 0 and short_position == 0:
            return 0.0

        current_hour = current_time.hour

        # 检查是否到达结算时间点且距离上次结算已过足够时间
        if current_hour not in self.FUNDING_SETTLEMENT_HOURS:
            return 0.0

        if (self.last_settlement_time and
            (current_time - self.last_settlement_time).total_seconds() < 3600):
            return 0.0

        # 计算资金费用
        # 多头持仓：费率>0时支付（负值），费率<0时收取（正值）
        # 空头持仓：与多头相反
        fee = 0.0
        if long_position > 0:
            fee += -long_position_value * funding_rate
        if short_position > 0:
            fee += short_position_value * funding_rate

        # 更新累计值
        if fee < 0:
            self.total_funding_fee_paid += abs(fee)
        else:
            self.total_funding_fee_received += fee

        # 记录本次结算
        record = {
            "timestamp": current_time,
            "long_position": long_position,
            "short_position": short_position,
            "long_position_value": long_position_value,
            "short_position_value": short_position_value,
            "funding_rate": funding_rate,
            "fee": fee,
            "cumulative_paid": self.total_funding_fee_paid,
            "cumulative_received": self.total_funding_fee_received
        }
        self.funding_records.append(record)
        self.last_settlement_time = current_time

        logger.info(
            f"[FundingFee] 结算资金费用: {fee:.4f} USDT "
            f"(多头:{long_position:.4f}/${long_position_value:.2f}, "
            f"空头:{short_position:.4f}/${short_position_value:.2f}, 费率:{funding_rate*100:.4f}%)"
        )

        return fee

    def get_summary(self) -> Dict:
        """获取资金费用汇总"""
        return {
            "total_paid": self.total_funding_fee_paid,
            "total_received": self.total_funding_fee_received,
            "net_fee": self.total_funding_fee_received - self.total_funding_fee_paid,
            "settlement_count": len(self.funding_records),
            "records": self.funding_records
        }


class BacktestEngine:
    """
    现货交易回测引擎

    功能特性：
    1. 支持仓位控制（最大仓位比例）
    2. 支持止损止盈
    3. 增量数据处理优化
    4. 完整的交易记录和绩效统计
    5. 可视化图表生成
    """

    def __init__(
        self,
        config: Optional[BacktestConfig] = None,
        initial_balance: float = None,
        commission: float = None,
        slippage: float = None,
        data_dir: str = None,
    ):
        """
        初始化回测引擎

        Args:
            config: 回测配置对象，如果提供则忽略其他参数
            initial_balance: 初始资金，如果config未提供则使用此参数
            commission: 手续费率，如果config未提供则使用此参数
            slippage: 滑点，如果config未提供则使用此参数
            data_dir: 数据目录，如果config未提供则使用此参数
        """
        if config is not None:
            self.config = config
        else:
            self.config = BacktestConfig(
                initial_balance=initial_balance if initial_balance is not None else BacktestConfig.initial_balance,
                commission=commission if commission is not None else BacktestConfig.commission,
                slippage=slippage if slippage is not None else BacktestConfig.slippage,
                data_dir=data_dir if data_dir is not None else BacktestConfig.data_dir,
            )
        self.data_dir = Path(self.config.data_dir)
        self.data_manager = BacktestDataManager(str(self.data_dir))
        self.funding_calculator = FundingFeeCalculator()
        self._reset_state()

    def _reset_state(self) -> None:
        """
        重置回测状态
        在每次回测开始前调用
        """
        self.balance = self.config.initial_balance
        self.position = 0.0
        self.avg_price = 0.0
        self.long_position = 0.0
        self.short_position = 0.0
        self.long_avg_price = 0.0
        self.short_avg_price = 0.0
        self.trades: List[TradeRecord] = []
        self.equity_curve: List[float] = []
        self.timestamps: List[datetime] = []
        self.max_equity = self.config.initial_balance
        self.max_drawdown = 0.0
        self.current_drawdown = 0.0
        self.consecutive_losses = 0
        self.max_consecutive_losses = 0

        # ATR和追踪止损状态（新增）
        self.current_atr: float = 0.0  # 当前ATR值
        self.trailing_stop_price: float = 0.0  # 当前追踪止损价
        self.initial_stop_loss_price: float = 0.0  # 初始止损价（ATR止损）
        self.highest_price_since_entry: float = 0.0  # 入场后最高价（多单用）
        self.lowest_price_since_entry: float = float('inf')  # 入场后最低价（空单用）
        self.is_trailing_stop_active: bool = False  # 追踪止损是否激活

        # 做多独立追踪止损变量
        self.long_trailing_stop_price: float = 0.0
        self.long_highest_price: float = 0.0
        self.long_initial_stop_loss_price: float = 0.0
        self.long_is_trailing_active: bool = False

        # 做空独立追踪止损变量
        self.short_trailing_stop_price: float = float('inf')
        self.short_lowest_price: float = float('inf')
        self.short_initial_stop_loss_price: float = float('inf')
        self.short_is_trailing_active: bool = False

        # 限价单统计（新增）
        self.cancelled_orders_count: int = 0  # 被取消的订单数量
        self.limit_orders: List[LimitOrder] = []  # 限价单记录列表

        # 资金费用计算器（重置）
        self.funding_calculator = FundingFeeCalculator()

    def load_data(
            self,
            symbol: str = "BTCUSDT",
            interval: str = "5m",
            start_date: Optional[str] = None,
            end_date: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        加载历史K线数据

        Args:
            symbol: 交易对
            interval: K线周期
            start_date: 开始日期，格式YYYY-MM-DD
            end_date: 结束日期，格式YYYY-MM-DD

        Returns:
            包含K线数据的字典
        """
        data: Dict[str, pd.DataFrame] = {}

        # 加载指定周期的K线
        df_interval = self._load_and_filter_data(
            f"{symbol}_{interval}.csv",
            start_date,
            end_date
        )
        if not df_interval.empty:
            data[interval] = self._prepare_dataframe(df_interval)
            logger.info("成功加载 %s 条%sK线数据", len(data[interval]), interval)
        else:
            logger.error("加载%s数据失败，请检查数据文件是否存在", interval)
            return data

        # 加载日线数据用于辅助分析
        df_1d = self._load_and_filter_data(f"{symbol}_1d.csv", start_date, end_date)
        if not df_1d.empty:
            data["1d"] = self._prepare_dataframe(df_1d)
            logger.info("成功加载 %s 条日线K线数据", len(data["1d"]))
        else:
            logger.warning("日线数据加载失败，策略可能无法正常计算日线级别指标")

        return data

    def _load_and_filter_data(
            self,
            filename: str,
            start_date: Optional[str],
            end_date: Optional[str]
    ) -> pd.DataFrame:
        """
        加载并过滤数据

        Args:
            filename: 数据文件名
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            过滤后的DataFrame
        """
        try:
            df = self.data_manager.load_klines_from_csv(filename)
            if df.empty:
                return df

            if "open_time" in df.columns:
                df["open_time"] = pd.to_datetime(df["open_time"])

                if start_date:
                    df = df[df["open_time"] >= pd.Timestamp(start_date)]
                if end_date:
                    df = df[df["open_time"] <= pd.Timestamp(end_date)]

            return df
        except Exception as e:
            logger.error("加载数据文件 %s 失败: %s", filename, e)
            return pd.DataFrame()

    def run_backtest(
            self,
            data: Dict[str, pd.DataFrame],
            strategy: ChanStrategy,
            interval: str = "5m",
            plot_filename: str = "backtest_plot.png"
    ) -> Dict[str, Any]:
        """
        执行回测主流程

        Args:
            data: K线数据
            strategy: 交易策略
            interval: K线周期
            plot_filename: 图表保存路径

        Returns:
            回测结果字典
        """
        try:
            # 验证数据
            if interval not in data:
                logger.error("缺少%s周期K线数据", interval)
                return {}

            df_interval = self._prepare_dataframe(data[interval])
            if df_interval.empty:
                logger.error("K线数据为空")
                return {}

            df_1d = data.get("1d", pd.DataFrame())
            if not df_1d.empty:
                df_1d = self._prepare_dataframe(df_1d)

            # 重置状态
            self._reset_state()

            # 配置策略
            strategy.use_binance_client = False

            # 准备日线时间索引
            daily_indices = self._prepare_daily_indices(df_interval, df_1d)

            # 执行回测循环
            self._run_backtest_loop(df_interval, df_1d, daily_indices, strategy)

            # 计算绩效指标
            results = self._calculate_performance()

            # 生成图表
            if self.config.plot_enabled:
                # 使用处理后的数据绘制图表（因为分型索引是在处理后数据上计算的）
                kline_data_for_plot = strategy.df_processed if hasattr(strategy, 'df_processed') and not strategy.df_processed.empty else df_interval
                self._plot_results(kline_data_for_plot, strategy, plot_filename)

            # 保存结果
            if self.config.save_results and results:
                self.save_results(results)

            return results

        except Exception as e:
            logger.error("回测执行失败: %s", e, exc_info=True)
            return {}

    def _prepare_daily_indices(
            self,
            df_interval: pd.DataFrame,
            df_1d: pd.DataFrame
    ) -> np.ndarray:
        """
        准备日线时间索引

        Args:
            df_interval: 周期K线数据
            df_1d: 日线数据

        Returns:
            日线结束索引数组
        """
        if df_1d.empty:
            return np.zeros(len(df_interval), dtype=int)

        # 将时间转换为日期
        daily_days = df_1d["open_time"].dt.normalize().to_numpy(dtype="datetime64[D]")
        bar_days = df_interval["open_time"].dt.normalize().to_numpy(dtype="datetime64[D]")

        # 为每个bar找到对应的日线结束位置
        daily_end_indices = np.searchsorted(daily_days, bar_days, side="right")
        return np.clip(daily_end_indices, 0, len(df_1d) - 1)

    def _run_backtest_loop(
            self,
            df_interval: pd.DataFrame,
            df_1d: pd.DataFrame,
            daily_indices: np.ndarray,
            strategy: ChanStrategy
    ) -> None:
        """
        执行回测循环

        Args:
            df_interval: 周期K线数据
            df_1d: 日线数据
            daily_indices: 日线索引
            strategy: 交易策略
        """
        # 创建进度条
        iterator = enumerate(zip(df_interval.itertuples(), daily_indices))
        if self.config.progress_bar:
            iterator = tqdm(iterator, total=len(df_interval), desc="回测进度")

        # 主循环
        for i, (kline, daily_end_idx) in iterator:
            # 更新策略数据
            if not df_1d.empty and daily_end_idx > 0:
                strategy.df_30m = df_interval.iloc[:i + 1]
                strategy.df_daily = df_1d.iloc[:daily_end_idx]

            # 处理数据
            try:
                strategy._process_data()
            except Exception as e:
                logger.warning("第%d根K线数据处理失败: %s", i, e)
                continue

            # 生成信号
            signal = strategy.generate_signal()

            # 计算ATR（用于动态止损）
            if self.config.use_atr_stop_loss or self.config.use_trailing_stop:
                self._calculate_current_atr(strategy)

            # 检查止损止盈（分多空独立检查）
            if self.long_position > 0:
                self._check_long_stop_loss(kline)
            if self.short_position > 0:
                self._check_short_stop_loss(kline)

            # 执行交易
            if signal and signal.get("action") != "HOLD":
                self._execute_trade(signal, kline)

            # 结算资金费用（合约交易）
            if self.config.enable_funding_fee and (self.long_position != 0 or self.short_position != 0):
                funding_fee = self._settle_funding_fee(kline)
                if funding_fee != 0:
                    self.balance += funding_fee  # 调整账户余额

            # 记录权益
            self._record_equity(kline)

            # 定期清理内存
            if i % 1000 == 0:
                import gc
                gc.collect()

    def _settle_funding_fee(self, kline) -> float:
        """
        结算资金费用（合约交易）

        在每根K线处理时检查是否到达结算时间点，
        如果是则分别计算多头和空头的资金费用并汇总

        Args:
            kline: 当前K线数据

        Returns:
            本次结算的资金费用（正数=收到，负数=支付，0=无需结算）
        """
        try:
            if hasattr(kline, 'close'):
                current_price = float(kline.close)
                current_time = kline.open_time
            else:
                current_price = float(kline["close"])
                current_time = kline["open_time"]

            long_position_value = abs(self.long_position * current_price)
            short_position_value = abs(self.short_position * current_price)

            funding_fee = self.funding_calculator.check_settlement(
                current_time=current_time,
                long_position=self.long_position,
                long_position_value=long_position_value,
                short_position=self.short_position,
                short_position_value=short_position_value,
                funding_rate=self.config.funding_rate
            )

            return funding_fee

        except Exception as e:
            logger.warning(f"[BacktestEngine] 资金费用结算失败: {e}")
            return 0.0

    def _calculate_current_atr(self, strategy) -> None:
        """
        计算当前ATR（Average True Range）值

        ATR用于衡量市场波动率，动态调整止损距离

        Args:
            strategy: 策略对象（包含K线数据）
        """
        try:
            if not hasattr(strategy, 'df_30m') or strategy.df_30m.empty:
                return

            df = strategy.df_30m
            period = self.config.atr_period

            if len(df) < period + 1:
                return

            # 计算True Range (TR)
            high = df['high'].astype(float)
            low = df['low'].astype(float)
            close = df['close'].astype(float)

            prev_close = close.shift(1)

            tr1 = high - low
            tr2 = abs(high - prev_close)
            tr3 = abs(low - prev_close)

            true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

            # 计算ATR（使用EMA平滑）
            atr = true_range.ewm(span=period, adjust=False).mean()

            self.current_atr = atr.iloc[-1]

        except Exception as e:
            logger.warning(f"[BacktestEngine] ATR计算失败: {e}")
            self.current_atr = 0.0

    def _calculate_kelly_position_size(
        self,
        base_investment_ratio: float,
        signal: Dict[str, Any]
    ) -> float:
        """
        使用凯利公式计算最优仓位大小（方案5：动态仓位管理）

        凯利公式：f = (bp - q) / b
        其中：
        - b = 盈亏比（平均盈利/平均亏损）
        - p = 胜率
        - q = 败率 (1-p)

        同时考虑连续亏损保护机制。

        Args:
            base_investment_ratio: 基础投入比例（如0.1表示10%）
            signal: 信号字典（包含盈亏比等信息）

        Returns:
            float: 调整后的仓位比例（限制在5%-25%范围内）
        """
        try:
            # ===== 连续亏损保护 =====
            if self.consecutive_losses >= 3:
                adjusted_ratio = base_investment_ratio * 0.5
                logger.warning(
                    f"[BacktestEngine] ⚠️ 连续亏损{self.consecutive_losses}次，"
                    f"减半仓位至{adjusted_ratio*100:.1f}%"
                )
                return max(0.05, adjusted_ratio)

            # ===== 凯利公式计算 =====
            # 使用历史交易统计（简化版）
            if len(self.trades) < 10:
                # 样本不足时使用基础比例的80%
                return base_investment_ratio * 0.8

            # 计算历史胜率和平均盈亏
            wins = [t for t in self.trades if t.profit > 0]
            losses = [t for t in self.trades if t.profit < 0]

            if not wins or not losses:
                return base_investment_ratio * 0.7

            win_rate = len(wins) / len(self.trades)
            avg_win = abs(sum(t.profit for t in wins) / len(wins))
            avg_loss = abs(sum(t.profit for t in losses) / len(losses))

            if avg_loss == 0:
                return base_investment_ratio

            # 盈亏比
            b = avg_win / avg_loss
            p = win_rate
            q = 1 - p

            # 凯利公式
            kelly = (b * p - q) / b if b > 0 else 0

            # 限制凯利结果在安全范围内（半凯利原则，更保守）
            kelly = max(0.05, min(kelly * 0.5, 0.25))  # 5%-25%

            logger.info(
                f"[BacktestEngine] 📊 凯利公式: "
                f"胜率={p*100:.1f}%, 盈亏比={b:.2f}, "
                f"凯利值={kelly*100:.1f}%"
            )

            return kelly

        except Exception as e:
            logger.warning(f"[BacktestEngine] 凯利公式计算失败: {e}")
            return base_investment_ratio * 0.7

    def _init_long_stop_loss(self, entry_price: float) -> None:
        """
        初始化多单止损位（开仓时调用）

        Args:
            entry_price: 开仓价格
        """
        if self.config.use_atr_stop_loss and self.current_atr > 0:
            atr_stop_distance = self.current_atr * self.config.atr_multiplier
            self.long_initial_stop_loss_price = entry_price - atr_stop_distance
            self.long_trailing_stop_price = self.long_initial_stop_loss_price
            self.long_highest_price = entry_price
            logger.info(
                f"[LONG] 初始化ATR止损: "
                f"入场价={entry_price:.2f}, ATR={self.current_atr:.2f}, "
                f"止损距离={atr_stop_distance:.2f}, 初始止损价={self.long_initial_stop_loss_price:.2f}"
            )
        else:
            self.long_initial_stop_loss_price = entry_price * (1 - self.config.long_stop_loss_ratio)
            self.long_trailing_stop_price = self.long_initial_stop_loss_price
            self.long_highest_price = entry_price
            logger.info(
                f"[LONG] 初始化固定止损: "
                f"入场价={entry_price:.2f}, 止损比例={self.config.long_stop_loss_ratio*100:.1f}%, "
                f"初始止损价={self.long_initial_stop_loss_price:.2f}"
            )

        self.long_is_trailing_active = False

    def _init_short_stop_loss(self, entry_price: float) -> None:
        """
        初始化空单止损位（开仓时调用）

        Args:
            entry_price: 开仓价格
        """
        if self.config.use_atr_stop_loss and self.current_atr > 0:
            atr_stop_distance = self.current_atr * self.config.atr_multiplier
            self.short_initial_stop_loss_price = entry_price + atr_stop_distance
            self.short_trailing_stop_price = self.short_initial_stop_loss_price
            self.short_lowest_price = entry_price
            logger.info(
                f"[SHORT] 初始化ATR止损: "
                f"入场价={entry_price:.2f}, ATR={self.current_atr:.2f}, "
                f"止损距离={atr_stop_distance:.2f}, 初始止损价={self.short_initial_stop_loss_price:.2f}"
            )
        else:
            self.short_initial_stop_loss_price = entry_price * (1 + self.config.short_stop_loss_ratio)
            self.short_trailing_stop_price = self.short_initial_stop_loss_price
            self.short_lowest_price = entry_price
            logger.info(
                f"[SHORT] 初始化固定止损: "
                f"入场价={entry_price:.2f}, 止损比例={self.config.short_stop_loss_ratio*100:.1f}%, "
                f"初始止损价={self.short_initial_stop_loss_price:.2f}"
            )

        self.short_is_trailing_active = False

    def _update_long_trailing_stop(self, current_price: float) -> None:
        """
        更新多单追踪止损位

        当盈利超过激活阈值后，开始追踪止损
        价格创新高 → 上移止损（锁利）

        Args:
            current_price: 当前价格
        """
        if not self.config.use_trailing_stop or self.long_position <= 0 or self.long_avg_price <= 0:
            return

        profit_pct = (current_price - self.long_avg_price) / self.long_avg_price

        if not self.long_is_trailing_active:
            if profit_pct >= self.config.long_trailing_stop_activation:
                self.long_is_trailing_active = True
                logger.info(
                    f"[LONG] ✨ 激活追踪止损! "
                    f"盈利={profit_pct*100:.2f}%, 当前价={current_price:.2f}"
                )

        if self.long_is_trailing_active:
            if current_price > self.long_highest_price:
                self.long_highest_price = current_price
                new_trailing_stop = self.long_highest_price * (
                    1 - self.config.long_trailing_stop_distance
                )
                if new_trailing_stop > self.long_trailing_stop_price:
                    old_stop = self.long_trailing_stop_price
                    self.long_trailing_stop_price = new_trailing_stop
                    logger.debug(
                        f"[LONG] 追踪止损上移: {old_stop:.2f} → {new_trailing_stop:.2f} "
                        f"(最高价={current_price:.2f})"
                    )

    def _update_short_trailing_stop(self, current_price: float) -> None:
        """
        更新空单追踪止损位

        当盈利超过激活阈值后，开始追踪止损
        价格创新低 → 下移止损（锁利）

        Args:
            current_price: 当前价格
        """
        if not self.config.use_trailing_stop or self.short_position <= 0 or self.short_avg_price <= 0:
            return

        profit_pct = (self.short_avg_price - current_price) / self.short_avg_price

        if not self.short_is_trailing_active:
            if profit_pct >= self.config.short_trailing_stop_activation:
                self.short_is_trailing_active = True
                logger.info(
                    f"[SHORT] ✨ 激活追踪止损! "
                    f"盈利={profit_pct*100:.2f}%, 当前价={current_price:.2f}"
                )

        if self.short_is_trailing_active:
            if current_price < self.short_lowest_price:
                self.short_lowest_price = current_price
                new_trailing_stop = self.short_lowest_price * (
                    1 + self.config.short_trailing_stop_distance
                )
                if new_trailing_stop < self.short_trailing_stop_price:
                    old_stop = self.short_trailing_stop_price
                    self.short_trailing_stop_price = new_trailing_stop
                    logger.debug(
                        f"[SHORT] 追踪止损下移(锁利): {old_stop:.2f} → {new_trailing_stop:.2f} "
                        f"(最低价={current_price:.2f})"
                    )

    def _check_long_stop_loss(self, kline) -> None:
        """
        检查多单止损/止盈触发（只平仓，不反向开仓）

        Args:
            kline: 当前K线数据
        """
        if self.long_position <= 0 or self.long_avg_price <= 0:
            return

        if hasattr(kline, 'close'):
            current_price = float(kline.close)
            open_time = kline.open_time
        else:
            current_price = float(kline["close"])
            open_time = kline["open_time"]

        self._update_long_trailing_stop(current_price)

        effective_stop_loss = self.long_trailing_stop_price

        if current_price <= effective_stop_loss:
            profit_pct = (current_price - self.long_avg_price) / self.long_avg_price
            if profit_pct > 0:
                stop_reason = "止盈 (追踪止损锁定利润)"
            else:
                stop_reason = "止损"

            logger.info(
                f"[LONG] {'✅止盈' if profit_pct > 0 else '🛑止损'}: "
                f"盈亏={profit_pct*100:+.2f}%, "
                f"开仓价={self.long_avg_price:.2f} -> 当前价={current_price:.2f}"
            )

            self._close_long(open_time, current_price, f"[LONG] {stop_reason}")

            if profit_pct >= self.config.long_take_profit_ratio:
                logger.info(
                    f"[LONG] 🎯 触发固定止盈: 盈利={profit_pct*100:.2f}% >= {self.config.long_take_profit_ratio*100:.1f}%"
                )

    def _check_short_stop_loss(self, kline) -> None:
        """
        检查空单止损/止盈触发（只平仓，不反向开仓）

        Args:
            kline: 当前K线数据
        """
        if self.short_position <= 0 or self.short_avg_price <= 0:
            return

        if hasattr(kline, 'close'):
            current_price = float(kline.close)
            open_time = kline.open_time
        else:
            current_price = float(kline["close"])
            open_time = kline["open_time"]

        self._update_short_trailing_stop(current_price)

        effective_stop_loss = self.short_trailing_stop_price

        if current_price >= effective_stop_loss:
            profit_pct = (self.short_avg_price - current_price) / self.short_avg_price
            if profit_pct > 0:
                stop_reason = "止盈 (追踪止损锁定利润)"
            else:
                stop_reason = "止损"

            logger.info(
                f"[SHORT] {'✅止盈' if profit_pct > 0 else '🛑止损'}: "
                f"盈亏={profit_pct*100:+.2f}%, "
                f"开仓价={self.short_avg_price:.2f} -> 当前价={current_price:.2f}"
            )

            self._close_short(open_time, current_price, f"[SHORT] {stop_reason}")

            if profit_pct >= self.config.short_take_profit_ratio:
                logger.info(
                    f"[SHORT] 🎯 触发固定止盈: 盈利={profit_pct*100:.2f}% >= {self.config.short_take_profit_ratio*100:.1f}%"
                )

    def _check_stop_loss_take_profit(self, kline) -> None:
        """
        检查止损止盈条件（保留原方法作为备用）

        Args:
            kline: 当前K线数据（可以是namedtuple或pd.Series）
        """
        if self.position <= 0 or self.avg_price <= 0:
            return

        # 支持namedtuple和Series两种格式
        if hasattr(kline, 'close'):
            current_price = float(kline.close)
            open_time = kline.open_time
        else:
            current_price = float(kline["close"])
            open_time = kline["open_time"]

        # 计算盈亏百分比
        profit_pct = (current_price - self.avg_price) / self.avg_price

        # 检查止损
        if profit_pct <= -self.config.stop_loss_pct:
            logger.info("触发止损: %.2f%%", profit_pct * 100)
            self._sell_with_reason(
                open_time,
                current_price,
                "STOP_LOSS"
            )

        # 检查止盈
        elif profit_pct >= self.config.take_profit_pct:
            logger.info("触发止盈: %.2f%%", profit_pct * 100)
            self._sell_with_reason(
                open_time,
                current_price,
                "TAKE_PROFIT"
            )

    def _execute_trade(self, signal: Dict[str, Any], kline) -> None:
        """
        执行交易（支持连续循环交易）

        交易逻辑：
        - BUY信号（底背驰）：判断是否有空单持仓
          * 有空单 -> 平仓空单 + 开多单
          * 无空单 -> 直接开多单
        - SELL信号（顶背驰）：判断是否有多单持仓
          * 有多单 -> 平仓多单 + 开空单
          * 无多单 -> 直接开空单

        配置参数（从self.config读取，可配置）：
        - investment_ratio: 每次投入总金额的比例，默认10%
        - leverage: 杠杆倍数，默认50倍
        - long_stop_loss_multiplier: 多单止损 = 爆仓价格 * 此值，默认120%
        - short_stop_loss_multiplier: 空单止损 = 爆仓价格 * 此值，默认80%

        Args:
            signal: 交易信号
            kline: 当前K线（可以是namedtuple或pd.Series）
        """
        action = signal.get("action")
        
        # 支持namedtuple和Series两种格式
        if hasattr(kline, 'close'):
            market_price = float(kline.close)
            open_time = kline.open_time
        else:
            market_price = float(kline["close"])
            open_time = kline["open_time"]
        reason = signal.get("reason", "")

        # ===== 限价单价格偏差检测（新增）=====
        if self.config.limit_order_enabled:
            target_price = signal.get("target_price")
            if target_price and target_price > 0:
                # 计算价格偏差
                deviation = abs(market_price - target_price) / target_price

                if deviation > self.config.price_deviation_tolerance:
                    # 价格偏差超过容忍度，取消交易
                    cancel_reason = (
                        f"限价单取消: 市场价{market_price:.2f} vs 目标价{target_price:.2f}, "
                        f"偏差={deviation*100:.3}% > 容忍度{self.config.price_deviation_tolerance*100:.1f}%"
                    )
                    logger.warning(f"[BacktestEngine] 🚫 {cancel_reason}")

                    # 记录被取消的订单
                    cancelled_order = LimitOrder(
                        timestamp=open_time,
                        action=action,
                        limit_price=target_price,
                        amount=0,
                        deviation_tolerance=self.config.price_deviation_tolerance,
                        status="cancelled",
                        reason=cancel_reason
                    )
                    self.limit_orders.append(cancelled_order)
                    self.cancelled_orders_count += 1

                    return  # 取消交易，不执行任何操作

                # 价格偏差在可接受范围内，使用较优价格
                if action == "BUY":
                    exec_price = min(market_price, target_price)
                else:  # SELL
                    exec_price = max(market_price, target_price)

                logger.info(
                    f"[BacktestEngine] ✅ 限价单通过: "
                    f"市场价={market_price:.2f}, 目标价={target_price:.2f}, "
                    f"偏差={deviation*100:.3}%, 使用成交价={exec_price:.2f}"
                )

        # 验证信号有效性
        if not self._validate_signal(action, signal):
            return

        # 从配置读取参数（支持自定义配置）
        investment_ratio = self.config.investment_ratio  # 默认10%
        leverage = self.config.leverage  # 默认50倍

        if action == "BUY":
            if self.long_position > 0:
                logger.info(
                    f"[BacktestEngine] 🚫 已持有多单({self.long_position:.4f}个)，"
                    f"忽略新BUY信号 @ ${market_price:.2f} (防止逆势加仓)"
                )
                return

            base_amount = self.balance * investment_ratio
            resonance_ratio = signal.get("position_size_ratio", 0.7)
            kelly_ratio = self._calculate_kelly_position_size(investment_ratio, signal)
            position_size_ratio = resonance_ratio * kelly_ratio
            actual_amount = base_amount * position_size_ratio

            if actual_amount <= 0:
                logger.warning(f"[BacktestEngine] 余额不足或仓位比例为0，无法开多单")
                return

            logger.info(
                f"[BacktestEngine] 仓位调整: "
                f"基础金额${base_amount:.2f} × "
                f"仓位比例{position_size_ratio*100:.0f}% ({signal.get('resonance_level', 'unknown')}) = "
                f"实际投入${actual_amount:.2f}"
            )

            if 'exec_price' in locals() and exec_price > 0:
                final_exec_price = exec_price * (1 + self.config.slippage)
            else:
                final_exec_price = market_price * (1 + self.config.slippage)

            quantity = (actual_amount * leverage) / final_exec_price

            liquidation_price = final_exec_price * (1 - 1/leverage)
            stop_loss_price = liquidation_price * self.config.long_stop_loss_multiplier

            self._open_long(
                open_time,
                final_exec_price,
                actual_amount,
                reason
            )
            logger.info(
                f"[BacktestEngine] 开多单成功: "
                f"实际投入${actual_amount:.2f} (理论${base_amount:.2f}), "
                f"仓位比例{position_size_ratio*100:.0f}%, "
                f"共振级别:{signal.get('resonance_level', 'unknown')}, "
                f"杠杆{leverage}x, "
                f"数量{quantity:.4f}, "
                f"开仓价{final_exec_price:.2f}, "
                f"爆仓价{liquidation_price:.2f}, "
                f"止损价{stop_loss_price:.2f} (爆仓价×{self.config.long_stop_loss_multiplier:.0f}%)"
            )

            self._init_long_stop_loss(final_exec_price)

        elif action == "SELL":
            if self.short_position > 0:
                logger.info(
                    f"[BacktestEngine] 🚫 已持有空单({self.short_position:.4f}个)，"
                    f"忽略新SELL信号 @ ${market_price:.2f} (防止逆势加仓)"
                )
                return

            base_amount = self.balance * investment_ratio
            resonance_ratio = signal.get("position_size_ratio", 0.7)
            kelly_ratio = self._calculate_kelly_position_size(investment_ratio, signal)
            position_size_ratio = resonance_ratio * kelly_ratio
            actual_amount = base_amount * position_size_ratio

            if actual_amount <= 0:
                logger.warning(f"[BacktestEngine] 余额不足或仓位比例为0，无法开空单")
                return

            logger.info(
                f"[BacktestEngine] 仓位调整: "
                f"基础金额${base_amount:.2f} × "
                f"仓位比例{position_size_ratio*100:.0f}% ({signal.get('resonance_level', 'unknown')}) = "
                f"实际投入${actual_amount:.2f}"
            )

            if 'exec_price' in locals() and exec_price > 0:
                final_exec_price = exec_price * (1 - self.config.slippage)
            else:
                final_exec_price = market_price * (1 - self.config.slippage)

            quantity = (actual_amount * leverage) / final_exec_price

            liquidation_price = final_exec_price * (1 + 1/leverage)
            stop_loss_price = liquidation_price * self.config.short_stop_loss_multiplier

            self._open_short(
                open_time,
                market_price,
                self.config.investment_ratio,
                self.config.leverage,
                signal.get("reason", "SELL信号开空")
            )
            logger.info(
                f"[BacktestEngine] 开空单成功: "
                f"实际投入${actual_amount:.2f} (理论${base_amount:.2f}), "
                f"仓位比例{position_size_ratio*100:.0f}%, "
                f"共振级别:{signal.get('resonance_level', 'unknown')}, "
                f"杠杆{leverage}x, "
                f"数量{quantity:.4f}, "
                f"开仓价{final_exec_price:.2f}, "
                f"爆仓价{liquidation_price:.2f}, "
                f"止损价{stop_loss_price:.2f} (爆仓价×{self.config.short_stop_loss_multiplier:.0f}%)"
            )

            self._init_short_stop_loss(final_exec_price)

    def _validate_signal(self, action: str, signal: Dict[str, Any]) -> bool:
        """
        验证交易信号有效性（支持连续循环交易）

        在连续循环交易模式下：
        - BUY信号：允许在有空单时执行（会先平空再开多）
        - SELL信号：允许在有多单时执行（会先平多再开空）
        - 不再阻止反向信号的执行

        Args:
            action: 交易动作
            signal: 交易信号

        Returns:
            信号是否有效
        """
        if action not in ["BUY", "SELL"]:
            return False

        # 连续循环交易模式下，不再阻止以下情况：
        # - BUY信号 + 有多单持仓：可以继续加仓或根据策略逻辑处理
        # - SELL信号 + 有空单持仓：可以继续加仓或根据策略逻辑处理
        # 这些判断由_execute_trade方法内部处理
        
        # 可以添加其他验证逻辑
        return True

    def _open_long_position(
            self,
            timestamp: datetime,
            price: float,
            investment_ratio: float,
            leverage: int,
            reason: str = "反向开多"
    ) -> None:
        """
        开多单（用于连续循环交易的反向开仓）

        Args:
            timestamp: 时间戳
            price: 成交价格
            investment_ratio: 投入比例
            leverage: 杠杆倍数
            reason: 开仓原因
        """
        # 考虑滑点
        exec_price = price * (1 + self.config.slippage)

        # 计算投入金额和数量（使用与主交易逻辑一致的计算方式）
        base_amount = self.balance * investment_ratio

        # 应用默认的仓位调整因子（与_execute_trade保持一致）
        position_size_ratio = 0.7 * 0.5  # 共振系数0.7 × 凯利系数0.5 ≈ 0.35
        actual_amount = base_amount * position_size_ratio

        if actual_amount <= 0 or self.balance < actual_amount:
            logger.warning(f"[BacktestEngine] 余额不足，无法开多单 (余额={self.balance:.2f}, 需要={actual_amount:.2f})")
            return

        quantity = (actual_amount * leverage) / exec_price

        # 计算止损价格
        liquidation_price = exec_price * (1 - 1/leverage)
        stop_loss_price = liquidation_price * self.config.long_stop_loss_multiplier

        # 执行买入
        self._buy_with_reason(
            timestamp,
            exec_price,
            actual_amount,
            reason
        )

        logger.info(
            f"[BacktestEngine] 反向开多单成功: "
            f"投入${actual_amount:.2f}, 杠杆{leverage}x, "
            f"数量{quantity:.4f}, 价{exec_price:.2f}, "
            f"止损{stop_loss_price:.2f}"
        )

        # 初始化追踪止损
        self._initialize_stop_loss(exec_price, "long")

    def _open_short_position(
            self,
            timestamp: datetime,
            price: float,
            investment_ratio: float,
            leverage: int,
            reason: str = "反向开空"
    ) -> None:
        """
        开空单（用于连续循环交易的反向开仓）

        Args:
            timestamp: 时间戳
            price: 成交价格
            investment_ratio: 投入比例
            leverage: 杠杆倍数
            reason: 开仓原因
        """
        # 考虑滑点（做空时价格向下）
        exec_price = price * (1 - self.config.slippage)

        # 计算投入金额和数量（使用与主交易逻辑一致的计算方式）
        base_amount = self.balance * investment_ratio

        # 应用默认的仓位调整因子（与_execute_trade保持一致）
        position_size_ratio = 0.7 * 0.5  # 共振系数0.7 × 凯利系数0.5 ≈ 0.35
        actual_amount = base_amount * position_size_ratio

        if actual_amount <= 0 or self.balance < actual_amount:
            logger.warning(f"[BacktestEngine] 余额不足，无法开空单 (余额={self.balance:.2f}, 需要={actual_amount:.2f})")
            return

        # 执行开空操作（直接修改状态，不调用_sell_with_reason避免检查）
        sell_amount = actual_amount / exec_price * (1 - self.config.commission)

        # 计算止损价格
        liquidation_price = exec_price * (1 + 1/leverage)
        stop_loss_price = liquidation_price * self.config.short_stop_loss_multiplier

        # 记录交易（空单用负数表示）
        trade = TradeRecord(
            timestamp=timestamp,
            action="SELL",  # 开空也记录为SELL
            price=exec_price,
            amount=sell_amount,
            balance=self.balance - actual_amount,
            position=-sell_amount,  # 负数表示空单
            equity=self.balance - actual_amount + (-sell_amount) * exec_price,
            reason=reason
        )

        # 更新状态
        self.position = -sell_amount  # 设置为负数表示空单
        self.avg_price = exec_price
        self.balance -= actual_amount
        self.trades.append(trade)

        logger.info(
            f"[BacktestEngine] 反向开空单成功: "
            f"投入${actual_amount:.2f}, 杠杆{leverage}x, "
            f"数量{sell_amount:.4f}, "
            f"价{exec_price:.2f}, 止损{stop_loss_price:.2f}"
        )

        # 初始化追踪止损
        self._initialize_stop_loss(exec_price, "short")

    def _buy_with_reason(
            self,
            timestamp: datetime,
            price: float,
            amount: float,
            reason: str
    ) -> None:
        """
        带原因的买入

        Args:
            timestamp: 时间戳
            price: 价格
            amount: 金额
            reason: 原因
        """
        if amount <= 0 or price <= 0:
            return

        # 计算可买入数量
        buy_amount = amount / price * (1 - self.config.commission)
        if buy_amount <= 0:
            return

        # 记录交易
        trade = TradeRecord(
            timestamp=timestamp,
            action="BUY",
            price=price,
            amount=buy_amount,
            balance=self.balance - amount,
            position=self.position + buy_amount,
            equity=self.balance - amount + (self.position + buy_amount) * price,
            reason=reason
        )

        # 更新状态
        if self.position == 0:
            self.avg_price = price
        else:
            total_cost = self.position * self.avg_price + buy_amount * price
            self.avg_price = total_cost / (self.position + buy_amount)

        self.position += buy_amount
        self.balance -= amount
        self.trades.append(trade)

        logger.info("买入 %.4f @ %.2f, 原因: %s", buy_amount, price, reason)

    def _close_short_position(
            self,
            timestamp: datetime,
            price: float,
            reason: str
    ) -> Optional[TradeRecord]:
        """
        平空单（买入平仓），正确计算空单盈亏

        空单盈亏公式:
          cost = |position| * avg_price  （开空时"借入"的价值）
          proceeds = |position| * price   （平空时"还回"的价值）
          profit = cost - proceeds        （正数=盈利，负数=亏损）
          profit_pct = (avg_price - price) / avg_price * 100

        Args:
            timestamp: 时间戳
            price: 平仓价格
            reason: 平仓原因

        Returns:
            TradeRecord 或 None（如果无空单可平）
        """
        if self.position >= 0 or price <= 0:
            return None

        abs_qty = abs(self.position)
        proceeds = abs_qty * price * (1 - self.config.commission)  # 买入平仓还回价值
        cost = abs_qty * self.avg_price  # 开空时借入价值
        profit = cost - proceeds  # 正数=盈利(价格跌了)，负数=亏损(价格涨了)
        profit_pct = ((self.avg_price - price) / self.avg_price * 100) if self.avg_price > 0 else 0.0

        # 更新连续亏损记录
        if profit < 0:
            self.consecutive_losses += 1
            self.max_consecutive_losses = max(
                self.max_consecutive_losses, self.consecutive_losses
            )
        else:
            self.consecutive_losses = 0

        trade = TradeRecord(
            timestamp=timestamp,
            action="BUY",  # 平空 = 买入
            price=price,
            amount=abs_qty,
            balance=self.balance + proceeds,
            position=0.0,
            equity=self.balance + proceeds,
            profit=profit,
            profit_pct=profit_pct,
            reason=reason
        )

        self.balance += proceeds
        self.position = 0.0
        self.avg_price = 0.0
        self.trades.append(trade)

        logger.info(
            f"[BacktestEngine] 平空单: {abs_qty:.4f} @ {price:.2f}, "
            f"利润: {profit:+.2f} ({profit_pct:+.2f}%), 原因: {reason}"
        )

        return trade

    def _sell_with_reason(self, timestamp: datetime, price: float, reason: str) -> None:
        """
        带原因的卖出

        Args:
            timestamp: 时间戳
            price: 价格
            reason: 原因
        """
        if self.position <= 0 or price <= 0:
            return

        # 计算卖出收益
        amount = self.position
        proceeds = amount * price * (1 - self.config.commission)

        # 计算利润
        cost = self.position * self.avg_price
        profit = proceeds - cost
        profit_pct = (profit / cost * 100) if cost > 0 else 0.0

        # 更新连续亏损记录
        if profit < 0:
            self.consecutive_losses += 1
            self.max_consecutive_losses = max(
                self.max_consecutive_losses,
                self.consecutive_losses
            )
        else:
            self.consecutive_losses = 0

        # 记录交易
        trade = TradeRecord(
            timestamp=timestamp,
            action="SELL",
            price=price,
            amount=amount,
            balance=self.balance + proceeds,
            position=0.0,
            equity=self.balance + proceeds,
            profit=profit,
            profit_pct=profit_pct,
            reason=reason
        )

        # 更新状态
        self.balance += proceeds
        self.position = 0.0
        self.avg_price = 0.0
        self.trades.append(trade)

        logger.info(
            "卖出 %.4f @ %.2f, 利润: %.2f (%.2f%%), 原因: %s",
            amount, price, profit, profit_pct, reason
        )

    def _record_equity(self, kline) -> None:
        """
        记录权益

        Args:
            kline: 当前K线（可以是namedtuple或pd.Series）
        """
        # 支持namedtuple和Series两种格式
        if hasattr(kline, 'close'):
            current_price = float(kline.close)
        else:
            current_price = float(kline["close"])

        # 计算持仓价值（支持多空双向）
        if self.position > 0:  # 多头持仓
            position_value = self.position * current_price
        elif self.position < 0:  # 空头持仓
            # 空头浮动盈亏 = (开仓价 - 当前价) × 数量
            position_value = (self.avg_price - current_price) * abs(self.position)
        else:  # 无持仓
            position_value = 0.0

        equity = self.balance + position_value

        # 记录时间戳和权益
        if hasattr(kline, 'open_time'):
            self.timestamps.append(kline.open_time)
        else:
            self.timestamps.append(pd.Timestamp.now())

        self.equity_curve.append(equity)

        # 更新最大回撤
        self.max_equity = max(self.max_equity, equity)
        if self.max_equity > 0:
            drawdown = (self.max_equity - equity) / self.max_equity * 100
            self.current_drawdown = drawdown
            self.max_drawdown = max(self.max_drawdown, drawdown)

    def _prepare_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        数据预处理

        Args:
            df: 原始数据

        Returns:
            处理后的数据
        """
        if df.empty:
            return df

        prepared = df.copy()

        # 转换时间列
        time_columns = ['open_time', 'close_time', 'timestamp']
        for col in time_columns:
            if col in prepared.columns:
                prepared[col] = pd.to_datetime(prepared[col], errors='coerce')

        # 转换数值列
        numeric_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_columns:
            if col in prepared.columns:
                prepared[col] = pd.to_numeric(prepared[col], errors='coerce')

        # 删除全为NaN的行
        prepared = prepared.dropna(subset=['open', 'high', 'low', 'close'], how='all')

        # 按时间排序
        if 'open_time' in prepared.columns:
            prepared = prepared.sort_values('open_time').reset_index(drop=True)

        return prepared

    def _calculate_performance(self) -> Dict[str, Any]:
        """
        计算绩效指标

        Returns:
            绩效指标字典
        """
        if not self.equity_curve:
            logger.warning("权益曲线为空，无法计算绩效")
            return {}

        # 基本指标
        final_equity = float(self.equity_curve[-1])
        net_profit = final_equity - self.config.initial_balance
        total_return = (net_profit / self.config.initial_balance * 100) if self.config.initial_balance > 0 else 0.0

        # 计算回撤
        equity_array = np.array(self.equity_curve, dtype=float)
        running_max = np.maximum.accumulate(equity_array)
        drawdowns = (running_max - equity_array) / running_max * 100
        drawdowns = np.where(np.isnan(drawdowns), 0, drawdowns)
        max_drawdown = float(np.max(drawdowns))

        # 构建已平仓交易
        closed_trades = self._build_closed_trades()

        # 计算交易统计
        if closed_trades:
            profits = [trade.profit for trade in closed_trades]
            returns_pct = [trade.return_pct for trade in closed_trades]

            winning_trades = [p for p in profits if p > 0]
            losing_trades = [p for p in profits if p <= 0]

            win_rate = len(winning_trades) / len(closed_trades) * 100
            profit_factor = (
                abs(sum(winning_trades) / sum(losing_trades))
                if sum(losing_trades) != 0 else 0.0
            )

            avg_profit = float(np.mean(profits))
            avg_win = float(np.mean(winning_trades)) if winning_trades else 0.0
            avg_loss = float(np.mean(losing_trades)) if losing_trades else 0.0
            avg_return_pct = float(np.mean(returns_pct))

            holding_hours = [trade.holding_hours for trade in closed_trades]
            avg_holding_hours = float(np.mean(holding_hours))

            # 计算夏普比率
            if len(self.equity_curve) > 1:
                returns = np.diff(equity_array) / equity_array[:-1]
                sharpe_ratio = self._calculate_sharpe_ratio(returns)
            else:
                sharpe_ratio = 0.0
        else:
            win_rate = 0.0
            profit_factor = 0.0
            avg_profit = 0.0
            avg_win = 0.0
            avg_loss = 0.0
            avg_return_pct = 0.0
            avg_holding_hours = 0.0
            sharpe_ratio = 0.0

        # 汇总结果
        results = {
            "initial_balance": self.config.initial_balance,
            "final_equity": final_equity,
            "net_profit": net_profit,
            "total_return_pct": total_return,
            "max_drawdown_pct": max_drawdown,
            "current_drawdown_pct": self.current_drawdown,
            "total_trades": len(self.trades),
            "closed_trades": len(closed_trades),
            "win_rate_pct": win_rate,
            "profit_factor": profit_factor,
            "avg_trade_profit": avg_profit,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "avg_return_pct": avg_return_pct,
            "avg_holding_hours": avg_holding_hours,
            "sharpe_ratio": sharpe_ratio,
            "max_consecutive_losses": self.max_consecutive_losses,

            # 限价单统计（新增）
            "cancelled_orders_count": self.cancelled_orders_count,
            "limit_order_enabled": self.config.limit_order_enabled,
            "price_deviation_tolerance": self.config.price_deviation_tolerance,

            "final_balance": self.balance,
            "final_position": self.position,
            "avg_position_price": self.avg_price,
            "timestamps": self.timestamps,
            "equity_curve": self.equity_curve,
        }

        # 添加资金费用汇总（如果启用）
        if self.config.enable_funding_fee:
            funding_summary = self.funding_calculator.get_summary()
            results["funding_fee_summary"] = {
                "total_paid": funding_summary["total_paid"],
                "total_received": funding_summary["total_received"],
                "net_fee": funding_summary["net_fee"],
                "settlement_count": funding_summary["settlement_count"]
            }

        # 验证结果
        if not self._validate_results(results):
            logger.warning("绩效指标计算可能存在问题")

        return results

    def _calculate_sharpe_ratio(self, returns: np.ndarray) -> float:
        """
        计算夏普比率

        Args:
            returns: 收益率序列

        Returns:
            夏普比率
        """
        if len(returns) == 0 or np.std(returns) == 0:
            return 0.0

        # 年化因子：假设每天有6.5小时交易时间，一年有252个交易日
        # 如果数据是5分钟K线，每根K线间隔5分钟
        hourly_returns = returns
        annual_factor = np.sqrt(6.5 * 252)  # 假设每小时计算一次收益

        sharpe = np.mean(hourly_returns) / np.std(hourly_returns) * annual_factor
        return float(sharpe)

    def _build_closed_trades(self) -> List[ClosedTrade]:
        """
        构建已平仓交易列表

        Returns:
            已平仓交易列表
        """
        closed_trades = []

        # 按交易对分组
        for i in range(0, len(self.trades) - 1, 2):
            if i + 1 >= len(self.trades):
                break

            buy_trade = self.trades[i]
            sell_trade = self.trades[i + 1]

            if buy_trade.action != "BUY" or sell_trade.action != "SELL":
                continue

            # 计算持仓时间
            holding_hours = (
                    (sell_trade.timestamp - buy_trade.timestamp).total_seconds() / 3600
            )

            # 计算收益
            entry_value = buy_trade.amount * buy_trade.price
            exit_value = sell_trade.amount * sell_trade.price
            profit = exit_value - entry_value
            return_pct = (profit / entry_value * 100) if entry_value > 0 else 0.0

            # 检查是否触发止损止盈
            stop_loss_hit = "STOP_LOSS" in sell_trade.reason
            take_profit_hit = "TAKE_PROFIT" in sell_trade.reason

            closed_trade = ClosedTrade(
                entry_time=buy_trade.timestamp,
                exit_time=sell_trade.timestamp,
                entry_price=buy_trade.price,
                exit_price=sell_trade.price,
                amount=buy_trade.amount,
                profit=profit,
                return_pct=return_pct,
                holding_hours=holding_hours,
                stop_loss_hit=stop_loss_hit,
                take_profit_hit=take_profit_hit
            )

            closed_trades.append(closed_trade)

        return closed_trades

    def _validate_results(self, results: Dict[str, Any]) -> bool:
        """
        验证回测结果的合理性

        Args:
            results: 回测结果

        Returns:
            结果是否合理
        """
        for key, value in results.items():
            if isinstance(value, float):
                if np.isnan(value) or np.isinf(value):
                    logger.error("结果 %s 包含无效值: %s", key, value)
                    return False

                # 检查回撤是否为负数
                if "drawdown" in key.lower() and value < 0:
                    logger.warning("回撤值为负数: %s = %.2f", key, value)

        # 检查基本逻辑
        if results.get("final_equity", 0) < 0:
            logger.error("最终权益为负数: %.2f", results["final_equity"])
            return False

        if results.get("total_return_pct", 0) < -100:
            logger.error("总收益率小于-100%%: %.2f%%", results["total_return_pct"])
            return False

        return True

    def _plot_results(
            self,
            kline_data: pd.DataFrame,
            strategy: ChanStrategy,
            filename: str
    ) -> None:
        """
        生成图表

        Args:
            kline_data: K线数据
            strategy: 交易策略
            filename: 保存文件名
        """
        try:
            # 准备交易信号
            signals = []
            for trade in self.trades:
                if trade.action in ["BUY", "SELL"]:
                    signals.append({
                        "action": trade.action,
                        "price": trade.price,
                        "timestamp": trade.timestamp,
                        "reason": trade.reason
                    })

            # 创建绘图器
            plotter = ChanPlotter(
                kline_data=kline_data,
                fractals=strategy.fractals if hasattr(strategy, 'fractals') else [],
                pens=strategy.pens if hasattr(strategy, 'pens') else [],
                segments=strategy.segments if hasattr(strategy, 'segments') else [],
                signals=signals,
                strategy=strategy  # 传入策略对象以支持均线绘制和共振标注
            )

            # 绘制图表
            plotter.plot()
            plotter.save(filename)
            logger.info("图表已保存到: %s", filename)

        except Exception as e:
            logger.error("生成图表失败: %s", e, exc_info=True)

    def save_results(self, results: Dict[str, Any], filename: str = "backtest_results.json") -> None:
        """
        保存回测结果

        Args:
            results: 回测结果
            filename: 文件名
        """
        try:
            # 转换时间戳
            serializable = {}
            for key, value in results.items():
                if key in ["timestamps"] and isinstance(value, list):
                    serializable[key] = [
                        ts.isoformat() if hasattr(ts, 'isoformat') else str(ts)
                        for ts in value
                    ]
                elif hasattr(value, 'isoformat'):  # 处理datetime
                    serializable[key] = value.isoformat()
                else:
                    serializable[key] = value

            # 保存交易记录
            serializable["trades"] = [
                {k: (v.isoformat() if hasattr(v, 'isoformat') else v)
                 for k, v in asdict(trade).items()}
                for trade in self.trades
            ]

            # 保存文件
            file_path = self.data_dir / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(serializable, f, indent=2, ensure_ascii=False, default=str)

            logger.info("回测结果已保存到: %s", file_path)

        except Exception as e:
            logger.error("保存回测结果失败: %s", e)

    def print_summary(self, results: Dict[str, Any]) -> None:
        """
        打印回测摘要

        Args:
            results: 回测结果
        """
        if not results:
            print("无回测结果")
            return

        print("\n" + "=" * 60)
        print("回测结果摘要")
        print("=" * 60)

        print(f"\n📈 收益表现:")
        print(f"   初始资金: ${results.get('initial_balance', 0):.2f}")
        print(f"   最终权益: ${results.get('final_equity', 0):.2f}")
        print(f"   净利润: ${results.get('net_profit', 0):.2f}")
        print(f"   总收益率: {results.get('total_return_pct', 0):.2f}%")

        print(f"\n📉 风险指标:")
        print(f"   最大回撤: {results.get('max_drawdown_pct', 0):.2f}%")
        print(f"   当前回撤: {results.get('current_drawdown_pct', 0):.2f}%")
        print(f"   夏普比率: {results.get('sharpe_ratio', 0):.2f}")

        print(f"\n📊 交易统计:")
        print(f"   总交易次数: {results.get('total_trades', 0)}")
        print(f"   平仓交易数: {results.get('closed_trades', 0)}")
        print(f"   胜率: {results.get('win_rate_pct', 0):.2f}%")
        print(f"   盈亏比: {results.get('profit_factor', 0):.2f}")
        print(f"   平均持仓时间: {results.get('avg_holding_hours', 0):.2f}小时")

        print(f"\n💰 资金状态:")
        print(f"   当前余额: ${results.get('final_balance', 0):.2f}")
        print(f"   当前持仓: {results.get('final_position', 0):.4f}")
        if results.get('final_position', 0) > 0:
            print(f"   持仓均价: ${results.get('avg_position_price', 0):.2f}")

        # 打印限价单统计（如果启用）
        if results.get('limit_order_enabled', False):
            print(f"\n🎯 限价单统计:")
            print(f"   限价单模式: {'已启用' if results.get('limit_order_enabled') else '未启用'}")
            print(f"   价格偏差容忍度: {results.get('price_deviation_tolerance', 0)*100:.2f}%")
            print(f"   被取消的订单数: {results.get('cancelled_orders_count', 0)}")
            cancellation_rate = (
                results.get('cancelled_orders_count', 0) /
                (results.get('total_trades', 0) + results.get('cancelled_orders_count', 0)) * 100
                if (results.get('total_trades', 0) + results.get('cancelled_orders_count', 0)) > 0
                else 0
            )
            print(f"   订单取消率: {cancellation_rate:.2f}%")

        # 打印资金费用汇总（如果启用）
        if "funding_fee_summary" in results:
            funding = results["funding_fee_summary"]
            print(f"\n💸 资金费用（合约交易）:")
            print(f"   累计支付: ${funding.get('total_paid', 0):.4f} USDT")
            print(f"   累计收取: ${funding.get('total_received', 0):.4f} USDT")
            print(f"   净费用: ${funding.get('net_fee', 0):.4f} USDT")
            print(f"   结算次数: {funding.get('settlement_count', 0)} 次")

        print("\n" + "=" * 60)


def main():
    """
    主函数 - 回测示例
    """
    # 创建配置
    config = BacktestConfig(
        initial_balance=10000.0,
        slippage=0.0005,
        max_position_ratio=0.5,  # 每次最多使用50%资金
        stop_loss_pct=0.05,  # 5%止损
        take_profit_pct=0.1,  # 10%止盈
        plot_enabled=True,
        save_results=True,
        progress_bar=True
    )

    # 创建回测引擎
    engine = BacktestEngine(config)

    # 加载数据
    print("正在加载数据...")
    data = engine.load_data(
        symbol="BTCUSDT",
        interval="5m",
        start_date="2024-01-01",
        end_date="2024-12-31"
    )

    if not data or "5m" not in data or data["5m"].empty:
        print("数据加载失败，请检查数据文件")
        return

    # 创建策略
    from trading_system.strategies.chan_strategy import ChanStrategy
    strategy = ChanStrategy(use_binance_client=False)

    # 运行回测
    print("开始回测...")
    results = engine.run_backtest(
        data=data,
        strategy=strategy,
        interval="5m",
        plot_filename="backtest_result.png"
    )

    # 打印结果
    if results:
        engine.print_summary(results)

        # 保存详细结果
        engine.save_results(results, "detailed_results.json")
    else:
        print("回测失败，无结果")


if __name__ == "__main__":
    main()