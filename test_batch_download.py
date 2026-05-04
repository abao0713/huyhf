import asyncio
from trading_system.okx.client import BinanceRestClient
from datetime import datetime
import pandas as pd

async def test_batch_download_180d():
    """测试180天30m K线数据的分批下载功能"""

    print("=" * 70)
    print("测试：180天 ETHUSDT 30分钟K线数据 分批下载")
    print("=" * 70)

    start_date = "2026-03-04"
    end_date = "2026-05-03"

    print(f"\n📅 目标时间范围: {start_date} ~ {end_date}")
    print(f"   预期天数: 约60天")
    print(f"   预期K线数: ~2880根 (60天 × 24小时 × 2根/小时)")

    client = BinanceRestClient()

    try:
        start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
        end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)

        print(f"\n⏰ 时间戳范围: {start_ts} ~ {end_ts}")

        all_data = []
        current_start = start_ts
        batch_num = 0
        BATCH_SIZE = 1000

        print(f"\n🔄 开始分批下载 (每批最多{BATCH_SIZE}条)...")
        print("-" * 70)

        while True:
            print(f"\n📦 第{batch_num + 1}批请求:")
            print(f"   startTime: {current_start}")
            print(f"   endTime: {end_ts}")

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

        print("\n" + "=" * 70)
        print("📊 下载结果统计")
        print("=" * 70)

        if not all_data:
            print("❌ 未获取到任何数据")
            return

        df = pd.DataFrame(all_data, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore"
        ])

        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        df = df.drop_duplicates(subset=["open_time"])
        df = df.sort_values("open_time").reset_index(drop=True)

        print(f"\n✅ 总获取K线数: {len(df)} 条 (去重后)")
        print(f"   请求批次数: {batch_num} 批")

        if len(df) > 0:
            time_start = df['open_time'].iloc[0]
            time_end = df['open_time'].iloc[-1]
            actual_days = (time_end - time_start).days

            print(f"\n📅 实际时间范围:")
            print(f"   开始: {time_start}")
            print(f"   结束: {time_end}")
            print(f"   覆盖天数: {actual_days} 天")

            for col in ["open", "high", "low", "close"]:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            print(f"\n💰 价格范围:")
            print(f"   最高: ${df['high'].max():.2f}")
            print(f"   最低: ${df['low'].min():.2f}")
            print(f"   首条: ${df['open'].iloc[0]:.2f}")
            print(f"   末条: ${df['close'].iloc[-1]:.2f}")

            print(f"\n📈 数据预览:")
            print(f"\n前5行:\n{df.head()}")
            print(f"\n后5行:\n{df.tail()}")

            expected_klines = actual_days * 24 * 2
            coverage = (len(df) / expected_klines) * 100 if expected_klines > 0 else 0
            print(f"\n📊 数据完整度: {coverage:.1f}% ({len(df)}/{expected_klines})")

            if len(df) >= 2000:
                print("\n🎉 成功！已获取足够多的180天数据用于回测")
            else:
                print(f"\n⚠️  数据量偏少，可能需要调整时间范围或检查API限制")

    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_batch_download_180d())
