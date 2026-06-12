"""
Crypto_Chan_4H_Master_v1 - 回测入口脚本
基于缠论多周期（4H/1H/15M）的加密货币双向持仓交易系统。

使用方法:
    python run_ethusdc_mtf_backtest.py
    python run_ethusdc_mtf_backtest.py --capital 20000 --days 180
    python run_ethusdc_mtf_backtest.py --data-dir trading_system/data/binance_history
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def run_crypto_chan_strategy(args):
    """
    运行 Crypto_Chan_4H_Master_v1 策略回测

    数据源优先级：
    1. --data-dir 指定的本地 CSV 文件
    2. CCXT 库（需安装 ccxt，自动连接 Binance 获取数据）

    Args:
        args: argparse.Namespace，包含 symbol, capital, days, data_dir 等参数
    """
    from trading_system.strategies.mtf_fractal_strategy import (
        StrategyConfigRoot,
        CryptoChan4HBacktestEngine,
        BacktestReportV2,
    )

    print("=" * 80)
    print("🔮 Crypto_Chan_4H_Master_v1 - 缠论 4H/1H/15M 策略回测")
    print("   特性: Chan分型/笔/中枢/背驰 + 执行指令引擎 + 双向对冲")
    print("=" * 80)

    SYMBOL = args.symbol if hasattr(args, 'symbol') and args.symbol else "ETH/USDC"
    CAPITAL = args.capital

    print(f"\n📊 配置信息:")
    print(f"  {'='*60}")
    print(f"  📌 交易对: {SYMBOL}")
    print(f"  📅 K线周期: 4H (趋势) + 1H (结构) + 15M (入场)")
    print(f"  💰 初始资金: ${CAPITAL:,}")
    print(f"  🎯 策略模块: 缠论中枢/背驰 + 执行指令引擎 + 双向对冲")
    print(f"  {'='*60}")

    import json
    import logging
    logger = logging.getLogger(__name__)

    # ── 内嵌策略 JSON 配置 ──
    # 直接在此构建完整的策略配置，无需外部 JSON 文件
    # 所有参数与 Crypto_Chan_4H_Master_v1 策略设计文档一致
    json_config = json.dumps({
        "strategy_metadata": {
            "name": "Crypto_Chan_4H_Master_v1",
            "version": "1.0",
            "description": "基于缠论4H/1H/15M级别的交易系统",
            "base_currency": "USDC",
            "trading_pairs": [SYMBOL],
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
    # 将 JSON 反序列化为强类型配置对象，便于策略内部使用
    config = StrategyConfigRoot.from_json(json_config)

    # ── 数据加载（CSV 优先，CCXT 兜底）──
    import pandas as pd
    data_dir = args.data_dir if hasattr(args, 'data_dir') and args.data_dir else None

    if data_dir:
        # 方案 A：从本地 CSV 文件加载历史数据（推荐用于回测）
        data_path = Path(data_dir)
        symbol_file = SYMBOL.replace("/", "").replace("USDC", "USDC")  # ETH/USDC → ETHUSDC
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
                print(f"  📂 加载 {tf}: {len(dfs[tf])} 行 from {fp}")

        if "4h" in dfs:
            # 创建回测引擎并运行
            engine = CryptoChan4HBacktestEngine(config, CAPITAL)
            report = engine.run(
                df_4h=dfs.get("4h", pd.DataFrame()),
                df_1h=dfs.get("1h", pd.DataFrame()),
                df_15m=dfs.get("15m", pd.DataFrame()),
                df_daily=dfs.get("1d", pd.DataFrame()),
            )
            report.print_report()  # 终端打印完整回测报告

            # 将回测结果持久化为 JSON，便于后续分析
            import json as json_mod
            results_file = PROJECT_ROOT / "trading_system" / "data" / "binance_history" / "crypto_chan_backtest_results.json"
            results_file.parent.mkdir(parents=True, exist_ok=True)
            with open(results_file, "w") as f:
                json_mod.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
            print(f"\n💾 结果已保存: {results_file}")
            return  # CSV 数据成功加载并运行，直接返回

    # 方案 B：通过 CCXT 从交易所实时获取数据（作为兜底方案）
    try:
        from trading_system.data.market_data import CCXTDataProvider
        provider = CCXTDataProvider("binance")
        dfs = provider.fetch_multiple_timeframes(SYMBOL, ["4h", "1h", "15m", "1d"], limit=500)
        engine = CryptoChan4HBacktestEngine(config, CAPITAL)
        report = engine.run(
            df_4h=dfs.get("4h", pd.DataFrame()),
            df_1h=dfs.get("1h", pd.DataFrame()),
            df_15m=dfs.get("15m", pd.DataFrame()),
            df_daily=dfs.get("1d", pd.DataFrame()),
        )
        report.print_report()
    except ImportError:
        print("❌ CCXT 未安装且未指定 data_dir，无法获取数据")
        print("   请安装: pip install ccxt")
        print("   或指定: --data-dir trading_system/data/binance_history")
        sys.exit(1)


def main():
    """命令行入口：解析参数并运行 Crypto_Chan_4H_Master_v1 策略回测"""
    parser = argparse.ArgumentParser(
        description="Crypto_Chan_4H_Master_v1 - 缠论多周期 ETHUSDC 回测",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_ethusdc_mtf_backtest.py
  python run_ethusdc_mtf_backtest.py --capital 20000 --days 180
  python run_ethusdc_mtf_backtest.py --data-dir trading_system/data/binance_history
        """
    )
    parser.add_argument(
        "--symbol", type=str, default=None,
        help="交易对 (默认: ETH/USDC)"
    )
    parser.add_argument(
        "--capital", type=float, default=10000,
        help="初始资金 (默认: 10000)"
    )
    parser.add_argument(
        "--days", type=int, default=90,
        help="回测天数 (默认: 90)"
    )
    parser.add_argument(
        "--data-dir", type=str, default=None,
        help="本地CSV数据目录"
    )

    args = parser.parse_args()
    run_crypto_chan_strategy(args)


if __name__ == "__main__":
    main()