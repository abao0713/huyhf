import asyncio
from trading_system.okx.client import BinanceRestClient
from datetime import datetime, timedelta
import pandas as pd
import os


def get_date_range(days=60):
    """获取日期范围"""
    today = datetime.now()
    end_date = today.strftime("%Y-%m-%d")
    start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    return start_date, end_date


async def download_ethusdt_180d():
    """使用分批下载功能获取ETHUSDT 60天K线数据"""

    # start_date = "2026-03-04"
    # end_date = "2026-05-03"
    start_date, end_date = get_date_range(days=180)
    print("=" * 70)
    print("📥 下载 ETHUSDT 完整K线数据（使用分批下载）")
    print("=" * 70)
    print(f"\n📅 目标时间范围: {start_date} ~ {end_date}")
    print(f"   预期天数: ~60天")
    print(f"   预期K线数: ~2880根 (60天 × 24小时 × 2根/小时)")

    client = BinanceRestClient()

    try:
        start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
        end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)

        all_data = []
        current_start = start_ts
        batch_num = 0
        BATCH_SIZE = 1000

        print(f"\n🔄 开始分批下载 (每批最多{BATCH_SIZE}条)...")
        print("-" * 70)

        while True:
            print(f"\n📦 第{batch_num + 1}批请求...")

            data = await client.get_spot_klines(
                symbol="ETHUSDT",
                interval="30m",
                startTime=current_start,
                endTime=end_ts,
                limit=BATCH_SIZE
            )

            if not data or (isinstance(data, dict) and "error" in data):
                print(f"   ❌ 获取失败或无数据")
                break

            all_data.extend(data)
            batch_num += 1

            received = len(data) if isinstance(data, list) else 0
            total = len(all_data)
            print(f"   ✅ 本批获取: {received} 条 | 累计: {total} 条")

            if received < BATCH_SIZE:
                print(f"   🏁 返回数据少于{BATCH_SIZE}条，已到末尾")
                break

            last_timestamp = data[-1][0]
            current_start = last_timestamp + 1

            await asyncio.sleep(0.2)

        if not all_data:
            print("\n❌ 未获取到任何数据")
            return

        df = pd.DataFrame(all_data, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore"
        ])

        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        df = df.drop_duplicates(subset=["open_time"])
        df = df.sort_values("open_time").reset_index(drop=True)

        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        df = df[["open_time", "open", "high", "low", "close", "volume"]]

        print("\n" + "=" * 70)
        print("✅ 数据下载完成！")
        print("=" * 70)
        print(f"\n📊 统计信息:")
        print(f"   总K线数: {len(df)} 条 (去重后)")
        print(f"   请求批次: {batch_num} 批")

        if len(df) > 0:
            time_start = df['open_time'].iloc[0]
            time_end = df['open_time'].iloc[-1]
            actual_days = (time_end - time_start).days

            print(f"\n📅 时间范围:")
            print(f"   开始: {time_start}")
            print(f"   结束: {time_end}")
            print(f"   覆盖: {actual_days} 天")

            print(f"\n💰 价格范围:")
            print(f"   最高: ${df['high'].max():.2f}")
            print(f"   最低: ${df['low'].min():.2f}")

        save_path = r"trading_system\data\binance_history\ETHUSDT_30m.csv"
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        df.to_csv(save_path, index=False)

        print(f"\n💾 数据已保存到: {save_path}")
        print(f"   文件大小: {os.path.getsize(save_path) / 1024:.1f} KB")

        daily_data = await client.get_spot_klines(
            symbol="ETHUSDT",
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

            daily_save_path = r"trading_system\data\binance_history\ETHUSDT_1d.csv"
            daily_df.to_csv(daily_save_path, index=False)
            print(f"✅ 日线数据已保存: {daily_save_path} ({len(daily_df)}条)")
        else:
            print("⚠️  日线数据获取失败（非关键错误）")

    except Exception as e:
        print(f"\n❌ 下载出错: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.close()
        print("\n✨ 下载任务完成！")

if __name__ == "__main__":
    asyncio.run(download_ethusdt_180d())
