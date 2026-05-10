"""
下载 ETHUSDC 30分钟K线数据（近3个月/90天）

使用方法:
    python download_ethusdc_90d.py

数据保存位置:
    - trading_system/data/binance_history/ETHUSDC_30m.csv (30分钟K线)
    - trading_system/data/binance_history/ETHUSDC_1d.csv   (日线K线)

注意:
    ETHUSDC 是币安的稳定币交易对，数据源与ETHUSDT相同
"""

import asyncio
from trading_system.okx.client import BinanceRestClient
from datetime import datetime, timedelta
import pandas as pd
import os


def get_date_range(days=90):
    """获取日期范围（默认90天 ≈ 3个月）"""
    today = datetime.now()
    end_date = today.strftime("%Y-%m-%d")
    start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    return start_date, end_date


async def download_ethusdc_90d():
    """使用分批下载功能获取ETHUSDC 90天K线数据"""

    start_date, end_date = get_date_range(days=90)
    
    print("=" * 80)
    print("📥 下载 ETHUSDC 完整K线数据（30分钟级别 + 日线）")
    print("=" * 80)
    print(f"\n📅 目标时间范围: {start_date} ~ {end_date}")
    print(f"   数据周期: 约3个月 (90天)")
    print(f"   预期30m K线数: ~4320根 (90天 × 24小时 × 2根/小时)")

    client = BinanceRestClient()

    try:
        start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
        end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)

        # ===== 1. 下载30分钟K线 =====
        print(f"\n{'='*80}")
        print("📊 第1步: 下载30分钟K线数据")
        print(f"{'='*80}")
        
        all_data_30m = []
        current_start = start_ts
        batch_num = 0
        BATCH_SIZE = 1000

        print(f"\n🔄 开始分批下载30m数据 (每批最多{BATCH_SIZE}条)...")
        print("-" * 70)

        while True:
            print(f"\n📦 第{batch_num + 1}批请求...")

            data = await client.get_spot_klines(
                symbol="ETHUSDC",          # 注意：使用ETHUSDC
                interval="30m",
                startTime=current_start,
                endTime=end_ts,
                limit=BATCH_SIZE
            )

            if not data or (isinstance(data, dict) and "error" in data):
                print(f"   ❌ 获取失败或无数据")
                break

            all_data_30m.extend(data)
            batch_num += 1

            received = len(data) if isinstance(data, list) else 0
            total = len(all_data_30m)
            print(f"   ✅ 本批获取: {received} 条 | 累计: {total} 条")

            if received < BATCH_SIZE:
                print(f"   🏁 返回数据少于{BATCH_SIZE}条，已到末尾")
                break

            last_timestamp = data[-1][0]
            current_start = last_timestamp + 1

            await asyncio.sleep(0.2)

        if not all_data_30m:
            print("\n❌ 未获取到任何30m数据")
            return

        # 处理30m数据
        df_30m = pd.DataFrame(all_data_30m, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore"
        ])

        df_30m["open_time"] = pd.to_datetime(df_30m["open_time"], unit="ms")
        df_30m = df_30m.drop_duplicates(subset=["open_time"])
        df_30m = df_30m.sort_values("open_time").reset_index(drop=True)

        for col in ["open", "high", "low", "close", "volume"]:
            df_30m[col] = pd.to_numeric(df_30m[col], errors='coerce')

        df_30m = df_30m[["open_time", "open", "high", "low", "close", "volume"]]

        # 保存30m数据
        save_path_30m = r"trading_system\data\binance_history\ETHUSDC_30m.csv"
        os.makedirs(os.path.dirname(save_path_30m), exist_ok=True)
        df_30m.to_csv(save_path_30m, index=False)

        print("\n" + "=" * 80)
        print("✅ 30分钟K线数据下载完成！")
        print("=" * 80)
        print(f"\n📊 30m数据统计:")
        print(f"   总K线数: {len(df_30m)} 条 (去重后)")
        print(f"   请求批次: {batch_num} 批")

        if len(df_30m) > 0:
            time_start = df_30m['open_time'].iloc[0]
            time_end = df_30m['open_time'].iloc[-1]
            actual_days = (time_end - time_start).days

            print(f"\n📅 时间范围:")
            print(f"   开始: {time_start}")
            print(f"   结束: {time_end}")
            print(f"   覆盖: {actual_days} 天 (~{actual_days/30:.1f}个月)")

            print(f"\n💰 价格范围:")
            print(f"   最高: ${df_30m['high'].max():.2f}")
            print(f"   最低: ${df_30m['low'].min():.2f}")
            print(f"   最新: ${df_30m['close'].iloc[-1]:.2f}")

        print(f"\n💾 30m数据已保存到: {save_path_30m}")
        print(f"   文件大小: {os.path.getsize(save_path_30m) / 1024:.1f} KB")

        # ===== 2. 下载日线数据 =====
        print(f"\n{'='*80}")
        print("📊 第2步: 下载日线K线数据（用于趋势判断）")
        print(f"{'='*80}")

        daily_data = await client.get_spot_klines(
            symbol="ETHUSDC",
            interval="1d",
            startTime=start_ts,
            endTime=end_ts,
            limit=1000
        )

        if daily_data and not (isinstance(daily_data, dict) and "error" in daily_data):
            daily_df = pd.DataFrame(daily_data, columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_volume", "trades", "taker_buy_base",
                "taker_buy_quote", "ignore"
            ])

            daily_df["open_time"] = pd.to_datetime(daily_df["open_time"], unit="ms")
            for col in ["open", "high", "low", "close", "volume"]:
                daily_df[col] = pd.to_numeric(daily_df[col], errors='coerce')
            daily_df = daily_df[["open_time", "open", "high", "low", "close", "volume"]]

            daily_save_path = r"trading_system\data\binance_history\ETHUSDC_1d.csv"
            daily_df.to_csv(daily_save_path, index=False)
            
            print(f"\n✅ 日线数据已保存: {daily_save_path} ({len(daily_df)}条)")
            
            if len(daily_df) > 0:
                print(f"   日线时间范围: {daily_df['open_time'].iloc[0]} ~ {daily_df['open_time'].iloc[-1]}")
        else:
            print("⚠️  日线数据获取失败（非关键错误，回测仍可进行）")

        # ===== 总结 =====
        print("\n" + "=" * 80)
        print("🎉 所有数据下载完成！")
        print("=" * 80)
        
        print(f"\n📁 文件清单:")
        print(f"   ✅ {save_path_30m}")
        if 'daily_save_path' in dir():
            print(f"   ✅ {daily_save_path}")
        
        print(f"\n🚀 下一步操作:")
        print(f"   运行回测: python run_ethusdc_v2_backtest.py")
        print(f"   或手动运行: python trading_system/backtest/run_backtest.py --symbol ETHUSDC ...")
        
    except Exception as e:
        print(f"\n❌ 下载出错: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.close()
        print("\n✨ 下载任务完成！")


if __name__ == "__main__":
    asyncio.run(download_ethusdc_90d())
