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
    logging.getLogger(_mod).setLevel(logging.INFO)  # 调试时设为INFO，生产时可改回WARNING

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
        import os
        # 跨平台方式检查进程是否存在
        os.kill(pid, 0)
        return True
    except OSError:
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
        import os
        
        # 跨平台启动进程
        kwargs = {
            'args': [sys.executable, script_path] + args,
            'stdout': subprocess.DEVNULL,
            'stderr': subprocess.DEVNULL,
            'cwd': str(PROJECT_ROOT),
        }
        
        # Windows 特有设置
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            kwargs['startupinfo'] = startupinfo
            if hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP'):
                kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            # Linux/Mac 设置
            kwargs['preexec_fn'] = os.setsid
        
        # 启动进程
        process = subprocess.Popen(**kwargs)
        
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
        # 跨平台终止进程
        if os.name == 'nt':
            # Windows: 使用 taskkill
            subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                          capture_output=True)
        else:
            # Linux/Mac: 使用 os.kill
            import signal
            os.kill(pid, signal.SIGTERM)
        
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
            "base_currency": "USDT",
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
            "atr": {"period": 14, "source": "4h", "multiplier_stop_loss": 1.0, "multiplier_take_profit": 2.0},
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
            "sizing": {"method": "atr_based", "risk_per_trade_percent": 2.0,
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
                df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
            dfs[tf] = df
            _logger.debug(f"加载 {tf}: {len(df)} 行 from {fp}")
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
        max_price_deviation: float = 0.002,
    ):
        self.config = config
        self.initial_capital = initial_capital
        self.commission = commission
        self.symbol = config.metadata.trading_pairs[0] if config.metadata.trading_pairs else "ETH/USDT"
        self.use_realtime = use_realtime
        self.max_price_deviation = max_price_deviation  # 限价单回退市价单时的最大价格偏差（默认0.2%）

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

        # 心跳日志：周期性存活状态（可通过环境变量 HEARTBEAT_INTERVAL_SEC 配置，默认 300 秒）
        self._heartbeat_interval_sec: float = float(os.environ.get("HEARTBEAT_INTERVAL_SEC", "300"))
        self._last_heartbeat_ts: float = time.time()

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
        _logger.debug(f"[Live] 正在获取账户余额...")
        balance_result = await self.client.get_account_balance()
        _logger.debug(f"[Live] 余额API原始返回: {json.dumps(balance_result, default=str, ensure_ascii=False)}")

        # 预加载交易对精度规则（tickSize/stepSize/minQty/minNotional）
        symbol_clean = self.symbol.replace("/", "")
        _logger.debug(f"[Live] 正在加载交易对精度规则: {symbol_clean}...")
        try:
            exchange_info = await self.client.get_exchange_info()
            if "error" not in exchange_info:
                precision = self.client._get_precision(symbol_clean)
                _logger.debug(
                    f"[Live] 精度规则已加载: tickSize={precision.get('tick_size')}, "
                    f"stepSize={precision.get('step_size')}, minQty={precision.get('min_qty')}, "
                    f"minNotional={precision.get('min_notional')}"
                )
            else:
                _logger.warning(f"[Live] 获取exchange_info失败，将使用默认精度: {exchange_info.get('msg', '')}")
        except Exception as e:
            _logger.warning(f"[Live] 获取exchange_info异常，将使用默认精度: {e}")
        if "error" not in balance_result:
            # 新的返回格式是字典，包含完整的余额信息
            self._balance = balance_result.get("availableBalance", self.initial_capital)
            self.strategy.current_capital = self._balance
            
            # 更新初始资金为实时余额
            self.initial_capital = self._balance
            
            # 记录完整的余额信息（仅一行摘要，明细见 DEBUG）
            _logger.info(
                f"[Live] 账户余额: 可用=${balance_result.get('availableBalance', 0):,.2f}, "
                f"钱包=${balance_result.get('crossWalletBalance', 0):,.2f}, "
                f"未实现盈亏=${balance_result.get('crossUnPnl', 0):,.2f}, "
                f"最大可提=${balance_result.get('maxWithdrawAmount', 0):,.2f}"
            )
            _logger.debug(
                f"[Live] 余额明细: 仓位初始保证金=${balance_result.get('positionInitialMargin', 0):,.2f}, "
                f"挂单初始保证金=${balance_result.get('openOrderInitialMargin', 0):,.2f}"
            )
        else:
            _logger.warning(f"[Live] 无法获取账户余额，使用默认值: ${self.initial_capital:,.2f}")
            self._balance = self.initial_capital

        # 启动前检查仓位并平仓（保证策略从零仓位开始）
        await self._close_all_positions()
        # 平仓后重新获取余额（反映平仓后的资金变化）
        await self._refresh_balance()
        self.initial_capital = self._balance
        _logger.info(f"[Live] 平仓后最终可用余额: ${self._balance:,.2f}（已设为初始资金）")

        # 发送策略启动通知
        self._send_dingtalk_status("started", {
            "symbol": self.symbol,
            "mode": "Live",
            "initial_capital": f"${self._balance:,.2f}",
        })

        # 使用策略直接处理数据（不需要预计算指标）
        _logger.info(
            f"[Live] 注入策略数据: 4H={len(df_4h)}行, 1H={len(df_1h) if not df_1h.empty else 0}行, "
            f"15M={len(df_15m) if not df_15m.empty else 0}行, 1D={len(df_daily) if not df_daily.empty else 0}行"
        )
        self.strategy.inject_data(df_4h, df_1h, df_15m, df_daily)
        self.strategy._live_mode = True  # 启用实盘模式，使用iloc[-2]避免未来函数
        _logger.info(
            f"[Live] 策略数据注入完成: 日线趋势={self.strategy.daily_trend}, "
            f"市场状态={self.strategy._market_regime.value}, "
            f"4H背驰: 顶={self.strategy._chan_4h.beichi_top}, 底={self.strategy._chan_4h.beichi_bottom}, "
            f"4H分型: 顶={self.strategy._chan_4h.has_top_fractal}, 底={self.strategy._chan_4h.has_bottom_fractal}, "
            f"中枢数={len(self.strategy._chan_4h.zhongshu_list)}"
        )

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

    async def _refresh_balance(self) -> float:
        """调用API刷新账户余额，返回最新可用余额"""
        try:
            result = await self.client.get_account_balance()
            if "error" not in result:
                new_balance = float(result.get("availableBalance", self._balance))
                if abs(new_balance - self._balance) > 0.01:
                    _logger.debug(f"[Live] 余额刷新: ${self._balance:,.2f} → ${new_balance:,.2f}")
                self._balance = new_balance
                self.strategy.current_capital = self._balance
            else:
                _logger.debug(f"[Live] 余额刷新失败(使用缓存值): {result.get('msg', '')}")
        except Exception as e:
            _logger.debug(f"[Live] 余额刷新异常(使用缓存值): {e}")
        return self._balance

    async def _close_all_positions(self) -> None:
        """启动前检查仓位，撤销挂单并市价平仓所有持仓
        
        保证策略从“零仓位”状态开始运行，避免遗留仓位与策略信号冲突。
        """
        symbol_clean = self.symbol.replace("/", "")
        _logger.info(f"[启动] 检查现有仓位和挂单: {symbol_clean}...")
        
        # —— 1. 撤销所有未成交挂单 ——
        try:
            open_orders = await self.client.get_open_orders(symbol=symbol_clean)
            if open_orders:
                _logger.info(f"[启动] 发现 {len(open_orders)} 个未成交挂单，正在撤销...")
                for order in open_orders:
                    order_id = order.get("orderId")
                    if order_id:
                        cancel_result = await self.client.cancel_order(
                            symbol=symbol_clean, order_id=int(order_id)
                        )
                        if "error" not in cancel_result:
                            _logger.debug(f"[启动] 撤销挂单成功: orderId={order_id}, "
                                        f"side={order.get('side')}, price={order.get('price')}")
                        else:
                            _logger.warning(f"[启动] 撤销挂单失败: orderId={order_id}, error={cancel_result}")
            else:
                _logger.info("[启动] 无未成交挂单")
        except Exception as e:
            _logger.warning(f"[启动] 撤销挂单异常: {e}")
        
        # —— 2. 查询并平仓所有持仓 ——
        try:
            positions = await self.client.get_positions(symbol=symbol_clean)
            active_positions = [
                p for p in positions
                if abs(float(p.get("positionAmt", 0))) > 0
            ]
            
            if not active_positions:
                _logger.info("[启动] 当前无持仓，策略将从零仓位开始")
                return
            
            _logger.info(f"[启动] 发现 {len(active_positions)} 个持仓，正在平仓...")
            for pos in active_positions:
                position_amt = float(pos.get("positionAmt", 0))
                position_side = pos.get("positionSide", "BOTH")
                entry_price = float(pos.get("entryPrice", 0))
                unrealized_pnl = float(pos.get("unRealizedProfit", 0))
                abs_qty = abs(position_amt)
                
                # 确定平仓方向：多仓用 SELL 平，空仓用 BUY 平
                if position_amt > 0:
                    side = "SELL"
                    direction = "多仓"
                else:
                    side = "BUY"
                    direction = "空仓"
                
                _logger.info(
                    f"[启动] 平仓 {direction}: {symbol_clean}, "
                    f"positionSide={position_side}, qty={abs_qty}, "
                    f"entryPrice={entry_price:.2f}, unrealizedPnL={unrealized_pnl:.2f}"
                )
                
                result = await self.client.place_order(
                    symbol=symbol_clean,
                    side=side,
                    order_type="MARKET",
                    quantity=abs_qty,
                )
                
                if "error" not in result:
                    fill_price = float(result.get("avgPrice", 0) or 0)
                    _logger.info(
                        f"[启动] 平仓成功: {direction} {abs_qty}, "
                        f"fill_price={fill_price:.2f}, orderId={result.get('orderId')}"
                    )
                else:
                    _logger.error(f"[启动] 平仓失败: {direction} {abs_qty}, error={result}")
            
            # 平仓完成后刷新余额
            await self._refresh_balance()
            _logger.info(f"[启动] 所有持仓已平仓，最新余额: ${self._balance:,.2f}")
            
        except Exception as e:
            _logger.error(f"[启动] 平仓异常: {e}", exc_info=True)
    
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

        _logger.debug(f"[Live] 开始获取最新K线数据...")
        for tf, limit in [("4h", 10), ("1h", 40), ("15m", 160), ("1d", 5)]:
            try:
                _logger.debug(f"[Live] 请求K线: pair={symbol_clean}, contractType=PERPETUAL, interval={tf}, limit={limit}")
                result = await self.client.get_continuous_klines(
                    pair=symbol_clean,
                    contractType="PERPETUAL",
                    interval=tf,
                    limit=limit,
                )
                _logger.debug(f"[Live] {tf} K线响应: 类型={type(result).__name__}, 长度={len(result) if isinstance(result, list) else 'N/A'}")
                if isinstance(result, list) and result:
                    _logger.debug(f"[Live] {tf} 首根K线: {result[0]}")
                    _logger.debug(f"[Live] {tf} 末根K线: {result[-1]}")
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
        """检查止损/止盈条件，返回需要执行的订单列表（对齐回测逻辑）"""
        orders = []
        hedging = self.strategy.hedging
        _logger.debug(
            f"[Paper] 检查平仓条件: price={current_price:.4f} | "
            f"多头: qty={hedging.long_qty:.4f}, SL={hedging.long_stop_loss:.4f}, "
            f"TP={hedging.long_take_profit:.4f} | "
            f"空头: qty={hedging.short_qty:.4f}, SL={hedging.short_stop_loss:.4f}, "
            f"TP={hedging.short_take_profit:.4f}"
        )

        # 更新移动止损（对齐回测的 _update_trailing_stop_long/short）
        if hedging.long_qty > 0:
            self.strategy._update_trailing_stop_long()
        if hedging.short_qty > 0:
            self.strategy._update_trailing_stop_short()

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
            elif current_price >= hedging.long_take_profit:
                _logger.info(f"[Paper] 多头止盈触发: price={current_price:.2f} >= TP={hedging.long_take_profit:.2f}")
                orders.append({
                    "action": "CLOSE_LONG",
                    "price": current_price,
                    "quantity": hedging.long_qty,
                    "reason": "止盈"
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
            elif current_price <= hedging.short_take_profit:
                _logger.info(f"[Paper] 空头止盈触发: price={current_price:.2f} <= TP={hedging.short_take_profit:.2f}")
                orders.append({
                    "action": "CLOSE_SHORT",
                    "price": current_price,
                    "quantity": hedging.short_qty,
                    "reason": "止盈"
                })

        return orders

    async def _execute_orders(self, orders: List[Dict]) -> None:
        """通过交易客户端执行订单列表（支持Paper和Live模式）"""
        symbol_clean = self.symbol.replace("/", "")
        mode_tag = "Live" if self.use_realtime else "Paper"
        _logger.info(f"[{mode_tag}] 执行订单列表: 共{len(orders)}笔")

        for idx, order in enumerate(orders):
            action = order["action"]
            price = order["price"]
            quantity = order["quantity"]
            reason = order.get("reason", "")
            _logger.debug(f"[{mode_tag}] 订单[{idx+1}/{len(orders)}]: action={action}, price={price:.4f}, qty={quantity:.4f}, reason={reason}")

            side = "BUY" if "LONG" in action else "SELL"
            is_close = action.startswith("CLOSE")

            if is_close:
                order_type = "MARKET"
            else:
                order_type = "LIMIT"

            # 调用统一的客户端接口
            _logger.debug(
                f"[{mode_tag}] 下单请求: symbol={symbol_clean}, side={side}, "
                f"type={order_type}, qty={quantity:.4f}, price={price:.4f}"
            )
            result = await self.client.place_order(
                symbol=symbol_clean,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
            )
            _logger.debug(f"[{mode_tag}] 下单响应: {json.dumps(result, default=str, ensure_ascii=False)}")


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
                _logger.error(f"[{mode_tag}] 订单失败: {action}, error={result}")

        # 订单执行完成后刷新余额
        if orders:
            await self._refresh_balance()


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
            return {"error": "4H数据为空", "completed": True}

        total_bars = len(df_4h)
        _logger.info(f"[Paper] 开始模拟盘执行: {total_bars} 根4H K线")
        self._running = True

        # 确定起始位置（跳过已初始化的数据，从最新bar开始）
        start_idx = max(0, self._bar_index)
        if start_idx >= total_bars:
            _logger.info("[Paper] 已到达数据末尾，直接进入实时监控模式")
            # 不设置 self._running = False，继续进入实时监控模式
            # 跳过历史数据处理，直接进入实时监控
            pass
        else:
            # 正常处理历史数据
            pass

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
            # 更新客户端的当前价格（仅Paper模式下的模拟客户端需要）

            # 检查止损/止盈
            close_orders = self._check_close_conditions(current_price)
            if close_orders:
                _logger.info(f"[历史] bar={i} 触发平仓条件: {[o.get('action') for o in close_orders]}")
                await self._execute_orders(close_orders)

            # 同步策略持仓与客户端持仓
            self._sync_strategy_to_client()

            # 生成信号
            _logger.debug(
                f"[历史] bar={i} 生成信号前: 日线趋势={self.strategy.daily_trend}, "
                f"市场状态={self.strategy._market_regime.value}, "
                f"4H背驰: 顶={self.strategy._chan_4h.beichi_top}, 底={self.strategy._chan_4h.beichi_bottom}, "
                f"4H分型: 顶={self.strategy._chan_4h.has_top_fractal}, 底={self.strategy._chan_4h.has_bottom_fractal}, "
                f"中枢数={len(self.strategy._chan_4h.zhongshu_list)}, "
                f"ATR={self.strategy._atr_value:.4f}"
            )
            signal = self.strategy.generate_signal(bar_idx=i)
            if signal:
                mode_tag = "Live" if self.use_realtime else "Paper"
                _logger.info(f"[{mode_tag}] bar={i} 信号: action={signal.get('action')}, price={signal.get('price', 0):.2f}, "
                           f"stop_loss={signal.get('stop_loss', 0):.2f}, take_profit={signal.get('take_profit', 0):.2f}, "
                           f"tp1={signal.get('tp1', 0):.2f}, reason={signal.get('reason', '')}")
                _logger.debug(f"[{mode_tag}] bar={i} 信号完整数据: {json.dumps(signal, default=str, ensure_ascii=False)}")
                
                # 发送信号钉钉通知
                self._send_dingtalk_signal(signal)
                
                trades_before = len(self.strategy.trades)
                self.strategy.apply_signal(signal)
                trades_after = len(self.strategy.trades)

                if trades_after > trades_before:
                    # 执行新增的交易记录
                    new_trades = self.strategy.trades[trades_before:]
                    _logger.info(f"[历史] bar={i} 新增{len(new_trades)}笔交易记录")
                    for trade_idx, trade in enumerate(new_trades):
                        symbol_clean = self.symbol.replace("/", "")
                        side = "BUY" if "LONG" in trade.action else "SELL"
                        is_close = trade.action.startswith("CLOSE")
                        order_type = "MARKET" if is_close else "LIMIT"
                        _logger.debug(
                            f"[历史] bar={i} 交易[{trade_idx+1}/{len(new_trades)}]: "
                            f"action={trade.action}, price={trade.price:.4f}, qty={trade.quantity:.4f}, "
                            f"下单参数: symbol={symbol_clean}, side={side} "
                            f"type={order_type}"
                        )

                        result = await self.client.place_order(
                            symbol=symbol_clean,
                            side=side,
                            order_type=order_type,
                            quantity=trade.quantity,
                            price=trade.price,
                        )
                        _logger.debug(f"[历史] bar={i} 下单响应: {json.dumps(result, default=str, ensure_ascii=False)}")

                        # 处理结果
                        order_success = result and "error" not in result
                        if order_success:
                            order_id = result.get("orderId")
                            if order_type == "LIMIT":
                                self._pending_orders.append({
                                    "order_id": order_id,
                                    "symbol": symbol_clean,
                                    "action": trade.action,
                                    "quantity": trade.quantity,
                                    "submitted_price": trade.price,
                                })
                                _logger.info(f"[历史] bar={i} 限价单已提交: {trade.action}, order_id={order_id}")
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
                                _logger.info(f"[历史] bar={i} 市价单成交: {trade.action}, qty={trade.quantity:.4f}, fill_price={fill_price:.2f}")
                        else:
                            # 限价单失败 → 尝试市价单回退（需检查价格偏差）
                            _logger.warning(f"[历史] bar={i} 限价单失败: {trade.action}, error={result}")
                            if order_type == "LIMIT" and not is_close:
                                deviation = abs(current_price - trade.price) / trade.price if trade.price > 0 else float('inf')
                                if deviation <= self.max_price_deviation:
                                    _logger.info(
                                        f"[历史] bar={i} 价格偏差 {deviation:.4f} <= {self.max_price_deviation}，"
                                        f"回退市价单: {trade.action}"
                                    )
                                    result = await self.client.place_order(
                                        symbol=symbol_clean,
                                        side=side,
                                        order_type="MARKET",
                                        quantity=trade.quantity,
                                    )
                                    _logger.debug(f"[历史] bar={i} 市价单回退响应: {json.dumps(result, default=str, ensure_ascii=False)}")
                                    if result and "error" not in result:
                                        fill_price = float(result.get("avgPrice", trade.price) or trade.price)
                                        trade.price = fill_price
                                        self._executed_trades.append({
                                            "timestamp": datetime.now().isoformat(),
                                            "action": trade.action,
                                            "price": fill_price,
                                            "limit_price": trade.limit_price,
                                            "quantity": trade.quantity,
                                            "order_type": "MARKET",
                                            "reason": trade.reason,
                                            "order_id": result.get("orderId"),
                                        })
                                        _logger.info(f"[历史] bar={i} 市价单回退成交: {trade.action}, qty={trade.quantity:.4f}, fill_price={fill_price:.2f}")
                                    else:
                                        _logger.error(f"[历史] bar={i} 市价单回退也失败: {trade.action}, error={result}")
                                else:
                                    _logger.warning(
                                        f"[历史] bar={i} 价格偏差 {deviation:.4f} > {self.max_price_deviation}，"
                                        f"放弃市价回退: {trade.action} (current={current_price:.2f}, limit={trade.price:.2f})"
                                    )

                    # 刷新余额并同步策略资金
                    await self._refresh_balance()
                    self.strategy.current_capital = self._balance

            # 打印状态
            self._print_status(i, total_bars, current_price)

            # 模拟轮询间隔
            if poll_interval > 0 and i < total_bars - 1:
                await asyncio.sleep(poll_interval)

        # 历史数据处理完成，进入实时监控模式
        _logger.info("历史数据处理完成，进入实时监控模式")
        
        # 重新设置 _running 为 True，确保进入实时监控循环
        self._running = True
        
        # 获取最后一根K线的open_time作为基准
        last_bar_time = df_4h.iloc[-1]["open_time"]
        if hasattr(last_bar_time, "timestamp"):
            last_bar_timestamp = int(last_bar_time.timestamp() * 1000)
        else:
            last_bar_timestamp = int(last_bar_time)
        
        _logger.debug(f"[实时] 最后一根K线时间: {last_bar_time}")
        _logger.info(f"[实时] 开始实时监控（每次轮询检查信号和止损/止盈）...")

        # 实时监控循环
        realtime_bar_count = 0
        total_bars = len(df_4h)
        # 当前价格：始终取最新K线的收盘价（当前K线始终在形成中，任何时候都可检查信号）
        current_price = float(df_4h.iloc[-1]["close"])
        _logger.debug(f"[实时] 初始价格: {current_price:.2f}")
        while self._running:
            try:
                # 等待轮询间隔
                await asyncio.sleep(poll_interval)
                
                # 获取最新的K线数据
                symbol_clean = self.symbol.replace("/", "")
                _logger.debug(
                    f"[实时] 请求K线: pair={symbol_clean}, contractType=PERPETUAL, "
                    f"interval=4h, limit=10"
                )
                latest_klines = await self.client.get_continuous_klines(
                    pair=symbol_clean,
                    contractType="PERPETUAL",
                    interval="4h",
                    limit=10  # 获取最近10根K线
                )
                
                if not latest_klines or len(latest_klines) == 0:
                    _logger.warning("[实时] 获取K线数据失败，继续等待...")
                    continue
                
                _logger.debug(f"[实时] K线响应: 长度={len(latest_klines)}, 末根={latest_klines[-1]}")
                
                # 解析最新K线
                latest_kline = latest_klines[-1]
                latest_open_time = latest_kline[0]  # 第一列是open_time
                
                # ============================================================
                # 1. 如果出现了新K线（open_time 更新），更新策略数据
                # ============================================================
                if latest_open_time > last_bar_timestamp:
                    realtime_bar_count += 1
                    _logger.debug(f"[实时] 检测到新的4H K线 #{realtime_bar_count}")
                    _logger.debug(f"[实时] 新K线时间: {pd.to_datetime(latest_open_time, unit='ms')}")
                    
                    # 更新最后一根K线的时间戳
                    last_bar_timestamp = latest_open_time
                    
                    # 将新K线数据转换为DataFrame格式
                    new_bar_data = {
                        "open_time": pd.to_datetime(latest_open_time, unit='ms'),
                        "open": float(latest_kline[1]),
                        "high": float(latest_kline[2]),
                        "low": float(latest_kline[3]),
                        "close": float(latest_kline[4]),
                        "volume": float(latest_kline[5]),
                    }
                    
                    # 追加到DataFrame
                    new_row = pd.DataFrame([new_bar_data])
                    df_4h = pd.concat([df_4h, new_row], ignore_index=True)
                    total_bars = len(df_4h)
                    
                    _logger.debug(
                        f"[实时] bar={realtime_bar_count} 新K线数据: "
                        f"time={new_bar_data['open_time']}, open={new_bar_data['open']:.2f}, "
                        f"high={new_bar_data['high']:.2f}, low={new_bar_data['low']:.2f}, "
                        f"close={new_bar_data['close']:.2f}, volume={new_bar_data['volume']:.4f}, "
                        f"total_bars={total_bars}"
                    )
                    
                    # 注入实时时间
                    self.strategy._sim_time = new_bar_data["open_time"].to_pydatetime()
                    
                    # 注入数据到策略（仅在新K线出现时更新策略内部数据结构）
                    self.strategy.inject_data_incremental(
                        df_4h, None, None, None,
                        update_1h=False, update_15m=False,
                    )
                
                # ============================================================
                # 2. 每次轮询都执行：获取最新价格、检查止损/止盈、生成信号
                #    （当前K线始终在形成中，任何时候都可检查信号和止损/止盈）
                # ============================================================
                # 始终取最新K线的收盘价作为当前价格
                current_price = float(latest_klines[-1][4])

                # 心跳日志：周期性输出存活状态（默认每 5 分钟一次）
                if time.time() - self._last_heartbeat_ts >= self._heartbeat_interval_sec:
                    _logger.info(
                        f"[心跳] alive | price={current_price:.2f} | "
                        f"long={self.strategy.hedging.long_qty:.4f}@{self.strategy.hedging.long_entry_price:.2f} "
                        f"short={self.strategy.hedging.short_qty:.4f}@{self.strategy.hedging.short_entry_price:.2f} | "
                        f"bar={realtime_bar_count} | balance=${self._balance:,.2f}"
                    )
                    self._last_heartbeat_ts = time.time()

                # 检查止损/止盈
                close_orders = self._check_close_conditions(current_price)
                if close_orders:
                    _logger.info(f"[实时] 触发平仓条件 (price={current_price:.2f}): {[o.get('action') for o in close_orders]}")
                    await self._execute_orders(close_orders)
                
                # 同步策略持仓与客户端持仓
                self._sync_strategy_to_client()
                
                # 生成信号
                _logger.debug(
                    f"[实时] 生成信号前: 日线趋势={self.strategy.daily_trend}, "
                    f"市场状态={self.strategy._market_regime.value}, "
                    f"4H背驰: 顶={self.strategy._chan_4h.beichi_top}, 底={self.strategy._chan_4h.beichi_bottom}, "
                    f"4H分型: 顶={self.strategy._chan_4h.has_top_fractal}, 底={self.strategy._chan_4h.has_bottom_fractal}, "
                    f"中枢数={len(self.strategy._chan_4h.zhongshu_list)}, ATR={self.strategy._atr_value:.4f}"
                )
                signal = self.strategy.generate_signal(
                    bar_idx=total_bars - 1, live_mode=True, current_price=current_price
                )
                if signal:
                    _logger.info(
                        f"[实时] 信号: action={signal.get('action')}, "
                        f"price={signal.get('price', 0):.2f}, stop_loss={signal.get('stop_loss', 0):.2f}, "
                        f"take_profit={signal.get('take_profit', 0):.2f}, tp1={signal.get('tp1', 0):.2f}, "
                        f"reason={signal.get('reason', '')}"
                    )
                    _logger.debug(f"[实时] 信号完整数据: {json.dumps(signal, default=str, ensure_ascii=False)}")
                    
                    # 发送信号钉钉通知
                    self._send_dingtalk_signal(signal)
                    
                    trades_before = len(self.strategy.trades)
                    self.strategy.apply_signal(signal)
                    trades_after = len(self.strategy.trades)
                    
                    if trades_after > trades_before:
                        # 执行新增的交易记录
                        new_trades = self.strategy.trades[trades_before:]
                        _logger.info(f"[实时] 新增{len(new_trades)}笔交易记录")
                        for trade_idx, trade in enumerate(new_trades):
                            symbol_clean = self.symbol.replace("/", "")
                            side = "BUY" if "LONG" in trade.action else "SELL"

                            is_close = trade.action.startswith("CLOSE")
                            order_type = "MARKET" if is_close else "LIMIT"
                            _logger.debug(
                                f"[实时] 交易[{trade_idx+1}/{len(new_trades)}]: "
                                f"action={trade.action}, price={trade.price:.4f}, qty={trade.quantity:.4f}, "
                                f"下单参数: symbol={symbol_clean}, side={side} "
                                f"type={order_type}"
                            )
                            
                            result = await self.client.place_order(
                                symbol=symbol_clean,
                                side=side,
                                order_type=order_type,
                                quantity=trade.quantity,
                                price=trade.price,
                            )
                            _logger.debug(f"[实时] 下单响应: {json.dumps(result, default=str, ensure_ascii=False)}")
                            
                            # 处理结果
                            order_success = result and "error" not in result
                            if order_success:
                                order_id = result.get("orderId")
                                if order_type == "LIMIT":
                                    self._pending_orders.append({
                                        "order_id": order_id,
                                        "symbol": symbol_clean,
                                        "action": trade.action,
                                        "quantity": trade.quantity,
                                        "submitted_price": trade.price,
                                    })
                                    _logger.info(f"[实时] 限价单已提交: {trade.action}, order_id={order_id}")
                                else:
                                    fill_price = float(result.get("avgPrice", trade.price) or trade.price)
                                    trade.price = fill_price
                                    self._executed_trades.append({
                                        "action": trade.action,
                                        "price": fill_price,
                                        "quantity": trade.quantity,
                                        "pnl": 0,
                                    })
                                    _logger.info(f"[实时] 市价单成交: {trade.action}, qty={trade.quantity:.4f}, fill_price={fill_price:.2f}")
                            else:
                                # 限价单失败 → 尝试市价单回退（需检查价格偏差）
                                _logger.warning(f"[实时] 限价单失败: {trade.action}, error={result}")
                                if order_type == "LIMIT" and not is_close:
                                    deviation = abs(current_price - trade.price) / trade.price if trade.price > 0 else float('inf')
                                    if deviation <= self.max_price_deviation:
                                        _logger.info(
                                            f"[实时] 价格偏差 {deviation:.4f} <= {self.max_price_deviation}，"
                                            f"回退市价单: {trade.action}"
                                        )
                                        result = await self.client.place_order(
                                            symbol=symbol_clean,
                                            side=side,
                                            order_type="MARKET",
                                            quantity=trade.quantity,
                                        )
                                        _logger.debug(f"[实时] 市价单回退响应: {json.dumps(result, default=str, ensure_ascii=False)}")
                                        if result and "error" not in result:
                                            fill_price = float(result.get("avgPrice", trade.price) or trade.price)
                                            trade.price = fill_price
                                            self._executed_trades.append({
                                                "action": trade.action,
                                                "price": fill_price,
                                                "quantity": trade.quantity,
                                                "pnl": 0,
                                            })
                                            _logger.info(f"[实时] 市价单回退成交: {trade.action}, qty={trade.quantity:.4f}, fill_price={fill_price:.2f}")
                                        else:
                                            _logger.error(f"[实时] 市价单回退也失败: {trade.action}, error={result}")
                                    else:
                                        _logger.warning(
                                            f"[实时] 价格偏差 {deviation:.4f} > {self.max_price_deviation}，"
                                            f"放弃市价回退: {trade.action} (current={current_price:.2f}, limit={trade.price:.2f})"
                                        )
                        
                        # 刷新余额并同步策略资金
                        await self._refresh_balance()
                        self.strategy.current_capital = self._balance
                
                # 打印实时状态
                self._print_realtime_status(total_bars, current_price)
                
                # 每10分钟刷新一次余额
                now = time.time()
                if not hasattr(self, '_last_balance_refresh') or (now - self._last_balance_refresh) >= 600:
                    await self._refresh_balance()
                    self._last_balance_refresh = now
                
            except KeyboardInterrupt:
                _logger.info("[实时] 用户中断，退出实时监控")
                break
            except Exception as e:
                _logger.error(f"[实时] 实时监控异常: {e}", exc_info=True)
                # 继续运行，不因单次异常退出
                continue
        
        self._running = False
        await self.client.close()
        report = await self._generate_report()
        # 标识是否正常处理完所有数据
        report["completed"] = True
        return report

    def _sync_strategy_to_client(self) -> None:
        """同步策略持仓状态
        
        Live模式：由Binance API管理持仓，无需手动同步。
        此处仅用于触发余额刷新。
        """
        # BinanceRestClient 由API直接管理持仓，不需要手动同步
        pass

    def _print_status(self, i: int, total: int, current_price: float) -> None:
        """打印当前状态"""
        h = self.strategy.hedging
        mode_tag = "Live" if self.use_realtime else "Paper"

        # 统一使用本地跟踪余额（Live模式由 _refresh_balance 定期刷新）
        balance = self._balance

        # 计算权益
        equity = balance
        if h.long_qty > 0:
            equity += (current_price - h.long_entry_price) * h.long_qty
        if h.short_qty > 0:
            equity += (h.short_entry_price - current_price) * h.short_qty
        pnl_pct = ((equity - self.initial_capital) / self.initial_capital * 100) if self.initial_capital > 0 else 0

        _logger.debug(
            f"[{mode_tag}] [{i + 1}/{total}] price={current_price:.2f} | "
            f"余额=${balance:,.2f} | 权益=${equity:,.2f} ({pnl_pct:+.2f}%) | "
            f"多仓={h.long_qty:.4f}@{h.long_entry_price:.2f} | "
            f"空仓={h.short_qty:.4f}@{h.short_entry_price:.2f} | "
            f"加仓={self.strategy._add_count}/3"
        )

    def _print_realtime_status(self, total: int, current_price: float) -> None:
        """打印实时监控状态"""
        h = self.strategy.hedging
        mode_tag = "Live" if self.use_realtime else "Paper"

        # 统一使用本地跟踪余额（Live模式由 _refresh_balance 定期刷新）
        balance = self._balance

        # 计算权益
        equity = balance
        if h.long_qty > 0:
            equity += (current_price - h.long_entry_price) * h.long_qty
        if h.short_qty > 0:
            equity += (h.short_entry_price - current_price) * h.short_qty
        pnl_pct = ((equity - self.initial_capital) / self.initial_capital * 100) if self.initial_capital > 0 else 0

        _logger.debug(
            f"[实时] [{total}/{total}] price={current_price:.2f} | "
            f"余额=${balance:,.2f} | 权益=${equity:,.2f} ({pnl_pct:+.2f}%) | "
            f"多仓={h.long_qty:.4f}@{h.long_entry_price:.2f} | "
            f"空仓={h.short_qty:.4f}@{h.short_entry_price:.2f} | "
            f"加仓={self.strategy._add_count}/3"
        )

    async def _generate_report(self) -> Dict[str, Any]:
        """生成最终报告"""
        mode_tag = "Live" if self.use_realtime else "Paper"

        # 通过API获取最新账户余额
        final_balance = self._balance
        try:
            account = await self.client.get_account_balance()
            if "error" not in account:
                final_balance = float(account.get("availableBalance", self._balance))
            else:
                _logger.warning(f"[Report] 获取最终余额失败，使用缓存值: {account.get('msg', '')}")
        except Exception as e:
            _logger.warning(f"[Report] 获取最终余额异常，使用缓存值: {e}")
        initial_balance = self.initial_capital

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
    parser.add_argument("--symbol", default="ETH/USDT", help="交易对 (默认: ETH/USDT)")
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
    parser.add_argument("--max-deviation", type=float, default=0.002, help="限价单回退市价单的最大价格偏差（默认0.002=0.2%%）")
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
    print(f"  价格偏差限制: {args.max_deviation:.4f} ({args.max_deviation*100:.2f}%%)")
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
        max_price_deviation=args.max_deviation,
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
            _logger.info("策略执行器启动")
            report = asyncio.run(_run())
            
            # 检查是否正常退出（实时监控模式下，只有用户中断才会退出）
            if report.get("completed"):
                _logger.info("程序正常退出")
                break
            
            # 运行时长达到（非异常退出）
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