"""
多周期共振分型策略V2 - ETHUSDC 4小时+30分钟回测脚本
Multi-TF Fractal Strategy Backtest

特性：
- 4小时K线检测支撑/阻力区域+Chan分型
- 30分钟K线检测多类确认信号
- 双向对称交易（做多+做空）
- ATR动态止损
- 试探入场+确认加仓两阶段建仓

使用方法:
    python run_ethusdc_mtf_backtest.py
"""

import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
BACKTEST_SCRIPT = PROJECT_ROOT / "trading_system" / "backtest" / "run_backtest.py"


def get_date_range(days=60):
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    return start_date, end_date


def main():
    print("=" * 80)
    print("🚀 多周期共振分型策略 - ETHUSDC 4h+30m 回测")
    print("   特性: Chan分型引擎 + ATR动态止损 + 双向对称")
    print("=" * 80)

    if not BACKTEST_SCRIPT.exists():
        print(f"❌ 错误: 找不到回测脚本 {BACKTEST_SCRIPT}")
        sys.exit(1)

    SYMBOL = "ETHUSDC"
    INTERVAL = "4h"
    INITIAL_BALANCE = 10000

    start_date, end_date = get_date_range(days=90)

    INVESTMENT_RATIO = 0.50
    LEVERAGE = 10

    LONG_STOP_LOSS_MULTIPLIER = 1.50
    SHORT_STOP_LOSS_MULTIPLIER = 0.70

    SUPPORT_LEVELS = ""
    RESISTANCE_LEVELS = ""

    ENABLE_EARLY_ENTRY = True
    ENABLE_EARLY_SHORT_ENTRY = True
    EARLY_ENTRY_MIN_CONFIDENCE = 0.6
    EARLY_ENTRY_RATIO = 0.40
    EARLY_SHORT_ENTRY_RATIO = 0.40
    MIN_EARLY_ENTRY_CONDITIONS = 2

    cmd = [
        sys.executable,
        str(BACKTEST_SCRIPT),

        "--symbol", SYMBOL,
        "--interval", INTERVAL,
        "--initial-balance", str(INITIAL_BALANCE),

        "--start-date", start_date,
        "--end-date", end_date,

        "--investment-ratio", str(INVESTMENT_RATIO),
        "--leverage", str(LEVERAGE),

        "--long-stop-loss-multiplier", str(LONG_STOP_LOSS_MULTIPLIER),
        "--short-stop-loss-multiplier", str(SHORT_STOP_LOSS_MULTIPLIER),

        "--strategy-version", "mtf",

        "--enable-early-entry",
        "--enable-early-short-entry",
        "--early-entry-min-confidence", str(EARLY_ENTRY_MIN_CONFIDENCE),
        "--min-early-entry-conditions", str(MIN_EARLY_ENTRY_CONDITIONS),
    ]
    if SUPPORT_LEVELS.strip():
        cmd.extend(["--support-levels", SUPPORT_LEVELS])
    if RESISTANCE_LEVELS.strip():
        cmd.extend(["--resistance-levels", RESISTANCE_LEVELS])

    print("\n📊 配置信息:")
    print(f"  {'='*60}")
    print(f"  📌 交易对: {SYMBOL}")
    print(f"  📅 K线周期: {INTERVAL} + 30m (多周期)")
    print(f"  💰 初始资金: ${INITIAL_BALANCE:,}")
    print(f"  📆 数据范围: {start_date} ~ {end_date} (约90天)")
    print(f"  {'='*60}")
    print(f"\n⚙️  仓位管理:")
    print(f"  ├─ 投入比例: {INVESTMENT_RATIO*100:.0f}%")
    print(f"  ├─ 杠杆倍数: {LEVERAGE}x")
    print(f"  ├─ 提前入场仓位: {EARLY_ENTRY_RATIO*100:.0f}% (首次)")
    print(f"  ├─ 标准加仓仓位: {(1.0-EARLY_ENTRY_RATIO)*100:.0f}% (K3确认)")
    print(f"\n🎯 策略特性:")
    print(f"  ✅ Chan分型引擎 (4h)")
    print(f"  ✅ ATR动态止损 (ATR×3.5)")
    print(f"  ✅ 双向对称交易")
    print(f"  ✅ 日线趋势过滤")
    print(f"  ✅ 成交量萎缩过滤")
    print(f"  ✅ 30m 4信号确认")
    print(f"  ✅ 15m 提前做多入场（底分型预判）")
    print(f"  ✅ 15m 提前做空入场（顶分型预判）")
    if ENABLE_EARLY_ENTRY:
        print(f"  ├─ 提前做多仓位: {EARLY_ENTRY_RATIO*100:.0f}%")
    if ENABLE_EARLY_SHORT_ENTRY:
        print(f"  ├─ 提前做空仓位: {EARLY_SHORT_ENTRY_RATIO*100:.0f}%")
    print(f"  └─ 入场条件满足数: >= {MIN_EARLY_ENTRY_CONDITIONS}/3 (一买/二买/趋势)")
    print(f"\n📉 支撑位: {SUPPORT_LEVELS if SUPPORT_LEVELS.strip() else '自动计算'}")
    print(f"📈 阻力位: {RESISTANCE_LEVELS if RESISTANCE_LEVELS.strip() else '自动计算'}")
    print(f"\n{'-'*80}")
    print("开始运行回测...\n")

    print("执行命令:")
    print(" ".join(cmd))
    print()

    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            check=False,
        )

        if result.returncode == 0:
            print("\n" + "=" * 80)
            print("✅ 回测成功完成！")
            print("=" * 80)

            print(f"\n📈 生成的图表和报告:")
            charts_dir = PROJECT_ROOT / "trading_system" / "backtest" / "charts"
            backtest_dir = PROJECT_ROOT / "trading_system" / "backtest"

            print(f"  📊 缠论图表: {backtest_dir / 'backtest_plot.png'}")
            print(f"  📈 权益曲线: {charts_dir / 'equity_curve.png'}")
            print(f"  📉 收益率图: {charts_dir / 'returns.png'}")
            print(f"  📉 回撤图:   {charts_dir / 'drawdown.png'}")
            print(f"\n💾 结果数据: {backtest_dir / 'chan_strategy_backtest_results.json'}")

        else:
            print(f"\n❌ 回测失败，退出码: {result.returncode}")
            sys.exit(result.returncode)

    except Exception as e:
        print(f"\n❌ 运行出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()