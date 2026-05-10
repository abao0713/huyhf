"""
缠论策略V2 - ETHUSDC 30分钟回测脚本
分型驱动交易系统测试

特性：
- 分型识别触发交易（无需等待背驰）
- 动态加仓（最多3次）
- 即时反转（顶底分型切换时立即平仓+反向开仓）
- 完全配置化的参数系统

使用方法:
    python run_ethusdc_v2_backtest.py
    
配置说明:
    所有参数均可在此文件中修改，或通过命令行传递给 run_backtest.py
"""

import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent
BACKTEST_SCRIPT = PROJECT_ROOT / "trading_system" / "backtest" / "run_backtest.py"


def get_date_range(days=60):
    """
    获取日期范围
    
    Args:
        days: 天数，默认最近60天
    
    Returns:
        (start_date, end_date) 元组，格式为YYYY-MM-DD
    """
    today = datetime.now()
    end_date = today.strftime("%Y-%m-%d")
    start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    return start_date, end_date


def main():
    print("=" * 80)
    print("🚀 缠论策略V2 - ETHUSDC 30分钟回测")
    print("   特性: 分型驱动 + 动态加仓(最多3次) + 即时反转")
    print("=" * 80)
    
    # 检查脚本是否存在
    if not BACKTEST_SCRIPT.exists():
        print(f"❌ 错误: 找不到回测脚本 {BACKTEST_SCRIPT}")
        sys.exit(1)
    
    # ===== 配置参数（可自定义修改）=====
    
    # 基础配置
    SYMBOL = "ETHUSDC"
    INTERVAL = "30m"
    INITIAL_BALANCE = 10000  # 初始资金 $10,000
    
    # 数据范围（最近3个月 = 90天）
    start_date, end_date = get_date_range(days=90)
    
    # 仓位管理配置
    INVESTMENT_RATIO = 0.10      # 投入比例 10%
    LEVERAGE = 20                # 杠杆倍数 20x
    MAX_ADD_POSITIONS = 3         # 最大加仓次数
    
    # 止损配置
    LONG_STOP_LOSS_MULTIPLIER = 1.50   # 多单止损 = 爆仓价 × 150%
    SHORT_STOP_LOSS_MULTIPLIER = 0.70  # 空单止损 = 爆仓价 × 70%
    
    # 构建命令
    cmd = [
        sys.executable,
        str(BACKTEST_SCRIPT),
        
        # ===== 基础配置 =====
        "--symbol", SYMBOL,
        "--interval", INTERVAL,
        "--initial-balance", str(INITIAL_BALANCE),
        
        # ===== 日期范围 =====
        "--start-date", start_date,
        "--end-date", end_date,
        
        # ===== 仓位管理配置 =====
        "--investment-ratio", str(INVESTMENT_RATIO),
        "--leverage", str(LEVERAGE),
        
        # ===== 止损配置 =====
        "--long-stop-loss-multiplier", str(LONG_STOP_LOSS_MULTIPLIER),
        "--short-stop-loss-multiplier", str(SHORT_STOP_LOSS_MULTIPLIER),
        
        # ===== V2策略特有参数 =====
        "--strategy-version", "v2",
        "--max-add-positions", str(MAX_ADD_POSITIONS),
    ]
    
    # 打印配置信息
    print("\n📊 配置信息:")
    print(f"  {'='*60}")
    print(f"  📌 交易对: {SYMBOL}")
    print(f"  📅 K线周期: {INTERVAL}")
    print(f"  💰 初始资金: ${INITIAL_BALANCE:,}")
    print(f"  📆 数据范围: {start_date} ~ {end_date} (约3个月/90天)")
    print(f"  {'='*60}")
    print(f"\n⚙️  仓位管理:")
    print(f"  ├─ 投入比例: {INVESTMENT_RATIO*100:.0f}%")
    print(f"  ├─ 杠杆倍数: {LEVERAGE}x")
    print(f"  └─ 最大加仓: {MAX_ADD_POSITIONS}次")
    print(f"\n🛡️  止损配置:")
    print(f"  ├─ 多单止损: 爆仓价 × {LONG_STOP_LOSS_MULTIPLIER:.2f} ({LONG_STOP_LOSS_MULTIPLIER*100:.0f}%)")
    print(f"  └─ 空单止损: 爆仓价 × {SHORT_STOP_LOSS_MULTIPLIER:.2f} ({SHORT_STOP_LOSS_MULTIPLIER*100:.0f}%)")
    print(f"\n🎯 策略特性:")
    print(f"  ✅ 分型驱动（无需背驰确认）")
    print(f"  ✅ 动态加仓（最多{MAX_ADD_POSITIONS}次）")
    print(f"  ✅ 即时反转（反向分型立即平仓+开仓）")
    print(f"\n{'-'*80}")
    print("开始运行回测...\n")
    
    # 打印执行命令（调试用）
    print("执行命令:")
    print(" ".join(cmd))
    print()
    
    # 运行命令
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
            
            print(f"\n🔍 下一步操作:")
            print(f"  1. 查看图表分析交易表现")
            print(f"  2. 对比V1和V2的收益率、最大回撤、胜率等指标")
            print(f"  3. 根据回测结果调整参数（如加仓次数、杠杆等）")
            
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
