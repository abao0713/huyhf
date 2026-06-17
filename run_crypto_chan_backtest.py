"""
Crypto_Chan_4H_Master_v1 策略回测脚本

基于缠论 4H/1H/15M 多周期分析，支持双向持仓与动态对冲。

使用方法:
    python run_crypto_chan_backtest.py
    python run_crypto_chan_backtest.py --symbol ETH/USDC --capital 10000 --days 90
    python run_crypto_chan_backtest.py --symbol ETH/USDC --data-dir trading_system/data/binance_history
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading_system.strategies.mtf_fractal_strategy import (
    StrategyConfigRoot,
    CryptoChan4HMasterStrategy,
    CryptoChan4HBacktestEngine,
    BacktestReportV2,
    generate_backtest_report,
    CCXTDataProvider,
)
from trading_system.strategies.chan_backtest_chart import ChanBacktestChart

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
# 静默缠论和策略模块的INFO日志，大幅减少IO开销
# chan_strategy 的 "数据长度不足" 属于正常情况，设为 ERROR 级别完全静默
for _mod in ["trading_system.strategies.chan_strategy",
             "trading_system.strategies.mtf_fractal_strategy",
             "trading_system.strategies.chan_first_buy_strategy"]:
    logging.getLogger(_mod).setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

DEFAULT_DATA_DIR = PROJECT_ROOT / "trading_system" / "data" / "binance_history"
DEFAULT_RESULTS_FILE = PROJECT_ROOT / "trading_system" / "data" / "binance_history" / "crypto_chan_backtest_results.json"


def build_config(symbol: str) -> StrategyConfigRoot:
    """构建策略配置（内嵌默认 JSON 配置）"""
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
            "atr": {
                "period": 14,
                "source": "4h",
                "multiplier_stop_loss": 1.5,
                "multiplier_take_profit": 3.0
            },
            "macd": {
                "fast": 12,
                "slow": 26,
                "signal": 9
            }
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
                "trend_mode": {
                    "main_position": "100%",
                    "hedge_position": "0-30%",
                    "trigger": "1h divergence against 4h trend"
                },
                "range_mode": {
                    "upper_bound_short": "50%",
                    "lower_bound_long": "50%",
                    "net_exposure": "0%",
                    "exit_rule": "Close opposite side if price breaks 4h central pivot."
                }
            },
            "sizing": {
                "method": "atr_based",
                "risk_per_trade_percent": 1.0,
                "calculation": "Position_Size = (Account_Equity * Risk%) / (ATR_4h * 1.5)"
            }
        },
        "execution_directives": [
            {
                "id": "RULE_001",
                "priority": 1,
                "condition": "Daily_Trend == UP AND 4h_Type_2B_Confirmed",
                "action": "OPEN_LONG_MAIN_POSITION",
                "params": {"size": "full", "sl": "atr_1.5"}
            },
            {
                "id": "RULE_002",
                "priority": 1,
                "condition": "Daily_Trend == DOWN AND 4h_Type_2S_Confirmed",
                "action": "OPEN_SHORT_MAIN_POSITION",
                "params": {"size": "full", "sl": "atr_1.5"}
            },
            {
                "id": "RULE_003",
                "priority": 2,
                "condition": "Funding_Rate > 0.001 AND Action == OPEN_LONG",
                "action": "REJECT_ENTRY",
                "params": {"reason": "Funding rate too high, risk of long squeeze."}
            },
            {
                "id": "RULE_004",
                "priority": 3,
                "condition": "Price_Breaks_4h_Pivot_Upwards AND Range_Mode == TRUE",
                "action": "CLOSE_SHORT_AND_OPEN_LONG",
                "params": {"transition": "from_range_to_trend"}
            },
            {
                "id": "RULE_005",
                "priority": 4,
                "condition": "Weekday IN ['Sat', 'Sun']",
                "action": "ADJUST_LEVERAGE_AND_SIZE",
                "params": {"max_leverage": 5, "size_multiplier": 0.5}
            }
        ]
    }
    return StrategyConfigRoot.from_dict(json_config)


def load_csv_data(symbol: str, data_dir: Path, start_date: Optional[str] = None,
                  end_date: Optional[str] = None) -> dict:
    """从本地 CSV 文件加载多周期数据"""
    # 处理符号格式: ETH/USDC -> ETHUSDC
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
            logger.info(f"加载 {tf}: {len(df)} 行 from {fp}")
        else:
            logger.warning(f"文件不存在: {fp}")
    # 日期过滤
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


def main():
    parser = argparse.ArgumentParser(
        description="Crypto_Chan_4H_Master_v1 策略回测",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_crypto_chan_backtest.py
  python run_crypto_chan_backtest.py --symbol ETH/USDC --capital 10000 --days 90
  python run_crypto_chan_backtest.py --symbol ETH/USDC --data-dir trading_system/data/binance_history
  python run_crypto_chan_backtest.py --symbol ETH/USDC --start 2026-01-01 --end 2026-06-01
        """
    )
    parser.add_argument("--symbol", default="ETH/USDC", help="交易对 (默认: ETH/USDC)")
    parser.add_argument("--capital", type=float, default=10000.0, help="初始资金 (默认: 10000)")
    parser.add_argument("--commission", type=float, default=0.0004, help="手续费率 (默认: 0.04%%)")
    parser.add_argument("--days", type=int, default=90, help="回测天数（CCXT模式）(默认: 90)")
    parser.add_argument("--start", default=None, help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="结束日期 YYYY-MM-DD")
    parser.add_argument("--data-dir", default=None, help="本地CSV数据目录")
    parser.add_argument("--output", default=None, help="结果输出JSON路径")
    parser.add_argument("--no-progress", action="store_true", help="禁用进度条")
    parser.add_argument("--use-ccxt", action="store_true", help="强制使用CCXT获取数据")
    parser.add_argument("--fast", action="store_true", help="快速回测模式（跳过冗余计算，提升4-6倍速度）")
    parser.add_argument("--plot", action="store_true", default=True, help="生成回测可视化图表（默认开启）")
    parser.add_argument("--no-plot", action="store_true", help="不生成回测可视化图表")
    parser.add_argument("--plot-output", default=None, help="图表输出路径")
    parser.add_argument("--no-show", action="store_true", help="不显示图表（仅保存）")
    args = parser.parse_args()

    print("=" * 70)
    print("  Crypto_Chan_4H_Master_v1 策略回测")
    print("  基于缠论 4H/1H/15M 多周期分析")
    print("=" * 70)
    print(f"  交易对:       {args.symbol}")
    print(f"  初始资金:     ${args.capital:,.2f}")
    print(f"  手续费率:     {args.commission*100:.2f}%")
    if args.fast:
        print(f"  模式:         快速回测（跳过冗余计算）")
    if args.data_dir:
        print(f"  数据源:       本地CSV ({args.data_dir})")
    else:
        print(f"  数据源:       CCXT (Binance)")
    if args.start and args.end:
        print(f"  日期范围:     {args.start} ~ {args.end}")
    else:
        print(f"  回测天数:     {args.days} 天")
    print("=" * 70)

    # 构建配置
    config = build_config(args.symbol)

    # 加载数据
    if args.data_dir:
        data_dir = Path(args.data_dir)
        if not data_dir.exists():
            print(f"错误: 数据目录不存在: {data_dir}")
            sys.exit(1)
        dfs = load_csv_data(args.symbol, data_dir, args.start, args.end)
    elif args.use_ccxt:
        dfs = load_ccxt_data(args.symbol, args.days)
    else:
        # 优先尝试本地数据，再尝试CCXT
        default_dir = DEFAULT_DATA_DIR
        if default_dir.exists():
            dfs = load_csv_data(args.symbol, default_dir, args.start, args.end)
            if not dfs.get("4h", pd.DataFrame()).empty:
                logger.info("使用本地CSV数据")
            else:
                logger.info("本地数据为空，尝试CCXT...")
                try:
                    dfs = load_ccxt_data(args.symbol, args.days)
                except ImportError:
                    print("错误: CCXT未安装且本地数据不可用")
                    print("请运行: pip install ccxt")
                    sys.exit(1)
        else:
            try:
                dfs = load_ccxt_data(args.symbol, args.days)
            except ImportError:
                print("错误: CCXT未安装且无本地数据")
                print("请运行: pip install ccxt 或使用 --data-dir 指定本地数据路径")
                sys.exit(1)

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

    # 运行回测
    print(f"\n开始回测...")
    engine = CryptoChan4HBacktestEngine(config, args.capital, args.commission)
    report = engine.run(
        df_4h=df_4h,
        df_1h=dfs.get("1h", pd.DataFrame()),
        df_15m=dfs.get("15m", pd.DataFrame()),
        df_daily=dfs.get("1d", pd.DataFrame()),
        progress=not args.no_progress,
    )

    # 打印报告
    report.print_report()

    # 保存结果
    output_path = args.output
    if output_path is None:
        output_path = DEFAULT_RESULTS_FILE
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report.to_dict(), f, indent=2, default=str)
    print(f"\n结果已保存: {output_path}")

    # 生成可视化图表（默认开启，--no-plot 可关闭）
    if args.plot and not args.no_plot:
        print("\n生成可视化图表...")
        plot_output = args.plot_output
        if plot_output is None:
            plot_dir = PROJECT_ROOT / "trading_system" / "backtest"
            plot_dir.mkdir(parents=True, exist_ok=True)
            plot_output = plot_dir / f"{args.symbol.replace('/', '')}_backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        
        try:
            # 从回测引擎提取缠论分析数据
            chan_4h = engine.strategy._chan_4h
            macd_4h = engine.strategy._macd_4h

            # 从 trade_history 提取买卖点信号
            buy_sell_points = []
            for trade in report.trade_history:
                action = trade.get('action', '')
                price = trade.get('price', 0)
                timestamp = trade.get('timestamp')
                if not price or not timestamp:
                    continue

                # 根据 action 映射信号类型
                signal_type = None
                if 'OPEN_LONG' in action or action == 'BUY':
                    reason = trade.get('reason', '')
                    if 'type_2b' in reason or '2B' in reason:
                        signal_type = '2B'
                    elif 'type_2' in reason or '二买' in reason:
                        signal_type = '2B'
                    else:
                        signal_type = '1B'
                elif 'OPEN_SHORT' in action or action == 'SELL':
                    reason = trade.get('reason', '')
                    if 'type_2' in reason or '二卖' in reason:
                        signal_type = '2S'
                    else:
                        signal_type = '1S'
                else:
                    continue

                # 找到对应 K 线索引
                if isinstance(timestamp, str):
                    ts = pd.Timestamp(timestamp)
                else:
                    ts = timestamp

                idx = None
                for i, row in df_4h.reset_index(drop=True).iterrows():
                    if 'open_time' in row:
                        ot = row['open_time']
                        if isinstance(ot, str):
                            ot = pd.Timestamp(ot)
                        if ot >= ts:
                            idx = i
                            break

                if idx is not None:
                    buy_sell_points.append({
                        'type': signal_type,
                        'idx': idx,
                        'price': price,
                    })

            # 构建背驰连线数据
            divergence_lines = []
            beichi_pens = []
            chan_pens = getattr(chan_4h, 'pens', [])
            for pen in chan_pens:
                if hasattr(pen, 'macd_area') and pen.macd_area:
                    beichi_pens.append(pen)
            if len(beichi_pens) >= 2:
                for j in range(1, len(beichi_pens)):
                    p0 = beichi_pens[j - 1]
                    p1 = beichi_pens[j]
                    if p0.direction == p1.direction:
                        macd_ratio = 0.0
                        if p0.macd_area != 0:
                            macd_ratio = abs(p1.macd_area / p0.macd_area)
                        if macd_ratio < 0.85 and macd_ratio > 0:
                            div_type = 'bull' if p1.direction == 'down' else 'bear'
                            try:
                                divergence_lines.append({
                                    'type': div_type,
                                    'price_idx1': p0.end_fractal.idx,
                                    'price_idx2': p1.end_fractal.idx,
                                    'macd_idx1': p0.end_fractal.idx,
                                    'macd_idx2': p1.end_fractal.idx,
                                })
                            except Exception:
                                pass

            # 生成图表
            chart = ChanBacktestChart(
                df=df_4h,
                fractals=getattr(chan_4h, 'fractals', []),
                pens=chan_pens,
                segments=getattr(chan_4h, 'segments', []),
                zhongshu_list=getattr(chan_4h, 'zhongshu_list', []),
                buy_sell_points=buy_sell_points,
                macd_data=macd_4h if macd_4h else {},
                divergence_lines=divergence_lines,
                title=f"缠论回测分析 - {args.symbol}",
            )
            chart.plot()
            saved_path = chart.save(str(plot_output), dpi=150)
            print(f"图表已保存: {saved_path}")

        except Exception as e:
            logger.error(f"生成图表失败: {e}")
            import traceback
            traceback.print_exc()

    return report


if __name__ == "__main__":
    main()
