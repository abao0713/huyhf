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
import signal
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading_system.okx.client import BinanceRestClient
from trading_system.okx.paper_client import PaperTradingClient
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
    return parser.parse_args()


async def main():
    args = parse_args()

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

    executor_cls = DryRunExecutor if args.dry_run else MultiTFFractalStrategyExecutor
    executor = executor_cls(
        client=client,
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
    asyncio.run(main())