import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading_system.strategies.backtest_engine import BacktestEngine, BacktestConfig
from trading_system.strategies.chan_strategy import ChanStrategy


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


DEFAULT_DATA_DIR = PROJECT_ROOT / "trading_system" / "data" / "binance_history"
DEFAULT_CHART_DIR = PROJECT_ROOT / "trading_system" / "backtest" / "charts"
DEFAULT_RESULTS_FILE = "chan_strategy_backtest_results.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Chan strategy backtest.")
    parser.add_argument("--symbol", default="ETHUSDC", help="Backtest symbol, for example ETHUSDC.")
    parser.add_argument("--interval", default="5m", help="Backtest interval, for example 5m.")
    parser.add_argument("--initial-balance", type=float, default=10000.0, help="Initial capital.")
    parser.add_argument("--commission", type=float, default=0.001, help="Commission ratio.")
    parser.add_argument("--slippage", type=float, default=0.0005, help="Slippage ratio.")
    parser.add_argument("--limit-5m", type=int, default=1000, help="Maximum 5m bars to use.")
    parser.add_argument("--limit-1d", type=int, default=200, help="Maximum daily bars to use.")
    parser.add_argument("--hg1", type=int, default=8, help="Fractal window for Chan strategy.")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="Directory with historical CSV files.")
    parser.add_argument("--chart-dir", default=str(DEFAULT_CHART_DIR), help="Directory for generated charts.")
    parser.add_argument("--results-file", default=DEFAULT_RESULTS_FILE, help="Output JSON filename.")
    parser.add_argument(
        "--load-existing",
        action="store_true",
        help="Load an existing result file instead of running a new backtest when available.",
    )
    
    # 连续循环交易配置参数
    parser.add_argument(
        "--investment-ratio", 
        type=float, 
        default=0.10,
        help="每次投入总金额的比例（默认0.10，即10%%）"
    )
    parser.add_argument(
        "--leverage", 
        type=int, 
        default=50,
        help="杠杆倍数（默认50倍）"
    )
    parser.add_argument(
        "--long-stop-loss-multiplier", 
        type=float, 
        default=1.20,
        help="多单止损 = 爆仓价格 × 此值（默认1.20，即120%%）"
    )
    parser.add_argument(
        "--short-stop-loss-multiplier", 
        type=float, 
        default=0.80,
        help="空单止损 = 爆仓价格 × 此值（默认0.80，即80%%）"
    )
    
    # 日期范围参数
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="开始日期，格式YYYY-MM-DD（例如：2026-04-25）"
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="结束日期，格式YYYY-MM-DD（例如：2026-05-02）"
    )
    
    return parser.parse_args()


def build_engine(
    data_dir: Path,
    initial_balance: float,
    commission: float,
    slippage: float,
    investment_ratio: float = 0.10,
    leverage: int = 50,
    long_stop_loss_multiplier: float = 1.20,
    short_stop_loss_multiplier: float = 0.80,
) -> BacktestEngine:
    """
    构建回测引擎
    
    Args:
        data_dir: 数据目录
        initial_balance: 初始资金
        commission: 手续费率
        slippage: 滑点比例
        investment_ratio: 每次投入总金额的比例（默认10%）
        leverage: 杠杆倍数（默认50倍）
        long_stop_loss_multiplier: 多单止损倍数（默认120%）
        short_stop_loss_multiplier: 空单止损倍数（默认80%）
    
    Returns:
        配置好的BacktestEngine实例
    """
    config = BacktestConfig(
        initial_balance=initial_balance,
        commission=commission,
        slippage=slippage,
        data_dir=str(data_dir),
        
        # 连续循环交易配置
        investment_ratio=investment_ratio,
        leverage=leverage,
        long_stop_loss_multiplier=long_stop_loss_multiplier,
        short_stop_loss_multiplier=short_stop_loss_multiplier,
    )
    
    return BacktestEngine(config=config)


def trim_data(data: Dict[str, pd.DataFrame], limit_interval: int, limit_1d: int, interval: str) -> Dict[str, pd.DataFrame]:
    trimmed = dict(data)
    if interval in trimmed and limit_interval > 0:
        trimmed[interval] = trimmed[interval].iloc[:limit_interval].copy()
    if "1d" in trimmed and limit_1d > 0:
        trimmed["1d"] = trimmed["1d"].iloc[:limit_1d].copy()
    return trimmed


def run_backtest(
    symbol: str = "ETHUSDC",
    interval: str = "30m",
    initial_balance: float = 10000.0,
    commission: float = 0.001,
    slippage: float = 0.0005,
    limit_interval: int = 1000,
    limit_1d: int = 200,
    hg1: int = 8,
    data_dir: Optional[Path] = None,
    chart_dir: Optional[Path] = None,
    results_file: str = DEFAULT_RESULTS_FILE,
    # 连续循环交易配置参数
    investment_ratio: float = 0.10,
    leverage: int = 50,
    long_stop_loss_multiplier: float = 1.20,
    short_stop_loss_multiplier: float = 0.80,
    # 日期范围参数
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a Chan strategy backtest and persist the result.
    
    Args:
        symbol: 交易对符号（默认ETHUSDC）
        interval: K线周期（默认30m）
        initial_balance: 初始资金（默认10000.0）
        commission: 手续费率（默认0.001）
        slippage: 滑点比例（默认0.0005）
        limit_interval: 周期K线数量限制（默认1000）
        limit_1d: 日线K线数量限制（默认200）
        hg1: 分型窗口大小（默认8）
        data_dir: 数据目录
        chart_dir: 图表目录
        results_file: 结果文件名
        investment_ratio: 每次投入总金额的比例（默认10%）
        leverage: 杠杆倍数（默认50倍）
        long_stop_loss_multiplier: 多单止损倍数（默认120%）
        short_stop_loss_multiplier: 空单止损倍数（默认80%）
        start_date: 开始日期，格式YYYY-MM-DD（可选）
        end_date: 结束日期，格式YYYY-MM-DD（可选）
    
    Returns:
        回测结果字典
    """
    data_dir = Path(data_dir or DEFAULT_DATA_DIR)
    chart_dir = Path(chart_dir or DEFAULT_CHART_DIR)

    logger.info("Starting Chan strategy backtest: symbol=%s, interval=%s", symbol, interval)
    
    # 记录日期范围信息
    if start_date or end_date:
        logger.info("Date range: %s to %s", start_date or "earliest", end_date or "latest")
    
    logger.info("Continuous trading config: investment_ratio=%.2f, leverage=%dx, "
                "long_stop=%.2f, short_stop=%.2f",
                investment_ratio, leverage, long_stop_loss_multiplier, short_stop_loss_multiplier)

    engine = build_engine(
        data_dir=data_dir,
        initial_balance=initial_balance,
        commission=commission,
        slippage=slippage,
        # 传递连续循环交易配置
        investment_ratio=investment_ratio,
        leverage=leverage,
        long_stop_loss_multiplier=long_stop_loss_multiplier,
        short_stop_loss_multiplier=short_stop_loss_multiplier,
    )

    data = engine.load_data(symbol, interval, start_date=start_date, end_date=end_date)
    if not data or interval not in data or "1d" not in data:
        logger.error("Historical data is incomplete, cannot run backtest.")
        return {}

    data = trim_data(data, limit_interval=limit_interval, limit_1d=limit_1d, interval=interval)
    logger.info(
        "Loaded data: %s=%s rows, 1d=%s rows",
        interval,
        len(data[interval]),
        len(data["1d"]),
    )

    strategy = ChanStrategy(symbol=symbol, hg1=hg1, use_binance_client=False)
    results = engine.run_backtest(data, strategy, interval)

    if not results:
        logger.warning("Backtest finished without results.")
        return {}

    engine.save_results(results, results_file)
    generate_report(results)
    generate_visualizations(results, chart_dir)
    return results


def generate_report(results: Dict[str, Any]) -> None:
    """打印简洁的回测摘要"""
    print("=" * 60)
    print("  缠论策略回测报告")
    print("=" * 60)
    print(f"\n收益表现:")
    print(f"  初始资金:       ${results['initial_balance']:,.2f}")
    print(f"  最终权益:       ${results['final_equity']:,.2f}")
    print(f"  净利润:         ${results.get('net_profit', 0.0):,.2f}")
    print(f"  总收益率:       {results.get('total_return_pct', results.get('total_return', 0.0)):.2f}%")
    print(f"\n风险指标:")
    print(f"  最大回撤:       {results.get('max_drawdown_pct', results.get('max_drawdown', 0.0)):.2f}%")
    print(f"  夏普比率:       {results['sharpe_ratio']:.2f}")
    print(f"\n交易统计:")
    print(f"  总交易次数:     {results['total_trades']}")
    print(f"  已平仓交易:     {results.get('closed_trades', 0)}")
    print(f"  胜率:           {results.get('win_rate_pct', results.get('win_rate', 0.0)):.2f}%")
    print(f"  盈利因子:       {results['profit_factor']:.2f}")
    print(f"  平均每笔盈亏:   ${results.get('avg_trade_profit', 0.0):,.2f}")
    print(f"  平均持仓时间:   {results.get('avg_holding_hours', results.get('avg_holding_time', 0.0)):.1f} 小时")
    print(f"\n资金状态:")
    print(f"  账户余额:       ${results.get('final_balance', results['initial_balance']):,.2f}")
    if results.get('final_long_position', 0) > 0:
        print(f"  做多持仓:       {results.get('final_long_position', 0):.4f} 均价 ${results.get('long_avg_price', 0):,.2f}")
    if results.get('final_short_position', 0) > 0:
        print(f"  做空持仓:       {results.get('final_short_position', 0):.4f} 均价 ${results.get('short_avg_price', 0):,.2f}")
    print("=" * 60)


def generate_visualizations(results: Dict[str, Any], chart_dir: Path) -> None:
    """Generate equity, returns and drawdown charts."""
    logger.info("Generating charts in %s", chart_dir)
    chart_dir.mkdir(parents=True, exist_ok=True)

    timestamps = [pd.Timestamp(ts) for ts in results["timestamps"]]
    equity_curve = results["equity_curve"]

    plt.figure(figsize=(12, 6))
    plt.plot(timestamps, equity_curve, label="权益曲线")
    plt.title("缠论策略权益曲线")
    plt.xlabel("日期")
    plt.ylabel("权益 ($)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(chart_dir / "equity_curve.png")
    plt.close()

    returns = [
        (equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1] * 100
        for i in range(1, len(equity_curve))
        if equity_curve[i - 1] != 0
    ]
    if returns:
        plt.figure(figsize=(12, 6))
        plt.plot(timestamps[1 : len(returns) + 1], returns, label="周期收益率")
        plt.title("缠论策略收益率")
        plt.xlabel("日期")
        plt.ylabel("收益率 (%)")
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.savefig(chart_dir / "returns.png")
        plt.close()

    equity_array = np.array(equity_curve, dtype=float)
    running_max = np.maximum.accumulate(equity_array)
    safe_running_max = np.where(running_max == 0, 1, running_max)
    drawdown = (equity_array - running_max) / safe_running_max * 100

    plt.figure(figsize=(12, 6))
    plt.plot(timestamps, drawdown, label="回撤")
    plt.title("缠论策略回撤")
    plt.xlabel("日期")
    plt.ylabel("回撤 (%)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(chart_dir / "drawdown.png")
    plt.close()


def load_results(results_path: Path) -> Optional[Dict[str, Any]]:
    if not results_path.exists():
        logger.error("Results file does not exist: %s", results_path)
        return None

    with results_path.open("r", encoding="utf-8") as file:
        results = json.load(file)

    if "timestamps" in results:
        results["timestamps"] = [pd.Timestamp(ts) for ts in results["timestamps"]]
    if "trades" in results:
        for trade in results["trades"]:
            if isinstance(trade.get("timestamp"), str):
                trade["timestamp"] = pd.Timestamp(trade["timestamp"])
    return results


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    chart_dir = Path(args.chart_dir)
    results_path = data_dir / args.results_file

    if args.load_existing:
        results = load_results(results_path)
        if results:
            generate_report(results)
            generate_visualizations(results, chart_dir)
        return

    results = run_backtest(
        symbol=args.symbol,
        interval=args.interval,
        initial_balance=args.initial_balance,
        commission=args.commission,
        slippage=args.slippage,
        limit_interval=args.limit_5m,
        limit_1d=args.limit_1d,
        hg1=args.hg1,
        data_dir=data_dir,
        chart_dir=chart_dir,
        results_file=args.results_file,
        # 传递连续循环交易配置参数
        investment_ratio=args.investment_ratio,
        leverage=args.leverage,
        long_stop_loss_multiplier=args.long_stop_loss_multiplier,
        short_stop_loss_multiplier=args.short_stop_loss_multiplier,
        # 传递日期范围参数
        start_date=args.start_date,
        end_date=args.end_date,
    )

    if not results:
        existing_results = load_results(results_path)
        if existing_results:
            generate_report(existing_results)
            generate_visualizations(existing_results, chart_dir)


if __name__ == "__main__":
    main()
