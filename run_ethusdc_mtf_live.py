"""
多周期共振分型预判策略 - Binance模拟盘实时交易（多空双向）

使用方法:
    python run_ethusdc_mtf_live.py
    python run_ethusdc_mtf_live.py --dry-run    # 只生成信号不下单
    python run_ethusdc_mtf_live.py --real       # 实盘模式(需确认)
    python run_ethusdc_mtf_live.py --support-levels 2300,2250,2200
    python run_ethusdc_mtf_live.py --resistance-levels 2400,2450,2500
"""

import argparse
import asyncio
import logging
import os
import platform
import signal
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading_system.binance.client import BinanceRestClient
from trading_system.binance.config import config as binance_config
from trading_system.binance.paper_client import PaperTradingClient
from trading_system.notify import DingTalkNotifier
from trading_system.strategies.mtf_fractal_strategy import (
    MultiTFFractalStrategy, MultiTFFractalStrategyExecutor
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(PROJECT_ROOT / "mtf_live_trading.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

SYMBOL = "ETHUSDC"
CHECK_INTERVAL = 60
DEFAULT_PID_FILE = PROJECT_ROOT / "mtf_live_daemon.pid"
DEFAULT_SUPPORT_LEVELS = [2300, 2270, 2240, 2210, 2180]
DEFAULT_RESISTANCE_LEVELS = [2400, 2450, 2500, 2550, 2600]
SUPPORT_THRESHOLD = 15.0
RESISTANCE_THRESHOLD = 15.0
PROBE_RATIO = 0.40
CONFIRM_RATIO = 0.60
PROFIT_LOSS_RATIO = 1.5
LEVERAGE = 20
INVESTMENT_RATIO = 0.10
MAX_LOSS_PER_TRADE_PCT = 0.02
MAX_CONSECUTIVE_STOPS = 3
MAX_DAILY_LOSS_PCT = 0.05
TRENDLINE_PERIOD = 20
STOP_OFFSET = 5.0


def daemonize(pid_file):
    """将当前进程以守护进程方式重新启动（跨平台）

    - Linux: start_new_session=True 脱离终端
    - Windows: DETACHED_PROCESS + CREATE_NEW_PROCESS_GROUP 脱离控制台
    """
    args = [sys.executable] + sys.argv
    args = [a for a in args if a not in ("--daemon", "-d")]

    kwargs: dict = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
        "close_fds": True,
    }

    if platform.system() == "Windows":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    proc = subprocess.Popen(args, **kwargs)

    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(proc.pid))

    print(f"守护进程已启动")
    print(f"  PID:      {proc.pid}")
    print(f"  PID文件:  {pid_file}")
    print(f"  日志文件:  {PROJECT_ROOT / 'mtf_live_trading.log'}")
    print(f"  停止命令:  python run_ethusdc_mtf_live.py --stop")


def stop_daemon(pid_file):
    """停止正在运行的守护进程"""
    if not pid_file.exists():
        print("未找到 PID 文件，守护进程可能未运行")
        return False

    try:
        pid = int(pid_file.read_text().strip())
    except (ValueError, OSError):
        print("PID 文件无效，已删除")
        pid_file.unlink(missing_ok=True)
        return False

    try:
        if platform.system() == "Windows":
            os.kill(pid, signal.SIGBREAK)
        else:
            os.kill(pid, signal.SIGTERM)
        print(f"已向 PID {pid} 发送终止信号")
        pid_file.unlink(missing_ok=True)
        return True
    except OSError:
        print(f"进程 PID {pid} 不存在，已删除 PID 文件")
        pid_file.unlink(missing_ok=True)
        return False


def check_daemon_status(pid_file):
    """检查守护进程运行状态"""
    if not pid_file.exists():
        print("守护进程未运行（无 PID 文件）")
        return

    try:
        pid = int(pid_file.read_text().strip())
    except (ValueError, OSError):
        print("PID 文件无效")
        return

    try:
        os.kill(pid, 0)
        print(f"守护进程运行中 (PID: {pid})")
    except OSError:
        print(f"守护进程未运行 (PID {pid} 已不存在)")
        pid_file.unlink(missing_ok=True)


class DryRunExecutor(MultiTFFractalStrategyExecutor):
    """仅生成信号不下单的测试执行器"""

    async def _execute_signal(self, signal):
        action = signal.get("action", "")
        ratio = signal.get("position_ratio", 0)
        logger.info(f"[DRY-RUN] >>> 信号: action={action}, ratio={ratio} (不执行下单)")
        self.strategy.update_position_from_signal(signal)


def parse_args():
    parser = argparse.ArgumentParser(description="多周期共振底分型预判策略 - 模拟盘/实盘交易")
    parser.add_argument("--real", action="store_true", help="使用实盘API（默认使用模拟盘testnet）")
    parser.add_argument("--dry-run", action="store_true", help="仅生成信号不下单（调试模式）")
    parser.add_argument("--paper", action="store_true", help="本地纸交易模式（本地模拟成交，不依赖交易所）")
    parser.add_argument("--commission-rate", type=float, default=0.0004, help="纸交易手续费率 (默认: 0.04%%)")
    parser.add_argument("--support-levels", type=str, default=None,
                       help="关键支撑位列表，逗号分隔，如2300,2250,2200")
    parser.add_argument("--resistance-levels", type=str, default=None,
                       help="关键阻力位列表，逗号分隔，如2400,2450,2500")
    parser.add_argument("--dingtalk-token", type=str, default=None,
                       help="钉钉机器人 Webhook access_token")
    parser.add_argument("--dingtalk-secret", type=str, default=None,
                       help="钉钉机器人加签密钥")
    parser.add_argument("--no-notify", action="store_true",
                       help="禁用钉钉通知")
    parser.add_argument("--no-debug-signal", action="store_true",
                       help="关闭信号诊断日志（默认开启）")
    parser.add_argument("--debug-interval", type=int, default=6,
                       help="信号诊断日志输出间隔（默认每6个周期输出一次，1=每个周期）")
    parser.add_argument("--daemon", "-d", action="store_true",
                       help="以守护进程模式在后台运行（关闭命令行不影响运行）")
    parser.add_argument("--stop", action="store_true",
                       help="停止正在运行的守护进程")
    parser.add_argument("--status", action="store_true",
                       help="查看守护进程运行状态")
    parser.add_argument("--pid-file", type=str, default=str(DEFAULT_PID_FILE),
                       help=f"PID 文件路径 (默认: {DEFAULT_PID_FILE})")
    return parser.parse_args()


async def main(args):
    is_simulated = not args.real
    mode = "实盘" if args.real else "模拟盘"
    if args.dry_run:
        mode = "DRY-RUN(仅信号)"

    support_levels = DEFAULT_SUPPORT_LEVELS
    if args.support_levels:
        try:
            support_levels = [float(x.strip()) for x in args.support_levels.split(",")]
        except ValueError:
            logger.error(f"无效的支撑位参数: {args.support_levels}")
            return

    resistance_levels = DEFAULT_RESISTANCE_LEVELS
    if args.resistance_levels:
        try:
            resistance_levels = [float(x.strip()) for x in args.resistance_levels.split(",")]
        except ValueError:
            logger.error(f"无效的阻力位参数: {args.resistance_levels}")
            return

    print()
    print("=" * 65)
    print(f"  多周期共振分型预判策略 - 多空双向 - {mode}交易")
    print("=" * 65)
    print(f"  交易对:      {SYMBOL}")
    print(f"  K线周期:     4h + 30m 双周期")
    print(f"  检查间隔:     {CHECK_INTERVAL}秒")
    print(f"  关键支撑位:   {support_levels}")
    print(f"  关键阻力位:   {resistance_levels}")
    print(f"  支撑阈值:     ±{SUPPORT_THRESHOLD}点")
    print(f"  阻力阈值:     ±{RESISTANCE_THRESHOLD}点")
    print(f"  试探仓位:     {PROBE_RATIO*100:.0f}%")
    print(f"  确认加仓:     {CONFIRM_RATIO*100:.0f}%")
    print(f"  止盈盈亏比:   {PROFIT_LOSS_RATIO}")
    print(f"  杠杆倍数:     {LEVERAGE}x")
    print(f"  单笔亏损上限: {MAX_LOSS_PER_TRADE_PCT*100:.0f}%")
    print(f"  连续止损上限: {MAX_CONSECUTIVE_STOPS}次")
    print(f"  日亏损上限:   {MAX_DAILY_LOSS_PCT*100:.0f}%")
    print("=" * 65)

    if args.real:
        print()
        print("  WARNING  实盘模式！将使用真实资金交易！")
        confirm = input("  输入 'YES' 确认继续: ")
        if confirm != "YES":
            print("  已取消")
            return

    print()
    print("  启动中...")
    print()

    if args.paper:
        client = PaperTradingClient(
            commission_rate=args.commission_rate,
            is_simulated=True,
        )
        await client.initialize()
        is_simulated = True
        logger.info(f"纸交易模式已启用: 手续费={args.commission_rate*100:.2f}%")
    elif args.dry_run:
        client = BinanceRestClient(is_simulated=is_simulated)
        logger.info("DRY-RUN模式: 仅生成信号，不执行下单")
    else:
        client = BinanceRestClient(is_simulated=is_simulated)
        logger.info(f"交易模式: {'实盘' if not is_simulated else '模拟盘(testnet)'}")

    notifier = None
    if not args.no_notify:
        dt_token = args.dingtalk_token or binance_config.dingtalk_access_token
        dt_secret = args.dingtalk_secret or binance_config.dingtalk_secret
        if dt_token and dt_secret:
            try:
                notifier = DingTalkNotifier(access_token=dt_token, secret=dt_secret)
                logger.info("钉钉通知已启用")
            except Exception as e:
                logger.warning(f"钉钉通知初始化失败: {e}")

    executor_cls = DryRunExecutor if args.dry_run else MultiTFFractalStrategyExecutor
    executor = executor_cls(
        client=client,
        notifier=notifier,
        symbol=SYMBOL,
        check_interval=CHECK_INTERVAL,
        support_levels=support_levels,
        support_threshold=SUPPORT_THRESHOLD,
        resistance_levels=resistance_levels,
        resistance_threshold=RESISTANCE_THRESHOLD,
        profit_loss_ratio=PROFIT_LOSS_RATIO,
        probe_ratio=PROBE_RATIO,
        confirm_ratio=CONFIRM_RATIO,
        leverage=LEVERAGE,
        investment_ratio=INVESTMENT_RATIO,
        max_loss_per_trade_pct=MAX_LOSS_PER_TRADE_PCT,
        max_consecutive_stops=MAX_CONSECUTIVE_STOPS,
        max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
        trendline_period=TRENDLINE_PERIOD,
        stop_offset=STOP_OFFSET,
        debug_signal=not args.no_debug_signal,
        debug_interval=args.debug_interval,
    )

    stop_event = asyncio.Event()

    def shutdown_handler(sig, frame):
        logger.info(f"收到退出信号: {sig}")
        stop_event.set()

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        task = asyncio.create_task(executor.start())
        await stop_event.wait()
        logger.info("正在停止执行器...")
        await executor.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    except Exception as e:
        logger.error(f"运行异常: {e}", exc_info=True)
    finally:
        await client.close()
        logger.info("执行器已完全停止")


if __name__ == "__main__":
    args = parse_args()
    pid_file = Path(args.pid_file)

    if args.stop:
        stop_daemon(pid_file)
        sys.exit(0)

    if args.status:
        check_daemon_status(pid_file)
        sys.exit(0)

    if args.daemon:
        daemonize(pid_file)
        sys.exit(0)

    asyncio.run(main(args))