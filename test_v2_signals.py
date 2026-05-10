"""
快速测试 ChanStrategyV2 的信号生成
"""

import asyncio
from trading_system.strategies.chan_strategy_v2 import ChanStrategyV2


async def test_v2_signals():
    print("=" * 80)
    print("🧪 测试 ChanStrategyV2 信号生成")
    print("=" * 80)
    
    # 创建策略实例
    strategy = ChanStrategyV2(
        symbol="ETHUSDC",
        time_frame="30m",
        max_add_positions=3,
        investment_ratio=0.10,
        leverage=20,
        use_binance_client=False
    )
    
    # 初始化
    print("\n1️⃣ 初始化策略...")
    success = await strategy.initialize("ETHUSDC")
    
    if not success:
        print("❌ 初始化失败！")
        return
    
    print(f"✅ 初始化成功！")
    print(f"   分型数量: {len(strategy.fractals)}")
    print(f"   当前分型索引: {strategy._current_fractal_idx}")
    
    if strategy.fractals:
        print(f"\n前5个分型:")
        for i, fractal in enumerate(strategy.fractals[:5]):
            price = fractal.high if fractal.type == "top" else fractal.low
            print(f"   [{i}] {fractal.type.upper()} @ 索引{fractal.idx}, 价格{price:.2f}")
    
    # 测试生成多个信号
    print(f"\n2️⃣ 测试信号生成（模拟10次调用）:")
    for i in range(10):
        signal = strategy.generate_signal()
        
        action = signal.get("action", "HOLD")
        reason = signal.get("reason", "")
        
        if action != "HOLD":
            print(f"   调用{i+1}: 🎯 {action} - {reason}")
        else:
            print(f"   调用{i+1}: ⏸️ HOLD (已处理{strategy._current_fractal_idx}/{len(strategy.fractals)}个分型)")
        
        # 防止无限循环
        if strategy._current_fractal_idx >= len(strategy.fractals):
            print(f"\n✅ 所有分型都已处理完毕！")
            break
    
    # 显示最终状态
    status = strategy.get_status()
    print(f"\n3️⃣ 最终状态:")
    for key, value in status.items():
        print(f"   {key}: {value}")


if __name__ == "__main__":
    asyncio.run(test_v2_signals())
