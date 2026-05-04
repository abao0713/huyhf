"""
快速测试脚本：运行ETHUSDT 30分钟回测（最近7天数据 + 连续循环交易配置）
"""

import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent
BACKTEST_SCRIPT = PROJECT_ROOT / "trading_system" / "backtest" / "run_backtest.py"


def get_date_range(days=7):
    """
    获取日期范围
    
    Args:
        days: 天数，默认最近7天
    
    Returns:
        (start_date, end_date) 元组，格式为YYYY-MM-DD
    """
    today = datetime.now()
    end_date = today.strftime("%Y-%m-%d")
    start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    return start_date, end_date


def main():
    print("=" * 70)
    print("运行 ETHUSDT 30分钟 回测（连续循环交易模式）")
    print("=" * 70)
    
    # 检查脚本是否存在
    if not BACKTEST_SCRIPT.exists():
        print(f"错误: 找不到回测脚本 {BACKTEST_SCRIPT}")
        sys.exit(1)
    
    # 获取日期范围（最近7天）
    start_date, end_date = get_date_range(days=60)
    
    # 构建命令
    cmd = [
        sys.executable,
        str(BACKTEST_SCRIPT),
        "--symbol", "ETHUSDT",
        "--interval", "30m",
        "--initial-balance", "10000",
        
        # 日期范围：最近7天
        "--start-date", start_date,
        "--end-date", end_date,
        
        # 连续循环交易配置（使用默认值）
        "--investment-ratio", "0.10",      # 10%投入
        "--leverage", "50",                  # 50倍杠杆
        "--long-stop-loss-multiplier", "1.20",   # 多单止损120%
        "--short-stop-loss-multiplier", "0.80",  # 空单止损80%
    ]
    
    print("\n执行命令:")
    print(" ".join(cmd))
    print("\n配置参数:")
    print("  交易对: ETHUSDT")
    print("  K线周期: 30m")
    print("  初始资金: $10,000")
    print(f"  数据范围: {start_date} ~ {end_date} ")
    print("  投入比例: 10%")
    print("  杠杆倍数: 50x")
    print("  多单止损: 爆仓价 × 120%")
    print("  空单止损: 爆仓价 × 80%")
    print("\n" + "-" * 70)
    print("开始运行回测...\n")
    
    # 运行命令
    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            check=False,
        )
        
        if result.returncode == 0:
            print("\n" + "=" * 70)
            print("✅ 回测成功完成！")
            print("=" * 70)
            print(f"\n📊 生成的图表文件:")
            print(f"   - 缠论图表: {PROJECT_ROOT / 'trading_system' / 'backtest' / 'backtest_plot.png'}")
            print(f"   - 权益曲线: {PROJECT_ROOT / 'trading_system' / 'backtest' / 'charts' / 'equity_curve.png'}")
            print(f"   - 收益率图: {PROJECT_ROOT / 'trading_system' / 'backtest' / 'charts' / 'returns.png'}")
            print(f"   - 回撤图: {PROJECT_ROOT / 'trading_system' / 'backtest' / 'charts' / 'drawdown.png'}")
        else:
            print(f"\n❌ 回测失败，退出码: {result.returncode}")
            sys.exit(result.returncode)
            
    except Exception as e:
        print(f"\n❌ 运行出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
