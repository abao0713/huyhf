"""
缠论V2策略 - Binance模拟盘实时交易

使用最佳风控参数: hg1=8, 杠杆20x, 投入10%, 加仓3次, 止损1.50/0.70

使用方法:
    python run_ethusdc_v2_live.py
    python run_ethusdc_v2_live.py --dry-run    # 只生成信号不下单
    python run_ethusdc_v2_live.py --real       # 实盘模式(需确认)
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
from trading_system.strategies.chan_strategy_v2 import ChanStrategyV2Executor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(PROJECT_ROOT / "v2_live_trading.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


SYMBOL = "ETHUSDC"
TIMEFRAME = "30m"
CHECK_INTERVAL = 60
INVESTMENT_RATIO = 0.10
LEVERAGE = 20
MAX_ADD_POSITIONS = 3
LONG_SL_MULTIPLIER = 1.50
SHORT_SL_MULTIPLIER = 0.70
HG1 = 8


class DryRunExecutor(ChanStrategyV2Executor):
    """仅生成信号不下单的测试执行器"""

    async def _execute_v2_signal(self, signal):
        action = signal.get("action", "")
        is_add = signal.get("is_add_position", False)
        logger.info(f"[DRY-RUN] >>> 信号: action={action}, add={is_add} (不执行下单)")
        self.strategy.update_position_state(signal=signal)


def parse_args():
    parser = argparse.ArgumentParser(description="缠论V2策略 - 模拟盘/实盘交易")
    parser.add_argument("--dry-run", action="store_true", help="仅生成信号不下单")
    parser.add_argument("--real", action="store_true", help="实盘模式（需API密钥）")
    return parser.parse_args()


async def main():
    args = parse_args()

    is_simulated = not args.real
    mode = "实盘" if args.real else "模拟盘"
    if args.dry_run:
        mode = "DRY-RUN(仅信号)"

    print()
    print("=" * 65)
    print(f"  缠论策略V2 - {mode}交易")
    print("=" * 65)
    print(f"  交易对:    {SYMBOL}")
    print(f"  K线周期:   {TIMEFRAME}")
    print(f"  检查间隔:   {CHECK_INTERVAL}秒")
    print(f"  投入比例:   {INVESTMENT_RATIO*100:.0f}%")
    print(f"  杠杆倍数:   {LEVERAGE}x")
    print(f"  最大加仓:   {MAX_ADD_POSITIONS}次")
    print(f"  分型窗口:   hg1={HG1}")
    print(f"  多单止损:   {LONG_SL_MULTIPLIER}x爆仓价")
    print(f"  空单止损:   {SHORT_SL_MULTIPLIER}x爆仓价")
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

    client = BinanceRestClient(is_simulated=is_simulated)

    if args.dry_run:
        executor = DryRunExecutor(
            client=client,
            symbol=SYMBOL,
            time_frame=TIMEFRAME,
            check_interval=CHECK_INTERVAL,
            investment_ratio=INVESTMENT_RATIO,
            leverage=LEVERAGE,
            max_add_positions=MAX_ADD_POSITIONS,
            long_sl_multiplier=LONG_SL_MULTIPLIER,
            short_sl_multiplier=SHORT_SL_MULTIPLIER,
            hg1=HG1,
        )
    else:
        executor = ChanStrategyV2Executor(
            client=client,
            symbol=SYMBOL,
            time_frame=TIMEFRAME,
            check_interval=CHECK_INTERVAL,
            investment_ratio=INVESTMENT_RATIO,
            leverage=LEVERAGE,
            max_add_positions=MAX_ADD_POSITIONS,
            long_sl_multiplier=LONG_SL_MULTIPLIER,
            short_sl_multiplier=SHORT_SL_MULTIPLIER,
            hg1=HG1,
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