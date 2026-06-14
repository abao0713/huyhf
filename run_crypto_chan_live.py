"""
Crypto_Chan_4H_Master_v1 策略实时执行脚本

基于缠论 4H/1H/15M 多周期分析，连接 Binance 实盘进行交易。
配置从 .env 文件自动加载，支持钉钉消息通知和守护进程模式。

使用方法:
    # 默认守护进程模式（后台运行，自动重启）
    python run_crypto_chan_live.py
    
    # 前台运行模式
    python run_crypto_chan_live.py --foreground
    
    # 查看守护进程状态
    python run_crypto_chan_live.py --status
    
    # 停止守护进程
    python run_crypto_chan_live.py --stop
"""

import argparse
import asyncio
import atexit
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

import pandas as pd
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 加载环境变量
load_dotenv(PROJECT_ROOT / ".env")

from trading_system.strategies.mtf_fractal_strategy import (
    StrategyConfigRoot,
    CryptoChan4HMasterStrategy,
    CryptoChan4HBacktestEngine,
    TradeRecordV2,
    CCXTDataProvider,
)
from trading_system.binance.client import BinanceRestClient
from trading_system.notify.dingtalk import DingTalkNotifier

# 日志配置
LOG_DIR = PROJECT_ROOT / "logs"
PID_FILE = PROJECT_ROOT / "run_crypto_chan_live.pid"
LOG_FILE = LOG_DIR / "crypto_chan_live.log"

# 创建日志目录
LOG_DIR.mkdir(exist_ok=True)

# 配置日志同时输出到文件和控制台
file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

for _mod in ["trading_system.strategies.chan_strategy",
             "trading_system.strategies.mtf_fractal_strategy",
             "trading_system.strategies.chan_first_buy_strategy"]:
    logging.getLogger(_mod).setLevel(logging.WARNING)

_logger = logging.getLogger("crypto_chan_live")
_logger.setLevel(logging.INFO)
_logger.addHandler(file_handler)
_logger.addHandler(console_handler)

DEFAULT_DATA_DIR = PROJECT_ROOT / "trading_system" / "data" / "binance_history"
DEFAULT_RESULTS_FILE = PROJECT_ROOT / "trading_system" / "data" / "binance_history" / "live_results.json"

# 全局变量用于守护进程控制
_daemon_running = True
_executor_instance = None


def mask_secret(value: str, visible_prefix: int = 4, visible_suffix: int = 4) -> str:
    """对敏感信息进行脱敏处理

    Args:
        value: 原始字符串
        visible_prefix: 保留前缀字符数
        visible_suffix: 保留后缀字符数

    Returns:
        脱敏后的字符串，如 "abcd****efgh"
    """
    if not value:
        return "***"
    if len(value) <= visible_prefix + visible_suffix:
        return "***"
    return f"{value[:visible_prefix]}{'*' * (len(value) - visible_prefix - visible_suffix)}{value[-visible_suffix:]}"


def daemon_get_pid() -> Optional[int]:
    """获取守护进程PID"""
    if PID_FILE.exists():
        try:
            return int(PID_FILE.read_text().strip())
        except:
            return None
    return None


def daemon_is_running() -> bool:
    """检查守护进程是否正在运行"""
    pid = daemon_get_pid()
    if pid is None:
        return False
    try:
        # Windows上使用tasklist检查进程
        import subprocess
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True, text=True, encoding='utf-8', errors='ignore'
        )
        lines = result.stdout.split('\n')
        # 检查输出中是否有该PID（排除标题行和空行）
        for line in lines:
            line = line.strip()
            if line and str(pid) in line and 'PID' not in line:
                return True
        return False
    except Exception as e:
        _logger.warning(f"检查进程状态失败: {e}")
        return False


def daemon_start(script_path: str, args: List[str]) -> bool:
    """启动守护进程"""
    if daemon_is_running():
        pid = daemon_get_pid()
        _logger.error(f"守护进程已在运行中 (PID: {pid})")
        return False
    
    try:
        import subprocess
        import threading
        
        # 直接使用 Popen 启动，设置创建新进程组
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        
        # 启动进程
        process = subprocess.Popen(
            [sys.executable, script_path] + args,
            startupinfo=startupinfo,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(PROJECT_ROOT),
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP') else 0
        )
        
        # 等待进程启动
        time.sleep(2)
        
        # 检查是否成功启动
        if process.poll() is None:
            # 进程仍在运行，写入 PID
            PID_FILE.write_text(str(process.pid))
            _logger.info(f"守护进程已启动 (PID: {process.pid})")
            print(f"守护进程已启动 (PID: {process.pid})")
            print(f"日志文件: {LOG_FILE}")
            return True
        else:
            _logger.error(f"守护进程启动失败，退出码: {process.returncode}")
            return False
    except Exception as e:
        _logger.error(f"启动守护进程失败: {e}")
        return False


def daemon_stop() -> bool:
    """停止守护进程"""
    pid = daemon_get_pid()
    if pid is None or not daemon_is_running():
        _logger.info("守护进程未运行")
        print("守护进程未运行")
        return True
    
    try:
        import subprocess
        # Windows上使用taskkill终止进程
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], 
                      capture_output=True)
        time.sleep(1)
        
        if not daemon_is_running():
            try:
                PID_FILE.unlink()
            except FileNotFoundError:
                pass
            _logger.info("守护进程已停止")
            print("守护进程已停止")
            return True
        else:
            _logger.error("守护进程停止失败")
            return False
    except Exception as e:
        _logger.error(f"停止守护进程失败: {e}")
        return False


def daemon_status() -> None:
    """显示守护进程状态"""
    pid = daemon_get_pid()
    if pid and daemon_is_running():
        print(f"守护进程正在运行 (PID: {pid})")
        print(f"日志文件: {LOG_FILE}")
        # 读取最后几行日志
        if LOG_FILE.exists():
            try:
                lines = LOG_FILE.read_text(encoding='utf-8').splitlines()
                print("\n最近日志:")
                for line in lines[-10:]:
                    print(f"  {line}")
            except:
                pass
    else:
        print("守护进程未运行")
        if PID_FILE.exists():
            PID_FILE.unlink()


def signal_handler(signum, frame):
    """信号处理器"""
    global _daemon_running
    _logger.info(f"收到退出信号 (信号号: {signum})，正在停止...")
    _daemon_running = False
    
    if _executor_instance:
        _executor_instance._running = False


def cleanup():
    """清理函数"""
    try:
        PID_FILE.unlink()
    except FileNotFoundError:
        pass
    _logger.info("清理完成")


def build_config(symbol: str) -> StrategyConfigRoot:
    """构建策略配置（与回测共用）"""
    json_config = {
        "strategy_metadata": {
            "name": "Crypto_Chan_4H_Master_v1",
            "version": "1.0",
            "description": "基于缠论4H/1H/15M级别的交易系统，支持双向持仓与动态对冲。",
            "base_currency": "USDC",
            "trading_pairs": [symbol],
            "timeframe_config": {
                "trend_level": "4h",
                "structure_level": "1h",
                "entry_level": "15m"
            }
        },
        "global_filters": {
            "daily_cutoff": "0:00",
            "weekend_mode": {
                "enabled": True,
                "days": ["Sat", "Sun"],
                "action": "reduce_position_to_50_percent_and_no_breakout_trades"
            },
            "funding_rate_fuse": {
                "threshold": 0.001,
                "condition_gt": "disable_long_entry_on_3rd_buy",
                "condition_lt": "disable_short_entry_on_3rd_sell"
            }
        },
        "indicators": {
            "atr": {"period": 14, "source": "4h", "multiplier_stop_loss": 1.5, "multiplier_take_profit": 3.0},
            "macd": {"fast": 12, "slow": 26, "signal": 9}
        },
        "trade_logic": {
            "long_setup": {
                "type_2_buy": {
                    "level": "4h",
                    "condition": "Price retraces to the first 4h central pivot after 1st buy, not breaking the 1st buy low.",
                    "confirmation_1h": "MACD green bars shrink vs previous drop; Bottom fractal confirmed.",
                    "entry_15m": "Break of 15m downtrend line or 15m bottom fractal close.",
                    "stop_loss": "Entry_price - (ATR_4h * 1.5)"
                },
                "type_2b_like_buy": {
                    "level": "4h",
                    "condition": "Price breaks above 4h central pivot and retests the pivot high as support.",
                    "confirmation_1h": "Volume decreases on pullback; MACD histogram does not make new lows.",
                    "entry_15m": "15m small reversal (bottom fractal) at the pivot zone.",
                    "stop_loss": "Entry_price - (ATR_4h * 1.5)"
                }
            },
            "short_setup": {
                "type_2_sell": {
                    "level": "4h",
                    "condition": "Price rallies to the first 4h central pivot after 1st sell, not breaking the 1st sell high.",
                    "confirmation_1h": "MACD red bars shrink vs previous rise; Top fractal confirmed.",
                    "entry_15m": "Break of 15m uptrend line or 15m top fractal close.",
                    "stop_loss": "Entry_price + (ATR_4h * 1.5)"
                }
            }
        },
        "position_management": {
            "hedging_rules": {
                "trend_mode": {"main_position": "100%", "hedge_position": "0-30%", "trigger": "1h divergence against 4h trend"},
                "range_mode": {"upper_bound_short": "50%", "lower_bound_long": "50%", "net_exposure": "0%",
                               "exit_rule": "Close opposite side if price breaks 4h central pivot."}
            },
            "sizing": {"method": "atr_based", "risk_per_trade_percent": 1.0,
                       "calculation": "Position_Size = (Account_Equity * Risk%) / (ATR_4h * 1.5)"},
            "position_sizing": {
                "capital_usage_ratio": 0.6,
                "first_entry_pct": 0.4,
                "add_entry_pcts": [0.25, 0.18, 0.10],
                "max_add_count": 3
            }
        },
        "execution_directives": [
            {"id": "RULE_001", "priority": 1, "condition": "Daily_Trend == UP AND 4h_Type_2B_Confirmed",
             "action": "OPEN_LONG_MAIN_POSITION", "params": {"size": "full", "sl": "atr_1.5"}},
            {"id": "RULE_002", "priority": 1, "condition": "Daily_Trend == DOWN AND 4h_Type_2S_Confirmed",
             "action": "OPEN_SHORT_MAIN_POSITION", "params": {"size": "full", "sl": "atr_1.5"}},
            {"id": "RULE_003", "priority": 2, "condition": "Funding_Rate > 0.001 AND Action == OPEN_LONG",
             "action": "REJECT_ENTRY", "params": {"reason": "Funding rate too high, risk of long squeeze."}},
            {"id": "RULE_004", "priority": 3, "condition": "Price_Breaks_4h_Pivot_Upwards AND Range_Mode == TRUE",
             "action": "CLOSE_SHORT_AND_OPEN_LONG", "params": {"transition": "from_range_to_trend"}},
            {"id": "RULE_005", "priority": 4, "condition": "Weekday IN ['Sat', 'Sun']",
             "action": "ADJUST_LEVERAGE_AND_SIZE", "params": {"max_leverage": 5, "size_multiplier": 0.5}}
        ]
    }
    return StrategyConfigRoot.from_dict(json_config)


def load_csv_data(symbol: str, data_dir: Path, start_date: Optional[str] = None,
                  end_date: Optional[str] = None) -> dict:
    """从本地 CSV 文件加载多周期数据"""
    symbol_clean = symbol.replace("/", "")
    timeframes = {
        "4h": data_dir / f"{symbol_clean}_4h.csv",
        "1h": data_dir / f"{symbol_clean}_1h.csv",
        "15m": data_dir / f"{symbol_clean}_15m.csv",
        "1d": data_dir / f"{symbol_clean}_1d.csv",
    }
    dfs = {}
    for tf, fp in timeframes.items():
        if fp.exists():
            df = pd.read_csv(fp)
            if "open_time" in df.columns:
                df["open_time"] = pd.to_datetime(df["open_time"])
            dfs[tf] = df
            _logger.info(f"加载 {tf}: {len(df)} 行 from {fp}")
        else:
            _logger.warning(f"文件不存在: {fp}")
    if start_date and end_date:
        for tf in dfs:
            if "open_time" in dfs[tf].columns:
                mask = (dfs[tf]["open_time"] >= pd.Timestamp(start_date)) & \
                       (dfs[tf]["open_time"] <= pd.Timestamp(end_date) + pd.Timedelta(days=1))
                dfs[tf] = dfs[tf][mask].reset_index(drop=True)
    return dfs


def load_ccxt_data(symbol: str, days: int = 90) -> dict:
    """通过 CCXT 获取数据"""
    provider = CCXTDataProvider("binance")
    since_ms = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    dfs = {}
    for tf in ["4h", "1h", "15m", "1d"]:
        df = provider.fetch_ohlcv(symbol, timeframe=tf, limit=1000, since_ms=since_ms)
        dfs[tf] = df
    return dfs


class CryptoChanLiveExecutor:
    """多周期缠论策略实时执行器

    连接 Binance 实盘进行交易，支持钉钉消息通知。
    """

    def __init__(
        self,
        config: StrategyConfigRoot,
        initial_capital: float = 10000.0,
        commission: float = 0.00018,
        api_key: str = None,
        secret_key: str = None,
        use_realtime: bool = True,
        dingtalk_token: str = None,
        dingtalk_secret: str = None,
    ):
        self.config = config
        self.initial_capital = initial_capital
        self.commission = commission
        self.symbol = config.metadata.trading_pairs[0] if config.metadata.trading_pairs else "ETH/USDC"
        self.use_realtime = use_realtime

        # 策略实例
        self.strategy = CryptoChan4HMasterStrategy(config)
        self.strategy.current_capital = initial_capital
        self.strategy.initial_capital = initial_capital

        # Binance 实盘客户端
        self.client = BinanceRestClient(
            api_key=api_key,
            secret_key=secret_key,
            is_simulated=True,  # 连接实盘模拟环境
        )
        self._balance = initial_capital
        _logger.info("[Live] 使用BinanceRestClient连接实盘")

        # 钉钉通知器
        self._dingtalk = None
        if dingtalk_token and dingtalk_secret:
            try:
                self._dingtalk = DingTalkNotifier(
                    access_token=dingtalk_token,
                    secret=dingtalk_secret,
                )
                _logger.info("[DingTalk] 钉钉通知器已初始化")
            except Exception as e:
                _logger.warning(f"[DingTalk] 初始化失败: {e}")

        # 状态
        self._running = False
        self._last_4h_close_time: Optional[int] = None
        self._bar_index: int = 0
        self._executed_trades: List[Dict] = []
        self._pending_orders: List[Dict] = []  # 待查询的订单ID

    async def initialize(self, dfs: Dict[str, pd.DataFrame]) -> None:
        """初始化策略和交易客户端

        Args:
            dfs: 多周期数据字典 {"4h": df, "1h": df, "15m": df, "1d": df}
        """
        df_4h = dfs.get("4h", pd.DataFrame())
        df_1h = dfs.get("1h", pd.DataFrame())
        df_15m = dfs.get("15m", pd.DataFrame())
        df_daily = dfs.get("1d", pd.DataFrame())

        if df_4h.empty:
            raise ValueError("4H数据为空，无法初始化策略")

        # 从API获取账户余额（使用 futures_account_balance_v3）
        balance_result = await self.client.get_account_balance()
        if "error" not in balance_result:
            # 新的返回格式是字典，包含完整的余额信息
            self._balance = balance_result.get("availableBalance", self.initial_capital)
            self.strategy.current_capital = self._balance
            
            # 记录完整的余额信息
            _logger.info(f"[Live] 账户余额信息:")
            _logger.info(f"  - 可用余额: ${balance_result.get('availableBalance', 0):,.2f}")
            _logger.info(f"  - 跨仓钱包余额: ${balance_result.get('crossWalletBalance', 0):,.2f}")
            _logger.info(f"  - 跨仓未实现盈亏: ${balance_result.get('crossUnPnl', 0):,.2f}")
            _logger.info(f"  - 仓位初始保证金: ${balance_result.get('positionInitialMargin', 0):,.2f}")
            _logger.info(f"  - 挂单初始保证金: ${balance_result.get('openOrderInitialMargin', 0):,.2f}")
            _logger.info(f"  - 最大可提: ${balance_result.get('maxWithdrawAmount', 0):,.2f}")
        else:
            _logger.warning(f"[Live] 无法获取账户余额，使用默认值: ${self.initial_capital:,.2f}")
            self._balance = self.initial_capital

        # 发送策略启动通知
        self._send_dingtalk_status("started", {
            "symbol": self.symbol,
            "mode": "Live",
            "initial_capital": f"${self._balance:,.2f}",
        })

        # 使用策略直接处理数据（不需要预计算指标）
        self.strategy.inject_data(df_4h, df_1h, df_15m, df_daily)
        _logger.info("[Live] 策略数据注入完成")

        # 记录最后一个4H bar的close_time用于后续检测新bar
        if "close_time" in df_4h.columns:
            last_close = df_4h["close_time"].iloc[-1]
            if isinstance(last_close, (int, float)):
                self._last_4h_close_time = int(last_close)
            elif hasattr(last_close, "timestamp"):
                self._last_4h_close_time = int(last_close.timestamp() * 1000)

        self._bar_index = len(df_4h) - 1
        self._dfs = dfs
        _logger.info(f"[Paper] 策略初始化完成, 已加载 {len(df_4h)} 根4H K线, 当前bar_index={self._bar_index}")

    def _send_dingtalk_status(self, status_type: str, info: dict = None) -> None:
        """发送钉钉状态通知"""
        if not self._dingtalk:
            return
        try:
            self._dingtalk.send_status(status_type, info)
        except Exception as e:
            _logger.error(f"[DingTalk] 发送状态通知失败: {e}")

    def _send_dingtalk_signal(self, signal: dict) -> None:
        """发送交易信号钉钉通知"""
        if not self._dingtalk:
            return
        try:
            self._dingtalk.send_trade_signal(signal, self.symbol)
        except Exception as e:
            _logger.error(f"[DingTalk] 发送信号通知失败: {e}")

    def _send_dingtalk_order(self, action: str, result: dict) -> None:
        """发送订单结果钉钉通知"""
        if not self._dingtalk:
            return
        try:
            self._dingtalk.send_order_result(action, result, self.symbol)
        except Exception as e:
            _logger.error(f"[DingTalk] 发送订单通知失败: {e}")

    async def _fetch_latest_klines(self) -> Dict[str, pd.DataFrame]:
        """获取最新K线数据"""
        symbol_clean = self.symbol.replace("/", "")
        new_dfs = {}

        for tf, limit in [("4h", 10), ("1h", 40), ("15m", 160), ("1d", 5)]:
            try:
                result = await self.client.get_continuous_klines(
                    pair=symbol_clean,
                    contractType="PERPETUAL",
                    interval=tf,
                    limit=limit,
                )
                if isinstance(result, list) and result:
                    rows = []
                    for candle in result:
                        if isinstance(candle, list) and len(candle) >= 6:
                            rows.append({
                                "open_time": pd.to_datetime(candle[0], unit="ms"),
                                "open": float(candle[1]),
                                "high": float(candle[2]),
                                "low": float(candle[3]),
                                "close": float(candle[4]),
                                "volume": float(candle[5]),
                                "close_time": int(candle[6]) if len(candle) > 6 else 0,
                            })
                    new_dfs[tf] = pd.DataFrame(rows)
            except Exception as e:
                _logger.warning(f"[Live] 获取{tf} K线失败: {e}")

        return new_dfs

    def _check_close_conditions(self, current_price: float) -> List[Dict]:
        """检查止损/止盈/加仓条件，返回需要执行的订单列表"""
        orders = []
        hedging = self.strategy.hedging

        # 检查多头止损
        if hedging.long_qty > 0 and hedging.long_stop_loss > 0:
            if current_price <= hedging.long_stop_loss:
                _logger.info(f"[Paper] 多头止损触发: price={current_price:.2f} <= SL={hedging.long_stop_loss:.2f}")
                orders.append({
                    "action": "CLOSE_LONG",
                    "price": current_price,
                    "quantity": hedging.long_qty,
                    "reason": "止损"
                })

        # 检查空头止损
        if hedging.short_qty > 0 and hedging.short_stop_loss > 0:
            if current_price >= hedging.short_stop_loss:
                _logger.info(f"[Paper] 空头止损触发: price={current_price:.2f} >= SL={hedging.short_stop_loss:.2f}")
                orders.append({
                    "action": "CLOSE_SHORT",
                    "price": current_price,
                    "quantity": hedging.short_qty,
                    "reason": "止损"
                })

        # 检查多头TP1（部分止盈）
        if hedging.long_qty > 0 and hedging.long_tp1 > 0 and not hedging.long_tp1_hit:
            if current_price >= hedging.long_tp1:
                _logger.info(f"[Paper] 多头TP1触发: price={current_price:.2f} >= TP1={hedging.long_tp1:.2f}")
                tp1_qty = hedging.long_qty * 0.5
                orders.append({
                    "action": "CLOSE_LONG",
                    "price": current_price,
                    "quantity": tp1_qty,
                    "reason": "TP1部分止盈"
                })
                hedging.long_tp1_hit = True

        # 检查空头TP1（部分止盈）
        if hedging.short_qty > 0 and hedging.short_tp1 > 0 and not hedging.short_tp1_hit:
            if current_price <= hedging.short_tp1:
                _logger.info(f"[Paper] 空头TP1触发: price={current_price:.2f} <= TP1={hedging.short_tp1:.2f}")
                tp1_qty = hedging.short_qty * 0.5
                orders.append({
                    "action": "CLOSE_SHORT",
                    "price": current_price,
                    "quantity": tp1_qty,
                    "reason": "TP1部分止盈"
                })
                hedging.short_tp1_hit = True

        return orders

    async def _execute_orders(self, orders: List[Dict]) -> None:
        """通过交易客户端执行订单列表（支持Paper和Live模式）"""
        symbol_clean = self.symbol.replace("/", "")
        mode_tag = "Live" if self.use_realtime else "Paper"

        for order in orders:
            action = order["action"]
            price = order["price"]
            quantity = order["quantity"]
            reason = order.get("reason", "")

            side = "BUY" if "LONG" in action else "SELL"
            position_side = "LONG" if "LONG" in action else "SHORT"
            is_close = action.startswith("CLOSE")

            if is_close:
                order_type = "MARKET"
            else:
                order_type = "LIMIT"

            # 调用统一的客户端接口
            result = await self.client.place_order(
                symbol=symbol_clean,
                side=side,
                position_side=position_side,
                order_type=order_type,
                quantity=quantity,
                price=price,
            )

            # 处理结果（两种模式的返回格式略有不同）
            if self.use_realtime:
                # Live模式：BinanceRestClient返回格式
                if "orderId" in result and "error" not in result:
                    order_id = result.get("orderId")
                    # Live模式下限价单可能未立即成交，需要查询实际成交价
                    if order_type == "LIMIT":
                        self._pending_orders.append({
                            "order_id": order_id,
                            "symbol": symbol_clean,
                            "action": action,
                            "quantity": quantity,
                            "reason": reason,
                            "submitted_price": price,
                        })
                        _logger.info(f"[{mode_tag}] 限价单已提交: {action}, order_id={order_id}, "
                                    f"price={price:.2f}, qty={quantity:.4f}")
                    else:
                        # 市价单立即成交
                        fill_price = float(result.get("avgPrice", price) or price)
                        self._executed_trades.append({
                            "timestamp": datetime.now().isoformat(),
                            "action": action,
                            "price": fill_price,
                            "quantity": quantity,
                            "reason": reason,
                            "order_id": order_id,
                        })
                        _logger.info(f"[{mode_tag}] 市价单成交: {action}, qty={quantity:.4f}, "
                                    f"fill_price={fill_price:.2f}")
                else:
                    error_msg = result.get("msg", result.get("error", "Unknown"))
                    _logger.error(f"[{mode_tag}] 订单失败: {action}, error={error_msg}")
            else:
                # Paper模式：PaperTradingClient返回格式
                if result.get("code") == 0:
                    fill_price = float(result.get("avgPrice", price))
                    self._executed_trades.append({
                        "timestamp": datetime.now().isoformat(),
                        "action": action,
                        "price": fill_price,
                        "quantity": quantity,
                        "reason": reason,
                        "order_id": result.get("orderId"),
                    })
                    _logger.info(f"[{mode_tag}] 订单成交: {action}, qty={quantity:.4f}, "
                                f"fill_price={fill_price:.2f}, reason={reason}")
                else:
                    _logger.error(f"[{mode_tag}] 订单失败: {action}, error={result.get('msg', 'Unknown')}")

    async def run_loop(
        self,
        dfs: Dict[str, pd.DataFrame],
        duration_hours: int = 0,
        poll_interval: int = 60,
    ) -> Dict[str, Any]:
        """主循环：使用本地CSV数据模拟逐步执行

        Args:
            dfs: 多周期数据字典
            duration_hours: 运行时长（小时），0=运行完所有数据
            poll_interval: 轮询间隔（秒）
        """
        df_4h = dfs.get("4h", pd.DataFrame())
        df_1h = dfs.get("1h", pd.DataFrame())
        df_15m = dfs.get("15m", pd.DataFrame())
        df_daily = dfs.get("1d", pd.DataFrame())

        if df_4h.empty:
            _logger.error("4H数据为空")
            return {"error": "4H数据为空"}

        total_bars = len(df_4h)
        _logger.info(f"[Paper] 开始模拟盘执行: {total_bars} 根4H K线")
        self._running = True

        # 确定起始位置（跳过已初始化的数据，从最新bar开始）
        start_idx = max(0, self._bar_index)
        if start_idx >= total_bars:
            _logger.info("[Paper] 已到达数据末尾")
            self._running = False
            return await self._generate_report()

        import numpy as np

        # 预计算索引映射
        idx_map_1h = None
        idx_map_15m = None
        idx_map_daily = None
        if df_1h is not None and not df_1h.empty and "open_time" in df_1h.columns:
            idx_map_1h = np.searchsorted(df_1h["open_time"].values, df_4h["open_time"].values, side="right")
        if df_15m is not None and not df_15m.empty and "open_time" in df_15m.columns:
            idx_map_15m = np.searchsorted(df_15m["open_time"].values, df_4h["open_time"].values, side="right")
        if df_daily is not None and not df_daily.empty and "open_time" in df_daily.columns:
            idx_map_daily = np.searchsorted(df_daily["open_time"].values, df_4h["open_time"].values, side="right")

        last_1h_end = 0
        last_15m_end = 0
        start_time = time.time()
        duration_seconds = duration_hours * 3600 if duration_hours > 0 else 0

        for i in range(start_idx, total_bars):
            if not self._running:
                break

            # 检查运行时长
            if duration_seconds > 0 and (time.time() - start_time) > duration_seconds:
                _logger.info(f"[Paper] 达到运行时长限制 ({duration_hours}h)，停止")
                break

            # 处理待成交限价单
            self.strategy._process_pending_limit_orders()

            df_4h_slice = df_4h.iloc[:i + 1]

            cur_1h_end = int(idx_map_1h[i]) if idx_map_1h is not None else 0
            cur_15m_end = int(idx_map_15m[i]) if idx_map_15m is not None else 0
            need_1h = (cur_1h_end != last_1h_end)
            need_15m = (cur_15m_end != last_15m_end)
            last_1h_end = cur_1h_end
            last_15m_end = cur_15m_end

            df_1h_slice = df_1h.iloc[:cur_1h_end] if need_1h and idx_map_1h is not None else None
            df_15m_slice = df_15m.iloc[:cur_15m_end] if need_15m and idx_map_15m is not None else None

            if idx_map_daily is not None:
                cur_daily_end = int(idx_map_daily[i])
                df_daily_slice = df_daily.iloc[:max(cur_daily_end, 1)]
            else:
                df_daily_slice = df_daily

            # 注入模拟时间
            bar_time = df_4h.iloc[i]["open_time"]
            if hasattr(bar_time, "to_pydatetime"):
                self.strategy._sim_time = bar_time.to_pydatetime()
            else:
                self.strategy._sim_time = bar_time

            # 注入数据
            self.strategy.inject_data_incremental(
                df_4h_slice, df_1h_slice, df_15m_slice, df_daily_slice,
                update_1h=need_1h, update_15m=need_15m,
            )

            # 获取当前价格
            current_price = float(df_4h.iloc[i]["close"])
            # 更新客户端的当前价格（用于计算盈亏）
            if not self.use_realtime:
                self.client._current_price[self.symbol.replace("/", "")] = current_price

            # 检查止损/止盈
            close_orders = self._check_close_conditions(current_price)
            if close_orders:
                await self._execute_orders(close_orders)

            # 同步策略持仓与客户端持仓
            self._sync_strategy_to_client()

            # 生成信号
            signal = self.strategy.generate_signal(bar_idx=i)
            if signal:
                mode_tag = "Live" if self.use_realtime else "Paper"
                _logger.info(f"[{mode_tag}] 信号: {signal.get('action')} @ {signal.get('price', 0):.2f}")
                
                # 发送信号钉钉通知
                self._send_dingtalk_signal(signal)
                
                trades_before = len(self.strategy.trades)
                self.strategy.apply_signal(signal)
                trades_after = len(self.strategy.trades)

                if trades_after > trades_before:
                    # 执行新增的交易记录
                    new_trades = self.strategy.trades[trades_before:]
                    for trade in new_trades:
                        symbol_clean = self.symbol.replace("/", "")
                        side = "BUY" if "LONG" in trade.action else "SELL"
                        position_side = "LONG" if "LONG" in trade.action else "SHORT"
                        is_close = trade.action.startswith("CLOSE")
                        order_type = "MARKET" if is_close else "LIMIT"

                        result = await self.client.place_order(
                            symbol=symbol_clean,
                            side=side,
                            position_side=position_side,
                            order_type=order_type,
                            quantity=trade.quantity,
                            price=trade.price,
                        )

                        # 处理结果
                        if self.use_realtime:
                            if "orderId" in result and "error" not in result:
                                order_id = result.get("orderId")
                                if order_type == "LIMIT":
                                    self._pending_orders.append({
                                        "order_id": order_id,
                                        "symbol": symbol_clean,
                                        "action": trade.action,
                                        "quantity": trade.quantity,
                                        "submitted_price": trade.price,
                                    })
                                    _logger.info(f"[{mode_tag}] 限价单已提交: {trade.action}, order_id={order_id}")
                                else:
                                    fill_price = float(result.get("avgPrice", trade.price) or trade.price)
                                    trade.price = fill_price
                                    self._executed_trades.append({
                                        "timestamp": datetime.now().isoformat(),
                                        "action": trade.action,
                                        "price": fill_price,
                                        "limit_price": trade.limit_price,
                                        "quantity": trade.quantity,
                                        "order_type": order_type,
                                        "reason": trade.reason,
                                        "order_id": order_id,
                                    })
                                    _logger.info(f"[{mode_tag}] {trade.action}: qty={trade.quantity:.4f}, fill_price={fill_price:.2f}")
                            else:
                                _logger.error(f"[{mode_tag}] 订单失败: {trade.action}, error={result.get('msg', result.get('error', ''))}")
                        else:
                            if result.get("code") == 0:
                                fill_price = float(result.get("avgPrice", trade.price))
                                trade.price = fill_price
                                self._executed_trades.append({
                                    "timestamp": datetime.now().isoformat(),
                                    "action": trade.action,
                                    "price": fill_price,
                                    "limit_price": trade.limit_price,
                                    "quantity": trade.quantity,
                                    "order_type": order_type,
                                    "reason": trade.reason,
                                    "order_id": result.get("orderId"),
                                })
                                _logger.info(f"[{mode_tag}] {trade.action}: qty={trade.quantity:.4f}, fill_price={fill_price:.2f}")
                            else:
                                _logger.error(f"[{mode_tag}] 订单失败: {trade.action}, error={result.get('msg', '')}")

                    # 同步策略资金到客户端余额
                    if not self.use_realtime:
                        self.strategy.current_capital = self.client._balance

            # 打印状态
            self._print_status(i, total_bars, current_price)

            # 模拟轮询间隔
            if poll_interval > 0 and i < total_bars - 1:
                await asyncio.sleep(poll_interval)

        self._running = False
        await self.client.close()
        return await self._generate_report()

    def _sync_strategy_to_client(self) -> None:
        """同步策略持仓状态到客户端（用于止损/止盈后更新）"""
        hedging = self.strategy.hedging
        symbol_clean = self.symbol.replace("/", "")

        # Live模式：不需要手动同步，由API管理持仓
        if self.use_realtime:
            return

        # Paper模式：检查模拟盘是否有持仓，而策略已清空
        client_positions = self.client._positions
        if hedging.long_qty <= 0:
            for p in list(client_positions):
                if p.get("positionSide") == "LONG":
                    client_positions.remove(p)
        if hedging.short_qty <= 0:
            for p in list(client_positions):
                if p.get("positionSide") == "SHORT":
                    client_positions.remove(p)

    def _print_status(self, i: int, total: int, current_price: float) -> None:
        """打印当前状态"""
        h = self.strategy.hedging
        mode_tag = "Live" if self.use_realtime else "Paper"

        # 获取余额（两种模式不同）
        if self.use_realtime:
            balance = self._balance
        else:
            balance = self.client._balance

        # 计算权益
        equity = balance
        if h.long_qty > 0:
            equity += (current_price - h.long_entry_price) * h.long_qty
        if h.short_qty > 0:
            equity += (h.short_entry_price - current_price) * h.short_qty
        pnl_pct = ((equity - self.initial_capital) / self.initial_capital * 100) if self.initial_capital > 0 else 0

        _logger.info(
            f"[{mode_tag}] [{i + 1}/{total}] price={current_price:.2f} | "
            f"余额=${balance:,.2f} | 权益=${equity:,.2f} ({pnl_pct:+.2f}%) | "
            f"多仓={h.long_qty:.4f}@{h.long_entry_price:.2f} | "
            f"空仓={h.short_qty:.4f}@{h.short_entry_price:.2f} | "
            f"加仓={self.strategy._add_count}/3"
        )

    async def _generate_report(self) -> Dict[str, Any]:
        """生成最终报告"""
        mode_tag = "Live" if self.use_realtime else "Paper"

        # 获取账户信息（两种模式不同）
        if self.use_realtime:
            account = await self.client.get_account_balance()
            final_balance = float(account.get("availableBalance", self._balance))
            initial_balance = self.initial_capital
        else:
            account = await self.client.get_account_balance()
            final_balance = self.client._balance
            initial_balance = self.client._initial_balance

        total_pnl = final_balance - initial_balance
        pnl_pct = (total_pnl / initial_balance * 100) if initial_balance > 0 else 0

        winning = [t for t in self._executed_trades if t.get("pnl", 0) > 0]
        losing = [t for t in self._executed_trades if t.get("pnl", 0) <= 0]

        report = {
            "symbol": self.symbol,
            "mode": mode_tag,
            "initial_capital": initial_balance,
            "final_balance": final_balance,
            "total_pnl": total_pnl,
            "pnl_pct": pnl_pct,
            "total_trades": len(self._executed_trades),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": (len(winning) / len(self._executed_trades) * 100) if self._executed_trades else 0,
            "trades": self._executed_trades,
            "generated_at": datetime.now().isoformat(),
        }

        _logger.info("=" * 60)
        _logger.info(f"  {mode_tag}模式执行结束 — 最终报告")
        _logger.info("=" * 60)
        _logger.info(f"  交易对:         {self.symbol}")
        _logger.info(f"  初始资金:       ${initial_balance:,.2f}")
        _logger.info(f"  最终余额:       ${final_balance:,.2f}")
        _logger.info(f"  总盈亏:         ${total_pnl:+,.2f}  ({pnl_pct:+.2f}%)")
        _logger.info(f"  交易次数:       {len(self._executed_trades)}")
        _logger.info(f"  盈利次数:       {len(winning)}")
        _logger.info(f"  亏损次数:       {len(losing)}")
        if self._executed_trades:
            _logger.info(f"  胜率:           {report['win_rate']:.2f}%")
        _logger.info("=" * 60)

        return report


def main():
    # 从环境变量获取默认配置
    env_api_key = os.getenv("BINANCE_API_KEY", "").strip('"').strip("'")
    env_secret_key = os.getenv("BINANCE_SECRET_KEY", "").strip('"').strip("'")
    env_dingtalk_token = os.getenv("DINGTALK_WEBHOOK_ACCESS_TOKEN", "").strip('"').strip("'")
    env_dingtalk_secret = os.getenv("DINGTALK_WEBHOOK_SECRET", "").strip('"').strip("'")

    parser = argparse.ArgumentParser(
        description="Crypto_Chan_4H_Master_v1 策略实时执行器（连接Binance testnet）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 守护进程模式（后台运行，自动重启）
  python run_crypto_chan_live.py --daemon
  
  # 查看守护进程状态
  python run_crypto_chan_live.py --status
  
  # 停止守护进程
  python run_crypto_chan_live.py --stop
  
  # 前台运行模式
  python run_crypto_chan_live.py --foreground
        """
    )
    parser.add_argument("--symbol", default="ETH/USDC", help="交易对 (默认: ETH/USDC)")
    parser.add_argument("--capital", type=float, default=10000.0, help="初始资金 (默认: 10000)")
    parser.add_argument("--commission", type=float, default=0.00018, help="手续费率 (默认: 0.0018%%)")
    parser.add_argument("--duration", type=int, default=0, help="运行时长（小时），0=持续运行")
    parser.add_argument("--interval", type=int, default=60, help="轮询间隔（秒）")
    parser.add_argument("--data-dir", default=None, help="本地CSV数据目录")
    parser.add_argument("--api-key", default=env_api_key, help="Binance API Key（默认从.env获取）")
    parser.add_argument("--secret-key", default=env_secret_key, help="Binance Secret Key（默认从.env获取）")
    parser.add_argument("--dingtalk-token", default=env_dingtalk_token, help="钉钉机器人Token（默认从.env获取）")
    parser.add_argument("--dingtalk-secret", default=env_dingtalk_secret, help="钉钉机器人Secret（默认从.env获取）")
    parser.add_argument("--export", default=None, help="结果输出JSON路径")
    parser.add_argument("--realtime", action="store_true", default=True, help="实时模式：持续监控新K线（默认启用）")
    parser.add_argument("--daemon", action="store_true", default=True, help="守护进程模式（后台运行，默认启用）")
    parser.add_argument("--foreground", action="store_true", help="前台运行模式（覆盖默认守护进程模式）")
    parser.add_argument("--stop", action="store_true", help="停止守护进程")
    parser.add_argument("--status", action="store_true", help="查看守护进程状态")
    parser.add_argument("--restart", action="store_true", help="重启守护进程")
    args = parser.parse_args()

    script_path = sys.argv[0]
    
    # 处理守护进程控制命令
    if args.stop:
        daemon_stop()
        return
    
    if args.status:
        daemon_status()
        return
    
    if args.restart:
        daemon_stop()
        time.sleep(2)
        daemon_start(script_path, ["--daemon"])
        return
    
    # 检查API Key
    if not args.api_key or not args.secret_key:
        print("错误: 需要提供 --api-key 和 --secret-key（或在.env中配置）")
        sys.exit(1)

    # 守护进程模式（默认启用，除非指定--foreground）
    if args.daemon and not args.foreground:
        daemon_start(script_path, ["--foreground"] + sys.argv[1:])
        return
    
    # 注册信号处理器和清理函数
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    atexit.register(cleanup)
    
    # 确保PID文件被清理
    if PID_FILE.exists():
        PID_FILE.unlink()
    PID_FILE.write_text(str(os.getpid()))

    print("=" * 70)
    print("  Crypto_Chan_4H_Master_v1 策略实时执行器")
    print("  基于缠论 4H/1H/15M 多周期分析")
    print("  Live模式 — 连接Binance实盘")
    print("=" * 70)
    print(f"  交易对:       {args.symbol}")
    print(f"  初始资金:     ${args.capital:,.2f}")
    print(f"  手续费率:     {args.commission * 100:.2f}%")
    if args.duration > 0:
        print(f"  运行时长:     {args.duration} 小时")
    else:
        print(f"  运行模式:     持续运行")
    print(f"  轮询间隔:     {args.interval}s")
    print(f"  API Key:      {mask_secret(args.api_key)}（已配置）")
    if args.dingtalk_token:
        print(f"  钉钉通知:     已启用")
    print("=" * 70)

    # 构建配置
    config = build_config(args.symbol)

    # 加载数据
    if args.data_dir:
        data_dir = Path(args.data_dir)
        if not data_dir.exists():
            print(f"错误: 数据目录不存在: {data_dir}")
            sys.exit(1)
        dfs = load_csv_data(args.symbol, data_dir)
    else:
        default_dir = DEFAULT_DATA_DIR
        if default_dir.exists():
            dfs = load_csv_data(args.symbol, default_dir)
            if not dfs.get("4h", pd.DataFrame()).empty:
                _logger.info("使用本地CSV数据")
            else:
                _logger.info("本地数据为空，尝试CCXT...")
                dfs = load_ccxt_data(args.symbol, 90)
        else:
            dfs = load_ccxt_data(args.symbol, 90)

    df_4h = dfs.get("4h", pd.DataFrame())
    if df_4h.empty:
        print("错误: 无法加载 4H 数据")
        sys.exit(1)

    print(f"\n数据加载完成:")
    for tf in ["4h", "1h", "15m", "1d"]:
        df = dfs.get(tf, pd.DataFrame())
        if not df.empty and "open_time" in df.columns:
            t_min = df["open_time"].min()
            t_max = df["open_time"].max()
            print(f"  {tf:>4s}: {len(df):>5} 根K线  [{t_min} ~ {t_max}]")

    # 创建执行器
    executor = CryptoChanLiveExecutor(
        config=config,
        initial_capital=args.capital,
        commission=args.commission,
        api_key=args.api_key,
        secret_key=args.secret_key,
        use_realtime=args.realtime,
        dingtalk_token=args.dingtalk_token,
        dingtalk_secret=args.dingtalk_secret,
    )
    
    # 注册全局执行器实例（用于信号处理）
    global _executor_instance
    _executor_instance = executor

    # 运行（带自动重启）
    max_restart = 5
    restart_count = 0
    
    async def _run():
        await executor.initialize(dfs)
        return await executor.run_loop(
            dfs=dfs,
            duration_hours=args.duration,
            poll_interval=args.interval,
        )
    
    while _daemon_running:
        try:
            print(f"\n开始Live模式执行...")
            _logger.info("=" * 50)
            _logger.info("策略执行器启动")
            _logger.info("=" * 50)
            report = asyncio.run(_run())
            
            # 运行完成（非异常退出）
            if args.duration > 0:
                _logger.info(f"运行时长达到 ({args.duration}h)，正常退出")
                break
            
            # 持续运行模式下，检查是否应该继续
            if not _daemon_running:
                break
            
            # 意外退出，尝试重启
            restart_count += 1
            if restart_count > max_restart:
                _logger.error(f"重启次数超过上限 ({max_restart})，停止自动重启")
                break
            
            _logger.warning(f"检测到异常退出，{5 * restart_count}秒后重启 (第{restart_count}次)")
            _logger.info("发送重启通知...")
            executor._send_dingtalk_status("error", {
                "symbol": args.symbol,
                "error": f"进程异常退出，{5 * restart_count}秒后重启",
            })
            time.sleep(5 * restart_count)  # 递增等待时间
            
        except KeyboardInterrupt:
            _logger.info("收到键盘中断信号，退出")
            break
        except Exception as e:
            restart_count += 1
            _logger.error(f"执行异常: {e}")
            if restart_count > max_restart:
                _logger.error(f"重启次数超过上限，停止")
                break
            time.sleep(5 * restart_count)

    # 清理PID文件
    try:
        PID_FILE.unlink()
    except FileNotFoundError:
        pass
    _logger.info("策略执行器已停止")

    return report

if __name__ == "__main__":
    main()